"""H4: reservation races, retry bounds, process deadlines and actual SDK mock errors."""

import json
import multiprocessing
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal

import pytest
from agent_harness.admission import GEMINI_TOKEN_CEILING, GeminiFreeAdmission
from agent_harness.contracts import ModelMessage, ModelRequest, ModelResponse, Usage
from agent_harness.controls import (
    AdmissionDenied,
    BoundedGateway,
    ExecutionPolicy,
    ReservationQuote,
    SharedControls,
)
from agent_harness.gateway import ProviderGateway, failed_response
from agent_harness.isolated_transport import IsolatedTransport
from agent_harness.offline_example import example_context
from control_workers import SdkWorker, Worker
from pydantic import ValidationError


class FakeClock:
    def __init__(self):
        self.origin = example_context("source", "lock").clock
        self.elapsed = 0.0
        self.wall_offset = 0.0
        self.waits = []

    def now(self):
        return self.origin + timedelta(seconds=self.elapsed + self.wall_offset)

    def monotonic(self):
        return self.elapsed

    def sleep(self, seconds):
        self.waits.append(seconds)
        self.elapsed += seconds


def context(**changes):
    value = example_context("invented-source", "invented-lock")
    return value.model_copy(
        update={
            "mode": "fresh_candidate",
            "deadline": value.clock + timedelta(seconds=60),
            "budget": value.budget.model_copy(
                update={"max_model_calls": 10, "max_tokens": 100, "max_cost": Decimal("1")}
            ),
            **changes,
        }
    )


def request(**changes):
    return ModelRequest(
        provider="invented",
        endpoint="in-process",
        model="invented-v1",
        messages=(ModelMessage(role="user", content="invented request"),),
        parameters={},
    ).model_copy(update=changes)


def response(code=None, *, retryable=True, usage=None):
    usage = usage or Usage(
        model_calls=1, input_tokens=2, output_tokens=3, cost=Decimal("0.01"), cost_currency="USD"
    )
    if code:
        return failed_response(
            request(), code, "Invented failure", dispatched=True, retryable=retryable, usage=usage
        )
    return ModelResponse(
        provider="invented",
        model="invented-v1",
        output=ModelMessage(role="assistant", content="invented answer"),
        usage=usage,
    )


class Quote:
    def __init__(self, *, tokens=10, cost="0.1", currency="USD"):
        self.value = ReservationQuote(
            version="invented-cap-v1",
            max_tokens=tokens,
            max_cost=Decimal(cost),
            currency=currency,
            evidence_ref="test:reviewed-cap",
        )

    def quote(self, request):
        return self.value


class Script:
    def __init__(self, results, *, clock=None, delay=0):
        self.results = list(results)
        self.clock, self.delay = clock, delay
        self.seen = []
        self.lock = threading.Lock()

    def generate(self, context, request, *, timeout_seconds):
        with self.lock:
            self.seen.append(timeout_seconds)
            result = self.results.pop(0)
        if self.clock and self.delay:
            self.clock.sleep(self.delay)
        if isinstance(result, Exception):
            raise result
        return result


def controlled(results, *, policy=None, clock=None, quote=None, delay=0):
    clock = clock or FakeClock()
    control = SharedControls(clock=clock)
    script = Script(results, clock=clock, delay=delay)
    return BoundedGateway(script, control, quote or Quote(), policy=policy), script, clock


@pytest.fixture(autouse=True)
def no_live(monkeypatch):
    for key in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"):
        monkeypatch.delenv(key, raising=False)

    def forbidden(*args, **kwargs):
        pytest.fail("control test attempted outbound network")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)


@pytest.mark.parametrize("code", ["rate_limited", "unavailable", "timeout"])
def test_transient_retry_is_bounded_and_usage_includes_failed_attempts(code):
    gateway, script, clock = controlled([response(code), response(code), response()])
    result = gateway.generate(context(), request())
    assert result.failure is None and result.usage.model_calls == 3
    assert result.usage.input_tokens == 6 and result.usage.output_tokens == 9
    assert result.usage.cost == Decimal("0.03") and clock.waits == [0.25, 0.5]
    state = gateway.controls.snapshot(context().tenant_id, context().run_id)
    assert (state.reserved_calls, state.reserved_tokens, state.reserved_cost) == (
        3,
        30,
        Decimal("0.3"),
    )
    assert len(script.seen) == 3 and len(gateway.calls[0].reservations) == 3


