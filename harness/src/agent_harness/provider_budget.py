"""Durable, shared, conservatively consumed provider-attempt allowance."""

import math
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Literal
from uuid import uuid4

from pydantic import AwareDatetime, Field

from agent_harness.contracts import Contract, ModelRequest, ModelResponse, NonEmpty, RunContext
from agent_harness.gateway import DeadlineTransport, failed_response
from agent_harness.release_contracts import Sha256, pin


class ProviderAllowance(Contract):
    version: Literal["shared-gemini-free-allowance-v1"] = "shared-gemini-free-allowance-v1"
    allowance_id: NonEmpty
    authorization_ref: NonEmpty
    project_sha256: Sha256
    max_attempts: Annotated[int, Field(gt=0, le=418)] = 180
    models: tuple[Literal["gemini-3.5-flash-lite", "gemini-3.8-flash"], ...]
    approved_at: AwareDatetime
    expires_at: AwareDatetime


class AllowanceAmendment(Contract):
    version: Literal["gemini-allowance-amendment-v1"] = "gemini-allowance-amendment-v1"
    previous_allowance_sha256: Sha256
    authorization_ref: NonEmpty
    maximum: Literal[320] = 320
    approved_at: AwareDatetime
    expires_at: AwareDatetime
    consumed_before: Annotated[int, Field(ge=0)]


class DevelopmentExtension(Contract):
    version: Literal["gemini-development-extension-v1"] = "gemini-development-extension-v1"
    original_allowance_sha256: Sha256
    previous_amendment_sha256: Sha256
    authorization_ref: NonEmpty
    maximum: Literal[344] = 344
    consumed_before: Literal[320] = 320
    agent: Literal["revenue"] = "revenue"
    model: Literal["gemini-3.8-flash"] = "gemini-3.8-flash"
    run_id: NonEmpty
    request_sha256s: Annotated[tuple[Sha256, ...], Field(min_length=12, max_length=12)]
    approved_at: AwareDatetime
    expires_at: AwareDatetime


def extend_development(ledger: "AttemptLedger", extension: DevelopmentExtension) -> str:
    """Append the specific owner-approved 24-attempt development extension in place."""
    extension = DevelopmentExtension.model_validate_json(extension.canonical_json())
    with ledger.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        grant = ledger.authorization(db)
        used, unsettled = db.execute(
            "SELECT count(*),sum(response_pin IS NULL) FROM attempts"
        ).fetchone()
        if (
            grant.max_attempts != 320
            or extension.model not in grant.models
            or used != 320
            or unsettled
            or extension.original_allowance_sha256 != ledger.allowance_sha256
            or extension.previous_amendment_sha256 != ledger.amendment_sha256
            or extension.approved_at < grant.approved_at
            or extension.expires_at < grant.expires_at
            or extension.expires_at <= extension.approved_at
            or len(set(extension.request_sha256s)) != 12
        ):
            raise ValueError("development extension scope/count/interval differs")
        db.execute(
            "CREATE TABLE development_extensions(pin TEXT PRIMARY KEY, document TEXT NOT NULL)"
        )
        db.execute(
            "INSERT INTO development_extensions VALUES(?,?)",
            (pin(extension), extension.canonical_json()),
        )
        db.execute(
            "CREATE TABLE development_slots(request_pin TEXT NOT NULL, "
            "trial_id TEXT NOT NULL, ticket TEXT NOT NULL UNIQUE, "
            "PRIMARY KEY(request_pin,trial_id))"
        )
        for operation in ("UPDATE", "DELETE"):
            db.execute(
                f"CREATE TRIGGER immutable_development_{operation} BEFORE {operation} "
                "ON development_extensions BEGIN SELECT RAISE(ABORT,'immutable extension'); END"
            )
            db.execute(
                f"CREATE TRIGGER immutable_slot_{operation} BEFORE {operation} "
                "ON development_slots BEGIN SELECT RAISE(ABORT,'immutable slot'); END"
            )
    return pin(extension)


def amend(path: Path, previous_pin: str, amendment: AllowanceAmendment) -> str:
    """Append an explicitly pinned amendment in place; never reset attempt history.

    Caller authenticates the owner instruction and publishes the new external pin privately.
    Old clients fail closed once an amendment exists. No attempt can be outstanding.
    """
    amendment = AllowanceAmendment.model_validate_json(amendment.canonical_json())
    ledger = AttemptLedger(path, previous_pin)
    with ledger.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        grant = ledger.authorization(db)
        used, unsettled = db.execute(
            "SELECT count(*),sum(response_pin IS NULL) FROM attempts"
        ).fetchone()
        if (
            amendment.previous_allowance_sha256 != previous_pin
            or amendment.consumed_before != used
            or unsettled
            or amendment.maximum <= grant.max_attempts
            or amendment.expires_at <= amendment.approved_at
            or amendment.approved_at < grant.approved_at
            or amendment.expires_at < grant.expires_at
        ):
            raise ValueError("allowance amendment scope/count/interval differs")
        db.execute("CREATE TABLE amendments(pin TEXT PRIMARY KEY, document TEXT NOT NULL)")
        db.execute(
            "INSERT INTO amendments VALUES(?,?)", (pin(amendment), amendment.canonical_json())
        )
        db.execute(
            "CREATE TRIGGER immutable_amendment_update BEFORE UPDATE ON amendments "
            "BEGIN SELECT RAISE(ABORT,'immutable amendment'); END"
        )
        db.execute(
            "CREATE TRIGGER immutable_amendment_delete BEFORE DELETE ON amendments "
            "BEGIN SELECT RAISE(ABORT,'immutable amendment'); END"
        )
    return pin(amendment)


