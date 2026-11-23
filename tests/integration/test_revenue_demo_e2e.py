"""Actual SQL + authenticated HTTP: source -> proposal -> review -> receipt -> restart."""

import hashlib

from fastapi.testclient import TestClient
from revenue_integrity.console_auth import AuthStore, provision, setup_console
from revenue_integrity.operations import OperationStore, enroll
from test_revenue_operations import app as app

from revenue_demo import DemoService, cases, principal, provisioned_records
from revenue_demo_web import application
from revenue_profiling import Recorder

ORIGIN = "http://127.0.0.1:8878"
PASSWORD = "Invented walkthrough password 2026"


def signed(app, role, trial):
    client = TestClient(app, base_url=ORIGIN)
    assert (
        client.post(
            "/api/login",
            json={"username": "demo-" + role, "password": PASSWORD},
            headers={"origin": ORIGIN},
        ).status_code
        == 200
    )
    suffix = hashlib.sha256(trial.name.encode()).hexdigest()[:12]
    headers = {"origin": ORIGIN, "x-csrf-token": client.cookies.get("revenue_csrf_" + suffix)}
    return client, headers


def test_entire_constructed_walkthrough_rejects_bypasses_and_survives_reconstruction(app):
    server, trial, _ = app
    with server.connect(trial.name) as admin:
        setup_console(admin, trial.name)
        for record in provisioned_records():
            enroll(admin, record)
        for role in ("operator", "reviewer"):
            provision(admin, principal(role), PASSWORD)

    def connect():
        return server.connect_trial(trial)

    def build():
        return application(
            DemoService(OperationStore(connect), Recorder()),
            AuthStore(connect),
            origin=ORIGIN,
            trial_id=trial.name,
        )

    web = build()
    anonymous = TestClient(web, base_url=ORIGIN)
    assert anonymous.get("/walkthrough").status_code == 200
    assert anonymous.get("/walkthrough-api/cases").status_code == 403
    op, oh = signed(web, "operator", trial)
    rv, rh = signed(web, "reviewer", trial)
    c = cases()[0]
    analyze = {"case_id": c.case_id, "document": c.document.text, "question": "Check this invoice."}
    assert op.post("/walkthrough-api/analyze", json=analyze).status_code == 403
    result = op.post("/walkthrough-api/analyze", json=analyze, headers=oh)
    assert result.status_code == 200
    finding = result.json()
    assert finding["delta_minor"] == "500" and finding["action"] == "proposable"
    for candidate in cases()[3:]:
        bad = op.post(
            "/walkthrough-api/analyze",
            json={
                "case_id": candidate.case_id,
                "document": candidate.document.text,
                "question": "Check this invoice.",
            },
            headers=oh,
        ).json()
        assert bad["action"] in ("review", "request_information")
    changed = {**analyze, "document": c.document.text + "\ncharge=1"}
    assert op.post("/walkthrough-api/analyze", json=changed, headers=oh).json()["action"] == "deny"
    assert (
        op.post(
            "/api/proposals",
            json={
                "operation_id": "bypass",
                "kind": "invoice_correct",
                "resource_id": c.invoice_id,
                "expected_version": 0,
            },
            headers=oh,
        ).status_code
        == 409
    )
    request = {
        "analysis": analyze,
        "expected_version": 0,
        "analysis_digest": finding["analysis_digest"],
        "operation_id": "walkthrough-correct",
    }
    assert rv.post("/walkthrough-api/propose", json=request, headers=rh).status_code == 403
    proposed = op.post("/walkthrough-api/propose", json=request, headers=oh)
    assert proposed.status_code == 200
    assert proposed.json()["command"]["invoice_amount_minor"] == "3000"
    assert op.get("/api/workbench").json()["digest"]["ledger_entries"] == "0"
    url = "/api/proposals/walkthrough-correct"
    assert op.post(url + "/apply", json={}, headers=oh).status_code == 409
    display = rv.get("/api/workbench").json()["proposals"][0]
    assert (
        op.post(
            url + "/review",
            json={"decision": "approve", "action_digest": display["action_digest"]},
            headers=oh,
        ).status_code
        == 403
    )
    assert (
        rv.post(
            url + "/review", json={"decision": "approve", "action_digest": "f" * 64}, headers=rh
        ).status_code
        == 409
    )
    assert (
        rv.post(
            url + "/review",
            json={"decision": "approve", "action_digest": display["action_digest"]},
            headers=rh,
        ).status_code
        == 200
    )
    assert rv.get("/api/workbench").json()["digest"]["ledger_entries"] == "0"
    assert rv.post(url + "/apply", json={}, headers=rh).status_code == 403
    receipt = op.post(url + "/apply", json={}, headers=oh)
    assert receipt.status_code == 200 and receipt.json()["committed"]
    # Fresh app/store instances; sessions, exact approved action and receipt remain in SQL.
    restarted = build()
    op2, oh2 = signed(restarted, "operator", trial)
    assert op2.post(url + "/apply", json={}, headers=oh2).json() == receipt.json()
    assert op2.post("/walkthrough-api/propose", json=request, headers=oh2).status_code == 200
    workbench = op2.get("/api/workbench").json()
    assert workbench["digest"]["ledger_entries"] == "1"
    assert workbench["ledger"][0]["delta_minor"] == "500"
    assert (
        op2.post("/walkthrough-api/analyze", json=analyze, headers=oh2).json()["action"]
        == "no_change"
    )
    assert op2.post("/api/logout", json={}, headers=oh2).status_code == 200
    assert op2.get("/walkthrough-api/cases").status_code == 403
