"""Required actual Postgres approval, duplicate, compensation and role controls."""

import json
import os
import shutil
import subprocess
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import psycopg
import pytest
from agent_harness.local_services import Workspace
from agent_harness.postgres import drop_trial
from psycopg.types.json import Jsonb
from revenue_integrity.billing_contracts import BillingInput
from revenue_integrity.operation_contracts import (
    BusinessReview,
    ChangeCommand,
    RevenueGrant,
    RevenueRecord,
)
from revenue_integrity.operations import OperationStore, enroll, setup

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    if shutil.which("docker") is None:
        pytest.fail("Docker is required for Revenue acceptance")
    root = tmp_path_factory.mktemp("revenue-operations-workspace")
    shutil.copyfile(ROOT / "compose.yaml", root / "compose.yaml")
    workspace = Workspace(root)
    workspace.config(initialize=True)
    workspace.up()
    server, trial = workspace.server(), workspace.create("revenue-r5-acceptance")
    try:
        with server.connect(trial.name) as admin:
            setup(admin, trial.name)
        yield server, trial, OperationStore(lambda: server.connect_trial(trial))
    finally:
        drop_trial(server, trial)
        workspace.down(destroy=True)


def seed(app, *, issued=9000, price=5000, facts=True, **terms):
    server, trial, store = app
    account, target, invoice = ("invented-" + uuid.uuid4().hex for _ in range(3))
    source = BillingInput.model_validate_json(
        json.dumps(
            dict(
                case_id=invoice,
                tenant_id="invented",
                account_id=account,
                subscription_id="invented-subscription",
                period_start="2026-01-01",
                period_end="2026-02-01",
                terms=dict(start="2026-01-01", seats=2, unit_price_minor=price, **terms),
                invoice=dict(amount_minor=issued),
            )
        )
    )
    records = (
        RevenueRecord(
            tenant_id="invented", resource_id=account, kind="account", note="  internal note  "
        ),
        RevenueRecord(tenant_id="invented", resource_id=target, kind="account"),
        RevenueRecord(
            tenant_id="invented",
            resource_id=invoice,
            kind="invoice",
            amount_minor=issued,
            account_id=account,
            billing_input=source if facts else None,
        ),
    )
    with server.connect(trial.name) as admin:
        for record in records:
            enroll(admin, record)
    operator = RevenueGrant(
        tenant_id="invented",
        actor_id="operator",
        invoice_ids=(invoice,),
        account_ids=(account, target),
        capabilities=("read", "propose", "apply", "crm_trim"),
    )
    reviewer = operator.model_copy(
        update={"actor_id": "reviewer", "capabilities": ("read", "review")}
    )
    cmd = ChangeCommand(
        tenant_id="invented",
        business_operation_id="op-" + uuid.uuid4().hex,
        kind="invoice_correct",
        resource_id=invoice,
        expected_version=0,
        invoice_amount_minor=2 * price,
    )
    return store, operator, reviewer, cmd, records


def approved(seed_value):
    store, operator, reviewer, cmd, records = seed_value
    proposal = store.propose(operator, cmd)
    assert proposal.adjustment_minor == cmd.invoice_amount_minor - records[2].amount_minor
    store.review(reviewer, cmd.business_operation_id, approve=True)
    return store, operator, reviewer, cmd


def record(store, grant, resource):
    return next(r for r in store.records(grant) if r.resource_id == resource)


def undo(receipt):
    return ChangeCommand(
        tenant_id=receipt.command.tenant_id,
        business_operation_id="undo-" + uuid.uuid4().hex,
        kind="compensate",
        resource_id=receipt.before.resource_id,
        expected_version=receipt.after.version,
        original_operation_id=receipt.command.business_operation_id,
    )