def initialize(path: Path, allowance: ProviderAllowance) -> str:
    allowance = ProviderAllowance.model_validate_json(allowance.canonical_json())
    if (
        allowance.expires_at <= allowance.approved_at
        or not allowance.models
        or allowance.max_attempts > 180
    ):
        raise ValueError("allowance interval/model inventory invalid")
    # Exclusive filesystem creation prevents accidental reset of a consumed allowance.
    with path.open("xb"):
        pass
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
class AttemptLedger:
    path: Path
    allowance_sha256: str
    amendment_sha256: str | None = None
    development_extension_sha256: str | None = None
    paired_extension_sha256: str | None = None

    def development_extension(self, db: sqlite3.Connection) -> DevelopmentExtension | None:
        exists = db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='development_extensions'"
        ).fetchone()
        if not exists:
            if self.development_extension_sha256 is not None:
                raise ValueError("pinned development extension missing")
            return None
        rows = db.execute("SELECT pin,document FROM development_extensions").fetchall()
        if len(rows) != 1 or rows[0][0] != self.development_extension_sha256:
            raise ValueError("development extension requires current external pin")
        value = DevelopmentExtension.model_validate_json(rows[0][1])
        if (
            pin(value) != self.development_extension_sha256
            or value.original_allowance_sha256 != self.allowance_sha256
            or value.previous_amendment_sha256 != self.amendment_sha256
            or len(set(value.request_sha256s)) != 12
        ):
            raise ValueError("development extension pin/scope differs")
        return value

    def connect(self) -> sqlite3.Connection:
        if self.path.is_symlink():
            raise ValueError("allowance database symlink rejected")
        db = sqlite3.connect(self.path.resolve().as_uri() + "?mode=rw", uri=True, timeout=10)
        db.execute("PRAGMA synchronous=FULL")
        return db

    def authorization(self, db: sqlite3.Connection) -> ProviderAllowance:
        rows = db.execute("SELECT pin,document FROM authorization").fetchall()
        if len(rows) != 1 or rows[0][0] != self.allowance_sha256:
            raise ValueError("shared allowance authorization differs")
        value = ProviderAllowance.model_validate_json(rows[0][1])
        if pin(value) != self.allowance_sha256 or value.expires_at <= value.approved_at:
            raise ValueError("shared allowance document differs")
        exists = db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='amendments'"
        ).fetchone()
        if exists:
            amendments = db.execute("SELECT pin,document FROM amendments").fetchall()
            if len(amendments) != 1 or amendments[0][0] != self.amendment_sha256:
                raise ValueError("allowance amendment requires the current external pin")
            amendment = AllowanceAmendment.model_validate_json(amendments[0][1])
            if (
                pin(amendment) != self.amendment_sha256
                or amendment.previous_allowance_sha256 != self.allowance_sha256
                or amendment.maximum <= value.max_attempts
                or amendment.expires_at <= amendment.approved_at
                or amendment.approved_at < value.approved_at
                or amendment.expires_at < value.expires_at
                or amendment.consumed_before
                > db.execute("SELECT count(*) FROM attempts").fetchone()[0]
            ):
                raise ValueError("allowance amendment differs")
            value = value.model_copy(
                update={
                    "max_attempts": amendment.maximum,
                    "expires_at": amendment.expires_at,
                    "approved_at": amendment.approved_at,
                }
            )
        elif self.amendment_sha256 is not None:
            raise ValueError("pinned allowance amendment is missing")
        extension = self.development_extension(db)
        if extension is not None:
            used = db.execute("SELECT count(*) FROM attempts").fetchone()[0]
            if (
                value.max_attempts != 320
                or used < 320
                or extension.approved_at < value.approved_at
                or extension.expires_at < value.expires_at
                or extension.expires_at <= extension.approved_at
            ):
                raise ValueError("development extension interval/history differs")
            value = value.model_copy(
                update={
                    "max_attempts": 344,
                    "approved_at": extension.approved_at,
                    "expires_at": extension.expires_at,
                }
            )
        from agent_harness.paired_budget import paired_authorization

        return paired_authorization(db, self, value)

    def reserve(self, context: RunContext, request: ModelRequest, *, project_sha256: str) -> str:
        context = RunContext.model_validate_json(context.canonical_json())
        request = ModelRequest.model_validate_json(request.canonical_json())
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            grant = self.authorization(db)
            now = datetime.now(UTC)
            if (
                context.mode != "fresh_candidate"
                or context.agent_id not in ("olist", "cfpb", "revenue")
                or request.provider != "google-gemini-developer-api"
                or request.endpoint != "https://generativelanguage.googleapis.com"
                or request.model not in grant.models
                or project_sha256 != grant.project_sha256
                or not grant.approved_at <= now < grant.expires_at
                or now >= context.deadline
            ):
                raise ValueError("provider attempt is outside the authorized scope/interval")
            count = db.execute("SELECT count(*) FROM attempts").fetchone()[0]
            extension = self.development_extension(db)
            paired = self.paired_extension_sha256 is not None
            if extension is not None and not paired:
                prior_count = db.execute(
                    "SELECT count(*) FROM attempts WHERE serial>320 AND request_pin=?",
                    (pin(request),),
                ).fetchone()[0]
                if (
                    context.agent_id != extension.agent
                    or context.run_id != extension.run_id
                    or request.model != extension.model
                    or pin(request) not in extension.request_sha256s
                    or context.trial_id not in ("trial-1", "trial-2")
                    or prior_count >= 2
                ):
                    raise ValueError("development request outside authorized frozen schedule")
            if count >= grant.max_attempts:
                raise ValueError("shared provider-attempt allowance exhausted")
            ticket = uuid4().hex
            if paired:
                from agent_harness.paired_budget import reserve_slot

                reserve_slot(db, self, context, request, ticket)
            elif extension is not None:
                db.execute(
                    "INSERT INTO development_slots VALUES(?,?,?)",
                    (pin(request), context.trial_id, ticket),
                )
            db.execute(
                "INSERT INTO attempts VALUES(?,?,?,?,?,NULL,NULL)",
                (count + 1, ticket, pin(context), pin(request), now.isoformat()),
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
                (pin(response), datetime.now(UTC).isoformat(), ticket),
            )
            if changed.rowcount != 1:
                raise ValueError("attempt missing or already settled")

    def summary(self) -> dict[str, int | str]:
        with self.connect() as db:
            grant = self.authorization(db)
            used, unknown = db.execute(
                "SELECT count(*),sum(response_pin IS NULL) FROM attempts"
            ).fetchone()
        return dict(
            allowance_sha256=self.allowance_sha256,
            maximum=grant.max_attempts,
            consumed=used,
            remaining=grant.max_attempts - used,
            unsettled=unknown or 0,
        )


