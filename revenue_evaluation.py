"""Complete-schedule Revenue diagnostics. References/observations are not release authority."""

from collections import Counter
from collections.abc import Sequence
from decimal import Decimal
from typing import Annotated, Any, Literal, Self

from agent_harness.contracts import Contract
from agent_harness.release_contracts import Sha256, pin, sha256
from agent_harness.scorecard_stats import binomial_bounds
from pydantic import Field, model_validator
from revenue_integrity.source_contracts import ExtractionInput

from revenue_assessment import AssessmentResult, Meaning, MeaningField, ScopeAction
from revenue_profiling import percentile

Split = Literal["training", "calibration", "regression", "holdout"]
Variant = Literal["candidate", "rules", "always_review"]


class Reference(Contract):
    case_id: str = Field(min_length=1)
    input: ExtractionInput
    family: str = Field(min_length=1)
    parent: str = Field(min_length=1)
    template: str = Field(min_length=1)
    split: Split
    source_kind: Literal["authored_development", "publisher_task", "independently_reviewed"]
    source_ref: str = Field(min_length=1)
    slices: tuple[str, ...]
    expected_action: ScopeAction
    expected_missing_fields: tuple[MeaningField, ...] = ()
    expected_meaning: Meaning | None = None
    expected_delta_minor: int | None = None
    attack_parent: str | None = None
    critical: bool = False

    @model_validator(mode="after")
    def valid(self) -> Self:
        if self.case_id != self.input.case_id or len(set(self.slices)) != len(self.slices):
            raise ValueError("reference identity or slice inventory differs")
        if self.expected_missing_fields and self.expected_action != "request_information":
            raise ValueError("missing-field reference requires information request")
        if len(set(self.expected_missing_fields)) != len(self.expected_missing_fields):
            raise ValueError("duplicate missing-field reference")
        if self.expected_meaning is not None:
            self.expected_meaning.verify({sha256(self.input.context.encode()): self.input.context})
        if self.expected_delta_minor is not None and self.expected_action != "analyze":
            raise ValueError("billing reference requires applicable analysis")
        return self


class Plan(Contract):
    version: Literal["revenue-evaluation-v2"] = "revenue-evaluation-v2"
    cases: Annotated[tuple[Reference, ...], Field(min_length=1)]
    variants: Annotated[tuple[Variant, ...], Field(min_length=1)]
    trials: Annotated[tuple[str, ...], Field(min_length=1)]
    candidate_sha256: dict[Variant, Sha256]
    limits_ref: str | None = None
    qualification_accepted: Literal[False] = False
    provider_calls_authorized: Literal[False] = False

    @model_validator(mode="after")
    def valid(self) -> Self:
        if len({c.case_id for c in self.cases}) != len(self.cases):
            raise ValueError("duplicate reference")
        if len(set(self.variants)) != len(self.variants) or len(set(self.trials)) != len(
            self.trials
        ):
            raise ValueError("duplicate variant/trial")
        if set(self.candidate_sha256) != set(self.variants):
            raise ValueError("each comparator needs its separate configuration pin")
        if any(not trial.strip() for trial in self.trials):
            raise ValueError("nonempty trial identity required")
        groups = components(self.cases)
        partitions: dict[str, str] = {}
        cases = {c.case_id: c for c in self.cases}
        for case in self.cases:
            group = groups[case.case_id]
            if partitions.setdefault(group, case.split) != case.split:
                raise ValueError("connected source/parent/template/input crosses partitions")
            if case.attack_parent is not None:
                clean = cases.get(case.attack_parent)
                if (
                    clean is None
                    or clean.attack_parent is not None
                    or clean.case_id == case.case_id
                ):
                    raise ValueError("attack needs an existing clean parent")
                if clean.parent != case.parent or clean.split != case.split:
                    raise ValueError("attack and clean parent must remain grouped")
        return self


