"""Invented planner decisions through the actual customer-confirmed service; no SDK."""

import uuid

import pytest
from agent_harness.contracts import ModelMessage, ModelRequest
from olist_support.business_contracts import BusinessReview
from olist_support.console_cases import MODEL_SERVICE_AGENT, MODEL_SERVICE_CANDIDATE, CaseStore
from olist_support.console_contracts import Decision, Submission
from olist_support.customer_intent import CustomerIntentStore
from olist_support.routing_contracts import RoutingPlan
from olist_support.workflow import FixedPlanner, IntentDecision, IntentPlan, RoutingGatewayPlanner
from test_olist_business import app as app
from test_olist_console import actors, customer_confirm, observed
from test_olist_console import console as console
from test_olist_workflow import InventedGateway, context


def model_context():
    ctx = context(event=uuid.uuid4().hex, run=uuid.uuid4().hex)
    return ctx.model_copy(
        update={
            "agent_id": MODEL_SERVICE_AGENT,
            "versions": ctx.versions.model_copy(update={"candidate": MODEL_SERVICE_CANDIDATE}),
        }
    )


def submit(console, plan, *, review=False, planner=None):
    order, operator, reviewer = actors(console)
    ctx = model_context()
    store = CaseStore(
        lambda: console[0].connect_trial(console[1]), planner=planner or FixedPlanner(plan)
    )
    request = Submission(
        event_key=uuid.uuid4().hex,
        order_id=order,
        text="Invented original customer text, not a trusted action.",
        intent="refund",
        require_review=review,
    )
    case = store.submit(operator, request, ctx, run_limit_minor=10000)
    return store, case, operator, reviewer, ctx, request


@pytest.mark.parametrize("intent", ["clarify", "unsupported", "review", "status", "reship"])
def test_saved_fine_intent_never_falls_back_to_staff_refund_placeholder(console, intent):
    plan = RoutingPlan(routing_version="olist-intent-routing-v2", intent=intent)
    store, case, _, reviewer, _, _ = submit(console, plan)
    assert case.intent_source == "planner" and case.intent_decision.plan == plan
    assert case.status == ("status" if intent == "status" else "review_required")
    assert case.command is None and case.action_digest is None
    assert observed(console, case) == ((0, 0), (0, 0), 0)
    if case.status == "review_required":
        with pytest.raises(BusinessReview):
            store.decide(
                reviewer,
                case.case_id,
                Decision(
                    decision="approve",
                    expected_version=case.version,
                    action_digest=None,
                    rationale="Cannot invent a refund.",
                ),
            )


@pytest.mark.parametrize("amount", [None, 5000, 3000, 0, 10001])
def test_requested_amount_survives_policy_snapshot_and_customer_portal(console, amount):
    plan = RoutingPlan(
        routing_version="olist-intent-routing-v2", intent="refund", requested_minor=amount
    )
    _, case, _, _, _, _ = submit(console, plan)
    assert case.intent_decision.plan == plan
    assert observed(console, case) == ((0, 0), (0, 0), 0)
    # Customer HTTP composition has no model; it must use the saved typed decision.
    reader = CaseStore(lambda: console[0].connect_trial(console[1]))
    if amount not in (None, 5000):
        assert case.command is None and case.proposal.action == "review"
        return
    assert case.command.amount_minor == 5000
    customer, payload = customer_confirm(reader, case, console)
    result = CustomerIntentStore(reader).execute(
        customer, case.case_id, payload, run_limit_minor=10000
    )
    assert result.status == "committed" and result.intent_decision.plan == plan
    assert observed(console, case) == ((5000, 1), (1, 5000), 1)


def test_wrong_planner_refund_cannot_commit_without_independent_customer_choice(console):
    _, case, _, _, _, _ = submit(
        console, RoutingPlan(routing_version="olist-intent-routing-v2", intent="refund")
    )
    assert case.result.reason == "customer_confirmation_required" and case.command is not None
    assert observed(console, case) == ((0, 0), (0, 0), 0)


