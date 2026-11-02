"""Invented customer authority, exact SQL effects and authenticated HTTP boundaries."""

import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import psycopg
import pytest
from fastapi.testclient import TestClient
from olist_support.business_contracts import BusinessReview
from olist_support.console_api import create_app
from olist_support.console_auth import AuthStore, provision
from olist_support.console_cases import CaseStore
from olist_support.console_contracts import Decision, Principal, Submission
from olist_support.customer_intent import Authority, Confirmation, CustomerIntentStore
from psycopg.types.json import Jsonb
from test_olist_business import app as app
from test_olist_console import ORIGIN, PASSWORD, actors, observed
from test_olist_console import console as console
from test_olist_workflow import context


def test_database_rejects_older_refund_writer_and_unreceipted_balance_change(console):
    store, case, customer, reviewer = pending(console)
    # The old low-level writer has policy/capability authority, not customer consent.
    with pytest.raises(psycopg.errors.CheckViolation):
        store.business.refund(
            reviewer.grant(case.order_id),
            case.command,
            run_id=uuid.uuid4().hex,
            run_limit_minor=10000,
        )
    with pytest.raises(psycopg.errors.CheckViolation):
        with store.connect() as connection:
            connection.execute(
                "UPDATE olist.orders SET refunded_minor=1,version=version+1 "
                "WHERE tenant_id=%s AND order_id=%s",
                (case.tenant_id, case.order_id),
            )
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with store.connect() as connection:
            connection.execute(
                "ALTER TABLE olist.refunds DISABLE TRIGGER olist_customer_authority_commit"
            )
    assert observed(console, case) == ((0, 0), (0, 0), 0)
    intent, payload = authority(store, case, customer)
    intent.confirm(customer, case.case_id, payload)
    # Even a confirmed challenge needs consumption/case/audit in this same commit.
    with pytest.raises(psycopg.errors.CheckViolation):
        store.business.refund(
            reviewer.grant(case.order_id),
            case.command,
            run_id=uuid.uuid4().hex,
            run_limit_minor=10000,
        )
    assert observed(console, case) == ((0, 0), (0, 0), 0)


def test_restore_preserves_consumed_authority_after_customer_revocation(console):
    from agent_harness.postgres import drop_trial
    from olist_support.backup import capture, restore
    from olist_support.service_health import readiness
    from test_olist_operations_recovery import bootstrap

    store, case, customer, _ = pending(console)
    intent, payload = authority(store, case, customer)
    intent.confirm(customer, case.case_id, payload)
    result = intent.execute(customer, case.case_id, payload, run_limit_minor=10000)
    with console[0].connect(console[1].name) as admin:
        admin.execute(
            "UPDATE olist_app.accounts SET enabled=false WHERE username=%s", (customer.username,)
        )
    archive = capture(
        console[0], console[1], code_revision="invented-customer-source", environment_lock="a" * 64
    )
    from agent_harness.release_contracts import pin

    target = restore(
        console[0],
        console[1].workspace_key,
        "customer-restore-" + uuid.uuid4().hex,
        archive,
        archive_sha256=pin(archive),
        bootstrap=bootstrap,
    )
    try:
        restored = CaseStore(lambda: console[0].connect_trial(target))
        assert restored.detail(customer, case.case_id)[0].result.receipt == result.result.receipt
        assert readiness(restored.connect)["ready"]
        with restored.connect() as connection:
            row = connection.execute(
                "SELECT state FROM olist_intent.challenges WHERE tenant_id=%s AND case_id=%s",
                (case.tenant_id, case.case_id),
            ).fetchone()
            assert row == ("consumed",)
    finally:
        drop_trial(console[0], target)


def pending(console, *, required_review=False):
    order, operator, reviewer = actors(console)
    store = CaseStore(lambda: console[0].connect_trial(console[1]))
    # Deliberately wrong suggested refund on a size complaint: still no effect.
    case = store.submit(
        operator,
        Submission(
            event_key=uuid.uuid4().hex,
            order_id=order,
            text="The size is wrong; what options do I have?",
            intent="refund",
            require_review=required_review,
        ),
        context(event=uuid.uuid4().hex, run=uuid.uuid4().hex),
        run_limit_minor=10000,
    )
    customer = Principal(
        username="customer" + uuid.uuid4().hex,
        tenant_id=case.tenant_id,
        actor_id=uuid.uuid4().hex,
        role="customer",
        order_ids=(order,),
    )
    with console[0].connect(console[1].name) as admin:
        provision(admin, customer, PASSWORD)
    return store, case, customer, reviewer


