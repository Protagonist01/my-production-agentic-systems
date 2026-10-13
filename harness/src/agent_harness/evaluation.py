"""Evaluator-only objects and a minimal runner, separate from agent contracts."""

from typing import Annotated, Literal, Protocol, Self

from pydantic import Field, JsonValue, model_validator

from agent_harness.contracts import (
    Agent,
    AgentInput,
    AgentResult,
    Contract,
    EvidenceReference,
    Failure,
    ModelGateway,
    NonEmpty,
    Outcome,
    RunContext,
)


class ExpectedResult(Contract):
    outcome: Outcome
    output: str | None
    eligible_for_autonomy: bool
    required_review: bool
    allowed_decisions: tuple[NonEmpty, ...]
    expected_state_changes: dict[str, JsonValue]


class FaultScenario(Contract):
    """Definition/expectations only; injection execution remains H7."""

    scenario_id: NonEmpty
    target: NonEmpty
    timing: Literal["before_dispatch", "after_dispatch", "after_commit", "on_resume"]
    recoverable: bool
    expected_safe_behavior: NonEmpty
    required_invariants: tuple[NonEmpty, ...]


class EvalCase(Contract):
    case_id: NonEmpty
    input: AgentInput
    snapshot_ref: NonEmpty
    source_kind: Literal["original", "hybrid", "synthetic"]
    source_version: NonEmpty
    policy_version: NonEmpty
    scorer_version: NonEmpty
    expected: ExpectedResult
    hidden_state: dict[str, JsonValue]
    risk: NonEmpty
    slices: tuple[NonEmpty, ...] = ()
    faults: tuple[FaultScenario, ...] = ()

    def agent_input(self) -> AgentInput:
        # Reconstruct a closed model: never serialize the full case to the agent.
        return AgentInput.model_validate_json(self.input.model_dump_json())


class ScoreResult(Contract):
    metric: NonEmpty
    scorer_version: NonEmpty
    eligible: bool
    value: float | None = None
    category: NonEmpty | None = None
    evidence: tuple[EvidenceReference, ...] = ()
    failure: Failure | None = None

    @model_validator(mode="after")
    def explicit_score_or_error(self) -> Self:
        has_score = (self.value is not None) != (self.category is not None)
        if self.failure is None and not has_score:
            raise ValueError("a score requires exactly one numeric value or category")
        if self.failure is not None:
            if (
                self.value is not None
                or self.category is not None
                or self.failure.stage != "scorer"
            ):
                raise ValueError("scorer failure cannot carry a score and must have stage scorer")
        return self


class CaseReport(Contract):
    context: RunContext
    source_kind: Literal["original", "hybrid", "synthetic"]
    source_version: NonEmpty
    policy_version: NonEmpty
    scorer_version: NonEmpty
    result: AgentResult
    scores: Annotated[tuple[ScoreResult, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def matching_evidence(self) -> Self:
        expected_ids = (self.context.run_id, self.context.case_id, self.context.trial_id)
        if (self.result.run_id, self.result.case_id, self.result.trial_id) != expected_ids:
            raise ValueError("result identity differs from run context")
        if any(score.scorer_version != self.scorer_version for score in self.scores):
            raise ValueError("score version differs from report")
        if self.policy_version != self.context.versions.policy:
            raise ValueError("policy version differs from report context")
        return self


class Scorer(Protocol):
    def score(self, case: EvalCase, result: AgentResult) -> tuple[ScoreResult, ...]: ...


def run_case(
    context: RunContext, case: EvalCase, agent: Agent, gateway: ModelGateway, scorer: Scorer
) -> CaseReport:
    """Run one case; infrastructure/programming errors propagate, never become a pass."""
    context = RunContext.model_validate_json(context.model_dump_json())
    case = EvalCase.model_validate_json(case.model_dump_json())
    if context.case_id != case.case_id:
        raise ValueError("case identity differs from run context")
    if context.versions.data_snapshot != case.snapshot_ref:
        raise ValueError("snapshot differs from run context")
    if context.versions.policy != case.policy_version:
        raise ValueError("policy differs from run context")
    if case.faults:
        raise NotImplementedError("FaultScenario execution is not implemented; see H7")
    result = AgentResult.model_validate_json(
        agent.run(context, case.agent_input(), gateway).model_dump_json()
    )
    if (result.run_id, result.case_id, result.trial_id) != (
        context.run_id,
        context.case_id,
        context.trial_id,
    ):
        raise ValueError("result identity differs from run context")
    # Give the scorer a distinct copy so it cannot change the retained agent result.
    scored_result = AgentResult.model_validate_json(result.model_dump_json())
    scores = tuple(
        ScoreResult.model_validate_json(s.model_dump_json())
        for s in scorer.score(case, scored_result)
    )
    return CaseReport(
        context=context,
        source_kind=case.source_kind,
        source_version=case.source_version,
        policy_version=case.policy_version,
        scorer_version=case.scorer_version,
        result=result,
        scores=scores,
    )
