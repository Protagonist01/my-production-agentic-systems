"""Opt-in Supply timings: bounded metadata, explicit gaps, no content or remote export."""

import asyncio
import hashlib
import hmac
import multiprocessing as mp
import os
import secrets
import threading
import time
from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from math import ceil, isfinite
from typing import Annotated, Any, Literal, TypeVar

from agent_harness.contracts import Contract
from pydantic import Field, model_validator

STAGES = (
    "request",
    "response_send",
    "startup",
    "authenticate",
    "login",
    "scope_check",
    "assessment",
    "shipment_read",
    "alert_read",
    "planning",
    "board",
    "review",
    "apply",
    "confirm",
    "notice_build",
    "notice_list",
    "notice_read",
    "database_context",
    "sql_connect",
    "sql_execute",
    "sql_lock_statement",
    "sql_fetch",
    "sql_commit",
    "sql_rollback",
    "sql_transaction",
    "sql_finalize",
    "event",
    "event_step",
    "event_send",
    "approval_wait",
    "confirmation_wait",
    "queue_wait",
    "recovery",
    "worker",
    "worker_launch",
    "worker_ready_wait",
    "worker_execution",
    "worker_result_wait",
    "worker_result_receive",
    "worker_cleanup",
    "profile_persist",
)
Outcome = Literal["ok", "error", "timeout", "cancelled"]
Operation = Literal[
    "assessment", "board", "review", "apply", "confirm", "auth", "other", "event", "worker"
]
T = TypeVar("T")


class TraceContext(Contract):
    trace_id: Annotated[str, Field(pattern=r"^[0-9a-f]{32}$")]
    parent_span: Annotated[str, Field(pattern=r"^[0-9a-f]{16}$")] | None = None


class Span(Contract):
    span_id: Annotated[str, Field(pattern=r"^[0-9a-f]{16}$")]
    parent_span: Annotated[str, Field(pattern=r"^[0-9a-f]{16}$")] | None
    trace_id: Annotated[str, Field(pattern=r"^[0-9a-f]{32}$")]
    incident_ref: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")] | None
    process_id: Annotated[int, Field(gt=0)]
    stage: str
    operation: Operation
    start_ns: Annotated[int, Field(ge=0)]
    end_ns: Annotated[int, Field(ge=0)]
    process_cpu_ns: Annotated[int, Field(ge=0)]
    outcome: Outcome
    http_status: Annotated[int, Field(ge=100, le=599)] | None = None

    @model_validator(mode="after")
    def ordered(self) -> "Span":
        if self.stage not in STAGES or self.end_ns < self.start_ns:
            raise ValueError("fixed stage and ordered monotonic interval required")
        if self.span_id == self.parent_span:
            raise ValueError("span cannot parent itself")
        return self


@dataclass
class Finish:
    http_status: int | None = None


def percentile(values: list[float], q: float) -> float | None:
    if not 0 < q <= 1 or any(not isfinite(v) or v < 0 for v in values):
        raise ValueError("finite nonnegative values and percentile in (0,1] required")
    return sorted(values)[ceil(len(values) * q) - 1] if values else None


