"""Offline reference-relative evaluator diagnostics, never a release/clinical approval."""

from collections import Counter, defaultdict
from typing import Annotated, Literal, Self

from pydantic import AwareDatetime, Field, model_validator

from agent_harness.contracts import Contract, NonEmpty
from agent_harness.release_contracts import Sha256, pin
from agent_harness.scorecard_stats import binomial_bounds

Positive = Annotated[int, Field(gt=0)]
Rate = Annotated[float, Field(ge=0, le=1)]


class QualificationCase(Contract):
    case_id: NonEmpty
    input_sha256: Sha256
    independence_keys: Annotated[tuple[NonEmpty, ...], Field(min_length=1)]
    split: Literal["development", "calibration", "holdout"]
    slices: tuple[NonEmpty, ...]
    expected_accept: bool
    reference_sha256: Sha256
    reference_kind: Literal["published_reference", "independent_program", "ai_provisional"]
    applicability_ref: NonEmpty | None = None
    exposure: Literal["withheld_from_tuning", "public_reference", "unknown"]
    critical_reject: bool = False
    invariant_failed: bool = False

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if self.expected_accept and (self.critical_reject or self.invariant_failed):
            raise ValueError("known invariant/critical rejection cannot have an accept reference")
        if len(set(self.independence_keys)) != len(self.independence_keys) or len(
            set(self.slices)
        ) != len(self.slices):
            raise ValueError("duplicate group or slice")
        return self


