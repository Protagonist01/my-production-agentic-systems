"""Real gateway and SQLite accounting, invented outputs, zero provider calls."""

import sqlite3
from datetime import timedelta

import pytest
from agent_harness.gateway import failed_response
from test_controls import FakeClock
from test_olist_demo_study import Scripted, history

from olist_demo_acceptance import digest
from olist_demo_budget_readback import inspect
from olist_demo_resilience_study import (
    TABLES,
    Scope,
    capture,
    initialize,
    policy,
    readback,
    slots,
    task_context,
)


def fixture(tmp_path):
    path, parent = history(tmp_path)
    scope = Scope(
        **parent.model_dump(
            exclude={
                "version",
                "schedule",
                "max_attempts",
                "max_tokens",
                "http_seconds",
                "parent_seconds",
                "lifetime_ceiling",
                "retained_bound_slots",
            }
        ),
        retained_bound_slots=16,
        lifetime_ceiling=312,
        policy=policy(),
        schedule=slots(),
    )
    clock = FakeClock()
    clock.origin = scope.starts_at + timedelta(seconds=1)
    return initialize(path, scope), scope, clock


def test_complete_mock_tasks_are_not_provider_quality_and_raw_accounting_is_additive(tmp_path):
    ledger, scope, clock = fixture(tmp_path)
    scripted = Scripted()
    result = capture(ledger, scripted, clock=clock)
    assert result == readback(ledger)
    assert len(scripted.calls) == result["reserved_attempts"] == 146
    assert result["completed_tasks"] == 146 and result["unfinished_tasks"] == 0
    assert result["domain"]["scheduled_joint_agreement"] == 1
    assert not result["model_quality_observed"] and not result["demo_release_accepted"]
    assert result["provider_attempts_counted"] == 0
    report = inspect(ledger.path)
    assert report["total_consumed"] == 150 and report["latest_recorded_ceiling"] == 312
    assert report["retained_bound_slots"] == 16
    with ledger.connect() as db:
        from olist_demo_budget_readback import historical_hash

        assert historical_hash(db, TABLES) == scope.historical_sha256
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            db.execute("DELETE FROM olist_r2_results")


def test_transient_failure_retries_same_task_once_and_preserves_unknown_usage(tmp_path):
    ledger, scope, clock = fixture(tmp_path)

    class Transient(Scripted):
        def generate(self, wire, *, timeout_seconds):
            if not self.calls:
                self.calls.append(wire)
                return failed_response(
                    wire, "unavailable", "Invented HTTP 503", dispatched=True, retryable=True
                )
            return super().generate(wire, timeout_seconds=timeout_seconds)

    transport = Transient()
    result = capture(ledger, transport, clock=clock)
    assert result["completed_tasks"] == 146 and result["reserved_attempts"] == 147
    assert result["raw_provider_failures"] == result["raw_unknown_token_rows"] == 1
    assert result["raw_failure_rate"] == 1 / 147 and result["retried_tasks"] == 1
    assert result["raw_reported_model_calls"] == 147
    assert result["domain"]["scheduled_joint_agreement"] == 1
    assert clock.waits == [1.0]
    with ledger.connect() as db:
        import json

        response = json.loads(
            db.execute("SELECT response FROM olist_r2_task_results WHERE ordinal=1").fetchone()[0]
        )
    assert response["usage"]["model_calls"] == 2
    assert response["usage"]["input_tokens"] is None


@pytest.mark.parametrize("kind", ["meaning", "schema", "permission"])
def test_no_retry_for_meaning_schema_or_permission(tmp_path, kind):
    ledger, _, clock = fixture(tmp_path)

    class Wrong(Scripted):
        def generate(self, wire, *, timeout_seconds):
            value = super().generate(wire, timeout_seconds=timeout_seconds)
            if len(self.calls) != 3:
                return value
            if kind == "permission":
                return failed_response(wire, "permission_denied", "Invented", dispatched=True)
            return value.model_copy(
                update={
                    "output": value.output.model_copy(
                        update={
                            "content": '{"intent":"review"}'
                            if kind == "schema"
                            else self.values[
                                slots()[1].request.messages[-1].content
                            ].canonical_json()
                        }
                    )
                }
            )

    transport = Wrong()
    result = capture(ledger, transport, clock=clock)
    assert len(transport.calls) == (3 if kind == "permission" else 146)
    assert not clock.waits or all(w == 60 for w in clock.waits)
    assert result["raw_provider_failures"] == (1 if kind == "permission" else 0)
    if kind == "permission":
        assert result["stopped"]
    else:
        assert result["domain"]["scheduled_joint_agreement"] < 1


def test_late_output_cannot_pass_canary_or_receive_new_deadline(tmp_path):
    ledger, _, clock = fixture(tmp_path)

    class Late(Scripted):
        def generate(self, wire, *, timeout_seconds):
            clock.sleep(31)
            return super().generate(wire, timeout_seconds=timeout_seconds)

    report = capture(ledger, Late(), clock=clock)
    assert report["stopped"] and not report["both_canaries_passed"]
    assert report["reserved_attempts"] == report["completed_tasks"] == 1


