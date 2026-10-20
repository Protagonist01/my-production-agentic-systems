"""Explicit fictional monthly SIM inputs and evaluator-only literal expectations."""

from datetime import date
from typing import Annotated, Literal

from agent_harness.contracts import Contract, NonEmpty
from pydantic import Field

Identity = Annotated[str, Field(min_length=1, max_length=256, pattern=r"\S")]
Minor = Annotated[int, Field(ge=0, le=2**63 - 1)]
Seats = Annotated[int, Field(ge=1, le=1_000_000)]
POLICY = "revenue-monthly-whole-seat-sim-v1"


class SubscriptionTerms(Contract):
    start: date
    end: date | None = None
    seats: Seats | None
    unit_price_minor: Minor | None
    annual_uplift_bps: Annotated[int, Field(ge=0, le=10000)] | None = None
    uplift_anchor: date | None = None
    conflicting_terms: tuple[NonEmpty, ...] = ()


class Amendment(Contract):
    effective: date
    sequence: Annotated[int, Field(ge=1)]
    seats: Seats | None = None
    unit_price_minor: Minor | None = None


class Credit(Contract):
    effective: date
    amount_minor: Minor


class Invoice(Contract):
    amount_minor: Minor


class BillingInput(Contract):
    case_id: Identity
    tenant_id: Identity
    account_id: Identity
    subscription_id: Identity
    period_start: date
    period_end: date
    terms: SubscriptionTerms
    amendments: tuple[Amendment, ...] = ()
    credits: tuple[Credit, ...] = ()
    invoice: Invoice
    unit: Literal["SIM"] = "SIM"
    source_kind: Literal["synthetic"] = "synthetic"
    policy_version: Literal["revenue-monthly-whole-seat-sim-v1"] = (
        "revenue-monthly-whole-seat-sim-v1"
    )


class BillingExpected(Contract):
    """Literal fixture judgment; generated independently of the production reconciler."""

    should_be_minor: Minor | None
    disposition: Literal["correct", "underbilled", "overbilled", "review"]
    reason: NonEmpty
    arithmetic: NonEmpty


class BillingCase(Contract):
    input: BillingInput
    group_id: NonEmpty
    split: Literal["development", "regression", "holdout"]
    treatment: NonEmpty
    expected: BillingExpected
    reviewer_kind: Literal["ai"] = "ai"
    review_status: Literal["provisional"] = "provisional"
    policy_approval: Literal["user-approved-policy-not-label-review"] = (
        "user-approved-policy-not-label-review"
    )
