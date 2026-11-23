"""Fresh Gemini task evaluation with existing bounded retries and durable raw attempts.

This prepares a new allowance; it never resumes, resets or re-scores an old failed slot.
"""

import argparse
import json
import math
import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from functools import cache
from pathlib import Path
from typing import Annotated, Literal, Self

from agent_harness.admission import GEMINI_TOKEN_CEILING, GeminiFreeAdmission
from agent_harness.contracts import Budget, ModelRequest, ModelResponse, RunContext, WireContract
from agent_harness.controls import (
    BoundedGateway,
    Clock,
    ControlledCall,
    ExecutionPolicy,
    SharedControls,
    SystemClock,
    combine_usage,
)
from agent_harness.gateway import DeadlineTransport, ProviderGateway, failed_response
from agent_harness.isolated_transport import AttemptTiming
from agent_harness.offline_example import example_context
from pydantic import AwareDatetime, Field, model_validator

from olist_demo_acceptance import canonical, cases, digest
from olist_demo_acceptance import prepare as prepare_references
from olist_demo_budget_readback import historical_hash, inspect
from olist_demo_capture import ROOT, source_pin, write
from olist_demo_evaluation import TaskObservation, baselines, summarize
from olist_demo_semantic_v2 import VERSION, request
from olist_demo_study import OwnerGrant, Pin, Slot, canaries, reference_pin
from olist_demo_worker import SDKTransport, SDKWorker, environment_pin

TABLES = frozenset(
    {
        "olist_r2_scope",
        "olist_r2_tasks",
        "olist_r2_attempts",
        "olist_r2_results",
        "olist_r2_task_results",
        "olist_r2_stop",
    }
)
MAX_ATTEMPTS = 292


def policy() -> ExecutionPolicy:
    return ExecutionPolicy(
        version="olist-query-two-attempts-v2",
        max_attempts=2,
        attempt_timeout_seconds=30.0,
        backoff_seconds=1.0,
        max_backoff_seconds=1.0,
        circuit_failure_threshold=3,
        circuit_cooldown_seconds=60.0,
    )


def slots() -> tuple[Slot, ...]:
    return tuple(
        [
            Slot(case_id=f"demo-canary-{i}", trial=0, request=request(text))
            for i, (text, _) in enumerate(canaries(), 1)
        ]
        + [
            Slot(case_id=c.case_id, trial=trial, request=request(c.text))
            for trial in (1, 2, 3)
            for c in cases()
        ]
    )


@cache
def schedule_pin() -> str:
    return digest(canonical([s.model_dump(mode="json") for s in slots()]))


class Scope(WireContract):
    version: Literal["olist-resilient-demo-study-v2"] = "olist-resilient-demo-study-v2"
    origin: Literal["mock", "provider"]
    ledger_reference: str
    historical_sha256: Pin
    historical_consumed: Annotated[int, Field(ge=0)]
    retained_bound_slots: Annotated[int, Field(ge=0)]
    lifetime_ceiling: Annotated[int, Field(ge=292)]
    project_sha256: Pin
    source_sha256: Pin
    environment_sha256: Pin
    reference_sha256: Pin
    starts_at: AwareDatetime
    expires_at: AwareDatetime
    max_attempts: Literal[292] = 292
    max_tokens: int = MAX_ATTEMPTS * GEMINI_TOKEN_CEILING
    task_seconds: Literal[30] = 30
    policy: ExecutionPolicy
    schedule: tuple[Slot, ...]

    @model_validator(mode="after")
    def frozen(self) -> Self:
        if (
            digest(canonical([s.model_dump(mode="json") for s in self.schedule])) != schedule_pin()
            or self.reference_sha256 != reference_pin()
            or self.policy != policy()
            or self.max_tokens != MAX_ATTEMPTS * GEMINI_TOKEN_CEILING
            or self.lifetime_ceiling != self.historical_consumed + self.retained_bound_slots + 292
            or not Path(self.ledger_reference).is_absolute()
            or not timedelta(0) < self.expires_at - self.starts_at <= timedelta(days=7)
        ):
            raise ValueError("exact task schedule, retry policy, reservations and expiry required")
        return self


