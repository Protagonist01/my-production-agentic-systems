"""Strict private application records; HTTP callers never supply principals or grants."""

from datetime import datetime
from typing import Annotated, Literal

from agent_harness.contracts import Contract, RunContext
from pydantic import Field

from olist_support.business_contracts import CallerGrant, Identity, RefundCommand
from olist_support.policy import PolicyProposal, ScenarioConfirmation
from olist_support.views import OrderView
from olist_support.workflow import WorkflowResult


class Principal(Contract):
    username: Identity
    tenant_id: Identity
    actor_id: Identity
    role: Literal["operator", "reviewer"]
    order_ids: Annotated[tuple[Identity, ...], Field(max_length=1000)]

    def grant(self, order: str) -> CallerGrant:
        grant = CallerGrant(
            tenant_id=self.tenant_id,
            actor_id=self.actor_id,
            order_ids=self.order_ids,
            capabilities=("read", "refund"),
        )
        grant.require(self.tenant_id, order, "read")
        return grant

    def require(self, role: str) -> None:
        if self.role != role:
            raise PermissionError("role does not authorize this operation")


class Submission(Contract):
    event_key: Identity
    order_id: Identity
    text: Annotated[str, Field(min_length=1, max_length=8192)]
    intent: Literal["refund", "status", "reship"]
    require_review: bool = False


Status = Literal[
    "processing",
    "review_required",
    "approved",
    "rejected",
    "stale",
    "committed",
    "status",
    "needs_recovery",
]


class CaseRecord(Contract):
    case_id: Identity
    tenant_id: Identity
    order_id: Identity
    submitted_actor: Identity
    status: Status
    version: Annotated[int, Field(ge=0)]
    request: Submission
    context: RunContext
    created_at: datetime
    updated_at: datetime
    result: WorkflowResult | None = None
    proposal: PolicyProposal | None = None
    evidence: OrderView | None = None
    confirmation: ScenarioConfirmation | None = None
    command: RefundCommand | None = None
    record_pin: str | None = None
    action_digest: str | None = None
    approved_by: Identity | None = None
    approval_version: int | None = None
    error_code: str | None = None


class Decision(Contract):
    decision: Literal["approve", "reject"]
    expected_version: Annotated[int, Field(ge=0)]
    action_digest: str | None
    rationale: Annotated[str, Field(min_length=1, max_length=2000)]


class Resume(Contract):
    action_digest: str | None
