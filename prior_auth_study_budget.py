"""Append-only PA development scope in the existing shared SQLite budget file.

Historical tables/triggers remain byte-for-byte equivalent as logical SQL data.
The historical stopped routing scope is never reopened or modified. This separate
namespace is explicitly budgeted and counted; old ledger clients do not understand it.
"""

import hashlib
import json
import re
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal

from agent_harness.contracts import WireContract
from prior_auth.contracts import Digest
from prior_auth.source_io import external
from pydantic import AwareDatetime, Field, model_validator

OWN = {"pa_scope", "pa_reservations", "pa_settlements", "pa_stops"}


def pin(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode()
    ).hexdigest()


def historical_snapshot(db: sqlite3.Connection) -> str:
    schema = db.execute(
        "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name"
    ).fetchall()
    schema = [row for row in schema if row[2] not in OWN]
    rows = {}
    for kind, name, _, _ in schema:
        if kind == "table":
            if not re.fullmatch(r"[A-Za-z_]\w*", name):
                raise ValueError("unexpected historical table name")
            rows[name] = sorted(
                json.dumps(row, separators=(",", ":"))
                for row in db.execute('SELECT * FROM "' + name + '"')
            )
    return pin({"schema": schema, "rows": rows})


class Slot(WireContract):
    ordinal: Annotated[int, Field(ge=1, le=170)]
    phase: Literal["canary", "domain"]
    case_id: str
    trial: Annotated[int, Field(ge=0, le=1)]
    criterion: str
    request_sha256: Digest


class Grant(WireContract):
    version: Literal["prior-auth-development-784-v1"] = "prior-auth-development-784-v1"
    authorization_ref: Literal["owner-2026-11-13-approved-pa-v2-and-confirmed-Free"] = (
        "owner-2026-11-13-approved-pa-v2-and-confirmed-Free"
    )
    packet_sha256: Digest
    historical_sha256: Digest
    project_sha256: Digest
    execution_sha256: Digest
    approved_at: AwareDatetime
    expires_at: AwareDatetime
    maximum: Literal[784] = 784
    new_attempts_max: Literal[170] = 170
    historical_consumed: Literal[447] = 447
    slots: Annotated[tuple[Slot, ...], Field(min_length=3, max_length=170)]

    @model_validator(mode="after")
    def complete(self) -> "Grant":
        if not 0 < (self.expires_at - self.approved_at).total_seconds() <= 7 * 86400:
            raise ValueError("approved seven-day scope required")
        if [s.ordinal for s in self.slots] != list(range(1, len(self.slots) + 1)) or (
            [s.phase for s in self.slots[:2]] != ["canary", "canary"]
            or any(s.phase != "domain" for s in self.slots[2:])
        ):
            raise ValueError("two canaries then fixed ordered domain slots required")
        return self


