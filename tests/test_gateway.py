"""H2: actual pinned SDK wire, contract failures, identity and attempt separation."""

import base64
import json
import socket
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest
from agent_harness.contracts import ModelMessage, ModelPart, ModelRequest, ModelResponse, ToolSchema
from agent_harness.gateway import ModelExchange, ProviderGateway
from agent_harness.gemini import ENDPOINT, MODEL, PROVIDER, GeminiTransport
from agent_harness.offline_example import example_context
from pydantic import ValidationError


def context(trial="trial-1", mode="fresh_candidate"):
    return example_context("invented-source", "invented-lock").model_copy(
        update={"mode": mode, "trial_id": trial}
    )


def request(**changes):
    value = ModelRequest(
        provider=PROVIDER,
        endpoint=ENDPOINT,
        model=MODEL,
        messages=(ModelMessage(role="user", content="invented prompt"),),
        parameters={"temperature": 0, "max_output_tokens": 128},
    )
    return value.model_copy(update=changes)


def wire(parts=None, **changes):
    value = {
        "responseId": "invented-response",
        "modelVersion": MODEL,
        "candidates": [
            {
                "content": {"role": "model", "parts": parts or [{"text": "invented"}]},
                "finishReason": "STOP",
            }
        ],
        "usageMetadata": {
            "promptTokenCount": 12,
            "candidatesTokenCount": 3,
            "thoughtsTokenCount": 7,
            "totalTokenCount": 22,
            "cachedContentTokenCount": 2,
        },
    }
    value.update(changes)
    return value


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("H2 offline test attempted a network connection")

    monkeypatch.setattr(socket.socket, "connect", forbidden)


def gateway(handler):
    return ProviderGateway(
        GeminiTransport(
            "invented-key", free_tier_confirmed=True, http_transport=httpx.MockTransport(handler)
        )
    )


def test_real_sdk_text_usage_no_hidden_retry_and_safe_config():
    seen = []

    def handler(http_request):
        seen.append(http_request)
        return httpx.Response(200, json=wire())

    result = gateway(handler).generate(context(), request())
    assert result.failure is None and result.output.content == "invented"
    assert result.usage.model_calls == 1 and result.usage.input_tokens == 12
    assert result.usage.output_tokens == 10 and result.provider_usage["thinking_tokens"] == 7
    assert result.usage.cost is None and result.model_revision == MODEL
    assert result.provider_request_id == "invented-response" and len(seen) == 1
    assert str(seen[0].url) == ENDPOINT + "/v1beta/models/" + MODEL + ":generateContent"
    payload = json.loads(seen[0].content)
    assert payload["generationConfig"]["candidateCount"] == 1
    assert payload["generationConfig"]["maxOutputTokens"] == 128


@pytest.mark.parametrize("payload", ['{"answer":"42"}', '{"answer":42,"answer":43}', "NaN"])
def test_json_output_is_locally_validated_without_coercion(payload):
    schema = {
        "type": "object",
        "properties": {"answer": {"const": 42}},
        "required": ["answer"],
        "additionalProperties": False,
    }
    result = gateway(lambda _: httpx.Response(200, json=wire([{"text": payload}]))).generate(
        context(), request(output_schema=schema)
    )
    assert result.failure.code == "invalid_response" and result.usage.model_calls == 1


def tool_schema():
    return ToolSchema(
        name="lookup",
        description="Invented read",
        parameters={
            "type": "object",
            "properties": {"id": {"const": "invented-1"}},
            "required": ["id"],
            "additionalProperties": False,
        },
    )


def test_function_round_trip_preserves_order_signature_ids_and_schema():
    signature = base64.b64encode(b"invented-opaque-signature").decode()
    seen = []
    parts = [
        {"text": "Checking."},
        {
            "functionCall": {"name": "lookup", "args": {"id": "invented-1"}, "id": "provider-call"},
            "thoughtSignature": signature,
        },
    ]

    def handler(http_request):
        seen.append(json.loads(http_request.content))
        return httpx.Response(
            200, json=wire(parts if len(seen) == 1 else [{"text": '{"answer":42}'}])
        )

    instance = gateway(handler)
    first_request = request(tools=(tool_schema(),), tool_choice="lookup")
    first = instance.generate(context(), first_request)
    assert first.failure is None
    assert first.output.parts[1].thought_signature == signature
    followup = request(
        messages=(
            *first_request.messages,
            first.output,
            ModelMessage(
                role="tool",
                tool_call_id=first.output.tool_calls[0].call_id,
                tool_name="lookup",
                content='{"answer":42}',
            ),
        ),
        tools=(tool_schema(),),
        tool_choice="none",
        output_schema={
            "type": "object",
            "properties": {"answer": {"const": 42}},
            "required": ["answer"],
        },
    )
    second = instance.generate(context(), followup)
    assert second.failure is None and json.loads(second.output.content) == {"answer": 42}
    assert seen[1]["contents"][1]["parts"] == parts
    result_part = seen[1]["contents"][2]["parts"][0]["functionResponse"]
    assert result_part == {"id": "provider-call", "name": "lookup", "response": {"answer": 42}}
    assert [exchange.occurrence for exchange in instance.exchanges] == [1, 2]


