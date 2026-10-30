"""Actual SDK serialization with fake HTTP and network denied; no provider canary."""

import json
import socket

import httpx
import pytest
from agent_harness.contracts import ModelMessage, ModelRequest, ModelResponse, Usage
from agent_harness.gemini import ENDPOINT, MODEL, PROVIDER, GeminiTransport
from olist_support.workflow import GatewayPlanner, RoutingGatewayPlanner
from test_olist_workflow import REQUEST, context


@pytest.mark.parametrize(
    "planner_type,versioned", [(GatewayPlanner, False), (RoutingGatewayPlanner, True)]
)
def test_actual_sdk_wire_preserves_version_schema_and_never_sends_source_labels(
    monkeypatch, planner_type, versioned
):
    class Capture:
        request = None

        def generate(self, context, request):
            self.request = request
            content = {"intent": "review", "requested_minor": None}
            if versioned:
                content["routing_version"] = "olist-intent-routing-v2"
            return ModelResponse(
                provider=request.provider,
                model=request.model,
                output=ModelMessage(role="assistant", content=json.dumps(content)),
                usage=Usage(
                    model_calls=0, input_tokens=0, output_tokens=0, cost=None, cost_currency=None
                ),
            )

    capture = Capture()
    template = ModelRequest(
        provider=PROVIDER,
        model=MODEL,
        endpoint=ENDPOINT,
        messages=(ModelMessage(role="user", content="unused"),),
        parameters={"temperature": 0.0, "max_output_tokens": 512, "thinking_level": "LOW"},
    )
    c = context()
    decision = planner_type(capture, template).plan(c, REQUEST)
    assert decision.failure_code is None
    seen = []

    def handler(request):
        body = json.loads(request.content)
        config = body["generationConfig"]
        assert config["maxOutputTokens"] == min(c.budget.max_tokens, 512)
        assert ("routing_version" in config["responseJsonSchema"]["properties"]) is versioned
        assert body["contents"] == [{"parts": [{"text": REQUEST.text}], "role": "user"}]
        assert not body.get("tools")
        seen.append(body)
        text = {"intent": "review", "requested_minor": None}
        if versioned:
            text["routing_version"] = "olist-intent-routing-v2"
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {"role": "model", "parts": [{"text": json.dumps(text)}]},
                        "finishReason": "STOP",
                    }
                ],
                "usageMetadata": {
                    "promptTokenCount": 3,
                    "candidatesTokenCount": 5,
                    "totalTokenCount": 8,
                },
            },
        )

    def deny(*args, **kwargs):
        raise AssertionError("network forbidden during SDK test")

    monkeypatch.setattr(socket, "create_connection", deny)
    monkeypatch.setattr(socket, "getaddrinfo", deny)
    monkeypatch.setattr(socket.socket, "connect", deny)
    transport = GeminiTransport(
        "invented-sdk-only-key",
        free_tier_confirmed=True,
        http_transport=httpx.MockTransport(handler),
    )
    response = transport.generate(capture.request)
    assert response.failure is None and len(seen) == 1
