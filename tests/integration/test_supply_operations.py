"""Actual SQL concurrency, exact approvals, crashes and bounded graph recovery."""

import os
import shutil
import subprocess
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path

import inngest
import psycopg
import pytest
from agent_harness.local_services import Workspace
from agent_harness.postgres import drop_trial
from inngest.experimental import mocked
from psycopg.types.json import Jsonb
from supply_chain.action_contracts import Command, Grant, ReviewRequired
from supply_chain.events import EventHandlers, IncidentWake, build_functions, event_for
from supply_chain.operations import OperationStore, enroll, setup
from supply_chain.simulator import NOW
from supply_chain.workflow import SupplyWorkflow
from test_supply_simulator import fact

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    root = tmp_path_factory.mktemp("supply-operations-workspace")
    shutil.copyfile(ROOT / "compose.yaml", root / "compose.yaml")
    workspace = Workspace(root)
    workspace.config(initialize=True)
    workspace.up()
    server, trial = workspace.server(), workspace.create("supply-s2-s3-s4-acceptance")
    now = [NOW]
    try:
        with server.connect(trial.name) as admin:
            setup(admin, trial.name)
        store = OperationStore(lambda: server.connect_trial(trial), clock=lambda: now[0])
        yield server, trial, store, now
    finally:
        drop_trial(server, trial)
        workspace.down(destroy=True)


def seed(app, *, count=1, delay=12, **changes):
    server, trial, store, now = app
    now[0] = NOW
    event = "incident-" + uuid.uuid4().hex
    shipments = tuple(
        fact("shipment-" + uuid.uuid4().hex, estimated_delay_hours=delay, **changes)
        for _ in range(count)
    )
    with server.connect(trial.name) as admin:
        enroll(admin, event, shipments)
    operator = Grant(
        tenant_id="invented",
        actor_id="operator",
        event_ids=(event,),
        shipment_ids=tuple(s.shipment_id for s in shipments),
        capabilities=("read", "propose", "apply"),
    )
    reviewer = operator.model_copy(
        update={"actor_id": "reviewer", "capabilities": ("read", "review")}
    )
    confirmer = operator.model_copy(
        update={"actor_id": "confirmer", "capabilities": ("read", "confirm")}
    )
    return store, operator, reviewer, confirmer, event, shipments


def command(value, action="reroute", index=0):
    store, operator, _, _, event, shipments = value
    budget, facts = store.portfolio(operator, event)
    shipment = next(s for s in facts if s.shipment_id == shipments[index].shipment_id)
    return Command(
        tenant_id=operator.tenant_id,
        event_id=event,
        shipment_id=shipment.shipment_id,
        expected_shipment_version=shipment.version,
        expected_budget_version=budget["version"],
        action=action,
    )


def approve(value, cmd):
    store, operator, reviewer, *_ = value
    proposal = store.propose(operator, cmd)
    if proposal.status == "pending":
        store.review(reviewer, cmd, proposal.payload_sha256, approve=True)
    return proposal


def test_parallel_duplicates_and_postcommit_retry_have_exactly_one_debit(app):
    value = seed(app)
    store, operator, *_ = value
    cmd = command(value)
    approve(value, cmd)
    with ThreadPoolExecutor(max_workers=3) as pool:
        receipts = list(
            pool.map(lambda run: store.apply(operator, cmd, run_id=run), ("one", "two", "three"))
        )
    assert receipts[0] == receipts[1] == receipts[2]
    assert len(store.receipts(operator, cmd.event_id)) == 1
    budget, facts = store.portfolio(operator, cmd.event_id)
    assert budget["spent_minor"] == 8000 and budget["version"] == facts[0].version == 1
    assert store.apply(operator, cmd, run_id="new-run") == receipts[0]


def test_concurrent_distinct_shipments_cannot_overspend(app):
    value = seed(app, count=2)
    server, trial, store, _ = app
    _, operator, _, _, event, _ = value
    with server.connect(trial.name) as admin:
        admin.execute(
            "UPDATE supply.budgets SET spent_minor=48000 WHERE tenant_id=%s AND event_id=%s",
            (operator.tenant_id, event),
        )
    commands = tuple(command(value, "expedite", i) for i in range(2))
    for cmd in commands:
        approve(value, cmd)

    def execute(cmd):
        try:
            return store.apply(operator, cmd, run_id="concurrent")
        except ReviewRequired as error:
            return str(error)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(execute, commands))
    assert sum(isinstance(x, str) for x in results) == 1
    assert store.portfolio(operator, event)[0]["spent_minor"] == 50000
    assert len(store.receipts(operator, event)) == 1
    with pytest.raises(ReviewRequired, match="budget_exhausted"):
        store.propose(operator, command(value, "expedite", 1 if isinstance(results[1], str) else 0))


