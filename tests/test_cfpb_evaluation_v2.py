"""Invented development witnesses, deliberately wrong outputs and complete denominators."""

import json
from datetime import UTC, datetime, timedelta

import pytest
from agent_harness.contracts import ModelMessage, ModelResponse, Usage
from cfpb_triage.classical import TfidfBaseline
from cfpb_triage.economics import WorkSample, economic_report, shadow_stop
from cfpb_triage.evaluation_corpus import development_cases, public_intent_references
from cfpb_triage.evaluation_v2 import Observation, correct, scorecard, validate_groups
from cfpb_triage.measurement import Profiler, timing_report
from cfpb_triage.routing_experiments import OperatingLimits, calibrate, drift
from cfpb_triage.scope_routing import ScopeOutput, ScopePolicy, route_v2
from cfpb_triage.triage_contracts import digest_text
from pydantic import ValidationError
from test_cfpb_classifier import complaint, context, taxonomy


def policy_v2():
    return ScopePolicy(
        taxonomy_sha256=taxonomy().digest(),
        reference_sha256="e" * 64,
        cheap_threshold=0.8,
        strong_threshold=0.8,
        scope_threshold=0.8,
    )


def ctx():
    return context().model_copy(
        update={
            "versions": context().versions.model_copy(
                update={"policy": digest_text(policy_v2().canonical_json())}
            )
        }
    )


def wire(scope="in_scope", priority="routine", confidence=0.9):
    classification = {
        "product": "Credit card",
        "issue": "Billing dispute",
        "priority": priority,
        "ambiguity": "clear",
        "confidence": confidence,
        "quotes": ["credit card"],
    }
    return {
        "scope": scope,
        "confidence": confidence,
        "quotes": ["credit card"],
        "classification": classification if scope == "in_scope" else None,
    }


class Gateway:
    def __init__(self, outputs):
        self.outputs = iter(outputs)
        self.calls = []

    def generate(self, context, request):
        self.calls.append(request)
        output = next(self.outputs)
        if isinstance(output, ModelResponse):
            return output
        return ModelResponse(
            provider=request.provider,
            model=request.model,
            usage=Usage(
                model_calls=1, input_tokens=1, output_tokens=1, cost=None, cost_currency=None
            ),
            output=ModelMessage(role="assistant", content=json.dumps(output)),
        )


def test_scope_routes_and_mixed_input_remain_untrusted_data():
    gateway = Gateway([wire()])
    result = route_v2(gateway, ctx(), complaint(), taxonomy(), policy_v2())
    assert result.action == "classified" and len(gateway.calls) == 1
    assert "untrusted" in gateway.calls[0].messages[0].content
    assert json.loads(gateway.calls[0].messages[1].content) == {"narrative": complaint().narrative}
    assert not gateway.calls[0].tools
    assert {r.stage for r in result.timings} >= {"parse", "evidence_check", "routing"}


@pytest.mark.parametrize(
    "scope,action",
    [
        ("out_of_scope", "scope_response"),
        ("insufficient", "review_required"),
        ("unsupported_request", "review_required"),
        ("taxonomy_gap", "review_required"),
    ],
)
def test_explicit_scope_outcomes(scope, action):
    gateway = Gateway([wire(scope)])
    result = route_v2(gateway, ctx(), complaint(), taxonomy(), policy_v2())
    assert result.scope == scope and result.action == action and len(gateway.calls) == 1


def test_risk_cannot_be_downgraded_and_bad_evidence_does_not_retry():
    gateway = Gateway([wire(priority="elevated"), wire()])
    result = route_v2(gateway, ctx(), complaint(), taxonomy(), policy_v2())
    assert result.action == "review_required" and len(gateway.calls) == 1
    bad = wire()
    bad["quotes"] = ["fabricated"]
    gateway = Gateway([bad, wire()])
    result = route_v2(gateway, ctx(), complaint(), taxonomy(), policy_v2())
    assert result.reason == "operational_failure" and len(gateway.calls) == 1


def test_cheaper_low_confidence_can_escalate_but_bindings_precede_dispatch():
    gateway = Gateway([wire(confidence=0.7), wire()])
    result = route_v2(gateway, ctx(), complaint(), taxonomy(), policy_v2())
    assert len(gateway.calls) == 2 and result.action == "classified"
    with pytest.raises(ValueError, match="binding"):
        route_v2(gateway, context(), complaint(), taxonomy(), policy_v2())
    assert len(gateway.calls) == 2


