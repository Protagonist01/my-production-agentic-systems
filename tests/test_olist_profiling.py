"""Exact clocks and real planner parsing exercise opt-in content-free timing."""

import asyncio
import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from agent_harness.contracts import ModelMessage, ModelRequest
from olist_support.routing_contracts import RoutingPlan
from olist_support.workflow import WorkflowRequest
from test_olist_workflow import InventedGateway, context

from olist_profiling import ProfiledCases, ProfiledHTTP, ProfiledPlanner, Recorder


def test_nested_stages_known_clock_errors_no_payload_and_no_double_count_claim():
    clock = iter((0, 10, 20, 40, 50, 90))
    r = Recorder(clock=lambda: next(clock))
    with r.phase("request"):
        with r.phase("planner"):
            with pytest.raises(ValueError), r.phase("parse"):
                raise ValueError("SECRET SENTINEL")
    s = r.snapshot()
    assert [(x["sequence"], x["parent"], x["elapsed_ns"], x["failed"]) for x in s["spans"]] == [
        (0, None, 90, False),
        (1, 0, 40, False),
        (2, 1, 20, True),
    ]
    assert "SECRET" not in json.dumps(s)
    assert s["capacity_complete"] and not s["all_subprocesses_instrumented"]
    assert s["stages"]["gateway"]["percentiles_ns"]["0.95"] is None


def test_capacity_and_active_coverage_do_not_silently_pass():
    r = Recorder(limit=1)
    with r.phase("request"):
        assert not r.snapshot()["finalized"]
        with r.phase("parse"):
            pass
    s = r.snapshot()
    assert s["dropped"] == 1 and not s["capacity_complete"]
    assert len(s["spans"]) == 1
    assert not r.coverage(("request",))["complete"]
    with pytest.raises(ValueError):
        with r.phase("SECRET arbitrary stage"):
            pass


def test_per_request_coverage_does_not_borrow_stages_from_other_requests():
    r = Recorder()
    with r.phase("request"), r.phase("gateway"):
        pass
    with r.phase("request"), r.phase("parse"):
        pass
    c = r.coverage(("request", "gateway", "parse"))
    assert c["requests"] == 2 and c["complete_requests"] == 0
    assert c["missing_stage_counts"] == {"request": 0, "gateway": 1, "parse": 1}
    with pytest.raises(ValueError):
        r.coverage(())


def test_threads_do_not_share_parent_context():
    r = Recorder()

    def worker():
        with r.phase("request"), r.phase("parse"):
            pass

    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(lambda _: worker(), range(9)))
    rows = r.snapshot()["spans"]
    requests = {x["sequence"] for x in rows if x["stage"] == "request"}
    assert len(rows) == 18 and len(requests) == 9
    assert all(x["parent"] in requests for x in rows if x["stage"] == "parse")


def test_actual_planner_gateway_parse_and_fixed_failure_keep_contract():
    r = Recorder()
    plan = RoutingPlan(routing_version="olist-intent-routing-v2", intent="unsupported")
    gateway = InventedGateway(plan.canonical_json())
    route = ModelRequest(
        provider="invented",
        endpoint="in-process",
        model="invented-v1",
        messages=(ModelMessage(role="user", content="unused"),),
        parameters={},
    )
    planner = ProfiledPlanner(gateway, route, r)
    request = WorkflowRequest(order_id="invented-order", text="SECRET poem request")
    assert planner.plan(context(), request).plan == plan
    assert len(gateway.requests) == 1
    stages = r.snapshot()["stages"]
    assert all(stages[x]["observations"] == 1 for x in ("planner", "gateway", "parse"))
    assert "SECRET" not in json.dumps(r.snapshot())
    failed = ProfiledPlanner(InventedGateway('{"intent":"refund"}'), route, r)
    assert failed.plan(context(), request).failure_code == "invalid_intent_response"
    assert r.snapshot()["stages"]["parse"]["failures"] == 1


def test_asgi_profiles_http_and_preserves_lifespan_failure():
    r = Recorder()
    seen = []

    async def app(scope, receive, send):
        seen.append(scope["type"])
        if scope["type"] == "http":
            raise RuntimeError("SECRET")

    wrapped = ProfiledHTTP(app, r)

    async def invoke():
        with pytest.raises(RuntimeError):
            await wrapped({"type": "http"}, None, None)
        await wrapped({"type": "lifespan"}, None, None)

    asyncio.run(invoke())
    assert seen == ["http", "lifespan"]
    assert r.snapshot()["stages"]["request"]["failures"] == 1


def test_case_wrapper_times_refused_real_operation_without_database_or_secret():
    def refused():
        raise PermissionError("SECRET database")

    r = Recorder()
    store = ProfiledCases(refused, recorder=r)
    with pytest.raises(PermissionError), store.connection():
        pass
    assert r.snapshot()["stages"]["database_context"]["failures"] == 1
    assert "SECRET" not in json.dumps(r.snapshot())
