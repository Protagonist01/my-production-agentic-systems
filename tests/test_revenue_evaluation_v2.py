"""Independent small arithmetic witnesses for denominators, missingness and split controls."""

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from agent_harness.release_contracts import pin

from revenue_assessment import AssessmentResult, ScopeDecision
from revenue_diagnostics import capture, development_plan, fixtures, readback, rules
from revenue_evaluation import Observation, Plan, metric, scorecard
from revenue_profiling import Recorder
from revenue_protocol import Criteria, Study, audit


def observation(plan, case, *, trial="trial-1", **changes):
    fields = dict(
        case_id=case.case_id,
        variant="rules",
        trial=trial,
        candidate_sha256=plan.candidate_sha256["rules"],
        input_sha256=pin(case.input),
        result=AssessmentResult(
            case_id=case.case_id, decision=ScopeDecision(action="review", reason="scope_uncertain")
        ),
    )
    fields.update(changes)
    return Observation(**fields)


def test_empty_schedule_unknowns_are_not_zero_cost_safety_or_measured_quality():
    plan = development_plan()
    report = scorecard(plan, ())
    measured = report["variants"]["rules"]
    assert measured["scheduled"] == measured["missing"] == 48
    assert measured["reference_relative_correct"]["numerator"] == 0
    assert measured["reference_relative_correct"]["denominator"] == 48
    assert measured["unauthorized_effects"] == {
        "numerator": 0,
        "denominator": 48,
        "unknown": 48,
        "rate": None,
        "known_only_rate": None,
    }
    assert measured["cost"]["total"] is None
    assert measured["latency"]["p95_seconds"] is None
    assert measured["unnecessary_review"]["rate"] is None
    assert measured["independent_group_proxy_count"] == 1
    assert report["release_allowed"] is False


def test_one_observation_cannot_erase_missing_trials_or_supply_unknown_effects():
    plan = development_plan()
    row = observation(
        plan, plan.cases[0], latency_seconds=2.0, cost=Decimal("0.25"), currency="USD"
    )
    measured = scorecard(plan, (row,))["variants"]["rules"]
    assert measured["observed"] == 1 and measured["missing"] == 47
    assert measured["cost"]["known_complete"] is False
    assert measured["unauthorized_effects"]["unknown"] == 48
    assert measured["coverage_error_curve"][0]["missing_confidence"] == 48


def test_duplicate_extra_wrong_input_and_candidate_pins_refuse():
    plan = development_plan()
    row = observation(plan, plan.cases[0])
    with pytest.raises(ValueError):
        scorecard(plan, (row, row))
    for update in ({"trial": "extra"}, {"input_sha256": "f" * 64}, {"candidate_sha256": "f" * 64}):
        with pytest.raises(ValueError):
            scorecard(plan, (row.model_copy(update=update),))


def test_split_leakage_through_template_and_intermediate_group_is_refused():
    plan = development_plan()
    cases = (plan.cases[0], plan.cases[1].model_copy(update={"split": "holdout"}))
    with pytest.raises(ValueError):
        Plan.model_validate(plan.model_copy(update={"cases": cases}).model_dump())
    # Full graph remains joined in a slice even if the bridging record is omitted.
    a, b, c = plan.cases[:3]
    a = a.model_copy(update={"family": "a", "template": "one", "parent": "a", "slices": ("edge",)})
    b = b.model_copy(
        update={
            "family": "a",
            "template": "two",
            "parent": "b",
            "attack_parent": None,
            "slices": ("bridge",),
        }
    )
    c = c.model_copy(update={"family": "c", "template": "two", "parent": "c", "slices": ("edge",)})
    plan = Plan.model_validate(plan.model_copy(update={"cases": (a, b, c)}).model_dump())
    assert (
        scorecard(plan, ())["variants"]["rules"]["slices"]["edge"]["independent_group_proxy_count"]
        == 1
    )


def test_partial_independent_support_judgment_retains_unknown_claims():
    plan = development_plan()
    result = rules(fixtures()[0], Recorder())
    row = observation(
        plan, plan.cases[0], result=result, support_judgments={"unit_price_minor": False}
    )
    metric_ = scorecard(plan, (row,))["variants"]["rules"]["unsupported_claims"]
    assert metric_["numerator"] == 1 and metric_["denominator"] == 8
    assert metric_["unknown"] == 7 and metric_["rate"] is None


def test_paired_capture_has_actual_baselines_missing_candidate_and_recomputable_readback(tmp_path):
    output = tmp_path / "capture"
    digest = capture(output)
    assert readback(output, digest)["observations"] == 96
    report = json.loads((output / "report.json").read_text())
    assert report["variants"]["candidate"]["missing"] == 48
    assert report["variants"]["rules"]["reference_relative_correct"]["numerator"] == 45
    assert report["variants"]["rules"]["adversarial"]["clean_pass_attack_fail"] == 3
    assert report["variants"]["rules"]["unauthorized_effects"]["rate"] is None
    with pytest.raises(FileExistsError):
        capture(output)
    (output / "observations.json").write_text("[]")
    with pytest.raises(ValueError):
        readback(output, digest)


def test_metric_does_not_hide_unknowns_and_zero_denominator():
    assert metric([True, False, None])["rate"] is None
    assert metric([True, False, None])["known_only_rate"] == 0.5
    assert metric([])["rate"] is None


def test_prospective_criteria_bind_order_pins_and_unknown_effect_blockers():
    plan = development_plan()
    now = datetime(2026, 1, 1, tzinfo=UTC)
    criteria = Criteria(
        plan_sha256=pin(plan),
        frozen_at=now,
        minimum_accuracy=0.95,
        minimum_eligible_coverage=0.95,
        maximum_false_admission=0.0,
        maximum_group_error_upper=0.05,
        maximum_p95_seconds=30.0,
        minimum_groups=1,
        required_slices=("scope", "adversarial"),
        rationale_ref="proposed test only",
    )
    study = Study(
        criteria_sha256=pin(criteria),
        started_at=now + timedelta(seconds=1),
        finished_at=now + timedelta(seconds=2),
        observations=(),
    )
    result = audit(plan, criteria, study, "rules")
    assert not result["diagnostic_criteria_met"] and not result["release_allowed"]
    assert "overall:unauthorized_effects" in result["failed_checks"]
    with pytest.raises(ValueError):
        audit(
            plan,
            criteria,
            study.model_copy(update={"started_at": now - timedelta(seconds=1)}),
            "rules",
        )


def test_discrepancy_flags_without_references_are_unknown_not_excluded():
    plan = development_plan()
    row = observation(plan, plan.cases[0], discrepancy_flag=True)
    measured = scorecard(plan, (row,))["variants"]["rules"]
    assert measured["discrepancy_precision"]["denominator"] == 1
    assert measured["discrepancy_precision"]["unknown"] == 1
    assert measured["flagged_without_billing_reference"] == 1


def test_existing_shared_judge_qualification_is_reused_without_activation():
    from test_evaluator_qualification import NOW, sample

    from revenue_protocol import evaluator_diagnostics

    data, protocol, study = sample()
    with pytest.raises(ValueError):
        evaluator_diagnostics(data, protocol, study, now=NOW)
    data = data.model_copy(update={"agent": "revenue-integrity"})
    protocol = protocol.model_copy(update={"dataset_sha256": pin(data)})
    study = study.model_copy(update={"protocol_sha256": pin(protocol)})
    report = evaluator_diagnostics(data, protocol, study, now=NOW)
    assert report["qualification_diagnostic"]["criteria_met"]
    assert not report["evaluator_activated"] and not report["billing_meaning_certified"]
