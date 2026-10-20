"""Required real Postgres O4/O5 transactions, races and process-crash recovery."""

import json
import os
import shutil
import subprocess
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import psycopg
import pytest
from agent_harness.local_services import Workspace
from agent_harness.postgres import drop_trial
from olist_support.business import BusinessStore, enroll, setup
from olist_support.business_contracts import BusinessReview, CallerGrant, RefundCommand
from olist_support.workflow import FixedPlanner, IntentPlan, SupportWorkflow, WorkflowRequest
from olist_support.workflow_postgres import saver, setup_checkpoints
from test_olist_policy import confirmation, invented_view
from test_olist_workflow import context

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    if shutil.which("docker") is None:
        pytest.fail("Docker is required; Olist database acceptance cannot be skipped")
    root = tmp_path_factory.mktemp("olist backend workspace")
    shutil.copyfile(ROOT / "compose.yaml", root / "compose.yaml")
    workspace = Workspace(root)
    workspace.config(initialize=True)
    workspace.up()
    server, trial = workspace.server(), workspace.create("olist-o4-o5-acceptance")
    try:
        with server.connect(trial.name) as admin:
            setup(admin, trial.name)
        with server.connect(trial.name) as admin:
            setup_checkpoints(admin, trial.name)
        yield server, trial, BusinessStore(lambda: server.connect_trial(trial))
    finally:
        drop_trial(server, trial)
        workspace.down(destroy=True)


def seed(app, amount=5000, *, facts=True, **changes):
    server, trial, store = app
    tenant, order = "invented-tenant", "order-" + uuid.uuid4().hex
    view = invented_view(amount, order_id=order, **changes)
    proof = confirmation(order_id=order) if facts else None
    with server.connect(trial.name) as admin:
        enroll(admin, view, proof)
    grant = CallerGrant(
        tenant_id=tenant,
        actor_id="invented-actor",
        order_ids=(order,),
        capabilities=("read", "refund"),
    )
    command = RefundCommand(
        tenant_id=tenant,
        business_operation_id="op-" + uuid.uuid4().hex,
        order_id=order,
        amount_minor=amount,
        expected_version=0,
    )
    return grant, command


def observed(app, command):
    server, trial, _ = app
    with server.connect(trial.name) as admin:
        row = admin.execute(
            "SELECT refunded_minor,version FROM olist.orders WHERE tenant_id=%s AND order_id=%s",
            (command.tenant_id, command.order_id),
        ).fetchone()
        n = admin.execute(
            (
                "SELECT count(*),coalesce(sum(amount_minor),0) FROM olist.refunds "
                "WHERE tenant_id=%s AND order_id=%s"
            ),
            (command.tenant_id, command.order_id),
        ).fetchone()
        return row, n


def test_refund_commits_once_and_duplicate_new_run_returns_original_audit(app):
    grant, command = seed(app)
    store = app[2]
    run = "run-" + uuid.uuid4().hex
    first = store.refund(grant, command, run_id=run, run_limit_minor=10000)
    retry = store.refund(grant, command, run_id=run + "-new", run_limit_minor=10000)
    assert retry == first and retry.original_run_id == run and retry.actor_id == grant.actor_id
    assert observed(app, command) == ((5000, 1), (1, 5000))
    assert store.verify_receipt(grant, first)
    assert store.order(grant, command.tenant_id, command.order_id)[0].currency_unit is None


def test_unauthorized_and_mismatched_repeated_payload_cannot_read_or_write(app):
    grant, command = seed(app)
    store = app[2]
    first = store.refund(grant, command, run_id=uuid.uuid4().hex, run_limit_minor=10000)
    for bad in (
        grant.model_copy(update={"tenant_id": "other"}),
        grant.model_copy(update={"capabilities": ("read",)}),
        grant.model_copy(update={"order_ids": ()}),
    ):
        with pytest.raises(PermissionError):
            store.refund(bad, command, run_id=uuid.uuid4().hex, run_limit_minor=10000)
    with pytest.raises(BusinessReview, match="payload_mismatch"):
        store.refund(
            grant,
            command.model_copy(update={"amount_minor": 4999}),
            run_id=uuid.uuid4().hex,
            run_limit_minor=10000,
        )
    assert observed(app, command) == ((5000, 1), (1, 5000)) and store.verify_receipt(grant, first)


def test_missing_conflicting_facts_stale_versions_and_partial_request_do_not_write(app):
    for changes, facts in (({}, False), ({"final_source_status": "delivered"}, True), ({}, True)):
        grant, command = seed(app, facts=facts, **changes)
        if facts and not changes:
            command = command.model_copy(update={"expected_version": 1})
        with pytest.raises(BusinessReview):
            app[2].refund(grant, command, run_id=uuid.uuid4().hex, run_limit_minor=10000)
        assert observed(app, command) == ((0, 0), (0, 0))
    grant, command = seed(app)
    with pytest.raises(BusinessReview, match="full_payment"):
        app[2].refund(
            grant,
            command.model_copy(update={"amount_minor": 1000}),
            run_id=uuid.uuid4().hex,
            run_limit_minor=10000,
        )
    assert observed(app, command) == ((0, 0), (0, 0))