def test_unapproved_self_review_forged_digest_and_scopes_are_denied(app):
    value = seed(app)
    store, operator, reviewer, _, _, _ = value
    cmd = command(value)
    proposal = store.propose(operator, cmd)
    with pytest.raises(ReviewRequired, match="approval_required"):
        store.apply(operator, cmd, run_id="unapproved")
    with pytest.raises(PermissionError, match="separate"):
        store.review(
            reviewer.model_copy(update={"actor_id": operator.actor_id}),
            cmd,
            proposal.payload_sha256,
            approve=True,
        )
    with pytest.raises(ReviewRequired, match="payload"):
        store.review(reviewer, cmd, "0" * 64, approve=True)
    for bad in (
        operator.model_copy(update={"tenant_id": "other"}),
        operator.model_copy(update={"event_ids": ()}),
        operator.model_copy(update={"shipment_ids": ()}),
        operator.model_copy(update={"capabilities": ("read",)}),
    ):
        with pytest.raises(PermissionError):
            store.apply(bad, cmd, run_id="denied")
    assert not store.receipts(operator, cmd.event_id)


def test_exact_payload_change_and_stale_budget_need_new_approval(app):
    value = seed(app, count=2)
    store, operator, reviewer, _, event, _ = value
    first, second = command(value, index=0), command(value, "expedite", 1)
    old = approve(value, first)
    approve(value, second)
    store.apply(operator, second, run_id="first-effect")
    with pytest.raises(ReviewRequired, match="stale"):
        store.apply(operator, first, run_id="stale")
    fresh = command(value, index=0)
    revised = store.propose(operator, fresh)
    assert revised.status == "pending" and revised.payload_sha256 != old.payload_sha256
    with pytest.raises(ReviewRequired, match="payload"):
        store.review(reviewer, fresh, old.payload_sha256, approve=True)
    store.review(reviewer, fresh, revised.payload_sha256, approve=True)
    store.apply(operator, fresh, run_id="fresh")
    assert store.portfolio(operator, event)[0]["replans"] == 1


def test_approval_expiry_and_rejection_are_safe_terminal_outcomes(app):
    for approve_decision in (None, False):
        value = seed(app)
        store, operator, reviewer, *_ = value
        cmd = command(value)
        proposal = store.propose(operator, cmd)
        if approve_decision is False:
            store.review(reviewer, cmd, proposal.payload_sha256, approve=False)
        else:
            app[3][0] = NOW + timedelta(minutes=30)
        snapshot = store.snapshot(operator, cmd)
        assert snapshot.outcome == ("expired" if approve_decision is None else "rejected")
        with pytest.raises(ReviewRequired):
            store.apply(operator, cmd, run_id="terminal")
        assert not store.receipts(operator, cmd.event_id)


def test_confirmation_early_wrong_late_duplicate_and_timeout_preserve_debit(app):
    value = seed(app)
    store, operator, _, confirmer, event, _ = value
    cmd = command(value, "expedite")
    proposal = approve(value, cmd)
    with pytest.raises(ReviewRequired, match="before_commit"):
        store.confirm(confirmer, cmd, proposal.payload_sha256, success=True)
    receipt = store.apply(operator, cmd, run_id="commit")
    with pytest.raises(ReviewRequired, match="payload"):
        store.confirm(confirmer, cmd, "0" * 64, success=True)
    app[3][0] = receipt.confirmation_deadline
    assert store.snapshot(operator, cmd).outcome == "confirmation_timeout"
    assert (
        store.confirm(confirmer, cmd, receipt.payload_sha256, success=True).outcome
        == "confirmation_timeout"
    )
    assert store.portfolio(operator, event)[0]["spent_minor"] == 2000
    assert store.apply(operator, cmd, run_id="after-timeout") == receipt


@pytest.mark.parametrize("success", [True, False])
def test_confirmation_is_durable_first_terminal_wins(app, success):
    value = seed(app)
    store, operator, _, confirmer, event, _ = value
    cmd = command(value, "expedite")
    approve(value, cmd)
    receipt = store.apply(operator, cmd, run_id="commit")
    first = store.confirm(confirmer, cmd, receipt.payload_sha256, success=success)
    second = store.confirm(confirmer, cmd, receipt.payload_sha256, success=not success)
    assert first == second
    assert first.outcome == ("confirmed" if success else "confirmation_failed")
    assert store.portfolio(operator, event)[0]["spent_minor"] == 2000