@pytest.mark.parametrize("code", ["rate_limited", "unavailable", "timeout"])
def test_attempt_cap_stops_a_permanently_failing_transport(code):
    gateway, script, _ = controlled([response(code)] * 5)
    result = gateway.generate(context(), request())
    assert result.failure.code == code and result.usage.model_calls == 3
    assert len(script.seen) == 3


@pytest.mark.parametrize(
    "code", ["invalid_response", "permission_denied", "budget_exhausted", "replay_mismatch"]
)
def test_nontransient_errors_do_not_retry_even_if_marked_retryable(code):
    gateway, script, clock = controlled([response(code)])
    result = gateway.generate(context(), request())
    assert result.failure.code == code and len(script.seen) == 1 and not clock.waits


def test_retryable_false_disables_retry():
    gateway, script, _ = controlled([response("timeout", retryable=False)])
    assert gateway.generate(context(), request()).failure.code == "timeout"
    assert len(script.seen) == 1


@pytest.mark.parametrize(
    "dimension,value", [("max_model_calls", 1), ("max_tokens", 10), ("max_cost", Decimal("0.1"))]
)
def test_each_budget_dimension_blocks_second_attempt(dimension, value):
    ctx = context()
    ctx = ctx.model_copy(update={"budget": ctx.budget.model_copy(update={dimension: value})})
    gateway, script, _ = controlled([response("timeout"), response()])
    result = gateway.generate(ctx, request())
    assert result.failure.code == "budget_exhausted" and result.usage.model_calls == 1
    assert len(script.seen) == 1


def test_unknown_usage_keeps_full_reservation_and_unknown_observations():
    unknown = Usage(
        model_calls=1, input_tokens=None, output_tokens=None, cost=None, cost_currency=None
    )
    gateway, _, _ = controlled([response("timeout", usage=unknown), response()])
    result = gateway.generate(context(), request())
    assert result.usage.model_calls == 2 and result.usage.input_tokens is None
    assert result.usage.output_tokens is None and result.usage.cost is None
    snapshot = gateway.controls.snapshot(context().tenant_id, context().run_id)
    assert snapshot.reserved_tokens == 20 and snapshot.reserved_cost == Decimal("0.2")
    assert snapshot.observed_usage.cost is None


def test_shared_reservations_are_atomic_across_agents_and_gateway_instances():
    clock = FakeClock()
    controls = SharedControls(clock=clock)
    attempts = Script([response(), response()])
    policy = ExecutionPolicy(max_attempts=1)
    base = context()
    base = base.model_copy(
        update={
            "budget": base.budget.model_copy(
                update={"max_model_calls": 2, "max_tokens": 20, "max_cost": Decimal("0.2")}
            )
        }
    )
    barrier = threading.Barrier(12)

    def run(index):
        gateway = BoundedGateway(attempts, controls, Quote(), policy=policy)
        barrier.wait(timeout=10)
        return gateway.generate(base.model_copy(update={"agent_id": f"agent-{index}"}), request())

    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(run, range(12)))
    assert sum(result.failure is None for result in results) == 2
    assert (
        sum(
            result.failure is not None and result.failure.code == "budget_exhausted"
            for result in results
        )
        == 10
    )
    assert len(attempts.seen) == 2
    state = controls.snapshot(base.tenant_id, base.run_id)
    assert state.reserved_calls == 2 and state.reserved_cost == Decimal("0.2")


def test_runs_and_tenants_have_independent_capacity():
    gateway, _, _ = controlled([response()] * 3, policy=ExecutionPolicy(max_attempts=1))
    for changes in ({}, {"run_id": "other-run"}, {"tenant_id": "other-tenant"}):
        assert gateway.generate(context(**changes), request()).failure is None


