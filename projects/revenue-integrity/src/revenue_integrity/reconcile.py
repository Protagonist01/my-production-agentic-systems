"""Pure, conservative monthly SIM arithmetic. No invoice or payment mutation."""

from datetime import date
from typing import Literal

from agent_harness.contracts import Contract

from revenue_integrity.billing_contracts import BillingInput


class Reconciliation(Contract):
    case_id: str
    disposition: Literal["correct", "underbilled", "overbilled", "review"]
    should_be_minor: int | None
    issued_minor: int
    delta_minor: int | None
    reasons: tuple[str, ...]
    policy_version: Literal["revenue-monthly-whole-seat-sim-v1"] = (
        "revenue-monthly-whole-seat-sim-v1"
    )
    unit: Literal["SIM"] = "SIM"


def _next_month(value: date) -> date:
    return date(value.year + (value.month == 12), value.month % 12 + 1, 1)


def reconcile(value: BillingInput) -> Reconciliation:
    """Return a review result whenever exact monthly arithmetic is not authorized.

    Positive delta means the issued invoice was too small. The uplift anchor is
    the FIRST scheduled uplift, not the subscription's base anniversary.
    """
    value = BillingInput.model_validate(value.model_dump())
    terms = value.terms

    def review(reason: str) -> Reconciliation:
        return Reconciliation(
            case_id=value.case_id,
            disposition="review",
            should_be_minor=None,
            issued_minor=value.invoice.amount_minor,
            delta_minor=None,
            reasons=(reason,),
        )

    if (
        value.period_start.year == 9999
        and value.period_start.month == 12
        or value.period_start.day != 1
        or value.period_end != _next_month(value.period_start)
    ):
        return review("not_one_complete_calendar_month")
    if terms.conflicting_terms:
        return review("conflicting_terms")
    if terms.seats is None or terms.unit_price_minor is None:
        return review("missing_seats_or_price")
    if terms.start.day != 1 or (terms.end is not None and terms.end.day != 1):
        return review("partial_subscription_month")
    if terms.end is not None and terms.end <= terms.start:
        return review("invalid_subscription_interval")
    if (terms.annual_uplift_bps is None) != (terms.uplift_anchor is None):
        return review("incomplete_explicit_uplift")
    if terms.uplift_anchor is not None and (
        terms.uplift_anchor.day != 1 or terms.uplift_anchor <= terms.start
    ):
        return review("invalid_uplift_anchor")
    if any(event.effective.day != 1 for event in value.amendments) or any(
        event.effective.day != 1 for event in value.credits
    ):
        return review("partial_month_event")
    if any(
        event.effective < terms.start or (terms.end is not None and event.effective >= terms.end)
        for event in value.amendments
    ):
        return review("amendment_outside_subscription")
    amendments = sorted(value.amendments, key=lambda event: (event.effective, event.sequence))
    if len({event.sequence for event in amendments}) != len(amendments):
        return review("duplicate_amendment_sequence")
    if any(
        left.sequence >= right.sequence
        for left, right in zip(amendments, amendments[1:], strict=False)
    ):
        return review("amendment_sequence_conflicts_with_date")
    by_date: dict[date, dict[str, int]] = {}
    for event in amendments:
        if event.seats is None and event.unit_price_minor is None:
            return review("empty_amendment")
        fields = by_date.setdefault(event.effective, {})
        for name in ("seats", "unit_price_minor"):
            updated = getattr(event, name)
            if updated is not None:
                if name in fields and fields[name] != updated:
                    return review("conflicting_same_date_amendments")
                fields[name] = updated
    active = terms.start <= value.period_start and (
        terms.end is None or value.period_start < terms.end
    )
    seats, price = terms.seats, terms.unit_price_minor
    price_date = terms.start
    for effective, fields in sorted(by_date.items()):
        if effective > value.period_start:
            break
        seats = fields.get("seats", seats)
        if "unit_price_minor" in fields:
            price, price_date = fields["unit_price_minor"], effective
    if active and terms.uplift_anchor is not None:
        anchor = terms.uplift_anchor
        for year in range(anchor.year, value.period_start.year + 1):
            anniversary = date(year, anchor.month, 1)
            if anniversary > value.period_start:
                break
            if anniversary == price_date:
                return review("price_amendment_uplift_order_unknown")
            if anniversary > price_date:
                numerator = price * (10000 + (terms.annual_uplift_bps or 0))
                if numerator % 10000:
                    return review("fractional_minor_uplift")
                price = numerator // 10000
    gross = seats * price if active else 0
    credits = sum(
        event.amount_minor for event in value.credits if event.effective == value.period_start
    )
    if credits > gross:
        return review("credit_exceeds_monthly_charge")
    expected = gross - credits
    if expected > 2**63 - 1:
        return review("amount_outside_supported_range")
    delta = expected - value.invoice.amount_minor
    return Reconciliation(
        case_id=value.case_id,
        disposition="correct" if delta == 0 else "underbilled" if delta > 0 else "overbilled",
        should_be_minor=expected,
        issued_minor=value.invoice.amount_minor,
        delta_minor=delta,
        reasons=("exact_monthly_sim_arithmetic",),
    )
