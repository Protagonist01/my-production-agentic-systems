"""Trusted Revenue read/reconcile authority; no billing mutation or policy permission."""

from typing import Annotated, Literal

from agent_harness.access import ResourceScope
from agent_harness.contracts import Contract
from pydantic import Field

Identity = Annotated[str, Field(min_length=1, max_length=256, pattern=r"\S")]


class BillingGrant(Contract):
    """Issued by trusted composition; a billing world names one scoped public input."""

    tenant_id: Identity
    actor_id: Identity
    world_ids: tuple[Identity, ...]
    capabilities: tuple[Literal["read", "reconcile"], ...]

    def require(self, *, tenant_id: str, world_id: str, capability: str) -> None:
        ResourceScope(
            tenant_id=self.tenant_id,
            actor_id=self.actor_id,
            resource_kind="billing_world",
            resource_ids=self.world_ids,
            capabilities=self.capabilities,
        ).require(
            tenant_id=tenant_id,
            resource_kind="billing_world",
            resource_id=world_id,
            capability=capability,
        )