class Recorder:
    def __init__(
        self,
        *,
        limit: int = 4096,
        clock: Callable[[], int] = time.monotonic_ns,
        cpu_clock: Callable[[], int] = time.process_time_ns,
    ) -> None:
        if type(limit) is not int or not 1 <= limit <= 100_000:
            raise ValueError("positive bounded span capacity required")
        self.limit, self.clock, self.cpu_clock = limit, clock, cpu_clock
        self._key = secrets.token_bytes(32)
        self._context: ContextVar[TraceContext | None] = ContextVar("supply_trace", default=None)
        self._incident: ContextVar[str | None] = ContextVar("supply_incident", default=None)
        self._operation: ContextVar[Operation] = ContextVar("supply_operation", default="other")
        self._lock = threading.Lock()
        self._rows: list[Span] = []
        self._count = self._active = self._dropped = self._anomalies = 0

    @contextmanager
    def bind(self, context: TraceContext) -> Iterator[None]:
        context = TraceContext.model_validate_json(context.canonical_json())
        token = self._context.set(context)
        try:
            yield
        finally:
            self._context.reset(token)

    def context(self) -> TraceContext:
        return self._context.get() or TraceContext(trace_id=secrets.token_hex(16))

    @contextmanager
    def incident(self, tenant: str, event: str) -> Iterator[None]:
        # Only the digest is retained. The random key is private to this recorder lifetime.
        digest = hmac.new(self._key, (tenant + "\0" + event).encode(), hashlib.sha256).hexdigest()
        token = self._incident.set(digest)
        try:
            yield
        finally:
            self._incident.reset(token)

    @contextmanager
    def phase(self, stage: str, *, operation: Operation | None = None) -> Iterator[Finish]:
        if stage not in STAGES:
            raise ValueError("fixed stage name required")
        previous = self.context()
        span_id = secrets.token_hex(8)
        token = self._context.set(previous.model_copy(update={"parent_span": span_id}))
        operation_token = self._operation.set(operation or self._operation.get())
        with self._lock:
            admitted = self._count < self.limit
            self._count += 1
            self._active += 1
            self._dropped += not admitted
        start, cpu = self.clock(), self.cpu_clock()
        finish = Finish()
        outcome: Outcome = "ok"
        try:
            yield finish
        except BaseException as error:
            outcome = (
                "timeout"
                if isinstance(error, TimeoutError)
                else ("cancelled" if isinstance(error, asyncio.CancelledError) else "error")
            )
            raise
        finally:
            end, used = self.clock(), self.cpu_clock() - cpu
            with self._lock:
                self._anomalies += end < start or used < 0
                self._active -= 1
                if admitted:
                    self._rows.append(
                        Span(
                            span_id=span_id,
                            parent_span=previous.parent_span,
                            trace_id=previous.trace_id,
                            incident_ref=self._incident.get(),
                            process_id=os.getpid(),
                            stage=stage,
                            operation=self._operation.get(),
                            start_ns=max(0, start),
                            end_ns=max(0, start, end),
                            process_cpu_ns=max(0, used),
                            outcome=outcome,
                            http_status=finish.http_status,
                        )
                    )
            self._operation.reset(operation_token)
            self._context.reset(token)

    def call(self, stage: str, fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        with self.phase(stage):
            return fn(*args, **kwargs)

    async def wait(
        self,
        stage: Literal["approval_wait", "confirmation_wait", "event_step", "event_send"],
        fn: Callable[[], Awaitable[T]],
    ) -> T:
        with self.phase(stage):
            return await fn()

    def snapshot(self, *, required: tuple[str, ...] = ()) -> dict[str, Any]:
        if len(required) != len(set(required)) or any(s not in STAGES for s in required):
            raise ValueError("distinct known required stages needed")
        with self._lock:
            rows = tuple(sorted(self._rows, key=lambda s: (s.start_ns, s.span_id)))
            active, dropped, anomalies = self._active, self._dropped, self._anomalies
        roots = [
            s
            for s in rows
            if s.stage in ("request", "event", "worker", "worker_execution")
            and s.parent_span not in {r.span_id for r in rows}
        ]
        by_id = {s.span_id: s for s in rows}
        complete = 0
        for root in roots:
            observed = set()
            for row in rows:
                current, seen = row, set()
                while current.parent_span in by_id and current.span_id not in seen:
                    seen.add(current.span_id)
                    current = by_id[current.parent_span]
                if current.span_id == root.span_id:
                    observed.add(row.stage)
            complete += set(required) <= observed
        stages = {}
        for stage in STAGES:
            members = [s for s in rows if s.stage == stage]
            values = [(s.end_ns - s.start_ns) / 1e9 for s in members]
            stages[stage] = {
                "observed": len(values),
                "p50_seconds": percentile(values, 0.5),
                "p95_seconds": percentile(values, 0.95),
                "outcomes": {
                    o: sum(s.outcome == o for s in members)
                    for o in ("ok", "error", "timeout", "cancelled")
                },
            }
        return {
            "version": "supply-content-free-timing-v1",
            "spans": [s.model_dump(mode="json") for s in rows],
            "stages": stages,
            "active": active,
            "dropped": dropped,
            "clock_anomalies": anomalies,
            "coverage": {
                "required": required,
                "roots": len(roots),
                "complete_roots": complete if not (active or dropped or anomalies) else 0,
                "complete": bool(required and roots)
                and complete == len(roots)
                and not (active or dropped or anomalies),
            },
            "unobserved_stages": [s for s in STAGES if not stages[s]["observed"]],
            "limits": [
                "Inclusive nested/parallel timings must not be summed as sequential latency.",
                "Process CPU is inclusive process-wide CPU, not per-thread attribution.",
                "SQL lock statements include execution/roundtrip, not isolated server lock wait.",
                "Transaction finalization is not an independent fsync/WAL measurement.",
                "Absent queue/provider/worker stages remain unmeasured; no all-subprocess claim.",
                "Incident correlation is recorder-local; process trace context is explicit.",
                "Local memory/shutdown snapshots are not crash-durable remote trace delivery.",
            ],
            "remote_exported": False,
        }


@dataclass(frozen=True)
class WorkerResult:
    value: Any
    outcome: Literal["ok", "error", "timeout", "crashed"]
    child_profile: dict[str, Any] | None


def _worker(fn: Callable[[], Any], connection: Any, context: dict[str, Any]) -> None:
    recorder = Recorder()
    try:
        connection.send("ready")
        if connection.recv() != "run":
            return
        with recorder.bind(TraceContext.model_validate(context)):
            try:
                with recorder.phase("worker_execution", operation="worker"):
                    value = fn()
            except BaseException:
                connection.send(("error", None, recorder.snapshot()))
            else:
                connection.send(("ok", value, recorder.snapshot()))
    finally:
        connection.close()


def run_worker(
    recorder: Recorder, fn: Callable[[], Any], *, timeout_seconds: float = 30
) -> WorkerResult:
    """Trusted local callable only, not an upload/command API or an untrusted-code sandbox.

    Values are returned to the trusted caller, never written into spans. The caller owns
    their privacy. Parent wait includes scheduling/IPC; child execution is separately timed.
    """
    with recorder.phase("worker", operation="worker"):
        return _run_worker(recorder, fn, timeout_seconds=timeout_seconds)


def _run_worker(
    recorder: Recorder, fn: Callable[[], Any], *, timeout_seconds: float
) -> WorkerResult:
    if not isfinite(timeout_seconds) or not 0 < timeout_seconds <= 300:
        raise ValueError("bounded positive worker timeout required")
    context = mp.get_context("spawn")
    parent, child = context.Pipe()
    process = context.Process(
        target=_worker, args=(fn, child, recorder.context().model_dump(mode="json"))
    )
    deadline = time.monotonic() + timeout_seconds
    result = WorkerResult(None, "crashed", None)
    started = False
    try:
        with recorder.phase("worker_launch"):
            process.start()
            started = True
            child.close()
        with recorder.phase("worker_ready_wait"):
            if not parent.poll(max(0, deadline - time.monotonic())):
                raise TimeoutError()
            if parent.recv() != "ready":
                raise RuntimeError("worker readiness refused")
        parent.send("run")
        with recorder.phase("worker_result_wait"):
            if not parent.poll(max(0, deadline - time.monotonic())):
                raise TimeoutError()
        with recorder.phase("worker_result_receive"):
            outcome, value, profile = parent.recv()
            if outcome not in ("ok", "error"):
                raise RuntimeError("worker outcome refused")
            result = WorkerResult(value, outcome, profile)
    except TimeoutError:
        result = WorkerResult(None, "timeout", None)
    except (EOFError, BrokenPipeError):
        result = WorkerResult(None, "crashed", None)
    finally:
        with recorder.phase("worker_cleanup"):
            if started:
                process.join(timeout=1)
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=2)
                if process.is_alive():
                    process.kill()
                    process.join(timeout=2)
                if process.is_alive():
                    raise RuntimeError("owned worker cleanup incomplete")
                process.close()
            child.close()
            parent.close()
    return result
