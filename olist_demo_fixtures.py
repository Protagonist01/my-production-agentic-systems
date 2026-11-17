"""Fictional order fixtures for the declared demo contract, never real Olist orders."""

from dataclasses import dataclass

from olist_support.policy import ScenarioConfirmation
from olist_support.views import AmountTotal, OrderView

from olist_demo_acceptance import VERSION, DemoCase, canonical, digest


@dataclass(frozen=True)
class Fixture:
    view: OrderView
    facts: ScenarioConfirmation | None
    expected_new_refund_minor: int | None


def fixture(case: DemoCase, *, tenant_id: str, order_id: str) -> Fixture:
    """Trusted provisioning only. Candidate receives none of this function's references."""
    payments = {
        "olist-demo-refund-1": 3725,
        "olist-demo-refund-2": 1950,
        "olist-demo-refund-3": 8800,
        "olist-demo-refund-4": 10000,
        "olist-demo-refund-5": 10001,
    }
    payment = payments.get(case.case_id, 5000)
    view = OrderView(
        tenant_id=tenant_id,
        order_id=order_id,
        as_of_source_local="2026-11-17T00:00:00",
        source_manifest_sha256=digest(
            canonical({"version": VERSION, "fictional_fixture": case.case_id})
        ),
        currency_unit=None,
        snapshot_details_visible=True,
        events=(),
        final_source_status="delivered" if case.fixture == "conflicting_facts" else "canceled",
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
        payment=AmountTotal(known_minor=payment, total_minor=payment, missing_rows=0),
    )
    facts = (
        None
        if case.fixture == "missing_facts"
        else ScenarioConfirmation(
            tenant_id=tenant_id,
            order_id=order_id,
            available_at_source_local="2026-11-16T00:00:00",
            unit="SIM",
            payment_confirmed=True,
            undelivered_confirmed=case.fixture != "conflicting_facts",
            prior_refund_minor=0,
        )
    )
    return Fixture(
        view,
        facts,
        payment
        if case.case_id
        in (
            "olist-demo-refund-1",
            "olist-demo-refund-2",
            "olist-demo-refund-4",
        )
        else None,
    )
