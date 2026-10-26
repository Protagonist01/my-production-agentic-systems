"""Separate maximum-12 invented-only Groq smoke allowance; never the Gemini grant."""

import math
import os
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Literal
from uuid import uuid4

from jsonschema.exceptions import SchemaError
from pydantic import AwareDatetime, Field
from referencing.exceptions import Unresolvable

from agent_harness.contracts import Contract, ModelRequest, ModelResponse, NonEmpty, RunContext
from agent_harness.gateway import DeadlineTransport, failed_response
from agent_harness.groq import ENDPOINT, MODEL, PROVIDER, request_payload
from agent_harness.provider_budget import AttemptLedger
from agent_harness.release_contracts import Sha256, pin


class SmokeAllowance(Contract):
    version: Literal["groq-invented-free-smoke-v1"] = "groq-invented-free-smoke-v1"
    authorization_ref: NonEmpty
    free_account_attestation_ref: NonEmpty
    credential_sha256: Sha256
    request_sha256: Annotated[tuple[Sha256, ...], Field(min_length=1, max_length=12)]
    max_attempts: Annotated[int, Field(gt=0, le=12)]
    approved_at: AwareDatetime
    expires_at: AwareDatetime


def initialize(path: Path, allowance: SmokeAllowance) -> str:
    allowance = SmokeAllowance.model_validate_json(allowance.canonical_json())
    if allowance.expires_at <= allowance.approved_at or len(set(allowance.request_sha256)) != len(
        allowance.request_sha256
    ):
        raise ValueError("invalid smoke interval/request inventory")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(descriptor)
    with sqlite3.connect(path) as db:
        db.executescript("""
        CREATE TABLE authorization(pin TEXT PRIMARY KEY, document TEXT NOT NULL);
        CREATE TABLE attempts(serial INTEGER PRIMARY KEY, ticket TEXT NOT NULL UNIQUE,
          context_pin TEXT NOT NULL, request_pin TEXT NOT NULL, reserved_at TEXT NOT NULL,
          response_pin TEXT, settled_at TEXT);
        CREATE TRIGGER no_delete BEFORE DELETE ON attempts
          BEGIN SELECT RAISE(ABORT,'append only'); END;
        CREATE TRIGGER no_rebind BEFORE UPDATE ON attempts
          WHEN NEW.serial!=OLD.serial OR NEW.ticket!=OLD.ticket OR NEW.context_pin!=OLD.context_pin
            OR NEW.request_pin!=OLD.request_pin OR NEW.reserved_at!=OLD.reserved_at
            OR OLD.response_pin IS NOT NULL
          BEGIN SELECT RAISE(ABORT,'immutable reservation'); END;
        """)
        db.execute(
            "INSERT INTO authorization VALUES(?,?)", (pin(allowance), allowance.canonical_json())
        )
    return pin(allowance)


@dataclass(frozen=True)
class SmokeLedger:
    path: Path
    allowance_sha256: str

    def connect(self) -> sqlite3.Connection:
        # Reuse only the existing RW/no-symlink/FULL-sync connection primitive.
        return AttemptLedger(self.path, self.allowance_sha256).connect()

    def authorization(self, db: sqlite3.Connection) -> SmokeAllowance:
        rows = db.execute("SELECT pin,document FROM authorization").fetchall()
        if len(rows) != 1 or rows[0][0] != self.allowance_sha256:
            raise ValueError("Groq smoke allowance pin differs")
        value = SmokeAllowance.model_validate_json(rows[0][1])
        if pin(value) != self.allowance_sha256 or value.expires_at <= value.approved_at:
            raise ValueError("Groq smoke allowance document differs")
        return value

    def reserve(self, context: RunContext, request: ModelRequest, credential_sha256: str) -> str:
        context = RunContext.model_validate_json(context.canonical_json())
        request = ModelRequest.model_validate_json(request.canonical_json())
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            grant = self.authorization(db)
            now = datetime.now(UTC)
            if (
                context.mode != "fresh_candidate"
                or context.agent_id != "groq-invented-smoke"
                or (request.provider, request.endpoint, request.model)
                != (PROVIDER, ENDPOINT, MODEL)
                or request.fingerprint() not in grant.request_sha256
                or credential_sha256 != grant.credential_sha256
                or not grant.approved_at <= now < grant.expires_at
                or now >= context.deadline
            ):
                raise ValueError("request outside authorized invented Groq smoke scope")
            count = db.execute("SELECT count(*) FROM attempts").fetchone()[0]
            if count >= grant.max_attempts:
                raise ValueError("Groq smoke cap exhausted")
            ticket = uuid4().hex
            db.execute(
                "INSERT INTO attempts VALUES(?,?,?,?,?,NULL,NULL)",
                (
                    count + 1,
                    ticket,
                    pin(context),
                    request.fingerprint(),
                    now.isoformat(),
                ),
            )
        return ticket

    def settle(self, ticket: str, response: ModelResponse) -> None:
        response = ModelResponse.model_validate_json(response.canonical_json())
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self.authorization(db)
            changed = db.execute(
                "UPDATE attempts SET response_pin=?,settled_at=? "
                "WHERE ticket=? AND response_pin IS NULL",
                (
                    pin(response),
                    datetime.now(UTC).isoformat(),
                    ticket,
                ),
            )
            if changed.rowcount != 1:
                raise ValueError("smoke ticket missing or already settled")

    def summary(self) -> dict[str, int]:
        with self.connect() as db:
            grant = self.authorization(db)
            consumed, unsettled = db.execute(
                "SELECT count(*),sum(response_pin IS NULL) FROM attempts"
            ).fetchone()
        return {
            "maximum": grant.max_attempts,
            "consumed": consumed,
            "remaining": grant.max_attempts - consumed,
            "unsettled": unsettled or 0,
        }


@dataclass(frozen=True)
class SmokeTransport:
    delegate: DeadlineTransport
    ledger: SmokeLedger
    context: RunContext
    credential_sha256: str

    def generate(self, request: ModelRequest, *, timeout_seconds: float = 30.0) -> ModelResponse:
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            return failed_response(
                request, "timeout", "No Groq attempt time remaining", dispatched=False
            )
        try:
            request_payload(request)
            ticket = self.ledger.reserve(self.context, request, self.credential_sha256)
        except (ValueError, OSError, sqlite3.Error, SchemaError, TypeError, Unresolvable):
            return failed_response(
                request, "budget_exhausted", "Groq smoke authorization denied", dispatched=False
            )
        # A crash/throw/failed HTTP attempt remains consumed. Never refund or retry here.
        result = self.delegate.generate(request, timeout_seconds=timeout_seconds)
        self.ledger.settle(ticket, result)
        return result
