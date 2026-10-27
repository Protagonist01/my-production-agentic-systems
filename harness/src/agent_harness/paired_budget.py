"""Specific owner-approved 74-slot development extension; no legacy-slot reuse."""

import json
import sqlite3
from typing import Annotated, Literal

from pydantic import AwareDatetime, Field

from agent_harness.cases import _unique_object
from agent_harness.contracts import (
    Contract,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    NonEmpty,
    RunContext,
)
from agent_harness.provider_budget import AttemptLedger, ProviderAllowance
from agent_harness.release_contracts import Sha256, pin


def canary_requests() -> tuple[ModelRequest, ...]:
    first = ModelRequest(
        provider="google-gemini-developer-api",
        endpoint="https://generativelanguage.googleapis.com",
        model="gemini-3.5-flash-lite",
        parameters={"temperature": 0.0, "max_output_tokens": 512, "thinking_level": "LOW"},
        messages=(
            ModelMessage(role="user", content="Invented canary: return JSON answer for 1+7."),
        ),
        output_schema={
            "type": "object",
            "properties": {"answer": {"type": "integer"}},
            "required": ["answer"],
            "additionalProperties": False,
        },
    )
    text = ("Invented compatibility text. " * 2000)[:50000]
    catalog = [
        {"evidence_id": f"s{i // 300}", "start": i, "text": text[i : i + 300], "schema_version": 1}
        for i in range(0, len(text), 300)
    ]
    second = ModelRequest(
        provider="google-gemini-developer-api",
        endpoint="https://generativelanguage.googleapis.com",
        model="gemini-3.5-flash-lite",
        parameters={"temperature": 0.0, "max_output_tokens": 512, "thinking_level": "LOW"},
        messages=(
            ModelMessage(
                role="system",
                content=(
                    "Invented interface canary. Return exactly JSON with decision accept "
                    'and evidence_ids ["s0"].'
                ),
            ),
            ModelMessage(
                role="user",
                content=json.dumps(
                    {"question": "Invented compatibility check only", "source_catalog": catalog},
                    separators=(",", ":"),
                ),
            ),
        ),
        output_schema={
            "type": "object",
            "additionalProperties": False,
            "required": ["decision", "evidence_ids"],
            "properties": {
                "decision": {"type": "string", "enum": ["accept", "reject", "abstain"]},
                "evidence_ids": {
                    "type": "array",
                    "maxItems": 3,
                    "items": {
                        "type": "string",
                        "enum": [f"s{i // 300}" for i in range(0, len(text), 300)],
                    },
                },
            },
        },
    )
    return first, second


class PairedSlot(Contract):
    case_id: NonEmpty
    request_sha256: Sha256
    trial_id: NonEmpty
    variant: Literal["canary", "baseline", "task_wording", "evidence_selection"]


class PairedExtension(Contract):
    version: Literal["gemini-paired-development-extension-v1"] = (
        "gemini-paired-development-extension-v1"
    )
    authorization_ref: NonEmpty
    original_allowance_sha256: Sha256
    previous_amendment_sha256: Sha256
    previous_development_sha256: Sha256
    maximum: Literal[418] = 418
    consumed_before: Literal[341] = 341
    model: Literal["gemini-3.5-flash-lite"] = "gemini-3.5-flash-lite"
    run_id: NonEmpty
    approved_at: AwareDatetime
    expires_at: AwareDatetime
    slots: Annotated[tuple[PairedSlot, ...], Field(min_length=74, max_length=74)]


def valid(extension: PairedExtension, ledger: AttemptLedger) -> None:
    if (
        extension.original_allowance_sha256 != ledger.allowance_sha256
        or extension.previous_amendment_sha256 != ledger.amendment_sha256
        or extension.previous_development_sha256 != ledger.development_extension_sha256
        or extension.expires_at <= extension.approved_at
        or len({(s.request_sha256, s.trial_id) for s in extension.slots}) != 74
    ):
        raise ValueError("paired extension pin/interval/unique schedule differs")
    canaries = [s for s in extension.slots if s.variant == "canary"]
    domain = [s for s in extension.slots if s.variant != "canary"]
    cases = {s.case_id for s in domain}
    if (
        len(canaries) != 2
        or len({s.request_sha256 for s in canaries}) != 2
        or {s.request_sha256 for s in canaries} != {pin(r) for r in canary_requests()}
        or len(cases) != 12
        or any(s.case_id in cases for s in canaries)
        or len({s.request_sha256 for s in domain}) != 36
    ):
        raise ValueError("paired schedule population differs")
    for case in cases:
        slots = [s for s in domain if s.case_id == case]
        if {(s.variant, s.trial_id) for s in slots} != {
            (v, t)
            for v in ("baseline", "task_wording", "evidence_selection")
            for t in ("trial-1", "trial-2")
        } or len(slots) != 6:
            raise ValueError("paired schedule missing/duplicated case variant/trial")
        for variant in ("baseline", "task_wording", "evidence_selection"):
            if len({s.request_sha256 for s in slots if s.variant == variant}) != 1:
                raise ValueError("paired trials must repeat the identical request")


def load(db: sqlite3.Connection, ledger: AttemptLedger) -> PairedExtension | None:
    exists = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='paired_extensions'"
    ).fetchone()
    if not exists:
        if ledger.paired_extension_sha256 is not None:
            raise ValueError("pinned paired extension missing")
        return None
    rows = db.execute("SELECT pin,document FROM paired_extensions").fetchall()
    if len(rows) != 1 or rows[0][0] != ledger.paired_extension_sha256:
        raise ValueError("paired extension requires current external pin")
    extension = PairedExtension.model_validate_json(rows[0][1])
    if pin(extension) != ledger.paired_extension_sha256:
        raise ValueError("paired extension document differs")
    valid(extension, ledger)
    return extension


