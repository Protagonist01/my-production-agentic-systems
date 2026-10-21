"""Scoped operator projection and exact ledger-derived stage totals."""

import hashlib
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol

from agent_harness.contracts import Contract

from revenue_integrity.billing_contracts import BillingInput
from revenue_integrity.console_contracts import Principal, Submission
from revenue_integrity.operation_contracts import (
    BusinessReview,
    ChangeCommand,
    Proposal,
    Receipt,
    RevenueGrant,
    RevenueRecord,
)
from revenue_integrity.reconcile import reconcile


class Operations(Protocol):
    def snapshot(
        self, grant: RevenueGrant
    ) -> tuple[tuple[RevenueRecord, ...], tuple[Proposal, ...], tuple[Receipt, ...]]: ...
    def records(self, grant: RevenueGrant) -> tuple[RevenueRecord, ...]: ...
    def proposals(self, grant: RevenueGrant) -> tuple[Proposal, ...]: ...
    def ledger(self, grant: RevenueGrant) -> tuple[Receipt, ...]: ...
    def propose(
        self, grant: RevenueGrant, command: ChangeCommand, *, ttl_seconds: int = 86400
    ) -> Proposal: ...
    def review(self, grant: RevenueGrant, operation_id: str, *, approve: bool) -> Proposal: ...
    def apply(self, grant: RevenueGrant, operation_id: str, *, run_id: str) -> Receipt: ...
    def trim(self, grant: RevenueGrant, command: ChangeCommand, *, run_id: str) -> Receipt: ...
    def sweep(self, grant: RevenueGrant) -> tuple[Proposal, ...]: ...


class Finding(Contract):
    resource_id: str
    expected_version: int
    original_minor: int | None
    current_minor: int | None
    should_be_minor: int | None
    delta_minor: int | None
    disposition: str
    eligible: bool
    reason: str


class Digest(Contract):
    found_minor: int
    proposed_minor: int
    approved_minor: int
    applied_minor: int
    rejected_minor: int
    compensated_minor: int
    net_adjustment_minor: int
    pending_count: int
    expired_count: int
    ledger_entries: int
    unit: str = "SIM"


def action_digest(proposal: Proposal) -> str:
    return hashlib.sha256(proposal.command.canonical_json().encode()).hexdigest()


def finding(record: RevenueRecord, *, original: bool = False) -> Finding:
    if record.kind != "invoice":
        raise ValueError("invoice required")
    if record.billing_input is None:
        return Finding(
            resource_id=record.resource_id,
            expected_version=record.version,
            original_minor=None,
            current_minor=record.amount_minor,
            should_be_minor=None,
            delta_minor=None,
            disposition="review",
            eligible=False,
            reason="source_facts_missing",
        )
    data = record.billing_input.model_dump()
    if not original:
        data["invoice"] = {"schema_version": 1, "amount_minor": record.amount_minor}
    result = reconcile(BillingInput.model_validate(data))
    eligible = (
        result.disposition in ("underbilled", "overbilled")
        and result.delta_minor is not None
        and abs(result.delta_minor) <= 10000
    )
    return Finding(
        resource_id=record.resource_id,
        expected_version=record.version,
        original_minor=record.billing_input.invoice.amount_minor,
        current_minor=record.amount_minor,
        should_be_minor=result.should_be_minor,
        delta_minor=result.delta_minor,
        disposition=result.disposition,
        eligible=eligible,
        reason=(
            "adjustment_above_cap"
            if result.delta_minor is not None and abs(result.delta_minor) > 10000
            else result.reasons[0]
        ),
    )