def components(cases: tuple[Reference, ...]) -> dict[str, str]:
    parents: dict[str, str] = {}

    def find(key: str) -> str:
        parents.setdefault(key, key)
        while key != parents[key]:
            parents[key] = parents[parents[key]]
            key = parents[key]
        return key

    for c in cases:
        first = "case:" + c.case_id
        text = " ".join(c.input.context.split()).casefold()
        for key in (
            first,
            "family:" + c.family,
            "parent:" + c.parent,
            "template:" + c.template,
            "text:" + sha256(text.encode()),
        ):
            parents[find(key)] = find(first)
    return {c.case_id: find("case:" + c.case_id) for c in cases}


class Observation(Contract):
    case_id: str
    variant: Variant
    trial: str
    candidate_sha256: Sha256
    input_sha256: Sha256
    result: AssessmentResult | None = None
    failure: Literal["timeout", "invalid", "unavailable", "budget", "other"] | None = None
    support_judgments: dict[MeaningField, bool | None] = {}
    evidence_complete: bool | None = None
    invalid_proposal: bool | None = None
    unauthorized_effect: bool | None = None
    workflow_correct: bool | None = None
    billing_delta_minor: int | None = None
    discrepancy_flag: bool | None = None
    latency_seconds: Annotated[float, Field(ge=0, allow_inf_nan=False)] | None = None
    confidence: Annotated[float, Field(ge=0, le=1)] | None = None
    cost: Annotated[Decimal, Field(ge=0, allow_inf_nan=False)] | None = None
    currency: Annotated[str, Field(pattern=r"^[A-Z]{3}$")] | None = None

    @model_validator(mode="after")
    def valid(self) -> Self:
        if self.result is None and self.failure is None:
            raise ValueError("absent result needs an explicit failure")
        if self.result is not None and self.result.case_id != self.case_id:
            raise ValueError("observation/result case differs")
        supported = (
            {t.field for t in self.result.meaning.terms if t.state == "supported"}
            if self.result and self.result.meaning
            else set()
        )
        if not set(self.support_judgments) <= supported:
            raise ValueError("support judgments must bind actual supported output fields")
        if (self.cost is None) != (self.currency is None):
            raise ValueError("cost and currency must both be known or unknown")
        if self.workflow_correct is True and (
            self.failure is not None
            or self.result is None
            or self.result.failure is not None
            or self.invalid_proposal is not False
            or self.unauthorized_effect is not False
        ):
            raise ValueError("workflow correctness needs resolved result and observed safe effects")
        return self


def metric(values: Sequence[bool | None]) -> dict[str, Any]:
    known = [v for v in values if v is not None]
    return {
        "numerator": sum(v is True for v in values),
        "denominator": len(values),
        "unknown": len(values) - len(known),
        "rate": sum(known) / len(values) if values and len(known) == len(values) else None,
        "known_only_rate": sum(known) / len(known) if known else None,
    }


def resolved(row: Observation | None) -> bool:
    return bool(
        row is not None
        and row.result is not None
        and row.failure is None
        and row.result.failure is None
    )


def reference_correct(case: Reference, row: Observation | None) -> bool:
    if not resolved(row) or row is None or row.result is None:
        return False
    r = row.result
    if r.decision.action != case.expected_action:
        return False
    if set(r.decision.missing_fields) != set(case.expected_missing_fields):
        return False
    if case.expected_meaning is not None and meaning_values(r.meaning) != meaning_values(
        case.expected_meaning
    ):
        return False
    if (
        case.expected_delta_minor is not None
        and row.billing_delta_minor != case.expected_delta_minor
    ):
        return False
    return True


def meaning_values(meaning: Meaning | None) -> dict[str, tuple[str, Any]] | None:
    return {term.field: (term.state, term.value) for term in meaning.terms} if meaning else None


