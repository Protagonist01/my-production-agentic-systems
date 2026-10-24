"""R7 reference-relative extraction and SIM billing metrics; no release/effect claims."""

from collections import Counter

from agent_harness.contracts import Contract, NonEmpty
from agent_harness.evaluation_population import ratio, validate_matrix
from agent_harness.release_contracts import Sha256, pin

from revenue_integrity.billing_contracts import BillingCase
from revenue_integrity.extraction import ExtractionClaim
from revenue_integrity.reconcile import Reconciliation
from revenue_integrity.source_contracts import ExtractionInput, PublishedTarget


class ExtractionCase(Contract):
    input: ExtractionInput
    target: PublishedTarget


class ExtractionPlan(Contract):
    source_manifest_sha256: Sha256
    cases: tuple[ExtractionCase, ...]
    trial_ids: tuple[NonEmpty, ...]


class ExtractionObservation(Contract):
    case_id: NonEmpty
    trial_id: NonEmpty
    claim: ExtractionClaim | None = None
    failure_code: NonEmpty | None = None


def extraction_report(
    plan: ExtractionPlan, observations: tuple[ExtractionObservation, ...]
) -> dict[str, object]:
    plan = ExtractionPlan.model_validate_json(plan.canonical_json())
    observations = tuple(
        ExtractionObservation.model_validate_json(o.canonical_json()) for o in observations
    )
    validate_matrix(
        tuple(c.input.case_id for c in plan.cases),
        plan.trial_ids,
        tuple((o.case_id, o.trial_id) for o in observations),
    )
    families: dict[str, set[str]] = {}
    for case in plan.cases:
        target, value = case.target, case.input
        if target.case_id != value.case_id:
            raise ValueError("Revenue extraction target differs from input identity")
        families.setdefault(target.family_id, set()).add(target.split)
        for span in target.answers:
            if value.context[span.start : span.start + len(span.text)] != span.text:
                raise ValueError("Revenue reference span differs from original context")
        if len({(s.start, s.text) for s in target.answers}) != len(target.answers):
            raise ValueError("duplicate Revenue reference span")
    if any(len(splits) != 1 for splits in families.values()):
        raise ValueError("Revenue document family crosses splits")
    for o in observations:
        if o.claim and o.claim.case_id != o.case_id:
            raise ValueError("Revenue extraction claim identity differs")
    lookup = {(o.case_id, o.trial_id): o for o in observations}

    def measure(cases: tuple[ExtractionCase, ...]) -> dict[str, object]:
        counts: Counter[str] = Counter()
        for case in cases:
            expected = {(s.start, s.text) for s in case.target.answers}
            for trial in plan.trial_ids:
                counts["scheduled"] += 1
                counts["reference_spans"] += len(expected)
                counts["no_answer"] += case.target.impossible
                o = lookup.get((case.input.case_id, trial))
                claim = o.claim if o else None
                counts["missing"] += o is None or claim is None
                failed = bool(o and o.failure_code)
                counts["failed"] += failed
                valid = claim is not None and (claim.outcome == "supported") == bool(claim.spans)
                occupied: list[tuple[int, int]] = []
                for span in claim.spans if claim else ():
                    end = span.start + len(span.text)
                    valid &= case.input.context[span.start : end] == span.text and not any(
                        span.start < right and end > left for left, right in occupied
                    )
                    occupied.append((span.start, end))
                counts["invalid"] += claim is not None and not valid
                unresolved = not valid or failed or bool(claim and claim.outcome == "uncertain")
                counts["unresolved"] += unresolved
                counts["supported"] += bool(
                    claim and not unresolved and claim.outcome == "supported"
                )
                counts["abstained"] += bool(
                    claim and not unresolved and claim.outcome == "unsupported"
                )
                counts["uncertain"] += bool(claim and claim.outcome == "uncertain")
                predicted = (
                    {(s.start, s.text) for s in claim.spans}
                    if claim and valid and not failed
                    else set()
                )
                # Even invalid/duplicate/failed submitted spans remain in precision's denominator.
                counts["submitted_spans"] += len(claim.spans) if claim else 0
                counts["matched_spans"] += len(expected & predicted)
                correct = bool(
                    claim
                    and not unresolved
                    and (
                        claim.outcome == "unsupported"
                        if case.target.impossible
                        else claim.outcome == "supported" and predicted == expected
                    )
                )
                counts["correct"] += correct
                counts["no_answer_correct"] += case.target.impossible and correct
                counts["false_support"] += case.target.impossible and bool(
                    claim and claim.outcome == "supported"
                )
        return {
            "cases": len(cases),
            "document_families": len({c.target.family_id for c in cases}),
            **{
                k: counts[k]
                for k in (
                    "scheduled",
                    "correct",
                    "missing",
                    "failed",
                    "invalid",
                    "unresolved",
                    "reference_spans",
                    "submitted_spans",
                    "matched_spans",
                    "no_answer",
                    "no_answer_correct",
                    "false_support",
                    "supported",
                    "abstained",
                    "uncertain",
                )
            },
            "exact_span_precision": ratio(counts["matched_spans"], counts["submitted_spans"]),
            "exact_span_recall": ratio(counts["matched_spans"], counts["reference_spans"]),
            "case_correct_rate": ratio(counts["correct"], counts["scheduled"]),
        }

    return {
        "version": "revenue-original-extraction-report-v1",
        "plan_sha256": pin(plan),
        "release_allowed": False,
        "source_kind": "original",
        "all": measure(plan.cases),
        "categories": {
            category: measure(tuple(c for c in plan.cases if c.target.category == category))
            for category in sorted({c.target.category for c in plan.cases})
        },
        "splits": {
            s: measure(tuple(c for c in plan.cases if c.target.split == s))
            for s in ("development", "holdout")
        },
        "limitations": (
            "Exact literal spans against publisher references only; no legal meaning, "
            "supported numeric terms or recovered revenue claim. Qualified review, H10 "
            "receipts/accounting, state/authorization/recovery and methodology release "
            "gates remain required."
        ),
    }


