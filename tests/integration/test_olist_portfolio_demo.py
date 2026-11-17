"""Actual SQL/HTTPS-origin composition with invented SDK results, never model quality."""

import json
import uuid

import pytest
from agent_harness.contracts import ModelMessage, ModelResponse, Usage
from fastapi.testclient import TestClient
from olist_support.console_api import create_app
from olist_support.console_auth import AuthStore, provision
from olist_support.console_cases import CaseStore
from test_olist_business import app as app
from test_olist_console import PASSWORD, actors, customer_confirm, observed
from test_olist_console import console as console

from olist_demo_acceptance import cases
from olist_demo_fixtures import fixture
from olist_demo_planner import DemoPlanner

ORIGIN = "https://olist-demo.example.test"


def application(store, trial, auth=None):
    return create_app(
        store,
        auth or AuthStore(store.connect),
        origin=ORIGIN,
        trial_id=trial.name,
        code_revision="invented-portfolio-composition",
        environment_lock="a" * 64,
        run_limit_minor=10000,
        allow_public_https=True,
    )


def login(client, principal):
    signed = client.post(
        "/api/login",
        json={"username": principal.username, "password": PASSWORD},
        headers={"origin": ORIGIN},
    )
    assert signed.status_code == 200
    cookies = signed.headers.get_list("set-cookie")
    assert len(cookies) == 2 and all("Secure" in c and "SameSite=strict" in c for c in cookies)
    assert "HttpOnly" in cookies[0]
    return {"origin": ORIGIN, "x-csrf-token": client.cookies[signed.json()["csrf_cookie"]]}


@pytest.mark.parametrize("intent", ["refund", "status", "reship", "unsupported"])
def test_semantic_adapter_actual_http_sql_customer_and_restart(console, intent):
    order, operator, reviewer = actors(console)
    with console[0].connect(console[1].name) as admin:
        provision(admin, operator, PASSWORD)
        provision(admin, reviewer, PASSWORD)
    calls = []

    class Gateway:
        def generate(self, ctx, wire):
            calls.append(wire)
            return ModelResponse(
                provider=wire.provider,
                model=wire.model,
                output=ModelMessage(
                    role="assistant",
                    content=json.dumps(
                        {
                            "intent": intent,
                            "amount_status": "explicit" if intent == "refund" else "not_applicable",
                            "requested_minor": 5000 if intent == "refund" else None,
                            "currency": "SIM" if intent == "refund" else "unspecified",
                            "amount_evidence": "50.00 SIM" if intent == "refund" else None,
                        }
                    ),
                ),
                usage=Usage(
                    model_calls=1, input_tokens=20, output_tokens=20, cost=None, cost_currency=None
                ),
            )

    store = CaseStore(lambda: console[0].connect_trial(console[1]), planner=DemoPlanner(Gateway()))
    body = {
        "event_key": uuid.uuid4().hex,
        "order_id": order,
        "text": "Refund exactly 50.00 SIM.",
        "intent": "refund",
        "require_review": intent == "refund",
    }
    with TestClient(application(store, console[1]), base_url=ORIGIN) as staff:
        headers = login(staff, operator)
        first = staff.post("/api/cases", json=body, headers=headers)
        assert first.status_code == 200
        assert staff.post("/api/cases", json=body, headers=headers).json() == first.json()
        assert len(calls) == 1 and calls[0].messages[-1].content == body["text"]
        case = store.detail(operator, first.json()["case_id"])[0]
        assert case.intent_decision.plan.intent == intent
        assert observed(console, case) == ((0, 0), (0, 0), 0)
    if intent == "refund":
        assert case.status == "review_required" and case.command.amount_minor == 5000
        with TestClient(application(store, console[1]), base_url=ORIGIN) as review:
            headers = login(review, reviewer)
            approved = review.post(
                f"/api/cases/{case.case_id}/decision",
                json={
                    "decision": "approve",
                    "expected_version": case.version,
                    "action_digest": case.action_digest,
                    "rationale": "Invented review.",
                },
                headers=headers,
            )
            assert approved.status_code == 200
            case = store.detail(operator, case.case_id)[0]
    # A fresh application/process uses saved state, without a planner or a new call.
    restarted = CaseStore(store.connect)
    if intent != "refund":
        assert case.command is None
        assert case.status == ("status" if intent == "status" else "review_required")
        return
    customer, confirmation = customer_confirm(restarted, case, console)
    with TestClient(application(restarted, console[1]), base_url=ORIGIN) as portal:
        headers = login(portal, customer)
        endpoint = f"/api/customer/cases/{case.case_id}/execute"
        first = portal.post(endpoint, json=confirmation.model_dump(mode="json"), headers=headers)
        assert first.status_code == 200
        assert (
            portal.post(endpoint, json=confirmation.model_dump(mode="json"), headers=headers).json()
            == first.json()
        )
        assert first.json()["status"] == "committed"
    assert observed(console, case) == ((5000, 1), (1, 5000), 1) and len(calls) == 1


def test_public_origin_keeps_host_csrf_and_transport_headers_separate(console):
    store = CaseStore(lambda: console[0].connect_trial(console[1]))
    with TestClient(application(store, console[1]), base_url=ORIGIN) as client:
        assert client.get("/health/live").headers["strict-transport-security"] == "max-age=31536000"
        assert client.get("/health/live", headers={"host": "attacker.test"}).status_code == 400
        result = client.post(
            "/api/login",
            json={"username": "invented", "password": PASSWORD},
            headers={
                "origin": "https://attacker.test",
                "x-forwarded-host": "olist-demo.example.test",
            },
        )
        assert result.status_code == 403