def test_crashed_reserved_task_cannot_be_restarted_or_reset(tmp_path):
    ledger, scope, clock = fixture(tmp_path)
    context = task_context(scope, ledger.pin, 1, clock.now())
    ledger.start_task(1, context)
    ledger.reserve(1, context, slots()[0].request, now=clock.now())
    assert inspect(ledger.path)["unsettled_by_namespace"]["olist_r2_attempts"] == 1
    with pytest.raises(PermissionError, match="unfinished"):
        capture(ledger, Scripted(), clock=clock)
    with pytest.raises(PermissionError):
        ledger.start_task(1, task_context(scope, ledger.pin, 1, clock.now() + timedelta(seconds=1)))


def test_durable_backoff_and_third_attempt_denial(tmp_path):
    ledger, scope, clock = fixture(tmp_path)
    context = task_context(scope, ledger.pin, 1, clock.now())
    ledger.start_task(1, context)
    wire = slots()[0].request
    for i in (1, 2):
        if i == 2:
            with pytest.raises(PermissionError, match="transient retry"):
                ledger.reserve(1, context, wire, now=clock.now())
            clock.sleep(1)
        serial = ledger.reserve(1, context, wire, now=clock.now())
        ledger.settle(
            serial,
            failed_response(wire, "unavailable", "Invented", dispatched=True, retryable=True),
            0,
            clock.now(),
            None,
        )
    clock.sleep(1)
    with pytest.raises(PermissionError):
        ledger.reserve(1, context, wire, now=clock.now())
    assert inspect(ledger.path)["total_consumed"] == 6


def test_fresh_scope_preserves_all_unused_slots_and_requires_new_exact_grant(tmp_path):
    path, old = history(tmp_path)
    values = old.model_dump(
        exclude={
            "version",
            "schedule",
            "max_attempts",
            "max_tokens",
            "http_seconds",
            "parent_seconds",
            "lifetime_ceiling",
            "retained_bound_slots",
        }
    )
    scope = Scope(
        **values, retained_bound_slots=10, lifetime_ceiling=306, policy=policy(), schedule=slots()
    )
    before = path.read_bytes()
    with pytest.raises(PermissionError, match="earlier unused allocations"):
        initialize(path, scope)
    assert before == path.read_bytes()
    real = scope.model_copy(
        update={"origin": "provider", "retained_bound_slots": 16, "lifetime_ceiling": 312}
    )
    with pytest.raises(PermissionError, match="new exact"):
        initialize(path, real)
    assert before == path.read_bytes()
    assert digest(real.canonical_json().encode()) != digest(scope.canonical_json().encode())


def test_second_process_cannot_claim_same_logical_request(tmp_path):
    ledger, scope, clock = fixture(tmp_path)
    from olist_demo_resilience_study import Ledger

    other = Ledger(ledger.path, ledger.pin)
    context = task_context(scope, ledger.pin, 1, clock.now())
    ledger.start_task(1, context)
    with pytest.raises(PermissionError):
        other.start_task(1, context)
    ledger.reserve(1, context, slots()[0].request, now=clock.now())
    with pytest.raises(PermissionError):
        other.reserve(1, context, slots()[0].request, now=clock.now())


def test_permanent_failed_task_circuit_counts_tasks_not_retry_attempts(tmp_path):
    ledger, _, clock = fixture(tmp_path)

    class Failed(Scripted):
        def generate(self, wire, *, timeout_seconds):
            if len(self.calls) < 2:
                return super().generate(wire, timeout_seconds=timeout_seconds)
            self.calls.append(wire)
            return failed_response(
                wire, "unavailable", "Invented 503", dispatched=True, retryable=True
            )

    result = capture(ledger, Failed(), clock=clock)
    assert result["completed_tasks"] == 5 and result["reserved_attempts"] == 8
    assert result["raw_provider_failures"] == 6 and result["stopped"]
    assert result["stop_reasons"] == [("failed_task_circuit",)]
    assert clock.waits == [1, 60, 1, 60, 1]


def test_real_sdk_adapter_with_network_denied_canaries(tmp_path):
    ledger, scope, _ = fixture(tmp_path)
    from olist_demo_study import canaries
    from olist_demo_worker import SDKTransport, SDKWorker

    outputs = {
        slots()[i].request.fingerprint(): value.canonical_json()
        for i, (_, value) in enumerate(canaries())
    }

    class CanarySDK(SDKTransport):
        count = 0

        def generate(self, request, *, timeout_seconds):
            self.count += 1
            if self.count > 2:
                return failed_response(
                    request, "permission_denied", "Readiness complete", dispatched=False
                )
            return super().generate(request, timeout_seconds=timeout_seconds)

    transport = CanarySDK(SDKWorker("invented-no-credential", scope.project_sha256, outputs))
    result = capture(ledger, transport)
    assert result["both_canaries_passed"]
    assert result["reserved_attempts"] == 3 and result["completed_tasks"] == 3
    assert result["stopped"] and result["provider_attempts_counted"] == 0
    assert all(row["phases"] is not None for row in result["process_timings"][:2])