def test_concurrent_different_orders_cannot_overspend_one_run(app):
    pairs = [seed(app), seed(app)]
    run = uuid.uuid4().hex

    def execute(pair):
        grant, command = pair
        try:
            return app[2].refund(grant, command, run_id=run, run_limit_minor=5000)
        except BusinessReview:
            return None

    with ThreadPoolExecutor(max_workers=6) as pool:
        rows = list(pool.map(execute, pairs * 3))
    assert sum(x is not None for x in rows) == 3
    assert sum(observed(app, c)[1][0] for _, c in pairs) == 1
    server, trial, _ = app
    with server.connect(trial.name) as admin:
        assert admin.execute(
            (
                "SELECT spent_minor,limit_minor FROM olist.run_budgets "
                "WHERE tenant_id=%s AND run_id=%s"
            ),
            (pairs[0][1].tenant_id, run),
        ).fetchone() == (5000, 5000)
    remaining = next(pair for pair in pairs if observed(app, pair[1])[0][0] == 0)
    with pytest.raises(BusinessReview, match="configuration_changed"):
        app[2].refund(*remaining, run_id=run, run_limit_minor=10000)


def test_concurrent_new_operations_cannot_refund_same_order_twice(app):
    grant, command = seed(app)

    def execute(i):
        try:
            return app[2].refund(
                grant,
                command.model_copy(update={"business_operation_id": str(i)}),
                run_id=uuid.uuid4().hex,
                run_limit_minor=10000,
            )
        except BusinessReview:
            return None

    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(execute, range(4)))
    assert sum(r is not None for r in rows) == 1
    assert observed(app, command) == ((5000, 1), (1, 5000))


def test_transaction_failure_rolls_back_and_commit_timeout_retries_original(app):
    grant, command = seed(app)

    def before(stage):
        if stage == "before_commit":
            raise RuntimeError("invented transaction failure")

    with pytest.raises(RuntimeError):
        app[2].refund(grant, command, run_id=uuid.uuid4().hex, run_limit_minor=10000, fault=before)
    assert observed(app, command) == ((0, 0), (0, 0))

    def after(stage):
        if stage == "after_commit":
            raise TimeoutError("invented timeout after commit")

    with pytest.raises(TimeoutError):
        app[2].refund(grant, command, run_id=uuid.uuid4().hex, run_limit_minor=10000, fault=after)
    assert observed(app, command) == ((5000, 1), (1, 5000))
    assert (
        app[2].refund(grant, command, run_id=uuid.uuid4().hex, run_limit_minor=10000).amount_minor
        == 5000
    )
    assert observed(app, command) == ((5000, 1), (1, 5000))


def test_runtime_cannot_rewrite_append_only_ledger_or_create_schema(app):
    server, trial, _ = app
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with server.connect_trial(trial) as connection:
            connection.execute("DELETE FROM olist.refunds")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with server.connect_trial(trial) as connection:
            connection.execute("CREATE TABLE olist.not_allowed(x integer)")


def test_postgres_graph_status_review_and_completed_resume(app):
    server, trial, store = app
    for intent, outcome in (
        ("status", "status"),
        ("reship", "review_required"),
        ("refund", "refunded"),
    ):
        grant, command = seed(app)
        c = context(event=uuid.uuid4().hex, run=uuid.uuid4().hex)
        request = WorkflowRequest(order_id=command.order_id, text="Invented support request.")
        with saver(lambda: server.connect_trial(trial)) as checkpoints:
            result = SupportWorkflow(store, FixedPlanner(IntentPlan(intent=intent))).run(
                c, request, grant, checkpoints, run_limit_minor=10000
            )
        assert result.outcome == outcome
        with saver(lambda: server.connect_trial(trial)) as checkpoints:
            again = SupportWorkflow(store, FixedPlanner(IntentPlan(intent="review"))).run(
                c.model_copy(update={"run_id": "new-run"}),
                request,
                grant,
                checkpoints,
                run_limit_minor=10000,
            )
        assert again == result
        assert observed(app, command)[1][0] == (1 if intent == "refund" else 0)


