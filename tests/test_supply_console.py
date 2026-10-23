"""Offline account scopes, truthful notices and API perimeter witnesses."""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from supply_chain.console_api import create_app, wire
from supply_chain.console_contracts import IncidentScope, Principal, Selection
from supply_chain.notices import make_notice, message
from supply_chain.simulator import NOW
from test_supply_simulator import fact


def actor(role="viewer"):
    return Principal(
        username=role + "-user",
        tenant_id="invented",
        actor_id=role,
        role=role,
        scopes=(IncidentScope(event_id="incident", shipment_ids=("shipment",)),),
    )


@pytest.mark.parametrize(
    "role,cap",
    [("operator", "apply"), ("reviewer", "review"), ("confirmer", "confirm"), ("viewer", "read")],
)
def test_server_scopes_are_incident_specific(role, cap):
    user = actor(role)
    grant = user.grant("incident")
    grant.require("invented", "shipment", cap)
    with pytest.raises(PermissionError):
        user.grant("other")
    with pytest.raises(PermissionError):
        grant.require("other", "shipment", "read")
    with pytest.raises(PermissionError):
        grant.require("invented", "other", "read")


def test_client_selection_cannot_supply_price_or_authority():
    value = dict(event_id="incident", shipment_id="shipment", payload_sha256="a" * 64)
    Selection(**value)
    for extra in ({"cost_minor": 0}, {"tenant_id": "other"}, {"capabilities": ["apply"]}):
        with pytest.raises(ValidationError):
            Selection(**value, **extra)


def test_notice_identity_ignores_poll_time_and_preserves_fact_changes():
    first = make_notice(fact(), "incident", "unassessed", None, None, NOW)
    later = make_notice(fact(), "incident", "unassessed", None, None, NOW + timedelta(seconds=1))
    changed = make_notice(fact(estimated_delay_hours=4), "incident", "unassessed", None, None, NOW)
    assert first.notice_id == later.notice_id != changed.notice_id
    assert "estimated delay 12 hours" in first.body
    assert "No SIM action is proposed" in first.body
    with pytest.raises(ValueError):
        message(fact(), "delivered", None)


def test_wire_keeps_booleans_and_exact_amounts():
    assert wire({"n": 2**63 - 1, "read": False}) == {"n": "9223372036854775807", "read": False}


class Auth:
    def authenticate(self, token, csrf=None):
        if token != "valid" or csrf not in (None, "csrf"):
            raise PermissionError()
        return actor()


class Notices:
    def context(self, user, event):
        user.grant(event)
        return None


class Service:
    notices = Notices()

    def assess(self, user, event):
        raise PermissionError()

    def board(self, user, event):
        user.grant(event)
        return {"event_id": event}


def test_api_session_origin_body_limit_and_packaged_assets():
    import hashlib

    origin = "http://127.0.0.1:8877"
    app = create_app(Service(), Auth(), origin=origin, trial_id="test")
    client = TestClient(app, base_url=origin)
    assert client.get("/api/incidents").status_code == 403
    cookie = "supply_session_" + hashlib.sha256(b"test").hexdigest()[:12]
    client.cookies.set(cookie, "valid")
    assert client.get("/api/incidents").json()["incidents"][0]["event_id"] == "incident"
    assert client.get("/api/workbench/other").status_code == 403
    assert client.post("/api/assess", json={"event_id": "incident"}).status_code == 403
    assert client.post("/api/assess", content="x" * 16385).status_code == 413
    for path in ("/", "/assets/console.css", "/assets/console.js"):
        response = client.get(path)
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert client.get("/assets/missing").status_code == 404
    with pytest.raises(ValueError):
        create_app(Service(), Auth(), origin="https://example.com", trial_id="test")
