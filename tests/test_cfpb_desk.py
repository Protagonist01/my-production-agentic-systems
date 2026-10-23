"""Invented protected-API, closed tool, diagnostic and privacy witnesses."""

from datetime import UTC, datetime

import pytest
from cfpb_triage.desk_api import create_app
from cfpb_triage.desk_contracts import Principal, QueueCommand
from cfpb_triage.desk_worker import failed
from cfpb_triage.diagnostics import compare, profile
from cfpb_triage.triage_contracts import Decision
from fastapi.testclient import TestClient
from pydantic import ValidationError
from test_cfpb_classifier import complaint, policy, taxonomy

NOW = datetime(2026, 10, 23, 12, tzinfo=UTC)


def actor(case=None, role="reviewer", tenant="demo"):
    return Principal(
        username=role + "-test",
        tenant_id=tenant,
        actor_id=role,
        role=role,
        case_ids=(case or complaint().case_id,),
    )


def record():
    return {
        "tenant_id": "demo",
        "case_id": complaint().case_id,
        "version": 1,
        "complaint": complaint().model_dump(mode="json"),
        "taxonomy": taxonomy().model_dump(mode="json"),
        "policy": policy().model_dump(mode="json"),
        "result": None,
        "status": "queued",
        "review_ref": "invented-reviewed",
        "provenance": "invented",
        "events": [],
        "job": None,
        "can_review": True,
    }


def test_scopes_and_closed_commands_have_no_resolution_capability():
    with pytest.raises(PermissionError):
        actor(role="viewer").require(complaint().case_id, write=True)
    with pytest.raises(PermissionError):
        actor().require("other")
    with pytest.raises(ValidationError):
        QueueCommand.model_validate({"command_id": "x", "expected_version": 1, "reason": "refund"})
    with pytest.raises(ValidationError):
        QueueCommand.model_validate(
            {
                "command_id": "x",
                "expected_version": 1,
                "reason": "expert_review",
                "narrative": "private",
            }
        )


def test_actual_api_authentication_origin_csrf_payload_and_no_raw_ingress():
    class Auth:
        def login(self, username, password):
            return "token", "csrf", actor()

        def authenticate(self, token, csrf=None):
            if token != "token" or csrf not in (None, "csrf"):
                raise PermissionError()
            return actor()

        def logout(self, token):
            pass

    class Store:
        def snapshot(self, user, case):
            user.require(case)
            return record()

        def enqueue(self, user, case, command):
            user.require(case, write=True)
            return 2

    client = TestClient(
        create_app(Store(), Auth(), origin="http://127.0.0.1:8883", trial_id="invented"),
        base_url="http://127.0.0.1:8883",
    )
    assert client.get("/api/cases").status_code == 403
    assert (
        client.post(
            "/api/login",
            headers={"Origin": "http://evil.invalid"},
            json={"username": "reviewer", "password": "invented-password"},
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/login",
            headers={"Origin": "http://127.0.0.1:8883"},
            json={"username": "reviewer", "password": "invented-password"},
        ).status_code
        == 200
    )
    path = "/api/cases/" + complaint().case_id + "/review"
    payload = {"command_id": "review", "expected_version": 1, "reason": "expert_review"}
    assert (
        client.post(path, headers={"Origin": "http://127.0.0.1:8883"}, json=payload).status_code
        == 403
    )
    headers = {"Origin": "http://127.0.0.1:8883", "X-CSRF-Token": "csrf"}
    assert client.post(path, headers=headers, json=payload).json() == {"version": 2}
    assert (
        client.post(path, headers=headers, json={**payload, "outcome": "resolved"}).status_code
        == 422
    )
    assert client.post(path, headers=headers, content="x" * 20000).status_code == 413
    assert client.get("/api/cases/other").status_code == 403
    assert (
        client.post("/api/enroll", headers=headers, json={"narrative": "private"}).status_code
        == 404
    )
    assert client.get("/api/cases", headers={"Host": "127.0.0.1:9999"}).status_code == 403
    assert client.get("/api/diagnostics").json()["cases"] == 1
    response = client.get("/")
    assert "default-src 'self'" in response.headers["content-security-policy"]
    assert response.headers["cache-control"] == "no-store"


def test_diagnostic_shifts_are_scoped_aggregates_with_unknown_language_and_no_accuracy_claim():
    original = profile([record()])
    changed = record()
    changed["complaint"] = {"narrative": "mi cuenta en el banco que la cuenta " + ("XXXX " * 700)}
    changed["result"] = {
        "prediction": {"product": "Other"},
        "attempts": [{"model": "invented-new-model"}],
    }
    result = compare(original, profile([changed]))
    for dimension in ["categories", "lengths", "languages", "masking", "models", "providers"]:
        assert (
            result["dimensions"][dimension]["alert"]
            or result["dimensions"][dimension]["insufficient_data"]
        )
    assert not result["accuracy_claim"]
    assert complaint().narrative not in str(result) and "narrative" not in original.model_dump()
    assert compare(profile([]), original)["dimensions"]["categories"]["insufficient_data"]


def test_worker_failed_result_contains_no_unverified_prediction():
    result = failed(record())
    assert isinstance(result, Decision) and result.outcome == "review_required"
    assert result.prediction is None and result.attempts == ()


def test_trace_hierarchy_masks_narrative_and_preserves_unknown_accounting():
    from agent_harness.telemetry import TraceSession
    from cfpb_triage.tracing import traced_route
    from test_cfpb_classifier import Gateway, context, prediction

    class Exporter:
        def __init__(self):
            self.spans = ()

        def export(self, spans):
            self.spans = spans
            return True

        def flush(self):
            return True

        def shutdown(self):
            pass

    out = Exporter()
    trace = TraceSession(out, b"c" * 32)
    result = traced_route(
        trace,
        Gateway(prediction().canonical_json()),
        context(),
        complaint(),
        taxonomy(),
        policy(),
        provenance="invented",
    )
    assert result.outcome == "classified" and trace.health.healthy
    kinds = {s.kind: s for s in out.spans}
    assert set(kinds) == {"run", "agent", "node", "model"}
    assert kinds["agent"].parent_id == kinds["run"].span_id
    assert kinds["model"].parent_id == kinds["node"].span_id
    assert kinds["run"].attributes["source_kind"] == "synthetic"
    assert kinds["run"].attributes["source_count"] == 0
    assert complaint().narrative not in str(out.spans)
    assert complaint().narrative not in str([s.attributes for s in out.spans])
