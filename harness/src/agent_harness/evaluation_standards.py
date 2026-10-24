"""Private cross-domain evaluation audit; declarations are not deployment approval.

Domain adapters still own semantic labels, state inspection and correctness. This
module checks experimental design and complete denominators without importing them.
"""

import unicodedata
from collections import Counter
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import AwareDatetime, Field, model_validator

from agent_harness.cases import Identifier as NonEmpty
from agent_harness.contracts import Contract, Money
from agent_harness.controls import add_money
from agent_harness.release_contracts import Sha256, pin, sha256
from agent_harness.scorecard_stats import binomial_bounds

Count = Annotated[int, Field(ge=0)]
Positive = Annotated[int, Field(gt=0)]
Rate = Annotated[float, Field(ge=0, le=1)]
Seconds = Annotated[float, Field(ge=0)]


class StandardProfile(Contract):
    version: NonEmpty
    agent: NonEmpty
    required_fields: Annotated[tuple[NonEmpty, ...], Field(min_length=1)]
    required_holdout_slices: Annotated[tuple[NonEmpty, ...], Field(min_length=1)]
    qualified_label_review_required: bool = False
    requires_eligible_cases: bool = True
    claim_scope: Literal["application", "simulation"] = "application"

    @model_validator(mode="after")
    def unique(self) -> Self:
        for values in (self.required_fields, self.required_holdout_slices):
            if len(set(values)) != len(values):
                raise ValueError("duplicate standard requirement")
        return self


class Review(Contract):
    reviewer: NonEmpty
    reference: NonEmpty
    reviewed_at: AwareDatetime
    kind: Literal["ai_provisional", "human_retrospective", "human_blind", "qualified_blind"]


class StandardCase(Contract):
    case_id: NonEmpty
    # Correlated source records, document families and edited parents share keys.
    independence_keys: Annotated[tuple[NonEmpty, ...], Field(min_length=1)]
    language_family: NonEmpty
    input_text: NonEmpty
    split: Literal["development", "regression", "holdout"]
    source_kind: Literal["original", "hybrid", "synthetic"]
    slices: tuple[NonEmpty, ...]
    eligible_for_autonomy: bool
    required_review: bool
    critical: bool
    label_review: Review | None = None

    @model_validator(mode="after")
    def disposition(self) -> Self:
        if self.eligible_for_autonomy and self.required_review:
            raise ValueError("required review cannot also be eligible for autonomy")
        return self


class StandardProtocol(Contract):
    version: NonEmpty
    profile_sha256: Sha256
    dataset_sha256: Sha256
    scorer_sha256: Sha256
    baseline_sha256: Sha256
    frozen_at: AwareDatetime
    trials_per_case: Positive
    # No arbitrary production thresholds: an unset requirement refuses qualification.
    min_holdout_groups: Positive | None = None
    min_holdout_groups_per_slice: Positive | None = None
    min_correct_rate: Rate | None = None
    min_field_correct_rates: dict[NonEmpty, Rate] = {}
    min_all_repetitions_correct_rate: Rate | None = None
    max_group_error_upper_bound: Rate | None = None
    max_unnecessary_review_rate: Rate | None = None
    max_missed_review_rate: Rate | None = None
    max_unresolved_rate: Rate | None = None
    max_p95_seconds: Seconds | None = None
    max_total_cost: Money | None = None
    max_model_calls: Count | None = None
    max_total_tokens: Count | None = None
    cost_currency: NonEmpty | None = None
    representative_sampling_ref: NonEmpty | None = None
    independence_review_ref: NonEmpty | None = None
    evaluator_validation_ref: NonEmpty | None = None
    sample_size_rationale_ref: NonEmpty | None = None
    simulation_sensitivity_ref: NonEmpty | None = None
    baseline_review: Review | None = None
    threshold_review: Review | None = None


class StandardRow(Contract):
    case_id: NonEmpty
    trial_id: NonEmpty
    outcome: Literal["completed", "review_required", "unresolved"]
    correct: bool
    unsafe: bool
    fields: dict[NonEmpty, bool]
    baseline_correct: bool | None = None
    elapsed_seconds: Seconds | None = None
    input_tokens: Count | None = None
    output_tokens: Count | None = None
    model_calls: Count | None = None
    cost: Money | None = None
    cost_currency: NonEmpty | None = None

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if self.outcome == "unresolved" and self.correct:
            raise ValueError("unresolved cannot be correct")
        if self.correct and (self.unsafe or not all(self.fields.values())):
            raise ValueError("correct cannot hide unsafe effects or failed fields")
        if (self.cost is None) != (self.cost_currency is None):
            raise ValueError("cost and currency must be known together")
        return self


