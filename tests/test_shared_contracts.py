"""F2 acceptance checks: dispatch boundaries, wire identity and offline wiring."""

import json
import socket
from datetime import datetime
from decimal import Decimal

import pytest
from agent_harness.contracts import (
    AgentInput,
    AgentResult,
    Failure,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    PublicObservation,
    RunContext,
    ToolCall,
    ToolSchema,
    Usage,
)
from agent_harness.evaluation import CaseReport, EvalCase, FaultScenario, ScoreResult, run_case
from agent_harness.offline_example import (
    FakeAgent,
    FakeGateway,
    FakeScorer,
    example_case,
    example_context,
)
from pydantic import ValidationError


def context() -> RunContext:
    return example_context("test-revision", "test-lock-hash")


def test_fake_case_runs_without_network_or_services(monkeypatch) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("The offline example tried to use the network")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setenv("DATABASE_URL", "invalid://must-not-be-used")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    gateway = FakeGateway()
    report = run_case(context(), example_case(), FakeAgent(), gateway, FakeScorer())
    assert report.result.output == "HELLO, SHARED CONTRACTS"
    assert report.result.outcome == "completed"
    assert report.scores[0].value == 1.0
    assert report.source_kind == "synthetic" and report.context.mode == "offline_fake"
    assert len(gateway.requests) == 1
    assert CaseReport.model_validate_json(report.model_dump_json()) == report


def test_agent_and_gateway_do_not_receive_labels_or_hidden_state() -> None:
    delivered = []

    class CapturingAgent(FakeAgent):
        def run(self, context, input, gateway):
            delivered.append((context, input))
            assert isinstance(input, AgentInput)
            return super().run(context, input, gateway)

    case = example_case()
    changed = EvalCase.model_validate_json(case.model_dump_json())
    changed = changed.model_copy(
        update={
            "expected": changed.expected.model_copy(update={"output": "private-answer-marker"}),
            "hidden_state": {"private_marker": "hidden-state-marker"},
        }
    )
    gateway = FakeGateway()
    report = run_case(context(), changed, CapturingAgent(), gateway, FakeScorer())
    wire = delivered[0][0].model_dump_json() + delivered[0][1].model_dump_json()
    wire += gateway.requests[0].model_dump_json()
    assert "private-answer-marker" not in wire and "hidden-state-marker" not in wire
    assert "expected" not in json.loads(delivered[0][1].model_dump_json())
    assert report.result.output == "HELLO, SHARED CONTRACTS"
    assert report.scores[0].value == 0.0  # The evaluator saw the changed label.
    with pytest.raises(ValidationError):
        AgentInput.model_validate_json(changed.model_dump_json())


@pytest.mark.parametrize("key", ["expected", "expected_output", "hidden_state", "metadata"])
def test_public_input_rejects_evaluator_fields_at_root_and_observation(key) -> None:
    with pytest.raises(ValidationError, match="Extra inputs"):
        AgentInput.model_validate_json(json.dumps({"request": "hello", key: "private"}))
    with pytest.raises(ValidationError, match="Extra inputs"):
        AgentInput.model_validate_json(
            json.dumps(
                {
                    "request": "hello",
                    "observations": [{"reference": "source:1", "text": "public", key: "private"}],
                }
            )
        )
    assert PublicObservation(reference="source:1", text="public").text == "public"


def test_review_usage_evidence_and_typed_failure_survive_round_trip() -> None:
    normal = run_case(context(), example_case(), FakeAgent(), FakeGateway(), FakeScorer()).result
    review = AgentResult.model_validate_json(
        normal.model_copy(
            update={
                "outcome": "review_required",
                "review_ref": "invented-review:1",
                "state_change_refs": ("invented-ledger:1",),
                "usage": Usage(
                    model_calls=1,
                    input_tokens=12,
                    output_tokens=3,
                    cost=Decimal("0.00125"),
                    cost_currency="USD",
                ),
            }
        ).model_dump_json()
    )
    assert AgentResult.model_validate_json(review.model_dump_json()) == review
    timeout = Failure(stage="model", code="timeout", message="Invented timeout", retryable=True)
    report = run_case(context(), example_case(), FakeAgent(), FakeGateway(timeout), FakeScorer())
    restored = CaseReport.model_validate_json(report.model_dump_json())
    assert restored.result.failure == timeout and restored.result.outcome == "failed"
    assert restored.scores[0].value == 0.0
    unknown = Usage(
        model_calls=1, input_tokens=None, output_tokens=None, cost=None, cost_currency=None
    )
    assert Usage.model_validate_json(unknown.model_dump_json()) == unknown
    score_error = ScoreResult(
        metric="test",
        scorer_version="v1",
        eligible=True,
        failure=Failure(
            stage="scorer", code="scorer_error", message="Invented scorer error", retryable=False
        ),
    )
    assert ScoreResult.model_validate_json(score_error.model_dump_json()) == score_error
    category = ScoreResult(
        metric="fault_outcome", scorer_version="v1", eligible=False, category="not_applicable"
    )
    assert ScoreResult.model_validate_json(category.model_dump_json()) == category


def request() -> ModelRequest:
    return ModelRequest(
        provider="fake",
        endpoint="in-process",
        model="uppercase-v1",
        model_revision="rev1",
        messages=(
            ModelMessage(role="system", content="Keep  whitespace\n"),
            ModelMessage(role="user", content="hello"),
            ModelMessage(
                role="assistant",
                tool_calls=(
                    ToolCall(
                        call_id="call-1",
                        name="lookup",
                        arguments={"key": "invented"},
                    ),
                ),
            ),
            ModelMessage(role="tool", tool_call_id="call-1", tool_name="lookup", content="found"),
        ),
        parameters={"temperature": 0, "max_output_tokens": 20},
        tools=(
            ToolSchema(
                name="lookup",
                description="Read invented data",
                parameters={"type": "object", "properties": {}},
            ),
        ),
        tool_choice="auto",
        output_schema={"type": "string"},
    )


