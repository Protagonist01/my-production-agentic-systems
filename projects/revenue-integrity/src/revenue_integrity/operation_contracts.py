"""Closed SIM action payloads; grants are issued only by trusted composition."""

from datetime import datetime
from typing import Annotated, Literal

from agent_harness.access import ResourceScope
from agent_harness.contracts import Contract
from pydantic import Field, model_validator

from revenue_integrity.billing_contracts import BillingInput

Identity = Annotated[str, Field(min_length=1, max_length=256, pattern=r"\S")]
Minor = Annotated[int, Field(ge=0, le=2**63 - 1)]
Capability = Literal["read", "propose", "review", "apply", "crm_trim"]


class RevenueGrant(Contract):
    tenant_id: Identity
    actor_id: Identity
    invoice_ids: tuple[Identity, ...] = ()
    account_ids: tuple[Identity, ...] = ()
    capabilities: tuple[Capability, ...] = ()

    def require(self, tenant: str, kind: str, resource: str, capability: str) -> None:
        ids = (
            self.invoice_ids if kind == "invoice" else self.account_ids if kind == "account" else ()
        )
        ResourceScope(
            tenant_id=self.tenant_id,
            actor_id=self.actor_id,
            resource_kind=kind,
            resource_ids=ids,
            capabilities=self.capabilities,
        ).require(tenant_id=tenant, resource_kind=kind, resource_id=resource, capability=capability)

    def require_any(self, resource: str, capability: str) -> None:
        if capability not in self.capabilities or resource not in (
            *self.invoice_ids,
            *self.account_ids,
        ):
            raise PermissionError("Revenue resource/capability denied")


class RevenueRecord(Contract):
    tenant_id: Identity
    resource_id: Identity
    kind: Literal["invoice", "account"]
    version: Minor = 0
    amount_minor: Minor | None = None
    account_id: Identity | None = None
    billing_input: BillingInput | None = None
    note: Annotated[str, Field(max_length=20000)] = ""
    alias_to: Identity | None = None

    @model_validator(mode="after")
    def shape(self) -> "RevenueRecord":
        if self.kind == "invoice":
            if (
                self.amount_minor is None
                or self.account_id is None
                or self.alias_to is not None
                or self.note
            ):
                raise ValueError("invalid invoice record")
            if self.billing_input is not None and (
                self.billing_input.tenant_id != self.tenant_id
                or self.billing_input.account_id != self.account_id
            ):
                raise ValueError("invoice source identity mismatch")
        elif (
            self.amount_minor is not None
            or self.account_id is not None
            or self.billing_input is not None
        ):
            raise ValueError("invalid account record")
        return self


class ChangeCommand(Contract):
    tenant_id: Identity
    business_operation_id: Identity
    kind: Literal["invoice_correct", "account_merge", "crm_trim", "compensate"]
    resource_id: Identity
    expected_version: Minor
    invoice_amount_minor: Minor | None = None
    target_account_id: Identity | None = None
    expected_target_version: Minor | None = None
    original_operation_id: Identity | None = None
    unit: Literal["SIM"] = "SIM"

    @model_validator(mode="after")
    def shape(self) -> "ChangeCommand":
        fields = (
            self.invoice_amount_minor is not None,
            self.target_account_id is not None,
            self.expected_target_version is not None,
            self.original_operation_id is not None,
        )
        expected = {
            "invoice_correct": (True, False, False, False),
            "account_merge": (False, True, True, False),
            "crm_trim": (False, False, False, False),
            "compensate": (False, False, False, True),
        }
        if fields != expected[self.kind]:
            raise ValueError("action payload fields do not match action kind")
        return self


class Proposal(Contract):
    command: ChangeCommand
    adjustment_minor: int = 0
    proposer_id: Identity
    status: Literal["pending", "approved", "rejected", "expired"] = "pending"
    reviewer_id: Identity | None = None
    created_at: datetime
    expires_at: datetime

    @model_validator(mode="after")
    def shape(self) -> "Proposal":
        if any(
            x.tzinfo is None or x.utcoffset() is None for x in (self.created_at, self.expires_at)
        ):
            raise ValueError("proposal timestamps require timezones")
        if self.expires_at <= self.created_at:
            raise ValueError("invalid proposal interval")
        if self.status in ("approved", "rejected") and self.reviewer_id is None:
            raise ValueError("review decision requires reviewer")
        return self


class Receipt(Contract):
    command: ChangeCommand
    ledger_id: Identity
    before: RevenueRecord
    after: RevenueRecord
    original_run_id: Identity
    actor_id: Identity
    reviewer_id: Identity | None
    target: RevenueRecord | None = None
    committed_at: datetime
    committed: Literal[True] = True


class BusinessReview(ValueError):
    """Bounded, public conflict code; no private payload is included."""