def paired_authorization(
    db: sqlite3.Connection, ledger: AttemptLedger, previous: ProviderAllowance
) -> ProviderAllowance:
    extension = load(db, ledger)
    if extension is None:
        return previous
    if (
        previous.max_attempts != 344
        or extension.model not in previous.models
        or extension.approved_at < previous.approved_at
        or extension.expires_at < previous.expires_at
        or db.execute("SELECT count(*) FROM attempts").fetchone()[0] < 341
    ):
        raise ValueError("paired extension history/interval differs")
    return previous.model_copy(
        update={
            "max_attempts": 418,
            "approved_at": extension.approved_at,
            "expires_at": extension.expires_at,
        }
    )


def append_extension(ledger: AttemptLedger, extension: PairedExtension) -> str:
    extension = PairedExtension.model_validate_json(extension.canonical_json())
    valid(extension, ledger)
    with ledger.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        previous = ledger.authorization(db)
        used, unsettled = db.execute(
            "SELECT count(*),sum(response_pin IS NULL) FROM attempts"
        ).fetchone()
        if (
            previous.max_attempts != 344
            or used != 341
            or unsettled
            or extension.model not in previous.models
            or extension.approved_at < previous.approved_at
            or extension.expires_at < previous.expires_at
        ):
            raise ValueError("paired extension requires exact settled341 history")
        db.execute("CREATE TABLE paired_extensions(pin TEXT PRIMARY KEY,document TEXT NOT NULL)")
        db.execute(
            "INSERT INTO paired_extensions VALUES(?,?)",
            (pin(extension), extension.canonical_json()),
        )
        db.execute(
            "CREATE TABLE paired_slots(request_pin TEXT NOT NULL,trial_id TEXT NOT NULL,"
            "case_id TEXT NOT NULL,context_pin TEXT NOT NULL,ticket TEXT NOT NULL UNIQUE,"
            "PRIMARY KEY(request_pin,trial_id))"
        )
        db.execute(
            "CREATE TABLE paired_canary_passes(request_pin TEXT PRIMARY KEY,"
            "response_pin TEXT NOT NULL)"
        )
        for table in ("paired_extensions", "paired_slots", "paired_canary_passes"):
            for operation in ("UPDATE", "DELETE"):
                db.execute(
                    f"CREATE TRIGGER immutable_{table}_{operation} BEFORE {operation} ON {table} "
                    "BEGIN SELECT RAISE(ABORT,'immutable paired scope/slot'); END"
                )
        # Even an old executable that ignores this extension cannot use the three old slots.
        db.execute("""
        CREATE TRIGGER require_paired_scope BEFORE INSERT ON attempts
        WHEN NEW.serial>341 AND NOT EXISTS(
          SELECT 1 FROM paired_slots WHERE ticket=NEW.ticket AND request_pin=NEW.request_pin
            AND context_pin=NEW.context_pin)
        BEGIN SELECT RAISE(ABORT,'current paired scope required'); END;
        """)
    return pin(extension)


def reserve_slot(
    db: sqlite3.Connection,
    ledger: AttemptLedger,
    context: RunContext,
    request: ModelRequest,
    ticket: str,
) -> None:
    extension = load(db, ledger)
    if (
        extension is None
        or context.agent_id != "revenue"
        or context.run_id != extension.run_id
        or request.model != extension.model
    ):
        raise ValueError("outside paired development scope")
    slots = [
        s
        for s in extension.slots
        if (s.case_id, s.request_sha256, s.trial_id)
        == (context.case_id, pin(request), context.trial_id)
    ]
    if len(slots) != 1:
        raise ValueError("outside frozen paired schedule")
    if (
        slots[0].variant != "canary"
        and db.execute("SELECT count(*) FROM paired_canary_passes").fetchone()[0] != 2
    ):
        raise ValueError("both invented canaries must pass before domain dispatch")
    db.execute(
        "INSERT INTO paired_slots VALUES(?,?,?,?,?)",
        (pin(request), context.trial_id, context.case_id, pin(context), ticket),
    )


def record_canary_pass(
    ledger: AttemptLedger, request: ModelRequest, response: ModelResponse
) -> None:
    request = ModelRequest.model_validate_json(request.canonical_json())
    response = ModelResponse.model_validate_json(response.canonical_json())
    candidates = canary_requests()
    if request not in candidates or response.failure or response.output is None:
        raise ValueError("canary did not complete")
    if (
        response.provider != request.provider
        or response.model != request.model
        or response.output.tool_calls
    ):
        raise ValueError("canary route/output differs")
    content = json.loads(response.output.content or "", object_pairs_hook=_unique_object)
    expected = (
        {"answer": 8}
        if request == candidates[0]
        else {"decision": "accept", "evidence_ids": ["s0"]}
    )
    if content != expected or (request == candidates[0] and type(content["answer"]) is not int):
        raise ValueError("canary answer incorrect")
    with ledger.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        ledger.authorization(db)
        if not db.execute(
            "SELECT 1 FROM attempts WHERE request_pin=? AND response_pin=?",
            (pin(request), pin(response)),
        ).fetchone():
            raise ValueError("canary must have matching settled reservation")
        db.execute("INSERT INTO paired_canary_passes VALUES(?,?)", (pin(request), pin(response)))