def test_postcommit_process_exit_and_recreated_store_recover_original(app, tmp_path):
    value = seed(app)
    server, trial, store, _ = app
    _, operator, *_ = value
    cmd = command(value, "expedite")
    approve(value, cmd)
    script = tmp_path / "crash.py"
    script.write_text(
        """import os, json
from datetime import datetime
import psycopg
from supply_chain.action_contracts import Command, Grant
from supply_chain.operations import OperationStore
store=OperationStore(
    lambda: psycopg.connect(os.environ["SUPPLY_CRASH_DSN"],
        password=os.environ["SUPPLY_CRASH_PASSWORD"]),
    clock=lambda: datetime.fromisoformat(os.environ["SUPPLY_CRASH_CLOCK"]))
def crash(stage):
    if stage=="after_commit": os._exit(73)
store.apply(Grant.model_validate_json(os.environ["SUPPLY_CRASH_GRANT"]),Command.model_validate_json(os.environ["SUPPLY_CRASH_COMMAND"]),run_id="crash",fault=crash)
""",
        encoding="utf-8",
    )
    with server.connect_trial(trial) as connection:
        dsn = connection.info.dsn
    result = subprocess.run(
        [sys.executable, str(script)],
        env={
            **os.environ,
            "SUPPLY_CRASH_DSN": dsn,
            "SUPPLY_CRASH_PASSWORD": trial.password,
            "SUPPLY_CRASH_CLOCK": NOW.isoformat(),
            "SUPPLY_CRASH_GRANT": operator.canonical_json(),
            "SUPPLY_CRASH_COMMAND": cmd.canonical_json(),
        },
        capture_output=True,
        timeout=60,
    )
    assert result.returncode == 73, result.stderr.decode(errors="replace")
    restarted = OperationStore(lambda: server.connect_trial(trial), clock=lambda: NOW)
    receipt = restarted.apply(operator, cmd, run_id="restart")
    assert receipt.execution_run_id == "crash"
    assert len(restarted.receipts(operator, cmd.event_id)) == 1


def test_beforecommit_failure_rolls_back_budget_state_and_ledger(app):
    value = seed(app)
    store, operator, *_ = value
    cmd = command(value, "expedite")
    approve(value, cmd)

    def fail(stage):
        if stage == "before_commit":
            raise TimeoutError("invented precommit timeout")

    with pytest.raises(TimeoutError):
        store.apply(operator, cmd, run_id="rollback", fault=fail)
    budget, facts = store.portfolio(operator, cmd.event_id)
    assert budget["spent_minor"] == budget["version"] == facts[0].version == 0
    assert not store.receipts(operator, cmd.event_id)


@pytest.mark.parametrize(
    "changes", [dict(facts_complete=False), dict(alert_conflict=True), dict(capacity=0)]
)
def test_ineligible_or_unavailable_action_cannot_be_approved(app, changes):
    value = seed(app, **changes)
    store, operator, *_ = value
    with pytest.raises(ReviewRequired):
        store.propose(operator, command(value))
    assert not store.receipts(operator, value[4])


def test_stale_shipment_record_and_schema_or_role_tampering_fail(app):
    value = seed(app)
    server, trial, store, _ = app
    _, operator, *_ = value
    cmd = command(value, "expedite")
    approve(value, cmd)
    with server.connect(trial.name) as admin:
        row = admin.execute(
            "SELECT document FROM supply.shipments WHERE tenant_id=%s AND shipment_id=%s",
            (operator.tenant_id, cmd.shipment_id),
        ).fetchone()[0]
        row["version"] = 1
        admin.execute(
            "UPDATE supply.shipments SET version=1,document=%s "
            "WHERE tenant_id=%s AND shipment_id=%s",
            (Jsonb(row), operator.tenant_id, cmd.shipment_id),
        )
    with pytest.raises(ReviewRequired, match="stale"):
        store.apply(operator, cmd, run_id="stale-shipment")
    with server.connect_trial(trial) as connection:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            connection.execute("DELETE FROM supply.ledger")
    with server.connect(trial.name) as admin:
        setup(admin, trial.name)