def test_approved_r4_correction_retry_and_concurrent_duplicate_one_effect(app):
    store, operator, reviewer, cmd = approved(seed(app))
    with ThreadPoolExecutor(max_workers=2) as pool:
        receipts = list(
            pool.map(
                lambda run: store.apply(operator, cmd.business_operation_id, run_id=run),
                ("one", "two"),
            )
        )
    assert receipts[0] == receipts[1]
    assert record(store, operator, cmd.resource_id).amount_minor == 10000
    assert record(store, operator, cmd.resource_id).version == 1
    assert len(store.ledger(operator)) == 1
    assert store.apply(operator, cmd.business_operation_id, run_id="new-run") == receipts[0]
    assert store.review(reviewer, cmd.business_operation_id, approve=True).status == "approved"


def test_approval_and_self_review_and_unauthorized_writes_blocked(app):
    store, operator, reviewer, cmd, _ = seed(app)
    store.propose(operator, cmd)
    with pytest.raises(BusinessReview, match="approval_required"):
        store.apply(operator, cmd.business_operation_id, run_id="no")
    self_reviewer = reviewer.model_copy(update={"actor_id": operator.actor_id})
    with pytest.raises(PermissionError):
        store.review(self_reviewer, cmd.business_operation_id, approve=True)
    with pytest.raises(PermissionError):
        store.apply(reviewer, cmd.business_operation_id, run_id="no")
    with pytest.raises(PermissionError):
        store.propose(operator.model_copy(update={"tenant_id": "other"}), cmd)
    assert not store.ledger(operator)


@pytest.mark.parametrize(
    "mode", ["wrong_amount", "over_cap", "missing_source", "conflict", "new_key_wrong_payload"]
)
def test_reviewer_cannot_override_r4_source_facts_or_cap(app, mode):
    kwargs = (
        {"price": 15000}
        if mode == "over_cap"
        else {"facts": False}
        if mode == "missing_source"
        else {"conflicting_terms": ("ambiguous",)}
        if mode == "conflict"
        else {}
    )
    store, operator, reviewer, cmd, _ = seed(app, **kwargs)
    if mode == "wrong_amount":
        cmd = cmd.model_copy(update={"invoice_amount_minor": 9999})
    if mode == "new_key_wrong_payload":
        store.propose(operator, cmd)
        cmd = cmd.model_copy(update={"invoice_amount_minor": 9999})
    with pytest.raises(BusinessReview):
        store.propose(operator, cmd)
    assert record(store, operator, cmd.resource_id).version == 0 and not store.ledger(operator)


def test_stale_approved_payload_and_rejection_visible(app):
    store, operator, reviewer, cmd = approved(seed(app))
    server, trial, _ = app
    current = record(store, operator, cmd.resource_id)
    changed = current.model_copy(update={"version": 1})
    with server.connect(trial.name) as admin:
        admin.execute(
            "UPDATE revenue.records SET version=1,document=%s "
            "WHERE tenant_id=%s AND resource_id=%s",
            (Jsonb(changed.model_dump(mode="json")), operator.tenant_id, cmd.resource_id),
        )
    with pytest.raises(BusinessReview, match="stale_record"):
        store.apply(operator, cmd.business_operation_id, run_id="stale")
    assert not store.ledger(operator)
    store2, op2, rev2, cmd2, _ = seed(app)
    store2.propose(op2, cmd2)
    store2.review(rev2, cmd2.business_operation_id, approve=False)
    with pytest.raises(BusinessReview):
        store2.apply(op2, cmd2.business_operation_id, run_id="rejected")
    assert store2.proposals(op2)[0].status == "rejected"