@pytest.mark.parametrize(
    "status,code,retryable",
    [
        (400, "invalid_response", False),
        (401, "permission_denied", False),
        (403, "permission_denied", False),
        (408, "timeout", True),
        (429, "rate_limited", True),
        (503, "unavailable", True),
        (504, "timeout", True),
    ],
)
def test_http_failures_are_typed_redacted_and_never_retried(status, code, retryable):
    seen = []

    def handler(http_request):
        seen.append(http_request)
        return httpx.Response(
            status, json={"error": {"code": status, "message": "private-marker-invented-key"}}
        )

    instance = gateway(handler)
    response = instance.generate(context(), request())
    assert len(seen) == 1 and response.failure.code == code
    assert response.failure.retryable is retryable and response.usage.model_calls == 1
    assert "private-marker" not in response.model_dump_json()
    assert "invented-key" not in instance.exchanges[0].model_dump_json()


@pytest.mark.parametrize(
    "exception,code", [(httpx.ReadTimeout, "timeout"), (httpx.ConnectError, "unavailable")]
)
def test_transport_errors_are_safe(exception, code):
    def handler(http_request):
        raise exception("private-marker", request=http_request)

    result = gateway(handler).generate(context(), request())
    assert result.failure.code == code and "private-marker" not in result.model_dump_json()


@pytest.mark.parametrize(
    "changes",
    [
        {"candidates": []},
        {"candidates": [{"finishReason": "MAX_TOKENS"}]},
        {"candidates": [{"finishReason": "SAFETY"}]},
        {
            "candidates": [
                {"finishReason": "STOP", "content": {"role": "user", "parts": [{"text": "wrong"}]}}
            ]
        },
        {"usageMetadata": {"promptTokenCount": -1}},
    ],
)
def test_malformed_blocked_and_truncated_responses_fail(changes):
    result = gateway(lambda _: httpx.Response(200, json=wire(**changes))).generate(
        context(), request()
    )
    assert result.failure.code == "invalid_response" and result.output is None


@pytest.mark.parametrize(
    "changes",
    [
        {"provider": "other"},
        {"endpoint": "https://other.invalid"},
        {"model": "paid-model"},
        {"parameters": {"unknown": 1}},
        {"parameters": {"temperature": "0"}},
        {"parameters": {"max_output_tokens": True}},
        {"parameters": {"max_output_tokens": 513}},
        {"messages": (ModelMessage(role="developer", content="unsupported"),)},
        {
            "messages": (
                ModelMessage(role="tool", content="{}", tool_call_id="orphan", tool_name="lookup"),
            )
        },
        {"output_schema": {"$ref": "https://schemas.invalid/private"}},
        {"tool_choice": "required"},
    ],
)
def test_unsupported_requests_fail_before_dispatch(changes):
    def forbidden(_):
        pytest.fail("Invalid request was dispatched")

    result = gateway(forbidden).generate(context(), request(**changes))
    assert result.failure is not None and result.usage.model_calls == 0


@pytest.mark.parametrize("mode", ["offline_fake", "strict_replay"])
def test_live_gateway_never_dispatches_replay_or_fake(mode):
    instance = gateway(lambda _: pytest.fail("Mode boundary was bypassed"))
    result = instance.generate(context(mode=mode), request())
    assert result.failure.code == "permission_denied" and result.usage.model_calls == 0


def test_identical_requests_keep_distinct_responses_and_trial_occurrences():
    count = 0

    def handler(_):
        nonlocal count
        count += 1
        return httpx.Response(200, json=wire([{"text": f"answer-{count}"}]))

    instance = gateway(handler)
    for trial in ("trial-1", "trial-1", "trial-2"):
        instance.generate(context(trial), request())
    records = instance.exchanges
    assert [record.occurrence for record in records] == [1, 2, 1]
    assert len({record.request.fingerprint() for record in records}) == 1
    assert len({record.identity() for record in records}) == 3
    assert [record.response.output.content for record in records] == [
        "answer-1",
        "answer-2",
        "answer-3",
    ]
    assert ModelExchange.model_validate_json(records[0].model_dump_json()) == records[0]
    records[0].request.parameters["temperature"] = 2
    assert instance.exchanges[0].request.parameters["temperature"] == 0


def test_route_revision_mismatch_fails_and_concurrent_occurrences_are_unique():
    instance = gateway(lambda _: httpx.Response(200, json=wire(modelVersion="other-revision")))
    result = instance.generate(context(), request(model_revision="pinned-revision"))
    assert result.failure.code == "invalid_response"
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda _: instance.generate(context(), request()), range(8)))
    assert sorted(record.occurrence for record in instance.exchanges) == list(range(1, 10))


