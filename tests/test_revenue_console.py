"""Offline Revenue session/API/numeric/event mechanism witnesses with invented data."""

import json
from datetime import UTC, datetime, timedelta
from importlib.resources import files

import inngest
import pytest
from fastapi.testclient import TestClient
from inngest.experimental import mocked
from revenue_integrity.billing_contracts import BillingInput
from revenue_integrity.console_api import create_app, wire
from revenue_integrity.console_auth import password_hash, password_matches
from revenue_integrity.console_contracts import Principal, Submission, Wake
from revenue_integrity.console_service import ConsoleService, action_digest, finding
from revenue_integrity.events import EventHandlers, build_functions, event_for
from revenue_integrity.operation_contracts import (
    BusinessReview,
    Proposal,
    Receipt,
    RevenueRecord,
)

NOW = datetime(2026, 10, 21, tzinfo=UTC)
ORIGIN = "http://127.0.0.1:8876"


def actor(role="operator", tenant="invented"):
    return Principal(
        username=role + "-user",
        tenant_id=tenant,
        actor_id=role,
        role=role,
        invoice_ids=("invoice",),
        account_ids=("account", "target"),
    )


def record(amount=9000, price=5000):
    source = BillingInput.model_validate_json(
        json.dumps(
            dict(
                case_id="invoice",
                tenant_id="invented",
                account_id="account",
                subscription_id="subscription",
                period_start="2026-01-01",
                period_end="2026-02-01",
                terms=dict(start="2026-01-01", seats=2, unit_price_minor=price),
                invoice=dict(amount_minor=amount),
            )
        )
    )
    return RevenueRecord(
        tenant_id="invented",
        resource_id="invoice",
        kind="invoice",
        amount_minor=amount,
        account_id="account",
        billing_input=source,
    )


def submission(op="operation", version=0):
    return Submission(
        operation_id=op, kind="invoice_correct", resource_id="invoice", expected_version=version
    )


class Memory:
    """A mechanism double only; Postgres durability is verified separately."""

    def __init__(self):
        self.row = record()
        self.ps = []
        self.rs = []
        self.calls = 0

    def snapshot(self, g):
        return self.records(g), self.proposals(g), self.ledger(g)

    def records(self, g):
        g.require("invented", "invoice", "invoice", "read")
        return (self.row,)

    def proposals(self, g):
        g.require("invented", "invoice", "invoice", "read")
        return tuple(self.ps)

    def ledger(self, g):
        g.require("invented", "invoice", "invoice", "read")
        return tuple(self.rs)

    def propose(self, g, c, ttl_seconds=86400):
        p = Proposal(
            command=c,
            adjustment_minor=c.invoice_amount_minor - self.row.amount_minor,
            proposer_id=g.actor_id,
            created_at=NOW,
            expires_at=NOW + timedelta(days=1),
        )
        self.ps.append(p)
        return p

    def review(self, g, op, approve):
        p = next(p for p in self.ps if p.command.business_operation_id == op)
        p = p.model_copy(
            update={"status": "approved" if approve else "rejected", "reviewer_id": g.actor_id}
        )
        self.ps = [p]
        return p

    def sweep(self, g):
        return ()

    def apply(self, g, op, run_id):
        self.calls += 1
        p = self.ps[0]
        if p.status != "approved":
            raise BusinessReview("approval_required")
        if self.rs:
            return self.rs[0]
        after = self.row.model_copy(
            update={"version": 1, "amount_minor": p.command.invoice_amount_minor}
        )
        receipt = Receipt(
            command=p.command,
            ledger_id="ledger",
            before=self.row,
            after=after,
            original_run_id=run_id,
            actor_id=g.actor_id,
            reviewer_id=p.reviewer_id,
            committed_at=NOW,
        )
        self.row = after
        self.rs.append(receipt)
        return receipt


class Auth:
    def __init__(self, user):
        self.user = user

    def login(self, u, p):
        return "invented-session-token-long-enough", "invented-csrf-token-long-enough", self.user

    def authenticate(self, token, csrf=None):
        if token != "invented-session-token-long-enough" or csrf not in (
            None,
            "invented-csrf-token-long-enough",
        ):
            raise PermissionError("denied")
        return self.user

    def logout(self, token):
        pass


def client(user=None, publish=None):
    memory = Memory()
    service = ConsoleService(memory, clock=lambda: NOW)
    auth = Auth(user or actor())
    c = TestClient(
        create_app(service, auth, origin=ORIGIN, trial_id="invented", publish=publish),
        base_url=ORIGIN,
    )
    assert (
        c.post(
            "/api/login",
            json={"username": "invented", "password": "invented password"},
            headers={"origin": ORIGIN},
        ).status_code
        == 200
    )
    headers = {"origin": ORIGIN, "x-csrf-token": "invented-csrf-token-long-enough"}
    return c, memory, service, headers


def test_password_and_principal_closed_roles():
    password = "invented password long enough"
    first, second = password_hash(password), password_hash(password)
    assert first != second and password_matches(password, first) and password not in first
    assert not password_matches(password + "x", first) and not password_matches(
        password, "malformed"
    )
    assert actor().grant().capabilities == ("read", "propose", "apply", "crm_trim")
    assert actor("reviewer").grant().capabilities == ("read", "review")


@pytest.mark.parametrize(
    "origin",
    [
        "https://example.com",
        "http://0.0.0.0:8876",
        "http://user@localhost:8876",
        "http://localhost:8876/path",
        "http://localhost:8876?x=1",
    ],
)
def test_origin_restrictions(origin):
    with pytest.raises(ValueError):
        create_app(None, None, origin=origin, trial_id="test")