def test_compensation_requires_new_approval_appends_and_cannot_repeat(app):
    store, operator, reviewer, cmd = approved(seed(app))
    first = store.apply(operator, cmd.business_operation_id, run_id="apply")
    compensation = undo(first)
    store.propose(operator, compensation)
    with pytest.raises(BusinessReview):
        store.apply(operator, compensation.business_operation_id, run_id="no-consent")
    store.review(reviewer, compensation.business_operation_id, approve=True)
    reversed_receipt = store.apply(operator, compensation.business_operation_id, run_id="undo")
    assert (
        reversed_receipt.before == first.after
        and reversed_receipt.after.amount_minor == first.before.amount_minor
    )
    assert reversed_receipt.after.version == 2 and len(store.ledger(operator)) == 2
    assert (
        store.apply(operator, compensation.business_operation_id, run_id="retry")
        == reversed_receipt
    )
    again = compensation.model_copy(
        update={"business_operation_id": "again-" + uuid.uuid4().hex, "expected_version": 2}
    )
    with pytest.raises(BusinessReview, match="already_compensated"):
        store.propose(operator, again)


def test_compensation_refuses_intervening_change_even_restored_value(app):
    store, operator, reviewer, cmd = approved(seed(app))
    receipt = store.apply(operator, cmd.business_operation_id, run_id="first")
    compensation = undo(receipt)
    store.propose(operator, compensation)
    store.review(reviewer, compensation.business_operation_id, approve=True)
    current = record(store, operator, cmd.resource_id)
    later = current.model_copy(update={"version": 2})
    server, trial, _ = app
    with server.connect(trial.name) as admin:
        admin.execute(
            "UPDATE revenue.records SET version=2,document=%s "
            "WHERE tenant_id=%s AND resource_id=%s",
            (Jsonb(later.model_dump(mode="json")), operator.tenant_id, cmd.resource_id),
        )
    with pytest.raises(BusinessReview):
        store.apply(operator, compensation.business_operation_id, run_id="unsafe-undo")
    assert record(store, operator, cmd.resource_id) == later and len(store.ledger(operator)) == 1


def test_alias_merge_preserves_invoice_and_compensation(app):
    store, operator, reviewer, _, records = seed(app)
    donor, target, invoice = records
    cmd = ChangeCommand(
        tenant_id=operator.tenant_id,
        business_operation_id="merge-" + uuid.uuid4().hex,
        kind="account_merge",
        resource_id=donor.resource_id,
        expected_version=0,
        target_account_id=target.resource_id,
        expected_target_version=0,
    )
    store.propose(operator, cmd)
    store.review(reviewer, cmd.business_operation_id, approve=True)
    merged = store.apply(operator, cmd.business_operation_id, run_id="merge")
    assert (
        merged.after.alias_to == target.resource_id
        and record(store, operator, invoice.resource_id) == invoice
    )
    comp = undo(merged)
    store.propose(operator, comp)
    store.review(reviewer, comp.business_operation_id, approve=True)
    assert (
        store.apply(operator, comp.business_operation_id, run_id="unmerge").after.alias_to is None
    )
    self_merge = cmd.model_copy(
        update={
            "business_operation_id": "self-" + uuid.uuid4().hex,
            "expected_version": 2,
            "target_account_id": donor.resource_id,
            "expected_target_version": 2,
        }
    )
    with pytest.raises(BusinessReview):
        store.propose(operator, self_merge)


def test_only_surrounding_note_trim_automatic_and_approved_undo(app):
    store, operator, reviewer, invoice, records = seed(app)
    account = records[0]
    cmd = ChangeCommand(
        tenant_id=operator.tenant_id,
        business_operation_id="trim-" + uuid.uuid4().hex,
        kind="crm_trim",
        resource_id=account.resource_id,
        expected_version=0,
    )
    receipt = store.trim(operator, cmd, run_id="trim")
    assert receipt.after.note == "internal note" and receipt.reviewer_id is None
    assert store.trim(operator, cmd, run_id="retry") == receipt
    with pytest.raises((BusinessReview, PermissionError)):
        store.trim(operator, invoice, run_id="forbidden")
    comp = undo(receipt)
    store.propose(operator, comp)
    store.review(reviewer, comp.business_operation_id, approve=True)
    assert (
        store.apply(operator, comp.business_operation_id, run_id="untrim").after.note
        == account.note
    )


