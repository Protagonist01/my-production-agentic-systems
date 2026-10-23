"""Trusted identities and closed reviewer commands; no clinical execution capability."""

from datetime import datetime
from typing import Annotated, Literal, Self

from agent_harness.access import ResourceScope
from agent_harness.contracts import Contract
from pydantic import Field, model_validator

from prior_auth.contracts import CriterionId, Id


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
            resource_kind="prior-auth-case",
            resource_ids=self.case_ids,
            capabilities=("read", "review") if self.role == "reviewer" else ("read",),
        ).require(
            tenant_id=self.tenant_id,
            resource_kind="prior-auth-case",
            resource_id=case_id,
            capability="review" if write else "read",
        )


class WaitRequest(Contract):
    command_id: Id
    expected_version: Annotated[int, Field(ge=1)]
    criteria: Annotated[tuple[CriterionId, ...], Field(min_length=1, max_length=7)]
    deadline: datetime

    @model_validator(mode="after")
    def valid(self) -> Self:
        if self.deadline.utcoffset() is None or len(set(self.criteria)) != len(self.criteria):
            raise ValueError("aware deadline and unique criteria required")
        return self


class ReviewNote(Contract):
    command_id: Id
    expected_version: Annotated[int, Field(ge=1)]
    outcome: Literal["request_information", "qualified_review"]
    # Free-form note text is excluded from the mutation and event log. Reviewers
    # select a fixed reason rather than accidentally copying identifiers into traces.
    reason: Literal[
        "missing_documentation", "conflicting_evidence", "policy_scope", "expert_review"
    ]


class RedactedDelivery(Contract):
    delivery_id: Id
    expected_version: Annotated[int, Field(ge=1)]
    text: Annotated[str, Field(min_length=1, max_length=50000)]
    # A trusted local import path supplies a concrete redaction review reference.
    review_ref: Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{1,96}$")]


class StateChanged(ValueError):
    """Refresh canonical state before retrying a newly intended operation."""
