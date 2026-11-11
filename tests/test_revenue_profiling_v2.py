"""Measure real local boundaries without recording document, auth, SQL or error text."""

import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from agent_harness.contracts import ModelMessage, ModelRequest, ModelResponse, Usage
from agent_harness.isolated_transport import AttemptTiming, IsolatedTransport

from revenue_profiled_runtime import ProfiledHTTP, ProfiledOperations
from revenue_profiling import AttemptTransport, Recorder, percentile


class InventedWorker:
    def generate(self, request, *, timeout_seconds):
        return ModelResponse(
            provider=request.provider,
            model=request.model,
            output=ModelMessage(role="assistant", content="invented"),
            usage=Usage(
                model_calls=0, input_tokens=None, output_tokens=None, cost=None, cost_currency=None
            ),
        )


def test_nested_intervals_are_inclusive_and_not_added():
    ticks = iter((0, 10, 20, 60, 100))
    recorder = Recorder(clock=lambda: next(ticks), cpu_clock=lambda: 0)
    with recorder.phase("request", input_bytes=32):
        with recorder.phase("extraction"):
            pass
    report = recorder.snapshot()
    outer, inner = report["spans"]
    assert outer["parent"] is None and inner["parent"] == outer["sequence"]
    assert outer["end_ns"] - outer["start_ns"] == 90
    assert inner["end_ns"] - inner["start_ns"] == 40
    assert report["complete"] is True
    assert report["all_subprocesses_instrumented"] is False


@pytest.mark.parametrize(
    "exception,outcome",
    [(ValueError, "error"), (TimeoutError, "timeout"), (asyncio.CancelledError, "cancelled")],
)
def test_exceptions_keep_their_type_and_omit_their_text(exception, outcome):
    recorder = Recorder()
    with pytest.raises(exception):
        with recorder.phase("sql_execute"):
            raise exception("PRIVATE_SQL_PASSWORD_DOCUMENT_CANARY")
    report = recorder.snapshot()
    assert report["stages"]["sql_execute"]["outcomes"][outcome] == 1
    assert "PRIVATE_SQL" not in json.dumps(report)


def test_capacity_and_regressing_clock_are_incomplete_without_masking_exceptions():
    recorder = Recorder(limit=1)
    with recorder.phase("request"):
        assert recorder.snapshot()["complete"] is False
        with recorder.phase("extraction"):
            pass
    assert recorder.snapshot()["dropped"] == 1
    assert recorder.snapshot()["complete"] is False
    ticks = iter((0, 10, 9))
    recorder = Recorder(clock=lambda: next(ticks), cpu_clock=lambda: 0)
    with pytest.raises(TimeoutError):
        with recorder.phase("request"):
            raise TimeoutError("preserved")
    assert recorder.snapshot()["clock_anomalies"] == 1


def test_parent_context_does_not_bleed_between_threads():
    recorder = Recorder()
    barrier = Barrier(2)

    def task():
        with recorder.phase("request"):
            barrier.wait(timeout=10)
            with recorder.phase("extraction"):
                pass

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _: task(), range(2)))
    rows = recorder.snapshot()["spans"]
    parents = {r["sequence"] for r in rows if r["stage"] == "request"}
    assert len(parents) == 2
    assert {r["parent"] for r in rows if r["stage"] == "extraction"} == parents


def test_worker_milestones_keep_unknowns_and_observer_pid_scope():
    recorder = Recorder(clock=lambda: 0)
    timing = AttemptTiming(
        elapsed_seconds=4.0,
        worker_entered_after_seconds=1.0,
        generation_returned_after_seconds=3.0,
        frame_ready_after_seconds=3.5,
        timed_out=False,
        exit_code=0,
    )
    with recorder.phase("gateway"):
        recorder.attempt(timing, started_ns=0)
    report = recorder.snapshot()
    assert report["stages"]["worker_generation"]["p95_seconds"] == 2
    assert report["provider_internal_time_known"] is False
    assert all(r["worker_process_id_known"] is False for r in report["spans"])
    recorder = Recorder(clock=lambda: 0)
    recorder.attempt(timing.model_copy(update={"worker_entered_after_seconds": None}), started_ns=0)
    assert recorder.snapshot()["stages"]["worker_generation"]["observations"] == 0
    with pytest.raises(ValueError):
        recorder.attempt(timing.model_copy(update={"elapsed_seconds": 2.0}), started_ns=0)


def test_fixed_metadata_and_quantiles():
    recorder = Recorder()
    with pytest.raises(ValueError), recorder.phase("private document contents"):
        pass
    with pytest.raises(ValueError), recorder.phase("request", input_bytes=True):
        pass
    assert percentile([], 0.95) is None
    assert percentile([1, 2, 3, 4], 0.95) == 4
    with pytest.raises(ValueError):
        percentile([1], 0)


def test_asgi_response_and_operation_wrappers_preserve_failure_and_payload():
    recorder = Recorder()

    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    messages = []

    async def send(message):
        messages.append(message)

    async def receive():
        return {"type": "http.request", "body": b""}

    asyncio.run(ProfiledHTTP(app, recorder)({"type": "http"}, receive, send))
    assert len(messages) == 2
    assert recorder.snapshot()["stages"]["response_send"]["observations"] == 2

    class Store:
        def apply(self, grant, operation_id, *, run_id):
            assert (grant, operation_id, run_id) == ("grant", "op", "run")
            raise PermissionError("private refusal")

    with pytest.raises(PermissionError):
        ProfiledOperations(Store(), recorder).apply("grant", "op", run_id="run")
    assert recorder.snapshot()["stages"]["apply"]["outcomes"]["error"] == 1


def test_owned_real_fake_process_has_all_observed_milestones_and_is_cleaned_up():
    recorder = Recorder()
    transport = AttemptTransport(IsolatedTransport(InventedWorker()), recorder)
    request = ModelRequest(
        provider="invented",
        model="fake",
        endpoint="in-process",
        messages=(ModelMessage(role="user", content="private invented canary"),),
        parameters={},
    )
    response = transport.generate(request, timeout_seconds=60.0)
    assert response.failure is None and response.usage.model_calls == 0
    report = recorder.snapshot()
    for stage in ("worker_startup", "worker_generation", "worker_serialization", "worker_cleanup"):
        assert report["stages"][stage]["observations"] == 1
    assert "private invented canary" not in json.dumps(report)
    assert transport.delegate.last_timing.exit_code == 0


def test_failed_delegate_cannot_reimport_stale_attempt_timing():
    class Delegate:
        last_timing = AttemptTiming(
            elapsed_seconds=4.0,
            worker_entered_after_seconds=None,
            generation_returned_after_seconds=None,
            frame_ready_after_seconds=None,
            timed_out=True,
            exit_code=1,
        )

        def generate(self, *args, **kwargs):
            raise TimeoutError("new attempt never started")

    recorder = Recorder()
    transport = AttemptTransport(Delegate(), recorder)
    with pytest.raises(TimeoutError):
        transport.generate(None, timeout_seconds=1.0)
    assert len(recorder.snapshot()["spans"]) == 1