def test_actual_routing_parser_keeps_usage_and_text_only_wire_through_customer_commit(console):
    gateway = InventedGateway(
        '{"routing_version":"olist-intent-routing-v2","intent":"refund","requested_minor":5000}'
    )
    route = ModelRequest(
        provider="invented",
        endpoint="in-process",
        model="invented-model",
        messages=(ModelMessage(role="user", content="unused"),),
        parameters={},
    )
    store, case, _, _, ctx, request = submit(
        console, None, planner=RoutingGatewayPlanner(gateway, route)
    )
    assert len(gateway.requests) == 1 and case.intent_decision.usage.model_calls == 1
    wire = gateway.requests[0]
    assert tuple(m.role for m in wire.messages) == ("system", "user")
    assert wire.messages[1].content == request.text and wire.tools == ()
    reader = CaseStore(store.connect)
    customer, payload = customer_confirm(reader, case, console)
    intent = CustomerIntentStore(reader)
    result = intent.execute(customer, case.case_id, payload, run_limit_minor=10000)
    assert result.result.usage == case.result.usage
    assert result.result.usage_run_id == ctx.run_id
    assert intent.execute(customer, case.case_id, payload, run_limit_minor=10000) == result
    assert len(gateway.requests) == 1 and observed(console, case) == ((5000, 1), (1, 5000), 1)


def test_required_staff_review_remains_additional_to_model_and_customer(console):
    store, case, _, reviewer, _, _ = submit(
        console,
        RoutingPlan(routing_version="olist-intent-routing-v2", intent="refund"),
        review=True,
    )
    assert case.command is not None and case.request.require_review
    with pytest.raises((PermissionError, BusinessReview)):
        store.resume(reviewer, case.case_id, case.action_digest, run_limit_minor=10000)
    approved = store.decide(
        reviewer,
        case.case_id,
        Decision(
            decision="approve",
            expected_version=case.version,
            action_digest=case.action_digest,
            rationale="Invented review.",
        ),
    )
    with pytest.raises(BusinessReview):
        store.resume(reviewer, case.case_id, approved.action_digest, run_limit_minor=10000)
    customer_confirm(store, approved, console)
    assert (
        store.resume(reviewer, case.case_id, approved.action_digest, run_limit_minor=10000).status
        == "committed"
    )


def test_wrong_candidate_identity_is_rejected_before_planner_dispatch(console):
    order, operator, _ = actors(console)
    store = CaseStore(
        lambda: console[0].connect_trial(console[1]),
        planner=FixedPlanner(
            RoutingPlan(routing_version="olist-intent-routing-v2", intent="refund")
        ),
    )
    with pytest.raises(PermissionError):
        store.submit(
            operator,
            Submission(
                event_key=uuid.uuid4().hex, order_id=order, text="Invented", intent="refund"
            ),
            context(),
            run_limit_minor=10000,
        )


def test_checkpoint_recovery_keeps_original_run_and_does_not_call_planner_again(
    console, monkeypatch
):
    calls = []

    class Counting:
        def plan(self, ctx, request):
            calls.append((ctx, request))
            return IntentDecision(
                plan=RoutingPlan(routing_version="olist-intent-routing-v2", intent="refund")
            )

    order, operator, _ = actors(console)
    store = CaseStore(lambda: console[0].connect_trial(console[1]), planner=Counting())
    ctx = model_context()
    request = Submission(
        event_key=uuid.uuid4().hex, order_id=order, text="Invented", intent="refund"
    )
    original_save = store.save

    def fail_save(connection, case):
        raise RuntimeError("Invented loss after durable graph, before case update")

    monkeypatch.setattr(store, "save", fail_save)
    with pytest.raises(RuntimeError):
        store.submit(operator, request, ctx, run_limit_minor=10000)
    monkeypatch.setattr(store, "save", original_save)
    pending_case = store.listing(operator)[0]
    with pytest.raises(BusinessReview):
        CaseStore(store.connect).run_request(operator, pending_case.case_id, run_limit_minor=10000)
    recovered = store.run_request(operator, pending_case.case_id, run_limit_minor=10000)
    assert len(calls) == 1
    actual, wire = calls[0]
    assert (
        actual.run_id == ctx.run_id
        and actual.deadline == ctx.deadline
        and actual.budget == ctx.budget
    )
    assert wire.text == request.text and recovered.intent_decision.execution_run_id == ctx.run_id
    assert recovered.status == "review_required" and recovered.command.amount_minor == 5000
    assert observed(console, recovered) == ((0, 0), (0, 0), 0)


def test_planner_failure_and_unversioned_success_cannot_create_service_authority(console):
    class Failed:
        def plan(self, ctx, request):
            return IntentDecision(plan=IntentPlan(intent="review"), failure_code="timeout")

    _, failed, _, _, _, _ = submit(console, None, planner=Failed())
    assert failed.status == "review_required" and failed.command is None
    assert failed.intent_decision.failure_code == "timeout"
    assert observed(console, failed) == ((0, 0), (0, 0), 0)
    _, legacy, _, _, _, _ = submit(console, IntentPlan(intent="refund"))
    assert legacy.status == "needs_recovery" and legacy.command is None
    assert observed(console, legacy) == ((0, 0), (0, 0), 0)