def accounted(db: sqlite3.Connection) -> int:
    return int(
        db.execute(
            "SELECT coalesce(sum(coalesce(tokens,?)),0) FROM olist_r2_results",
            (GEMINI_TOKEN_CEILING,),
        ).fetchone()[0]
    )


class Ledger:
    def __init__(self, path: Path, pin: str, grant_pin: str | None = None):
        self.path, self.pin, self.grant_pin = path.resolve(strict=True), pin, grant_pin

    def connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path.as_uri() + "?mode=rw", uri=True, timeout=10)
        db.execute("PRAGMA synchronous=FULL")
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def scope(self, db: sqlite3.Connection) -> Scope:
        row = db.execute("SELECT document,owner_grant FROM olist_r2_scope").fetchall()
        if len(row) != 1 or digest(row[0][0].encode()) != self.pin:
            raise PermissionError("exact externally pinned resilience scope required")
        scope = Scope.model_validate_json(row[0][0])
        if scope.ledger_reference != str(self.path):
            raise PermissionError("same approved shared ledger path required")
        if historical_hash(db, TABLES) != scope.historical_sha256:
            raise PermissionError("all earlier history must remain unchanged")
        if scope.origin == "provider":
            if row[0][1] is None:
                raise PermissionError("separate owner grant required")
            grant = OwnerGrant.model_validate_json(row[0][1])
            if (
                digest(grant.canonical_json().encode()) != self.grant_pin
                or grant.scope_sha256 != self.pin
            ):
                raise PermissionError("exact owner grant pin required")
        elif self.grant_pin is not None or row[0][1] is not None:
            raise PermissionError("mock execution cannot carry provider authority")
        return scope

    def start_task(self, ordinal: int, context: RunContext) -> None:
        context = RunContext.model_validate_json(context.canonical_json())
        with closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            scope = self.scope(db)
            count = db.execute("SELECT count(*) FROM olist_r2_tasks").fetchone()[0]
            done = db.execute("SELECT count(*) FROM olist_r2_task_results").fetchone()[0]
            if (
                not scope.starts_at <= context.clock < scope.expires_at
                or count != done
                or ordinal != count + 1
                or not 1 <= ordinal <= 146
                or db.execute("SELECT 1 FROM olist_r2_stop").fetchone()
                or context != task_context(scope, self.pin, ordinal, context.clock)
            ):
                raise PermissionError("expired, unfinished, stopped or changed task context")
            if (
                ordinal > 2
                and db.execute(
                    "SELECT count(*) FROM olist_r2_task_results WHERE ordinal<=2 AND canary_pass=1"
                ).fetchone()[0]
                != 2
            ):
                raise PermissionError("both end-to-end canaries must pass")
            db.execute(
                "INSERT INTO olist_r2_tasks VALUES(?,?,?)",
                (
                    ordinal,
                    scope.schedule[ordinal - 1].request.fingerprint(),
                    context.canonical_json(),
                ),
            )

    def reserve(self, task: int, context: RunContext, wire: ModelRequest, *, now: datetime) -> int:
        with closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            scope = self.scope(db)
            row = db.execute(
                "SELECT request_sha256,context FROM olist_r2_tasks WHERE ordinal=?", (task,)
            ).fetchone()
            count = db.execute("SELECT count(*) FROM olist_r2_attempts").fetchone()[0]
            settled = db.execute("SELECT count(*) FROM olist_r2_results").fetchone()[0]
            sub = db.execute(
                "SELECT count(*) FROM olist_r2_attempts WHERE task=?", (task,)
            ).fetchone()[0]
            if (
                not 1 <= task <= 146
                or row != (wire.fingerprint(), context.canonical_json())
                or count != settled
                or wire != scope.schedule[task - 1].request
                or not scope.starts_at <= now < min(scope.expires_at, context.deadline)
                or count >= scope.max_attempts
                or sub >= 2
                or db.execute("SELECT 1 FROM olist_r2_stop").fetchone()
                or db.execute(
                    "SELECT 1 FROM olist_r2_task_results WHERE ordinal=?", (task,)
                ).fetchone()
                or accounted(db) + GEMINI_TOKEN_CEILING > scope.max_tokens
            ):
                raise PermissionError("attempt outside settled exact task/budget/deadline")
            if sub:
                previous = db.execute(
                    "SELECT r.response,r.settled_at FROM olist_r2_results r "
                    "JOIN olist_r2_attempts a ON a.serial=r.serial WHERE a.task=? "
                    "ORDER BY a.subattempt DESC LIMIT 1",
                    (task,),
                ).fetchone()
                response = ModelResponse.model_validate_json(previous[0])
                f = response.failure
                if (
                    f is None
                    or not f.retryable
                    or f.code not in ("timeout", "rate_limited", "unavailable")
                    or (now - datetime.fromisoformat(previous[1])).total_seconds() < 1
                ):
                    raise PermissionError(
                        "only one bounded transient retry; never retry meaning/schema"
                    )
            serial = count + 1
            db.execute(
                "INSERT INTO olist_r2_attempts VALUES(?,?,?,?,?)",
                (serial, task, sub + 1, wire.fingerprint(), now.isoformat()),
            )
            return int(serial)

    def settle(
        self,
        serial: int,
        response: ModelResponse,
        elapsed_ms: float,
        now: datetime,
        timing: str | None,
    ) -> None:
        response = ModelResponse.model_validate_json(response.canonical_json())
        if not math.isfinite(elapsed_ms) or elapsed_ms < 0:
            raise ValueError("finite attempt timing required")
        if timing is not None:
            timing = AttemptTiming.model_validate_json(timing).canonical_json()
        with closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            scope = self.scope(db)
            row = db.execute(
                "SELECT task FROM olist_r2_attempts WHERE serial=?", (serial,)
            ).fetchone()
            if row is None:
                raise PermissionError("reserved attempt required")
            usage = response.usage
            tokens = (
                None
                if usage.input_tokens is None or usage.output_tokens is None
                else usage.input_tokens + usage.output_tokens
            )
            wire = scope.schedule[row[0] - 1].request
            if (response.provider, response.model) != (wire.provider, wire.model):
                raise PermissionError("attempt response route differs")
            db.execute(
                "INSERT INTO olist_r2_results VALUES(?,?,?,?,?,?)",
                (serial, response.canonical_json(), tokens, elapsed_ms, now.isoformat(), timing),
            )
            if (
                usage.model_calls > 1
                or (tokens is not None and tokens > GEMINI_TOKEN_CEILING)
                or (usage.cost is not None and usage.cost != 0)
            ):
                db.execute(
                    "INSERT OR IGNORE INTO olist_r2_stop VALUES(1,?)", ("accounting_breach",)
                )

    def finish_task(
        self,
        ordinal: int,
        response: ModelResponse,
        controlled: ControlledCall,
        elapsed_ms: float,
        now: datetime,
    ) -> None:
        response = ModelResponse.model_validate_json(response.canonical_json())
        controlled = ControlledCall.model_validate_json(controlled.canonical_json())
        if not math.isfinite(elapsed_ms) or elapsed_ms < 0:
            raise ValueError("finite logical task timing required")
        with closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            scope = self.scope(db)
            context_raw = db.execute(
                "SELECT context FROM olist_r2_tasks WHERE ordinal=?", (ordinal,)
            ).fetchone()
            if context_raw != (controlled.context.canonical_json(),):
                raise PermissionError("exact controlled task context required")
            wire = scope.schedule[ordinal - 1].request
            late = elapsed_ms > scope.task_seconds * 1000
            expected = controlled.response
            if late and expected.failure is None:
                expected = failed_response(
                    wire,
                    "timeout",
                    "Decision completed outside the task deadline",
                    dispatched=False,
                    usage=expected.usage,
                )
            if (
                controlled.policy != scope.policy
                or controlled.request_fingerprint != wire.fingerprint()
                or response != expected
                or (response.provider, response.model) != (wire.provider, wire.model)
            ):
                raise PermissionError("exact controlled policy, response and deadline required")
            count = db.execute(
                "SELECT count(*) FROM olist_r2_attempts WHERE task=?", (ordinal,)
            ).fetchone()[0]
            captured = db.execute(
                "SELECT r.response FROM olist_r2_results r JOIN olist_r2_attempts a "
                "ON a.serial=r.serial WHERE a.task=? ORDER BY a.subattempt",
                (ordinal,),
            ).fetchall()
            if count != len(captured):
                raise PermissionError("unsettled raw attempt blocks task completion")
            raw = [ModelResponse.model_validate_json(r[0]) for r in captured]
            raw_usage = tuple(r.usage for r in raw)
            if response.usage != combine_usage(raw_usage, "USD") or tuple(
                u for u in controlled.attempt_usage if u.model_calls
            ) != tuple(u for u in raw_usage if u.model_calls):
                raise PermissionError("task and raw attempt call accounting differ")
            passed = False
            if ordinal <= 2 and response.failure is None:
                from docs.evaluation.olist_semantic_candidate import parse

                try:
                    out = response.output
                    passed = bool(
                        out
                        and not out.tool_calls
                        and out.content
                        and parse(canaries()[ordinal - 1][0], out.content)
                        == canaries()[ordinal - 1][1]
                    )
                except ValueError:
                    pass
            db.execute(
                "INSERT INTO olist_r2_task_results VALUES(?,?,?,?,?,?)",
                (
                    ordinal,
                    response.canonical_json(),
                    controlled.canonical_json(),
                    elapsed_ms,
                    int(passed),
                    now.isoformat(),
                ),
            )
            reason = None
            if ordinal <= 2 and not passed:
                reason = "canary_failed"
            elif any(
                r.failure and r.failure.code in ("rate_limited", "permission_denied") for r in raw
            ):
                reason = "quota_or_permission_stop"
            elif any(
                (r.usage.input_tokens is None or r.usage.output_tokens is None)
                and (
                    r.failure is None
                    or r.failure.code not in ("timeout", "unavailable", "rate_limited")
                )
                for r in raw
            ):
                reason = "unknown_nontransient_usage"
            elif any(
                r.failure and not r.failure.retryable and r.failure.code == "unavailable"
                for r in raw
            ):
                reason = "unexpected_transport_failure"
            else:
                values = [
                    ModelResponse.model_validate_json(r[0])
                    for r in db.execute(
                        "SELECT response FROM olist_r2_task_results "
                        "WHERE ordinal>2 ORDER BY ordinal"
                    )
                ]
                failed = sum(r.failure is not None for r in values)
                if failed >= 8 or (
                    len(values) >= 3 and all(r.failure is not None for r in values[-3:])
                ):
                    reason = "failed_task_circuit"
            if reason:
                db.execute("INSERT OR IGNORE INTO olist_r2_stop VALUES(1,?)", (reason,))


