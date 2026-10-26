"""Offline evidence/schedule proposals, deliberately separate from release approval."""

from collections import Counter
from typing import Annotated, Literal, Self

from pydantic import AwareDatetime, Field, model_validator

from agent_harness.contracts import Contract, NonEmpty
from agent_harness.evaluation_standards import StandardProfile
from agent_harness.release_contracts import Sha256, pin

Count = Annotated[int, Field(ge=0)]
Positive = Annotated[int, Field(gt=0)]
Purpose = Literal["reference_drafting", "calibration", "candidate", "comparator", "fault", "judge"]
Method = Literal["independent_program", "external_reference", "model_assessment"]


class RequirementEvidence(Contract):
    field: NonEmpty
    methods: Annotated[tuple[Method, ...], Field(min_length=1)]
    check: NonEmpty
    existing_evidence: Annotated[tuple[NonEmpty, ...], Field(min_length=1)]
    remaining: Annotated[tuple[NonEmpty, ...], Field(min_length=1)]
    # A proposed evidence path is never an assertion that this field passed.
    acceptance: Literal["pending"] = "pending"

    @model_validator(mode="after")
    def unique_methods(self) -> Self:
        if len(set(self.methods)) != len(self.methods):
            raise ValueError("duplicate evidence method")
        return self


