"""Required real SQL sessions, review UI projection, event recovery and ledger digest."""

import hashlib
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from inngest.experimental import mocked
from revenue_integrity.console_api import create_app
from revenue_integrity.console_auth import AuthStore, provision, setup_console
from revenue_integrity.console_contracts import Principal, Submission, Wake
from revenue_integrity.console_service import ConsoleService, action_digest
from revenue_integrity.events import EventHandlers, build_functions, event_for
from revenue_integrity.operation_contracts import BusinessReview
from revenue_integrity.operations import OperationStore
from test_revenue_operations import app as app
from test_revenue_operations import seed

PASSWORD = "invented Revenue password 2026"
ORIGIN = "http://127.0.0.1:8876"


@pytest.fixture(scope="module")
def console(app):
    with app[0].connect(app[1].name) as admin:
        setup_console(admin, app[1].name)
    return app


def actors(console, **kwargs):
    store, operator, reviewer, command, records = seed(console, **kwargs)
    users = tuple(
        Principal(
            username=role + uuid.uuid4().hex,
            tenant_id=grant.tenant_id,
            actor_id=role + uuid.uuid4().hex,
            role=role,
            invoice_ids=grant.invoice_ids,
            account_ids=grant.account_ids,
        )
        for role, grant in (("operator", operator), ("reviewer", reviewer))
    )
    with console[0].connect(console[1].name) as admin:
        for user in users:
            provision(admin, user, PASSWORD)
    auth = AuthStore(lambda: console[0].connect_trial(console[1]))
    service = ConsoleService(store)
    return service, auth, users, command, records


def submission(command, op=None):
    return Submission(
        operation_id=op or command.business_operation_id,
        kind="invoice_correct",
        resource_id=command.resource_id,
        expected_version=command.expected_version,
    )


def signed(service, auth, user, trial):
    client = TestClient(create_app(service, auth, origin=ORIGIN, trial_id=trial), base_url=ORIGIN)
    response = client.post(
        "/api/login",
        json={"username": user.username, "password": PASSWORD},
        headers={"origin": ORIGIN},
    )
    assert response.status_code == 200
    cookies = client.cookies
    suffix = hashlib.sha256(trial.encode()).hexdigest()[:12]
    headers = {"origin": ORIGIN, "x-csrf-token": cookies.get("revenue_csrf_" + suffix)}
    return client, headers


def test_sql_sessions_exact_review_duplicate_apply_and_truthful_digest(console):
    service, auth, (operator, reviewer), command, records = actors(console)
    op, oh = signed(service, auth, operator, console[1].name)
    rv, rh = signed(service, auth, reviewer, console[1].name)
    assert (
        op.post(
            "/api/proposals", json=submission(command).model_dump(mode="json"), headers=oh
        ).status_code
        == 200
    )
    proposal = service.store.proposals(operator.grant())[0]
    assert (
        op.post(
            "/api/proposals/" + command.business_operation_id + "/apply", json={}, headers=oh
        ).status_code
        == 409
    )
    assert (
        rv.post(
            "/api/proposals/" + command.business_operation_id + "/review",
            json={"decision": "approve", "action_digest": "0" * 64},
            headers=rh,
        ).status_code
        == 409
    )
    assert (
        rv.post(
            "/api/proposals/" + command.business_operation_id + "/review",
            json={"decision": "approve", "action_digest": action_digest(proposal)},
            headers=rh,
        ).status_code
        == 200
    )
    for _ in range(2):
        assert (
            op.post(
                "/api/proposals/" + command.business_operation_id + "/apply", json={}, headers=oh
            ).status_code
            == 200
        )
    result = op.get("/api/workbench").json()
    assert (
        result["digest"]["found_minor"] == "1000"
        and result["digest"]["applied_minor"] == "1000"
        and result["digest"]["ledger_entries"] == "1"
    )
    assert (
        result["findings"][0]["delta_minor"] == "0"
        and result["proposals"][0]["status"] == "applied"
    )
    assert "billing_input" not in str(result) and "unit_price_minor" not in str(result)
    assert (
        rv.post(
            "/api/proposals/" + command.business_operation_id + "/apply", json={}, headers=rh
        ).status_code
        == 403
    )
    assert op.post("/api/logout", json={}, headers=oh).status_code == 200
    assert op.get("/api/workbench").status_code == 403


