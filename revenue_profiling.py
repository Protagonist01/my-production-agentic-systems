"""Opt-in bounded content-free Revenue timing, independent of frozen runtime inventories."""

import asyncio
import os
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from math import ceil, isfinite
from typing import Annotated, Any, Literal, TypeVar

from agent_harness.contracts import Contract, ModelRequest, ModelResponse
from agent_harness.isolated_transport import AttemptTiming
from pydantic import Field, model_validator

STAGES = (
    "request",
    "queue_wait",
    "startup",
    "document_load",
    "document_parse",
    "relevance",
    "retrieval",
    "extraction",
    "gateway",
    "citation_check",
    "meaning_check",
    "reconciliation",
    "authenticate",
    "login",
    "proposal",
    "review",
    "apply",
    "sql_connect",
    "sql_execute",
    "sql_fetch",
    "sql_commit",
    "sql_rollback",
    "sql_transaction",
    "sql_finalize",
    "response_send",
    "worker_startup",
    "worker_generation",
    "worker_serialization",
    "worker_cleanup",
    "journal_persist",
    "telemetry_export",
    "approval_wait",
)
Outcome = Literal["ok", "error", "timeout", "cancelled"]
T = TypeVar("T")


class Span(Contract):
    sequence: Annotated[int, Field(ge=0)]
    parent: Annotated[int, Field(ge=0)] | None
    stage: str
    start_ns: Annotated[int, Field(ge=0)]
    end_ns: Annotated[int, Field(ge=0)]
    process_id: Annotated[int, Field(gt=0)]
    worker_process_id_known: Literal[False] = False
    outcome: Outcome
    process_cpu_ns: Annotated[int, Field(ge=0)] | None = None
    input_bytes: Annotated[int, Field(ge=0)] | None = None
    source: Literal["local_span", "isolated_attempt_milestones"] = "local_span"

    @model_validator(mode="after")
    def valid(self) -> "Span":
        if self.stage not in STAGES or self.end_ns < self.start_ns:
            raise ValueError("fixed stage and ordered monotonic interval required")
        if self.parent is not None and self.parent >= self.sequence:
            raise ValueError("parent must precede child")
        return self


def percentile(values: list[float], q: float) -> float | None:
    if not 0 < q <= 1:
        raise ValueError("percentile must be in (0,1]")
    return sorted(values)[ceil(len(values) * q) - 1] if values else None


