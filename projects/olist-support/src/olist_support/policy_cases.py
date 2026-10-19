"""Private O3 case contracts: literal reviewer labels never enter policy input."""

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal, Self

from agent_harness.contracts import Contract, NonEmpty
from pydantic import AwareDatetime, Field, model_validator

from olist_support.policy import POLICY_VERSION, ScenarioConfirmation, SupportRequest
from olist_support.views import OrderView

Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Split = Literal["development", "regression", "holdout"]


class CaseInput(Contract):
    case_id: Digest
    order: OrderView
    request: SupportRequest
    confirmation: ScenarioConfirmation | None


class ExpectedProposal(Contract):
    """Literal evaluator judgment, authored without calling the runtime proposal."""

    action: Literal["propose_full_refund", "review"]
    amount_minor: Annotated[int, Field(gt=0, le=10000)] | None
    reason: NonEmpty

    @model_validator(mode="after")
    def full_or_review(self) -> Self:
        if (self.action == "review") != (self.amount_minor is None):
            raise ValueError("review has no amount; refund has an exact positive amount")
        return self


class PolicyCase(Contract):
    input: CaseInput
    group_id: Digest
    split: Split
    source_kind: Literal["hybrid", "synthetic"]
    treatment: Literal["base", "adversarial"]
    original_view_sha256: Digest
    constructed_fields: tuple[NonEmpty, ...]
    expected: ExpectedProposal
    reviewer_id: NonEmpty
    reviewer_kind: Literal["ai", "human"]
    reviewed_at: AwareDatetime
    review_status: Literal["provisional"] = "provisional"
    guideline: Literal["olist-canceled-full-refund-sim-v1"] = POLICY_VERSION


class PolicyCases(Contract):
    version: Literal["olist-policy-cases-v1"] = "olist-policy-cases-v1"
    policy_version: Literal["olist-canceled-full-refund-sim-v1"] = POLICY_VERSION
    source_database_sha256: Digest
    source_manifest_sha256: Digest
    entries: Annotated[tuple[PolicyCase, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def grouped(self) -> Self:
        ids: set[str] = set()
        groups: dict[str, Split] = {}
        for entry in self.entries:
            if entry.input.case_id in ids:
                raise ValueError("duplicate case")
            ids.add(entry.input.case_id)
            if groups.setdefault(entry.group_id, entry.split) != entry.split:
                raise ValueError("order group crosses splits")
            confirmation = entry.input.confirmation
            order = entry.input.order
            if confirmation is not None and (confirmation.tenant_id, confirmation.order_id) != (
                order.tenant_id,
                order.order_id,
            ):
                raise ValueError("confirmation refers to another tenant/order")
            if entry.group_id != group_id(order.order_id):
                raise ValueError("group differs from underlying order")
            if not entry.constructed_fields:
                raise ValueError("hybrid/synthetic construction must be declared")
        return self


def digest(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def group_id(order_id: str) -> str:
    return digest("olist-o3-order-v1|" + order_id)


def external(path: Path) -> Path:
    path = path.expanduser().resolve()
    if any((p / ".git").exists() for p in (path, *path.parents)):
        raise ValueError("private policy cases must remain outside every Git checkout")
    return path


def local_clock(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is not None:
        raise ValueError("retain the explicitly unverified source-local clock")
    return parsed