class BillingPlan(Contract):
    source_manifest_sha256: Sha256
    cases: tuple[BillingCase, ...]
    trial_ids: tuple[NonEmpty, ...]


class BillingObservation(Contract):
    case_id: NonEmpty
    trial_id: NonEmpty
    result: Reconciliation | None = None
    failure_code: NonEmpty | None = None


def billing_report(
    plan: BillingPlan, observations: tuple[BillingObservation, ...]
) -> dict[str, object]:
    plan = BillingPlan.model_validate_json(plan.canonical_json())
    observations = tuple(
        BillingObservation.model_validate_json(o.canonical_json()) for o in observations
    )
    validate_matrix(
        tuple(c.input.case_id for c in plan.cases),
        plan.trial_ids,
        tuple((o.case_id, o.trial_id) for o in observations),
    )
    groups: dict[str, set[str]] = {}
    for case in plan.cases:
        groups.setdefault(case.group_id, set()).add(case.split)
        expected, value = case.expected, case.input
        amount = expected.should_be_minor
        disposition = (
            "review"
            if amount is None
            else "correct"
            if amount == value.invoice.amount_minor
            else "underbilled"
            if amount > value.invoice.amount_minor
            else "overbilled"
        )
        if expected.disposition != disposition:
            raise ValueError("Revenue literal amount/disposition reference conflicts")
    if any(len(splits) != 1 for splits in groups.values()):
        raise ValueError("Revenue billing group crosses splits")
    lookup = {(o.case_id, o.trial_id): o for o in observations}
    for o in observations:
        if o.result and o.result.case_id != o.case_id:
            raise ValueError("Revenue billing result belongs to different case")

    def measure(cases: tuple[BillingCase, ...]) -> dict[str, object]:
        counts: Counter[str] = Counter()
        for case in cases:
            expected, issued = case.expected, case.input.invoice.amount_minor
            delta = (
                expected.should_be_minor - issued if expected.should_be_minor is not None else None
            )
            discrepancy = expected.disposition in ("underbilled", "overbilled")
            for trial in plan.trial_ids:
                counts["scheduled"] += 1
                counts["discrepancies"] += discrepancy
                counts["discrepancy_minor"] += abs(delta or 0)
                counts["benign"] += expected.disposition == "correct"
                counts["required_review"] += expected.disposition == "review"
                o = lookup.get((case.input.case_id, trial))
                result = o.result if o else None
                failed = bool(o and o.failure_code)
                valid = bool(
                    result
                    and (result.should_be_minor is None or result.should_be_minor >= 0)
                    and result.issued_minor == issued
                    and result.delta_minor
                    == (
                        result.should_be_minor - issued
                        if result.should_be_minor is not None
                        else None
                    )
                    and result.disposition
                    == (
                        "review"
                        if result.should_be_minor is None
                        else "correct"
                        if result.should_be_minor == issued
                        else "underbilled"
                        if result.should_be_minor > issued
                        else "overbilled"
                    )
                )
                counts["missing"] += result is None
                counts["failed"] += failed
                counts["invalid"] += result is not None and not valid
                counts["unresolved"] += not valid or failed
                correct = bool(
                    result
                    and valid
                    and not failed
                    and result.should_be_minor == expected.should_be_minor
                    and result.disposition == expected.disposition
                    and result.reasons == (expected.reason,)
                )
                counts["amount_correct"] += bool(
                    result
                    and valid
                    and not failed
                    and result.should_be_minor == expected.should_be_minor
                )
                counts["reason_correct"] += bool(
                    result and valid and not failed and result.reasons == (expected.reason,)
                )
                counts["correct"] += correct
                detected = bool(
                    result
                    and valid
                    and not failed
                    and discrepancy
                    and result.disposition == expected.disposition
                )
                counts["detected_discrepancies"] += detected
                counts["detected_discrepancy_minor"] += abs(delta or 0) if detected else 0
                counts["exact_discrepancies"] += discrepancy and correct
                counts["false_alarms"] += expected.disposition == "correct" and bool(
                    result
                    and valid
                    and not failed
                    and result.disposition in ("underbilled", "overbilled")
                )
                counts["reviewed"] += bool(
                    result and valid and not failed and result.disposition == "review"
                )
                counts["missed_review"] += expected.disposition == "review" and bool(
                    result and result.disposition != "review"
                )
                counts["unnecessary_review"] += expected.disposition != "review" and bool(
                    result and valid and not failed and result.disposition == "review"
                )
        return {
            "cases": len(cases),
            "source_groups": len({c.group_id for c in cases}),
            **{
                k: counts[k]
                for k in (
                    "scheduled",
                    "correct",
                    "missing",
                    "failed",
                    "invalid",
                    "unresolved",
                    "discrepancies",
                    "detected_discrepancies",
                    "exact_discrepancies",
                    "discrepancy_minor",
                    "detected_discrepancy_minor",
                    "benign",
                    "false_alarms",
                    "required_review",
                    "reviewed",
                    "missed_review",
                    "unnecessary_review",
                    "amount_correct",
                    "reason_correct",
                )
            },
            "case_discrepancy_recall": ratio(
                counts["detected_discrepancies"], counts["discrepancies"]
            ),
            "sim_amount_weighted_recall": ratio(
                counts["detected_discrepancy_minor"], counts["discrepancy_minor"]
            ),
            "benign_false_alarm_rate": ratio(counts["false_alarms"], counts["benign"]),
        }

    return {
        "version": "revenue-sim-billing-report-v1",
        "plan_sha256": pin(plan),
        "release_allowed": False,
        "source_kind": "synthetic",
        "unit": "SIM",
        "all": measure(plan.cases),
        "treatments": {
            t: measure(tuple(c for c in plan.cases if c.treatment == t))
            for t in sorted({c.treatment for c in plan.cases})
        },
        "splits": {
            s: measure(tuple(c for c in plan.cases if c.split == s))
            for s in ("development", "regression", "holdout")
        },
        "limitations": (
            "Literal AI-provisional billing references, not real extraction or recovered "
            "revenue. Detection recall requires the correct discrepancy direction; exact "
            "amount/reason correctness is separate. This report observes no mutation and "
            "proves no authorization, compensation, exact state, recovery, engine ablation "
            "or fresh-provider release gate."
        ),
    }
