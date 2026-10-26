"""Invented missing/failure/risk rows, hidden-world sensitivity and catalog privacy."""

import json
from dataclasses import replace
from datetime import date

import pytest
from agent_harness.release_catalog import ReportPin, report_catalog
from agent_harness.release_contracts import sha256
from prior_auth.assessment import CRITERIA
from prior_auth.contracts import AssessmentResult, CheckedClaim, NoteInput, digest
from prior_auth.evaluation import EvaluationCase, ExpectedCriterion
from prior_auth.release_evaluation import AssessmentObservation, AssessmentPlan, assessment_report
from supply_chain.release_evaluation import (
    ActionObservation,
    SimulationPlan,
    simulation_report,
    world_pin,
)
from supply_chain.simulator import HiddenOutcome, do_nothing, make_scenario


def prior_case():
    text = "Invented missing documentation."
    note = NoteInput(
        case_id="one",
        tenant_id="invented",
        note_sha256=digest(text),
        text=text,
        service_date=date(2026, 10, 26),
        policy_id="cms-ncd-240-4-v3",
        policy_sha256="a" * 64,
        use="initial",
        provenance="invented",
    )
    return EvaluationCase(
        input=note,
        group_id="one-family",
        split="holdout",
        source_ref="invented-only",
        expected=tuple(
            ExpectedCriterion(
                criterion_id=k,
                state="insufficient",
                support_quotes=(),
                rationale="Independent invented missing-fact witness",
            )
            for k in CRITERIA
        ),
        expected_disposition="request_information",
        label_rationale="Provisional test labels",
    )


def prior_result(case, disposition="request_information"):
    return AssessmentResult(
        case_id=case.input.case_id,
        note_sha256=case.input.note_sha256,
        policy_sha256=case.input.policy_sha256,
        claims=tuple(
            CheckedClaim(criterion_id=k, state="insufficient", evidence=(), reason="Missing")
            for k in CRITERIA
        ),
        disposition=disposition,
        retrieval_failure=False,
        assessment_failure=False,
    )


def test_prior_auth_missing_trials_remain_in_both_risk_and_criterion_denominators():
    case = prior_case()
    plan = AssessmentPlan(
        candidate_sha256="b" * 64,
        source_manifest_sha256="c" * 64,
        cases=(case,),
        trial_ids=("one", "two", "three"),
        origin="mock",
    )
    observations = (
        AssessmentObservation(case_id="one", trial_id="one", result=prior_result(case)),
        AssessmentObservation(
            case_id="one",
            trial_id="two",
            result=prior_result(case, "evidence_complete_for_review"),
            failure_code="timeout",
        ),
    )
    report = assessment_report(plan, observations)
    total = report["all"]
    assert total["scheduled"] == total["non_approvable"] == 3
    assert total["correct"] == total["missing"] == total["failed"] == 1
    assert total["unresolved"] == 2 and total["all_trials_correct"] == 0
    assert total["incorrect_per_recommendation"] == 1 and total[
        "incorrect_per_non_approvable"
    ] == pytest.approx(1 / 3)
    assert all(c["scheduled"] == 3 for c in total["criterion"].values())
    assert not report["release_allowed"] and not report["clinical_validation"]
    assert assessment_report(plan, ())["all"]["incorrect_per_recommendation"] is None
    with pytest.raises(ValueError, match="duplicate"):
        assessment_report(plan, (*observations, observations[0]))
    changed = observations[0].model_copy(
        update={"result": prior_result(case).model_copy(update={"policy_sha256": "d" * 64})}
    )
    with pytest.raises(ValueError, match="different input"):
        assessment_report(plan, (changed,))


def supply_inputs():
    worlds = (
        make_scenario("development", "routine", 4),
        make_scenario("holdout", "scarce_capacity", 9),
    )
    plan = SimulationPlan(
        candidate_sha256="a" * 64,
        worlds_sha256=world_pin(worlds),
        scenario_ids=tuple(w.scenario_id for w in worlds),
        trial_ids=("one", "two", "three"),
        origin="mock",
    )
    return worlds, plan


