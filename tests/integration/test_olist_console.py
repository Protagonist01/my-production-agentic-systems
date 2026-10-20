"""Real Postgres approval/session/API boundaries with invented source facts only."""

import json
import os
import subprocess
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from olist_support.business import enroll
from olist_support.business_contracts import BusinessReview
from olist_support.console_api import create_app
from olist_support.console_auth import AuthStore, provision, setup_console
from olist_support.console_cases import CaseStore
from olist_support.console_contracts import Decision, Principal, Submission
from test_olist_business import app as app
from test_olist_policy import confirmation, invented_view
from test_olist_workflow import context

PASSWORD = "invented console password 2026"
ORIGIN = "http://127.0.0.1:8765"


@pytest.fixture(scope="module")
def console(app):
    server, trial, _ = app
    with server.connect(trial.name) as admin:
        setup_console(admin, trial.name)
    return app


def actors(console, amount=5000, *, facts=True):
    server, trial, _ = console
    order = "invented-console-" + uuid.uuid4().hex
    with server.connect(trial.name) as admin:
        enroll(
            admin,
            invented_view(amount, order_id=order),
            confirmation(order_id=order) if facts else None,
        )
    users = [
        Principal(
            username=role + uuid.uuid4().hex,
            tenant_id="invented-tenant",
            actor_id=role + uuid.uuid4().hex,
            role=role,
            order_ids=(order,),
        )
        for role in ("operator", "reviewer")
    ]
    return order, *users


def create_case(console, *, amount=5000, facts=True):
    order, operator, reviewer = actors(console, amount, facts=facts)
    store = CaseStore(lambda: console[0].connect_trial(console[1]))
    request = Submission(
        event_key=uuid.uuid4().hex,
        order_id=order,
        text="Invented refund request.",
        intent="refund",
        require_review=True,
    )
    case = store.submit(
        operator,
        request,
        context(event=uuid.uuid4().hex, run=uuid.uuid4().hex),
        run_limit_minor=10000,
    )
    assert case.status == "review_required"
    return store, case, operator, reviewer


def decide(store, case, reviewer, decision="approve"):
    return store.decide(
        reviewer,
        case.case_id,
        Decision(
            decision=decision,
            expected_version=case.version,
            action_digest=case.action_digest,
            rationale="Invented explicit reviewer decision.",
        ),
    )


def observed(console, case):
    with console[0].connect(console[1].name) as admin:
        order = admin.execute(
            "SELECT refunded_minor,version FROM olist.orders WHERE tenant_id=%s AND order_id=%s",
            (case.tenant_id, case.order_id),
        ).fetchone()
        ledger = admin.execute(
            (
                "SELECT count(*),coalesce(sum(amount_minor),0) FROM olist.refunds WHERE"
                " tenant_id=%s AND order_id=%s"
            ),
            (case.tenant_id, case.order_id),
        ).fetchone()
        events = admin.execute(
            (
                "SELECT count(*) FROM olist_app.events WHERE tenant_id=%s AND "
                "case_id=%s AND kind='committed'"
            ),
            (case.tenant_id, case.case_id),
        ).fetchone()[0]
    return order, ledger, events