def test_graph_restart_approval_confirmation_and_preserved_effects(app):
    value = seed(app)
    store, operator, reviewer, confirmer, event, _ = value
    first = SupplyWorkflow(store).run(operator, event, "graph-1")
    assert first.statuses[0].outcome == "pending" and first.spent_minor == 0
    proposal = store.current(operator, event, operator.shipment_ids[0])
    store.review(reviewer, proposal.command, proposal.payload_sha256, approve=True)
    second = SupplyWorkflow(store).run(operator, event, "graph-2")
    assert second.statuses[0].outcome == "awaiting_confirmation" and second.spent_minor == 8000
    store.confirm(confirmer, proposal.command, proposal.payload_sha256, success=True)
    third = SupplyWorkflow(store).run(operator, event, "graph-3")
    assert (
        third.statuses[0].outcome == "confirmed"
        and third.committed_operations == second.committed_operations
    )
    assert len(store.receipts(operator, event)) == 1


def test_persisted_replan_limit_survives_graph_restarts_and_preserves_prior_receipts(app):
    value = seed(app, count=4)
    store, operator, _, _, event, _ = value
    target = command(value, index=0)
    store.propose(operator, target)
    for index in range(1, 4):
        other = command(value, "expedite", index)
        approve(value, other)
        store.apply(operator, other, run_id=f"committed-{index}")
        if index < 3:
            store.propose(operator, command(value, index=0))
    result = SupplyWorkflow(store).run(operator, event, "restarted-graph")
    assert result.replans_used == 2 and result.spent_minor == 6000
    assert any(s.outcome == "replan_limit" for s in result.statuses)
    assert len(result.committed_operations) == 3


def test_inngest_real_sdk_waits_fanout_sweep_and_forged_wakeup_are_safe(app):
    value = seed(app)
    store, operator, reviewer, confirmer, event, _ = value
    wake = IncidentWake(tenant_id=operator.tenant_id, actor_id=operator.actor_id, event_id=event)
    handlers = EventHandlers(SupplyWorkflow(store), lambda tenant, actor: operator, lambda: (wake,))
    sdk = mocked.Inngest(app_id="supply-offline-sdk", is_production=False)
    functions = build_functions(sdk, handlers)
    fanout = mocked.trigger(
        functions[0], event_for(wake), sdk, step_stubs={"fanout-scoped-wakeups": ["invented"]}
    )
    assert fanout.status is mocked.Status.COMPLETED and fanout.output == {"shipments": 1}
    single = handlers.fanout(wake)[0]
    event_wake = event_for(single, "supply/shipment.requested")
    assert set(event_wake.data) == {"tenant_id", "actor_id", "event_id", "shipment_id"}
    pending = mocked.trigger(
        functions[1],
        event_wake,
        sdk,
        step_stubs={f"approval-wakeup-{i}": mocked.Timeout for i in range(3)},
    )
    assert pending.status is mocked.Status.COMPLETED and pending.output == {"status": "pending"}
    assert not store.receipts(operator, event)
    proposal = store.current(operator, event, single.shipment_id)
    store.review(reviewer, proposal.command, proposal.payload_sha256, approve=True)
    waiting = mocked.trigger(
        functions[1], event_wake, sdk, step_stubs={"confirmation-wakeup": mocked.Timeout}
    )
    assert waiting.status is mocked.Status.COMPLETED and waiting.output == {
        "status": "awaiting_confirmation"
    }
    store.confirm(confirmer, proposal.command, proposal.payload_sha256, success=True)
    sweep = mocked.trigger(
        functions[2], inngest.Event(name="inngest/scheduled.timer", data={}), sdk
    )
    assert sweep.status is mocked.Status.COMPLETED and sweep.output == {"confirmed": 1}
    assert handlers.reconcile(single) == {"status": "confirmed"}
    with pytest.raises(PermissionError):
        handlers.reconcile(single.model_copy(update={"tenant_id": "other"}))


def test_region_burst_is_bounded_deterministic_and_deduplicated(app):
    value = seed(app, count=10)
    store, operator, _, _, event, _ = value
    wake = IncidentWake(tenant_id=operator.tenant_id, actor_id=operator.actor_id, event_id=event)
    handlers = EventHandlers(SupplyWorkflow(store), lambda tenant, actor: operator, lambda: (wake,))
    first, second = handlers.fanout(wake), handlers.fanout(wake)
    assert first == second and len(first) == 10
    assert len({event_for(w, "supply/shipment.requested").id for w in first}) == 10
    for single in first:
        assert handlers.reconcile(single)["status"] == "pending"
    assert not store.receipts(operator, event)
    invalid = operator.model_copy(update={"shipment_ids": tuple("x" + str(i) for i in range(101))})
    with pytest.raises(ValueError):
        EventHandlers(SupplyWorkflow(store), lambda tenant, actor: invalid, lambda: ()).fanout(wake)
