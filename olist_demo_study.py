"""Exact new demo scope in the same ledger; never reuse or reset stopped studies."""

import json
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta
from functools import cache
from pathlib import Path
from typing import Annotated, Literal, Self

from agent_harness.admission import GEMINI_TOKEN_CEILING
from agent_harness.contracts import ModelRequest, ModelResponse, WireContract
from agent_harness.isolated_transport import AttemptTiming
from pydantic import AwareDatetime, Field, model_validator

from docs.evaluation.olist_semantic_candidate import SemanticOutput, parse, request
from olist_demo_acceptance import canonical, cases, digest
from olist_demo_budget_readback import historical_hash, inspect

TABLES = frozenset(
    {"olist_demo_scope", "olist_demo_attempts", "olist_demo_results", "olist_demo_stop"}
)
Pin = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class Slot(WireContract):
    case_id: str
    trial: Annotated[int, Field(ge=0, le=3)]
    request: ModelRequest


def canaries() -> tuple[tuple[str, SemanticOutput], ...]:
    return (
        (
            "Please refund exactly 12.34 SIM.",
            SemanticOutput(
                intent="refund",
                amount_status="explicit",
                requested_minor=1234,
                currency="SIM",
                amount_evidence="12.34 SIM",
            ),
        ),
        (
            "Where is my order?",
            SemanticOutput(
                intent="status",
                amount_status="not_applicable",
                requested_minor=None,
                currency="unspecified",
                amount_evidence=None,
            ),
        ),
    )


def slots() -> tuple[Slot, ...]:
    return tuple(
        [
            Slot(case_id=f"demo-canary-{i}", trial=0, request=request(text))
            for i, (text, _) in enumerate(canaries(), 1)
        ]
        + [
            Slot(case_id=case.case_id, trial=trial, request=request(case.text))
            for trial in (1, 2, 3)
            for case in cases()
        ]
    )


@cache
def schedule_pin() -> str:
    # Cache only an immutable hash, never mutable nested request dictionaries.
    return digest(canonical([s.model_dump(mode="json") for s in slots()]))


@cache
def reference_pin() -> str:
    return digest(canonical([c.model_dump(mode="json") for c in cases()]))


class Scope(WireContract):
    version: Literal["olist-portfolio-demo-study-v1"] = "olist-portfolio-demo-study-v1"
    origin: Literal["mock", "provider"]
    ledger_reference: str
    historical_sha256: Pin
    historical_consumed: Annotated[int, Field(ge=0)]
    retained_bound_slots: Annotated[int, Field(ge=0)]
    lifetime_ceiling: Annotated[int, Field(ge=0)]
    source_sha256: Pin
    environment_sha256: Pin
    reference_sha256: Pin
    project_sha256: Pin
    starts_at: AwareDatetime
    expires_at: AwareDatetime
    max_tokens: Literal[2000000] = 2000000
    http_seconds: Literal[90] = 90
    parent_seconds: Literal[110] = 110
    schedule: tuple[Slot, ...]

    @model_validator(mode="after")
    def frozen(self) -> Self:
        if (
            digest(canonical([s.model_dump(mode="json") for s in self.schedule])) != schedule_pin()
            or not Path(self.ledger_reference).is_absolute()
            or self.reference_sha256 != reference_pin()
            or self.lifetime_ceiling != self.historical_consumed + self.retained_bound_slots + 146
            or not timedelta(0) < self.expires_at - self.starts_at <= timedelta(days=7)
        ):
            raise ValueError("exact146schedule, preserved slots and bounded expiry required")
        return self


class OwnerGrant(WireContract):
    scope_sha256: Pin
    approval_ref: Annotated[str, Field(min_length=1, max_length=200)]
    configured_project_still_free: Literal[True]
    accepts_authored_demo_references: Literal[True]
    authorizes_only_this_study: Literal[True]


