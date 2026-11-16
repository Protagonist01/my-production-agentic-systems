"""Explicit Gemini runtime composition over a separate approved same-file grant.

No implicit grant, key loader, provider fallback or new ledger file. The owner must
approve final request/source/environment pins before trusted administration calls
initialize. This implementation alone never authorizes a provider attempt.
"""

import hashlib
import json
import platform
import re
import sqlite3
import subprocess
import sys
from collections.abc import Callable
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Any, Literal

from agent_harness.admission import GEMINI_TOKEN_CEILING
from agent_harness.contracts import ModelRequest, ModelResponse, RunContext, WireContract
from agent_harness.controls import DeadlineGateway
from agent_harness.gateway import failed_response
from prior_auth.contracts import Claim, Digest, Id, NoteInput, Policy, digest
from prior_auth.review_store import ReviewStore
from prior_auth.source_io import external
from pydantic import AwareDatetime, Field, model_validator

from prior_auth_demo_runtime import Scope
from prior_auth_profiling import Profiler

PREFIX = "pa_live_"
TABLES = {"pa_live_grant", "pa_live_attempts", "pa_live_settlements", "pa_live_stop"}


def supported_canary(response: ModelResponse, request: ModelRequest, note: NoteInput) -> bool:
    from prior_auth.assessment import check_claim
    from prior_auth.source import matching_spans

    from prior_auth_study_run import parse

    proposed = parse(response, request, note)
    if proposed is None or proposed.state != "met":
        return False
    claim = Claim(
        criterion_id=proposed.criterion_id,
        state=proposed.state,
        evidence=tuple(s for quote in proposed.quotes for s in matching_spans(note.text, quote)),
        rationale=proposed.rationale,
    )
    return check_claim(note, claim).state == "met"


def scope_binding(scope: Scope) -> str:
    value = scope.model_dump(mode="json")
    # Grant and runtime scope cross-reference one another. Exclude only this
    # reciprocal pointer from the scope hash to avoid an impossible hash cycle.
    value.pop("provider_scope_sha256")
    return digest(json.dumps(value, sort_keys=True, separators=(",", ":")))