def task_context(scope: Scope, pin: str, ordinal: int, now: datetime) -> RunContext:
    slot = scope.schedule[ordinal - 1]
    base = example_context(scope.source_sha256, scope.environment_sha256)
    return base.model_copy(
        update={
            "run_id": f"{pin}-{ordinal}",
            "tenant_id": "olist-demo-study",
            "agent_id": VERSION,
            "case_id": slot.case_id,
            "trial_id": f"trial-{slot.trial}",
            "business_event_id": f"text-only-{pin}-{ordinal}",
            "mode": "fresh_candidate",
            "clock": now,
            "deadline": now + timedelta(seconds=scope.task_seconds),
            "budget": Budget(
                max_model_calls=2,
                max_tokens=2 * GEMINI_TOKEN_CEILING,
                max_cost=Decimal(0),
                cost_currency="USD",
            ),
            "versions": base.versions.model_copy(
                update={
                    "candidate": VERSION,
                    "data_snapshot": scope.reference_sha256,
                    "policy": scope.policy.version,
                }
            ),
        }
    )


def initialize(
    path: Path,
    scope: Scope,
    grant: OwnerGrant | None = None,
    *,
    trusted_grant_sha256: str | None = None,
) -> Ledger:
    scope = Scope.model_validate_json(scope.canonical_json())
    pin = digest(scope.canonical_json().encode())
    if scope.ledger_reference != str(path.resolve(strict=True)):
        raise PermissionError("same approved shared ledger path required")
    if grant is not None:
        grant = OwnerGrant.model_validate_json(grant.canonical_json())
    if scope.origin == "provider" and (
        grant is None
        or grant.scope_sha256 != pin
        or digest(grant.canonical_json().encode()) != trusted_grant_sha256
    ):
        raise PermissionError("new exact retry-study grant and Free confirmation required")
    if scope.origin == "mock" and (grant is not None or trusted_grant_sha256 is not None):
        raise PermissionError("mock scope cannot carry provider authority")
    ledger = Ledger(path, pin, trusted_grant_sha256)
    with closing(ledger.connect()) as db, db:
        db.execute("BEGIN IMMEDIATE")
        names = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if names & TABLES:
            ledger.scope(db)
            return ledger
        if historical_hash(db) != scope.historical_sha256:
            raise PermissionError("exact earlier shared history required")
        report = inspect(path)
        if (
            report["historical_snapshot_sha256"] != scope.historical_sha256
            or any(report["unsettled_by_namespace"].values())
            or report["total_consumed"] != scope.historical_consumed
            or report["latest_recorded_ceiling"] - scope.historical_consumed
            != scope.retained_bound_slots
            or report["latest_recorded_ceiling"] + MAX_ATTEMPTS != scope.lifetime_ceiling
        ):
            raise PermissionError("all earlier unused allocations and exact shared count required")
        original = json.loads(db.execute("SELECT document FROM authorization").fetchone()[0])
        if original["project_sha256"] != scope.project_sha256:
            raise PermissionError("same configured Gemini project association required")
        db.execute(
            "CREATE TABLE olist_r2_scope(id INTEGER PRIMARY KEY CHECK(id=1),"
            "document TEXT NOT NULL,owner_grant TEXT)"
        )
        db.execute(
            "INSERT INTO olist_r2_scope VALUES(1,?,?)",
            (scope.canonical_json(), grant.canonical_json() if grant else None),
        )
        db.execute(
            "CREATE TABLE olist_r2_tasks(ordinal INTEGER PRIMARY KEY "
            "CHECK(ordinal BETWEEN 1 AND 146),request_sha256 TEXT NOT NULL,context TEXT NOT NULL)"
        )
        db.execute(
            "CREATE TABLE olist_r2_attempts(serial INTEGER PRIMARY KEY "
            "CHECK(serial BETWEEN 1 AND 292),task INTEGER NOT NULL REFERENCES olist_r2_tasks,"
            "subattempt INTEGER NOT NULL CHECK(subattempt BETWEEN 1 AND 2),"
            "request_sha256 TEXT NOT NULL,created TEXT NOT NULL,UNIQUE(task,subattempt))"
        )
        db.execute(
            "CREATE TABLE olist_r2_results(serial INTEGER PRIMARY KEY REFERENCES "
            "olist_r2_attempts,response TEXT NOT NULL,tokens INTEGER,elapsed_ms REAL NOT NULL,"
            "settled_at TEXT NOT NULL,process_timing TEXT)"
        )
        db.execute(
            "CREATE TABLE olist_r2_task_results(ordinal INTEGER PRIMARY KEY REFERENCES "
            "olist_r2_tasks,response TEXT NOT NULL,controlled_call TEXT NOT NULL,"
            "elapsed_ms REAL NOT NULL,canary_pass INTEGER NOT NULL,completed_at TEXT NOT NULL)"
        )
        db.execute(
            "CREATE TABLE olist_r2_stop(id INTEGER PRIMARY KEY CHECK(id=1),reason TEXT NOT NULL)"
        )
        for table in TABLES:
            for operation in ("UPDATE", "DELETE"):
                db.execute(
                    f"CREATE TRIGGER immutable_{table}_{operation} BEFORE {operation} ON {table} "
                    "BEGIN SELECT RAISE(ABORT,'immutable resilient study'); END"
                )
    return ledger