@pytest.mark.parametrize("change", ["budget", "deadline"])
def test_registered_run_rejects_limit_drift(change):
    gateway, script, _ = controlled([response()], policy=ExecutionPolicy(max_attempts=1))
    ctx = context()
    gateway.generate(ctx, request())
    replacement = (
        ctx.budget.model_copy(update={"max_model_calls": 999})
        if change == "budget"
        else ctx.deadline + timedelta(seconds=1)
    )
    result = gateway.generate(ctx.model_copy(update={change: replacement}), request())
    assert result.failure.code == "permission_denied" and len(script.seen) == 1


def test_currency_mismatch_and_missing_quote_fail_before_dispatch():
    gateway, script, _ = controlled([], quote=Quote(currency="EUR"))
    assert gateway.generate(context(), request()).failure.code == "budget_exhausted"
    assert not script.seen

    class Missing:
        def quote(self, request):
            raise ValueError("private value")

    gateway, script, _ = controlled([], quote=Missing())
    assert "private" not in gateway.generate(context(), request()).failure.message


@pytest.mark.parametrize(
    "usage",
    [
        Usage(model_calls=2, input_tokens=1, output_tokens=1, cost=None, cost_currency=None),
        Usage(model_calls=1, input_tokens=11, output_tokens=None, cost=None, cost_currency=None),
        Usage(
            model_calls=1,
            input_tokens=1,
            output_tokens=1,
            cost=Decimal("0.11"),
            cost_currency="USD",
        ),
        Usage(
            model_calls=1,
            input_tokens=1,
            output_tokens=1,
            cost=Decimal("0.01"),
            cost_currency="EUR",
        ),
    ],
)
def test_observed_ceiling_breach_freezes_run_and_preserves_actual_usage(usage):
    gateway, script, _ = controlled([response(usage=usage)])
    result = gateway.generate(context(), request())
    assert (
        result.failure.code == "budget_exhausted" and result.usage.model_calls == usage.model_calls
    )
    assert gateway.controls.snapshot(context().tenant_id, context().run_id).frozen
    assert (
        gateway.generate(context(), request()).failure.code == "budget_exhausted"
        and len(script.seen) == 1
    )


def test_decimal_precision_cannot_hide_an_extra_reservation():
    controls = SharedControls(clock=FakeClock())
    ctx = context()
    ctx = ctx.model_copy(
        update={"budget": ctx.budget.model_copy(update={"max_cost": Decimal("0.1")})}
    )
    controls.admit(ctx, request(), Quote(cost="0.1").value, ExecutionPolicy())
    with pytest.raises(AdmissionDenied, match="budget exhausted"):
        controls.admit(
            ctx, request(), Quote(cost="0.00000000000000000000000000001").value, ExecutionPolicy()
        )


def test_monotonic_deadline_ignores_wall_clock_reversal_and_clips_backoff():
    clock = FakeClock()
    ctx = context(deadline=clock.now() + timedelta(seconds=0.1))
    gateway, script, _ = controlled([response("timeout")], clock=clock)
    result = gateway.generate(ctx, request())
    assert result.failure.code == "timeout" and clock.elapsed == pytest.approx(0.1)
    assert script.seen == [pytest.approx(0.1)] and len(gateway.calls[0].reservations) == 1
    clock.wall_offset = -10000
    assert gateway.generate(ctx, request()).failure.code == "timeout" and len(script.seen) == 1


def test_late_success_is_not_returned_and_expired_run_never_dispatches():
    clock = FakeClock()
    ctx = context(deadline=clock.now() + timedelta(seconds=1))
    gateway, script, _ = controlled([response()], clock=clock, delay=2)
    result = gateway.generate(ctx, request())
    assert (
        result.failure.code == "timeout" and result.output is None and result.usage.model_calls == 1
    )
    assert script.seen == [1]
    assert gateway.generate(ctx, request()).failure.code == "timeout" and len(script.seen) == 1