class QualificationDataset(Contract):
    version: NonEmpty
    agent: NonEmpty
    field: NonEmpty
    frozen_at: AwareDatetime
    cases: Annotated[tuple[QualificationCase, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique(self) -> Self:
        if len({c.case_id for c in self.cases}) != len(self.cases):
            raise ValueError("duplicate qualification case")
        labels: dict[str, bool] = {}
        for case in self.cases:
            if case.input_sha256 in labels and labels[case.input_sha256] != case.expected_accept:
                raise ValueError("identical input has conflicting reference labels")
            labels[case.input_sha256] = case.expected_accept
        return self


class QualificationProtocol(Contract):
    version: Literal["evaluator-qualification-v1"] = "evaluator-qualification-v1"
    dataset_sha256: Sha256
    evaluator_sha256: Sha256
    frozen_at: AwareDatetime
    trial_ids: Annotated[tuple[NonEmpty, ...], Field(min_length=1)]
    required_slices: Annotated[tuple[NonEmpty, ...], Field(min_length=1)]
    min_holdout_groups: Positive
    min_groups_per_slice: Positive
    min_groups_per_class: Positive
    min_decision_coverage: Rate
    min_scheduled_accuracy: Rate
    max_false_accept_rate: Rate
    max_false_reject_rate: Rate
    max_group_error_upper_bound: Rate
    reference_validation_ref: NonEmpty | None = None
    sample_size_ref: NonEmpty | None = None
    # These are trusted methodology declarations, not authenticated reviewer approvals.

    @model_validator(mode="after")
    def unique(self) -> Self:
        if len(set(self.trial_ids)) != len(self.trial_ids) or len(set(self.required_slices)) != len(
            self.required_slices
        ):
            raise ValueError("duplicate trial or required slice")
        return self


class QualificationObservation(Contract):
    case_id: NonEmpty
    trial_id: NonEmpty
    input_sha256: Sha256
    evaluator_sha256: Sha256
    observed_at: AwareDatetime
    decision: Literal["accept", "reject", "abstain"] | None
    failure_code: NonEmpty | None = None

    @model_validator(mode="after")
    def status(self) -> Self:
        if (self.decision is None) != (self.failure_code is not None):
            raise ValueError("failed observation needs a code and no decision")
        return self


class QualificationStudy(Contract):
    protocol_sha256: Sha256
    started_at: AwareDatetime
    finished_at: AwareDatetime
    rows: tuple[QualificationObservation, ...]


def _components(cases: tuple[QualificationCase, ...]) -> dict[str, str]:
    """Union all parent/source/template keys before checking splits or counting groups."""
    parents: dict[str, str] = {}

    def find(key: str) -> str:
        parents.setdefault(key, key)
        while parents[key] != key:
            parents[key] = parents[parents[key]]
            key = parents[key]
        return key

    for case in cases:
        first = "input:" + case.input_sha256
        for key in (first, *("declared:" + key for key in case.independence_keys)):
            parents[find(key)] = find(first)
    return {c.case_id: find("input:" + c.input_sha256) for c in cases}


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def qualification_report(
    dataset: QualificationDataset,
    protocol: QualificationProtocol,
    study: QualificationStudy,
    *,
    now: AwareDatetime,
) -> dict[str, object]:
    """Check a frozen schedule; statistics cannot authenticate labels, samples or policy."""
    dataset = QualificationDataset.model_validate_json(dataset.canonical_json())
    protocol = QualificationProtocol.model_validate_json(protocol.canonical_json())
    study = QualificationStudy.model_validate_json(study.canonical_json())
    if now.tzinfo is None:
        raise ValueError("qualification audit needs an aware clock")
    if pin(dataset) != protocol.dataset_sha256 or pin(protocol) != study.protocol_sha256:
        raise ValueError("qualification input pin differs")
    if not dataset.frozen_at <= protocol.frozen_at <= study.started_at <= study.finished_at <= now:
        raise ValueError("qualification freeze/capture time order differs")
    cases = {c.case_id: c for c in dataset.cases}
    lookup: dict[tuple[str, str], QualificationObservation] = {}
    for row in study.rows:
        key = row.case_id, row.trial_id
        if key in lookup or row.case_id not in cases or row.trial_id not in protocol.trial_ids:
            raise ValueError("duplicate or unscheduled qualification observation")
        if row.input_sha256 != cases[row.case_id].input_sha256 or (
            row.evaluator_sha256 != protocol.evaluator_sha256
        ):
            raise ValueError("qualification input/evaluator binding differs")
        if not study.started_at <= row.observed_at <= study.finished_at:
            raise ValueError("observation outside capture interval")
        lookup[key] = row

    components = _components(dataset.cases)
    split_groups: dict[str, set[str]] = defaultdict(set)
    for case in dataset.cases:
        split_groups[components[case.case_id]].add(case.split)
    if any(len(splits) > 1 for splits in split_groups.values()):
        raise ValueError("connected reference/source/template group crosses splits")

    def measure(members: tuple[QualificationCase, ...]) -> dict[str, object]:
        counts: Counter[str] = Counter()
        failures: dict[str, bool] = {}
        class_groups: dict[bool, set[str]] = {True: set(), False: set()}
        class_failures: dict[bool, dict[str, bool]] = {True: {}, False: {}}
        for case in members:
            group = components[case.case_id]
            class_groups[case.expected_accept].add(group)
            class_failures[case.expected_accept].setdefault(group, False)
            failures.setdefault(group, False)
            for trial in protocol.trial_ids:
                counts["scheduled"] += 1
                label = "acceptable" if case.expected_accept else "unacceptable"
                counts[label + "_scheduled"] += 1
                row = lookup.get((case.case_id, trial))
                decision = row.decision if row else None
                decided = decision in ("accept", "reject")
                correct = decided and (decision == "accept") == case.expected_accept
                failures[group] |= not correct
                class_failures[case.expected_accept][group] |= not correct
                counts["missing"] += row is None
                counts["failed"] += row is not None and row.failure_code is not None
                counts["abstained"] += decision == "abstain"
                counts["decided"] += decided
                counts[label + "_decided"] += decided
                counts["correct"] += correct
                counts[label + "_unresolved"] += not decided
                if decided:
                    quadrant = (
                        ("true_accept" if case.expected_accept else "false_accept")
                        if decision == "accept"
                        else ("false_reject" if case.expected_accept else "true_reject")
                    )
                    counts[quadrant] += 1
                counts["critical_not_rejected"] += case.critical_reject and decision != "reject"
                counts["invariant_overridden"] += case.invariant_failed and decision == "accept"
        lower, upper = binomial_bounds(sum(failures.values()), len(failures))
        _, acceptable_upper = binomial_bounds(
            sum(class_failures[True].values()), len(class_failures[True])
        )
        _, unacceptable_upper = binomial_bounds(
            sum(class_failures[False].values()), len(class_failures[False])
        )
        return {
            **{
                name: counts[name]
                for name in (
                    "scheduled",
                    "acceptable_scheduled",
                    "unacceptable_scheduled",
                    "missing",
                    "failed",
                    "abstained",
                    "decided",
                    "correct",
                    "acceptable_unresolved",
                    "unacceptable_unresolved",
                    "true_accept",
                    "false_accept",
                    "true_reject",
                    "false_reject",
                    "critical_not_rejected",
                    "invariant_overridden",
                )
            },
            "decision_coverage": _ratio(counts["decided"], counts["scheduled"]),
            "scheduled_accuracy": _ratio(counts["correct"], counts["scheduled"]),
            "conditional_accuracy": _ratio(counts["correct"], counts["decided"]),
            "acceptable_decision_coverage": _ratio(
                counts["acceptable_decided"], counts["acceptable_scheduled"]
            ),
            "unacceptable_decision_coverage": _ratio(
                counts["unacceptable_decided"], counts["unacceptable_scheduled"]
            ),
            "false_accept_rate": _ratio(counts["false_accept"], counts["unacceptable_scheduled"]),
            "false_reject_rate": _ratio(counts["false_reject"], counts["acceptable_scheduled"]),
            "conditional_false_accept_rate": _ratio(
                counts["false_accept"], counts["false_accept"] + counts["true_reject"]
            ),
            "conditional_false_reject_rate": _ratio(
                counts["false_reject"], counts["false_reject"] + counts["true_accept"]
            ),
            "groups": len(failures),
            "acceptable_groups": len(class_groups[True]),
            "unacceptable_groups": len(class_groups[False]),
            "failed_groups": sum(failures.values()),
            "group_error_lower_bound": lower,
            "group_error_upper_bound": upper,
            "acceptable_group_error_upper_bound": acceptable_upper,
            "unacceptable_group_error_upper_bound": unacceptable_upper,
        }

    holdout = tuple(c for c in dataset.cases if c.split == "holdout")
    metrics = {"holdout": measure(holdout)}
    metrics.update(
        {
            "slice:" + tag: measure(tuple(c for c in holdout if tag in c.slices))
            for tag in protocol.required_slices
        }
    )
    blockers: set[str] = set()
    if protocol.reference_validation_ref is None:
        blockers.add("reference_applicability_unvalidated")
    if protocol.sample_size_ref is None:
        blockers.add("sample_size_rationale_missing")
    if any(c.reference_kind == "ai_provisional" or c.applicability_ref is None for c in holdout):
        blockers.add("holdout_reference_basis_unqualified")
    if any(c.exposure == "unknown" for c in holdout):
        blockers.add("holdout_exposure_unknown")
    if any(
        c.reference_kind == "ai_provisional" or c.applicability_ref is None
        for c in dataset.cases
        if c.split == "calibration"
    ):
        blockers.add("calibration_reference_basis_unqualified")
    calibration = measure(tuple(c for c in dataset.cases if c.split == "calibration"))
    if (
        calibration["missing"]
        or calibration["failed"]
        or not calibration["acceptable_groups"]
        or not calibration["unacceptable_groups"]
        or not calibration["decided"]
    ):
        blockers.add("calibration_incomplete_or_one_class")
    if calibration["critical_not_rejected"] or calibration["invariant_overridden"]:
        blockers.add("calibration_critical_or_invariant_failure")
    for scope, measured in metrics.items():
        for name, limit, floor in (
            (
                "groups",
                protocol.min_holdout_groups
                if scope == "holdout"
                else protocol.min_groups_per_slice,
                True,
            ),
            ("acceptable_groups", protocol.min_groups_per_class, True),
            ("unacceptable_groups", protocol.min_groups_per_class, True),
            ("decision_coverage", protocol.min_decision_coverage, True),
            ("acceptable_decision_coverage", protocol.min_decision_coverage, True),
            ("unacceptable_decision_coverage", protocol.min_decision_coverage, True),
            ("scheduled_accuracy", protocol.min_scheduled_accuracy, True),
            ("false_accept_rate", protocol.max_false_accept_rate, False),
            ("false_reject_rate", protocol.max_false_reject_rate, False),
            ("conditional_false_accept_rate", protocol.max_false_accept_rate, False),
            ("conditional_false_reject_rate", protocol.max_false_reject_rate, False),
            ("group_error_upper_bound", protocol.max_group_error_upper_bound, False),
            ("acceptable_group_error_upper_bound", protocol.max_group_error_upper_bound, False),
            ("unacceptable_group_error_upper_bound", protocol.max_group_error_upper_bound, False),
        ):
            value = measured[name]
            if not isinstance(value, (int, float)) or (value < limit if floor else value > limit):
                blockers.add(scope + ":" + name)
        if measured["critical_not_rejected"] or measured["invariant_overridden"]:
            blockers.add(scope + ":critical_or_invariant_failure")
        if measured["decided"] == 0:
            blockers.add(scope + ":no_decisions")
    return {
        "version": "evaluator-qualification-report-v1",
        "dataset_sha256": pin(dataset),
        "protocol_sha256": pin(protocol),
        "study_sha256": pin(study),
        "evaluator_sha256": protocol.evaluator_sha256,
        "agent": dataset.agent,
        "field": dataset.field,
        "metrics": metrics,
        "calibration": calibration,
        "development": measure(tuple(c for c in dataset.cases if c.split == "development")),
        "blockers": sorted(blockers),
        "criteria_met": not blockers,
        "release_allowed": False,
        "human_review_supplied": False,
        "unseen_model_data_claimed": False,
        "reference_exposure_counts": dict(Counter(c.exposure for c in holdout)),
        "uncertainty_assumption": "independent_comparable_source_groups_not_authenticated",
        "limits": (
            "Reference applicability, grouping, thresholds and exposure remain trusted inputs; "
            "no deployment approval."
        ),
    }
