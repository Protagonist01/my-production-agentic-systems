"""Explicit trusted in-process resource scope; authentication and domain rules stay outside."""

from agent_harness.contracts import Contract, NonEmpty


class ResourceScope(Contract):
    """An exact allow-list supplied by trusted composition, never by candidate output.

    Resource kinds and capability vocabularies belong to each domain adapter. Empty
    allow-lists grant nothing. Asterisks and prefixes have no special interpretation.
    """

    tenant_id: NonEmpty
    actor_id: NonEmpty
    resource_kind: NonEmpty
    resource_ids: tuple[NonEmpty, ...]
    capabilities: tuple[NonEmpty, ...]

    def require(
        self, *, tenant_id: str, resource_kind: str, resource_id: str, capability: str
    ) -> None:
        if (
            tenant_id != self.tenant_id
            or resource_kind != self.resource_kind
            or resource_id not in self.resource_ids
            or capability not in self.capabilities
        ):
            raise PermissionError("resource scope does not authorize this operation")
