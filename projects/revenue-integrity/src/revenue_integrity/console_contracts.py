"""Provisioned local identities and closed Revenue console requests."""

from typing import Annotated, Literal

from agent_harness.contracts import Contract
from pydantic import Field

from revenue_integrity.operation_contracts import Capability, RevenueGrant

Identity = Annotated[str, Field(min_length=1, max_length=256, pattern=r"\S")]


class Principal(Contract):
    username: Annotated[str, Field(min_length=3, max_length=64, pattern=r"^[a-z0-9][a-z0-9_.-]+$")]
    tenant_id: Identity
    actor_id: Identity
    role: Literal["operator", "reviewer"]
    invoice_ids: Annotated[tuple[Identity, ...], Field(max_length=1000)] = ()
    account_ids: Annotated[tuple[Identity, ...], Field(max_length=1000)] = ()

    def grant(self) -> RevenueGrant:
        capabilities: tuple[Capability, ...] = (
            ("read", "propose", "apply", "crm_trim")
            if self.role == "operator"
            else ("read", "review")
        )
        return RevenueGrant(
            tenant_id=self.tenant_id,
            actor_id=self.actor_id,
            invoice_ids=self.invoice_ids,
            account_ids=self.account_ids,
            capabilities=capabilities,
        )


class Submission(Contract):
    operation_id: Identity
    kind: Literal["invoice_correct", "account_merge", "compensate"]
    resource_id: Identity
    expected_version: Annotated[int, Field(ge=0)]
    target_account_id: Identity | None = None
    expected_target_version: Annotated[int, Field(ge=0)] | None = None
    original_operation_id: Identity | None = None


class Decision(Contract):
    decision: Literal["approve", "reject"]
    action_digest: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class Trim(Contract):
    operation_id: Identity
    resource_id: Identity
    expected_version: Annotated[int, Field(ge=0)]


class Wake(Contract):
    tenant_id: Identity
    actor_id: Identity
    operation_id: Identity