class Ledger:
    def __init__(self, path: Path, scope_pin: str) -> None:
        self.path, self.scope_pin = external(path), scope_pin

    def connect(self) -> sqlite3.Connection:
        if self.path.is_symlink():
            raise ValueError("budget symlink refused")
        db = sqlite3.connect(self.path.as_uri() + "?mode=rw", uri=True, timeout=10)
        db.execute("PRAGMA synchronous=FULL")
        return db

    def grant(self, db: sqlite3.Connection) -> Grant:
        rows = db.execute("SELECT pin,document FROM pa_scope").fetchall()
        if len(rows) != 1 or rows[0][0] != self.scope_pin:
            raise ValueError("external PA scope pin differs")
        grant = Grant.model_validate_json(rows[0][1])
        if hashlib.sha256(grant.canonical_json().encode()).hexdigest() != self.scope_pin:
            raise ValueError("PA scope bytes differ")
        if historical_snapshot(db) != grant.historical_sha256:
            raise ValueError("historical ledger changed")
        return grant

    def reserve(self, ordinal: int, request_pin: str, *, now: datetime) -> None:
        with closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            grant = self.grant(db)
            if not grant.approved_at <= now < grant.expires_at:
                raise ValueError("PA scope expired/not active")
            if db.execute("SELECT count(*) FROM pa_stops").fetchone()[0]:
                raise ValueError("PA study stopped")
            count = db.execute("SELECT count(*) FROM pa_reservations").fetchone()[0]
            settled = db.execute("SELECT count(*) FROM pa_settlements").fetchone()[0]
            if (
                count != settled
                or ordinal != count + 1
                or count >= len(grant.slots)
                or count >= 170
            ):
                raise ValueError("outstanding, repeated or out-of-order PA attempt")
            slot = grant.slots[count]
            if slot.request_sha256 != request_pin:
                raise ValueError("request outside approved slot")
            if (
                slot.phase == "domain"
                and db.execute(
                    "SELECT count(*) FROM pa_settlements WHERE ordinal IN(1,2) AND canary_pass=1"
                ).fetchone()[0]
                != 2
            ):
                raise ValueError("both canaries must pass")
            total = db.execute("SELECT COALESCE(sum(tokens),0) FROM pa_settlements").fetchone()[0]
            # Reserve the existing reviewed full input+output ceiling before I/O.
            from agent_harness.admission import GEMINI_TOKEN_CEILING

            if total + GEMINI_TOKEN_CEILING > 2_000_000 or 447 + count + 1 > 784:
                raise ValueError("shared attempt/token budget exhausted")
            db.execute(
                "INSERT INTO pa_reservations VALUES(?,?,?)", (ordinal, request_pin, now.isoformat())
            )

    def settle(
        self,
        ordinal: int,
        document: dict[str, object],
        *,
        tokens: int | None,
        canary_pass: bool,
        stop: str | None,
    ) -> None:
        with closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            grant = self.grant(db)
            reserved = db.execute(
                "SELECT count(*) FROM pa_reservations WHERE ordinal=?", (ordinal,)
            ).fetchone()[0]
            if (
                not reserved
                or not 1 <= ordinal <= len(grant.slots)
                or (canary_pass and grant.slots[ordinal - 1].phase != "canary")
                or (tokens is not None and (type(tokens) is not int or tokens < 0))
            ):
                raise ValueError("invalid PA settlement")
            db.execute(
                "INSERT INTO pa_settlements VALUES(?,?,?,?,?)",
                (
                    ordinal,
                    tokens,
                    int(canary_pass),
                    pin(document),
                    json.dumps(document, sort_keys=True, separators=(",", ":"), allow_nan=False),
                ),
            )
            from agent_harness.admission import GEMINI_TOKEN_CEILING

            if tokens is not None and (
                tokens > GEMINI_TOKEN_CEILING
                or db.execute("SELECT COALESCE(sum(tokens),0) FROM pa_settlements").fetchone()[0]
                > 2_000_000
            ):
                stop = "token_bound_breach"
            if stop is not None or tokens is None:
                db.execute("INSERT INTO pa_stops VALUES(1,?)", (stop or "usage_unknown",))

    def summary(self) -> dict[str, object]:
        with closing(self.connect()) as db:
            grant = self.grant(db)
            count = db.execute("SELECT count(*) FROM pa_reservations").fetchone()[0]
            settled = db.execute("SELECT count(*) FROM pa_settlements").fetchone()[0]
            stops = db.execute("SELECT reason FROM pa_stops").fetchall()
            return {
                "maximum": grant.maximum,
                "historical_consumed": 447,
                "pa_consumed": count,
                "total_consumed": 447 + count,
                "pa_unsettled": count - settled,
                "stop": stops[0][0] if stops else None,
                "old_history_unchanged": True,
            }

    def stop(self, reason: Literal["admission_denied", "execution_changed_or_expired"]) -> None:
        with closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            self.grant(db)
            db.execute("INSERT OR IGNORE INTO pa_stops VALUES(1,?)", (reason,))


def initialize(path: Path, grant: Grant) -> Ledger:
    """Trusted approved caller only. No implicit grant, reset or historical migration."""
    grant = Grant.model_validate_json(grant.canonical_json())
    scope_pin = hashlib.sha256(grant.canonical_json().encode()).hexdigest()
    ledger = Ledger(path, scope_pin)
    with closing(ledger.connect()) as db, db:
        db.execute("BEGIN IMMEDIATE")
        if (
            historical_snapshot(db) != grant.historical_sha256
            or db.execute("SELECT count(*) FROM attempts").fetchone()[0] != 447
            or db.execute("SELECT count(*) FROM attempts WHERE response_pin IS NULL").fetchone()[0]
            or (db.execute("SELECT count(*) FROM routing_stops").fetchone()[0] != 1)
        ):
            raise ValueError("exact settled stopped447 history required")
        previous = json.loads(db.execute("SELECT document FROM routing_extensions").fetchone()[0])
        if previous.get("maximum") != 614:
            raise ValueError("prior shared ceiling differs")
        db.execute("CREATE TABLE pa_scope(pin TEXT PRIMARY KEY,document TEXT NOT NULL)")
        db.execute("INSERT INTO pa_scope VALUES(?,?)", (scope_pin, grant.canonical_json()))
        db.execute(
            "CREATE TABLE pa_reservations(ordinal INTEGER PRIMARY KEY,"
            "request_pin TEXT NOT NULL,created TEXT NOT NULL)"
        )
        db.execute(
            "CREATE TABLE pa_settlements(ordinal INTEGER PRIMARY KEY REFERENCES "
            "pa_reservations(ordinal),tokens INTEGER,canary_pass INTEGER NOT NULL,"
            "document_pin TEXT NOT NULL,document TEXT NOT NULL)"
        )
        db.execute("CREATE TABLE pa_stops(id INTEGER PRIMARY KEY CHECK(id=1),reason TEXT NOT NULL)")
        for table in sorted(OWN):
            for operation in ("UPDATE", "DELETE"):
                db.execute(
                    f"CREATE TRIGGER immutable_{table}_{operation} BEFORE {operation} ON {table} "
                    "BEGIN SELECT RAISE(ABORT,'immutable PA study history'); END"
                )
    return ledger