def verify_runtime(scope: Scope) -> None:
    import subprocess

    import agent_harness
    import olist_support

    if (
        subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()
        or source_pin(ROOT) != scope.source_sha256
        or environment_pin() != scope.environment_sha256
        or any(
            m.__file__ is None or not Path(m.__file__).resolve().is_relative_to(ROOT)
            for m in (agent_harness, olist_support)
        )
    ):
        raise PermissionError("clean exact source/imports/environment required")


class RecordedTransport:
    def __init__(
        self,
        ledger: Ledger,
        task: int,
        context: RunContext,
        delegate: DeadlineTransport,
        clock: Clock,
    ):
        self.ledger, self.task, self.context, self.delegate, self.clock = (
            ledger,
            task,
            context,
            delegate,
            clock,
        )

    def generate(
        self, request: ModelRequest, *, timeout_seconds: float | None = None
    ) -> ModelResponse:
        if timeout_seconds is None:
            raise PermissionError("bounded task deadline required")
        wire = request
        start = self.clock.monotonic()
        try:
            serial = self.ledger.reserve(self.task, self.context, wire, now=self.clock.now())
        except PermissionError:
            return failed_response(
                wire, "budget_exhausted", "Durable task admission denied", dispatched=False
            )
        remaining = min(
            timeout_seconds - (self.clock.monotonic() - start),
            (self.context.deadline - self.clock.now()).total_seconds(),
        )
        if remaining <= 0:
            response = failed_response(
                wire, "timeout", "Task deadline exhausted before dispatch", dispatched=False
            )
        else:
            try:
                response = self.delegate.generate(wire, timeout_seconds=remaining)
            except Exception:
                response = failed_response(
                    wire,
                    "unavailable",
                    "Scoped transport failed; usage unknown",
                    dispatched=True,
                    retryable=False,
                )
        timing = self.delegate.last_timing if isinstance(self.delegate, SDKTransport) else None
        self.ledger.settle(
            serial,
            response,
            (self.clock.monotonic() - start) * 1000,
            self.clock.now(),
            timing.canonical_json() if timing else None,
        )
        return response