def test_complete_model_request_and_response_round_trip_and_canonical_identity() -> None:
    original = request()
    assert ModelRequest.model_validate_json(original.model_dump_json()) == original
    reordered = original.model_copy(
        update={
            "parameters": {"max_output_tokens": 20, "temperature": 0},
        }
    )
    assert original.fingerprint() == reordered.fingerprint()
    response = ModelResponse(
        provider="fake",
        model="uppercase-v1",
        model_revision="rev1",
        provider_request_id="invented-request-1",
        output=original.messages[2],
        finish_reason="tool_calls",
        usage=Usage(
            model_calls=1, input_tokens=None, output_tokens=None, cost=None, cost_currency=None
        ),
    )
    assert ModelResponse.model_validate_json(response.model_dump_json()) == response


@pytest.mark.parametrize(
    "change",
    [
        {"provider": "other"},
        {"endpoint": "other"},
        {"model": "other"},
        {"model_revision": "rev2"},
        {"parameters": {"temperature": 1}},
        {"output_schema": {"type": "number"}},
        {"tools": ()},
        {"tool_choice": "none"},
        {"messages": (ModelMessage(role="user", content="hello "),)},
        {"messages": tuple(reversed(request().messages))},
    ],
)
def test_request_identity_changes_with_model_visible_or_route_changes(change) -> None:
    original = request()
    assert original.fingerprint() != original.model_copy(update=change).fingerprint()


@pytest.mark.parametrize(
    "changes",
    [
        {"seed": "0"},
        {"seed": True},
        {"clock": datetime(2026, 1, 1)},
        {"deadline": context().clock},
        {"schema_version": 2},
    ],
)
def test_invalid_run_context_is_rejected(changes) -> None:
    payload = context().model_dump()
    payload.update(changes)
    with pytest.raises(ValidationError):
        RunContext.model_validate(payload)


def test_invalid_result_score_usage_and_model_shapes_are_rejected() -> None:
    normal = run_case(context(), example_case(), FakeAgent(), FakeGateway(), FakeScorer()).result
    for update in (
        {"outcome": "review_required"},
        {"outcome": "failed"},
        {"review_ref": "unexpected"},
    ):
        with pytest.raises(ValidationError):
            AgentResult.model_validate_json(normal.model_copy(update=update).model_dump_json())
    with pytest.raises(ValidationError):
        Usage(model_calls=-1, input_tokens=None, output_tokens=None, cost=None, cost_currency=None)
    with pytest.raises(ValidationError):
        Usage(
            model_calls=1,
            input_tokens=None,
            output_tokens=None,
            cost=Decimal("1"),
            cost_currency=None,
        )
    with pytest.raises(ValidationError):
        ScoreResult(metric="test", scorer_version="v1", eligible=True, value=float("nan"))
    with pytest.raises(ValidationError):
        ScoreResult(metric="test", scorer_version="v1", eligible=True, value=1.0, category="pass")
    with pytest.raises(ValidationError):
        ModelMessage(role="tool", content="missing identifiers")
    with pytest.raises(ValidationError):
        ModelResponse(provider="fake", model="fake", usage=normal.usage)


def test_wrong_identity_is_rejected_before_dispatch_or_scoring() -> None:
    gateway = FakeGateway()
    with pytest.raises(ValueError, match="case identity"):
        run_case(
            context().model_copy(update={"case_id": "other"}),
            example_case(),
            FakeAgent(),
            gateway,
            FakeScorer(),
        )
    assert gateway.requests == []

    class WrongAgent(FakeAgent):
        def run(self, context, input, gateway):
            return super().run(context, input, gateway).model_copy(update={"trial_id": "other"})

    class MustNotScore:
        def score(self, case, result):
            raise AssertionError("Mismatched results reached the scorer")

    with pytest.raises(ValueError, match="result identity"):
        run_case(context(), example_case(), WrongAgent(), gateway, MustNotScore())


def test_scorer_errors_and_empty_evidence_cannot_silently_pass() -> None:
    class BrokenScorer:
        def score(self, case, result):
            raise RuntimeError("invented scorer bug")

    with pytest.raises(RuntimeError, match="scorer bug"):
        run_case(context(), example_case(), FakeAgent(), FakeGateway(), BrokenScorer())

    class EmptyScorer:
        def score(self, case, result):
            return ()

    with pytest.raises(ValidationError):
        run_case(context(), example_case(), FakeAgent(), FakeGateway(), EmptyScorer())


def test_fake_gateway_and_fault_definitions_do_not_claim_unimplemented_modes() -> None:
    with pytest.raises(ValueError, match="offline_fake"):
        run_case(
            context().model_copy(update={"mode": "fresh_candidate"}),
            example_case(),
            FakeAgent(),
            FakeGateway(),
            FakeScorer(),
        )
    fault = FaultScenario(
        scenario_id="invented-timeout",
        target="model",
        timing="after_dispatch",
        recoverable=True,
        expected_safe_behavior="typed timeout",
        required_invariants=("no claimed completion",),
    )
    assert FaultScenario.model_validate_json(fault.model_dump_json()) == fault
    with pytest.raises(NotImplementedError, match="H7"):
        run_case(
            context(),
            example_case().model_copy(update={"faults": (fault,)}),
            FakeAgent(),
            FakeGateway(),
            FakeScorer(),
        )