def test_api_projection_csrf_role_origin_and_private_errors():
    c, memory, service, headers = client()
    data = c.get("/api/workbench").json()
    assert data["digest"]["found_minor"] == "1000"
    assert "billing_input" not in str(data) and "unit_price_minor" not in str(data)
    assert c.post("/api/proposals", json=submission().model_dump(mode="json")).status_code == 403
    assert (
        c.post(
            "/api/proposals",
            json=submission().model_dump(mode="json"),
            headers={**headers, "origin": "http://evil.invalid"},
        ).status_code
        == 403
    )
    forged = {
        **submission().model_dump(mode="json"),
        "invoice_amount_minor": 0,
        "tenant_id": "other",
    }
    response = c.post("/api/proposals", json=forged, headers=headers)
    assert response.status_code == 422 and "other" not in response.text
    response = c.post("/api/proposals", json=submission().model_dump(mode="json"), headers=headers)
    assert (
        response.status_code == 200
        and response.json()["command"]["invoice_amount_minor"] == "10000"
    )
    p = memory.ps[0]
    assert (
        c.post(
            "/api/proposals/operation/review",
            json={"decision": "approve", "action_digest": action_digest(p)},
            headers=headers,
        ).status_code
        == 403
    )
    assert c.get("/").headers["cache-control"] == "no-store"
    assert "frame-ancestors 'none'" in c.get("/").headers["content-security-policy"]
    assert (
        c.get("/assets/console.js").status_code == 200
        and c.get("/assets/unknown").status_code == 404
    )
    canary = "private-canary" * 100
    response = c.post(
        "/api/login", json={"username": "invented", "password": canary}, headers={"origin": ORIGIN}
    )
    assert response.status_code == 422 and canary not in response.text
    assert c.post("/api/login", content=b"x" * 16385).status_code == 413


def test_reviewer_exact_digest_and_relay_failure_preserve_committed_proposal():
    def broken(wake, reviewed):
        raise OSError("private relay failure canary")

    c, memory, service, headers = client(publish=broken)
    response = c.post("/api/proposals", json=submission().model_dump(mode="json"), headers=headers)
    assert response.status_code == 200 and response.json()["event_dispatch"] == "pending_recovery"
    assert len(memory.ps) == 1 and "private relay" not in response.text
    with pytest.raises(BusinessReview):
        service.review(actor("reviewer"), "operation", approve=True, digest="0" * 64)
    p = memory.ps[0]
    service.review(actor("reviewer"), "operation", approve=True, digest=action_digest(p))
    receipt = memory.apply(actor().grant(), "operation", run_id="run")
    assert memory.apply(actor().grant(), "operation", run_id="retry") == receipt
    assert service.propose(actor(), submission()) == memory.ps[0]
    with pytest.raises(BusinessReview):
        service.propose(actor(), submission(version=1))
    totals = service.workbench(actor())["digest"]
    assert (
        totals["found_minor"] == 1000
        and totals["proposed_minor"] == 1000
        and totals["approved_minor"] == 1000
        and totals["applied_minor"] == 1000
        and totals["ledger_entries"] == 1
    )
    assert service.workbench(actor())["findings"][0]["delta_minor"] == 0
    memory.ps = [memory.ps[0].model_copy(update={"status": "expired"})]
    assert service.workbench(actor())["digest"]["approved_minor"] == 1000


def test_exact_signed64_amounts_and_missing_facts_are_not_rounded():
    huge = 2**63 - 1
    payload = wire({"amount_minor": huge, "delta": -huge, "version": huge, "flag": True})
    assert payload == {
        "amount_minor": str(huge),
        "delta": str(-huge),
        "version": str(huge),
        "flag": True,
    }
    source = files("revenue_integrity").joinpath("web/console.js").read_text(encoding="utf-8")
    assert "BigInt(n)" in source and "Number.isSafeInteger" in source
    r = record().model_copy(update={"billing_input": None})
    assert finding(r).reason == "source_facts_missing" and not finding(r).eligible


def test_inngest_sdk_step_wait_and_sweep_composition_is_offline():
    memory = Memory()
    service = ConsoleService(memory, clock=lambda: NOW)
    service.propose(actor(), submission())
    handlers = EventHandlers(
        memory, lambda tenant, who: actor(), lambda: (actor(),), clock=lambda: NOW
    )
    sdk = mocked.Inngest(app_id="invented-sdk", is_production=False)
    functions = build_functions(sdk, handlers)
    wake = Wake(tenant_id="invented", actor_id="operator", operation_id="operation")
    event = event_for(wake)
    assert event.id == event_for(wake).id and event.id != event_for(wake, reviewed=True).id
    assert set(event.data) == {"tenant_id", "actor_id", "operation_id"}
    result = mocked.trigger(
        functions[0], event, sdk, step_stubs={"approval-wakeup": mocked.Timeout}
    )
    assert result.status is mocked.Status.COMPLETED and result.output == {"status": "pending"}
    p = memory.ps[0]
    service.review(actor("reviewer"), "operation", approve=True, digest=action_digest(p))
    result = mocked.trigger(functions[0], event, sdk)
    assert result.status is mocked.Status.COMPLETED and result.output == {"status": "applied"}
    result = mocked.trigger(
        functions[1], inngest.Event(name="inngest/scheduled.timer", data={}), sdk
    )
    assert result.status is mocked.Status.COMPLETED and len(memory.rs) == 1
    assert handlers.reconcile(wake, "duplicate") == {"status": "already_applied"}
    # A fabricated wakeup cannot approve a new canonical pending proposal.
    memory = Memory()
    service = ConsoleService(memory, clock=lambda: NOW)
    service.propose(actor(), submission())
    handlers = EventHandlers(
        memory, lambda tenant, who: actor(), lambda: (actor(),), clock=lambda: NOW
    )
    assert handlers.reconcile(wake, "forged") == {"status": "pending"} and memory.calls == 0
