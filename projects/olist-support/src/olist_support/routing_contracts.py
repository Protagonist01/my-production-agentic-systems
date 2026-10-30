"""Opt-in language routing; no change to the SIM action policy or legacy output schema."""

from typing import Annotated, Literal, Self

from agent_harness.contracts import Contract
from pydantic import Field, model_validator


class RoutingPlan(Contract):
    routing_version: Literal["olist-intent-routing-v2"]
    intent: Literal["refund", "status", "reship", "review", "clarify", "unsupported"]
    requested_minor: Annotated[int, Field(ge=0, le=2**63 - 1)] | None = None

    @model_validator(mode="after")
    def amount_only_for_refund(self) -> Self:
        if self.intent != "refund" and self.requested_minor is not None:
            raise ValueError("only a new refund request can carry a requested amount")
        return self