def test_circuit_opens_shares_cooldown_and_allows_one_probe():
    clock = FakeClock()
    controls = SharedControls(clock=clock)
    policy = ExecutionPolicy(
        max_attempts=1, circuit_failure_threshold=1, circuit_cooldown_seconds=2.0
    )
    failing = BoundedGateway(Script([response("unavailable")]), controls, Quote(), policy=policy)
    assert failing.generate(context(), request()).failure.code == "unavailable"
    script = Script([response()])
    second = BoundedGateway(script, controls, Quote(), policy=policy)
    assert (
        second.generate(context(run_id="other"), request()).failure.code == "unavailable"
        and not script.seen
    )
    clock.sleep(2)
    ticket = controls.admit(context(), request(), Quote().value, policy)
    assert second.generate(context(run_id="other"), request()).failure.code == "unavailable"
    controls.finish(ticket, response())
    assert second.generate(context(run_id="other"), request()).failure is None


def test_stale_inflight_success_cannot_close_a_newly_opened_circuit():
    controls = SharedControls(clock=FakeClock())
    policy = ExecutionPolicy(circuit_failure_threshold=1)
    first = controls.admit(context(), request(), Quote().value, policy)
    old = controls.admit(context(), request(), Quote().value, policy)
    controls.finish(first, response("timeout"))
    controls.finish(old, response())
    with pytest.raises(AdmissionDenied, match="circuit"):
        controls.admit(context(), request(), Quote().value, policy)


def test_failed_half_open_probe_reopens_and_other_tenants_are_not_blocked():
    clock = FakeClock()
    controls = SharedControls(clock=clock)
    policy = ExecutionPolicy(circuit_failure_threshold=1, circuit_cooldown_seconds=1.0)
    ticket = controls.admit(context(), request(), Quote().value, policy)
    controls.finish(ticket, response("timeout"))
    clock.sleep(1)
    probe = controls.admit(context(), request(), Quote().value, policy)
    controls.finish(probe, response("timeout"))
    with pytest.raises(AdmissionDenied):
        controls.admit(context(), request(), Quote().value, policy)
    controls.admit(context(tenant_id="other"), request(), Quote().value, policy)


def test_unexpected_exception_freezes_without_echoing_or_refunding():
    gateway, script, _ = controlled([RuntimeError("private detail")])
    result = gateway.generate(context(), request())
    assert result.failure.code == "budget_exhausted" and "private" not in result.canonical_json()
    snapshot = gateway.controls.snapshot(context().tenant_id, context().run_id)
    assert snapshot.frozen and snapshot.reserved_calls == 1 and snapshot.observed_usage.cost is None


@pytest.mark.parametrize(
    "changes",
    [
        {"max_attempts": 0},
        {"max_attempts": 6},
        {"attempt_timeout_seconds": float("nan")},
        {"attempt_timeout_seconds": 0.0},
        {"backoff_seconds": -1.0},
        {"circuit_cooldown_seconds": 0.0},
    ],
)
def test_invalid_control_limits_are_rejected(changes):
    with pytest.raises(ValidationError):
        ExecutionPolicy(**changes)


def test_actual_owned_process_timeout_leaves_no_background_worker(tmp_path):
    marker = tmp_path / "started"
    before = {p.pid for p in multiprocessing.active_children()}
    started = time.monotonic()
    # Include cold Windows spawn/import time while still requiring the worker to
    # enter its hanging body and be reaped within the finite attempt bound.
    result = IsolatedTransport(Worker("hang", str(marker))).generate(
        request(), timeout_seconds=30.0
    )
    elapsed = time.monotonic() - started
    assert result.failure.code == "timeout" and result.usage.model_calls == 1
    assert result.usage.cost is None and marker.exists()
    assert elapsed < 33.0
    assert {p.pid for p in multiprocessing.active_children()} == before


@pytest.mark.parametrize(
    "action,code",
    [
        ("success", None),
        ("crash", "unavailable"),
        ("error", "unavailable"),
        ("oversize", "invalid_response"),
    ],
)
def test_worker_success_crash_exception_and_frame_limit(action, code, capsys):
    result = IsolatedTransport(Worker(action)).generate(request(), timeout_seconds=30.0)
    assert (None if result.failure is None else result.failure.code) == code
    assert "private" not in result.canonical_json() and "private" not in capsys.readouterr().err


