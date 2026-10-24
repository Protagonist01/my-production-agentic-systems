"""Literal invented span/SIM arithmetic expectations, independent of candidate code."""

import pytest
from revenue_integrity.billing_contracts import BillingCase, BillingExpected, Invoice
from revenue_integrity.extraction import ExtractionClaim
from revenue_integrity.reconcile import Reconciliation
from revenue_integrity.release_evaluation import (
    BillingObservation,
    BillingPlan,
    ExtractionCase,
    ExtractionObservation,
    ExtractionPlan,
    billing_report,
    extraction_report,
)
from revenue_integrity.source_contracts import ExtractionInput, PublishedTarget, Span
from test_revenue_reconcile import case


def extraction_plan():
    cases = []
    for i in (1, 2):
        value = ExtractionInput(
            case_id=str(i) * 64, context="Invented α renewal.", question="Renewal?"
        )
        target = PublishedTarget(
            case_id=value.case_id,
            category="Renewal",
            answers=(Span(start=11, text="renewal"),) if i == 1 else (),
            impossible=i == 2,
            family_id=str(i + 2) * 64,
            split="holdout",
        )
        cases.append(ExtractionCase(input=value, target=target))
    return ExtractionPlan(
        source_manifest_sha256="a" * 64, cases=tuple(cases), trial_ids=("t1", "t2")
    )


def claim(value, spans=(), outcome="supported"):
    return ExtractionClaim(
        case_id=value.case_id, outcome=outcome, spans=spans, rationale="Invented test claim."
    )


def test_original_span_report_keeps_missing_recall_and_no_answer_denominators():
    plan = extraction_plan()
    value = plan.cases[0].input
    noanswer = plan.cases[1].input
    report = extraction_report(
        plan,
        (
            ExtractionObservation(
                case_id=value.case_id,
                trial_id="t1",
                claim=claim(value, (Span(start=11, text="renewal"),)),
            ),
            ExtractionObservation(
                case_id=noanswer.case_id,
                trial_id="t1",
                claim=claim(noanswer, outcome="unsupported"),
            ),
            ExtractionObservation(
                case_id=noanswer.case_id,
                trial_id="t2",
                claim=claim(noanswer, outcome="uncertain"),
                failure_code="timeout",
            ),
        ),
    )
    m = report["all"]
    assert m["scheduled"] == 4 and m["missing"] == 1 and m["failed"] == 1 and m["correct"] == 2
    assert m["reference_spans"] == 2 and m["matched_spans"] == m["submitted_spans"] == 1
    assert m["exact_span_precision"] == 1 and m["exact_span_recall"] == 0.5
    assert m["no_answer"] == 2 and m["no_answer_correct"] == 1
    assert m["supported"] == m["abstained"] == m["uncertain"] == 1
    assert not report["release_allowed"] and report["source_kind"] == "original"


@pytest.mark.parametrize(
    "spans",
    [
        (Span(start=0, text="fabricated"),),
        (Span(start=11, text="renewal"), Span(start=11, text="renewal")),
    ],
)
def test_forged_and_duplicate_spans_stay_in_precision_denominator(spans):
    plan = extraction_plan()
    value = plan.cases[0].input
    m = extraction_report(
        plan,
        (ExtractionObservation(case_id=value.case_id, trial_id="t1", claim=claim(value, spans)),),
    )["all"]
    assert m["invalid"] == 1 and m["matched_spans"] == 0 and m["submitted_spans"] == len(spans)
    assert m["exact_span_precision"] == 0 and m["exact_span_recall"] == 0