class StandardStudy(Contract):
    version: NonEmpty
    protocol_sha256: Sha256
    candidate_spec_sha256: Sha256
    candidate_evidence_sha256: Sha256
    started_at: AwareDatetime
    finished_at: AwareDatetime
    cases: Annotated[tuple[StandardCase, ...], Field(min_length=1)]
    trial_ids: Annotated[tuple[NonEmpty, ...], Field(min_length=1)]
    rows: tuple[StandardRow, ...]

    @model_validator(mode="after")
    def population(self) -> Self:
        ids = [c.case_id for c in self.cases]
        keys = [(r.case_id, r.trial_id) for r in self.rows]
        if len(set(ids)) != len(ids) or len(set(self.trial_ids)) != len(self.trial_ids):
            raise ValueError("duplicate case or scheduled trial identity")
        expected = {(c, t) for c in ids for t in self.trial_ids}
        if len(set(keys)) != len(keys) or not set(keys).issubset(expected):
            raise ValueError("duplicate or unexpected result row")
        if self.finished_at < self.started_at:
            raise ValueError("study time order")
        return self


def text_fingerprint(text: str) -> str:
    """Detect exact/format variants; this is not a semantic near-duplicate detector."""
    normalized = " ".join(unicodedata.normalize("NFKC", text).casefold().split())
    return sha256(normalized.encode())


def _reviewed(review: Review | None, before: datetime, *, qualified: bool = False) -> bool:
    return bool(
        review
        and review.kind
        in (("qualified_blind",) if qualified else ("human_blind", "qualified_blind"))
        and review.reviewed_at <= before
    )


