"""V2 no-effect routes persist through real checkpoint close/reopen and redelivery."""

import uuid

import pytest
from olist_support.release import collect_state
from olist_support.routing_contracts import RoutingPlan
from olist_support.workflow import FixedPlanner, SupportWorkflow, WorkflowRequest
from olist_support.workflow_postgres import saver
from test_olist_business import app as app
from test_olist_business import seed
from test_olist_workflow import context


@pytest.mark.parametrize(
    "intent,reason",
    [
        ("clarify", "request_needs_clarification"),
        ("unsupported", "unsupported_request"),
    ],
)
def test_v2_review_reopens_without_effect_or_second_planning(app, intent, reason):
    server, trial, store = app
    grant, command = seed(app)
    c = context(event=uuid.uuid4().hex, run=uuid.uuid4().hex)
    request = WorkflowRequest(order_id=command.order_id, text="Invented routing-state witness.")
    with server.connect(trial.name) as admin:
        before = collect_state(admin)
    with saver(lambda: server.connect_trial(trial)) as checkpoints:
        first = SupportWorkflow(
            store,
            FixedPlanner(RoutingPlan(routing_version="olist-intent-routing-v2", intent=intent)),
        ).run(c, request, grant, checkpoints, run_limit_minor=10000)
    assert first.outcome == "review_required" and first.reason == reason and first.receipt is None

    class Forbidden:
        def plan(self, *_):
            raise AssertionError("saved v2 route must not invoke another planner")

    with saver(lambda: server.connect_trial(trial)) as checkpoints:
        resumed = SupportWorkflow(store, Forbidden()).run(
            c.model_copy(update={"run_id": c.run_id + "-delivery"}),
            request,
            grant,
            checkpoints,
            run_limit_minor=10000,
        )
    with server.connect(trial.name) as admin:
        after = collect_state(admin)
    assert resumed == first and after == before