def readback(ledger: Ledger) -> dict[str, object]:
    with closing(ledger.connect()) as db:
        db.execute("BEGIN")
        scope = ledger.scope(db)
        task_rows = db.execute(
            "SELECT ordinal,response,elapsed_ms FROM olist_r2_task_results ORDER BY ordinal"
        ).fetchall()
        attempts = db.execute(
            "SELECT serial,response,elapsed_ms,process_timing FROM olist_r2_results ORDER BY serial"
        ).fetchall()
        count = db.execute("SELECT count(*) FROM olist_r2_attempts").fetchone()[0]
        task_count = db.execute("SELECT count(*) FROM olist_r2_tasks").fetchone()[0]
        stop = db.execute("SELECT reason FROM olist_r2_stop").fetchall()
        passed = db.execute(
            "SELECT count(*) FROM olist_r2_task_results WHERE ordinal<=2 AND canary_pass=1"
        ).fetchone()[0]
        tokens = accounted(db)
    if scope.origin == "provider" and source_pin(ROOT) != scope.source_sha256:
        raise PermissionError("exact resilience source required for readback")
    observations = tuple(
        TaskObservation(
            origin=scope.origin,
            case_id=scope.schedule[i - 1].case_id,
            trial=scope.schedule[i - 1].trial,
            request_sha256=scope.schedule[i - 1].request.fingerprint(),
            response=ModelResponse.model_validate_json(raw),
            elapsed_ms=elapsed,
        )
        for i, raw, elapsed in task_rows
        if i > 2
    )
    raw_responses = [ModelResponse.model_validate_json(raw) for _, raw, _, _ in attempts]
    raw_durations = sorted(float(elapsed) for _, _, elapsed, _ in attempts)
    return {
        "scope_sha256": ledger.pin,
        "origin": scope.origin,
        "measurement_unit": "logical_customer_request",
        "scheduled_tasks": 146,
        "task_leases": task_count,
        "completed_tasks": len(task_rows),
        "missing_tasks": 146 - task_count,
        "unfinished_tasks": task_count - len(task_rows),
        "reserved_attempts": count,
        "settled_attempts": len(attempts),
        "unsettled_attempts": count - len(attempts),
        "maximum_attempts": 292,
        "both_canaries_passed": passed == 2,
        "stopped": bool(stop),
        "stop_reasons": stop,
        "provider_attempts_counted": count if scope.origin == "provider" else 0,
        "raw_provider_failures": sum(r.failure is not None for r in raw_responses),
        "raw_failure_rate": sum(r.failure is not None for r in raw_responses) / len(attempts)
        if attempts
        else None,
        "raw_reported_model_calls": sum(r.usage.model_calls for r in raw_responses),
        "retried_tasks": sum(
            ModelResponse.model_validate_json(raw).usage.model_calls == 2 for _, raw, _ in task_rows
        ),
        "raw_latency_p95_ms": raw_durations[math.ceil(0.95 * len(raw_durations)) - 1]
        if raw_durations
        else None,
        "raw_unknown_cost_rows": sum(r.usage.cost is None for r in raw_responses),
        "raw_unknown_token_rows": sum(
            r.usage.input_tokens is None or r.usage.output_tokens is None for r in raw_responses
        ),
        "known_raw_input_tokens": sum(r.usage.input_tokens or 0 for r in raw_responses),
        "known_raw_output_tokens": sum(r.usage.output_tokens or 0 for r in raw_responses),
        "conservatively_accounted_tokens": tokens,
        "aggregate_consumed": scope.historical_consumed + count,
        "lifetime_ceiling": scope.lifetime_ceiling,
        "retained_bound_slots": scope.retained_bound_slots,
        "earlier_history_unchanged": True,
        "process_timings": [
            {"serial": i, "phases": json.loads(t) if t else None} for i, _, _, t in attempts
        ],
        "domain": summarize(observations, request_builder=request),
        "baselines": baselines(),
        "model_quality_observed": scope.origin == "provider" and bool(observations),
        "demo_release_accepted": False,
    }