@pytest.mark.parametrize(
    "origin", [ORIGIN, "https://example.test/path", "https://a@b.test", "https://example.test:444"]
)
def test_public_origin_is_explicit_opt_in_and_rejects_noncanonical_values(console, origin):
    store = CaseStore(lambda: console[0].connect_trial(console[1]))
    with pytest.raises(ValueError):
        create_app(
            store,
            AuthStore(store.connect),
            origin=origin,
            trial_id=console[1].name,
            code_revision="invented",
            environment_lock="a" * 64,
            run_limit_minor=10000,
        )


def test_managed_style_bootstrap_separates_runtime_from_schema_owner(console):
    from agent_harness.postgres import Trial, create_trial, drop_trial

    from olist_demo_host import bootstrap, preflight

    server, source, _ = console
    target = Trial(source.workspace_key, "managed-host-" + uuid.uuid4().hex, uuid.uuid4().hex)
    create_trial(server, target)
    try:
        bootstrap(lambda: server.connect(target.name), target.name)
        result = preflight(lambda: server.connect_trial(target))
        assert result["ready"] and not result["public_activation_ready"]
        # Supplying the schema-owner DSN as runtime configuration must fail.
        assert not preflight(lambda: server.connect(target.name))["ready"]
        with pytest.raises(ValueError, match="empty dedicated"):
            bootstrap(lambda: server.connect(target.name), target.name)
        from psycopg import sql

        with server.connect(target.name) as admin:
            admin.execute(
                sql.SQL("GRANT pg_read_all_data TO {}").format(sql.Identifier(target.name))
            )
        assert not preflight(lambda: server.connect_trial(target))["ready"]
    finally:
        drop_trial(server, target)


@pytest.mark.parametrize("reference", cases(), ids=lambda c: c.case_id)
def test_all48_authored_fixture_paths_require_customer_authority(console, reference):
    from olist_support.business import enroll
    from olist_support.console_contracts import Principal, Submission
    from olist_support.customer_intent import CustomerIntentStore
    from test_olist_demo_study import Scripted
    from test_olist_planner_service import model_context

    order = "fictional-" + uuid.uuid4().hex
    built = fixture(reference, tenant_id="invented-tenant", order_id=order)
    with console[0].connect(console[1].name) as admin:
        enroll(admin, built.view, built.facts)
    operator = Principal(
        username="operator-" + uuid.uuid4().hex,
        actor_id="operator-" + uuid.uuid4().hex,
        tenant_id="invented-tenant",
        role="operator",
        order_ids=(order,),
    )
    gateway = Scripted()

    class ReplayGateway:
        def generate(self, context, wire):
            return gateway.generate(wire, timeout_seconds=110)

    store = CaseStore(
        lambda: console[0].connect_trial(console[1]), planner=DemoPlanner(ReplayGateway())
    )
    ctx = model_context()
    ctx = ctx.model_copy(
        update={
            "versions": ctx.versions.model_copy(
                update={
                    "data_snapshot": built.view.source_manifest_sha256,
                }
            )
        }
    )
    body = Submission(
        event_key=uuid.uuid4().hex,
        order_id=order,
        text=reference.text,
        intent="refund",
        require_review=False,
    )
    case = store.submit(operator, body, ctx, run_limit_minor=10000)
    assert case.intent_decision.plan.intent in reference.acceptable_intents
    assert observed(console, case) == ((0, 0), (0, 0), 0)
    if built.expected_new_refund_minor is None:
        assert case.command is None
        return
    assert case.command.amount_minor == built.expected_new_refund_minor
    restarted = CaseStore(store.connect)
    customer, payload = customer_confirm(restarted, case, console)
    effect = CustomerIntentStore(restarted).execute(
        customer, case.case_id, payload, run_limit_minor=10000
    )
    assert effect.result.receipt.amount_minor == built.expected_new_refund_minor
    assert (
        CustomerIntentStore(restarted).execute(
            customer, case.case_id, payload, run_limit_minor=10000
        )
        == effect
    )
    assert len(gateway.calls) == 1


def test_managed_restore_keeps_exact_receipt_and_never_overwrites_source(console):
    from agent_harness.postgres import Trial, create_trial, drop_trial
    from agent_harness.release_contracts import pin
    from test_olist_console import create_case, decide

    from olist_demo_host import preflight
    from olist_demo_recovery import capture, restore

    store, case, operator, reviewer = create_case(console)
    approved = decide(store, case, reviewer, console=console)
    committed = store.resume(reviewer, case.case_id, approved.action_digest, run_limit_minor=10000)
    assert committed.status == "committed"

    def source():
        return console[0].connect(console[1].name)

    archive = capture(
        source,
        source_identity="invented-managed-source",
        code_revision="invented-restore-proof",
        environment_lock="a" * 64,
    )
    with pytest.raises(ValueError, match="empty dedicated"):
        restore(source, console[1].name, archive, archive_sha256=pin(archive))
    server, trial, _ = console
    target = Trial(trial.workspace_key, "managed-restore-" + uuid.uuid4().hex, uuid.uuid4().hex)
    create_trial(server, target)
    try:
        result = restore(
            lambda: server.connect(target.name), target.name, archive, archive_sha256=pin(archive)
        )
        assert result["application_rows_restored"] and result["sessions_revoked"]
        assert not result["host_loss_objective_met"] and not result["model_budget_recovered"]
        restored = CaseStore(lambda: server.connect_trial(target))
        actual = restored.detail(operator, case.case_id)[0]
        assert actual.result.receipt == committed.result.receipt
        assert preflight(restored.connect)["ready"]
        with restored.connect() as connection:
            assert connection.execute("SELECT count(*) FROM olist_app.sessions").fetchone() == (0,)
    finally:
        drop_trial(server, target)