def execution_pin(root: Path) -> str:
    names = subprocess.check_output(
        ["git", "ls-files", "--", "*.py", "*.sql", "uv.lock", "pyproject.toml"], cwd=root, text=True
    ).splitlines()
    return digest(
        json.dumps(
            {
                "code": {
                    n: hashlib.sha256((root / n).read_bytes()).hexdigest() for n in sorted(names)
                },
                "environment": {"python": sys.version, "platform": platform.platform()},
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )


def history(db: sqlite3.Connection) -> str:
    schema = db.execute(
        "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name"
    ).fetchall()
    schema = [r for r in schema if r[2] not in TABLES]
    rows = {}
    for kind, name, _, _ in schema:
        if kind == "table":
            if not re.fullmatch(r"[A-Za-z_]\w*", name):
                raise ValueError("unexpected ledger name")
            rows[name] = sorted(
                json.dumps(r, separators=(",", ":"))
                for r in db.execute('SELECT * FROM "' + name + '"')
            )
    return digest(
        json.dumps({"schema": schema, "rows": rows}, sort_keys=True, separators=(",", ":"))
    )


class Slot(WireContract):
    phase: Literal["canary", "domain"]
    case_id: Id
    request_sha256: Digest


class Grant(WireContract):
    version: Literal["prior-auth-live-gemini-v1"] = "prior-auth-live-gemini-v1"
    approval_ref: Annotated[str, Field(min_length=1, max_length=200)]
    free_project_confirmed: Literal[True]
    project_association_sha256: Digest
    historical_sha256: Digest
    execution_sha256: Digest
    runtime_scope_sha256: Digest
    starts_at: AwareDatetime
    expires_at: AwareDatetime
    historical_consumed: Literal[615] = 615
    lifetime_ceiling: Annotated[int, Field(ge=787, le=952)] = 952
    old_slots_preserved: Literal[169] = 169
    max_tokens: Literal[2000000] = 2000000
    slots: Annotated[tuple[Slot, ...], Field(min_length=3, max_length=168)]

    @model_validator(mode="after")
    def bounded(self) -> "Grant":
        if (
            self.historical_consumed + self.old_slots_preserved + len(self.slots)
            > self.lifetime_ceiling
        ):
            raise ValueError("ceiling must preserve every old bound slot plus the new schedule")
        if not timedelta(0) < self.expires_at - self.starts_at <= timedelta(days=7):
            raise ValueError("at most seven days required")
        if [s.phase for s in self.slots[:2]] != ["canary", "canary"] or any(
            s.phase != "domain" for s in self.slots[2:]
        ):
            raise ValueError("two canaries then domain slots required")
        return self


class Ledger:
    def __init__(self, path: Path, pin: str):
        self.path, self.pin = external(path), pin

    def connect(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.path.as_uri() + "?mode=rw", uri=True, timeout=10)
        c.execute("PRAGMA synchronous=FULL")
        c.execute("PRAGMA foreign_keys=ON")
        return c

    def grant(self, c: sqlite3.Connection) -> Grant:
        row = c.execute("SELECT pin,document FROM pa_live_grant").fetchall()
        if len(row) != 1 or row[0][0] != self.pin or digest(row[0][1]) != self.pin:
            raise ValueError("external live grant pin differs")
        grant = Grant.model_validate_json(row[0][1])
        if history(c) != grant.historical_sha256:
            raise ValueError("prior history changed")
        return grant

    def reserve(self, case_id: str, request: ModelRequest, *, phase: str, now: datetime) -> int:
        with closing(self.connect()) as c, c:
            c.execute("BEGIN IMMEDIATE")
            grant = self.grant(c)
            if (
                not grant.starts_at <= now < grant.expires_at
                or c.execute("SELECT 1 FROM pa_live_stop").fetchone()
            ):
                raise PermissionError("live grant expired/stopped")
            count = c.execute("SELECT count(*) FROM pa_live_attempts").fetchone()[0]
            settled = c.execute("SELECT count(*) FROM pa_live_settlements").fetchone()[0]
            tokens = c.execute(
                "SELECT coalesce(sum(tokens),0) FROM pa_live_settlements"
            ).fetchone()[0]
            if (
                count != settled
                or count >= len(grant.slots)
                or tokens + GEMINI_TOKEN_CEILING > grant.max_tokens
            ):
                raise PermissionError("outstanding/exhausted live grant")
            slot = grant.slots[count]
            if (slot.phase, slot.case_id, slot.request_sha256) != (
                phase,
                case_id,
                request.fingerprint(),
            ):
                raise PermissionError("request outside exact ordered live slot")
            if (
                phase == "domain"
                and c.execute(
                    "SELECT count(*) FROM pa_live_settlements "
                    "WHERE ordinal IN(1,2) AND canary_pass=1"
                ).fetchone()[0]
                != 2
            ):
                raise PermissionError("both canaries must pass")
            ordinal = count + 1
            c.execute(
                "INSERT INTO pa_live_attempts VALUES(?,?,?)",
                (ordinal, request.fingerprint(), now.isoformat()),
            )
            return int(ordinal)

    def settle(self, ordinal: int, response: ModelResponse, *, canary_pass: bool) -> None:
        usage = response.usage
        tokens = (
            None
            if usage.input_tokens is None or usage.output_tokens is None
            else usage.input_tokens + usage.output_tokens
        )
        stopped = (
            response.failure is not None
            or tokens is None
            or tokens > GEMINI_TOKEN_CEILING
            or usage.model_calls != 1
            or (usage.cost is not None and usage.cost != 0)
        )
        with closing(self.connect()) as c, c:
            c.execute("BEGIN IMMEDIATE")
            grant = self.grant(c)
            if not c.execute(
                "SELECT 1 FROM pa_live_attempts WHERE ordinal=?", (ordinal,)
            ).fetchone():
                raise ValueError("unreserved settlement")
            if canary_pass and grant.slots[ordinal - 1].phase != "canary":
                raise ValueError("not a canary")
            text = response.canonical_json()
            c.execute(
                "INSERT INTO pa_live_settlements VALUES(?,?,?,?,?)",
                (ordinal, tokens, int(canary_pass and not stopped), digest(text), text),
            )
            if stopped or (grant.slots[ordinal - 1].phase == "canary" and not canary_pass):
                c.execute(
                    "INSERT OR IGNORE INTO pa_live_stop VALUES(1,?)", ("failed_unknown_or_canary",)
                )

    def summary(self) -> dict[str, Any]:
        with closing(self.connect()) as c:
            grant = self.grant(c)
            count = c.execute("SELECT count(*) FROM pa_live_attempts").fetchone()[0]
            settled = c.execute("SELECT count(*) FROM pa_live_settlements").fetchone()[0]
            return {
                "historical_consumed": 615,
                "new_consumed": count,
                "total_consumed": 615 + count,
                "lifetime_ceiling": grant.lifetime_ceiling,
                "unsettled": count - settled,
                "stopped": bool(c.execute("SELECT 1 FROM pa_live_stop").fetchone()),
                "old_history_unchanged": True,
                "old_bound_slots_preserved": grant.old_slots_preserved,
                "known_token_subtotal": c.execute(
                    "SELECT coalesce(sum(tokens),0) FROM pa_live_settlements"
                ).fetchone()[0],
                "unknown_token_settlements": c.execute(
                    "SELECT count(*) FROM pa_live_settlements WHERE tokens IS NULL"
                ).fetchone()[0],
                "known_subtotals_are_not_complete_cost": True,
            }


def initialize(path: Path, grant: Grant) -> Ledger:
    """Trusted owner-approved provisioner only; never called by a worker automatically."""
    grant = Grant.model_validate_json(grant.canonical_json())
    ledger = Ledger(path, digest(grant.canonical_json()))
    with closing(ledger.connect()) as c, c:
        c.execute("BEGIN IMMEDIATE")
        if history(c) != grant.historical_sha256:
            raise ValueError("exact prior history required")
        if (
            c.execute("SELECT count(*) FROM attempts").fetchone()[0] != 447
            or c.execute("SELECT count(*) FROM attempts WHERE response_pin IS NULL").fetchone()[0]
            or c.execute("SELECT count(*) FROM pa_reservations").fetchone()[0] != 168
            or c.execute("SELECT count(*) FROM pa_settlements").fetchone()[0] != 168
            or c.execute("SELECT 1 FROM pa_stops").fetchone()
        ):
            raise ValueError("complete settled615 history required")
        original = json.loads(c.execute("SELECT document FROM authorization").fetchone()[0])
        if original["project_sha256"] != grant.project_association_sha256:
            raise PermissionError("existing project association required")
        c.execute("CREATE TABLE pa_live_grant(pin TEXT PRIMARY KEY,document TEXT NOT NULL)")
        c.execute("INSERT INTO pa_live_grant VALUES(?,?)", (ledger.pin, grant.canonical_json()))
        c.execute(
            "CREATE TABLE pa_live_attempts(ordinal INTEGER PRIMARY KEY,"
            "request TEXT NOT NULL,created TEXT NOT NULL)"
        )
        c.execute(
            "CREATE TABLE pa_live_settlements(ordinal INTEGER PRIMARY KEY REFERENCES "
            "pa_live_attempts,tokens INTEGER,canary_pass INTEGER NOT NULL,"
            "response_pin TEXT NOT NULL,response TEXT NOT NULL)"
        )
        c.execute(
            "CREATE TABLE pa_live_stop(id INTEGER PRIMARY KEY CHECK(id=1),reason TEXT NOT NULL)"
        )
        for table in TABLES:
            for operation in ("UPDATE", "DELETE"):
                c.execute(
                    f"CREATE TRIGGER immutable_{table}_{operation} BEFORE {operation} ON {table} "
                    "BEGIN SELECT RAISE(ABORT,'immutable live history'); END"
                )
    return ledger


class LiveGateway:
    """Concrete deadline transport for DemoWorker; domain needs SQL reservation first."""

    def __init__(
        self,
        store: ReviewStore,
        scope: Scope,
        ledger: Ledger,
        transport: DeadlineGateway,
        *,
        execution_probe: Callable[[], str],
        project_association_sha256: str,
        profiler: Profiler | None = None,
    ):
        self.store, self.scope, self.ledger, self.transport = store, scope, ledger, transport
        self.execution_probe = execution_probe
        self.project_association_sha256 = project_association_sha256
        self.profiler = profiler or Profiler()

    def validate(self, scope: Scope, request: ModelRequest) -> None:
        with closing(self.ledger.connect()) as c:
            grant = self.ledger.grant(c)
        if (
            scope != self.scope
            or scope.mode != "fresh_candidate"
            or scope.provider_scope_sha256 != self.ledger.pin
            or scope_binding(scope) != grant.runtime_scope_sha256
            or self.execution_probe() != grant.execution_sha256
            or self.project_association_sha256 != grant.project_association_sha256
            or not grant.starts_at <= datetime.now(UTC) < grant.expires_at
            or (request.provider, request.endpoint, request.model)
            != (
                "google-gemini-developer-api",
                "https://generativelanguage.googleapis.com",
                "gemini-3.5-flash-lite",
            )
            or request.fingerprint() not in {s.request_sha256 for s in grant.slots}
        ):
            raise PermissionError("live scope/route/source/project differs")

    def _dispatch(
        self,
        context: RunContext,
        request: ModelRequest,
        phase: str,
        *,
        canary_check: Callable[[ModelResponse], bool] | None = None,
    ) -> ModelResponse:
        self.validate(self.scope, request)
        if (
            context.tenant_id != self.scope.tenant_id
            or context.case_id not in self.scope.case_ids
            or context.mode != "fresh_candidate"
            or context.run_id != self.scope.scope_id
            or context.agent_id != "prior-auth"
            or context.versions.candidate != self.scope.candidate
            or context.versions.code_revision != self.scope.code_revision
            or context.versions.environment_lock != self.scope.environment_sha256
        ):
            raise PermissionError("live context outside scope")
        ordinal = self.ledger.reserve(context.case_id, request, phase=phase, now=datetime.now(UTC))
        self.profiler.model_attempts += 1
        try:
            seconds = min(
                110,
                (context.deadline - datetime.now(UTC)).total_seconds(),
                (self.scope.expires_at - datetime.now(UTC)).total_seconds(),
            )
            if seconds <= 0:
                raise TimeoutError()
            with self.profiler.span("model"):
                response = ModelResponse.model_validate_json(
                    self.transport.generate(
                        context, request, timeout_seconds=seconds
                    ).canonical_json()
                )
            if (response.provider, response.model) != (request.provider, request.model):
                raise ValueError("wrong route")
        except Exception:
            response = failed_response(
                request, "unavailable", "Live result unavailable; usage unknown", dispatched=True
            )
        self.profiler.usage.append(response.usage)
        passed = False
        if canary_check is not None:
            try:
                passed = bool(canary_check(response))
            except Exception:
                passed = False
        self.ledger.settle(ordinal, response, canary_pass=passed)
        return response

    def canary(
        self,
        context: RunContext,
        request: ModelRequest,
        note: "NoteInput",
        policy: "Policy",
    ) -> ModelResponse:
        """Only exact, positive, constructed canaries; checker is never model-selected."""
        from prior_auth_demo_fixtures import note as fixed_note
        from prior_auth_demo_fixtures import requests

        if note != fixed_note(note.case_id, policy) or request not in requests((note,), policy)[:2]:
            raise PermissionError("exact complete-note adult/education canary required")
        if (context.case_id, context.tenant_id) != (note.case_id, note.tenant_id):
            raise PermissionError("canary context differs")
        return self._dispatch(
            context,
            request,
            "canary",
            canary_check=lambda response: supported_canary(response, request, note),
        )

    def generate(self, context: RunContext, request: ModelRequest) -> ModelResponse:
        if context.run_id != self.scope.scope_id or not context.trial_id.startswith(
            "case-version-"
        ):
            raise PermissionError("canonical SQL work context required")
        version = int(context.trial_id.removeprefix("case-version-"))
        # The durable SQL layer has committed its reservation before entering here.
        with self.store.transaction() as c:
            row = c.execute(
                "SELECT a.request_sha256 FROM prior_auth_demo.attempts a "
                "LEFT JOIN prior_auth_demo.settlements s USING(scope_id,work_sha256) "
                "WHERE a.scope_id=%s AND a.tenant_id=%s AND a.case_id=%s AND a.case_version=%s "
                "AND a.request_sha256=%s AND s.work_sha256 IS NULL",
                (
                    self.scope.scope_id,
                    context.tenant_id,
                    context.case_id,
                    version,
                    request.fingerprint(),
                ),
            ).fetchall()
        if len(row) != 1:
            raise PermissionError("one unsettled durable SQL reservation required")
        return self._dispatch(context, request, "domain")