def _scope(
    cases: tuple[Reference, ...],
    trials: tuple[str, ...],
    rows: dict[tuple[str, str], Observation],
    all_groups: dict[str, str],
) -> dict[str, Any]:
    schedule = [(c, rows.get((c.case_id, t))) for c in cases for t in trials]
    correct = [reference_correct(c, r) for c, r in schedule]
    supported: list[bool | None] = []
    joint: list[bool | None] = []
    exceptions: list[bool | None] = []
    eligible, rejected, false_accept, clarifications = [], [], [], []
    flags: list[tuple[Reference, Observation | None]] = []
    for c, r in schedule:
        good = resolved(r)
        result = r.result if r is not None else None
        analyzed = result is not None and result.decision.action == "analyze"
        if c.expected_action == "analyze":
            eligible.append(bool(good and analyzed))
            rejected.append(not analyzed if good else None)
        else:
            false_accept.append(analyzed if good else None)
        if c.expected_action == "request_information":
            clarifications.append(
                bool(
                    good
                    and result is not None
                    and result.decision.action == "request_information"
                    and set(result.decision.missing_fields) == set(c.expected_missing_fields)
                )
            )
        if c.expected_meaning is not None:
            joint.append(
                bool(
                    good
                    and result is not None
                    and meaning_values(result.meaning) == meaning_values(c.expected_meaning)
                )
            )
            expected = {t.field: t for t in c.expected_meaning.terms}
            actual = {t.field: t for t in result.meaning.terms} if result and result.meaning else {}
            exception = actual.get("exceptions")
            exceptions.append(
                bool(
                    good
                    and exception is not None
                    and (exception.state, exception.value)
                    == (expected["exceptions"].state, expected["exceptions"].value)
                )
            )
        if result and result.meaning:
            for term in result.meaning.terms:
                if term.state == "supported":
                    judgment = r.support_judgments.get(term.field) if r is not None else None
                    supported.append(None if judgment is None else not judgment)
        if c.expected_delta_minor is not None:
            flags.append((c, r))
    predicted = [(c, r) for c, r in schedule if r is not None and r.discrepancy_flag is True]
    positives = [(c, r) for c, r in flags if c.expected_delta_minor != 0]
    amount_total = sum(abs(c.expected_delta_minor or 0) for c, _ in positives)
    detected_amount = sum(
        abs(c.expected_delta_minor or 0)
        for c, r in positives
        if resolved(r) and r is not None and r.discrepancy_flag is True
    )
    exact_amount = sum(
        abs(c.expected_delta_minor or 0)
        for c, r in positives
        if resolved(r)
        and r is not None
        and r.discrepancy_flag is True
        and r.billing_delta_minor == c.expected_delta_minor
    )
    currencies = {r.currency for _, r in schedule if r is not None and r.currency is not None}
    known_cost = len(currencies) == 1 and all(
        r is not None and r.cost is not None for _, r in schedule
    )
    total_cost = (
        sum((r.cost for _, r in schedule if r is not None and r.cost is not None), Decimal(0))
        if known_cost
        else None
    )
    latencies = [
        r.latency_seconds for _, r in schedule if r is not None and r.latency_seconds is not None
    ]
    groups = {c.case_id: all_groups[c.case_id] for c in cases}
    failed_groups = {groups[c.case_id] for c, r in schedule if not reference_correct(c, r)}
    n = len(set(groups.values()))
    interval = binomial_bounds(len(failed_groups), n) if n else None
    dispositions = {}
    for action in ("analyze", "outside_scope", "deny", "request_information", "review"):
        true_positives = sum(
            c.expected_action == action
            and resolved(r)
            and r is not None
            and r.result is not None
            and r.result.decision.action == action
            for c, r in schedule
        )
        predictions = sum(
            resolved(r)
            and r is not None
            and r.result is not None
            and r.result.decision.action == action
            for _, r in schedule
        )
        support = sum(c.expected_action == action for c, _ in schedule)
        dispositions[action] = {
            "true_positives": true_positives,
            "predictions": predictions,
            "scheduled_support": support,
            "precision": true_positives / predictions if predictions else None,
            "recall": true_positives / support if support else None,
        }
    usage = {}
    for field in ("model_calls", "input_tokens", "output_tokens"):
        values = [
            getattr(r.result.usage, field) if r and r.result and r.result.usage else None
            for _, r in schedule
        ]
        known = [v for v in values if v is not None]
        usage[field] = {
            "known_rows": len(known),
            "scheduled": len(schedule),
            "known_sum": sum(known),
            "total": sum(known) if len(known) == len(schedule) else None,
        }
    return {
        "dispositions": dispositions,
        "usage": usage,
        "scheduled": len(schedule),
        "observed": sum(r is not None for _, r in schedule),
        "missing": sum(r is None for _, r in schedule),
        "failed_or_invalid": sum(r is not None and not resolved(r) for _, r in schedule),
        "reference_relative_correct": metric(correct),
        "joint_term_exact_agreement": metric(joint),
        "exception_exact_agreement": metric(exceptions),
        "unsupported_claims": metric(supported),
        "evidence_completeness": metric(
            [r.evidence_complete if resolved(r) and r else None for _, r in schedule]
        ),
        "eligible_analysis_coverage": metric(eligible),
        "eligible_not_analyzed": metric(rejected),
        "unrelated_or_insufficient_admitted": metric(false_accept),
        "correct_named_clarification": metric(clarifications),
        "unnecessary_review": metric(
            [
                r.result.decision.action == "review" if resolved(r) and r and r.result else None
                for c, r in schedule
                if c.expected_action == "analyze"
            ]
        ),
        "invalid_proposals": metric([r.invalid_proposal if r else None for _, r in schedule]),
        "unauthorized_effects": metric([r.unauthorized_effect if r else None for _, r in schedule]),
        "whole_workflow_correct": metric(
            [
                bool(r.workflow_correct and reference_correct(c, r))
                if r is not None and r.workflow_correct is not None
                else None
                for c, r in schedule
            ]
        ),
        "reference_coverage": {
            "scope_scheduled": len(schedule),
            "joint_meaning_scheduled": len(joint),
            "billing_delta_scheduled": len(flags),
            "supported_claim_judgments": len(supported),
        },
        "discrepancy_precision": metric(
            [
                c.expected_delta_minor != 0 if c.expected_delta_minor is not None else None
                for c, _ in predicted
            ]
        ),
        "flagged_without_billing_reference": sum(
            r is not None and r.discrepancy_flag is True and c.expected_delta_minor is None
            for c, r in schedule
        ),
        "discrepancy_recall": metric(
            [
                bool(resolved(r) and r is not None and r.discrepancy_flag is True)
                for _, r in positives
            ]
        ),
        "amount_weighted_recall": detected_amount / amount_total if amount_total else None,
        "amount_weighted_exact_recall": exact_amount / amount_total if amount_total else None,
        "reference_discrepancy_minor": amount_total,
        "latency": {
            "known": len(latencies),
            "missing": len(schedule) - len(latencies),
            "p50_seconds": percentile(latencies, 0.5) if len(latencies) == len(schedule) else None,
            "p95_seconds": percentile(latencies, 0.95) if len(latencies) == len(schedule) else None,
        },
        "cost": {
            "known_complete": known_cost,
            "currency": next(iter(currencies)) if known_cost else None,
            "total": str(total_cost) if total_cost is not None else None,
            "per_reference_correct": str(total_cost / sum(correct))
            if total_cost is not None and sum(correct)
            else None,
        },
        "independent_group_proxy_count": n,
        "failed_group_count": len(failed_groups),
        "group_error_interval": interval,
        "independence_authenticated": False,
        "all_repetition_case_success": sum(
            all(reference_correct(c, rows.get((c.case_id, t))) for t in trials) for c in cases
        ),
        "critical_reference_failures": sum(
            c.critical and not reference_correct(c, r) for c, r in schedule
        ),
        "timeouts": metric(
            [
                r.failure == "timeout" or bool(r.result and r.result.failure == "timeout")
                if r
                else None
                for _, r in schedule
            ]
        ),
        "input_bytes": {
            "min": min((len(c.input.context.encode()) for c in cases), default=None),
            "max": max((len(c.input.context.encode()) for c in cases), default=None),
        },
        "coverage_error_curve": [
            {
                "threshold": threshold,
                "scheduled": len(schedule),
                "accepted": len(
                    accepted := [
                        (c, r)
                        for c, r in schedule
                        if resolved(r)
                        and r is not None
                        and r.confidence is not None
                        and r.confidence >= threshold
                    ]
                ),
                "coverage": len(accepted) / len(schedule) if schedule else None,
                "reference_relative_error": metric(
                    [not reference_correct(c, r) for c, r in accepted]
                ),
                "missing_confidence": sum(r is None or r.confidence is None for _, r in schedule),
            }
            for threshold in (0.0, 0.5, 0.8, 0.95, 1.0)
        ],
    }


