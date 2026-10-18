"""Trusted invented uppercase compositions; mock dispatch is never release evidence."""

import inspect
import json
import os
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Literal

from agent_harness.admission import GeminiFreeAdmission
from agent_harness.contracts import (
    AgentInput,
    AgentResult,
    Contract,
    ModelGateway,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    NonEmpty,
    RunContext,
    Usage,
)
from agent_harness.controls import ReservationQuote
from agent_harness.evaluation import EvalCase, ScoreResult
from agent_harness.fresh_recording import FreshComponents
from agent_harness.release_contracts import CandidateSpec, pin, sha256
from agent_harness.scorers import ScorerCompatibility, ScorerRegistry, ScorerSpec
from agent_harness.trial_runner import StateLease


class RecordingConfig(Contract):
    composition: Literal["invented-uppercase-mock", "invented-uppercase-gemini"]
    prompt: NonEmpty
    request: ModelRequest


class MockUppercase:
    def generate(self, request: ModelRequest, *, timeout_seconds: float = 30.0) -> ModelResponse:
        # New dispatch even for identical requests. No stored responses or lookup path.
        text = request.messages[-1].content
        return ModelResponse(
            provider=request.provider,
            model=request.model,
            model_revision=request.model_revision,
            output=ModelMessage(role="assistant", content=(text or "").upper()),
            usage=Usage(
                model_calls=1, input_tokens=0, output_tokens=0, cost=Decimal(0), cost_currency="USD"
            ),
        )


class MockAdmission:
    def quote(self, request: ModelRequest) -> ReservationQuote:
        return ReservationQuote(
            version="invented-mock-v1",
            max_tokens=100,
            max_cost=Decimal(0),
            currency="USD",
            evidence_ref="invented-offline-only",
        )


@dataclass(frozen=True)
class UppercaseAgent:
    state: Path
    config: RecordingConfig

    def run(self, context: RunContext, input: AgentInput, gateway: ModelGateway) -> AgentResult:
        request = self.config.request.model_copy(
            update={
                "messages": (
                    ModelMessage(role="system", content=self.config.prompt),
                    ModelMessage(role="user", content=input.request),
                )
            }
        )
        response = gateway.generate(context, request)
        output = response.output.content if response.output is not None else None
        self.state.write_text(json.dumps({"output": output}), encoding="utf-8")
        return AgentResult(
            run_id=context.run_id,
            case_id=context.case_id,
            trial_id=context.trial_id,
            decision="return_text" if response.failure is None else "stop",
            outcome="completed" if response.failure is None else "failed",
            output=output,
            usage=response.usage,
            failure=response.failure,
        )


@dataclass(frozen=True)
class UppercaseScorer:
    state: Path

    def score(self, case: EvalCase, result: AgentResult) -> tuple[ScoreResult, ...]:
        actual = json.loads(self.state.read_text(encoding="utf-8"))
        correct = actual == {"output": case.expected.output} and result.outcome == "completed"
        return tuple(
            ScoreResult(
                metric=name, scorer_version=case.scorer_version, eligible=True, value=float(value)
            )
            for name, value in (
                ("invented_correct", correct),
                ("invented_safe", True),
                ("invented_review", False),
            )
        )


@dataclass(frozen=True)
class UppercaseFactory:
    candidate: CandidateSpec
    config: RecordingConfig

    @property
    def origin(self) -> Literal["provider", "mock"]:
        return "mock" if self.config.composition == "invented-uppercase-mock" else "provider"

    def validate(self) -> None:
        if (
            self.candidate.prompt_sha256,
            self.candidate.model_config_sha256,
            self.candidate.tools_sha256,
        ) != (
            sha256(self.config.prompt.encode()),
            pin(self.config.request),
            sha256(b"no-tools"),
        ):
            raise ValueError("composition prompt/model/tools differ from candidate fingerprint")
        if (
            self.candidate.policy_sha256,
            self.candidate.scorer_sha256,
            self.candidate.environment_sha256,
        ) != (
            sha256(b"fake-text-policy-v1"),
            sha256(inspect.getsource(UppercaseScorer).encode()),
            sha256(b"h6-invented-files-v1:invented-state-v1"),
        ):
            raise ValueError("composition policy/scorer/environment differs from candidate")
        if self.config.request.tools or self.config.request.output_schema is not None:
            raise ValueError("invented uppercase composition supports text only")
        if self.config.composition == "invented-uppercase-mock" and (
            self.config.request.provider,
            self.config.request.model,
            self.config.request.endpoint,
        ) != ("mock", "invented-uppercase", "in-process"):
            raise ValueError("mock composition requires explicit mock route")

    def verify_runtime_sources(self, root: Path) -> None:
        """Built-in CLI composition requires the full harness inventory and lock bytes."""
        package = Path(__file__).parent
        for path in package.glob("*.py"):
            key = "harness/src/agent_harness/" + path.name
            if self.candidate.source_files.get(key) != sha256(path.read_bytes()):
                raise ValueError("source inventory omits or differs from executing harness")
        if sha256((root / "uv.lock").read_bytes()) != self.candidate.environment_lock:
            raise ValueError("execution lock differs from candidate")
        if self.candidate.source_files.get("uv.lock") != self.candidate.environment_lock:
            raise ValueError("source inventory must include the reviewed lock")

    def build(self, context: RunContext, state: StateLease) -> FreshComponents:
        self.validate()
        if not isinstance(state.access, str):
            raise TypeError("invented file state required")
        path = Path(state.access) / "state.json"
        registry = ScorerRegistry()
        registry.register(
            ScorerSpec(
                scorer_id="invented-trial-state",
                version="invented-trial-state-v1",
                compatible=(
                    ScorerCompatibility(
                        snapshot_ref="invented-text-v1", policy_version="fake-text-policy-v1"
                    ),
                ),
            ),
            UppercaseScorer(path),
        )
        if self.origin == "mock":
            return FreshComponents(
                UppercaseAgent(path, self.config), MockUppercase(), MockAdmission(), registry
            )
        # Explicit selected real composition only. Never imported by offline base-wheel paths.
        from agent_harness.gemini import GeminiTransport

        confirmed = os.environ.get("GEMINI_FREE_TIER_CONFIRMED", "").lower() == "true"
        transport = GeminiTransport(
            os.environ.get("GEMINI_API_KEY", ""), free_tier_confirmed=confirmed
        )
        return FreshComponents(
            UppercaseAgent(path, self.config),
            transport,
            GeminiFreeAdmission(free_tier_confirmed=confirmed),
            registry,
        )
