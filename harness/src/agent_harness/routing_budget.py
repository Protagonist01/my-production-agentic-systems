"""Prospective Olist development slots; never apply an amendment or dispatch implicitly."""

import json
import sqlite3
from time import monotonic
from typing import Annotated, Literal, Self

from pydantic import AwareDatetime, Field, model_validator

from agent_harness.admission import GEMINI_TOKEN_CEILING
from agent_harness.cases import _unique_object
from agent_harness.contracts import Contract, ModelRequest, ModelResponse, NonEmpty, RunContext
from agent_harness.provider_budget import AttemptLedger, ProviderAllowance
from agent_harness.release_contracts import AttemptReceipt, CandidateSpec, Sha256, pin, sha256

Variant = Literal["candidate", "legacy"]


def behavior_pin(candidate: CandidateSpec) -> str:
    """Avoid the extension -> candidate -> provider-control -> extension hash cycle."""
    return pin(candidate.model_copy(update={"provider_control_sha256": None}))


class RoutingSlot(Contract):
    ordinal: Annotated[int, Field(ge=1, le=146)]
    phase: Literal["canary", "domain"]
    variant: Variant
    tenant_id: NonEmpty
    case_id: NonEmpty
    case_sha256: Sha256 | None = None
    run_id: NonEmpty
    business_event_id: NonEmpty
    data_snapshot: NonEmpty
    trial_id: NonEmpty
    request_sha256: Sha256


class RoutingExtension(Contract):
    version: Literal["gemini-olist-routing-extension-v1"] = "gemini-olist-routing-extension-v1"
    authorization_ref: NonEmpty
    historical_pins: Annotated[tuple[Sha256, ...], Field(min_length=6, max_length=6)]
    protocol_sha256: Sha256
    population_sha256: Sha256
    candidate_behavior_sha256: dict[Variant, Sha256]
    candidate_versions: dict[Variant, NonEmpty]
    code_revision: NonEmpty
    environment_lock: Sha256
    policy_version: NonEmpty
    execution_origin: Literal["mock", "provider"]
    maximum: Literal[614] = 614
    consumed_before: Literal[417] = 417
    preserve_unused: Literal[51] = 51
    approved_at: AwareDatetime
    expires_at: AwareDatetime
    slots: Annotated[tuple[RoutingSlot, ...], Field(min_length=146, max_length=146)]

    @model_validator(mode="after")
    def complete(self) -> Self:
        if (
            self.expires_at <= self.approved_at
            or set(self.candidate_behavior_sha256) != {"candidate", "legacy"}
            or set(self.candidate_versions) != {"candidate", "legacy"}
            or len(set(self.candidate_versions.values())) != 2
            or len(set(self.candidate_behavior_sha256.values())) != 2
            or [s.ordinal for s in self.slots] != list(range(1, 147))
            or [s.phase for s in self.slots] != ["canary"] * 2 + ["domain"] * 144
            or {s.variant for s in self.slots[:2]} != {"candidate", "legacy"}
            or any(s.case_sha256 is not None for s in self.slots[:2])
            or len({s.run_id for s in self.slots}) != 146
            or len({(s.case_id, s.variant, s.trial_id) for s in self.slots}) != 146
        ):
            raise ValueError("routing scope requires two canaries and 144 unique domain slots")
        domain = self.slots[2:]
        cases = {s.case_id for s in domain}
        if len(cases) != 24 or any(s.case_id in cases for s in self.slots[:2]):
            raise ValueError("routing scope needs 24 distinct domain cases")
        if {s.request_sha256 for s in self.slots[:2]} & {s.request_sha256 for s in domain}:
            raise ValueError("canary request cannot be a domain request")
        for case in cases:
            rows = [s for s in domain if s.case_id == case]
            if (
                {(s.variant, s.trial_id) for s in rows}
                != {
                    (v, t)
                    for v in ("candidate", "legacy")
                    for t in ("trial-1", "trial-2", "trial-3")
                }
                or len({s.case_sha256 for s in rows}) != 1
                or rows[0].case_sha256 is None
                or len({s.tenant_id for s in rows}) != 1
                or any(
                    len({s.request_sha256 for s in rows if s.variant == v}) != 1
                    for v in ("candidate", "legacy")
                )
            ):
                raise ValueError("routing case/reference/variant/trial membership differs")
        for offset in range(2, 146, 3):
            batch = self.slots[offset : offset + 3]
            if len({(s.case_id, s.variant) for s in batch}) != 1 or [s.trial_id for s in batch] != [
                "trial-1",
                "trial-2",
                "trial-3",
            ]:
                raise ValueError("routing recording requires consecutive three-trial batches")
        return self