def test_exact_approval_audit_and_refund_are_atomic_and_recover_after_lost_response(console):
    store, case, operator, reviewer = create_case(console)
    assert case.command.amount_minor == 5000 and case.evidence.currency_unit is None
    with pytest.raises(PermissionError):
        decide(store, case, operator)
    with pytest.raises(BusinessReview):
        store.decide(
            reviewer,
            case.case_id,
            Decision(
                decision="approve",
                expected_version=case.version,
                action_digest="forged",
                rationale="Invented invalid binding.",
            ),
        )
    approved = decide(store, case, reviewer)
    assert approved.status == "approved" and observed(console, case) == ((0, 0), (0, 0), 0)

    def before(stage):
        if stage == "before_commit":
            raise RuntimeError("invented before-commit failure")

    with pytest.raises(RuntimeError):
        store.resume(
            reviewer, case.case_id, case.action_digest, run_limit_minor=10000, fault=before
        )
    assert store.detail(reviewer, case.case_id)[0].status == "approved" and observed(
        console, case
    ) == ((0, 0), (0, 0), 0)

    def after(stage):
        if stage == "after_commit":
            raise TimeoutError("invented lost response")

    with pytest.raises(TimeoutError):
        store.resume(reviewer, case.case_id, case.action_digest, run_limit_minor=10000, fault=after)
    assert observed(console, case) == ((5000, 1), (1, 5000), 1)
    restarted = CaseStore(store.connect)
    first = restarted.resume(reviewer, case.case_id, case.action_digest, run_limit_minor=10000)
    again = restarted.resume(reviewer, case.case_id, case.action_digest, run_limit_minor=10000)
    assert (
        first == again
        and first.status == "committed"
        and first.result.receipt.actor_id == reviewer.actor_id
    )
    assert observed(console, case) == ((5000, 1), (1, 5000), 1)


def test_rejection_ineligible_facts_and_cap_cannot_be_overridden(console):
    for amount, facts in ((10001, True), (5000, False)):
        store, case, _, reviewer = create_case(console, amount=amount, facts=facts)
        assert case.command is None and case.action_digest is None
        with pytest.raises(BusinessReview):
            decide(store, case, reviewer)
        rejected = decide(store, case, reviewer, "reject")
        assert rejected.status == "rejected"
        with pytest.raises((PermissionError, BusinessReview)):
            store.resume(reviewer, case.case_id, None, run_limit_minor=10000)
        assert observed(console, case) == ((0, 0), (0, 0), 0)


def test_changed_record_invalidates_approval_and_requires_new_explicit_decision(console):
    store, case, _, reviewer = create_case(console)
    decide(store, case, reviewer)
    with console[0].connect(console[1].name) as admin:
        admin.execute(
            "UPDATE olist.orders SET version=version+1 WHERE tenant_id=%s AND order_id=%s",
            (case.tenant_id, case.order_id),
        )
    stale = store.resume(reviewer, case.case_id, case.action_digest, run_limit_minor=10000)
    assert stale.status == "stale" and observed(console, case) == ((0, 1), (0, 0), 0)
    refreshed = store.reevaluate(reviewer, case.case_id)
    assert refreshed.action_digest != case.action_digest and refreshed.command.expected_version == 1
    with pytest.raises(BusinessReview):
        decide(store, case, reviewer)
    decide(store, refreshed, reviewer)
    assert (
        store.resume(reviewer, case.case_id, refreshed.action_digest, run_limit_minor=10000).status
        == "committed"
    )
    assert observed(console, case) == ((5000, 2), (1, 5000), 1)


def test_reviewer_identity_scope_concurrent_decisions_and_resume_cannot_duplicate(console):
    store, case, operator, reviewer = create_case(console)
    other = reviewer.model_copy(update={"actor_id": "invented-other-reviewer"})

    def attempt(user):
        try:
            return decide(store, case, user)
        except BusinessReview:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, [reviewer, other]))
    approved = next(x for x in results if x is not None)
    assert sum(x is not None for x in results) == 1
    winner = reviewer if approved.approved_by == reviewer.actor_id else other
    loser = other if winner == reviewer else reviewer
    with pytest.raises(PermissionError):
        store.resume(loser, case.case_id, case.action_digest, run_limit_minor=10000)
    with pytest.raises(PermissionError):
        store.detail(reviewer.model_copy(update={"order_ids": ()}), case.case_id)
    with pytest.raises(LookupError):
        store.detail(reviewer.model_copy(update={"tenant_id": "another-tenant"}), case.case_id)
    with ThreadPoolExecutor(max_workers=2) as pool:
        out = list(
            pool.map(
                lambda _: store.resume(
                    winner, case.case_id, case.action_digest, run_limit_minor=10000
                ),
                range(2),
            )
        )
    assert all(x.status == "committed" for x in out) and observed(console, case) == (
        (5000, 1),
        (1, 5000),
        1,
    )