def billing_plan():
    cases = []
    for i, (issued, expected) in enumerate(
        ((2900, 3000), (2000, 3000), (3000, 3000), (3000, None))
    ):
        value = case(case_id="sim-" + str(i), invoice=Invoice(amount_minor=issued))
        cases.append(
            BillingCase(
                input=value,
                group_id="group-" + str(i),
                split="holdout",
                treatment="invented",
                expected=BillingExpected(
                    should_be_minor=expected,
                    disposition="review"
                    if expected is None
                    else "correct"
                    if expected == issued
                    else "underbilled",
                    reason="literal-review" if expected is None else "literal",
                    arithmetic="Independently specified invented amounts.",
                ),
            )
        )
    return BillingPlan(source_manifest_sha256="b" * 64, cases=tuple(cases), trial_ids=("t1",))


def result(case, *, amount=3000, reason="literal"):
    issued = case.input.invoice.amount_minor
    return Reconciliation(
        case_id=case.input.case_id,
        disposition="review"
        if amount is None
        else "correct"
        if amount == issued
        else "underbilled"
        if amount > issued
        else "overbilled",
        should_be_minor=amount,
        issued_minor=issued,
        delta_minor=amount - issued if amount is not None else None,
        reasons=(reason,),
    )


def test_sim_billing_reports_amount_weighted_recall_and_benign_false_alarm():
    plan = billing_plan()
    observations = (
        BillingObservation(
            case_id=plan.cases[0].input.case_id, trial_id="t1", result=result(plan.cases[0])
        ),
        BillingObservation(
            case_id=plan.cases[2].input.case_id,
            trial_id="t1",
            result=result(plan.cases[2], amount=3100),
        ),
        BillingObservation(
            case_id=plan.cases[3].input.case_id, trial_id="t1", result=result(plan.cases[3])
        ),
    )
    report = billing_report(plan, observations)
    m = report["all"]
    assert m["scheduled"] == 4 and m["missing"] == 1 and m["correct"] == 1
    assert m["discrepancies"] == 2 and m["detected_discrepancies"] == 1
    assert m["case_discrepancy_recall"] == 0.5 and m["sim_amount_weighted_recall"] == pytest.approx(
        100 / 1100
    )
    assert m["benign"] == m["false_alarms"] == m["missed_review"] == 1
    assert (
        report["unit"] == "SIM"
        and report["source_kind"] == "synthetic"
        and not report["release_allowed"]
    )


def test_wrong_billing_amount_can_detect_direction_without_exact_correctness():
    plan = billing_plan()
    c = plan.cases[0]
    m = billing_report(
        plan,
        (
            BillingObservation(
                case_id=c.input.case_id, trial_id="t1", result=result(c, amount=3100)
            ),
        ),
    )["all"]
    assert m["detected_discrepancies"] == 1 and m["exact_discrepancies"] == m["correct"] == 0
    assert m["amount_correct"] == 0 and m["reason_correct"] == 1


@pytest.mark.parametrize("mode", ["duplicate", "identity", "family", "reference"])
def test_revenue_reference_and_population_tampering_rejected(mode):
    plan = extraction_plan()
    c = plan.cases[0]
    o = ExtractionObservation(
        case_id=c.input.case_id, trial_id="t1", claim=claim(c.input, outcome="unsupported")
    )
    if mode == "duplicate":
        observations = (o, o)
    else:
        observations = (o,)
    if mode == "identity":
        observations = (
            o.model_copy(update={"claim": o.claim.model_copy(update={"case_id": "wrong"})}),
        )
    if mode == "family":
        plan = plan.model_copy(
            update={
                "cases": (
                    c,
                    plan.cases[1].model_copy(
                        update={
                            "target": plan.cases[1].target.model_copy(
                                update={"family_id": c.target.family_id, "split": "development"}
                            )
                        }
                    ),
                )
            }
        )
    if mode == "reference":
        plan = plan.model_copy(
            update={
                "cases": (
                    c.model_copy(
                        update={
                            "target": c.target.model_copy(
                                update={"answers": (Span(start=0, text="invented-wrong"),)}
                            )
                        }
                    ),
                    plan.cases[1],
                )
            }
        )
    with pytest.raises(ValueError):
        extraction_report(plan, observations)
