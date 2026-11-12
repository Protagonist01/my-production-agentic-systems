"""Real threads/processes, privacy, missing coverage and unchanged HTTP boundaries."""

import asyncio
import json
import multiprocessing
import os
from concurrent.futures import ThreadPoolExecutor

import pytest
from starlette.testclient import TestClient
from supply_chain.console_api import create_app
from supply_worker_fixtures import worker_dies, worker_error, worker_hangs, worker_ok
from test_supply_intake_diagnostics import Auth, Service

from supply_profiled_runtime import ProfiledHTTP, ProfiledStep, private_output
from supply_profiling import Recorder, run_worker


def test_nested_concurrent_privacy_and_required_coverage():
    recorder = Recorder()

    def request(index):
        with recorder.phase("request"), recorder.incident("PRIVATE_TENANT", "PRIVATE_EVENT"):
            with recorder.phase("assessment"):
                with recorder.phase("planning"):
                    pass
            if index == 0:
                with recorder.phase("sql_fetch"):
                    pass

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(request, (0, 1)))
    report = recorder.snapshot(required=("planning", "sql_fetch"))
    assert report["coverage"]["roots"] == 2
    assert report["coverage"]["complete_roots"] == 1
    assert not report["coverage"]["complete"]
    assert recorder.snapshot(required=("planning",))["coverage"]["complete"]
    assert len({s["trace_id"] for s in report["spans"]}) == 2
    assert len({s["incident_ref"] for s in report["spans"] if s["incident_ref"]}) == 1
    assert "PRIVATE_" not in json.dumps(report)
    assert not report["remote_exported"]


def test_errors_timeout_cancellation_capacity_and_backwards_clock():
    recorder = Recorder(limit=3)
    for error in (ValueError("private"), TimeoutError(), asyncio.CancelledError()):
        with pytest.raises(type(error)), recorder.phase("request"):
            raise error
    with recorder.phase("request"):
        pass
    report = recorder.snapshot(required=("request",))
    assert report["dropped"] == 1 and not report["coverage"]["complete"]
    assert {s["outcome"] for s in report["spans"]} == {"error", "timeout", "cancelled"}
    ticks = iter((10, 9))
    recorder = Recorder(clock=lambda: next(ticks))
    with recorder.phase("request"):
        pass
    assert recorder.snapshot()["clock_anomalies"] == 1
    with pytest.raises(ValueError):
        with recorder.phase("PRIVATE_NAME"):
            pass


@pytest.mark.parametrize(
    ("fn", "expected"), [(worker_ok, "ok"), (worker_error, "error"), (worker_dies, "crashed")]
)
def test_actual_worker_context_and_cleanup(fn, expected):
    recorder = Recorder()
    before = {p.pid for p in multiprocessing.active_children()}
    result = run_worker(recorder, fn, timeout_seconds=60)
    assert result.outcome == expected
    report = recorder.snapshot(required=("worker_launch", "worker_cleanup"))
    assert report["coverage"]["complete"]
    assert not ({p.pid for p in multiprocessing.active_children()} - before)
    assert "PRIVATE_" not in json.dumps(report)
    if result.child_profile:
        parent = next(s for s in report["spans"] if s["stage"] == "worker")
        child = next(s for s in result.child_profile["spans"] if s["stage"] == "worker_execution")
        assert child["parent_span"] == parent["span_id"]
        assert child["trace_id"] == parent["trace_id"]
        assert child["process_id"] != os.getpid()
        assert "PRIVATE_" not in json.dumps(result.child_profile)


def test_actual_worker_timeout_retains_missing_child_execution():
    recorder = Recorder()
    result = run_worker(recorder, worker_hangs, timeout_seconds=0.05)
    assert result.outcome == "timeout" and result.child_profile is None
    report = recorder.snapshot()
    assert "worker_execution" in report["unobserved_stages"]
    assert any(s["outcome"] == "timeout" for s in report["spans"])


def test_real_asgi_status_with_no_headers_body_or_paths_retained():
    recorder = Recorder()
    service = Service()
    app = ProfiledHTTP(
        create_app(service, Auth(), origin="http://127.0.0.1:8877", trial_id="boundary"), recorder
    )
    with TestClient(app, base_url="http://127.0.0.1:8877") as client:
        response = client.post("/api/assess", json={"text": "PRIVATE_POEM"})
    assert response.status_code == 422
    report = recorder.snapshot(required=("response_send",))
    assert report["coverage"]["complete"]
    assert next(s for s in report["spans"] if s["stage"] == "request")["http_status"] == 422
    assert "PRIVATE_" not in json.dumps(report)
    assert service.effects == []


def test_step_proxy_preserves_arguments_results_and_errors():
    class Step:
        async def run(self, key, fn):
            return await fn()

        async def send_event(self, key, events):
            return events

        async def wait_for_event(self, key, **kwargs):
            assert kwargs["event"] == "supply/shipment.reviewed"
            raise TimeoutError("PRIVATE_EVENT")

    recorder = Recorder()

    async def exercise():
        with recorder.phase("event"):
            step = ProfiledStep(Step(), recorder)

            async def fn():
                return "PRIVATE_VALUE"

            assert await step.run("private-key", fn) == "PRIVATE_VALUE"
            assert await step.send_event("private-key", ["PRIVATE_EVENT"]) == ["PRIVATE_EVENT"]
            with pytest.raises(TimeoutError):
                await step.wait_for_event("private-key", event="supply/shipment.reviewed")

    asyncio.run(exercise())
    report = recorder.snapshot(required=("event_step", "event_send", "approval_wait"))
    assert report["coverage"]["complete"]
    assert report["stages"]["approval_wait"]["outcomes"]["timeout"] == 1
    assert "PRIVATE_" not in json.dumps(report)


def test_profile_output_cannot_overwrite_or_live_in_git(tmp_path):
    path = tmp_path / "profile.json"
    path.write_text("preserve")
    with pytest.raises(ValueError):
        private_output(path)
    repo = tmp_path / "checkout"
    repo.mkdir()
    (repo / ".git").write_text("gitdir: elsewhere")
    with pytest.raises(ValueError):
        private_output(repo / "profile.json")


def test_actual_sdk_step_proxy_preserves_native_pending_wait_replay():
    from inngest.experimental import mocked
    from supply_chain.events import ShipmentWake, event_for

    from supply_profiled_runtime import profiled_functions

    class Handlers:
        def reconcile(self, wake):
            return {"status": "pending"}

        def wait_seconds(self, wake, status):
            return 1

    recorder = Recorder()
    sdk = mocked.Inngest(app_id="supply-profiled-unit", is_production=False)
    functions = profiled_functions(sdk, Handlers(), recorder)
    wake = ShipmentWake(
        tenant_id="invented",
        actor_id="operator",
        event_id="invented",
        shipment_id="invented-shipment",
    )
    result = mocked.trigger(
        functions[1],
        event_for(wake, "supply/shipment.requested"),
        sdk,
        step_stubs={f"approval-wakeup-{i}": mocked.Timeout for i in range(3)},
    )
    assert result.status is mocked.Status.COMPLETED and result.output == {"status": "pending"}
    report = recorder.snapshot()
    assert report["stages"]["approval_wait"]["observed"] > 0
    assert report["stages"]["event_step"]["observed"] > 0
    assert "queue_wait" in report["unobserved_stages"]