def test_isolated_transport_requires_explicit_finite_deadline():
    for timeout in (None, 0.0, -1.0, float("inf"), float("nan")):
        result = IsolatedTransport(Worker()).generate(request(), timeout_seconds=timeout)
        assert result.failure.code == "timeout" and result.usage.model_calls == 0


@pytest.mark.parametrize(
    "status,code", [(429, "rate_limited"), (503, "unavailable"), (408, "timeout")]
)
def test_actual_sdk_errors_retry_through_owned_workers_with_bounded_attempts(
    status, code, tmp_path
):
    from agent_harness.gemini import ENDPOINT, MODEL, PROVIDER

    req = request(provider=PROVIDER, endpoint=ENDPOINT, model=MODEL)
    clock = FakeClock()
    controls = SharedControls(clock=clock)
    raw = ProviderGateway(IsolatedTransport(SdkWorker(status, str(tmp_path))))
    gateway = BoundedGateway(
        raw, controls, Quote(), policy=ExecutionPolicy(max_attempts=2, attempt_timeout_seconds=60.0)
    )
    # Classification includes cold SDK imports; deadline enforcement is tested separately.
    result = gateway.generate(context(), req)
    stages = [json.loads(path.read_text()) for path in tmp_path.glob("*.json")]
    assert result.failure.code == code and result.usage.model_calls == 2, stages
    assert len(stages) == 2, stages
    for attempt in stages:
        assert attempt["phases"] == ["entered", "sdk_loaded", "mock_http", "completed"], stages
        assert attempt["http_calls"] == 1 and attempt["code"] == code, stages
    assert len(raw.exchanges) == 2 and len(gateway.calls[0].attempt_usage) == 2
    assert result.usage.cost is None and "private" not in result.canonical_json()


def test_free_admission_is_exact_route_attested_and_conservative():
    from agent_harness.gemini import ENDPOINT, MODEL, PROVIDER

    with pytest.raises(ValueError):
        GeminiFreeAdmission(free_tier_confirmed=False)
    policy = GeminiFreeAdmission(free_tier_confirmed=True)
    quote = policy.quote(request(provider=PROVIDER, endpoint=ENDPOINT, model=MODEL))
    assert quote.max_tokens == 1_114_112 == GEMINI_TOKEN_CEILING and quote.max_cost == Decimal(0)
    with pytest.raises(ValueError):
        policy.quote(request())


def test_current_retry_controller_executes_over_strict_replayed_attempts():
    from agent_harness.controls import ReplayAttempts
    from agent_harness.gateway import ModelExchange
    from agent_harness.recording import RecordingProvenance, make_recording
    from agent_harness.replay import ReplayBinding, StrictReplayGateway

    source = context()
    value = make_recording(
        tuple(
            ModelExchange(context=source, occurrence=i, request=request(), response=result)
            for i, result in enumerate((response("timeout"), response()), 1)
        ),
        RecordingProvenance(
            source_kind="synthetic",
            source_version="invented-h4",
            snapshot_ref=source.versions.data_snapshot,
            policy_version=source.versions.policy,
            scorer_version="invented-scorer",
            content_policy="invented-only",
            content_review_ref="test:review",
        ),
    )
    current = source.model_copy(update={"mode": "strict_replay", "run_id": "current-replay"})
    replay = StrictReplayGateway(value, (ReplayBinding(recorded=source, current=current),))
    gateway = BoundedGateway(ReplayAttempts(replay), SharedControls(clock=FakeClock()), Quote())
    result = gateway.generate(current, request())
    assert result.failure is None and result.usage.model_calls == 2
    replay.assert_complete()


def test_bare_live_gateway_cannot_be_adapted_as_replay_attempts():
    from agent_harness.controls import ReplayAttempts

    with pytest.raises(TypeError):
        ReplayAttempts(ProviderGateway(Worker()))


