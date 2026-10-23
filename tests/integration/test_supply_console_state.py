"""Actual SQL notice recovery, roles and atomic budget projection."""

from datetime import timedelta

import psycopg
import pytest
from supply_chain.console_auth import AuthStore, provision, setup_console
from supply_chain.console_contracts import (
    Confirmation,
    Decision,
    IncidentScope,
    Principal,
    Selection,
)
from supply_chain.console_service import ConsoleService
from supply_chain.notices import NoticeStore
from test_supply_operations import app as supply_app  # noqa: F401
from test_supply_operations import seed

pytestmark = pytest.mark.usefixtures("supply_app")


def test_durable_notices_roles_exact_review_and_confirmation(supply_app, monkeypatch):  # noqa: F811
    server, trial, store, now = supply_app
    _, operator, _, _, event, shipments = seed(supply_app)
    with server.connect(trial.name) as admin:
        setup_console(admin, trial.name)
    scope = (IncidentScope(event_id=event, shipment_ids=(shipments[0].shipment_id,)),)
    users = {
        role: Principal(
            username=role + "-console", tenant_id="invented", actor_id=role, role=role, scopes=scope
        )
        for role in ("operator", "reviewer", "confirmer", "viewer")
    }

    def connect():
        return server.connect_trial(trial)

    notices = NoticeStore(connect)
    service = ConsoleService(store, notices)
    board = service.assess(users["operator"], event)
    assert board["shipments"][0]["state"] == "pending"
    assert board["budget"]["spent_minor"] == 0
    proposal = board["shipments"][0]["snapshot"]["proposal"]
    value = dict(
        event_id=event,
        shipment_id=shipments[0].shipment_id,
        payload_sha256=proposal["payload_sha256"],
    )
    with pytest.raises(PermissionError):
        service.review(users["operator"], Decision(**value, approve=True))
    service.review(users["reviewer"], Decision(**value, approve=True))
    original = notices.append
    monkeypatch.setattr(notices, "append", lambda _: (_ for _ in ()).throw(RuntimeError("outage")))
    with pytest.raises(RuntimeError, match="outage"):
        service.apply(users["operator"], Selection(**value))
    assert len(store.receipts(operator, event)) == 1
    monkeypatch.setattr(notices, "append", original)
    board = service.board(users["viewer"], event)
    assert board["budget"]["spent_minor"] == 8000
    assert board["shipments"][0]["state"] == "awaiting_confirmation"
    assert any(n["state"] == "committed" for n in board["notices"])
    before = len(board["notices"])
    assert len(service.board(users["viewer"], event)["notices"]) == before
    service.apply(users["operator"], Selection(**value))
    assert len(store.receipts(operator, event)) == 1
    board = service.confirm(users["confirmer"], Confirmation(**value, success=True))
    assert board["shipments"][0]["state"] == "confirmed"
    assert "No shipment delivery outcome" in next(
        n["body"] for n in board["notices"] if n["state"] == "confirmed"
    )
    notice_id = board["notices"][0]["notice_id"]
    # Read state survives store reconstruction and belongs to one account.
    with server.connect(trial.name) as admin:
        for user in users.values():
            provision(admin, user, "invented-password-for-test")
    notices.acknowledge(users["viewer"], notice_id)
    rebuilt = NoticeStore(connect)
    assert next(n.read for n in rebuilt.list(users["viewer"], event) if n.notice_id == notice_id)
    assert not next(
        n.read for n in rebuilt.list(users["operator"], event) if n.notice_id == notice_id
    )
    other = users["viewer"].model_copy(update={"tenant_id": "other"})
    with pytest.raises(PermissionError):
        rebuilt.acknowledge(other, notice_id)
    auth = AuthStore(connect, clock=lambda: now[0])
    token, csrf, user = auth.login("viewer-console", "invented-password-for-test")
    assert auth.authenticate(token, csrf) == user
    with pytest.raises(PermissionError):
        auth.authenticate(token, "wrong")
    now[0] += timedelta(minutes=31)
    with pytest.raises(PermissionError):
        auth.authenticate(token, csrf)
    with connect() as runtime:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            runtime.execute("DELETE FROM supply_app.notices")