def test_schema_rejects_account_tools_and_conflicting_scope():
    with pytest.raises(ValidationError):
        ScopeOutput.model_validate({**wire(), "refund": True})
    with pytest.raises(ValidationError):
        ScopeOutput.model_validate({**wire(), "scope": "out_of_scope"})


def test_stage_timings_are_monotonic_payload_free_and_missing_stages_visible():
    ticks = iter((0, 10, 30, 40))
    profiler = Profiler(lambda: next(ticks))
    with profiler.span("routing"):
        with profiler.span("parse"):
            pass
    report = timing_report([profiler.rows, []])
    assert report["inclusive_spans_do_not_sum"]
    assert report["stages"]["parse"]["runs_present"] == 1
    assert report["stages"]["client_visible"]["p95_seconds"] is None
    with pytest.raises(RuntimeError):
        with Profiler().span("parse"):
            raise RuntimeError("invented private payload")


def reference(**updates):
    return development_cases()[6].model_copy(update=updates)


def observation(case=None, **updates):
    case = case or reference()
    row = Observation(
        case_id=case.case_id,
        variant="cheap_only",
        trial=1,
        action="classified",
        scope="in_scope",
        product=case.product,
        issue=case.issue,
        priority="routine",
        ambiguity="clear",
        confidence=0.9,
        evidence_exact=True,
        evidence_relevant=True,
        unauthorized_write=False,
        disclosure=False,
    )
    return row.model_copy(update=updates)


def test_missing_trials_unknown_cost_and_invented_references_never_release():
    case = reference()
    report = scorecard((case,), (observation(),), variants=("cheap_only",), trials=2)
    row = report["reports"]["cheap_only/stress"]
    assert (row["scheduled"], row["missing"], row["cost_unknown"]) == (2, 1, 2)
    assert row["automation_coverage"] == 0.5 and not row["release_eligible"]
    with pytest.raises(ValueError):
        scorecard((case,), (observation(), observation()), variants=("cheap_only",))


def test_actual_security_effects_hard_fail_even_with_correct_classification():
    case = reference(attack_goal="unauthorized_write")
    row = observation(case, unauthorized_write=True)
    report = scorecard((case,), (row,), variants=("cheap_only",))["reports"]["cheap_only/stress"]
    assert report["attack_successes"] == report["critical_failures"] == 1
    assert report["legitimate_task_successes"] == 1
    assert not correct(case, observation(evidence_relevant=None))


def test_scope_false_accept_and_reject_are_separate_and_failures_do_not_disappear():
    case = development_cases()[0]
    row = observation(case, failure="invalid")
    result = scorecard((case,), (row,), variants=("cheap_only",))["reports"]["cheap_only/stress"]
    assert result["scope_false_accepts"] == result["failures"] == 1
    assert result["selective_error"] == 1


@pytest.mark.parametrize("key", ["family", "parent", "text"])
def test_partition_leakage_rejected(key):
    a = reference()
    changes = {
        "case_id": "other",
        "family": "other",
        "parent": "other",
        "text": "Other words",
        "split": "holdout",
        key: getattr(a, key),
    }
    with pytest.raises(ValueError, match="crosses"):
        validate_groups((a, a.model_copy(update=changes)))


def test_calibration_refuses_holdout_and_does_not_force_automation_from_one_family():
    limits = OperatingLimits(
        maximum_group_error_upper=0.05, minimum_automatic_families=10, maximum_review_fraction=0.5
    )
    case = reference(split="calibration")
    report = calibrate((case,), (observation(),), limits)
    assert report["selected"] is None and not report["qualified_for_release"]
    with pytest.raises(ValueError, match="calibration"):
        calibrate((reference(split="holdout"),), (observation(),), limits)
    assert drift((), ("routine",))["total_variation"] is None


def sample(arm, *, basis="human_attested", **changes):
    start = datetime(2026, 11, 10, tzinfo=UTC)
    values = dict(
        case_id=arm,
        family="paired",
        actor=arm,
        arm=arm,
        basis=basis,
        arrived=start,
        accepted=start + timedelta(minutes=10),
        initial_seconds=120.0 if arm == "manual" else 60.0,
        correction_seconds=20.0,
        oversight_seconds=10.0,
        correct=True,
        hourly_labor=18.0,
        recurring_machine_cost=0.1,
        currency="USD",
    )
    return WorkSample.model_validate({**values, **changes})


