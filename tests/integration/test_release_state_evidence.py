"""Independent private SQL snapshots for invented queue and SIM correction effects."""

import pytest
import test_cfpb_desk_state
import test_revenue_operations
from agent_harness.state_evidence import read_state, save_state
from cfpb_triage.desk_contracts import QueueCommand
from cfpb_triage.desk_store import DeskStore
from cfpb_triage.state_evidence import QueueEvidence, assess_queue, collect_queue
from revenue_integrity.operations import OperationStore
from revenue_integrity.state_evidence import (
    InvoiceEvidence,
    InvoiceExpectation,
    assess_invoice,
    collect_operations,
)
from test_cfpb_desk_state import seed as seed_queue
from test_revenue_operations import approved, seed

cfpb_app = test_cfpb_desk_state.app
revenue_app = test_revenue_operations.app


def test_review_command_state_survives_reconstruction_and_duplicate(cfpb_app, tmp_path):
    server, trial, store, now, _ = cfpb_app
    case, user = seed_queue(cfpb_app)
    command = QueueCommand(command_id="saved-review", expected_version=1, reason="expert_review")

    def observe():
        with server.connect_trial(trial) as connection:
            return collect_queue(connection, user.tenant_id, case)

    before = observe()
    assert store.enqueue(user, case, command) == 2
    after = observe()
    rebuilt = DeskStore(lambda: server.connect_trial(trial), clock=lambda: now[0])
    assert rebuilt.snapshot(user, case)["status"] == "review_queued"
    restarted = observe()
    assert rebuilt.enqueue(user, case, command) == 2
    evidence = QueueEvidence(before=before, after=after, restarted=restarted, duplicate=observe())
    root = tmp_path / "queue"
    digest = save_state(root, evidence)
    saved = read_state(root, digest, QueueEvidence)
    report = assess_queue(saved, user, case, command)
    assert report["review_command_durable"] and not report["release_allowed"]
    for change in ("source", "event", "command", "restart", "duplicate", "job"):
        if change == "source":
            value = after.model_copy(update={"source_sha256": "0" * 64})
        elif change == "event":
            value = after.model_copy(update={"events": before.events})
        elif change == "command":
            value = after.model_copy(update={"commands": ()})
        elif change == "job":
            value = after.model_copy(update={"jobs": before.jobs})
        else:
            value = before
        field = {"restart": "restarted", "duplicate": "duplicate"}.get(change, "after")
        altered = saved.model_copy(update={field: value})
        assert not assess_queue(altered, user, case, command)["review_command_durable"]
    with pytest.raises(ValueError, match="scope"):
        assess_queue(saved, user, case, command.model_copy(update={"expected_version": 2}))
    with pytest.raises(PermissionError):
        assess_queue(saved, user.model_copy(update={"role": "viewer"}), case, command)


def test_invoice_exact_delta_receipt_and_duplicate_are_independently_recomputed(
    revenue_app, tmp_path
):
    server, trial, _ = revenue_app
    store, operator, reviewer, command = approved(seed(revenue_app))

    def observe():
        with server.connect_trial(trial) as connection:
            return collect_operations(connection)

    before = observe()
    result = store.apply(operator, command.business_operation_id, run_id="saved-correction")
    after = observe()
    rebuilt = OperationStore(lambda: server.connect_trial(trial))
    assert rebuilt.ledger(operator) == (result,)
    restarted = observe()
    duplicate = rebuilt.apply(operator, command.business_operation_id, run_id="redelivery")
    evidence = InvoiceEvidence(
        before=before,
        after=after,
        restarted=restarted,
        duplicate=observe(),
        result=result,
        duplicate_result=duplicate,
    )
    expectation = InvoiceExpectation(
        command=command,
        operator=operator,
        reviewer_id=reviewer.actor_id,
        run_id="saved-correction",
        expected_amount_minor=10000,
    )
    root = tmp_path / "invoice"
    digest = save_state(root, evidence)
    saved = read_state(root, digest, InvoiceEvidence)
    assert assess_invoice(saved, expectation)["passed"]
    assert not assess_invoice(saved, expectation)["release_allowed"]
    for altered in (
        saved.model_copy(update={"after": before}),
        saved.model_copy(update={"restarted": before}),
        saved.model_copy(update={"duplicate": before}),
        saved.model_copy(update={"result": result.model_copy(update={"actor_id": "wrong"})}),
        saved.model_copy(
            update={"duplicate_result": result.model_copy(update={"original_run_id": "wrong"})}
        ),
        saved.model_copy(
            update={
                "after": after.model_copy(
                    update={
                        "records": tuple(
                            r.model_copy(update={"note": "unexpected edit"})
                            if r.kind == "account"
                            else r
                            for r in after.records
                        )
                    }
                )
            }
        ),
    ):
        assert not assess_invoice(altered, expectation)["passed"]
    with pytest.raises(ValueError, match="independent invoice"):
        assess_invoice(saved, expectation.model_copy(update={"expected_amount_minor": 9999}))
    with pytest.raises(ValueError, match="separately approved"):
        assess_invoice(saved, expectation.model_copy(update={"reviewer_id": operator.actor_id}))
    with pytest.raises(PermissionError):
        assess_invoice(
            saved,
            expectation.model_copy(
                update={"operator": operator.model_copy(update={"capabilities": ("read",)})}
            ),
        )
    # Indexed SQL columns must agree with the saved JSON document as well.
    with server.connect(trial.name) as admin:
        admin.execute(
            "UPDATE revenue.records SET version=version+1 WHERE tenant_id=%s AND resource_id=%s",
            (command.tenant_id, command.resource_id),
        )
    with pytest.raises(ValueError, match="columns differ"):
        observe()
