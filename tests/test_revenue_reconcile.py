"""Independent invented arithmetic expectations; no candidate-generated gold."""

from datetime import date

import pytest
from revenue_integrity.billing_contracts import (
    Amendment,
    BillingInput,
    Credit,
    Invoice,
    SubscriptionTerms,
)
from revenue_integrity.reconcile import reconcile


def case(**changes):
    fields = dict(
        case_id="invented-r4",
        tenant_id="invented-tenant",
        account_id="invented-account",
        subscription_id="invented-subscription",
        period_start=date(2025, 1, 1),
        period_end=date(2025, 2, 1),
        terms=SubscriptionTerms(start=date(2024, 1, 1), seats=3, unit_price_minor=1000),
        invoice=Invoice(amount_minor=3000),
    )
    fields.update(changes)
    return BillingInput(**fields)


@pytest.mark.parametrize(
    ("invoice", "expected", "disposition", "delta"),
    [
        (3000, 3000, "correct", 0),
        (2500, 3000, "underbilled", 500),
        (3500, 3000, "overbilled", -500),
    ],
)
def test_independent_monthly_amounts(invoice, expected, disposition, delta):
    result = reconcile(case(invoice=Invoice(amount_minor=invoice)))
    assert (result.should_be_minor, result.disposition, result.delta_minor) == (
        expected,
        disposition,
        delta,
    )


def test_dated_ramp_credit_and_half_open_subscription():
    value = case(
        amendments=(
            Amendment(effective=date(2024, 12, 1), sequence=1, seats=4),
            Amendment(effective=date(2025, 2, 1), sequence=2, seats=99),
        ),
        credits=(Credit(effective=date(2025, 1, 1), amount_minor=500),),
    )
    assert reconcile(value).should_be_minor == 3500
    ended = value.model_dump()
    ended["terms"]["end"] = date(2025, 1, 1)
    ended["amendments"] = ()
    ended["credits"] = ()
    assert reconcile(BillingInput.model_validate(ended)).should_be_minor == 0


def test_explicit_uplift_compounds_and_price_amendment_resets_base():
    terms = SubscriptionTerms(
        start=date(2024, 1, 1),
        seats=2,
        unit_price_minor=10000,
        annual_uplift_bps=1000,
        uplift_anchor=date(2025, 1, 1),
    )
    assert reconcile(case(terms=terms)).should_be_minor == 22000
    assert (
        reconcile(
            case(
                terms=terms,
                period_start=date(2026, 1, 1),
                period_end=date(2026, 2, 1),
            )
        ).should_be_minor
        == 24200
    )
    assert (
        reconcile(
            case(
                terms=terms,
                period_start=date(2026, 1, 1),
                period_end=date(2026, 2, 1),
                amendments=(
                    Amendment(effective=date(2025, 7, 1), sequence=1, unit_price_minor=20000),
                ),
            )
        ).should_be_minor
        == 44000
    )


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        (
            {"period_start": date(9999, 12, 1), "period_end": date(9999, 12, 31)},
            "not_one_complete_calendar_month",
        ),
        ({"period_end": date(2025, 3, 1)}, "not_one_complete_calendar_month"),
        (
            {"terms": SubscriptionTerms(start=date(2024, 1, 1), seats=None, unit_price_minor=1)},
            "missing_seats_or_price",
        ),
        (
            {
                "terms": SubscriptionTerms(
                    start=date(2024, 1, 1),
                    seats=1,
                    unit_price_minor=1,
                    conflicting_terms=("two inconsistent prices",),
                )
            },
            "conflicting_terms",
        ),
        (
            {"terms": SubscriptionTerms(start=date(2024, 1, 15), seats=1, unit_price_minor=1)},
            "partial_subscription_month",
        ),
        (
            {
                "terms": SubscriptionTerms(
                    start=date(2024, 1, 1), seats=1, unit_price_minor=1, annual_uplift_bps=100
                )
            },
            "incomplete_explicit_uplift",
        ),
        (
            {
                "terms": SubscriptionTerms(
                    start=date(2024, 1, 1),
                    seats=1,
                    unit_price_minor=1,
                    annual_uplift_bps=100,
                    uplift_anchor=date(2025, 1, 1),
                )
            },
            "fractional_minor_uplift",
        ),
        (
            {"credits": (Credit(effective=date(2025, 1, 1), amount_minor=3001),)},
            "credit_exceeds_monthly_charge",
        ),
        (
            {"amendments": (Amendment(effective=date(2025, 1, 15), sequence=1, seats=4),)},
            "partial_month_event",
        ),
        (
            {
                "amendments": (
                    Amendment(effective=date(2025, 1, 1), sequence=1, seats=4),
                    Amendment(effective=date(2025, 1, 1), sequence=2, seats=5),
                )
            },
            "conflicting_same_date_amendments",
        ),
        (
            {
                "amendments": (
                    Amendment(effective=date(2025, 1, 1), sequence=1, seats=4),
                    Amendment(effective=date(2025, 2, 1), sequence=1, seats=5),
                )
            },
            "duplicate_amendment_sequence",
        ),
    ],
)
def test_unsupported_facts_produce_review_with_no_numeric_guess(changes, reason):
    result = reconcile(case(**changes))
    assert result.disposition == "review"
    assert result.should_be_minor is None and result.delta_minor is None
    assert result.reasons == (reason,)


def test_no_implicit_uplift_and_same_day_order_is_unknown():
    assert (
        reconcile(
            case(
                period_start=date(2030, 1, 1),
                period_end=date(2030, 2, 1),
            )
        ).should_be_minor
        == 3000
    )
    terms = SubscriptionTerms(
        start=date(2024, 1, 1),
        seats=1,
        unit_price_minor=10000,
        annual_uplift_bps=1000,
        uplift_anchor=date(2025, 1, 1),
    )
    result = reconcile(
        case(
            terms=terms,
            amendments=(Amendment(effective=date(2025, 1, 1), sequence=1, unit_price_minor=20000),),
        )
    )
    assert result.reasons == ("price_amendment_uplift_order_unknown",)