def test_observed_labor_counts_rework_and_estimates_cannot_claim_savings():
    rows = (sample("manual"), sample("assisted"))
    report = economic_report(rows, scheduled_per_arm=1)
    assert report["observed_active_seconds_saved"] == 60
    assert report["arms"]["assisted"]["correction_seconds"] == 20
    invented = tuple(s.model_copy(update={"basis": "invented"}) for s in rows)
    assert economic_report(invented, scheduled_per_arm=1)["observed_active_seconds_saved"] is None
    assert economic_report(rows[:1], scheduled_per_arm=1)["observed_active_seconds_saved"] is None


def test_blinding_overlap_censored_results_and_unknown_cost_are_not_free():
    rows = (sample("manual"), sample("assisted", accepted=None, recurring_machine_cost=None))
    report = economic_report(rows, scheduled_per_arm=1)
    assert report["observed_recurring_net_saving"] is None
    assert report["arms"]["assisted"]["unfinished_or_missing"] == 1
    with pytest.raises(ValueError, match="both arms"):
        economic_report(
            (sample("manual", actor="same"), sample("assisted", actor="same")), scheduled_per_arm=1
        )
    assert "critical_effect" in shadow_stop(
        critical_effect=True,
        missing_rate=0,
        review_backlog=0,
        p95_seconds=1,
        maximum_missing_rate=0.01,
        maximum_backlog=10,
        maximum_p95_seconds=2,
    )


def test_real_tfidf_baseline_fits_training_only_and_refuses_leakage():
    cases = development_cases()
    model = TfidfBaseline()
    model.fit(cases)
    test = reference(
        case_id="new",
        family="new",
        parent="new",
        text="credit card charged twice",
        split="calibration",
    )
    result = model.predict((test,))
    assert len(result) == 1 and 0 <= result[0]["confidence"] <= 1
    assert result[0]["action"] == "review_required"
    with pytest.raises(ValueError, match="overlaps"):
        model.predict((reference(split="holdout"),))
    with pytest.raises(ValueError, match="training-only"):
        model.fit((test,))


def test_public_reference_adapter_preserves_pin_and_source_split_without_risk_gold(tmp_path):
    path = tmp_path / "source.json"
    raw = json.dumps({"test": [["Invented weather query", "weather"]]})
    path.write_text(raw)
    rows = public_intent_references(
        path,
        expected_sha256=digest_text(raw),
        source="clinc150",
        publisher_split="test",
        mapping={"weather": "out_of_scope"},
        approval_ref="invented-license-review",
    )
    assert rows[0].publisher_split == "test" and rows[0].split == "training"
    assert rows[0].reference_kind == "publisher" and rows[0].priority == "uncertain"
    with pytest.raises(ValueError, match="pin"):
        public_intent_references(
            path,
            expected_sha256="a" * 64,
            source="clinc150",
            publisher_split="test",
            mapping={"weather": "out_of_scope"},
            approval_ref="approved",
        )


def test_calibration_retains_an_entire_missing_trial_and_rollback_is_stricter():
    from cfpb_triage.routing_experiments import review_only

    case = reference(split="calibration")
    limits = OperatingLimits(
        maximum_group_error_upper=0.99, minimum_automatic_families=1, maximum_review_fraction=1.0
    )
    report = calibrate((case,), (observation(),), limits, trials=2)
    assert not report["complete"] and report["selected"] is None
    original = policy_v2()
    rolled = review_only(original)
    assert rolled.cheap_threshold == rolled.strong_threshold == rolled.scope_threshold == 1.01
    assert original.cheap_threshold == 0.8 and rolled.canonical_json() != original.canonical_json()


def test_batch_latency_uses_wall_window_and_preserves_partial_timestamps():
    start = datetime(2026, 11, 10, tzinfo=UTC)
    case = reference()
    row = observation(started_at=start, finished_at=start + timedelta(seconds=4))
    result = scorecard((case,), (row,), variants=("cheap_only",))["reports"]["cheap_only/stress"]
    assert result["batch_observed_window_seconds"] == 4
    assert result["batch_throughput_per_second"] == 0.25
    result = scorecard((case,), (row,), variants=("cheap_only",), trials=2)["reports"][
        "cheap_only/stress"
    ]
    assert result["batch_throughput_per_second"] is None


