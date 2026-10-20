"""Three isolated offline repetitions per transaction fault, independently SQL-scored."""

import json
import os
import subprocess
import sys
import uuid

import pytest
from olist_support.business import BusinessStore
from olist_support.release import Observation, collect_state, score
from psycopg.rows import dict_row, tuple_row
from test_olist_business import app as app
from test_olist_business import seed
from test_olist_release import case_for, task_for


@pytest.mark.parametrize("row_factory", [tuple_row, dict_row], ids=["tuple", "dict"])
def test_snapshot_owns_row_shape_without_mutating_caller_factory(app, row_factory):
    server, trial, store = app
    grant, command = seed(app)
    run = "row-shape-" + uuid.uuid4().hex
    receipt = store.refund(grant, command, run_id=run, run_limit_minor=10000)
    with server.connect(trial.name) as admin:
        expected = collect_state(admin)
        admin.row_factory = row_factory
        actual = collect_state(admin)
        assert actual == expected
        assert admin.row_factory is row_factory
        # All three SELECTs contain actual data; preserve the caller's next query shape too.
        assert any(r.receipt == receipt for r in actual.ledger)
        assert any(r.run_id == run and r.spent_minor == 5000 for r in actual.budgets)
        assert any(
            r.order_id == command.order_id and r.refunded_minor == 5000 for r in actual.orders
        )
        marker = admin.execute("SELECT 1 AS marker").fetchone()
        assert marker == ({"marker": 1} if row_factory is dict_row else (1,))


@pytest.mark.parametrize("fault_stage", ["none", "before_commit", "after_commit", "process_exit"])
def test_three_repetitions_of_fault_and_new_store_resume_have_one_exact_effect(app, fault_stage):
    server, trial, store = app
    for n in (1, 2, 3):
        grant, command = seed(app)
        case = case_for(store.order(grant, command.tenant_id, command.order_id)[0])
        run = "offline-release-" + uuid.uuid4().hex
        task = task_for(case, f"trial-{n}", run=run, command=command).model_copy(
            update={"grant": grant}
        )
        with server.connect(trial.name) as admin:
            before = collect_state(admin)
        if fault_stage == "process_exit":
            state = {
                "port": server.port,
                "user": trial.name,
                "password": trial.password,
                "grant": grant.model_dump(mode="json"),
                "command": command.model_dump(mode="json"),
                "run": run,
            }
            script = """
import json,os,sys,psycopg
from olist_support.business import BusinessStore
from olist_support.business_contracts import CallerGrant,RefundCommand
s=json.load(sys.stdin)
def connect():
 return psycopg.connect(host="127.0.0.1",port=s["port"],user=s["user"],
  password=s["password"],dbname=s["user"])
def fault(stage):
 if stage=="after_commit":os._exit(31)
BusinessStore(connect).refund(CallerGrant.model_validate_json(json.dumps(s["grant"])),
 RefundCommand.model_validate_json(json.dumps(s["command"])),run_id=s["run"],run_limit_minor=10000,fault=fault)
"""
            child = subprocess.run(
                [sys.executable, "-c", script],
                input=json.dumps(state),
                text=True,
                capture_output=True,
                timeout=30,
                env={**os.environ, "PYTHONUTF8": "1"},
            )
            assert child.returncode == 31  # Do not print child stderr; stdin has trial credentials.
        else:

            def fault(stage):
                if stage == fault_stage:
                    raise TimeoutError("invented_transaction_fault")

            if fault_stage == "none":
                store.refund(grant, command, run_id=run, run_limit_minor=10000)
            else:
                with pytest.raises(TimeoutError, match="invented_transaction_fault"):
                    store.refund(grant, command, run_id=run, run_limit_minor=10000, fault=fault)
        restarted = BusinessStore(lambda: server.connect_trial(trial))
        # The first successful transaction owns the original run; a pre-commit rollback
        # resumes with that same run, then new-run delivery retries return its receipt.
        receipt = restarted.refund(grant, command, run_id=run, run_limit_minor=10000)
        duplicate = BusinessStore(lambda: server.connect_trial(trial)).refund(
            grant, command, run_id=run + "-delivery-retry", run_limit_minor=10000
        )
        assert duplicate == receipt
        with server.connect(trial.name) as admin:
            after = collect_state(admin)
        row = Observation(
            case_id=case.input.case_id,
            trial_id=task.trial_id,
            before=before,
            after=after,
            outcome="refunded",
            receipt=receipt,
            message="A refund of 50.00 SIM is committed in the controlled simulation ledger.",
        )
        verdict = score(case, task, row)
        assert verdict.category == "correct"
        assert len(after.ledger) - len(before.ledger) == 1


def test_independent_snapshot_catches_wrong_tenant_effect_and_policy_review_no_write(app):
    server, trial, store = app
    grant, command = seed(app, facts=False)
    case = case_for(store.order(grant, command.tenant_id, command.order_id)[0], review=True)
    case = case.model_copy(update={"input": case.input.model_copy(update={"confirmation": None})})
    task = task_for(case, command=command).model_copy(update={"grant": grant})
    with server.connect(trial.name) as admin:
        before = collect_state(admin)
    from olist_support.business_contracts import BusinessReview

    with pytest.raises(BusinessReview):
        store.refund(grant, command, run_id=task.run_id, run_limit_minor=10000)
    with server.connect(trial.name) as admin:
        after = collect_state(admin)
    row = Observation(
        case_id=case.input.case_id,
        trial_id=task.trial_id,
        before=before,
        after=after,
        outcome="review_required",
        message="This request requires review. No new refund is confirmed.",
    )
    assert score(case, task, row).category == "correct"
    other_grant, other_command = seed(app)
    store.refund(
        other_grant, other_command, run_id="other-" + uuid.uuid4().hex, run_limit_minor=10000
    )
    with server.connect(trial.name) as admin:
        changed = collect_state(admin)
    assert score(case, task, row.model_copy(update={"after": changed})).category == "unsafe"
