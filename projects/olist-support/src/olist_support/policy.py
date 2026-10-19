"""Constructed SIM-only refund proposals; no payment or shipping side effect."""

from datetime import datetime
from typing import Annotated, Literal, Self

from agent_harness.contracts import Contract, NonEmpty
from pydantic import Field, model_validator

from olist_support.views import OrderView

POLICY_VERSION: Literal["olist-canceled-full-refund-sim-v1"] = "olist-canceled-full-refund-sim-v1"
CAP_MINOR = 10_000
Minor = Annotated[int, Field(ge=0, le=2**63 - 1)]


class ScenarioConfirmation(Contract):
    """Trusted fictional scenario facts, separate from the unchanged original view."""

    tenant_id: NonEmpty
    order_id: NonEmpty
    available_at_source_local: NonEmpty
    unit: Literal["SIM"] | None
    payment_confirmed: bool | None
    undelivered_confirmed: bool | None
    prior_refund_minor: Minor | None
    provenance: Literal["constructed-simulation-v1"] = "constructed-simulation-v1"


class SupportRequest(Contract):
    intent: Literal["refund", "reship"]
    message: NonEmpty
    requested_minor: Minor | None = None


class PolicyProposal(Contract):
    policy_version: Literal["olist-canceled-full-refund-sim-v1"] = POLICY_VERSION
    action: Literal["propose_full_refund", "review"]
    reason: NonEmpty
    amount_minor: Minor | None = None
    unit: Literal["SIM"] | None = None
    committed: Literal[False] = False

    @model_validator(mode="after")
    def consistent_action(self) -> Self:
        if self.action == "review":
            if self.amount_minor is not None or self.unit is not None:
                raise ValueError("review cannot carry a refundable amount")
        elif (
            self.unit != "SIM"
            or self.amount_minor is None
            or not 0 < self.amount_minor <= CAP_MINOR
        ):
            raise ValueError("refund proposal must be within the SIM cap")
        return self


def _local(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is not None:
        raise ValueError("Use the explicitly unverified source-local clock")
    return parsed


def propose(
    view: OrderView, request: SupportRequest, confirmation: ScenarioConfirmation | None
) -> PolicyProposal:
    """Assess trusted scoped inputs. Request text never grants policy authority."""
    view = OrderView.model_validate_json(view.canonical_json())
    request = SupportRequest.model_validate_json(request.canonical_json())

    def review(reason: str) -> PolicyProposal:
        return PolicyProposal(action="review", reason=reason)

    if request.intent == "reship":
        return review("reship_requires_inventory_and_shipping_review")
    if confirmation is None:
        return review("missing_scenario_confirmation")
    confirmation = ScenarioConfirmation.model_validate_json(confirmation.canonical_json())
    if (confirmation.tenant_id, confirmation.order_id) != (view.tenant_id, view.order_id):
        raise PermissionError("scenario confirmation is outside this tenant/order")
    as_of = _local(view.as_of_source_local)
    if _local(confirmation.available_at_source_local) > as_of:
        return review("scenario_confirmation_not_yet_available")
    if confirmation.unit != "SIM":
        return review("simulation_unit_not_declared")
    if not view.snapshot_details_visible or view.final_source_status != "canceled":
        return review("visible_cancellation_not_established")
    # A source date cannot be used as a policy fact before it is available.
    if any(_local(event.source_local_time) > as_of for event in view.events):
        return review("future_event_in_view")
    if any(event.kind == "customer_delivery" for event in view.events):
        return review("delivery_conflicts_with_non_delivery")
    if confirmation.undelivered_confirmed is not True:
        return review("non_delivery_not_independently_confirmed")
    payment = view.payment
    if (
        confirmation.payment_confirmed is not True
        or payment is None
        or view.payment_count is None
        or view.payment_count < 1
        or payment.missing_rows != 0
        or payment.total_minor is None
        or payment.total_minor <= 0
        or payment.total_minor != payment.known_minor
        or type(payment.total_minor) is not int
        or payment.total_minor > 2**63 - 1
    ):
        return review("complete_positive_payment_not_confirmed")
    if confirmation.prior_refund_minor is None:
        return review("prior_refund_state_unknown")
    if confirmation.prior_refund_minor != 0:
        return review("prior_refund_requires_reconciliation")
    amount = payment.total_minor
    if request.requested_minor is not None and request.requested_minor != amount:
        return review("request_is_not_the_full_payment")
    if amount > CAP_MINOR:
        return review("above_automatic_cap")
    return PolicyProposal(
        action="propose_full_refund",
        reason="confirmed_canceled_paid_undelivered_within_simulation_cap",
        amount_minor=amount,
        unit="SIM",
    )


def proposal_message(proposal: PolicyProposal) -> str:
    """Fixed wording cannot claim money moved; later tools must prove commitment."""
    proposal = PolicyProposal.model_validate_json(proposal.canonical_json())
    if proposal.action == "review":
        return "This request requires review. No refund or shipment has been committed."
    if proposal.amount_minor is None or proposal.unit != "SIM":
        raise ValueError("refund proposal lacks its simulation amount/unit")
    major, minor = divmod(proposal.amount_minor, 100)
    return f"A full refund of {major}.{minor:02d} SIM is proposed. No refund has been committed."