def capture(
    ledger: Ledger, delegate: DeadlineTransport, *, clock: Clock | None = None
) -> dict[str, object]:
    with closing(ledger.connect()) as db:
        scope = ledger.scope(db)
        count = db.execute("SELECT count(*) FROM olist_r2_tasks").fetchone()[0]
        done = db.execute("SELECT count(*) FROM olist_r2_task_results").fetchone()[0]
    if count != done:
        raise PermissionError("unfinished task cannot be resent or given a new deadline")
    if scope.origin == "provider" and (
        clock is not None
        or not isinstance(delegate, SDKTransport)
        or delegate.worker.origin != "provider"
        or delegate.worker.project_sha256 != scope.project_sha256
    ):
        raise PermissionError("real selected SDK worker and system clock required")
    if isinstance(delegate, SDKTransport) and delegate.worker.origin != scope.origin:
        raise PermissionError("mock/provider transport origin differs")
    run_clock = clock or SystemClock()
    for ordinal in range(count + 1, 147):
        with closing(ledger.connect()) as db:
            if db.execute("SELECT 1 FROM olist_r2_stop").fetchone():
                break
            last = db.execute(
                "SELECT response,completed_at FROM olist_r2_task_results "
                "ORDER BY ordinal DESC LIMIT 1"
            ).fetchone()
        if last and ModelResponse.model_validate_json(last[0]).failure:
            delay = max(
                0.0, 60 - (run_clock.now() - datetime.fromisoformat(last[1])).total_seconds()
            )
            run_clock.sleep(min(delay, 60.0))
        if scope.origin == "provider":
            verify_runtime(scope)
        start = run_clock.monotonic()
        context = task_context(scope, ledger.pin, ordinal, run_clock.now())
        ledger.start_task(ordinal, context)
        recording = RecordedTransport(ledger, ordinal, context, delegate, run_clock)
        gateway = BoundedGateway(
            ProviderGateway(recording),
            SharedControls(clock=run_clock),
            GeminiFreeAdmission(free_tier_confirmed=True),
            policy=scope.policy,
        )
        response = gateway.generate(context, scope.schedule[ordinal - 1].request)
        elapsed = (run_clock.monotonic() - start) * 1000
        if elapsed > scope.task_seconds * 1000 and response.failure is None:
            response = failed_response(
                scope.schedule[ordinal - 1].request,
                "timeout",
                "Decision completed outside the task deadline",
                dispatched=False,
                usage=response.usage,
            )
        ledger.finish_task(ordinal, response, gateway.calls[-1], elapsed, run_clock.now())
    return readback(ledger)