class AgentEvidencePlan(Contract):
    agent: NonEmpty
    profile_sha256: Sha256
    requirements: Annotated[tuple[RequirementEvidence, ...], Field(min_length=1)]
    required_slices: Annotated[tuple[NonEmpty, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique(self) -> Self:
        fields = [r.field for r in self.requirements]
        if len(set(fields)) != len(fields) or len(set(self.required_slices)) != len(
            self.required_slices
        ):
            raise ValueError("duplicate field or slice")
        return self


class EvidenceMatrix(Contract):
    version: Literal["evidence-path-proposal-v1"] = "evidence-path-proposal-v1"
    agents: Annotated[tuple[AgentEvidencePlan, ...], Field(min_length=1)]


def validate_matrix(matrix: EvidenceMatrix, profiles: tuple[StandardProfile, ...]) -> int:
    """Bind every required field/slice to the actual profile; return coverage, not quality."""
    matrix = EvidenceMatrix.model_validate_json(matrix.canonical_json())
    profiles = tuple(StandardProfile.model_validate_json(p.canonical_json()) for p in profiles)
    expected = {p.agent: p for p in profiles}
    actual = {a.agent: a for a in matrix.agents}
    if len(expected) != len(profiles) or len(actual) != len(matrix.agents):
        raise ValueError("duplicate agent")
    if expected.keys() != actual.keys():
        raise ValueError("missing or extra agent")
    for name, profile in expected.items():
        plan = actual[name]
        if plan.profile_sha256 != pin(profile):
            raise ValueError("profile pin differs")
        if {r.field for r in plan.requirements} != set(profile.required_fields):
            raise ValueError("required fields differ")
        if set(plan.required_slices) != set(profile.required_holdout_slices):
            raise ValueError("required slices differ")
    return sum(len(a.requirements) for a in matrix.agents)


class AttemptLine(Contract):
    line_id: NonEmpty
    provider: NonEmpty
    agent: NonEmpty
    purpose: Purpose
    cases: Positive
    trials: Positive
    calls_per_trial: Positive
    orderings: Positive
    # Reserved worst case; execution may not retry automatically just because it fits.
    extra_attempts_per_call: Count

    def maximum_attempts(self) -> int:
        return (
            self.cases
            * self.trials
            * self.calls_per_trial
            * self.orderings
            * (1 + self.extra_attempts_per_call)
        )


class AllowanceSnapshot(Contract):
    provider: NonEmpty
    ledger_reference: NonEmpty
    observed_at: AwareDatetime
    maximum: Positive
    consumed: Count
    agents: Annotated[tuple[NonEmpty, ...], Field(min_length=1)]
    purposes: Annotated[tuple[Purpose, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def valid(self) -> Self:
        if self.consumed > self.maximum:
            raise ValueError("consumption exceeds allowance")
        if len(set(self.agents)) != len(self.agents) or len(set(self.purposes)) != len(
            self.purposes
        ):
            raise ValueError("duplicate allowance scope")
        return self


class AttemptPlan(Contract):
    version: Literal["offline-attempt-forecast-v1"] = "offline-attempt-forecast-v1"
    lines: Annotated[tuple[AttemptLine, ...], Field(min_length=1)]


class AllowanceSnapshots(Contract):
    snapshots: tuple[AllowanceSnapshot, ...]


class AttemptForecast(Contract):
    plan_sha256: Sha256
    snapshot_sha256s: dict[str, Sha256]
    maximum_by_provider: dict[str, Count]
    maximum_by_agent: dict[str, Count]
    remaining_before: dict[str, Count]
    blockers: tuple[NonEmpty, ...]
    fits_declared_snapshots: bool
    dispatch_allowed: Literal[False] = False
    release_allowed: Literal[False] = False


def forecast_attempts(
    plan: AttemptPlan, snapshots: tuple[AllowanceSnapshot, ...]
) -> AttemptForecast:
    """No IO/reservation/dispatch; caller declarations are not authenticated grants."""
    plan = AttemptPlan.model_validate_json(plan.canonical_json())
    snapshots = tuple(AllowanceSnapshot.model_validate_json(s.canonical_json()) for s in snapshots)
    if len({line.line_id for line in plan.lines}) != len(plan.lines):
        raise ValueError("duplicate schedule line")
    allowances = {s.provider: s for s in snapshots}
    if len(allowances) != len(snapshots):
        raise ValueError("one authoritative snapshot per provider required")
    providers: Counter[str] = Counter()
    agents: Counter[str] = Counter()
    blockers: set[str] = set()
    for line in plan.lines:
        attempts = line.maximum_attempts()
        providers[line.provider] += attempts
        agents[line.agent] += attempts
        allowance = allowances.get(line.provider)
        if allowance is None:
            blockers.add(f"{line.line_id}:missing_allowance")
        elif line.agent not in allowance.agents or line.purpose not in allowance.purposes:
            blockers.add(f"{line.line_id}:scope_not_in_snapshot")
    remaining = {s.provider: s.maximum - s.consumed for s in snapshots}
    for provider, attempts in providers.items():
        if provider in remaining and attempts > remaining[provider]:
            blockers.add(f"{provider}:attempt_cap_exceeded")
    return AttemptForecast(
        plan_sha256=pin(plan),
        snapshot_sha256s={s.provider: pin(s) for s in snapshots},
        maximum_by_provider=dict(providers),
        maximum_by_agent=dict(agents),
        remaining_before=remaining,
        blockers=tuple(sorted(blockers)),
        fits_declared_snapshots=not blockers,
    )


class EvidenceSpan(Contract):
    source_sha256: Sha256
    start: Count
    end: Positive
    text: NonEmpty

    def verify(self, source: str) -> bool:
        """Exact Unicode code-point offsets; support meaning is deliberately not inferred."""
        from agent_harness.release_contracts import sha256

        EvidenceSpan.model_validate_json(self.canonical_json())
        return (
            sha256(source.encode("utf-8")) == self.source_sha256
            and self.start < self.end <= len(source)
            and source[self.start : self.end] == self.text
        )


class AssessmentProposal(Contract):
    """Pin diagnostic evidence without masquerading as Review or qualifying a judge."""

    version: Literal["diagnostic-assessment-v1"] = "diagnostic-assessment-v1"
    agent: NonEmpty
    field: NonEmpty
    input_sha256: Sha256
    evaluator_sha256: Sha256
    source_sha256s: Annotated[tuple[Sha256, ...], Field(min_length=1)]
    method: Method
    judgment: Literal["supported", "contradicted", "unresolved"]
    spans: tuple[EvidenceSpan, ...]
    explanation: NonEmpty
    qualification_report_sha256: Sha256 | None = None
    # Even a supplied report hash is only a pointer, not authenticated qualification.
    status: Literal["diagnostic_only"] = "diagnostic_only"
    release_allowed: Literal[False] = False

    @model_validator(mode="after")
    def evidence(self) -> Self:
        if len(set(self.source_sha256s)) != len(self.source_sha256s):
            raise ValueError("duplicate source")
        if any(span.source_sha256 not in self.source_sha256s for span in self.spans):
            raise ValueError("span outside declared sources")
        if (
            self.method != "independent_program"
            and self.judgment != "unresolved"
            and not self.spans
        ):
            raise ValueError("text judgment requires evidence spans")
        return self