def test_authenticated_http_flow_rejects_role_tenant_csrf_and_forged_authority(console):
    order, operator, reviewer = actors(console)
    server, trial, _ = console
    with server.connect(trial.name) as admin:
        provision(admin, operator, PASSWORD)
        provision(admin, reviewer, PASSWORD)

    def connect():
        return server.connect_trial(trial)

    api = create_app(
        CaseStore(connect),
        AuthStore(connect),
        origin=ORIGIN,
        trial_id=trial.name,
        code_revision="invented-code",
        environment_lock="invented-lock",
        run_limit_minor=10000,
    )
    client = TestClient(api, base_url=ORIGIN)
    assert client.get("/api/cases").status_code == 403
    assert (
        client.post(
            "/api/login", json={"username": operator.username, "password": PASSWORD}
        ).status_code
        == 403
    )
    signed = client.post(
        "/api/login",
        json={"username": operator.username, "password": PASSWORD},
        headers={"origin": ORIGIN},
    )
    assert (
        signed.status_code == 200 and "httponly" in signed.headers.get_list("set-cookie")[0].lower()
    )
    csrf = client.cookies.get(signed.json()["csrf_cookie"])
    headers = {"origin": ORIGIN, "x-csrf-token": csrf}
    payload = Submission(
        event_key=uuid.uuid4().hex,
        order_id=order,
        text="Invented HTTP support request.",
        intent="refund",
        require_review=True,
    ).model_dump(mode="json")
    assert client.post("/api/cases", json=payload).status_code == 403
    assert (
        client.post(
            "/api/cases",
            json={**payload, "tenant_id": "forged", "role": "reviewer"},
            headers=headers,
        ).status_code
        == 422
    )
    response = client.post("/api/cases", json=payload, headers=headers)
    assert response.status_code == 200, response.text
    case = response.json()
    path = "/api/cases/" + case["case_id"]
    decision = {
        "decision": "approve",
        "expected_version": case["version"],
        "action_digest": case["action_digest"],
        "rationale": "Invented authenticated approval.",
    }
    assert client.post(path + "/decision", json=decision, headers=headers).status_code == 403
    assert client.post("/api/logout", json={}, headers=headers).status_code == 200
    assert client.get(path).status_code == 403
    signed = client.post(
        "/api/login",
        json={"username": reviewer.username, "password": PASSWORD},
        headers={"origin": ORIGIN},
    )
    headers = {"origin": ORIGIN, "x-csrf-token": client.cookies.get(signed.json()["csrf_cookie"])}
    assert client.get(path).status_code == 200
    assert client.post("/api/cases", json=payload, headers=headers).status_code == 403
    assert (
        client.post(path + "/decision", json=decision, headers=headers).json()["status"]
        == "approved"
    )
    result = client.post(
        path + "/resume", json={"action_digest": case["action_digest"]}, headers=headers
    )
    assert result.status_code == 200 and result.json()["status"] == "committed", result.text
    assert client.get(path).json()["case"]["result"]["receipt"]["committed"] is True
    assert client.get("/health").json()["status"] == "ready"
    assert "frame-ancestors 'none'" in client.get("/health").headers["content-security-policy"]


def test_sessions_persist_expire_revoke_and_password_failures_are_throttled(console):
    _, operator, _ = actors(console)
    server, trial, _ = console
    with server.connect(trial.name) as admin:
        provision(admin, operator, PASSWORD)

    def connect():
        return server.connect_trial(trial)

    auth = AuthStore(connect)
    for _ in range(5):
        with pytest.raises(PermissionError):
            auth.login(operator.username, "incorrect invented password")
    with pytest.raises(PermissionError):
        auth.login(operator.username, PASSWORD)
    with server.connect(trial.name) as admin:
        admin.execute("DELETE FROM olist_app.login_attempts")
    token, csrf, user = auth.login(operator.username, PASSWORD)
    assert AuthStore(connect).authenticate(token, csrf) == user
    with pytest.raises(PermissionError):
        auth.authenticate(token, "forged-csrf")
    with server.connect(trial.name) as admin:
        admin.execute(
            "UPDATE olist_app.accounts SET enabled=false WHERE username=%s", (operator.username,)
        )
    with pytest.raises(PermissionError):
        auth.authenticate(token)
    with server.connect(trial.name) as admin:
        admin.execute(
            "UPDATE olist_app.accounts SET enabled=true WHERE username=%s", (operator.username,)
        )
        admin.execute(
            "UPDATE olist_app.sessions SET expires_at=now()-interval '1 second' WHERE username=%s",
            (operator.username,),
        )
    with pytest.raises(PermissionError):
        auth.authenticate(token)