def prepare(output: Path, path: Path, *, now: datetime) -> dict[str, object]:
    report = inspect(path)
    if any(report["unsettled_by_namespace"].values()):
        raise PermissionError("all earlier attempts must be settled")
    with closing(sqlite3.connect(path.resolve(strict=True).as_uri() + "?mode=ro", uri=True)) as db:
        project = json.loads(db.execute("SELECT document FROM authorization").fetchone()[0])[
            "project_sha256"
        ]
    retained = report["latest_recorded_ceiling"] - report["total_consumed"]
    if retained < report["retained_bound_slots"]:
        raise PermissionError("all earlier unused allocations must remain retained")
    scope = Scope(
        origin="provider",
        ledger_reference=str(path.resolve(strict=True)),
        historical_sha256=report["historical_snapshot_sha256"],
        historical_consumed=report["total_consumed"],
        retained_bound_slots=retained,
        lifetime_ceiling=report["latest_recorded_ceiling"] + 292,
        project_sha256=project,
        source_sha256=source_pin(ROOT),
        environment_sha256=environment_pin(),
        reference_sha256=reference_pin(),
        starts_at=now,
        expires_at=now + timedelta(days=7),
        policy=policy(),
        schedule=slots(),
    )
    verify_runtime(scope)
    prepare_references(output)
    write(output / "scope.json", scope.model_dump(mode="json"))
    result = {
        "scope_sha256": digest(scope.canonical_json().encode()),
        "tasks": 146,
        "maximum_attempts": 292,
        "historical_consumed": scope.historical_consumed,
        "retained_bound_slots": retained,
        "proposed_lifetime_ceiling": scope.lifetime_ceiling,
        "max_token_reservation": scope.max_tokens,
        "expires_at": scope.expires_at.isoformat(),
        "provider_calls_authorized": 0,
    }
    write(output / "proposal.json", result)
    return result


