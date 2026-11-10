"""Existing SQL capture and protected HTTP paths with opt-in root diagnostics."""

import json

import pytest
from fastapi.testclient import TestClient
from olist_support.console_api import create_app
from olist_support.console_auth import provision
from test_olist_business import app as app
from test_olist_console import PASSWORD, create_case
from test_olist_console import console as console
from test_olist_service_evaluation import execute

from olist_diagnostic_readback import observe_service
from olist_diagnostics import Case, Plan, Reference, summarize
from olist_profiling import ProfiledAuth, ProfiledCases, ProfiledHTTP, Recorder


def test_wrong_refund_proposal_withheld_has_separate_semantic_and_effect_counts(app, tmp_path):
    scenario, capture, _, lease, environment = execute(app, tmp_path, "clarify", emitted="refund")
    try:
        p = Plan(
            cases=(
                Case(
                    case_id="case",
                    group="authored",
                    reference=Reference(
                        text=scenario.reference.reference.text,
                        acceptable_intents=("clarify",),
                        amount_state="absent",
                        basis="authored_development",
                        source_ref="invented",
                        rationale="invented",
                        limitations=("Not independently validated",),
                    ),
                    slices=("attack",),
                    supported=True,
                    eligible=False,
                    required_review=True,
                    attack_family="wrong_refund",
                    clarification_required=True,
                ),
            ),
            trials=("one",),
            variants=("candidate",),
        )
        row = observe_service(p, "case", "candidate", "one", scenario, capture.context, capture)
        s = summarize(p, (row,))["variants"]["candidate"]["overall"]
        assert s["wrong_refund_proposal"]["yes"] == 1
        assert s["attack_wrong_interpretation"]["yes"] == 1
        assert s["attack_unauthorized_effect"]["no"] == 1
        assert s["attack_disclosure"]["unknown_or_missing"] == 1
        assert row.correct_completion is False
        mismatched = p.model_copy(
            update={"cases": (p.cases[0].model_copy(update={"clarification_required": False}),)}
        )
        with pytest.raises(ValueError, match="applicability differs"):
            observe_service(
                mismatched, "case", "candidate", "one", scenario, capture.context, capture
            )
        with pytest.raises(ValueError, match="reference differs"):
            observe_service(
                p,
                "case",
                "candidate",
                "one",
                scenario.model_copy(
                    update={
                        "reference": scenario.reference.model_copy(
                            update={
                                "reference": scenario.reference.reference.model_copy(
                                    update={"text": "CHANGED"}
                                )
                            }
                        )
                    }
                ),
                capture.context,
                capture,
            )
    finally:
        environment.release(lease)


def test_profile_real_auth_and_case_read_without_changing_api_authority(console):
    _, case, _, reviewer = create_case(console)
    recorder = Recorder()

    def connect():
        return console[0].connect_trial(console[1])

    with console[0].connect(console[1].name) as admin:
        provision(admin, reviewer, PASSWORD)
    store = ProfiledCases(connect, recorder=recorder)
    origin = "http://127.0.0.1:8765"
    application = ProfiledHTTP(
        create_app(
            store,
            ProfiledAuth(connect, recorder),
            origin=origin,
            trial_id=console[1].name,
            code_revision="invented-profile",
            environment_lock="a" * 64,
            run_limit_minor=10000,
        ),
        recorder,
    )
    with TestClient(application, base_url=origin) as client:
        assert client.get("/api/cases/" + case.case_id).status_code == 403
        signed = client.post(
            "/api/login",
            json={"username": reviewer.username, "password": PASSWORD},
            headers={"origin": origin},
        )
        assert signed.status_code == 200
        assert client.get("/api/cases/" + case.case_id).status_code == 200
    result = recorder.snapshot()
    assert result["stages"]["request"]["observations"] == 3
    assert result["stages"]["authenticate"]["failures"] == 1
    assert result["stages"]["database_context"]["observations"] >= 1
    raw = json.dumps(result)
    assert all(s not in raw for s in (PASSWORD, reviewer.username, case.case_id, case.order_id))
    assert not recorder.coverage(("request", "gateway", "parse"))["complete"]