def historical_pins(ledger: AttemptLedger) -> tuple[str | None, ...]:
    return (
        ledger.allowance_sha256,
        ledger.amendment_sha256,
        ledger.development_extension_sha256,
        ledger.paired_extension_sha256,
        ledger.availability_override_sha256,
        ledger.model_extension_sha256,
    )


def load(db: sqlite3.Connection, ledger: AttemptLedger) -> RoutingExtension | None:
    exists = db.execute(
        "SELECT 1 FROM sqlite_master WHERE name='routing_extensions' AND type='table'"
    ).fetchone()
    if not exists:
        if ledger.routing_extension_sha256 is not None:
            raise ValueError("pinned routing extension is missing")
        return None
    rows = db.execute("SELECT pin,document FROM routing_extensions").fetchall()
    if len(rows) != 1 or rows[0][0] != ledger.routing_extension_sha256:
        raise ValueError("routing extension requires the current external pin")
    value = RoutingExtension.model_validate_json(rows[0][1])
    if pin(value) != ledger.routing_extension_sha256 or value.historical_pins != historical_pins(
        ledger
    ):
        raise ValueError("routing extension history/document differs")
    return value


def routing_authorization(
    db: sqlite3.Connection, ledger: AttemptLedger, prior: ProviderAllowance
) -> ProviderAllowance:
    extension = load(db, ledger)
    if extension is None:
        return prior
    if (
        prior.max_attempts != 468
        or extension.approved_at < prior.approved_at
        or extension.expires_at < prior.expires_at
        or "gemini-3.5-flash-lite" not in prior.models
        or db.execute("SELECT count(*) FROM attempts").fetchone()[0] < 417
    ):
        raise ValueError("routing extension requires the prior 468 scope and settled history")
    return prior.model_copy(
        update={
            "max_attempts": 614,
            "approved_at": extension.approved_at,
            "expires_at": extension.expires_at,
        }
    )


def append_routing_extension(ledger: AttemptLedger, extension: RoutingExtension) -> str:
    """Trusted caller authenticates an actual owner approval; no CLI or implicit amendment."""
    extension = RoutingExtension.model_validate_json(extension.canonical_json())
    if extension.historical_pins != historical_pins(ledger) or ledger.routing_extension_sha256:
        raise ValueError("routing extension historical pins differ")
    with ledger.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        prior = ledger.authorization(db)
        used, unsettled = db.execute(
            "SELECT count(*),sum(response_pin IS NULL) FROM attempts"
        ).fetchone()
        if (
            prior.max_attempts != 468
            or used != 417
            or unsettled
            or extension.approved_at < prior.approved_at
            or extension.expires_at < prior.expires_at
            or "gemini-3.5-flash-lite" not in prior.models
        ):
            raise ValueError("routing extension requires exact settled417 history")
        db.execute("CREATE TABLE routing_extensions(pin TEXT PRIMARY KEY,document TEXT NOT NULL)")
        db.execute(
            "INSERT INTO routing_extensions VALUES(?,?)",
            (pin(extension), extension.canonical_json()),
        )
        db.execute(
            "CREATE TABLE routing_slots(ordinal INTEGER PRIMARY KEY,"
            "allocation_no INTEGER UNIQUE NOT NULL,request_pin TEXT NOT NULL,"
            "context_pin TEXT NOT NULL,ticket TEXT UNIQUE NOT NULL,"
            "started_monotonic REAL NOT NULL)"
        )
        db.execute(
            "CREATE TABLE routing_settlements(ordinal INTEGER PRIMARY KEY,"
            "response_pin TEXT NOT NULL,tokens INTEGER,transient INTEGER NOT NULL,"
            "canary_pass INTEGER NOT NULL,document TEXT NOT NULL)"
        )
        db.execute(
            "CREATE TABLE routing_stops(id INTEGER PRIMARY KEY CHECK(id=1),reason TEXT NOT NULL)"
        )
        db.execute(
            "CREATE TABLE routing_canary_receipts(ordinal INTEGER PRIMARY KEY,"
            "receipt_pin TEXT NOT NULL,document TEXT NOT NULL)"
        )
        for table in (
            "routing_extensions",
            "routing_slots",
            "routing_settlements",
            "routing_stops",
            "routing_canary_receipts",
        ):
            for operation in ("UPDATE", "DELETE"):
                db.execute(
                    f"CREATE TRIGGER immutable_{table}_{operation} BEFORE {operation} ON {table} "
                    "BEGIN SELECT RAISE(ABORT,'immutable routing scope'); END"
                )
        db.execute("""CREATE TRIGGER require_routing_scope BEFORE INSERT ON attempts
          WHEN NEW.serial>417 AND NOT EXISTS(SELECT 1 FROM routing_slots
            WHERE ticket=NEW.ticket AND request_pin=NEW.request_pin AND context_pin=NEW.context_pin)
          BEGIN SELECT RAISE(ABORT,'current routing scope required'); END;""")
    return pin(extension)