def private_worker(configuration: Path, project_sha256: str) -> SDKWorker:
    """Load only the explicitly selected file and verify the prior project association."""
    from prior_auth_study_budget import pin
    from prior_auth_study_run import private_configuration

    path = private_configuration(configuration)
    values = dict(
        line.split("=", 1)
        for line in path.read_text().splitlines()
        if "=" in line and not line.startswith("#")
    )
    key = values["GEMINI_API_KEY"].strip().strip("\"'")
    if not key or values.get("GEMINI_FREE_TIER_CONFIRMED", "").strip().lower() not in {
        "true",
        "1",
        "yes",
    }:
        raise PermissionError("configured Free confirmation required")
    association = pin(
        {
            "configuration_reference": str(path),
            "credential_sha256": digest(key.encode()),
            "meaning": (
                "operator-selected-credential-association-not-provider-verified-cloud-project"
            ),
        }
    )
    if association != project_sha256:
        raise PermissionError("same authorized project association required")
    return SDKWorker(key, association)


def main() -> None:
    cli = argparse.ArgumentParser(description=__doc__)
    mode = cli.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", type=Path)
    mode.add_argument("--capture", type=Path)
    mode.add_argument("--readback", type=Path)
    cli.add_argument("--ledger", type=Path, required=True)
    cli.add_argument("--owner-grant", type=Path)
    cli.add_argument("--owner-grant-pin")
    cli.add_argument("--configuration", type=Path)
    args = cli.parse_args()
    if args.prepare:
        result = prepare(args.prepare, args.ledger, now=datetime.now(UTC))
    else:
        if not args.owner_grant or not args.owner_grant_pin:
            cli.error("separate exact owner grant and trusted pin required")
        scope = Scope.model_validate_json((args.capture or args.readback).read_bytes())
        grant = OwnerGrant.model_validate_json(args.owner_grant.read_bytes())
        if digest(
            grant.canonical_json().encode()
        ) != args.owner_grant_pin or grant.scope_sha256 != digest(scope.canonical_json().encode()):
            raise PermissionError("exact owner grant pin required")
        if args.capture:
            if not args.configuration:
                cli.error("capture requires the existing selected private Gemini configuration")
            verify_runtime(scope)
            ledger = initialize(
                args.ledger, scope, grant, trusted_grant_sha256=args.owner_grant_pin
            )
            worker = private_worker(args.configuration, scope.project_sha256)
            result = capture(ledger, SDKTransport(worker))
        else:
            result = readback(Ledger(args.ledger, grant.scope_sha256, args.owner_grant_pin))
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