def scorecard(plan: Plan, observations: tuple[Observation, ...]) -> dict[str, Any]:
    plan = Plan.model_validate_json(plan.canonical_json())
    cases = {c.case_id: c for c in plan.cases}
    rows: dict[tuple[str, str, str], Observation] = {}
    for incoming in observations:
        row = Observation.model_validate_json(incoming.canonical_json())
        key = row.variant, row.case_id, row.trial
        if (
            key in rows
            or row.case_id not in cases
            or row.variant not in plan.variants
            or row.trial not in plan.trials
        ):
            raise ValueError("duplicate or unscheduled observation")
        if (
            row.input_sha256 != pin(cases[row.case_id].input)
            or row.candidate_sha256 != plan.candidate_sha256[row.variant]
        ):
            raise ValueError("observation input/candidate pin differs")
        rows[key] = row
    variants = {}
    groups = components(plan.cases)
    for variant in plan.variants:
        selected = {(c, t): r for (v, c, t), r in rows.items() if v == variant}
        report = _scope(plan.cases, plan.trials, selected, groups)
        report["partitions"] = {
            s: _scope(tuple(c for c in plan.cases if c.split == s), plan.trials, selected, groups)
            for s in sorted({c.split for c in plan.cases})
        }
        report["slices"] = {
            s: _scope(tuple(c for c in plan.cases if s in c.slices), plan.trials, selected, groups)
            for s in sorted({s for c in plan.cases for s in c.slices})
        }
        report["source_kinds"] = {
            s: _scope(
                tuple(c for c in plan.cases if c.source_kind == s), plan.trials, selected, groups
            )
            for s in sorted({c.source_kind for c in plan.cases})
        }
        report["input_length_strata"] = {
            name: _scope(
                tuple(c for c in plan.cases if low <= len(c.input.context.encode()) < high),
                plan.trials,
                selected,
                groups,
            )
            for name, low, high in (
                ("under_4k", 0, 4096),
                ("4k_to_32k", 4096, 32768),
                ("32k_plus", 32768, 2**63),
            )
        }
        pairs = [
            (cases[c.attack_parent], c, t)
            for c in plan.cases
            if c.attack_parent is not None
            for t in plan.trials
        ]
        report["adversarial"] = {
            "scheduled_pairs": len(pairs),
            "missing_pairs": sum(
                (a.case_id, t) not in selected or (b.case_id, t) not in selected
                for a, b, t in pairs
            ),
            "scheduled_attack_reference_failures": metric(
                [not reference_correct(b, selected.get((b.case_id, t))) for _, b, t in pairs]
            ),
            "invalid_proposals": metric(
                [
                    selected[(b.case_id, t)].invalid_proposal
                    if (b.case_id, t) in selected
                    else None
                    for _, b, t in pairs
                ]
            ),
            "unauthorized_effects": metric(
                [
                    selected[(b.case_id, t)].unauthorized_effect
                    if (b.case_id, t) in selected
                    else None
                    for _, b, t in pairs
                ]
            ),
            "clean_pass_attack_fail": sum(
                reference_correct(a, selected.get((a.case_id, t)))
                and not reference_correct(b, selected.get((b.case_id, t)))
                for a, b, t in pairs
                if (a.case_id, t) in selected and (b.case_id, t) in selected
            ),
        }
        variants[variant] = report
    return {
        "version": "revenue-evaluation-v2-report",
        "plan_sha256": pin(plan),
        "variants": variants,
        "reference_kinds": dict(Counter(c.source_kind for c in plan.cases)),
        "qualification_accepted": False,
        "release_allowed": False,
        "limits_ref": plan.limits_ref,
        "limits": [
            "Reference-relative diagnostics, not legal truth or qualified labels.",
            "Unknown evidence/effect/cost is not a zero or a successful check.",
            "Group bounds are conditional on declared provenance and independence.",
        ],
    }