def audit_study(
    profile: StandardProfile, protocol: StandardProtocol, study: StandardStudy, *, now: datetime
) -> dict[str, object]:
    """Revalidate objects, bind pins, then audit all scheduled rows, including absences."""
    profile = StandardProfile.model_validate_json(profile.canonical_json())
    protocol = StandardProtocol.model_validate_json(protocol.canonical_json())
    study = StandardStudy.model_validate_json(study.canonical_json())
    if now.tzinfo is None:
        raise ValueError("audit clock must be timezone aware")
    if pin(profile) != protocol.profile_sha256 or pin(protocol) != study.protocol_sha256:
        raise ValueError("profile/protocol differs from reviewed pin")
    blockers: set[str] = set()
    if not protocol.frozen_at <= study.started_at <= study.finished_at <= now:
        blockers.add("protocol_or_capture_time_order")
    if len(study.trial_ids) != protocol.trials_per_case:
        blockers.add("repetition_schedule_mismatch")
    for field in (
        "min_holdout_groups",
        "min_holdout_groups_per_slice",
        "min_correct_rate",
        "min_all_repetitions_correct_rate",
        "max_group_error_upper_bound",
        "max_unnecessary_review_rate",
        "max_missed_review_rate",
        "max_unresolved_rate",
        "max_p95_seconds",
        "max_total_cost",
        "max_model_calls",
        "max_total_tokens",
        "cost_currency",
        "representative_sampling_ref",
        "independence_review_ref",
        "evaluator_validation_ref",
        "sample_size_rationale_ref",
    ):
        if field == "max_unnecessary_review_rate" and not profile.requires_eligible_cases:
            continue
        if getattr(protocol, field) is None:
            blockers.add("protocol_requirement_unset:" + field)
    for name in ("baseline_review", "threshold_review"):
        if not _reviewed(getattr(protocol, name), protocol.frozen_at):
            blockers.add(name + "_not_independently_frozen")
    if profile.claim_scope == "simulation" and protocol.simulation_sensitivity_ref is None:
        blockers.add("simulation_sensitivity_not_reviewed")
    groups: dict[str, set[str]] = {}
    texts: dict[str, set[str]] = {}
    families: dict[str, set[str]] = {}
    for case in study.cases:
        if not _reviewed(
            case.label_review,
            protocol.frozen_at,
            qualified=profile.qualified_label_review_required,
        ):
            blockers.add("labels_not_independently_frozen")
        for key in case.independence_keys:
            groups.setdefault(key, set()).add(case.split)
        texts.setdefault(text_fingerprint(case.input_text), set()).add(case.split)
        families.setdefault(case.language_family, set()).add(case.split)
    if any(len(splits) > 1 for splits in groups.values()):
        blockers.add("source_or_parent_group_leakage")
    if any(len(splits) > 1 for splits in texts.values()):
        blockers.add("normalized_input_leakage")
    if any(len(splits) > 1 for splits in families.values()):
        blockers.add("language_family_leakage")
    holdout = [c for c in study.cases if c.split == "holdout"]
    if {c.split for c in study.cases} != {"development", "regression", "holdout"}:
        blockers.add("missing_evaluation_partition")
    # Count connected components, not IDs or repeated trials, as source groups.
    components: list[set[str]] = []
    for case in holdout:
        connected = set(case.independence_keys)
        remaining = []
        for component in components:
            if component & connected:
                connected |= component
            else:
                remaining.append(component)
        components = [*remaining, connected]
    if protocol.min_holdout_groups is None or len(components) < protocol.min_holdout_groups:
        blockers.add("insufficient_holdout_groups")
    tags = {tag for c in holdout for tag in c.slices}
    for tag in profile.required_holdout_slices:
        if tag not in tags:
            blockers.add("missing_holdout_slice:" + tag)
    lookup = {(r.case_id, r.trial_id): r for r in study.rows}
    fields = set(profile.required_fields)
    metrics: dict[str, object] = {}
    for split in ("development", "regression", "holdout", "all"):
        cases = [c for c in study.cases if split == "all" or c.split == split]
        metrics[split] = _measure(cases, study.trial_ids, lookup, fields)
    for kind in ("original", "hybrid", "synthetic"):
        metrics["source_kind:" + kind] = _measure(
            [c for c in study.cases if c.source_kind == kind], study.trial_ids, lookup, fields
        )
    all_metrics = _measure(list(study.cases), study.trial_ids, lookup, fields)
    if all_metrics["missing"] or all_metrics["unresolved"] or all_metrics["missing_fields"]:
        blockers.add("incomplete_results")
    if all_metrics["unsafe"]:
        blockers.add("unsafe_effect")
    if all_metrics["critical_failures"]:
        blockers.add("critical_case_failed")
    if all_metrics["regressions"]:
        blockers.add("previously_passing_trial_regressed")
    if all_metrics["baseline_unknown"]:
        blockers.add("paired_baseline_incomplete")
    # Quality limits apply to holdout; safety, completeness and critical regressions
    # above apply everywhere. Slice scores remain visible, never replaced by averages.
    measured = _measure(holdout, study.trial_ids, lookup, fields)
    if profile.requires_eligible_cases and measured["eligible"] == 0:
        blockers.add("no_eligible_holdout_cases")
    for key, threshold, lower in (
        ("correct_rate", protocol.min_correct_rate, True),
        ("all_repetitions_correct_rate", protocol.min_all_repetitions_correct_rate, True),
        ("unnecessary_review_rate", protocol.max_unnecessary_review_rate, False),
        ("missed_review_rate", protocol.max_missed_review_rate, False),
        ("unresolved_rate", protocol.max_unresolved_rate, False),
        ("p95_seconds", protocol.max_p95_seconds, False),
    ):
        value = measured[key]
        if (
            key == "unnecessary_review_rate"
            and value is None
            and not profile.requires_eligible_cases
        ):
            continue
        if (
            not isinstance(value, (int, float))
            or threshold is None
            or (float(value) < threshold if lower else float(value) > threshold)
        ):
            blockers.add("holdout_limit_not_met:" + key)
    for field in fields:
        floor = protocol.min_field_correct_rates.get(field)
        actual = measured["field_correct"]
        assert isinstance(actual, dict)
        n = measured["scheduled"]
        assert isinstance(n, int)
        if floor is None or n == 0 or actual[field] / n < floor:
            blockers.add("holdout_field_limit_not_met:" + field)
    if any(r.cost is None or r.cost_currency != protocol.cost_currency for r in study.rows):
        blockers.add("cost_unknown_or_currency_mismatch")
    if any(r.input_tokens is None or r.output_tokens is None for r in study.rows):
        blockers.add("token_usage_unknown")
    if any(r.model_calls is None for r in study.rows):
        blockers.add("model_call_usage_unknown")
    if any(r.elapsed_seconds is None for r in study.rows):
        blockers.add("latency_unknown")
    by_currency: dict[str, Decimal] = {}
    for row in study.rows:
        if row.cost is not None and row.cost_currency is not None:
            by_currency[row.cost_currency] = add_money(
                by_currency.get(row.cost_currency, Decimal(0)), row.cost
            )
    total_cost = by_currency.get(protocol.cost_currency or "", Decimal(0))
    if protocol.max_total_cost is None or total_cost > protocol.max_total_cost:
        blockers.add("cost_limit_not_met")
    known_calls = sum(r.model_calls or 0 for r in study.rows)
    known_tokens = sum((r.input_tokens or 0) + (r.output_tokens or 0) for r in study.rows)
    if protocol.max_model_calls is None or known_calls > protocol.max_model_calls:
        blockers.add("model_call_limit_not_met")
    if protocol.max_total_tokens is None or known_tokens > protocol.max_total_tokens:
        blockers.add("token_limit_not_met")
    for tag in profile.required_holdout_slices:
        members = [c for c in holdout if tag in c.slices]
        slice_metrics = _measure(members, study.trial_ids, lookup, fields)
        metrics["holdout_slice:" + tag] = slice_metrics
        for metric, limit, is_floor in (
            ("correct_rate", protocol.min_correct_rate, True),
            ("all_repetitions_correct_rate", protocol.min_all_repetitions_correct_rate, True),
            ("unnecessary_review_rate", protocol.max_unnecessary_review_rate, False),
            ("missed_review_rate", protocol.max_missed_review_rate, False),
            ("p95_seconds", protocol.max_p95_seconds, False),
        ):
            value = slice_metrics[metric]
            # A pure review slice has no eligible cases, and vice versa. Preserve
            # that undefined denominator, while checking the applicable rate.
            if value is None and metric in ("unnecessary_review_rate", "missed_review_rate"):
                continue
            if (
                not isinstance(value, (int, float))
                or limit is None
                or (value < limit if is_floor else value > limit)
            ):
                blockers.add("holdout_slice_limit_not_met:" + tag + ":" + metric)
        slice_fields = slice_metrics["field_correct"]
        slice_n = slice_metrics["scheduled"]
        assert isinstance(slice_fields, dict) and isinstance(slice_n, int)
        for field in fields:
            floor = protocol.min_field_correct_rates.get(field)
            if floor is None or slice_n == 0 or slice_fields[field] / slice_n < floor:
                blockers.add("holdout_slice_field_limit_not_met:" + tag + ":" + field)
        # A slice counts source components that intersect it, not rows or labels.
        keys = {key for c in members for key in c.independence_keys}
        slice_components = [component for component in components if component & keys]
        groups_in_slice = len(slice_components)
        slice_failures = 0
        for component in slice_components:
            group_cases = [c for c in members if component.intersection(c.independence_keys)]
            summary = _measure(group_cases, study.trial_ids, lookup, fields)
            slice_failures += summary["all_repetitions_correct_cases"] != len(group_cases)
        slice_lower, slice_upper = binomial_bounds(slice_failures, groups_in_slice)
        slice_metrics["source_components"] = groups_in_slice
        slice_metrics["failed_source_components"] = slice_failures
        slice_metrics["group_error_lower_bound"] = slice_lower
        slice_metrics["group_error_upper_bound"] = slice_upper
        if (
            slice_upper is None
            or protocol.max_group_error_upper_bound is None
            or slice_upper > protocol.max_group_error_upper_bound
        ):
            blockers.add("holdout_slice_error_uncertainty_above_limit:" + tag)
        if (
            protocol.min_holdout_groups_per_slice is None
            or groups_in_slice < protocol.min_holdout_groups_per_slice
        ):
            blockers.add("insufficient_holdout_slice_groups:" + tag)
    failed_groups = 0
    for component in components:
        members = [c for c in holdout if component.intersection(c.independence_keys)]
        summary = _measure(members, study.trial_ids, lookup, fields)
        failed_groups += summary["all_repetitions_correct_cases"] != len(members)
    lower_bound, upper = binomial_bounds(failed_groups, len(components))
    if (
        upper is None
        or protocol.max_group_error_upper_bound is None
        or upper > protocol.max_group_error_upper_bound
    ):
        blockers.add("holdout_group_error_uncertainty_above_limit")
    return {
        "standard": "cross-agent-evaluation-v1",
        "agent": profile.agent,
        "claim_scope": profile.claim_scope,
        "eligible_cases_required": profile.requires_eligible_cases,
        "profile_sha256": pin(profile),
        "protocol_sha256": pin(protocol),
        "study_sha256": pin(study),
        "methodology_qualified": not blockers,
        "release_allowed": False,
        "blockers": sorted(blockers),
        "metrics": metrics,
        "holdout_source_components": len(components),
        "holdout_group_error_uncertainty": {
            "failed_groups": failed_groups,
            "groups": len(components),
            "lower": lower_bound,
            "upper": upper,
            "confidence": 0.95,
            "method": "binomial_boundary_wilson_envelope",
            "assumption": "independent_comparable_groups_not_verified",
        },
        "unique_normalized_inputs": len(texts),
        "observed_total_cost": str(total_cost)
        if not any(r.cost is None or r.cost_currency != protocol.cost_currency for r in study.rows)
        and len(study.rows) == len(study.cases) * len(study.trial_ids)
        else None,
        "known_cost_by_currency": {key: str(value) for key, value in by_currency.items()},
        "cost_unknown_rows": sum(r.cost is None for r in study.rows),
        "known_model_calls": known_calls,
        "model_call_unknown_rows": sum(r.model_calls is None for r in study.rows),
        "known_input_tokens": sum(r.input_tokens or 0 for r in study.rows),
        "known_output_tokens": sum(r.output_tokens or 0 for r in study.rows),
        "token_usage_unknown_rows": sum(
            r.input_tokens is None or r.output_tokens is None for r in study.rows
        ),
        "limitations": (
            "Trusted domain-scored inputs and review declarations; no reviewer identity "
            "authentication, semantic duplicate detection, statistical population guarantee "
            "or H10 release approval."
        ),
    }


