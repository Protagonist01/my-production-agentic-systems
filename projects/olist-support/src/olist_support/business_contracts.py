"""Trusted caller grants, stable SIM operation payloads and durable receipts."""

from typing import Annotated, Literal

from agent_harness.access import ResourceScope
from agent_harness.contracts import Contract
from pydantic import Field

Identity = Annotated[str, Field(min_length=1, max_length=256, pattern=r"\S")]
Minor = Annotated[int, Field(ge=0, le=2**63 - 1)]


class CallerGrant(Contract):
    """Issued by trusted composition; not an authentication/authorization service."""

    tenant_id: Identity
    actor_id: Identity
    order_ids: tuple[Identity, ...]
    capabilities: tuple[Literal["read", "refund"], ...]

    def require(self, tenant: str, order: str, capability: str) -> None:
        scope = ResourceScope(
            tenant_id=self.tenant_id,
            actor_id=self.actor_id,
            resource_kind="order",
            resource_ids=self.order_ids,
            capabilities=self.capabilities,
        )
        try:
            scope.require(
                tenant_id=tenant, resource_kind="order", resource_id=order, capability=capability
            )
        except PermissionError:
            raise PermissionError(
                "caller grant does not authorize this tenant/order/capability"
            ) from None


class RefundCommand(Contract):
    tenant_id: Identity
    business_operation_id: Identity
    order_id: Identity
    amount_minor: Annotated[int, Field(gt=0, le=10000)]
    expected_version: Minor
    unit: Literal["SIM"] = "SIM"


class RefundReceipt(Contract):
    tenant_id: Identity
    business_operation_id: Identity
    order_id: Identity
    ledger_id: Identity
    amount_minor: Annotated[int, Field(gt=0, le=10000)]
    unit: Literal["SIM"] = "SIM"
    order_version: Annotated[int, Field(gt=0)]
    original_run_id: Identity
    actor_id: Identity
    committed: Literal[True] = True


class BusinessReview(ValueError):
    """A state/policy/limit conflict requiring a fresh reviewed decision, with no write."""