def reserve_routing_slot(
    db: sqlite3.Connection,
    ledger: AttemptLedger,
    context: RunContext,
    request: ModelRequest,
    ticket: str,
) -> None:
    extension = load(db, ledger)
    count = db.execute("SELECT count(*) FROM routing_slots").fetchone()[0]
    if extension is None or count >= 146 or db.execute("SELECT 1 FROM routing_stops").fetchone():
        raise ValueError("routing scope stopped or exhausted")
    if db.execute("SELECT 1 FROM attempts WHERE response_pin IS NULL").fetchone():
        raise ValueError("unsettled reservation blocks subsequent routing dispatch")
    tick = monotonic()
    first = db.execute(
        "SELECT started_monotonic FROM routing_slots ORDER BY ordinal LIMIT 1"
    ).fetchone()
    if first and not 0 <= tick - first[0] < 26100:
        stop_db(db, "experiment_wall_limit")
        # Caller rolls back on refusal; wall-clock refusal remains effective on later attempts.
        raise ValueError("routing experiment wall limit")
    slot = extension.slots[count]
    if (
        context.agent_id != "olist"
        or (
            context.tenant_id,
            context.case_id,
            context.run_id,
            context.trial_id,
            context.business_event_id,
            pin(request),
        )
        != (
            slot.tenant_id,
            slot.case_id,
            slot.run_id,
            slot.trial_id,
            slot.business_event_id,
            slot.request_sha256,
        )
        or (
            context.versions.code_revision,
            context.versions.environment_lock,
            context.versions.candidate,
            context.versions.policy,
            context.versions.data_snapshot,
        )
        != (
            extension.code_revision,
            extension.environment_lock,
            extension.candidate_versions[slot.variant],
            extension.policy_version,
            slot.data_snapshot,
        )
        or request.model != "gemini-3.5-flash-lite"
        or request.tools
        or request.tool_choice
        or request.parameters
        != {"temperature": 0.0, "max_output_tokens": 512, "thinking_level": "LOW"}
        or context.budget.max_model_calls != 1
        or context.budget.max_tokens != GEMINI_TOKEN_CEILING
        or context.budget.max_cost != 0
        or context.budget.cost_currency != "USD"
        or (
            slot.phase == "domain"
            and db.execute("SELECT count(*) FROM routing_canary_receipts").fetchone()[0] != 2
        )
        or (
            count == 1
            and not db.execute("SELECT 1 FROM routing_canary_receipts WHERE ordinal=1").fetchone()
        )
    ):
        raise ValueError("outside next frozen routing slot or canary gate")
    db.execute(
        "INSERT INTO routing_slots VALUES(?,?,?,?,?,?)",
        (slot.ordinal, 468 + slot.ordinal, pin(request), pin(context), ticket, tick),
    )
    # Add trace rows satisfying historical SQL guards without reusing their unspent slots.
    trace = "routing-" + str(slot.ordinal) + "-" + context.trial_id
    db.execute(
        "INSERT INTO model_slots VALUES(?,?,?,?)", (pin(request), trace, pin(context), ticket)
    )
    db.execute(
        "INSERT INTO paired_slots VALUES(?,?,?,?,?)",
        (pin(request), trace, context.case_id, pin(context), ticket),
    )


def stop_db(db: sqlite3.Connection, reason: str) -> None:
    db.execute("INSERT OR IGNORE INTO routing_stops VALUES(1,?)", (reason,))