@dataclass(frozen=True)
class BudgetedTransport:
    delegate: DeadlineTransport
    ledger: AttemptLedger
    context: RunContext
    project_sha256: str

    def generate(self, request: ModelRequest, *, timeout_seconds: float = 30.0) -> ModelResponse:
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("provider dispatch requires a finite positive timeout")
        try:
            ticket = self.ledger.reserve(self.context, request, project_sha256=self.project_sha256)
        except (ValueError, OSError, sqlite3.Error):
            return failed_response(
                request, "budget_exhausted", "Shared allowance denied dispatch", dispatched=False
            )
        # No refund, even if delegate throws, process dies, or response parsing/settlement fails.
        response = self.delegate.generate(request, timeout_seconds=timeout_seconds)
        self.ledger.settle(ticket, response)
        return response


def main() -> int:
    """Prepare/inspect an allowance; deliberately offers no dispatch or reset command."""
    import argparse
    import json
    import sys

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("initialize", "status"))
    parser.add_argument("--ledger", required=True, type=Path)
    parser.add_argument("--allowance-sha256", required=True)
    parser.add_argument("--amendment-sha256")
    parser.add_argument("--development-extension-sha256")
    parser.add_argument("--paired-extension-sha256")
    parser.add_argument("--allowance", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "initialize":
            if args.allowance is None:
                raise ValueError("initialization needs a separately reviewed allowance file")
            allowance = ProviderAllowance.model_validate_json(args.allowance.read_bytes())
            if pin(allowance) != args.allowance_sha256:
                raise ValueError("allowance differs from external pin")
            initialize(args.ledger, allowance)
        elif args.allowance is not None:
            raise ValueError("status reads the existing authoritative ledger")
        print(
            json.dumps(
                AttemptLedger(
                    args.ledger,
                    args.allowance_sha256,
                    args.amendment_sha256,
                    args.development_extension_sha256,
                    args.paired_extension_sha256,
                ).summary(),
                sort_keys=True,
            )
        )
        return 0
    except (ValueError, OSError, sqlite3.Error):
        print(
            "Allowance operation refused; verify scope, pin and existing private ledger.",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
