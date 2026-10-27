"""Specific fifty-slot model-only study; append, never reset historical allowances."""

import json
import sqlite3
from typing import Annotated, Literal

from pydantic import AwareDatetime, Field

from agent_harness.cases import _unique_object
from agent_harness.contracts import Contract, ModelRequest, ModelResponse, NonEmpty, RunContext
from agent_harness.paired_budget import canary_requests
from agent_harness.provider_budget import AttemptLedger, ProviderAllowance
from agent_harness.release_contracts import Sha256, pin

Model = Literal["gemini-3.5-flash-lite", "gemini-3.8-flash"]
MODELS: tuple[Model, ...] = ("gemini-3.5-flash-lite", "gemini-3.8-flash")


def model_canaries() -> tuple[ModelRequest, ...]:
    return tuple(canary_requests()[1].model_copy(update={"model": m}) for m in MODELS)


class ModelSlot(Contract):
    case_id: NonEmpty
    request_sha256: Sha256
    model: Model
    trial_id: Literal["model-canary", "model-only-trial-1", "model-only-trial-2"]
    purpose: Literal["canary", "quality"]


class ModelExtension(Contract):
    version: Literal["gemini-model-only-extension-v1"] = "gemini-model-only-extension-v1"
    authorization_ref: NonEmpty
    historical_pins: Annotated[tuple[Sha256, ...], Field(min_length=5, max_length=5)]
    maximum: Literal[468] = 468
    consumed_before: Literal[415] = 415
    approved_at: AwareDatetime
    expires_at: AwareDatetime
    run_id: NonEmpty
    slots: Annotated[tuple[ModelSlot, ...], Field(min_length=50, max_length=50)]


def valid(extension: ModelExtension, ledger: AttemptLedger) -> None:
    if (
        extension.historical_pins
        != (
            ledger.allowance_sha256,
            ledger.amendment_sha256,
            ledger.development_extension_sha256,
            ledger.paired_extension_sha256,
            ledger.availability_override_sha256,
        )
        or extension.expires_at <= extension.approved_at
    ):
        raise ValueError("model extension historical pins/interval differ")
    canaries = [s for s in extension.slots if s.purpose == "canary"]
    domain = [s for s in extension.slots if s.purpose == "quality"]
    cases = {s.case_id for s in domain}
    if (
        len({(s.request_sha256, s.trial_id) for s in extension.slots}) != 50
        or len(canaries) != 2
        or len(cases) != 12
        or {(s.model, s.request_sha256, s.trial_id) for s in canaries}
        != {(r.model, pin(r), "model-canary") for r in model_canaries()}
        or any(s.case_id in cases for s in canaries)
        or len({s.request_sha256 for s in domain}) != 24
    ):
        raise ValueError("model schedule population differs")
    for case in cases:
        slots = [s for s in domain if s.case_id == case]
        if len(slots) != 4 or {(s.model, s.trial_id) for s in slots} != {
            (m, t) for m in MODELS for t in ("model-only-trial-1", "model-only-trial-2")
        }:
            raise ValueError("model schedule case/model/trial differs")
        if any(len({s.request_sha256 for s in slots if s.model == m}) != 1 for m in MODELS):
            raise ValueError("model trial request changed")


def load(db: sqlite3.Connection, ledger: AttemptLedger) -> ModelExtension | None:
    exists = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='model_extensions'"
    ).fetchone()
    if not exists:
        if ledger.model_extension_sha256 is not None:
            raise ValueError("pinned model extension missing")
        return None
    rows = db.execute("SELECT pin,document FROM model_extensions").fetchall()
    if len(rows) != 1 or rows[0][0] != ledger.model_extension_sha256:
        raise ValueError("model extension requires current external pin")
    extension = ModelExtension.model_validate_json(rows[0][1])
    if pin(extension) != ledger.model_extension_sha256:
        raise ValueError("model extension document differs")
    valid(extension, ledger)
    return extension


def model_authorization(
    db: sqlite3.Connection, ledger: AttemptLedger, previous: ProviderAllowance
) -> ProviderAllowance:
    extension = load(db, ledger)
    if extension is None:
        return previous
    if (
        previous.max_attempts != 418
        or extension.approved_at < previous.approved_at
        or extension.expires_at < previous.expires_at
        or not set(MODELS) <= set(previous.models)
        or db.execute("SELECT count(*) FROM attempts").fetchone()[0] < 415
    ):
        raise ValueError("model extension history differs")
    return previous.model_copy(
        update={
            "max_attempts": 468,
            "approved_at": extension.approved_at,
            "expires_at": extension.expires_at,
        }
    )