def test_rejection_reproposal_compensation_and_scope_do_not_invent_funnel(console):
    service, auth, (operator, reviewer), command, records = actors(console)
    first = service.propose(operator, submission(command))
    service.review(
        reviewer, command.business_operation_id, approve=False, digest=action_digest(first)
    )
    next_op = uuid.uuid4().hex
    second = service.propose(operator, submission(command, next_op))
    service.review(reviewer, next_op, approve=True, digest=action_digest(second))
    receipt = service.store.apply(operator.grant(), next_op, run_id="invented-apply")
    undo = Submission(
        operation_id="undo-" + uuid.uuid4().hex,
        kind="compensate",
        resource_id=command.resource_id,
        expected_version=receipt.after.version,
        original_operation_id=next_op,
    )
    compensation = service.propose(operator, undo)
    service.review(reviewer, undo.operation_id, approve=True, digest=action_digest(compensation))
    service.store.apply(operator.grant(), undo.operation_id, run_id="invented-undo")
    service.store.apply(operator.grant(), undo.operation_id, run_id="invented-retry")
    d = service.workbench(operator)["digest"]
    assert (
        d["found_minor"] == 1000
        and d["proposed_minor"] == 2000
        and d["approved_minor"] == 1000
        and d["rejected_minor"] == 1000
    )
    assert (
        d["applied_minor"] == 1000
        and d["compensated_minor"] == 1000
        and d["net_adjustment_minor"] == 0
        and d["ledger_entries"] == 2
    )
    outsider = operator.model_copy(update={"tenant_id": "other-tenant"})
    assert service.workbench(outsider)["records"] == []
    with pytest.raises((LookupError, PermissionError)):
        service.propose(outsider, submission(command))


def test_sdk_missed_approval_wakeup_and_repeated_sweeps_use_only_canonical_sql(console):
    service, auth, (operator, reviewer), command, records = actors(console)
    proposal = service.propose(operator, submission(command))
    handlers = EventHandlers(service.store, auth.principal_for, lambda: (operator,))
    initial = handlers.snapshot(
        Wake(
            tenant_id=operator.tenant_id,
            actor_id=operator.actor_id,
            operation_id=command.business_operation_id,
        )
    )
    assert initial["status"] == "pending"
    service.review(
        reviewer, command.business_operation_id, approve=True, digest=action_digest(proposal)
    )
    sdk = mocked.Inngest(app_id="invented-revenue-sql", is_production=False)
    functions = build_functions(sdk, handlers)
    wake = Wake(
        tenant_id=operator.tenant_id,
        actor_id=operator.actor_id,
        operation_id=command.business_operation_id,
    )
    # The read was memoized pending before the reviewer decision; its wakeup was missed.
    result = mocked.trigger(
        functions[0],
        event_for(wake),
        sdk,
        step_stubs={"read-proposal": initial, "approval-wakeup": mocked.Timeout},
    )
    assert result.status is mocked.Status.COMPLETED and result.output == {"status": "applied"}
    assert handlers.reconcile(wake, "retry") == {"status": "already_applied"}
    assert handlers.sweep() == {"expired": 0, "applied": 0, "unresolved": 0}
    assert len(service.store.ledger(operator.grant())) == 1
    assert (
        b"internal note" not in event_for(wake).model_dump_json().encode()
        and b"unit_price" not in event_for(wake).model_dump_json().encode()
    )


def test_expiry_disabled_account_and_login_throttle_are_real_sql(console):
    service, auth, (operator, reviewer), command, records = actors(console)
    now = datetime(2026, 10, 21, tzinfo=UTC)
    store = OperationStore(service.store.connect, clock=lambda: now)
    store.propose(operator.grant(), command, ttl_seconds=1)
    late = OperationStore(service.store.connect, clock=lambda: now + timedelta(seconds=2))
    assert len(late.sweep(operator.grant())) == 1
    assert late.proposals(operator.grant())[0].status == "expired"
    with pytest.raises(BusinessReview):
        late.review(reviewer.grant(), command.business_operation_id, approve=True)
    token, csrf, _ = auth.login(operator.username, PASSWORD)
    with console[0].connect(console[1].name) as admin:
        admin.execute(
            "UPDATE revenue_app.accounts SET enabled=false WHERE username=%s", (operator.username,)
        )
    with pytest.raises(PermissionError):
        auth.authenticate(token, csrf)
    for _ in range(6):
        with pytest.raises(PermissionError):
            auth.login(reviewer.username, "invented wrong password")
    with pytest.raises(PermissionError):
        auth.login(reviewer.username, PASSWORD)
