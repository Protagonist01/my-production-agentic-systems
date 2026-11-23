"""Compose the inspected language candidate with the existing protected SIM workflow.

This adapter creates no provider, credential, budget grant or action authority.
The caller must supply a separately bounded gateway. Quote checks are mechanical;
they do not establish that a price mention is really a requested refund amount.
"""

from collections.abc import Callable

from agent_harness.contracts import ModelGateway, ModelRequest, RunContext
from olist_support.routing_contracts import RoutingPlan
from olist_support.workflow import IntentDecision, WorkflowRequest

from docs.evaluation.olist_semantic_candidate import SemanticOutput, parse, request

VERSION = "olist-portfolio-semantic-planner-v1"


def project(value: SemanticOutput) -> RoutingPlan:
    """Never turn unknown money or a non-SIM amount into an implicit full refund."""
    intent = value.intent
    if intent == "refund" and (
        value.amount_status == "unclear"
        or (value.amount_status == "explicit" and value.currency != "SIM")
    ):
        return RoutingPlan(routing_version="olist-intent-routing-v2", intent="review")
    return RoutingPlan(
        routing_version="olist-intent-routing-v2",
        intent=intent,
        requested_minor=value.requested_minor if intent == "refund" else None,
    )


class DemoPlanner:
    def __init__(
        self,
        gateway: ModelGateway,
        *,
        request_builder: Callable[[str], ModelRequest] = request,
    ) -> None:
        self.gateway = gateway
        self.request_builder = request_builder

    def plan(self, context: RunContext, original: WorkflowRequest) -> IntentDecision:
        wire = self.request_builder(original.text)
        response = self.gateway.generate(context, wire)
        failure: str | None = response.failure.code if response.failure else None
        plan = RoutingPlan(routing_version="olist-intent-routing-v2", intent="review")
        if failure is None:
            try:
                if (
                    response.provider != wire.provider
                    or response.model != wire.model
                    or response.output is None
                    or response.output.tool_calls
                    or response.output.content is None
                ):
                    raise ValueError("wrong route or non-text response")
                plan = project(parse(original.text, response.output.content))
            except ValueError:
                failure = "invalid_semantic_response"
        return IntentDecision(plan=plan, usage=response.usage, failure_code=failure)
