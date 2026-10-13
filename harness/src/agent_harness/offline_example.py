"""Executable F2 wiring example. Invented input, no provider, database or telemetry."""

import argparse
import hashlib
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from agent_harness.contracts import (
    AgentInput,
    AgentResult,
    Budget,
    CandidateVersions,
    EvidenceReference,
    Failure,
    ModelGateway,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    RunContext,
    Usage,
)
from agent_harness.evaluation import (
    CaseReport,
    EvalCase,
    ExpectedResult,
    ScoreResult,
    run_case,
)


class FakeGateway:
    """Deterministic text-only test double; cannot claim fresh or replay evidence."""

    def __init__(self, failure: Failure | None = None) -> None:
        self.failure = failure
        self.requests: list[ModelRequest] = []

    def generate(self, context: RunContext, request: ModelRequest) -> ModelResponse:
        context = RunContext.model_validate_json(context.model_dump_json())
        request = ModelRequest.model_validate_json(request.model_dump_json())
        if context.mode != "offline_fake":
            raise ValueError("FakeGateway requires offline_fake mode")
        if (request.provider, request.model, request.endpoint) != (
            "fake",
            "uppercase-v1",
            "in-process",
        ):
            raise ValueError("FakeGateway only supports its explicit fake route")
        if request.tools or request.output_schema is not None or request.tool_choice is not None:
            raise ValueError("FakeGateway does not implement tools or structured output")
        if len(request.messages) != 1 or request.messages[0].role != "user":
            raise ValueError("FakeGateway expects one user message")
        content = request.messages[0].content
        if content is None or request.parameters != {"temperature": 0}:
            raise ValueError("FakeGateway requires text and its fixed generation parameters")
        self.requests.append(request)
        usage = Usage(
            model_calls=1, input_tokens=0, output_tokens=0, cost=Decimal("0"), cost_currency="USD"
        )
        return ModelResponse(
            provider="fake",
            model="uppercase-v1",
            usage=usage,
            failure=self.failure,
            output=(
                None
                if self.failure
                else ModelMessage(
                    role="assistant",
                    content=content.upper(),
                )
            ),
            finish_reason=None if self.failure else "stop",
        )


class FakeAgent:
    def run(self, context: RunContext, input: AgentInput, gateway: ModelGateway) -> AgentResult:
        # Validate the public contract before forwarding even the first message.
        input = AgentInput.model_validate_json(input.model_dump_json())
        returned = gateway.generate(
            context,
            ModelRequest(
                provider="fake",
                endpoint="in-process",
                model="uppercase-v1",
                messages=(ModelMessage(role="user", content=input.request),),
                parameters={"temperature": 0},
            ),
        )
        response = ModelResponse.model_validate_json(returned.model_dump_json())
        return AgentResult(
            run_id=context.run_id,
            case_id=context.case_id,
            trial_id=context.trial_id,
            decision="return_text" if response.failure is None else "stop",
            outcome="completed" if response.failure is None else "failed",
            output=None if response.output is None else response.output.content,
            usage=response.usage,
            failure=response.failure,
            evidence=(EvidenceReference(reference=f"model:{context.run_id}:1", kind="model"),),
            trace_ref=f"offline:{context.run_id}",
        )


class FakeScorer:
    """Exact text/outcome check only; domain state scorers are H6 work."""

    def score(self, case: EvalCase, result: AgentResult) -> tuple[ScoreResult, ...]:
        correct = (
            result.outcome == case.expected.outcome
            and result.output == case.expected.output
            and result.decision in case.expected.allowed_decisions
            and (result.review_ref is not None) == case.expected.required_review
        )
        return (
            ScoreResult(
                metric="fake_case_correct",
                scorer_version=case.scorer_version,
                eligible=True,
                value=float(correct),
                evidence=(EvidenceReference(reference=f"score:{case.case_id}", kind="score"),),
            ),
        )


def example_case() -> EvalCase:
    return EvalCase(
        case_id="fake-text-001",
        input=AgentInput(request="hello, shared contracts"),
        snapshot_ref="invented-text-v1",
        source_kind="synthetic",
        source_version="invented-v1",
        policy_version="fake-text-policy-v1",
        scorer_version="fake-exact-text-v1",
        expected=ExpectedResult(
            outcome="completed",
            output="HELLO, SHARED CONTRACTS",
            eligible_for_autonomy=True,
            required_review=False,
            allowed_decisions=("return_text",),
            expected_state_changes={},
        ),
        hidden_state={"private_marker": "evaluator-only-fixture"},
        risk="none",
        slices=("contract-wiring",),
    )


def example_context(code_revision: str, environment_lock: str) -> RunContext:
    clock = datetime(2026, 1, 1, tzinfo=UTC)
    return RunContext(
        run_id="fake-run-001",
        tenant_id="invented-tenant",
        agent_id="fake-uppercase-v1",
        case_id="fake-text-001",
        trial_id="trial-1",
        business_event_id="invented-event-001",
        mode="offline_fake",
        clock=clock,
        deadline=clock + timedelta(seconds=30),
        seed=0,
        budget=Budget(
            max_model_calls=1, max_tokens=100, max_cost=Decimal("0"), cost_currency="USD"
        ),
        versions=CandidateVersions(
            code_revision=code_revision,
            candidate="fake-uppercase-v1",
            data_snapshot="invented-text-v1",
            policy="fake-text-policy-v1",
            environment_lock=environment_lock,
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--code-revision", required=True, help="Actual source revision being exercised"
    )
    parser.add_argument(
        "--lockfile", type=Path, required=True, help="Hash the actual environment lock"
    )
    args = parser.parse_args()
    lock_hash = hashlib.sha256(args.lockfile.read_bytes()).hexdigest()
    report = run_case(
        example_context(args.code_revision, lock_hash),
        example_case(),
        FakeAgent(),
        FakeGateway(),
        FakeScorer(),
    )
    # Verify the wire representation before printing an evaluator report.
    restored = CaseReport.model_validate_json(report.model_dump_json())
    print(restored.model_dump_json(indent=2))
    if restored.scores[0].value != 1.0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
