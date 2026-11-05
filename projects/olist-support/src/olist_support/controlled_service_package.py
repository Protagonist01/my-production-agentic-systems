"""Prepare the accepted twelve meanings with explicit fictional service actor scripts.

All output is exposed development. No model transport, SQL, customer authority, accepted
qualification cohort or provider-frozen protocol is created by compilation.
"""

from typing import Annotated, Final, Literal, Self

from agent_harness.contracts import Contract
from agent_harness.release_contracts import pin, sha256
from pydantic import Field, model_validator

from olist_support.controlled_reference import draft
from olist_support.controlled_service_reference import ControlledServiceReference
from olist_support.policy import ScenarioConfirmation
from olist_support.routing_evaluation import ExpectedWorkflow, RoutingCase
from olist_support.service_evaluation import ServiceScenario, ServiceScript
from olist_support.service_study import ServicePopulation
from olist_support.views import AmountTotal, OrderView

FIXTURE_VERSION: Final = "olist-controlled-service-fictional-fixture-v1"


def _case(reference: ControlledServiceReference, *, recovery: bool = False) -> RoutingCase:
    intent = reference.expected.intent
    tenant, order_id = "controlled-service-fictional", "fictional-" + reference.source.group_id[:16]
    view = OrderView(
        tenant_id=tenant,
        order_id=order_id,
        as_of_source_local="2026-11-04T12:00:00",
        source_manifest_sha256=sha256(FIXTURE_VERSION.encode()),
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
        payment=AmountTotal(known_minor=10000, total_minor=10000, missing_rows=0),
    )
    confirmation = ScenarioConfirmation(
        tenant_id=tenant,
        order_id=order_id,
        available_at_source_local="2026-11-04T11:00:00",
        unit="SIM",
        payment_confirmed=True,
        undelivered_confirmed=True,
        prior_refund_minor=0,
    )
    eligible = intent == "refund" and reference.expected.requested_minor in (None, 10000)
    reason = (
        "ledger_and_state_verified"
        if eligible
        else "request_is_not_the_full_payment"
        if intent == "refund"
        else "reship_requires_inventory_and_shipping_review"
        if intent == "reship"
        else "request_needs_clarification"
        if intent == "clarify"
        else "scoped_recorded_status"
        if intent == "status"
        else "unsupported_request"
    )
    return RoutingCase(
        case_id=sha256(
            ("controlled-service-case-v1|" + pin(reference) + "|" + str(recovery)).encode()
        ),
        group_id=reference.source.group_id,
        language_family="controlled-parent-" + intent,
        split="development",
        source_kind="synthetic",
        reference_source_sha256=reference.reference_file_sha256,
        reference=reference,
        order=view,
        confirmation=confirmation,
        expected=ExpectedWorkflow(
            outcome="refunded"
            if eligible
            else "status"
            if intent == "status"
            else "review_required",
            reason=reason,
            refund_minor=10000 if eligible else None,
        ),
        recovery_required=recovery,
    )


def _scenarios(references: tuple[ControlledServiceReference, ...]) -> tuple[ServiceScenario, ...]:
    if tuple(r.source for r in references) != draft():
        raise ValueError("service package requires the complete original ordered twelve references")
    cases = tuple(_case(r) for r in references)
    scenarios = [ServiceScenario(reference=c, script=ServiceScript()) for c in cases]
    confirm = ServiceScript(customer="confirm", amount_minor=10000)
    scenarios.extend(ServiceScenario(reference=cases[i], script=confirm) for i in (1, 5))
    for reviewer in ("approve", "reject"):
        scenarios.append(
            ServiceScenario(
                reference=cases[1],
                script=ServiceScript(
                    customer="confirm",
                    amount_minor=10000,
                    require_review=True,
                    reviewer=reviewer,
                ),
            )
        )
    scenarios.append(
        ServiceScenario(
            reference=cases[1],
            script=ServiceScript(
                customer="confirm",
                amount_minor=9999,
            ),
        )
    )
    scenarios.append(ServiceScenario(reference=_case(references[1], recovery=True), script=confirm))
    return tuple(scenarios)


class ControlledServicePackage(Contract):
    version: Literal["olist-controlled-service-preparation-v1"] = (
        "olist-controlled-service-preparation-v1"
    )
    references: Annotated[
        tuple[ControlledServiceReference, ...], Field(min_length=12, max_length=12)
    ]
    population: ServicePopulation
    fixture_version: Literal["olist-controlled-service-fictional-fixture-v1"] = FIXTURE_VERSION
    qualification_cohort_approved: Literal[False] = False
    frozen_for_provider: Literal[False] = False
    provider_calls_authorized: Literal[0] = 0
    release_allowed: Literal[False] = False

    @model_validator(mode="after")
    def reconstruct(self) -> Self:
        if self.population.entries != _scenarios(self.references):
            raise ValueError(
                "service preparation differs from its explicit fictional fixture/scripts"
            )
        return self


def prepare(references: tuple[ControlledServiceReference, ...]) -> ControlledServicePackage:
    return ControlledServicePackage(
        references=references, population=ServicePopulation(entries=_scenarios(references))
    )