def test_supply_missing_partial_unsafe_and_failed_trials_do_not_disappear_from_cost_report():
    worlds, plan = supply_inputs()
    first, second = worlds
    observations = (
        ActionObservation(
            scenario_id=first.scenario_id, trial_id="one", actions=do_nothing(first.agent_input())
        ),
        ActionObservation(scenario_id=first.scenario_id, trial_id="two", actions={}),
        ActionObservation(
            scenario_id=second.scenario_id,
            trial_id="one",
            actions={s.shipment_id: "reroute" for s in second.observed},
        ),
        ActionObservation(scenario_id=second.scenario_id, trial_id="two", failure_code="timeout"),
    )
    report = simulation_report(plan, worlds, observations)
    for sensitivity in report["sensitivities"].values():
        total = sensitivity["all"]
        assert total["scheduled"] == 6 and total["missing"] == 3 and total["observed"] == 3
        assert total["completed"] == 1 and total["unresolved_trials"] == 5 and total["failed"] == 1
        assert total["unsafe_events"] > 0 and total["all_trials_completed"] == 0
        assert all(c["paired_observed"] == 3 for c in total["comparisons"].values())
    assert not report["release_allowed"] and not report["business_state_verified"]
    assert report["unit"] == "SIM"
    with pytest.raises(ValueError, match="duplicate"):
        simulation_report(plan, worlds, (*observations, observations[0]))
    changed = (
        replace(
            first, hidden=tuple(HiddenOutcome(t.shipment_id, (99, 99, 99)) for t in first.hidden)
        ),
        second,
    )
    with pytest.raises(ValueError, match="frozen world"):
        simulation_report(plan, changed, observations)
    altered = simulation_report(
        plan.model_copy(update={"worlds_sha256": world_pin(changed)}), changed, observations
    )
    assert (
        altered["sensitivities"]["50"]["all"]["comparisons"]
        != report["sensitivities"]["50"]["all"]["comparisons"]
    )


def test_catalog_pins_reports_and_never_exports_arbitrary_source_text_or_merged_accuracy(tmp_path):
    case = prior_case()
    plan = AssessmentPlan(
        candidate_sha256="b" * 64,
        source_manifest_sha256="c" * 64,
        cases=(case,),
        trial_ids=("one",),
        origin="mock",
    )
    report = assessment_report(plan, ())
    report["private_untrusted_text"] = "PRIVATE CANARY DO NOT PUBLISH"
    raw = json.dumps(report).encode()
    path = tmp_path / "private-report.json"
    path.write_bytes(raw)
    reference = ReportPin(scope="prior-auth", relative_path=path.name, sha256=sha256(raw))
    catalog = report_catalog(tmp_path, (reference,))
    assert "PRIVATE CANARY" not in json.dumps(catalog) and path.name not in json.dumps(catalog)
    assert catalog["blended_accuracy"] is None and not catalog["reports_complete"]
    assert catalog["entries"][0]["counts"]["missing"] == 1
    for name in ("../escape", "C:/escape", "a\\escape"):
        with pytest.raises(ValueError, match="private inventory"):
            report_catalog(tmp_path, (reference.model_copy(update={"relative_path": name}),))
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="external byte pin"):
        report_catalog(tmp_path, (reference,))


def test_prior_auth_all_trials_and_citation_failure_are_separate_from_missing_outputs():
    case = prior_case()
    plan = AssessmentPlan(
        candidate_sha256="b" * 64,
        source_manifest_sha256="c" * 64,
        cases=(case,),
        trial_ids=("one", "two", "three"),
        origin="deterministic",
    )
    observations = tuple(
        AssessmentObservation(case_id=case.input.case_id, trial_id=t, result=prior_result(case))
        for t in plan.trial_ids
    )
    total = assessment_report(plan, observations)["all"]
    assert total["all_trials_correct"] == 1 and total["completed"] == total["correct"] == 3
    from prior_auth.contracts import Span

    result = prior_result(case)
    wrong = result.claims[0].model_copy(
        update={"state": "met", "evidence": (Span(start=0, end=4, quote="Fake"),)}
    )
    changed = observations[0].model_copy(
        update={"result": result.model_copy(update={"claims": (wrong, *result.claims[1:])})}
    )
    total = assessment_report(plan, (changed, *observations[1:]))["all"]
    assert total["invalid"] == 1 and total["missing"] == 0 and total["unresolved"] == 1
    assert total["criterion"][wrong.criterion_id]["unsupported_met"] == 1