@pytest.mark.parametrize("stage", ["before_commit", "after_commit"])
def test_fault_retry_and_partial_batch_do_not_duplicate_effects(app, stage):
    first = approved(seed(app))
    second = approved(seed(app))
    store, operator, _, cmd = first
    first_receipt = store.apply(operator, cmd.business_operation_id, run_id="batch-first")
    store2, op2, _, cmd2 = second

    def fault(at):
        if at == stage:
            raise TimeoutError("invented fault")

    with pytest.raises(TimeoutError):
        store2.apply(op2, cmd2.business_operation_id, run_id="batch-second", fault=fault)
    assert store.apply(operator, cmd.business_operation_id, run_id="batch-retry") == first_receipt
    result = store2.apply(op2, cmd2.business_operation_id, run_id="batch-retry")
    assert result.after.version == 1 and len(store2.ledger(op2)) == 1


def test_expiry_owned_by_store_and_approved_retry_receipt_survives_expiry(app):
    server, trial, _ = app
    now = [datetime(2026, 1, 1, tzinfo=UTC)]
    store, operator, reviewer, cmd, _ = seed(app)
    store = OperationStore(lambda: server.connect_trial(trial), clock=lambda: now[0])
    store.propose(operator, cmd, ttl_seconds=1)
    now[0] += timedelta(seconds=2)
    with pytest.raises(BusinessReview, match="expired"):
        store.review(reviewer, cmd.business_operation_id, approve=True)
    assert store.sweep(operator)[0].status == "expired" and not store.sweep(operator)
    _, op2, rev2, cmd2, _ = seed(app)
    store.propose(op2, cmd2, ttl_seconds=1)
    store.review(rev2, cmd2.business_operation_id, approve=True)
    receipt = store.apply(op2, cmd2.business_operation_id, run_id="in-time")
    now[0] += timedelta(seconds=2)
    assert store.apply(op2, cmd2.business_operation_id, run_id="late-retry") == receipt
    assert not store.sweep(op2)


def test_restricted_role_cannot_modify_ledger_schema_or_fingerprint(app):
    _, trial, store = app
    server = app[0]
    for query in (
        "DELETE FROM revenue.ledger",
        "UPDATE revenue.ledger SET document='{}'::jsonb",
        "UPDATE revenue.proposals SET command_sha256='forged'",
        "CREATE TABLE revenue.forbidden(x int)",
    ):
        with server.connect_trial(trial) as connection:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                connection.execute(query)
    with server.connect(trial.name) as admin:
        setup(admin, trial.name)


def test_scoped_reads_hide_other_records_proposals_and_ledger(app):
    store, operator, reviewer, cmd = approved(seed(app))
    store.apply(operator, cmd.business_operation_id, run_id="one")
    empty = operator.model_copy(update={"invoice_ids": (), "account_ids": ()})
    assert store.records(empty) == store.proposals(empty) == store.ledger(empty) == ()
    foreign = operator.model_copy(update={"tenant_id": "other"})
    assert store.records(foreign) == store.proposals(foreign) == store.ledger(foreign) == ()


def test_real_process_exit_after_commit_returns_original_receipt(app):
    store, operator, _, command = approved(seed(app))
    server, trial, _ = app
    script = """
import json,os,psycopg
from revenue_integrity.operation_contracts import RevenueGrant
from revenue_integrity.operations import OperationStore
grant=RevenueGrant.model_validate_json(os.environ['REVENUE_TEST_GRANT'])
connection=json.loads(os.environ['REVENUE_TEST_CONNECTION'])
store=OperationStore(lambda:psycopg.connect(**connection))
def exit_after_commit(stage):
    if stage=='after_commit':os._exit(72)
store.apply(grant,os.environ['REVENUE_TEST_OPERATION'],run_id='exited-process',fault=exit_after_commit)
"""
    environment = os.environ.copy()
    environment["REVENUE_TEST_GRANT"] = operator.canonical_json()
    environment["REVENUE_TEST_OPERATION"] = command.business_operation_id
    environment["REVENUE_TEST_CONNECTION"] = json.dumps(
        dict(
            host="127.0.0.1",
            port=server.port,
            user=trial.name,
            password=trial.password,
            dbname=trial.name,
            connect_timeout=5,
        )
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        env=environment,
        capture_output=True,
        timeout=60,
    )
    assert result.returncode == 72
    receipt = store.apply(operator, command.business_operation_id, run_id="restart")
    assert receipt.original_run_id == "exited-process"
    assert receipt.after.version == 1 and len(store.ledger(operator)) == 1