def test_owned_process_hard_exit_after_commit_resumes_without_duplicate_effect(app):
    server, trial, store = app
    grant, command = seed(app)
    c = context(event=uuid.uuid4().hex, run=uuid.uuid4().hex)
    request = WorkflowRequest(order_id=command.order_id, text="Invented crash-recovery request.")
    state = {
        "port": server.port,
        "user": trial.name,
        "password": trial.password,
        "context": c.model_dump(mode="json"),
        "request": request.model_dump(mode="json"),
        "grant": grant.model_dump(mode="json"),
    }
    script = """import json,sys,os,psycopg
from agent_harness.contracts import RunContext
from olist_support.business import BusinessStore
from olist_support.business_contracts import CallerGrant
from olist_support.workflow import SupportWorkflow,FixedPlanner,IntentPlan,WorkflowRequest
from olist_support.workflow_postgres import saver
s=json.load(sys.stdin)
def connect():
 return psycopg.connect(host="127.0.0.1",port=s["port"],user=s["user"],
  password=s["password"],dbname=s["user"])
def fault(stage):
 if stage=="after_commit":os._exit(23)
with saver(connect) as checkpoints:
 SupportWorkflow(BusinessStore(connect),FixedPlanner(IntentPlan(intent="refund"))).run(
  RunContext.model_validate_json(json.dumps(s["context"])),
  WorkflowRequest.model_validate_json(json.dumps(s["request"])),
  CallerGrant.model_validate_json(json.dumps(s["grant"])),checkpoints,
  run_limit_minor=10000,fault=fault)
"""
    child = subprocess.run(
        [sys.executable, "-c", script],
        input=json.dumps(state),
        text=True,
        capture_output=True,
        timeout=60,
        env=os.environ.copy(),
    )
    assert child.returncode == 23, "owned crash drill did not reach the after-commit point"
    assert observed(app, command) == ((5000, 1), (1, 5000))
    with saver(lambda: server.connect_trial(trial)) as checkpoints:
        recovered = SupportWorkflow(store, FixedPlanner(IntentPlan(intent="review"))).run(
            c.model_copy(update={"run_id": "recovery-run"}),
            request,
            grant,
            checkpoints,
            run_limit_minor=10000,
        )
    assert recovered.outcome == "refunded" and recovered.receipt.original_run_id == c.run_id
    assert observed(app, command) == ((5000, 1), (1, 5000))


def test_receipt_and_source_tampering_do_not_become_verified_success(app):
    server, trial, store = app
    grant, command = seed(app)
    receipt = store.refund(grant, command, run_id=uuid.uuid4().hex, run_limit_minor=10000)
    assert not store.verify_receipt(grant, receipt.model_copy(update={"amount_minor": 4999}))
    with server.connect(trial.name) as admin:
        admin.execute(
            "UPDATE olist.refunds SET amount_minor=4999 WHERE tenant_id=%s AND operation_id=%s",
            (command.tenant_id, command.business_operation_id),
        )
    assert not store.verify_receipt(grant, receipt)
    grant, command = seed(app)
    with server.connect(trial.name) as admin:
        admin.execute(
            "UPDATE olist.orders SET source_pin=%s WHERE tenant_id=%s AND order_id=%s",
            ("wrong-pin", command.tenant_id, command.order_id),
        )
    with pytest.raises(ValueError, match="stored pin"):
        store.refund(grant, command, run_id=uuid.uuid4().hex, run_limit_minor=10000)
    assert observed(app, command) == ((0, 0), (0, 0))


def test_operator_cli_claims_new_private_output_before_refund(app, tmp_path, monkeypatch, capsys):
    from types import SimpleNamespace

    from olist_support import business_cli

    server, trial, _ = app
    grant, command = seed(app)
    c = context(event=uuid.uuid4().hex, run=uuid.uuid4().hex)
    request = WorkflowRequest(order_id=command.order_id, text="Invented private request canary.")
    for name, value in (("context", c), ("request", request), ("grant", grant)):
        (tmp_path / (name + ".json")).write_text(value.canonical_json(), encoding="utf-8")
    monkeypatch.setattr(
        business_cli,
        "Workspace",
        lambda root: SimpleNamespace(load_trial=lambda identity: trial, server=lambda: server),
    )

    def arguments(output):
        return [
            "olist-operator",
            "--root",
            str(ROOT),
            "--trial",
            "invented",
            "run",
            "--context",
            str(tmp_path / "context.json"),
            "--request",
            str(tmp_path / "request.json"),
            "--grant",
            str(tmp_path / "grant.json"),
            "--intent",
            "refund",
            "--run-limit-minor",
            "10000",
            "--output",
            str(output),
        ]

    existing = tmp_path / "existing.json"
    existing.write_text("sentinel", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", arguments(existing))
    with pytest.raises(SystemExit) as error:
        business_cli.main()
    assert error.value.code == 2 and existing.read_text(encoding="utf-8") == "sentinel"
    assert observed(app, command) == ((0, 0), (0, 0))
    output = tmp_path / "result.json"
    monkeypatch.setattr(sys, "argv", arguments(output))
    business_cli.main()
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["outcome"] == "refunded" and result["receipt"]["amount_minor"] == 5000
    assert observed(app, command) == ((5000, 1), (1, 5000))
    captured = capsys.readouterr()
    assert "Invented private request canary" not in captured.out + captured.err
