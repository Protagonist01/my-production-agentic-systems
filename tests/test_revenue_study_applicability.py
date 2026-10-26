"""Original citations, billing and effects keep separate applicable denominators."""

import pytest
from agent_harness.offline_example import example_context
from revenue_integrity.release_evaluation import BillingObservation, ExtractionObservation
from revenue_integrity.study_evidence import (
    TrialBinding,
    billing_checks,
    check_summary,
    extraction_checks,
    scoped_fields,
)
from test_revenue_release_evaluation import billing_plan, claim, extraction_plan, result


def binding(case_id, tenant="invented"):
    context = example_context("invented", "b" * 64)
    return TrialBinding(
        candidate_sha256="a" * 64,
        context=context.model_copy(
            update={
                "agent_id": "revenue",
                "case_id": case_id,
                "trial_id": "t1",
                "tenant_id": tenant,
                "versions": context.versions.model_copy(update={"data_snapshot": "c" * 64}),
            }
        ),
    )


def test_original_no_answer_has_undefined_span_denominators_without_forged_pass():
    case = extraction_plan().cases[1]
    observation = ExtractionObservation(
        case_id=case.input.case_id, trial_id="t1", claim=claim(case.input, outcome="unsupported")
    )
    checks = extraction_checks(case, observation, binding(case.input.case_id))
    values = {c.name: c for c in checks}
    for name in (
        "span_precision_check",
        "span_recall_check",
        "reconciliation_amount",
        "authorization",
    ):
        assert not values[name].applicable and values[name].passed is None
    assert values["abstention"].passed and values["execution_health"].passed
    assert values["supported_terms"].applicable and values["supported_terms"].passed is None
    assert not check_summary(checks)["complete"] and not check_summary(checks)["release_allowed"]
    failed = observation.model_copy(update={"failure_code": "timeout"})
    assert not {c.name: c for c in extraction_checks(case, failed, binding(case.input.case_id))}[
        "execution_health"
    ].passed


def test_missing_answer_spans_keep_reference_recall_and_abstention_failure():
    case = extraction_plan().cases[0]
    observation = ExtractionObservation(
        case_id=case.input.case_id, trial_id="t1", claim=claim(case.input, outcome="unsupported")
    )
    values = {c.name: c for c in extraction_checks(case, observation, binding(case.input.case_id))}
    assert values["span_recall_check"].applicable and not values["span_recall_check"].passed
    assert not values["abstention"].passed
    with pytest.raises(ValueError, match="scope"):
        extraction_checks(case, observation, binding("wrong"))


def test_sim_arithmetic_does_not_claim_original_contract_support_or_business_effects():
    case = billing_plan().cases[0]
    observation = BillingObservation(case_id=case.input.case_id, trial_id="t1", result=result(case))
    scope = binding(case.input.case_id, case.input.tenant_id)
    values = {c.name: c for c in billing_checks(case, observation, scope)}
    assert values["reconciliation_amount"].passed and values["reconciliation_reason"].passed
    assert values["supported_terms"].passed is None
    assert not values["exact_state"].applicable and values["exact_state"].passed is None
    failed = {
        c.name: c
        for c in billing_checks(case, observation.model_copy(update={"result": None}), scope)
    }
    assert not failed["reconciliation_amount"].passed and not failed["execution_health"].passed
    with pytest.raises(ValueError, match="unrelated"):
        scoped_fields("original-extraction", {"authorization": True}, evidence_ref="invented")


def test_empty_or_entirely_unrelated_checks_cannot_claim_complete_study():
    from revenue_integrity.study_evidence import ApplicableCheck

    for checks in (
        (),
        (
            ApplicableCheck(
                name="unrelated", applicable=False, passed=None, reason="Different study"
            ),
        ),
    ):
        with pytest.raises(ValueError, match="applicable obligations"):
            check_summary(checks)
