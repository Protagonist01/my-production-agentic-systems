"""Development reference witnesses; exact amount spans establish arithmetic, not intent."""

import re
from typing import Annotated, Literal, Self

from agent_harness.contracts import Contract, NonEmpty
from pydantic import Field, model_validator

from olist_support.routing_contracts import RoutingPlan


class AmountSpan(Contract):
    start: Annotated[int, Field(ge=0)]
    end: Annotated[int, Field(gt=0)]


class RoutingReference(Contract):
    version: Literal["olist-routing-reference-v1"] = "olist-routing-reference-v1"
    text: NonEmpty
    expected: RoutingPlan
    provenance: Literal["constructed_development", "publisher_projection_owner_accepted"]
    amount_span: AmountSpan | None = None
    semantic_gold_validated: Literal[False] = False
    release_allowed: Literal[False] = False

    @model_validator(mode="after")
    def exact_amount_witness(self) -> Self:
        if self.expected.requested_minor is None:
            if self.amount_span is not None:
                raise ValueError("no numeric reference must not contain an amount span")
            return self
        span = self.amount_span
        if span is None or not span.start < span.end <= len(self.text):
            raise ValueError("numeric reference requires a bounded exact span")
        # Require whole-token boundaries: never validate 12.34 embedded in 112.34 or -12.34.
        if span.start and (
            self.text[span.start - 1].isalnum() or self.text[span.start - 1] in ".-+"
        ):
            raise ValueError("amount span starts inside a larger token")
        if span.end < len(self.text) and self.text[span.end].isalnum():
            raise ValueError("amount span ends inside a larger token")
        match = re.fullmatch(r"(0|[1-9][0-9]*)\.([0-9]{2}) SIM", self.text[span.start : span.end])
        if match is None:
            raise ValueError("reference requires exact two-place SIM text")
        minor = int(match.group(1)) * 100 + int(match.group(2))
        if minor != self.expected.requested_minor:
            raise ValueError("literal amount differs from expected integer minor units")
        return self
