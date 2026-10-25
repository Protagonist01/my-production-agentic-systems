"""Independent isolated-SIM invoice/ledger evidence, separate from model extraction."""

import json
from typing import Any, Literal

from agent_harness.contracts import Contract, NonEmpty
from agent_harness.release_contracts import pin, sha256
from psycopg import Connection

from revenue_integrity.operation_contracts import (
    ChangeCommand,
    Proposal,
    Receipt,
    RevenueGrant,
    RevenueRecord,
)


class OperationState(Contract):
    records: tuple[RevenueRecord, ...]
    proposals: tuple[Proposal, ...]
    ledger: tuple[Receipt, ...]


class InvoiceEvidence(Contract):
    version: Literal["revenue-sim-invoice-state-v1"] = "revenue-sim-invoice-state-v1"
    before: OperationState
    after: OperationState
    restarted: OperationState
    duplicate: OperationState
    result: Receipt
    duplicate_result: Receipt


class InvoiceExpectation(Contract):
    command: ChangeCommand
    operator: RevenueGrant
    reviewer_id: NonEmpty
    run_id: NonEmpty
    expected_amount_minor: int


def collect_operations(connection: Connection[Any]) -> OperationState:
    """Whole disposable fixture DB only. Never pass a production/shared database."""
    with connection.transaction():
        connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        rows = connection.execute(
            "SELECT tenant_id,resource_id,kind,version,document FROM revenue.records "
            "ORDER BY tenant_id,resource_id"
        ).fetchall()
        proposals = connection.execute(
            "SELECT tenant_id,operation_id,command_sha256,document FROM revenue.proposals "
            "ORDER BY tenant_id,operation_id"
        ).fetchall()
        ledger = connection.execute(
            "SELECT tenant_id,operation_id,ledger_id,original_operation_id,document "
            "FROM revenue.ledger ORDER BY tenant_id,operation_id"
        ).fetchall()
    records = []
    for tenant, resource, kind, version, document in rows:
        value = RevenueRecord.model_validate_json(json.dumps(document))
        if (tenant, resource, kind, version) != (
            value.tenant_id,
            value.resource_id,
            value.kind,
            value.version,
        ):
            raise ValueError("record columns differ from document")
        records.append(value)
    ps = []
    for tenant, operation, command_sha, document in proposals:
        proposal = Proposal.model_validate_json(json.dumps(document))
        if (tenant, operation, command_sha) != (
            proposal.command.tenant_id,
            proposal.command.business_operation_id,
            pin(proposal.command),
        ):
            raise ValueError("proposal columns differ from document")
        ps.append(proposal)
    receipts = []
    for tenant, operation, ledger_id, original, document in ledger:
        receipt = Receipt.model_validate_json(json.dumps(document))
        if (tenant, operation, ledger_id, original) != (
            receipt.command.tenant_id,
            receipt.command.business_operation_id,
            receipt.ledger_id,
            receipt.command.original_operation_id,
        ):
            raise ValueError("ledger columns differ from document")
        receipts.append(receipt)
    return OperationState(records=tuple(records), proposals=tuple(ps), ledger=tuple(receipts))


def assess_invoice(evidence: InvoiceEvidence, expected: InvoiceExpectation) -> dict[str, object]:
    evidence = InvoiceEvidence.model_validate_json(evidence.canonical_json())
    expected = InvoiceExpectation.model_validate_json(expected.canonical_json())
    cmd, operator = expected.command, expected.operator
    if cmd.kind != "invoice_correct" or cmd.invoice_amount_minor != expected.expected_amount_minor:
        raise ValueError("independent invoice expectation differs from command")
    for capability in ("read", "propose", "apply"):
        operator.require(cmd.tenant_id, "invoice", cmd.resource_id, capability)
    before = evidence.before
    target = next(
        (
            r
            for r in before.records
            if (r.tenant_id, r.resource_id) == (cmd.tenant_id, cmd.resource_id)
        ),
        None,
    )
    proposal = next((p for p in before.proposals if p.command == cmd), None)
    if (
        target is None
        or target.kind != "invoice"
        or target.amount_minor is None
        or target.version != cmd.expected_version
        or target.billing_input is None
        or proposal is None
        or proposal.status != "approved"
        or proposal.proposer_id != operator.actor_id
        or proposal.reviewer_id != expected.reviewer_id
        or expected.reviewer_id == operator.actor_id
        or any(
            r.command.tenant_id == cmd.tenant_id
            and r.command.business_operation_id == cmd.business_operation_id
            for r in before.ledger
        )
    ):
        raise ValueError("fresh separately approved invoice fixture required")
    delta = expected.expected_amount_minor - target.amount_minor
    if not delta or abs(delta) > 10000 or expected.expected_amount_minor < 0:
        raise ValueError("invoice expectation violates SIM correction cap")
    if proposal.adjustment_minor != delta:
        raise ValueError("proposal adjustment differs from independent expected amount")
    after = target.model_copy(
        update={"version": target.version + 1, "amount_minor": expected.expected_amount_minor}
    )
    receipt = evidence.result
    receipt_valid = (
        receipt.command == cmd
        and receipt.before == target
        and receipt.after == after
        and receipt.target is None
        and receipt.original_run_id == expected.run_id
        and receipt.actor_id == operator.actor_id
        and receipt.reviewer_id == expected.reviewer_id
        and receipt.ledger_id
        == sha256(json.dumps([cmd.tenant_id, cmd.business_operation_id]).encode())
        and receipt.committed_at.tzinfo is not None
        and proposal.created_at <= receipt.committed_at < proposal.expires_at
    )
    expected_state = before.model_copy(
        update={
            "records": tuple(after if r == target else r for r in before.records),
            "ledger": tuple(
                sorted(
                    (*before.ledger, receipt),
                    key=lambda r: (r.command.tenant_id, r.command.business_operation_id),
                )
            ),
        }
    )
    exact = (
        receipt_valid
        and evidence.after == evidence.restarted == evidence.duplicate == expected_state
    )
    duplicate = receipt_valid and evidence.result == evidence.duplicate_result
    return dict(
        version=evidence.version,
        evidence_sha256=pin(evidence),
        exact_fixture_delta=exact,
        receipt_and_duplicate_preserved=duplicate,
        passed=exact and duplicate,
        mechanism_only=True,
        provider_calls=0,
        release_allowed=False,
        limitations="One approved SIM invoice correction with an independent expected amount; "
        "no model quality, real revenue, compensation, authorization-probe or full recovery claim.",
    )
