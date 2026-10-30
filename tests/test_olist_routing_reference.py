"""Invented reference construction and seeded arithmetic failures; no language-model score."""

import pytest
from olist_support.routing_contracts import RoutingPlan
from olist_support.routing_reference import AmountSpan, RoutingReference
from pydantic import ValidationError


def reference(text, intent, amount=None, token=None):
    start = text.index(token) if token is not None else None
    return RoutingReference(
        text=text,
        expected=RoutingPlan(
            routing_version="olist-intent-routing-v2", intent=intent, requested_minor=amount
        ),
        provenance="constructed_development",
        amount_span=None if start is None else AmountSpan(start=start, end=start + len(token)),
    )


@pytest.mark.parametrize(
    "text",
    [
        "Send a replacement; do not refund the payment.",
        "I want another shipment instead of money back.",
        "Please replace this order, rather than reimburse me.",
    ],
)
def test_reship_witnesses_remain_constructed_not_semantic_gold(text):
    result = reference(text, "reship")
    assert result.expected.intent == "reship" and result.expected.requested_minor is None
    assert not result.semantic_gold_validated and not result.release_allowed


@pytest.mark.parametrize(
    "amount,token",
    [
        (0, "0.00 SIM"),
        (1, "0.01 SIM"),
        (100, "1.00 SIM"),
        (9999, "99.99 SIM"),
        (10000, "100.00 SIM"),
        (10001, "100.01 SIM"),
    ],
)
def test_partial_zero_and_cap_boundaries_have_exact_numeric_witnesses(amount, token):
    result = reference(f"Refund exactly {token}, not my whole payment.", "refund", amount, token)
    assert result.expected.requested_minor == amount
    # This confirms transcription, never automatic refund eligibility or authorization.
    assert result.semantic_gold_validated is False


@pytest.mark.parametrize(
    "text,token,amount",
    [
        ("Refund 12.34 SIM", "12.34 SIM", 1235),
        ("Refund -12.34 SIM", "12.34 SIM", 1234),
        ("Refund 112.34 SIM", "12.34 SIM", 1234),
        ("Refund 12.34 SIMULATED", "12.34 SIM", 1234),
        ("Refund 12.3 SIM", "12.3 SIM", 1230),
        ("Refund 12.34 USD", "12.34 USD", 1234),
    ],
)
def test_mutated_reference_or_span_cannot_validate(text, token, amount):
    with pytest.raises(ValidationError):
        reference(text, "refund", amount, token)


def test_missing_numeric_span_and_non_refund_amount_refused():
    with pytest.raises(ValidationError):
        reference("Refund exactly 1.00 SIM", "refund", 100)
    with pytest.raises(ValidationError):
        reference("Send another item for 1.00 SIM", "reship", 100, "1.00 SIM")
