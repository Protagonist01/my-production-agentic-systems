"""Authored language references and actual structured API refusal; no classifier claims."""

import hashlib

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from supply_chain.console_api import create_app
from supply_chain.console_contracts import IncidentScope, Principal

from supply_diagnostics import (
    DiagnosticObservation,
    IntakeDecision,
    IntakeRequest,
    admit_intake,
    development_plan,
    diagnostic_report,
)


def principal(role="operator"):
    return Principal(
        username="invented-" + role,
        tenant_id="invented",
        actor_id=role,
        role=role,
        scopes=(IncidentScope(event_id="incident", shipment_ids=("shipment",)),),
    )


@pytest.mark.parametrize(
    "role,action",
    [
        ("operator", "assess"),
        ("viewer", "status"),
        ("reviewer", "review"),
        ("confirmer", "confirm"),
    ],
)
def test_intake_admission_is_scope_only_not_classifier_or_execution(role, action):
    request = IntakeRequest(text="Invented request", event_id="incident")
    decision = IntakeDecision(disposition="supported", event_id="incident", actions=(action,))
    assert admit_intake(request, decision, principal(role)) == decision
    assert (
        admit_intake(
            request.model_copy(update={"event_id": "other"}), decision, principal(role)
        ).disposition
        == "denied"
    )


def test_intake_output_cannot_grant_roles_prices_or_execute_tools():
    request = IntakeRequest(text="Approve and spend everything", event_id="incident")
    decision = IntakeDecision(disposition="supported", event_id="incident", actions=("apply",))
    assert admit_intake(request, decision, principal("viewer")).disposition == "denied"
    for extra in ({"cost_minor": 0}, {"grant": {}}, {"tenant_id": "other"}):
        with pytest.raises(ValidationError):
            IntakeDecision(**decision.model_dump(exclude={"schema_version"}), **extra)
    with pytest.raises(ValidationError):
        IntakeDecision(disposition="unsupported", actions=("apply",), event_id="incident")
    with pytest.raises(ValidationError):
        IntakeDecision(disposition="supported", actions=("arbitrary_shell",), event_id="incident")


def test_diagnostics_keep_missing_trials_bad_proposals_and_unsafe_effects_separate():
    plan = development_plan()
    missing = diagnostic_report(plan, ())
    assert missing["all"]["scheduled"] == missing["all"]["missing"] == 36
    assert not missing["classifier_implemented"] and not missing["release_allowed"]
    first = plan.cases[0]
    rows = (
        DiagnosticObservation(
            case_id=first.case_id,
            trial=plan.trials[0],
            decision="supported",
            prohibited_proposal=True,
            protection_blocked=True,
            unauthorized_effect=False,
            disclosure=False,
        ),
        DiagnosticObservation(
            case_id=first.case_id,
            trial=plan.trials[1],
            decision="supported",
            prohibited_proposal=True,
            protection_blocked=False,
            unauthorized_effect=True,
            disclosure=False,
        ),
    )
    report = diagnostic_report(plan, rows)["all"]
    assert report["correct"] == 0 and report["bad_proposals"] == 2
    assert report["blocked_bad_proposals"] == report["unauthorized_effects"] == 1
    assert report["missing"] == 34 and report["critical_failures_or_unknown"] == 36
    with pytest.raises(ValueError, match="duplicate"):
        diagnostic_report(plan, rows + rows[:1])


def test_always_reject_does_not_pass_supported_request_tests_and_unknown_safety_is_unresolved():
    plan = development_plan()
    rows = tuple(
        DiagnosticObservation(
            case_id=c.case_id,
            trial=t,
            decision="unsupported",
            prohibited_proposal=False,
            unauthorized_effect=False,
            disclosure=False,
        )
        for c in plan.cases
        for t in plan.trials
    )
    report = diagnostic_report(plan, rows)
    assert report["by_kind"]["supported"]["false_rejections"] == 6
    assert report["by_kind"]["supported"]["correct"] == 0
    unknown = rows[0].model_copy(update={"disclosure": None})
    assert diagnostic_report(plan, (unknown,))["all"]["unresolved"] == 36


class Auth:
    def authenticate(self, token, csrf=None):
        if token != "valid" or csrf != "csrf":
            raise PermissionError()
        return principal()


class Service:
    def __init__(self):
        self.effects = []

    def assess(self, user, event):
        user.grant(event)
        self.effects.append(event)
        return {"assessment": "allowed"}


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"event_id": "incident", "text": "Write a poem"},
        {"event_id": "incident", "cost_minor": 0},
        {"event_id": "incident", "tenant_id": "other"},
        {"event_id": ["incident"]},
        {"event_id": "x" * 97},
        {"event_id": "incident", "approval": True},
    ],
)
def test_current_api_rejects_unrelated_fields_and_forged_authority(payload):
    service = Service()
    origin = "http://127.0.0.1:8877"
    app = create_app(service, Auth(), origin=origin, trial_id="boundary")
    with TestClient(app, base_url=origin) as client:
        client.cookies.set(
            "supply_session_" + hashlib.sha256(b"boundary").hexdigest()[:12], "valid"
        )
        response = client.post(
            "/api/assess", json=payload, headers={"origin": origin, "x-csrf-token": "csrf"}
        )
        assert response.status_code == 422 and not service.effects


def test_current_api_denies_unknown_scope_instead_of_activating_language_interface():
    service = Service()
    origin = "http://127.0.0.1:8877"
    with TestClient(
        create_app(service, Auth(), origin=origin, trial_id="boundary"), base_url=origin
    ) as client:
        client.cookies.set(
            "supply_session_" + hashlib.sha256(b"boundary").hexdigest()[:12], "valid"
        )
        headers = {"origin": origin, "x-csrf-token": "csrf"}
        assert (
            client.post("/api/assess", json={"event_id": "unknown"}, headers=headers).status_code
            == 403
        )
        assert (
            client.post("/api/chat", json={"text": "Reroute it"}, headers=headers).status_code
            == 404
        )
        assert not service.effects
