"""Prospective single-use comparison slots in the existing shared ledger.

Installing a provider scope requires a separately trusted owner grant. This module never
loads credentials, changes old tables/stops, dispatches requests or creates a live ledger.
"""

import hashlib
import json
import re
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Annotated, Literal, Self

from agent_harness.contracts import ModelResponse, NonEmpty, WireContract
from agent_harness.cost_accounting import FreeTariff
from agent_harness.release_contracts import Sha256
from pydantic import AwareDatetime, Field, model_validator

PREFIX = "olist_semantic_"
TABLES = {PREFIX + name for name in ("scope", "attempts", "observations")}


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def pin(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def connect(path: Path) -> sqlite3.Connection:
    # mode=rw never creates a replacement for a missing lifetime ledger.
    db = sqlite3.connect(path.resolve().as_uri() + "?mode=rw", uri=True, timeout=5)
    db.execute("PRAGMA synchronous=FULL")
    return db


def historical_anchor(db: sqlite3.Connection) -> str:
    """Pin all old schema/rows, excluding only the three exact new tables/triggers."""
    result = []
    for name, table, kind, sql in db.execute(
        "SELECT name,tbl_name,type,sql FROM sqlite_master "
        "WHERE name NOT LIKE 'sqlite_%' ORDER BY name"
    ):
        if table in TABLES:
            continue
        if not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", name):
            raise ValueError("unsupported ledger schema identifier")
        if name.startswith(PREFIX) or table.startswith(PREFIX):
            raise ValueError("unexpected semantic ledger object")
        rows = []
        if kind == "table":
            rows = sorted(canonical(list(row)) for row in db.execute(f'SELECT * FROM "{name}"'))
        result.append((name, table, kind, sql, rows))
    return pin(canonical(result))


class Slot(WireContract):
    ordinal: Annotated[int, Field(ge=1, le=74)]
    phase: Literal["canary", "domain"]
    case_id: NonEmpty
    trial_id: NonEmpty
    request_sha256: Sha256


class Scope(WireContract):
    version: Literal["olist-semantic-comparison-scope-v1"] = "olist-semantic-comparison-scope-v1"
    origin: Literal["mock", "provider"]
    proposal_sha256: Sha256
    historical_anchor_sha256: Sha256
    project_sha256: Sha256
    allowance_sha256: Sha256
    tariff: FreeTariff
    source_files: dict[str, Sha256]
    environment_sha256: Sha256
    code_revision: Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]
    input_packet_sha256: Sha256
    reference_packet_sha256: Sha256
    canary_expectations_sha256: Sha256
    approved_at: AwareDatetime
    expires_at: AwareDatetime
    lifetime_cap: Literal[614] = 614
    consumed_before: Literal[447] = 447
    transferred_unattempted_routing_slots: Literal[74] = 74
    preserved_other_slots: Literal[93] = 93
    model: Literal["gemini-3.5-flash-lite"] = "gemini-3.5-flash-lite"
    http_timeout_seconds: Literal[90] = 90
    parent_timeout_seconds: Literal[110] = 110
    slots: Annotated[tuple[Slot, ...], Field(min_length=74, max_length=74)]

    @model_validator(mode="after")
    def complete(self) -> Self:
        if (
            self.tariff.project_sha256 != self.project_sha256
            or self.tariff.models != (self.model,)
            or not self.tariff.reviewed_at
            <= self.approved_at
            < self.expires_at
            <= self.tariff.expires_at
        ):
            raise ValueError("exact reviewed project/model tariff must cover the scope interval")
        if (
            not self.source_files
            or not self.approved_at < self.expires_at <= self.approved_at + timedelta(days=7)
        ):
            raise ValueError("source pins and a scope interval of at most seven days required")
        if [s.ordinal for s in self.slots] != list(range(1, 75)):
            raise ValueError("complete ordered 74-slot schedule required")
        if [s.phase for s in self.slots] != ["canary"] * 2 + ["domain"] * 72:
            raise ValueError("two canaries and 72 domain slots required")
        if len({(s.case_id, s.trial_id) for s in self.slots}) != 74:
            raise ValueError("duplicate case/trial slot")
        canaries, domain = self.slots[:2], self.slots[2:]
        if len({s.case_id for s in canaries}) != 2 or {s.case_id for s in canaries} & {
            s.case_id for s in domain
        }:
            raise ValueError("canary and domain cases must differ")
        if {s.request_sha256 for s in canaries} & {s.request_sha256 for s in domain}:
            raise ValueError("canary requests must not export domain inputs")
        if len({s.case_id for s in domain}) != 24:
            raise ValueError("24 domain cases required")
        for offset in range(2, 74, 3):
            group = self.slots[offset : offset + 3]
            if (
                len({s.case_id for s in group}) != 1
                or len({s.request_sha256 for s in group}) != 1
                or [s.trial_id for s in group] != ["trial-1", "trial-2", "trial-3"]
            ):
                raise ValueError("each case needs its unchanged request and three ordered trials")
        return self


class OwnerGrant(WireContract):
    """Trusted operator transcription; hashes do not authenticate the owner's identity."""

    scope_sha256: Sha256
    authorization_reference: NonEmpty
    exact_reply: NonEmpty
    free_project_confirmed: Literal[True]
    reallocate_74_unattempted_slots: Literal[True]
    retain_original_stop: Literal[True]
    no_paid_fallback: Literal[True]
    no_automatic_retries: Literal[True]
    development_only: Literal[True]
    limited_direct_command_reference_method_accepted: Literal[True]