@pytest.mark.parametrize("mode", ["strict_replay", "offline_fake"])
def test_controlled_modes_cannot_dispatch_live_attempt_gateway(mode):
    script = Script([response()])
    gateway = BoundedGateway(script, SharedControls(clock=FakeClock()), Quote())
    result = gateway.generate(context(mode=mode), request())
    assert result.failure.code == "permission_denied" and not script.seen


def test_replay_mismatch_remains_infrastructure_failure_and_freezes_reservation():
    from agent_harness.controls import ReplayAttempts
    from agent_harness.gateway import ModelExchange
    from agent_harness.recording import RecordingProvenance, make_recording
    from agent_harness.replay import ReplayBinding, ReplayMismatch, StrictReplayGateway

    source = context()
    value = make_recording(
        (ModelExchange(context=source, occurrence=1, request=request(), response=response()),),
        RecordingProvenance(
            source_kind="synthetic",
            source_version="invented-h4",
            snapshot_ref=source.versions.data_snapshot,
            policy_version=source.versions.policy,
            scorer_version="invented-scorer",
            content_policy="invented-only",
            content_review_ref="test:review",
        ),
    )
    current = source.model_copy(update={"mode": "strict_replay", "run_id": "current-replay"})
    replay = StrictReplayGateway(value, (ReplayBinding(recorded=source, current=current),))
    controls = SharedControls(clock=FakeClock())
    gateway = BoundedGateway(ReplayAttempts(replay), controls, Quote())
    with pytest.raises(ReplayMismatch):
        gateway.generate(current, request(parameters={"temperature": 0}))
    with pytest.raises(ReplayMismatch):
        replay.assert_complete()
    state = controls.snapshot(current.tenant_id, current.run_id)
    assert state.frozen and state.reserved_calls == 1 and not gateway.calls


@pytest.mark.parametrize("timeout", [0.0, -1.0, float("inf"), float("nan")])
def test_gemini_invalid_timeout_fails_before_http(timeout):
    import httpx
    from agent_harness.gemini import ENDPOINT, MODEL, PROVIDER, GeminiTransport

    def forbidden(value):
        pytest.fail("invalid timeout dispatched HTTP")

    value = request(provider=PROVIDER, endpoint=ENDPOINT, model=MODEL)
    transport = GeminiTransport(
        "invented-key", free_tier_confirmed=True, http_transport=httpx.MockTransport(forbidden)
    )
    result = transport.generate(value, timeout_seconds=timeout)
    assert result.failure.code == "timeout" and result.usage.model_calls == 0


def test_completed_frame_after_startup_deadline_cannot_be_returned(monkeypatch):
    from types import SimpleNamespace

    import agent_harness.isolated_transport as isolated

    clock = FakeClock()
    actual = multiprocessing.get_context("spawn")
    joins = []
    closed = []
    data = response().canonical_json().encode("utf-8")

    class FinishedDuringStartup:
        exitcode = 0

        def __init__(self, *, target, args, daemon):
            self.buffer, self.size = args[-2:]

        def start(self):
            # Simulate expensive bootstrap followed by a valid, but late, response.
            clock.sleep(2.0)
            self.buffer[: len(data)] = data
            self.size.value = len(data)

        def join(self, seconds):
            joins.append(seconds)

        def is_alive(self):
            return False

        def close(self):
            closed.append(True)

    ctx = SimpleNamespace(
        RawArray=actual.RawArray, RawValue=actual.RawValue, Process=FinishedDuringStartup
    )
    monkeypatch.setattr(isolated, "time", SimpleNamespace(monotonic=clock.monotonic))
    monkeypatch.setattr(
        isolated, "multiprocessing", SimpleNamespace(get_context=lambda method: ctx)
    )
    result = isolated.IsolatedTransport(Worker()).generate(request(), timeout_seconds=1.0)
    assert result.failure.code == "timeout" and result.output is None
    assert result.usage.model_calls == 1 and result.usage.cost is None
    assert joins == [0.0] and closed == [True]