class Ledger:
    def __init__(self, path: Path, scope_sha256: str):
        self.path, self.pin = path.resolve(strict=True), scope_sha256

    def connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path.as_uri() + "?mode=rw", uri=True, timeout=10)
        db.execute("PRAGMA synchronous=FULL")
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def scope(self, db: sqlite3.Connection) -> Scope:
        rows = db.execute("SELECT document FROM olist_demo_scope").fetchall()
        if len(rows) != 1 or digest(rows[0][0].encode()) != self.pin:
            raise PermissionError("exact externally pinned scope required")
        scope = Scope.model_validate_json(rows[0][0])
        if scope.ledger_reference != str(self.path):
            raise PermissionError("same approved ledger path required; copies cannot spend")
        if historical_hash(db, TABLES) != scope.historical_sha256:
            raise PermissionError("historical ledger changed")
        return scope

    def reserve(self, ordinal: int, wire: ModelRequest, *, now: datetime, origin: str) -> None:
        with closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            scope = self.scope(db)
            count = db.execute("SELECT count(*) FROM olist_demo_attempts").fetchone()[0]
            settled = db.execute("SELECT count(*) FROM olist_demo_results").fetchone()[0]
            tokens = db.execute(
                "SELECT coalesce(sum(tokens),0) FROM olist_demo_results"
            ).fetchone()[0]
            if (
                origin != scope.origin
                or not scope.starts_at <= now < scope.expires_at
                or db.execute("SELECT 1 FROM olist_demo_stop").fetchone()
                or count != settled
                or ordinal != count + 1
                or not 1 <= ordinal <= 146
                or scope.schedule[ordinal - 1].request != wire
                or tokens + GEMINI_TOKEN_CEILING > scope.max_tokens
            ):
                raise PermissionError("expired, stopped, outstanding or out-of-order scope")
            if (
                ordinal > 2
                and db.execute(
                    "SELECT count(*) FROM olist_demo_results WHERE ordinal<=2 AND canary_pass=1"
                ).fetchone()[0]
                != 2
            ):
                raise PermissionError("both canaries must pass")
            db.execute(
                "INSERT INTO olist_demo_attempts VALUES(?,?,?)",
                (ordinal, wire.fingerprint(), now.isoformat()),
            )

    def settle(
        self,
        ordinal: int,
        response: ModelResponse,
        elapsed_ms: float,
        timing_json: str | None = None,
    ) -> None:
        if timing_json is not None:
            timing_json = AttemptTiming.model_validate_json(timing_json).canonical_json()
        with closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            scope = self.scope(db)
            reserved = db.execute(
                "SELECT request_sha256 FROM olist_demo_attempts WHERE ordinal=?", (ordinal,)
            ).fetchone()
            if not 1 <= ordinal <= 146 or reserved != (
                scope.schedule[ordinal - 1].request.fingerprint(),
            ):
                raise ValueError("reserved exact request required")
            response = ModelResponse.model_validate_json(response.canonical_json())
            wire = scope.schedule[ordinal - 1].request
            usage = response.usage
            tokens = (
                None
                if usage.input_tokens is None or usage.output_tokens is None
                else usage.input_tokens + usage.output_tokens
            )
            stopped = (
                response.provider != wire.provider
                or response.model != wire.model
                or (
                    response.failure is not None
                    and not (ordinal > 2 and response.failure.code == "invalid_response")
                )
                or usage.model_calls != 1
                or tokens is None
                or tokens > GEMINI_TOKEN_CEILING
                or (usage.cost is not None and usage.cost != 0)
            )
            canary_pass = False
            if ordinal <= 2 and not stopped:
                try:
                    output = response.output
                    canary_pass = bool(
                        output
                        and not output.tool_calls
                        and output.content
                        and parse(canaries()[ordinal - 1][0], output.content)
                        == canaries()[ordinal - 1][1]
                    )
                except ValueError:
                    pass
            # Domain interpretation errors remain observations; no prompt repair/retry.
            db.execute(
                "INSERT INTO olist_demo_results VALUES(?,?,?,?,?,?)",
                (
                    ordinal,
                    response.canonical_json(),
                    tokens,
                    int(canary_pass),
                    elapsed_ms,
                    timing_json,
                ),
            )
            if stopped or (ordinal <= 2 and not canary_pass):
                db.execute(
                    "INSERT OR IGNORE INTO olist_demo_stop VALUES(1,?)",
                    ("failed_unknown_usage_or_canary",),
                )


def initialize(
    path: Path,
    scope: Scope,
    grant: OwnerGrant | None = None,
    *,
    trusted_grant_sha256: str | None = None,
) -> Ledger:
    """Trusted provisioner only. A prepared scope alone never admits a real request."""
    scope = Scope.model_validate_json(scope.canonical_json())
    if scope.ledger_reference != str(path.resolve(strict=True)):
        raise PermissionError("same approved ledger path required")
    if scope.origin == "provider":
        if grant is not None:
            grant = OwnerGrant.model_validate_json(grant.canonical_json())
        if (
            grant is None
            or digest(grant.canonical_json().encode()) != trusted_grant_sha256
            or grant.scope_sha256 != digest(scope.canonical_json().encode())
        ):
            raise PermissionError("separate exact owner grant/current Free confirmation required")
    elif grant is not None or trusted_grant_sha256 is not None:
        raise PermissionError("mock execution must not carry provider authority")
    report = inspect(path)
    if (
        report["total_consumed"] != scope.historical_consumed
        or report["retained_bound_slots"] != scope.retained_bound_slots
        or any(report["unsettled_by_namespace"].values())
    ):
        raise PermissionError("complete aggregate history and preserved slots required")
    ledger = Ledger(path, digest(scope.canonical_json().encode()))
    with closing(ledger.connect()) as db, db:
        db.execute("BEGIN IMMEDIATE")
        if historical_hash(db) != scope.historical_sha256:
            raise PermissionError("historical snapshot changed")
        original = json.loads(db.execute("SELECT document FROM authorization").fetchone()[0])
        if original["project_sha256"] != scope.project_sha256:
            raise PermissionError("existing project association required")
        db.execute(
            "CREATE TABLE olist_demo_scope(id INTEGER PRIMARY KEY CHECK(id=1),"
            "document TEXT NOT NULL)"
        )
        db.execute("INSERT INTO olist_demo_scope VALUES(1,?)", (scope.canonical_json(),))
        db.execute(
            "CREATE TABLE olist_demo_attempts(ordinal INTEGER PRIMARY KEY,"
            "request_sha256 TEXT NOT NULL,created TEXT NOT NULL)"
        )
        db.execute(
            "CREATE TABLE olist_demo_results(ordinal INTEGER PRIMARY KEY REFERENCES "
            "olist_demo_attempts,response TEXT NOT NULL,tokens INTEGER,"
            "canary_pass INTEGER NOT NULL,"
            "elapsed_ms REAL NOT NULL CHECK(elapsed_ms>=0),process_timing TEXT)"
        )
        db.execute(
            "CREATE TABLE olist_demo_stop(id INTEGER PRIMARY KEY CHECK(id=1),reason TEXT NOT NULL)"
        )
        for table in TABLES:
            for operation in ("UPDATE", "DELETE"):
                db.execute(
                    f"CREATE TRIGGER immutable_{table}_{operation} BEFORE {operation} ON {table} "
                    "BEGIN SELECT RAISE(ABORT,'immutable demo history'); END"
                )
    return ledger