def test_runtime_cannot_delete_decision_audit_or_provision_accounts(console):
    import psycopg

    for sql in ("DELETE FROM olist_app.events", "UPDATE olist_app.accounts SET enabled=false"):
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with console[0].connect_trial(console[1]) as connection:
                connection.execute(sql)


def test_owned_process_exit_preserves_exact_approval_completion_and_audit(console):
    store, case, _, reviewer = create_case(console)
    decide(store, case, reviewer)
    server, trial, _ = console
    state = {
        "port": server.port,
        "database": trial.name,
        "password": trial.password,
        "reviewer": reviewer.model_dump(mode="json"),
        "case_id": case.case_id,
        "digest": case.action_digest,
    }
    script = """import json,sys,os,psycopg
from olist_support.console_cases import CaseStore
from olist_support.console_contracts import Principal
s=json.load(sys.stdin)
def connect():
 return psycopg.connect(
  host="127.0.0.1",port=s["port"],user=s["database"],
  password=s["password"],dbname=s["database"])
def fault(stage):
 if stage=="after_commit":os._exit(29)
CaseStore(connect).resume(
 Principal.model_validate_json(json.dumps(s["reviewer"])),
 s["case_id"],s["digest"],run_limit_minor=10000,fault=fault)
"""
    child = subprocess.run(
        [sys.executable, "-c", script],
        input=json.dumps(state),
        text=True,
        capture_output=True,
        timeout=60,
        env=os.environ.copy(),
    )
    assert child.returncode == 29
    assert observed(console, case) == ((5000, 1), (1, 5000), 1)
    restarted = CaseStore(store.connect)
    recovered = restarted.resume(reviewer, case.case_id, case.action_digest, run_limit_minor=10000)
    assert (
        recovered.status == "committed" and recovered.result.receipt.actor_id == reviewer.actor_id
    )
    assert observed(console, case) == ((5000, 1), (1, 5000), 1)


def test_different_tenant_http_account_cannot_inspect_decide_or_resume(console):
    store, case, _, reviewer = create_case(console)
    other = reviewer.model_copy(
        update={"username": "other-" + uuid.uuid4().hex, "tenant_id": "invented-other-tenant"}
    )
    with console[0].connect(console[1].name) as admin:
        provision(admin, other, PASSWORD)
    auth = AuthStore(store.connect)
    client = TestClient(
        create_app(
            store,
            auth,
            origin=ORIGIN,
            trial_id=console[1].name,
            code_revision="invented-code",
            environment_lock="invented-lock",
            run_limit_minor=10000,
        ),
        base_url=ORIGIN,
    )
    signed = client.post(
        "/api/login",
        json={"username": other.username, "password": PASSWORD},
        headers={"origin": ORIGIN},
    )
    assert signed.status_code == 200
    headers = {"origin": ORIGIN, "x-csrf-token": client.cookies.get(signed.json()["csrf_cookie"])}
    path = "/api/cases/" + case.case_id
    assert client.get(path).status_code == 404
    assert (
        client.post(
            path + "/decision",
            json={
                "decision": "approve",
                "expected_version": case.version,
                "action_digest": case.action_digest,
                "rationale": "Invented out-of-scope attempt.",
            },
            headers=headers,
        ).status_code
        == 404
    )
    assert (
        client.post(
            path + "/resume", json={"action_digest": case.action_digest}, headers=headers
        ).status_code
        == 404
    )
    assert client.get("/api/cases").json() == []
    assert observed(console, case) == ((0, 0), (0, 0), 0)