class ConsoleService:
    def __init__(
        self, store: Operations, *, clock: Callable[[], datetime] = lambda: datetime.now(UTC)
    ) -> None:
        self.store = store
        self.clock = clock

    def workbench(self, principal: Principal) -> dict[str, object]:
        grant = principal.grant()
        records, proposals, receipts = self.store.snapshot(grant)
        findings = [finding(r) for r in records if r.kind == "invoice"]
        applied = {r.command.business_operation_id for r in receipts}
        bill = [p for p in proposals if p.command.kind == "invoice_correct"]
        original = [finding(r, original=True) for r in records if r.kind == "invoice"]
        digest = Digest(
            found_minor=sum(abs(f.delta_minor or 0) for f in original),
            proposed_minor=sum(abs(p.adjustment_minor) for p in bill),
            approved_minor=sum(
                abs(p.adjustment_minor)
                for p in bill
                if p.reviewer_id is not None and p.status != "rejected"
            ),
            applied_minor=sum(
                abs((r.after.amount_minor or 0) - (r.before.amount_minor or 0))
                for r in receipts
                if r.command.kind == "invoice_correct"
            ),
            rejected_minor=sum(abs(p.adjustment_minor) for p in bill if p.status == "rejected"),
            compensated_minor=sum(
                abs((r.after.amount_minor or 0) - (r.before.amount_minor or 0))
                for r in receipts
                if r.command.kind == "compensate" and r.before.kind == "invoice"
            ),
            net_adjustment_minor=sum(
                (r.after.amount_minor or 0) - (r.before.amount_minor or 0)
                for r in receipts
                if r.before.kind == "invoice"
            ),
            pending_count=sum(p.status == "pending" for p in proposals),
            expired_count=sum(p.status == "expired" for p in proposals),
            ledger_entries=len(receipts),
        )
        return {
            "at": self.clock().isoformat(),
            "unit": "SIM",
            "digest": digest.model_dump(mode="json"),
            "findings": [f.model_dump(mode="json") for f in findings],
            "records": [
                {
                    "resource_id": r.resource_id,
                    "kind": r.kind,
                    "version": r.version,
                    "amount_minor": r.amount_minor,
                    "account_id": r.account_id,
                    "note": r.note,
                    "alias_to": r.alias_to,
                }
                for r in records
            ],
            "proposals": [
                {
                    "operation_id": p.command.business_operation_id,
                    "command": p.command.model_dump(mode="json"),
                    "proposer_id": p.proposer_id,
                    "reviewer_id": p.reviewer_id,
                    "status": "applied" if p.command.business_operation_id in applied else p.status,
                    "adjustment_minor": p.adjustment_minor,
                    "created_at": p.created_at.isoformat(),
                    "expires_at": p.expires_at.isoformat(),
                    "overdue": self.clock() >= p.expires_at,
                    "action_digest": action_digest(p),
                }
                for p in proposals
            ],
            "ledger": [
                {
                    "ledger_id": r.ledger_id,
                    "operation_id": r.command.business_operation_id,
                    "kind": r.command.kind,
                    "resource_id": r.command.resource_id,
                    "before_version": r.before.version,
                    "after_version": r.after.version,
                    "delta_minor": (r.after.amount_minor or 0) - (r.before.amount_minor or 0),
                    "actor_id": r.actor_id,
                    "reviewer_id": r.reviewer_id,
                    "committed_at": r.committed_at.isoformat(),
                }
                for r in receipts
            ],
        }

    def propose(self, principal: Principal, payload: Submission) -> Proposal:
        if principal.role != "operator":
            raise PermissionError("operator required")
        previous = [
            p
            for p in self.store.proposals(principal.grant())
            if p.command.business_operation_id == payload.operation_id
        ]
        if previous:
            prior = previous[0]
            expected = (
                payload.kind,
                payload.resource_id,
                payload.expected_version,
                payload.target_account_id,
                payload.expected_target_version,
                payload.original_operation_id,
            )
            actual = (
                prior.command.kind,
                prior.command.resource_id,
                prior.command.expected_version,
                prior.command.target_account_id,
                prior.command.expected_target_version,
                prior.command.original_operation_id,
            )
            if expected != actual or prior.proposer_id != principal.actor_id:
                raise BusinessReview("operation_key_reused")
            return prior
        amount = None
        if payload.kind == "invoice_correct":
            matches = [
                r
                for r in self.store.records(principal.grant())
                if r.kind == "invoice" and r.resource_id == payload.resource_id
            ]
            if len(matches) != 1:
                raise LookupError("record unavailable")
            found = finding(matches[0])
            if not found.eligible:
                raise BusinessReview("finding_requires_review")
            amount = found.should_be_minor
        command = ChangeCommand(
            tenant_id=principal.tenant_id,
            business_operation_id=payload.operation_id,
            kind=payload.kind,
            resource_id=payload.resource_id,
            expected_version=payload.expected_version,
            invoice_amount_minor=amount,
            target_account_id=payload.target_account_id,
            expected_target_version=payload.expected_target_version,
            original_operation_id=payload.original_operation_id,
        )
        return self.store.propose(principal.grant(), command)

    def review(
        self, principal: Principal, operation_id: str, *, approve: bool, digest: str
    ) -> Proposal:
        if principal.role != "reviewer":
            raise PermissionError("reviewer required")
        proposals = [
            p
            for p in self.store.proposals(principal.grant())
            if p.command.business_operation_id == operation_id
        ]
        if len(proposals) != 1:
            raise LookupError("proposal unavailable")
        if action_digest(proposals[0]) != digest:
            raise BusinessReview("displayed_action_changed")
        return self.store.review(principal.grant(), operation_id, approve=approve)
