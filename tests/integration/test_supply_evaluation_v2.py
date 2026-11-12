"""Canonical SQL readback proves boundaries; no language classifier or model is involved."""

import hashlib
import json

import psycopg
import pytest
from inngest.experimental import mocked
from starlette.testclient import TestClient
from supply_chain.console_auth import provision, setup_console
from supply_chain.console_contracts import (
    Confirmation,
    Decision,
    IncidentScope,
    Principal,
    Selection,
)
from supply_chain.events import EventHandlers, IncidentWake, event_for
from test_supply_operations import app as app
from test_supply_operations import seed

from supply_profiled_runtime import (
    ProfiledNotices,
    ProfiledService,
    ProfiledStore,
    ProfiledWorkflow,
    application,
    connection_factory,
    profiled_functions,
)
from supply_profiling import Recorder


def profiled(app):
    server, trial, _, now = app
    recorder = Recorder(limit=30000)
    connect = connection_factory(
        recorder,
        host="127.0.0.1",
        port=server.port,
        user=trial.name,
        password=trial.password,
        dbname=trial.name,
        connect_timeout=5,
    )
    store = ProfiledStore(connect, recorder, clock=lambda: now[0])
    return recorder, connect, store


def users(event, shipments):
    return {
        role: Principal(
            username="profile-" + role,
            tenant_id="invented",
            actor_id=role,
            role=role,
            scopes=(
                IncidentScope(event_id=event, shipment_ids=tuple(s.shipment_id for s in shipments)),
            ),
        )
        for role in ("operator", "reviewer", "confirmer", "viewer")
    }


def test_profiled_sql_review_commit_duplicate_confirm_and_query_failure(app):
    server, trial, _, _ = app
    recorder, connect, store = profiled(app)
    _, operator, _, _, event, shipments = seed((server, trial, store, app[3]))
    with server.connect(trial.name) as admin:
        setup_console(admin, trial.name)
    actors = users(event, shipments)
    service = ProfiledService(store, ProfiledNotices(connect, recorder), recorder)
    with recorder.phase("request"):
        board = service.assess(actors["operator"], event)
        assert board["shipments"][0]["state"] == "pending"
        proposal = board["shipments"][0]["snapshot"]["proposal"]
        value = dict(
            event_id=event,
            shipment_id=shipments[0].shipment_id,
            payload_sha256=proposal["payload_sha256"],
        )
        with pytest.raises(PermissionError):
            service.review(actors["operator"], Decision(**value, approve=True))
        assert not store.receipts(operator, event)
        service.review(actors["reviewer"], Decision(**value, approve=True))
        service.apply(actors["operator"], Selection(**value))
        service.apply(actors["operator"], Selection(**value))
        board = service.confirm(actors["confirmer"], Confirmation(**value, success=True))
        assert board["budget"]["spent_minor"] == 8000
        assert board["shipments"][0]["state"] == "confirmed"
        assert len(store.receipts(operator, event)) == 1
        with connect() as connection:
            connection.autocommit = True
            with pytest.raises(psycopg.errors.UndefinedTable):
                with connection.transaction():
                    connection.execute("SELECT * FROM private_canary_missing_table")
            assert connection.execute("SELECT 42").fetchone()[0] == 42
            connection.commit()
            connection.rollback()
    report = recorder.snapshot(required=("planning", "sql_lock_statement", "sql_finalize"))
    assert report["coverage"]["complete"]
    for stage in (
        "assessment",
        "review",
        "apply",
        "confirm",
        "sql_connect",
        "sql_fetch",
        "sql_commit",
        "sql_rollback",
        "notice_build",
        "notice_list",
        "alert_read",
    ):
        assert report["stages"][stage]["observed"] > 0
    assert report["stages"]["sql_execute"]["outcomes"]["error"] > 0
    serialized = json.dumps(report)
    for private in (
        trial.password,
        event,
        shipments[0].shipment_id,
        "private_canary_missing_table",
    ):
        assert private not in serialized