def authority(store, case, customer):
    intent = CustomerIntentStore(store)
    offer = intent.issue(customer, case.case_id)
    payload = Confirmation(
        challenge=offer["challenge"],
        action="refund",
        amount_minor=offer["amount_minor"],
        unit="SIM",
    )
    return intent, payload


def test_wrong_suggestion_waits_for_exact_customer_confirmation_and_duplicate_returns_original(
    console,
):
    store, case, customer, _ = pending(console)
    assert (
        case.status == "review_required" and case.result.reason == "customer_confirmation_required"
    )
    assert observed(console, case) == ((0, 0), (0, 0), 0)
    assert customer.grant(case.order_id).capabilities == ("read",)
    intent, payload = authority(store, case, customer)
    with pytest.raises(BusinessReview):
        intent.execute(customer, case.case_id, payload, run_limit_minor=10000)
    intent.confirm(customer, case.case_id, payload)
    assert observed(console, case) == ((0, 0), (0, 0), 0)
    result = intent.execute(customer, case.case_id, payload, run_limit_minor=10000)
    assert result.status == "committed" and observed(console, case) == ((5000, 1), (1, 5000), 1)
    assert intent.execute(customer, case.case_id, payload, run_limit_minor=10000) == result
    assert intent.confirm(customer, case.case_id, payload) == {"confirmed": True, "committed": True}


def test_reviewer_approval_alone_and_cross_customer_or_amount_cannot_authorize(console):
    store, case, customer, reviewer = pending(console, required_review=True)
    intent = CustomerIntentStore(store)
    with pytest.raises(BusinessReview):
        intent.issue(customer, case.case_id)
    approved = store.decide(
        reviewer,
        case.case_id,
        Decision(
            decision="approve",
            expected_version=case.version,
            action_digest=case.action_digest,
            rationale="Invented review, not customer consent.",
        ),
    )
    with pytest.raises(BusinessReview):
        store.resume(reviewer, case.case_id, case.action_digest, run_limit_minor=10000)
    intent, payload = authority(store, approved, customer)
    with pytest.raises(PermissionError):
        intent.confirm(customer, case.case_id, payload.model_copy(update={"amount_minor": 4999}))
    with pytest.raises(PermissionError):
        intent.confirm(
            customer.model_copy(update={"actor_id": "another-customer"}), case.case_id, payload
        )
    with pytest.raises(PermissionError):
        intent.confirm(customer.model_copy(update={"order_ids": ()}), case.case_id, payload)
    assert observed(console, case) == ((0, 0), (0, 0), 0)
    intent.confirm(customer, case.case_id, payload)
    assert (
        store.resume(reviewer, case.case_id, case.action_digest, run_limit_minor=10000).status
        == "committed"
    )


def test_expired_or_rotated_challenge_and_changed_case_do_not_commit(console):
    store, case, customer, reviewer = pending(console)
    intent, old = authority(store, case, customer)
    _, payload = authority(store, case, customer)
    with pytest.raises(PermissionError):
        intent.confirm(customer, case.case_id, old)
    with console[0].connect(console[1].name) as admin:
        raw = admin.execute(
            "SELECT document FROM olist_intent.challenges WHERE tenant_id=%s AND case_id=%s",
            (case.tenant_id, case.case_id),
        ).fetchone()[0]
        value = Authority.model_validate_json(json.dumps(raw))
        past = datetime.now(UTC) - timedelta(minutes=10)
        value = value.model_copy(
            update={"issued_at": past, "expires_at": past + timedelta(minutes=5)}
        )
        admin.execute(
            "UPDATE olist_intent.challenges SET document=%s WHERE tenant_id=%s AND case_id=%s",
            (Jsonb(value.model_dump(mode="json")), case.tenant_id, case.case_id),
        )
    with pytest.raises(BusinessReview):
        intent.confirm(customer, case.case_id, payload)
    _, payload = authority(store, case, customer)
    intent.confirm(customer, case.case_id, payload)
    store.reevaluate(reviewer, case.case_id)
    with pytest.raises(BusinessReview):
        intent.execute(customer, case.case_id, payload, run_limit_minor=10000)
    assert observed(console, case) == ((0, 0), (0, 0), 0)


