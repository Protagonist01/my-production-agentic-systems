"""Independent SIM decision table for evaluation; never parses intent or executes effects."""

from datetime import datetime
from typing import Annotated, Literal

from agent_harness.contracts import Contract, NonEmpty
from pydantic import Field

from olist_support.views import OrderView

Minor = Annotated[int, Field(ge=0, le=2**63 - 1)]


class OracleFacts(Contract):
    tenant_id: NonEmpty
    order_id: NonEmpty
    available_at_source_local: NonEmpty
    unit: Literal["SIM"] | None
    payment_confirmed: bool | None
    undelivered_confirmed: bool | None
    prior_refund_minor: Minor | None


class OracleRequest(Contract):
    # Supplied by separate reference evidence, not extracted here from customer text.
    intent: Literal["refund", "reship"]
    requested_minor: Minor | None = None


class OracleDecision(Contract):
    oracle_version: Literal["independent-olist-table-v1"] = "independent-olist-table-v1"
    action: Literal["propose_full_refund", "review"]
    amount_minor: Minor | None
    failed_rules: tuple[NonEmpty, ...]
    committed: Literal[False] = False


def _source_clock(text: str) -> datetime:
    result = datetime.fromisoformat(text)
    if result.tzinfo is not None:
        raise ValueError("oracle requires declared source-local time")
    return result


def evaluate_policy(
    view: OrderView, request: OracleRequest, facts: OracleFacts | None
) -> OracleDecision:
    """Evaluate independently written policy predicates; production policy is not imported.

    Returns all failed predicates, not the candidate's first-error explanation. A result
    establishes only constructed policy behavior conditional on trusted structured facts.
    """
    view = OrderView.model_validate_json(view.canonical_json())
    request = OracleRequest.model_validate_json(request.canonical_json())

    def review(*rules: str) -> OracleDecision:
        return OracleDecision(action="review", amount_minor=None, failed_rules=rules)

    if request.intent == "reship":
        return review("reship_needs_inventory_review")
    if facts is None:
        return review("confirmation_required")
    facts = OracleFacts.model_validate_json(facts.canonical_json())
    if (view.tenant_id, view.order_id) != (facts.tenant_id, facts.order_id):
        raise PermissionError("oracle facts outside requested scope")
    now = _source_clock(view.as_of_source_local)
    payment = view.payment
    total = None if payment is None else payment.total_minor
    complete_payment = (
        payment is not None
        and payment.missing_rows == 0
        and type(total) is int
        and total is not None
        and 0 < total <= 2**63 - 1
        and total == payment.known_minor
        and view.payment_count is not None
        and view.payment_count > 0
    )
    predicates = {
        "confirmation_available": _source_clock(facts.available_at_source_local) <= now,
        "sim_unit": facts.unit == "SIM",
        "visible_cancellation": view.snapshot_details_visible
        and view.final_source_status == "canceled",
        "events_available": all(_source_clock(e.source_local_time) <= now for e in view.events),
        "no_delivery_conflict": all(e.kind != "customer_delivery" for e in view.events),
        "non_delivery_confirmed": facts.undelivered_confirmed is True,
        "payment_confirmed": facts.payment_confirmed is True and complete_payment,
        "no_prior_refund": facts.prior_refund_minor == 0,
        "full_payment_requested": request.requested_minor is None
        or request.requested_minor == total,
        "within_cap": total is not None and 0 < total <= 10_000,
    }
    failed = tuple(name for name, passed in predicates.items() if not passed)
    if failed:
        return review(*failed)
    return OracleDecision(action="propose_full_refund", amount_minor=total, failed_rules=())