class Recorder:
    """No content, route strings, SQL, identifiers, exceptions or provider bodies accepted."""

    def __init__(
        self,
        *,
        limit: int = 4096,
        clock: Callable[[], int] = time.monotonic_ns,
        cpu_clock: Callable[[], int] = time.process_time_ns,
    ) -> None:
        if type(limit) is not int or not 1 <= limit <= 100_000:
            raise ValueError("bounded positive timing capacity required")
        self.limit, self.clock, self.cpu_clock = limit, clock, cpu_clock
        self.origin = clock()
        self.parent: ContextVar[int | None] = ContextVar("revenue_profile_parent", default=None)
        self.lock = threading.Lock()
        self.rows: list[Span] = []
        self.next = self.active = self.dropped = 0
        self.clock_anomalies = 0

    def _reserve(self) -> tuple[int, bool]:
        with self.lock:
            seq = self.next
            self.next += 1
            admitted = seq < self.limit
            self.dropped += int(not admitted)
            return seq, admitted

    @contextmanager
    def phase(self, stage: str, *, input_bytes: int | None = None) -> Iterator[None]:
        if stage not in STAGES or (
            input_bytes is not None and (type(input_bytes) is not int or input_bytes < 0)
        ):
            raise ValueError("fixed stage and nonnegative byte count required")
        seq, admitted = self._reserve()
        parent = self.parent.get()
        token = self.parent.set(seq if admitted else parent)
        with self.lock:
            self.active += 1
        start, cpu = self.clock(), self.cpu_clock()
        outcome: Outcome = "ok"
        try:
            yield
        except BaseException as error:
            outcome = (
                "timeout"
                if isinstance(error, TimeoutError)
                else "cancelled"
                if isinstance(error, (asyncio.CancelledError, KeyboardInterrupt))
                else "error"
            )
            raise
        finally:
            end, ended_cpu = self.clock(), self.cpu_clock()
            self.parent.reset(token)
            with self.lock:
                self.active -= 1
                if end < start or start < self.origin or ended_cpu < cpu:
                    self.clock_anomalies += 1
                elif admitted:
                    self.rows.append(
                        Span(
                            sequence=seq,
                            parent=parent,
                            stage=stage,
                            start_ns=max(0, start - self.origin),
                            end_ns=max(0, end - self.origin),
                            process_id=os.getpid(),
                            outcome=outcome,
                            process_cpu_ns=max(0, ended_cpu - cpu),
                            input_bytes=input_bytes,
                        )
                    )

    def call(self, stage: str, fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        with self.phase(stage):
            return fn(*args, **kwargs)

    def attempt(self, timing: AttemptTiming, *, started_ns: int) -> None:
        """Import only observed intervals; local generation includes validation/SDK work."""
        timing = AttemptTiming.model_validate_json(timing.canonical_json())
        milestones = (
            timing.worker_entered_after_seconds,
            timing.generation_returned_after_seconds,
            timing.frame_ready_after_seconds,
            timing.elapsed_seconds,
        )
        known = [v for v in milestones if v is not None]
        if (
            started_ns < self.origin
            or any(not isfinite(v) for v in known)
            or any(b < a for a, b in zip(known, known[1:], strict=False))
        ):
            raise ValueError("attempt milestones differ from local monotonic order")
        pairs = (
            ("worker_startup", 0.0, milestones[0]),
            ("worker_generation", milestones[0], milestones[1]),
            ("worker_serialization", milestones[1], milestones[2]),
            ("worker_cleanup", milestones[2], milestones[3]),
        )
        for stage, a, b in pairs:
            if a is None or b is None:
                continue
            seq, admitted = self._reserve()
            if admitted:
                with self.lock:
                    self.rows.append(
                        Span(
                            sequence=seq,
                            parent=self.parent.get(),
                            stage=stage,
                            start_ns=started_ns - self.origin + round(a * 1e9),
                            end_ns=started_ns - self.origin + round(b * 1e9),
                            process_id=os.getpid(),
                            outcome="timeout"
                            if timing.timed_out
                            else "error"
                            if timing.exit_code not in (None, 0)
                            else "ok",
                            source="isolated_attempt_milestones",
                        )
                    )

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            rows = tuple(sorted(self.rows, key=lambda s: s.sequence))
            active, dropped, anomalies = self.active, self.dropped, self.clock_anomalies
        stages = {}
        for stage in STAGES:
            members = [s for s in rows if s.stage == stage]
            durations = [(s.end_ns - s.start_ns) / 1e9 for s in members]
            stages[stage] = {
                "observations": len(members),
                "outcomes": {
                    o: sum(s.outcome == o for s in members)
                    for o in ("ok", "error", "timeout", "cancelled")
                },
                "p50_seconds": percentile(durations, 0.5),
                "p95_seconds": percentile(durations, 0.95),
            }
        return {
            "version": "revenue-content-free-timing-v1",
            "spans": [s.model_dump(mode="json") for s in rows],
            "stages": stages,
            "active": active,
            "dropped": dropped,
            "clock_anomalies": anomalies,
            "complete": active == dropped == anomalies == 0,
            "duration_scope": "inclusive_monotonic_do_not_sum_nested_or_parallel_spans",
            "cpu_scope": "current_process_inclusive_not_per_thread_or_child_cpu",
            "pid_scope": "observer_process_not_child_identity_for_imported_milestones",
            "provider_internal_time_known": False,
            "memory_profiled": False,
            "all_subprocesses_instrumented": False,
            "release_allowed": False,
        }


class AttemptTransport:
    """Opt-in composition around existing transport; creates no keys or dispatch scope."""

    def __init__(self, delegate: Any, recorder: Recorder):
        self.delegate, self.recorder = delegate, recorder

    def generate(self, request: ModelRequest, *, timeout_seconds: float) -> ModelResponse:
        with self.recorder.phase("gateway"):
            started = self.recorder.clock()
            prior_timing = self.delegate.last_timing
            try:
                result: ModelResponse = self.delegate.generate(
                    request, timeout_seconds=timeout_seconds
                )
                return result
            finally:
                timing = self.delegate.last_timing
                if timing is not None and timing is not prior_timing:
                    self.recorder.attempt(timing, started_ns=started)