def test_model_wire_v1_and_mismatched_public_projection_are_rejected():
    payload = request().model_dump(mode="json")
    payload["serializer_version"] = 1
    with pytest.raises(ValidationError):
        ModelRequest.model_validate_json(json.dumps(payload))
    with pytest.raises(ValidationError):
        ModelMessage(role="assistant", content="changed", parts=(ModelPart(text="original"),))
    with pytest.raises(ValidationError):
        ModelPart(text="text", thought_signature="invalid-base64")


@pytest.mark.parametrize(
    "changes",
    [
        {"messages": (ModelMessage(role="user", content="invented prompt "),)},
        {"output_schema": {"type": "string"}},
        {"parameters": {"temperature": 1}},
        {"tools": (tool_schema(),)},
        {"tool_choice": "none"},
        {"model_revision": "revision"},
    ],
)
def test_model_visible_changes_have_distinct_fingerprints(changes):
    assert request().fingerprint() != request(**changes).fingerprint()


def test_valid_schema_local_reference_and_unknown_usage():
    schema = {
        "$defs": {"answer": {"const": 42}},
        "type": "object",
        "properties": {"answer": {"$ref": "#/$defs/answer"}},
        "required": ["answer"],
    }
    result = gateway(
        lambda _: httpx.Response(
            200,
            json=wire(
                [{"text": '{"answer":42}'}],
                usageMetadata={"promptTokenCount": 12, "candidatesTokenCount": 3},
            ),
        )
    ).generate(context(), request(output_schema=schema))
    assert result.failure is None and result.usage.input_tokens == 12
    assert result.usage.output_tokens is None and result.provider_usage["thinking_tokens"] is None


@pytest.mark.parametrize(
    "part",
    [
        {"functionCall": {"name": "lookup", "args": {"id": "wrong"}}},
        {"functionCall": {"name": "other", "args": {"id": "invented-1"}}},
        {"inlineData": {"mimeType": "image/png", "data": "aW52ZW50ZWQ="}},
    ],
)
def test_bad_function_arguments_undeclared_tools_and_modalities_fail_with_usage(part):
    result = gateway(lambda _: httpx.Response(200, json=wire([part]))).generate(
        context(), request(tools=(tool_schema(),))
    )
    assert result.failure.code == "invalid_response" and result.usage.input_tokens == 12
    assert result.usage.output_tokens == 10 and result.provider_request_id == "invented-response"


@pytest.mark.parametrize("status,content", [(200, b"not-json"), (302, b"redirect")])
def test_invalid_json_wire_and_redirect_do_not_trigger_another_request(status, content):
    seen = []

    def handler(http_request):
        seen.append(http_request)
        return httpx.Response(
            status, content=content, headers={"location": "https://other.invalid/private"}
        )

    result = gateway(handler).generate(context(), request())
    assert result.failure is not None and len(seen) == 1


def test_signature_and_part_order_are_in_request_identity():
    first = ModelMessage(
        role="assistant",
        content="AB",
        parts=(ModelPart(text="A", thought_signature="b25l"), ModelPart(text="B")),
    )
    changed = ModelMessage(
        role="assistant",
        content="AB",
        parts=(ModelPart(text="A", thought_signature="dHdv"), ModelPart(text="B")),
    )
    assert request(messages=(first,)).fingerprint() != request(messages=(changed,)).fingerprint()
    merged = ModelMessage(
        role="assistant", content="AB", parts=(ModelPart(text="AB", thought_signature="b25l"),)
    )
    assert request(messages=(first,)).fingerprint() != request(messages=(merged,)).fingerprint()


def test_mutating_transport_and_malformed_contract_cannot_corrupt_record():
    class MutatingTransport:
        def generate(self, sent):
            sent.parameters["temperature"] = 2
            return ModelResponse.model_construct(
                provider=PROVIDER, model=MODEL, usage={"bad": "contract"}
            )

    instance = ProviderGateway(MutatingTransport())
    result = instance.generate(context(), request())
    assert result.failure.code == "invalid_response"
    assert instance.exchanges[0].request.parameters["temperature"] == 0


def test_missing_confirmation_fails_without_client_and_response_unknowns_stay_unknown():
    with pytest.raises(ValueError):
        GeminiTransport("invented-key", free_tier_confirmed=False)
    result = gateway(lambda _: httpx.Response(200, json=wire(usageMetadata=None))).generate(
        context(), request()
    )
    assert result.failure is None and result.usage.output_tokens is None
    assert result.usage.input_tokens is None and result.usage.cost is None


@pytest.mark.parametrize("count", [True, "12"])
def test_numeric_usage_is_not_coerced_by_sdk(count):
    result = gateway(
        lambda _: httpx.Response(200, json=wire(usageMetadata={"promptTokenCount": count}))
    ).generate(context(), request())
    assert result.failure.code == "invalid_response" and result.usage.input_tokens is None


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_mutated_nested_nonfinite_input_is_rejected_before_json_can_turn_it_null(bad):
    value = request()
    value.parameters["temperature"] = bad
    instance = gateway(lambda _: pytest.fail("Invalid mutated request was dispatched"))
    with pytest.raises(ValidationError):
        instance.generate(context(), value)
    assert instance.exchanges == ()