def append_model_extension(ledger: AttemptLedger, extension: ModelExtension) -> str:
    extension = ModelExtension.model_validate_json(extension.canonical_json())
    valid(extension, ledger)
    with ledger.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        previous = ledger.authorization(db)
        used, unsettled = db.execute(
            "SELECT count(*),sum(response_pin IS NULL) FROM attempts"
        ).fetchone()
        if (
            previous.max_attempts != 418
            or used != 415
            or unsettled
            or extension.approved_at < previous.approved_at
            or extension.expires_at < previous.expires_at
            or not set(MODELS) <= set(previous.models)
        ):
            raise ValueError("model extension requires exact settled415 history")
        db.execute("CREATE TABLE model_extensions(pin TEXT PRIMARY KEY,document TEXT NOT NULL)")
        db.execute(
            "INSERT INTO model_extensions VALUES(?,?)", (pin(extension), extension.canonical_json())
        )
        db.execute(
            "CREATE TABLE model_slots(request_pin TEXT NOT NULL,trial_id TEXT NOT NULL,"
            "context_pin TEXT NOT NULL,ticket TEXT NOT NULL UNIQUE,"
            "PRIMARY KEY(request_pin,trial_id))"
        )
        db.execute(
            "CREATE TABLE model_canary_passes(request_pin TEXT PRIMARY KEY,"
            "response_pin TEXT NOT NULL)"
        )
        for table in ("model_extensions", "model_slots", "model_canary_passes"):
            for operation in ("UPDATE", "DELETE"):
                db.execute(
                    f"CREATE TRIGGER immutable_{table}_{operation} BEFORE {operation} ON {table} "
                    "BEGIN SELECT RAISE(ABORT,'immutable model scope'); END"
                )
        db.execute("""
        CREATE TRIGGER require_model_scope BEFORE INSERT ON attempts
        WHEN NEW.serial>415 AND NOT EXISTS(SELECT 1 FROM model_slots
          WHERE ticket=NEW.ticket AND request_pin=NEW.request_pin AND context_pin=NEW.context_pin)
        BEGIN SELECT RAISE(ABORT,'current model scope required'); END;
        """)
    return pin(extension)


def reserve_model_slot(
    db: sqlite3.Connection,
    ledger: AttemptLedger,
    context: RunContext,
    request: ModelRequest,
    ticket: str,
) -> None:
    extension = load(db, ledger)
    if extension is None or context.agent_id != "revenue" or context.run_id != extension.run_id:
        raise ValueError("outside model-only run")
    slots = [
        s
        for s in extension.slots
        if (s.case_id, s.model, s.request_sha256, s.trial_id)
        == (context.case_id, request.model, pin(request), context.trial_id)
    ]
    if len(slots) != 1:
        raise ValueError("outside frozen model-only slots")
    if (
        slots[0].purpose == "quality"
        and db.execute("SELECT count(*) FROM model_canary_passes").fetchone()[0] != 2
    ):
        raise ValueError("both model canaries must pass")
    db.execute(
        "INSERT INTO model_slots VALUES(?,?,?,?)",
        (pin(request), context.trial_id, pin(context), ticket),
    )
    # Append a namespaced trace row to satisfy the existing paired SQL guard, unchanged.
    db.execute(
        "INSERT INTO paired_slots VALUES(?,?,?,?,?)",
        (pin(request), context.trial_id, context.case_id, pin(context), ticket),
    )


def record_model_canary(
    ledger: AttemptLedger, request: ModelRequest, response: ModelResponse
) -> None:
    response = ModelResponse.model_validate_json(response.canonical_json())
    if (
        request not in model_canaries()
        or response.failure
        or response.output is None
        or response.output.tool_calls
        or (response.provider, response.model) != (request.provider, request.model)
        or json.loads(response.output.content or "", object_pairs_hook=_unique_object)
        != {"decision": "accept", "evidence_ids": ["s0"]}
    ):
        raise ValueError("model representative canary failed")
    with ledger.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        ledger.authorization(db)
        if not db.execute(
            "SELECT 1 FROM attempts JOIN model_slots USING(ticket) "
            "WHERE attempts.request_pin=? AND response_pin=?",
            (pin(request), pin(response)),
        ).fetchone():
            raise ValueError("model canary requires matching settled receipt")
        db.execute("INSERT INTO model_canary_passes VALUES(?,?)", (pin(request), pin(response)))
