"""Invented policy witnesses; no real order, language label or payment outcome."""

import ast
from pathlib import Path

import pytest
from olist_support.evaluation_oracle import OracleFacts, OracleRequest, evaluate_policy
from olist_support.views import AmountTotal, Event, OrderView


def view(amount=5000, **changes):
    return OrderView(
        **(
            dict(
                tenant_id="invented-tenant",
                order_id="invented-order",
                as_of_source_local="2026-10-20T12:00:00",
                source_manifest_sha256="invented",
                currency_unit=None,
                snapshot_details_visible=True,
                events=(),
                final_source_status="canceled",
                estimated_delivery_source_local=None,
                customer_city=None,
                customer_state=None,
                items=(),
                payments=(),
                reviews=(),
                item_count=0,
                payment_count=1,
                price=None,
                freight=None,
                payment=AmountTotal(known_minor=amount, total_minor=amount, missing_rows=0),
            )
            | changes
        )
    )


def facts(**changes):
    return OracleFacts(
        **(
            dict(
                tenant_id="invented-tenant",
                order_id="invented-order",
                available_at_source_local="2026-10-20T12:00:00",
                unit="SIM",
                payment_confirmed=True,
                undelivered_confirmed=True,
                prior_refund_minor=0,
            )
            | changes
        )
    )


@pytest.mark.parametrize(
    "amount,expected", [(0, None), (1, 1), (9999, 9999), (10000, 10000), (10001, None)]
)
def test_independently_specified_cap_witnesses(amount, expected):
    original = view(amount)
    before = original.canonical_json()
    result = evaluate_policy(original, OracleRequest(intent="refund"), facts())
    assert result.amount_minor == expected
    assert result.action == ("review" if expected is None else "propose_full_refund")
    assert result.committed is False and original.canonical_json() == before


@pytest.mark.parametrize(
    "view_changes,fact_changes,rule",
    [
        ({}, {"available_at_source_local": "2026-10-20T12:00:01"}, "confirmation_available"),
        ({}, {"unit": None}, "sim_unit"),
        ({"snapshot_details_visible": False}, {}, "visible_cancellation"),
        ({"final_source_status": "delivered"}, {}, "visible_cancellation"),
        (
            {"events": (Event(kind="payment", source_local_time="2026-10-21"),)},
            {},
            "events_available",
        ),
        (
            {"events": (Event(kind="customer_delivery", source_local_time="2026-10-20"),)},
            {},
            "no_delivery_conflict",
        ),
        ({}, {"undelivered_confirmed": None}, "non_delivery_confirmed"),
        ({}, {"payment_confirmed": False}, "payment_confirmed"),
        ({"payment": None}, {}, "payment_confirmed"),
        ({"payment_count": None}, {}, "payment_confirmed"),
        (
            {"payment": AmountTotal(known_minor=5000, total_minor=5000, missing_rows=1)},
            {},
            "payment_confirmed",
        ),
        (
            {"payment": AmountTotal(known_minor=4999, total_minor=5000, missing_rows=0)},
            {},
            "payment_confirmed",
        ),
        ({}, {"prior_refund_minor": None}, "no_prior_refund"),
        ({}, {"prior_refund_minor": 1}, "no_prior_refund"),
    ],
)
def test_missing_conflicting_and_future_facts_cannot_propose(view_changes, fact_changes, rule):
    result = evaluate_policy(
        view(**view_changes), OracleRequest(intent="refund"), facts(**fact_changes)
    )
    assert result.action == "review" and result.amount_minor is None
    assert rule in result.failed_rules


def test_partial_request_reship_unknown_confirmation_and_multiple_failures():
    assert (
        "full_payment_requested"
        in evaluate_policy(
            view(), OracleRequest(intent="refund", requested_minor=2000), facts()
        ).failed_rules
    )
    assert evaluate_policy(view(), OracleRequest(intent="reship"), None).action == "review"
    assert evaluate_policy(view(), OracleRequest(intent="refund"), None).action == "review"
    result = evaluate_policy(
        view(10001), OracleRequest(intent="refund"), facts(payment_confirmed=False)
    )
    assert set(result.failed_rules) == {"payment_confirmed", "within_cap"}


def test_out_of_scope_and_timezone_facts_are_not_silently_normalized():
    with pytest.raises(PermissionError):
        evaluate_policy(view(), OracleRequest(intent="refund"), facts(tenant_id="other"))
    with pytest.raises(ValueError, match="source-local"):
        evaluate_policy(
            view(),
            OracleRequest(intent="refund"),
            facts(available_at_source_local="2026-10-20T12:00:00+00:00"),
        )


def test_oracle_has_no_production_policy_dependency_and_exposes_seeded_wrong_answers():
    import olist_support.evaluation_oracle as module

    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    imports = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    assert "olist_support.policy" not in imports
    # An always-refund mutant is caught on a denied case; amount mutation on an eligible case.
    denied = evaluate_policy(view(10001), OracleRequest(intent="refund"), facts())
    allowed = evaluate_policy(view(5000), OracleRequest(intent="refund"), facts())
    assert (denied.action, denied.amount_minor) != ("propose_full_refund", 10001)
    assert (allowed.action, allowed.amount_minor) != ("propose_full_refund", 4999)