def test_absolute_adjustment_cap_allows_large_resulting_total_but_no_override(app):
    store, operator, _, command = approved(seed(app, issued=20000, price=15000))
    receipt = store.apply(operator, command.business_operation_id, run_id="at-cap")
    assert receipt.after.amount_minor == 30000
    assert receipt.after.amount_minor - receipt.before.amount_minor == 10000
    store, operator, _, command, _ = seed(app, issued=19999, price=15000)
    with pytest.raises(BusinessReview, match="correction_cap_exceeded"):
        store.propose(operator, command)


def test_saved_account_proposal_and_compensation_enforce_actual_resource_kind(app):
    store, operator, reviewer, _, records = seed(app)
    donor, target, _ = records
    command = ChangeCommand(
        tenant_id=operator.tenant_id,
        business_operation_id="kind-" + uuid.uuid4().hex,
        kind="account_merge",
        resource_id=donor.resource_id,
        expected_version=0,
        target_account_id=target.resource_id,
        expected_target_version=0,
    )
    store.propose(operator, command)
    store.review(reviewer, command.business_operation_id, approve=True)
    wrong_operator = operator.model_copy(
        update={
            "invoice_ids": (*operator.invoice_ids, donor.resource_id),
            "account_ids": (target.resource_id,),
        }
    )
    wrong_reviewer = reviewer.model_copy(
        update={
            "invoice_ids": (*reviewer.invoice_ids, donor.resource_id),
            "account_ids": (target.resource_id,),
        }
    )
    with pytest.raises(PermissionError):
        store.propose(wrong_operator, command)
    with pytest.raises(PermissionError):
        store.review(wrong_reviewer, command.business_operation_id, approve=True)
    assert store.proposals(wrong_operator) == ()
    receipt = store.apply(operator, command.business_operation_id, run_id="kind-merge")
    compensation = undo(receipt)
    store.propose(operator, compensation)
    store.review(reviewer, compensation.business_operation_id, approve=True)
    with pytest.raises(PermissionError):
        store.propose(wrong_operator, compensation)
    with pytest.raises(PermissionError):
        store.review(wrong_reviewer, compensation.business_operation_id, approve=True)
    assert store.proposals(wrong_reviewer) == ()


def test_workbench_snapshot_keeps_one_version_across_interleaved_commit(app):
    store, operator, _, command = approved(seed(app))
    original_reader = store._records
    committed = []

    def read_then_commit(connection, grant):
        records = original_reader(connection, grant)
        committed.append(
            store.apply(operator, command.business_operation_id, run_id="between-reads")
        )
        return records

    store._records = read_then_commit
    try:
        records, proposals, receipts = store.snapshot(operator)
    finally:
        store._records = original_reader
    assert committed[0].after.version == 1
    assert next(r for r in records if r.resource_id == command.resource_id).version == 0
    assert proposals[0].status == "approved" and receipts == ()
    records, _, receipts = store.snapshot(operator)
    assert next(r for r in records if r.resource_id == command.resource_id).version == 1
    assert receipts == (committed[0],)
    empty = operator.model_copy(update={"invoice_ids": (), "account_ids": ()})
    assert store.snapshot(empty) == ((), (), ())
    with pytest.raises(PermissionError):
        store.snapshot(operator.model_copy(update={"capabilities": ()}))