def test_conflicting_escalation_scope_and_unpinned_mode_cannot_auto_reject():
    gateway = Gateway([wire(confidence=0.7), wire("out_of_scope")])
    result = route_v2(gateway, ctx(), complaint(), taxonomy(), policy_v2())
    assert result.action == "review_required" and result.reason == "scope_uncertain"
    with pytest.raises(ValueError, match="mode"):
        route_v2(Gateway([]), ctx(), complaint(), taxonomy(), policy_v2(), mode="strong_only")


def test_cascade_calibration_keeps_stage_costs_and_never_downgrades_risk():
    from cfpb_triage.routing_experiments import calibrate_cascade

    case = reference(split="calibration")
    cheap = observation(confidence=0.7, scope_confidence=0.9, cost=0.01, currency="USD")
    strong = observation(variant="strong_only", scope_confidence=0.9, cost=0.02, currency="USD")
    limits = OperatingLimits(
        maximum_group_error_upper=0.99, minimum_automatic_families=1, maximum_review_fraction=1.0
    )
    report = calibrate_cascade((case,), (cheap, strong), limits, scope_threshold=0.8)
    point = next(
        p for p in report["curve"] if p["cheap_threshold"] == 0.8 and p["strong_threshold"] == 0.8
    )
    assert point["selected_stage_requests"] == 2 and point["coverage"] == 1
    assert point["counterfactual_cost_sum"] == pytest.approx(0.03)
    risk = cheap.model_copy(update={"priority": "elevated"})
    report = calibrate_cascade((case,), (risk, strong), limits, scope_threshold=0.8)
    assert all(p["selected_stage_requests"] == 1 and p["coverage"] == 0 for p in report["curve"])
    incomplete = calibrate_cascade((case,), (cheap,), limits, scope_threshold=0.8)
    assert not incomplete["complete"] and incomplete["selected"] is None


def test_critical_effect_blocks_thresholds_even_when_that_row_is_reviewed():
    case = reference(split="calibration")
    row = observation(scope_confidence=0.9, action="review_required", unauthorized_write=True)
    limits = OperatingLimits(
        maximum_group_error_upper=0.99, minimum_automatic_families=1, maximum_review_fraction=1.0
    )
    report = calibrate((case,), (row,), limits)
    assert report["selected"] is None and all(p["critical"] for p in report["curve"])


def test_provider_model_identity_and_null_scope_category_are_not_valid_classifications():
    response = Gateway([wire()]).generate(
        ctx(), type("Request", (), {"provider": "wrong-provider", "model": "wrong-model"})()
    )
    gateway = Gateway([response])
    decision = route_v2(gateway, ctx(), complaint(), taxonomy(), policy_v2())
    assert decision.reason == "operational_failure" and len(gateway.calls) == 1
    bad = wire()
    bad["classification"]["product"] = None
    bad["classification"]["issue"] = None
    gateway = Gateway([bad])
    assert (
        route_v2(gateway, ctx(), complaint(), taxonomy(), policy_v2()).action == "review_required"
    )
    item = complaint().model_copy(update={"narrative": "aaa"})
    bound = ctx().model_copy(
        update={"versions": ctx().versions.model_copy(update={"data_snapshot": digest_text("aaa")})}
    )
    output = wire("out_of_scope")
    output["quotes"] = ["aa"]
    result = route_v2(Gateway([output]), bound, item, taxonomy(), policy_v2())
    assert result.action == "review_required" and result.reason == "operational_failure"


def test_post_commit_timing_failure_does_not_mask_successful_http_action():
    from cfpb_triage.desk_api import create_app
    from fastapi.testclient import TestClient
    from test_cfpb_desk import actor

    class Auth:
        def login(self, username, password):
            return "token", "csrf", actor()

        def authenticate(self, token, csrf=None):
            if token != "token":
                raise PermissionError()
            return actor()

    class Store:
        pass

    class Evaluation:
        def evaluation_snapshot(self, user, case):
            return {"case_id": case, "version": 1, "arm": "manual"}

        def record_profile(self, *args):
            raise PermissionError("invented telemetry failure")

    client = TestClient(
        create_app(
            Store(),
            Auth(),
            origin="http://127.0.0.1:8883",
            trial_id="invented",
            evaluation=Evaluation(),
        ),
        base_url="http://127.0.0.1:8883",
    )
    client.post(
        "/api/login",
        json={"username": "reviewer-test", "password": "invented-password"},
        headers={"origin": "http://127.0.0.1:8883"},
    )
    response = client.get("/api/v2/evaluation/" + complaint().case_id)
    assert response.status_code == 200 and response.headers["X-CFPB-Timing"] == "not-recorded"
