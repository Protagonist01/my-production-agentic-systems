"""Bound SIM authorization/correction/reconstruction/compensation with actual SQL."""

import pytest
from agent_harness.offline_example import example_context
from revenue_integrity.operations import OperationStore
from revenue_integrity.state_evidence import InvoiceEvidence, InvoiceExpectation, collect_operations
from revenue_integrity.study_evidence import (
    DenialObservation,
    EffectTrial,
    TrialBinding,
    assess_effects,
)
from test_revenue_operations import app as app
from test_revenue_operations import approved, seed, undo


def test_candidate_trial_bound_effects_reject_wrong_scope_and_mutated_denials_or_undo(app):
    server, trial, _ = app
    store, operator, reviewer, command = approved(seed(app))
    context = example_context("invented", "b" * 64).model_copy(
        update={
            "agent_id": "revenue",
            "tenant_id": operator.tenant_id,
            "case_id": command.resource_id,
            "run_id": "bound-revenue-trial",
        }
    )
    binding = TrialBinding(candidate_sha256="a" * 64, context=context)

    def observe():
        with server.connect_trial(trial) as c:
            return collect_operations(c)

    before = observe()
    denials = []
    for kind, action in (
        (
            "wrong_tenant",
            lambda: store.propose(operator.model_copy(update={"tenant_id": "other"}), command),
        ),
        (
            "missing_capability",
            lambda: store.apply(reviewer, command.business_operation_id, run_id="denied"),
        ),
        (
            "self_review",
            lambda: store.review(
                reviewer.model_copy(update={"actor_id": operator.actor_id}),
                command.business_operation_id,
                approve=True,
            ),
        ),
    ):
        start = observe()
        with pytest.raises(PermissionError):
            action()
        denials.append(DenialObservation(kind=kind, rejected=True, before=start, after=observe()))
    receipt = store.apply(operator, command.business_operation_id, run_id=context.run_id)
    after = observe()
    rebuilt = OperationStore(lambda: server.connect_trial(trial))
    restarted = observe()
    duplicate = rebuilt.apply(operator, command.business_operation_id, run_id="redelivery")
    invoice = InvoiceEvidence(
        before=before,
        after=after,
        restarted=restarted,
        duplicate=observe(),
        result=receipt,
        duplicate_result=duplicate,
    )
    expected = InvoiceExpectation(
        command=command,
        operator=operator,
        reviewer_id=reviewer.actor_id,
        run_id=context.run_id,
        expected_amount_minor=10000,
    )
    compensation = undo(receipt)
    rebuilt.propose(operator, compensation)
    rebuilt.review(reviewer, compensation.business_operation_id, approve=True)
    undo_before = observe()
    undo_receipt = rebuilt.apply(
        operator, compensation.business_operation_id, run_id=context.run_id + "-compensate"
    )
    undo_after = observe()
    undo_duplicate = OperationStore(lambda: server.connect_trial(trial)).apply(
        operator, compensation.business_operation_id, run_id="undo-redelivery"
    )
    assert observe() == undo_after
    evidence = EffectTrial(
        binding=binding,
        invoice=invoice,
        expected=expected,
        denials=tuple(denials),
        compensation_before=undo_before,
        compensation_after=undo_after,
        compensation_result=undo_receipt,
        compensation_duplicate=undo_duplicate,
    )
    report = assess_effects(evidence, binding)
    assert (
        report["complete"]
        and report["passed"] == 4
        and report["failed"] == 0
        and not report["release_allowed"]
    )
    for altered in (
        evidence.model_copy(update={"denials": ()}),
        evidence.model_copy(update={"compensation_after": undo_before}),
        evidence.model_copy(
            update={"compensation_result": undo_receipt.model_copy(update={"ledger_id": "wrong"})}
        ),
        evidence.model_copy(update={"compensation_duplicate": receipt}),
    ):
        assert assess_effects(altered, binding)["failed"] > 0
    assert (
        assess_effects(evidence.model_copy(update={"compensation_result": None}), binding)[
            "unobserved"
        ]
        == 1
    )
    with pytest.raises(ValueError, match="scope"):
        assess_effects(evidence, binding.model_copy(update={"candidate_sha256": "c" * 64}))
