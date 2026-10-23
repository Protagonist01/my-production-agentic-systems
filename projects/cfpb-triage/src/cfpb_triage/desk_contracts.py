"""Exact complaint scopes and enqueue-only commands; no account-resolution action."""

from typing import Annotated, Literal

from agent_harness.access import ResourceScope
from agent_harness.contracts import Contract
from pydantic import Field

from cfpb_triage.triage_contracts import Id


class Principal(Contract):
    username: Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9_.-]{2,63}$")]
    tenant_id: Id
    actor_id: Id
    role: Literal["reviewer", "viewer"]
    case_ids: Annotated[tuple[Id, ...], Field(max_length=100)]

    def require(self, case_id: str, *, write: bool = False) -> None:
        ResourceScope(
            tenant_id=self.tenant_id,
            actor_id=self.actor_id,
            resource_kind="cfpb-case",
            resource_ids=self.case_ids,
            capabilities=("read", "enqueue_review") if self.role == "reviewer" else ("read",),
        ).require(
            tenant_id=self.tenant_id,
            resource_kind="cfpb-case",
            resource_id=case_id,
            capability="enqueue_review" if write else "read",
        )


class QueueCommand(Contract):
    command_id: Id
    expected_version: Annotated[int, Field(ge=1)]
    reason: Literal[
        "uncertainty", "high_priority", "incorrect_category", "masking_issue", "expert_review"
    ]


class StateChanged(ValueError):
    pass