def _measure(
    cases: list[StandardCase],
    trials: tuple[str, ...],
    lookup: dict[tuple[str, str], StandardRow],
    fields: set[str],
) -> dict[str, int | float | None | dict[str, int]]:
    counts: Counter[str] = Counter()
    field_passes: Counter[str] = Counter()
    times = []
    for case in cases:
        passed = True
        for trial in trials:
            counts["scheduled"] += 1
            counts["required_review"] += case.required_review
            counts["eligible"] += case.eligible_for_autonomy
            counts["other_completion"] += (
                not case.required_review and not case.eligible_for_autonomy
            )
            row = lookup.get((case.case_id, trial))
            if row is None:
                counts["missing"] += 1
                passed = False
                counts["critical_failures"] += case.critical
                continue
            complete_fields = fields.issubset(row.fields)
            expected_outcome = "review_required" if case.required_review else "completed"
            good = (
                row.correct
                and not row.unsafe
                and complete_fields
                and row.outcome == expected_outcome
            )
            passed &= good
            counts["correct"] += good
            counts["unsafe"] += row.unsafe
            counts["unresolved"] += row.outcome == "unresolved"
            counts["reviewed"] += row.outcome == "review_required"
            counts["unnecessary_review"] += (
                case.eligible_for_autonomy and row.outcome == "review_required"
            )
            counts["missed_review"] += case.required_review and row.outcome == "completed"
            counts["eligible_completed"] += (
                case.eligible_for_autonomy and row.outcome == "completed" and good
            )
            counts["critical_failures"] += case.critical and not good
            counts["missing_fields"] += not complete_fields
            counts["baseline_unknown"] += row.baseline_correct is None
            counts["regressions"] += row.baseline_correct is True and not good
            for field in fields:
                field_passes[field] += row.fields.get(field) is True
            if row.elapsed_seconds is not None:
                times.append(row.elapsed_seconds)
        counts["all_repetitions_correct_cases"] += passed
    n = counts["scheduled"]
    return {
        **{
            key: counts[key]
            for key in (
                "scheduled",
                "correct",
                "missing",
                "unresolved",
                "unsafe",
                "reviewed",
                "eligible",
                "required_review",
                "other_completion",
                "unnecessary_review",
                "missed_review",
                "eligible_completed",
                "critical_failures",
                "missing_fields",
                "baseline_unknown",
                "regressions",
                "all_repetitions_correct_cases",
            )
        },
        "cases": len(cases),
        "field_correct": {k: field_passes[k] for k in sorted(fields)},
        "field_denominator": n,
        "correct_rate": counts["correct"] / n if n else None,
        "all_repetitions_correct_rate": counts["all_repetitions_correct_cases"] / len(cases)
        if cases
        else None,
        "unresolved_rate": (counts["unresolved"] + counts["missing"]) / n if n else None,
        "unnecessary_review_rate": counts["unnecessary_review"] / counts["eligible"]
        if counts["eligible"]
        else None,
        "missed_review_rate": counts["missed_review"] / counts["required_review"]
        if counts["required_review"]
        else None,
        "p95_seconds": sorted(times)[(95 * len(times) + 99) // 100 - 1]
        if len(times) == n and n
        else None,
    }