def install(
    path: Path, scope: Scope, grant: OwnerGrant | None, *, trusted_grant_sha256: str | None = None
) -> str:
    scope = Scope.model_validate_json(scope.canonical_json())
    scope_pin = pin(scope.canonical_json())
    if scope.origin == "provider":
        if (
            grant is None
            or trusted_grant_sha256 is None
            or pin(grant.canonical_json()) != trusted_grant_sha256
            or grant.scope_sha256 != scope_pin
        ):
            raise ValueError("separately trusted exact provider owner grant required")
    elif grant is not None:
        raise ValueError("mock execution must not use a provider grant")
    with connect(path) as db:
        db.execute("BEGIN IMMEDIATE")
        if historical_anchor(db) != scope.historical_anchor_sha256:
            raise ValueError("old ledger history differs")
        count, unsettled = db.execute(
            "SELECT count(*),sum(response_pin IS NULL) FROM attempts"
        ).fetchone()
        stops = db.execute("SELECT count(*) FROM routing_stops").fetchone()[0]
        if (count, unsettled, stops) != (447, 0, 1):
            raise ValueError("old consumed, unsettled or stop inventory differs")
        if any(
            db.execute("SELECT 1 FROM sqlite_master WHERE name=?", (name,)).fetchone()
            for name in TABLES
        ):
            raise ValueError("scope already exists; no reset, replacement or automatic resume")
        db.execute(
            "CREATE TABLE olist_semantic_scope("
            "pin TEXT PRIMARY KEY, document TEXT NOT NULL, grant TEXT)"
        )
        db.execute(
            "INSERT INTO olist_semantic_scope VALUES(?,?,?)",
            (scope_pin, scope.canonical_json(), grant.canonical_json() if grant else None),
        )
        db.execute(
            "CREATE TABLE olist_semantic_attempts("
            "ordinal INTEGER PRIMARY KEY,request_pin TEXT NOT NULL,started TEXT NOT NULL)"
        )
        db.execute(
            "CREATE TABLE olist_semantic_observations(ordinal INTEGER PRIMARY KEY,"
            "response TEXT NOT NULL,response_pin TEXT NOT NULL,timing TEXT NOT NULL,"
            "continue_allowed INTEGER NOT NULL CHECK(continue_allowed IN (0,1)))"
        )
        for table in sorted(TABLES):
            for operation in ("UPDATE", "DELETE"):
                db.execute(
                    f"CREATE TRIGGER {table}_{operation} BEFORE {operation} ON {table} "
                    "BEGIN SELECT RAISE(ABORT,'immutable semantic evidence'); END"
                )
    return scope_pin


def _scope(
    db: sqlite3.Connection, expected: str, now: datetime, origin: str, *, settling: bool = False
) -> Scope:
    rows = db.execute("SELECT pin,document,grant FROM olist_semantic_scope").fetchall()
    if len(rows) != 1 or rows[0][0] != expected or pin(rows[0][1]) != expected:
        raise ValueError("exact installed scope required")
    scope = Scope.model_validate_json(rows[0][1])
    if (
        now.tzinfo is None
        or now < scope.approved_at
        or (now >= scope.expires_at and not settling)
        or scope.origin != origin
    ):
        raise ValueError("scope clock or execution origin differs")
    if scope.origin == "provider":
        grant = OwnerGrant.model_validate_json(rows[0][2])
        if grant.scope_sha256 != expected:
            raise ValueError("provider grant differs")
    if historical_anchor(db) != scope.historical_anchor_sha256:
        raise ValueError("historical ledger changed")
    return scope


def reserve(path: Path, expected: str, slot: Slot, *, now: datetime, origin: str) -> None:
    """Durably consume before dispatch; never roll back consumption after uncertainty."""
    with connect(path) as db:
        db.execute("BEGIN IMMEDIATE")
        scope = _scope(db, expected, now, origin)
        if scope.slots[slot.ordinal - 1] != slot:
            raise ValueError("request/case/trial/phase differs from frozen slot")
        used = db.execute("SELECT count(*) FROM olist_semantic_attempts").fetchone()[0]
        observed, stopped = db.execute(
            "SELECT count(*),sum(continue_allowed=0) FROM olist_semantic_observations"
        ).fetchone()
        if used != observed or stopped or slot.ordinal != used + 1 or used >= 74:
            raise ValueError("unobserved, stopped, repeated or out-of-order attempt")
        if scope.consumed_before + used + 1 + scope.preserved_other_slots > scope.lifetime_cap:
            raise ValueError("shared lifetime cap or preserved slots exhausted")
        db.execute(
            "INSERT INTO olist_semantic_attempts VALUES(?,?,?)",
            (slot.ordinal, slot.request_sha256, now.isoformat()),
        )


def observe(
    path: Path,
    expected: str,
    slot: Slot,
    response: ModelResponse,
    timing: dict[str, object],
    *,
    continue_allowed: bool,
    now: datetime,
    origin: str,
) -> None:
    """One atomic durable response/parent observation before another reservation."""
    response = ModelResponse.model_validate_json(response.canonical_json())
    raw = response.canonical_json()
    with connect(path) as db:
        db.execute("BEGIN IMMEDIATE")
        scope = _scope(db, expected, now, origin, settling=True)
        if scope.slots[slot.ordinal - 1] != slot:
            raise ValueError("observed slot differs")
        attempted = db.execute(
            "SELECT request_pin FROM olist_semantic_attempts WHERE ordinal=?", (slot.ordinal,)
        ).fetchone()
        if attempted != (slot.request_sha256,):
            raise ValueError("observation has no matching consumed attempt")
        if response.provider != "google-gemini-developer-api" or response.model != scope.model:
            raise ValueError("response provider/model differs")
        if response.failure is not None and continue_allowed:
            raise ValueError("provider failures must stop this development capture")
        db.execute(
            "INSERT INTO olist_semantic_observations VALUES(?,?,?,?,?)",
            (slot.ordinal, raw, pin(raw), canonical(timing), int(continue_allowed)),
        )