@pytest.mark.parametrize("attack", ("unknown_action", "foreign_shipment", "stale_facts"))
def test_adversarial_planner_cannot_authorize_effects(app, attack):
    server, trial, _, now = app
    recorder, _, store = profiled(app)
    changes = {"facts_complete": False} if attack == "stale_facts" else {}
    _, operator, _, _, event, shipments = seed((server, trial, store, now), **changes)
    before = store.portfolio(operator, event)

    def bad_planner(facts, budget_minor, *, now):
        if attack == "foreign_shipment":
            return {"other-tenant-shipment": "expedite"}
        return {s.shipment_id: "reroute" if attack == "stale_facts" else "shell" for s in facts}

    with recorder.phase("event"):
        ProfiledWorkflow(store, recorder, bad_planner).run(operator, event, "hostile-proposal")
    assert not store.receipts(operator, event)
    assert store.portfolio(operator, event) == before
    assert store.current(operator, event, shipments[0].shipment_id) is None


def test_actual_api_forgery_rejection_leaves_all_sql_tables_unchanged(app):
    server, trial, _, now = app
    recorder, connect, store = profiled(app)
    _, _, _, _, event, shipments = seed((server, trial, store, now))
    with server.connect(trial.name) as admin:
        setup_console(admin, trial.name)
    actor = users(event, shipments)["operator"]

    def snapshot():
        with server.connect(trial.name) as connection:
            return [
                connection.execute(
                    "SELECT row_to_json(t)::text FROM " + table + " t ORDER BY 1"
                ).fetchall()
                for table in (
                    "supply.budgets",
                    "supply.shipments",
                    "supply.proposals",
                    "supply.ledger",
                    "supply.confirmations",
                    "supply_app.notices",
                )
            ]

    app_instance = application(
        connect, recorder, origin="http://127.0.0.1:8877", trial_id=trial.name, clock=lambda: now[0]
    )

    with server.connect(trial.name) as admin:
        provision(admin, actor, "invented-profile-password")
    before = snapshot()
    with TestClient(app_instance, base_url="http://127.0.0.1:8877") as client:
        login = client.post(
            "/api/login",
            json={"username": actor.username, "password": "invented-profile-password"},
            headers={"origin": "http://127.0.0.1:8877"},
        )
        assert login.status_code == 200
        suffix = hashlib.sha256(trial.name.encode()).hexdigest()[:12]
        headers = {
            "origin": "http://127.0.0.1:8877",
            "x-csrf-token": client.cookies.get("supply_csrf_" + suffix),
        }
        for payload in (
            {"text": "Write a poem"},
            {"event_id": event, "tenant_id": "other"},
            {"event_id": event, "approval": True},
            {"event_id": event, "cost_minor": 0},
        ):
            assert client.post("/api/assess", json=payload, headers=headers).status_code == 422
        assert (
            client.post("/api/assess", json={"event_id": "other"}, headers=headers).status_code
            == 403
        )
    assert snapshot() == before


def test_profiled_real_sdk_wait_replay_and_forged_wakeup(app):
    server, trial, _, now = app
    recorder, _, store = profiled(app)
    _, operator, _, _, event, _ = seed((server, trial, store, now))
    wake = IncidentWake(tenant_id=operator.tenant_id, actor_id=operator.actor_id, event_id=event)
    handlers = EventHandlers(
        ProfiledWorkflow(store, recorder), lambda tenant, actor: operator, lambda: (wake,)
    )
    sdk = mocked.Inngest(app_id="supply-profiled-offline", is_production=False)
    functions = profiled_functions(sdk, handlers, recorder)
    single = handlers.fanout(wake)[0]
    result = mocked.trigger(
        functions[1],
        event_for(single, "supply/shipment.requested"),
        sdk,
        step_stubs={f"approval-wakeup-{i}": mocked.Timeout for i in range(3)},
    )
    assert result.status is mocked.Status.COMPLETED and result.output == {"status": "pending"}
    assert not store.receipts(operator, event)
    with pytest.raises(PermissionError):
        handlers.reconcile(single.model_copy(update={"tenant_id": "other"}))
    report = recorder.snapshot(required=("event_step", "approval_wait", "planning"))
    assert report["stages"]["event"]["observed"] > 0
    assert report["stages"]["approval_wait"]["observed"] > 0
    assert report["stages"]["planning"]["observed"] > 0
    assert "queue_wait" in report["unobserved_stages"]