def acknowledge_canary(ledger: AttemptLedger, receipt: AttemptReceipt) -> None:
    """Only an exact settled successful exchange with verified scoped accounting unlocks a gate."""
    from agent_harness.cost_accounting import CostAccounting, verify_accounting

    receipt = AttemptReceipt.model_validate_json(receipt.canonical_json())
    exchange = receipt.exchange
    if (
        exchange.occurrence != 1
        or receipt.execution_id != exchange.context.run_id
        or exchange.response.accounting is None
    ):
        raise ValueError("canary requires its complete accounted receipt")
    account = CostAccounting.model_validate_json(json.dumps(exchange.response.accounting))
    raw = exchange.response.model_copy(update={"usage": account.raw_usage, "accounting": None})
    with ledger.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        grant = ledger.authorization(db)
        extension = load(db, ledger)
        scope_sha = sha256(
            json.dumps(
                {"history": historical_pins(ledger), "routing": ledger.routing_extension_sha256},
                sort_keys=True,
            ).encode()
        )
        if (
            extension is None
            or account.capture_scope_sha256 != scope_sha
            or account.tariff.project_sha256 != grant.project_sha256
            or account.allowance_sha256 != ledger.allowance_sha256
        ):
            raise ValueError("canary receipt scope differs")
        verify_accounting(exchange.request, exchange.response)
        row = db.execute(
            "SELECT ordinal,response_pin,document FROM routing_slots "
            "JOIN routing_settlements USING(ordinal) WHERE request_pin=? AND context_pin=? "
            "AND canary_pass=1 AND ordinal<=2",
            (pin(exchange.request), pin(exchange.context)),
        ).fetchone()
        if row is None or row[1] != pin(raw) or row[2] != raw.canonical_json():
            raise ValueError("canary requires a matching settled successful receipt")
        db.execute(
            "INSERT INTO routing_canary_receipts VALUES(?,?,?)",
            (row[0], pin(receipt), receipt.canonical_json()),
        )


def stop(ledger: AttemptLedger, reason: str) -> None:
    if reason not in (
        "unsafe_or_unknown_state",
        "scorer_observation_failed",
        "owned_cleanup_failed",
        "fixture_setup_failed",
        "canary_capture_failed",
    ):
        raise ValueError("unknown routing safety stop")
    with ledger.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        ledger.authorization(db)
        if load(db, ledger) is None:
            raise ValueError("routing scope missing")
        stop_db(db, reason)


def settle_routing(
    db: sqlite3.Connection, ledger: AttemptLedger, ticket: str, response: ModelResponse
) -> None:
    extension = load(db, ledger)
    row = db.execute("SELECT ordinal FROM routing_slots WHERE ticket=?", (ticket,)).fetchone()
    if extension is None or row is None:
        raise ValueError("routing settlement requires its reserved slot")
    slot = extension.slots[row[0] - 1]
    usage = response.usage
    tokens = (
        None
        if usage.input_tokens is None or usage.output_tokens is None
        else usage.input_tokens + usage.output_tokens
    )
    error = response.failure.code if response.failure else None
    good = False
    if (
        slot.phase == "canary"
        and error is None
        and response.output is not None
        and not response.output.tool_calls
    ):
        try:
            data = json.loads(response.output.content or "", object_pairs_hook=_unique_object)
            expected: dict[str, object] = {"intent": "refund"}
            if slot.variant == "candidate":
                expected["routing_version"] = "olist-intent-routing-v2"
            if isinstance(data, dict):
                if "requested_minor" in data:
                    expected["requested_minor"] = None
                if "schema_version" in data:
                    expected["schema_version"] = 1
                good = data == expected and type(data.get("schema_version", 1)) is int
        except (ValueError, TypeError):
            good = False
    transient = error in ("timeout", "unavailable")
    if (
        (response.provider, response.model)
        != ("google-gemini-developer-api", "gemini-3.5-flash-lite")
        or usage.model_calls != 1
        or tokens is None
        or tokens > GEMINI_TOKEN_CEILING
    ):
        stop_db(db, "unknown_or_over_limit_usage")
        good = False
    elif error in ("permission_denied", "rate_limited", "budget_exhausted"):
        stop_db(db, "provider_denied")
    if slot.phase == "canary" and not good:
        stop_db(db, "canary_failed")
    previous = db.execute(
        "SELECT transient FROM routing_settlements ORDER BY ordinal DESC LIMIT 2"
    ).fetchall()
    if transient and len(previous) == 2 and all(r[0] for r in previous):
        stop_db(db, "consecutive_provider_failures")
    db.execute(
        "INSERT INTO routing_settlements VALUES(?,?,?,?,?,?)",
        (slot.ordinal, pin(response), tokens, int(transient), int(good), response.canonical_json()),
    )
    total = db.execute("SELECT sum(tokens) FROM routing_settlements").fetchone()[0]
    if total is not None and total > 146 * GEMINI_TOKEN_CEILING:
        stop_db(db, "experiment_token_limit")