def test_confirmation_and_effect_roll_back_together_and_recover_after_lost_response(console):
    store, case, customer, _ = pending(console)
    intent, payload = authority(store, case, customer)
    intent.confirm(customer, case.case_id, payload)

    def before(stage):
        if stage == "before_commit":
            raise RuntimeError("invented precommit failure")

    with pytest.raises(RuntimeError):
        intent.execute(customer, case.case_id, payload, run_limit_minor=10000, fault=before)
    assert observed(console, case) == ((0, 0), (0, 0), 0)

    def after(stage):
        if stage == "after_commit":
            raise TimeoutError("invented lost response")

    with pytest.raises(TimeoutError):
        intent.execute(customer, case.case_id, payload, run_limit_minor=10000, fault=after)
    rebuilt = CustomerIntentStore(CaseStore(store.connect))
    result = rebuilt.execute(customer, case.case_id, payload, run_limit_minor=10000)
    assert result.status == "committed" and observed(console, case) == ((5000, 1), (1, 5000), 1)


def test_concurrent_confirmation_delivery_has_one_effect_and_revocation_blocks_new_effect(console):
    store, case, customer, _ = pending(console)
    intent, payload = authority(store, case, customer)
    intent.confirm(customer, case.case_id, payload)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda _: intent.execute(customer, case.case_id, payload, run_limit_minor=10000),
                range(2),
            )
        )
    assert results[0].result.receipt == results[1].result.receipt
    assert observed(console, case) == ((5000, 1), (1, 5000), 1)
    store, case, customer, _ = pending(console)
    intent, payload = authority(store, case, customer)
    intent.confirm(customer, case.case_id, payload)
    with console[0].connect(console[1].name) as admin:
        admin.execute(
            "UPDATE olist_app.accounts SET enabled=false WHERE username=%s", (customer.username,)
        )
    with pytest.raises(BusinessReview):
        intent.execute(customer, case.case_id, payload, run_limit_minor=10000)
    assert observed(console, case) == ((0, 0), (0, 0), 0)


def test_customer_http_session_cannot_reach_internal_case_or_bypass_csrf(console):
    store, case, customer, _ = pending(console)
    client = TestClient(
        create_app(
            store,
            AuthStore(store.connect),
            origin=ORIGIN,
            trial_id=console[1].name,
            code_revision="invented-customer",
            environment_lock="a" * 64,
            run_limit_minor=10000,
        ),
        base_url=ORIGIN,
    )
    login = client.post(
        "/api/login",
        json={"username": customer.username, "password": PASSWORD},
        headers={"origin": ORIGIN},
    )
    headers = {"origin": ORIGIN, "x-csrf-token": client.cookies[login.json()["csrf_cookie"]]}
    assert client.get("/api/cases/" + case.case_id).status_code == 403
    assert client.get("/api/orders").status_code == 403
    path = "/api/customer/cases/" + case.case_id
    assert client.post(path + "/challenge", json={}).status_code == 403
    offer = client.post(path + "/challenge", json={}, headers=headers).json()
    body = {
        "challenge": offer["challenge"],
        "action": "refund",
        "amount_minor": offer["amount_minor"],
        "unit": "SIM",
    }
    assert (
        client.post(
            path + "/confirm", json={**body, "role": "customer"}, headers=headers
        ).status_code
        == 422
    )
    assert (
        client.post(
            path + "/confirm", json={**body, "amount_minor": 1}, headers=headers
        ).status_code
        == 403
    )
    assert client.post(path + "/confirm", json=body, headers=headers).json() == {
        "confirmed": True,
        "committed": False,
    }
    response = client.post(path + "/execute", json=body, headers=headers)
    assert response.status_code == 200 and response.json()["committed"]
    assert "events" not in client.get(path).json()
    assert observed(console, case) == ((5000, 1), (1, 5000), 1)