def test_supply_complete_wait_observations_pair_every_trial_and_sensitivity():
    worlds, plan = supply_inputs()
    observations = tuple(
        ActionObservation(
            scenario_id=w.scenario_id, trial_id=t, actions=do_nothing(w.agent_input())
        )
        for w in worlds
        for t in plan.trial_ids
    )
    report = simulation_report(plan, worlds, observations)
    for sensitivity in report["sensitivities"].values():
        total = sensitivity["all"]
        assert total["completed"] == total["scheduled"] == 6
        assert (
            total["all_trials_completed"] == 2 and total["unsafe_events"] == total["missing"] == 0
        )
        assert total["comparisons"]["do_nothing"]["difference_minor"] == 0
    assert (
        report["sensitivities"]["50"]["all"]["comparisons"]["do_nothing"]["candidate_total_minor"]
        < report["sensitivities"]["200"]["all"]["comparisons"]["do_nothing"][
            "candidate_total_minor"
        ]
    )


def test_explicit_wait_on_stale_or_conflicting_facts_does_not_claim_completion():
    worlds = (
        make_scenario("holdout", "expired_alerts", 8),
        make_scenario("holdout", "conflicting_alerts", 8),
    )
    plan = SimulationPlan(
        candidate_sha256="a" * 64,
        worlds_sha256=world_pin(worlds),
        scenario_ids=tuple(w.scenario_id for w in worlds),
        trial_ids=("one",),
        origin="mock",
    )
    observations = tuple(
        ActionObservation(
            scenario_id=w.scenario_id, trial_id="one", actions=do_nothing(w.agent_input())
        )
        for w in worlds
    )
    total = simulation_report(plan, worlds, observations)["sensitivities"]["100"]["all"]
    assert total["completed"] == 0 and total["unresolved_trials"] == 2 and total["missing"] == 0
    assert total["unresolved_shipments"] == total["scheduled_shipments"]


@pytest.mark.parametrize("change", ["scope", "version", "authorization", "count", "duplicate"])
def test_catalog_cannot_promote_wrong_version_authorization_or_invalid_counts(tmp_path, change):
    payload = {
        "version": "prior-auth-release-report-v1",
        "release_allowed": False,
        "all": {"scheduled": 1},
    }
    if change == "version":
        payload["version"] = "unknown"
    elif change == "authorization":
        payload["release_allowed"] = True
    elif change == "count":
        payload["all"]["scheduled"] = True
    raw = json.dumps(payload).encode()
    (tmp_path / "report.json").write_bytes(raw)
    ref = ReportPin(
        scope="cfpb" if change == "scope" else "prior-auth",
        relative_path="report.json",
        sha256=sha256(raw),
    )
    with pytest.raises(ValueError):
        report_catalog(tmp_path, (ref, ref) if change == "duplicate" else (ref,))


def test_catalog_cli_seals_new_output_and_refuses_overwrite_or_changed_inventory(
    tmp_path, monkeypatch, capsys
):
    from agent_harness.release_catalog import ReportInventory, main

    report = {
        "version": "prior-auth-release-report-v1",
        "release_allowed": False,
        "all": {"scheduled": 3, "missing": 3},
    }
    raw = json.dumps(report).encode()
    (tmp_path / "report.json").write_bytes(raw)
    inventory = ReportInventory(
        references=(ReportPin(scope="prior-auth", relative_path="report.json", sha256=sha256(raw)),)
    )
    source = tmp_path / "inventory.json"
    source.write_text(inventory.canonical_json(), encoding="utf-8")
    output = tmp_path / "catalog.json"
    argv = [
        "catalog",
        "--root",
        str(tmp_path),
        "--inventory",
        str(source),
        "--inventory-sha256",
        sha256(source.read_bytes()),
        "--output",
        str(output),
    ]
    monkeypatch.setattr("sys.argv", argv)
    assert main() == 0
    assert json.loads(capsys.readouterr().out)["catalog_sha256"] == sha256(output.read_bytes())
    original = output.read_bytes()
    assert main() == 2 and output.read_bytes() == original
    source.write_text("{}", encoding="utf-8")
    assert main() == 2 and output.read_bytes() == original
