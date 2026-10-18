"""Private metadata-only reporting contracts; not a release policy or scorer."""

from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from agent_harness.cases import Identifier, ManifestPin, Split
from agent_harness.contracts import Contract, Count, Money, Outcome, Usage
from agent_harness.trials import OutcomePolicy, TrialAssessment, TrialError

Mode = Literal["offline_fake", "strict_replay", "fresh_candidate"]


class ReportPolicy(Contract):
    version: Identifier
    required_case_ids: tuple[Identifier, ...]
    repeated_case_ids: tuple[Identifier, ...] = ()

    @model_validator(mode="after")
    def distinct_cases(self) -> Self:
        for values in (self.required_case_ids, self.repeated_case_ids):
            if len(values) != len(set(values)):
                raise ValueError("duplicate reporting policy case")
        return self


class Ratio(Contract):
    numerator: Count
    denominator: Count
    unknown: Count
    value: Annotated[float, Field(ge=0, le=1)] | None
    possible_upper: Annotated[float, Field(ge=0, le=1)] | None

    @model_validator(mode="after")
    def consistent_counts(self) -> Self:
        if self.numerator + self.unknown > self.denominator:
            raise ValueError("ratio counts exceed denominator")
        expected = self.numerator / self.denominator if self.denominator else None
        upper = (self.numerator + self.unknown) / self.denominator if self.denominator else None
        if (self.value, self.possible_upper) != (expected, upper):
            raise ValueError("ratio differs from explicit counts")
        return self


def ratio(numerator: int, denominator: int, unknown: int = 0) -> Ratio:
    return Ratio(
        numerator=numerator,
        denominator=denominator,
        unknown=unknown,
        value=numerator / denominator if denominator else None,
        possible_upper=(numerator + unknown) / denominator if denominator else None,
    )


class SafetyUncertainty(Contract):
    unit: Literal["group_within_slice"] = "group_within_slice"
    confidence: Annotated[float, Field(ge=0.95, le=0.95)] = 0.95
    method: Literal["binomial_boundary_wilson_envelope"] = "binomial_boundary_wilson_envelope"
    groups: Count
    observed_event_groups: Count
    unknown_groups: Count
    lower: Annotated[float, Field(ge=0, le=1)] | None
    upper: Annotated[float, Field(ge=0, le=1)] | None
    assumption: Literal["independent_comparable_groups_not_verified"] = (
        "independent_comparable_groups_not_verified"
    )


class UsageSummary(Contract):
    scheduled_trials: Count
    reported_trials: Count
    model_calls: Count | None
    known_model_calls: Count
    unknown_model_call_trials: Count
    input_tokens: Count | None
    known_input_tokens: Count
    unknown_input_token_trials: Count
    output_tokens: Count | None
    known_output_tokens: Count
    unknown_output_token_trials: Count
    cost: Money | None
    cost_currency: Identifier | None
    known_cost_by_currency: dict[str, Money]
    unknown_cost_trials: Count
    cost_per_autonomous_completion: Money | None


class TrialFact(Contract):
    case_id: Identifier
    trial_id: Identifier
    seed: Count
    assessment: TrialAssessment | None
    observed_outcome: Outcome | None
    usage: Usage | None
    usage_complete: bool
    errors: tuple[TrialError, ...]

    @property
    def category(self) -> str:
        return self.assessment.category if self.assessment is not None else "missing"

    @property
    def complete(self) -> bool:
        return self.assessment is not None and self.assessment.evidence_complete

    @property
    def passed(self) -> bool:
        return self.complete and self.category in (
            "autonomous_completion",
            "verified_completion",
            "appropriate_review",
        )


class CaseScorecard(Contract):
    case_id: Identifier
    group_id: Identifier
    split: Split
    source_kind: Literal["original", "hybrid", "synthetic"]
    source_version: Identifier
    risk: Identifier
    tags: tuple[str, ...]
    snapshot_ref: Identifier
    policy_version: Identifier
    scorer_id: Identifier
    scorer_version: Identifier
    eligible_for_autonomy: bool
    required_review: bool
    required_case: bool
    repeated_case: bool
    fault_kinds: tuple[str, ...]
    trials: tuple[TrialFact, ...]


class Summary(Contract):
    scheduled_trials: Count
    present_rows: Count
    missing_rows: Count
    category_counts: dict[str, Count]
    autonomous_completion: Ratio
    confirmed_success: Ratio
    observed_review: Ratio
    appropriate_review: Ratio
    unnecessary_review: Ratio
    observed_violations: Ratio
    evidence_complete: Ratio
    safety_uncertainty: SafetyUncertainty
    usage: UsageSummary


class SliceScorecard(Contract):
    dimension: Literal["split", "source_kind", "source_version", "risk", "tag", "fault_kind"]
    label: str
    summary: Summary


class RepeatedCorrectness(Contract):
    status: Literal[
        "not_declared", "requires_fresh_candidate", "requires_exactly_three_trials", "reported"
    ]
    all_three_correct: Ratio | None
    freshness_verified: Literal[False] = False


class Scorecard(Contract):
    reporter_version: Literal["h9-scorecard-v1"] = "h9-scorecard-v1"
    reporter_code_revision: Identifier
    private_report: Literal[True] = True
    experiment_id: Identifier
    batch_sha256: str
    manifest: ManifestPin
    report_policy: ReportPolicy
    outcome_policy: OutcomePolicy
    candidate: Identifier
    code_revision: Identifier
    environment_lock: Identifier
    environment_version: Identifier
    state_fixture: Identifier
    fault_plan_version: Identifier | None
    fault_plan_sha256: str | None
    mode: Mode
    freshness_verified: Literal[False] = False
    overall: Summary
    fault_outcomes: Summary
    repeated_correctness: RepeatedCorrectness
    slices: tuple[SliceScorecard, ...]
    cases: tuple[CaseScorecard, ...]


class CaseChange(Contract):
    case_id: Identifier
    required: bool
    trials: Count
    baseline_passes: Count
    candidate_passes: Count
    regressed_trial_ids: tuple[str, ...]
    improved_trial_ids: tuple[str, ...]
    new_unsafe_trial_ids: tuple[str, ...]
    new_unverified_trial_ids: tuple[str, ...]


class Comparison(Contract):
    reporter_version: Literal["h9-comparison-v1"] = "h9-comparison-v1"
    private_report: Literal[True] = True
    reporter_code_revision: Identifier
    baseline_candidate: Identifier
    baseline_code_revision: Identifier
    baseline_environment_lock: Identifier
    candidate_version: Identifier
    candidate_code_revision: Identifier
    candidate_environment_lock: Identifier
    baseline_sha256: str
    candidate_sha256: str
    baseline_approval: Literal["not_established_by_comparison"] = "not_established_by_comparison"
    release_decision: Literal["not_performed"] = "not_performed"
    manifest: ManifestPin
    report_policy: ReportPolicy
    mode: Mode
    completion_delta: float | None
    newly_failing_required_cases: tuple[str, ...]
    cases: tuple[CaseChange, ...]
