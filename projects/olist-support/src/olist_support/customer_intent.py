"""Customer transaction authority, independent of a planner's interpretation."""

import json
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from importlib.resources import files
from typing import TYPE_CHECKING, Annotated, Any, Literal, Self

from agent_harness.contracts import Contract
from psycopg import Connection, sql
from psycopg.types.json import Jsonb
from pydantic import AwareDatetime, Field, model_validator

from olist_support.business import BusinessStore, CommitRecorder, ConnectionFactory, FaultHook, sha
from olist_support.business_contracts import (
    BusinessReview,
    CallerGrant,
    RefundCommand,
    RefundReceipt,
)
from olist_support.console_contracts import CaseRecord, Principal
from olist_support.policy import POLICY_VERSION
from olist_support.workflow import WorkflowResult

CONFIRMATION_SECONDS = 300

if TYPE_CHECKING:
    from olist_support.console_cases import CaseStore


def guard_ready(connection: Connection[Any]) -> bool:
    source = files("olist_support").joinpath("customer_intent.sql").read_text(encoding="utf-8")
    functions = {
        "lock_customer_account": "account_guard",
        "stamp_customer_authority": "state_guard",
        "require_customer_authority": "refund_guard",
        "require_customer_order_effect": "order_guard",
    }
    expected = {name: source.split("$" + marker + "$")[1] for name, marker in functions.items()}
    function_rows = connection.execute(
        "SELECT p.proname,p.prosrc,p.proconfig,p.prosecdef FROM pg_proc p "
        "JOIN pg_namespace n ON n.oid=p.pronamespace "
        "WHERE n.nspname='olist_intent' AND p.pronargs=0 AND p.prorettype='trigger'::regtype"
    ).fetchall()
    actual = {name: body for name, body, config, definer in function_rows}
    if any(
        config != ["search_path=pg_catalog"] or definer for _, _, config, definer in function_rows
    ):
        return False
    if actual != expected:
        return False
    triggers = {
        "olist_customer_account_change": (
            "olist_app",
            "accounts",
            "lock_customer_account",
            False,
            "BEFORE",
            {"UPDATE", "DELETE"},
        ),
        "olist_customer_authority_state": (
            "olist_intent",
            "challenges",
            "stamp_customer_authority",
            False,
            "BEFORE",
            {"INSERT", "UPDATE"},
        ),
        "olist_customer_authority_commit": (
            "olist",
            "refunds",
            "require_customer_authority",
            True,
            "AFTER",
            {"INSERT"},
        ),
        "olist_customer_order_effect": (
            "olist",
            "orders",
            "require_customer_order_effect",
            True,
            "AFTER",
            {"UPDATE"},
        ),
    }
    rows = connection.execute(
        "SELECT t.tgname,n.nspname,c.relname,p.proname,t.tgenabled,t.tgdeferrable,"
        "t.tginitdeferred,pg_get_triggerdef(t.oid),t.tgqual IS NULL,pn.nspname "
        "FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid "
        "JOIN pg_namespace n ON n.oid=c.relnamespace JOIN pg_proc p ON p.oid=t.tgfoid "
        "JOIN pg_namespace pn ON pn.oid=p.pronamespace WHERE t.tgname=ANY(%s)",
        (list(triggers),),
    ).fetchall()
    if len(rows) != len(triggers):
        return False
    for (
        name,
        schema,
        table,
        function,
        enabled,
        deferred,
        initially,
        definition,
        unconditional,
        function_schema,
    ) in rows:
        wanted_schema, wanted_table, wanted_function, wanted_deferred, timing, events = triggers[
            name
        ]
        if (
            (schema, table, function) != (wanted_schema, wanted_table, wanted_function)
            or enabled != "O"
            or deferred != wanted_deferred
            or initially != wanted_deferred
            or not unconditional
            or function_schema != "olist_intent"
            or "FOR EACH ROW" not in definition
            or timing not in definition
            or set(definition.split(" ON ")[0].split()) & {"INSERT", "UPDATE", "DELETE", "TRUNCATE"}
            != events
        ):
            return False
    return True


class Confirmation(Contract):
    challenge: Annotated[str, Field(min_length=32, max_length=128)]
    action: Literal["refund"]
    amount_minor: Annotated[int, Field(gt=0, le=10000)]
    unit: Literal["SIM"]


class Authority(Contract):
    customer: Principal
    case_id: str
    case_version: int
    request_sha256: str
    command: RefundCommand
    action_digest: str
    record_pin: str
    policy_version: Literal["olist-canceled-full-refund-sim-v1"] = POLICY_VERSION
    issued_at: AwareDatetime
    expires_at: AwareDatetime
    confirmed_at: AwareDatetime | None = None
    consumed_receipt: RefundReceipt | None = None
    consumed_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def bound(self) -> Self:
        self.customer.require("customer")
        self.customer.grant(self.command.order_id)
        if (
            self.command.tenant_id != self.customer.tenant_id
            or not 0 < (self.expires_at - self.issued_at).total_seconds() <= CONFIRMATION_SECONDS
            or self.confirmed_at is not None
            and not self.issued_at <= self.confirmed_at < self.expires_at
        ):
            raise ValueError("invalid customer authority scope or interval")
        return self


def setup_customer_intent(admin: Connection[Any], runtime_role: str) -> None:
    ddl = files("olist_support").joinpath("customer_intent.sql").read_text(encoding="utf-8")
    with admin.transaction():
        admin.execute("SELECT pg_advisory_xact_lock(73412043)")
        admin.execute("CREATE SCHEMA IF NOT EXISTS olist_intent")
        admin.execute("REVOKE ALL ON SCHEMA olist_intent FROM PUBLIC")
        admin.execute(
            "CREATE TABLE IF NOT EXISTS olist_intent.schema_pin("
            "version integer PRIMARY KEY,sha256 text NOT NULL)"
        )
        current = admin.execute("SELECT version,sha256 FROM olist_intent.schema_pin").fetchall()
        if current and current != [(1, sha(ddl))]:
            raise ValueError("customer intent schema differs from immutable version1")
        if not current:
            admin.execute(ddl)
            admin.execute("INSERT INTO olist_intent.schema_pin VALUES(1,%s)", (sha(ddl),))
        admin.execute(
            sql.SQL("GRANT USAGE ON SCHEMA olist_intent TO {}").format(sql.Identifier(runtime_role))
        )
        admin.execute(
            sql.SQL("GRANT SELECT ON olist_intent.schema_pin TO {}").format(
                sql.Identifier(runtime_role)
            )
        )
        admin.execute(
            sql.SQL("GRANT SELECT,INSERT,UPDATE ON olist_intent.challenges TO {}").format(
                sql.Identifier(runtime_role)
            )
        )
        admin.execute(
            sql.SQL("GRANT SELECT ON olist_intent.legacy_refunds TO {}").format(
                sql.Identifier(runtime_role)
            )
        )


class ConfirmationRequiredStore(BusinessStore):
    """The service's planner path can propose, but cannot issue transaction authority."""

    def refund(
        self,
        grant: CallerGrant,
        command: RefundCommand,
        *,
        run_id: str,
        run_limit_minor: int,
        fault: FaultHook | None = None,
        expires_at: datetime | None = None,
        record_commit: CommitRecorder | None = None,
    ) -> RefundReceipt:
        raise BusinessReview("customer_confirmation_required")


def _authority(
    connection: Connection[Any], case: CaseRecord, *, lock: bool = False
) -> tuple[dict[str, Any], Authority]:
    row = connection.execute(
        "SELECT * FROM olist_intent.challenges WHERE tenant_id=%s AND case_id=%s"
        + (" FOR UPDATE" if lock else ""),
        (case.tenant_id, case.case_id),
    ).fetchone()
    if row is None:
        raise BusinessReview("customer_confirmation_required")
    return row, Authority.model_validate_json(json.dumps(row["document"]))


def _binding(case: CaseRecord, authority: Authority) -> None:
    if (
        authority.case_id != case.case_id
        or authority.case_version != case.version
        or authority.command != case.command
        or authority.action_digest != case.action_digest
        or authority.record_pin != case.record_pin
        or authority.request_sha256 != sha(case.request.canonical_json())
    ):
        raise BusinessReview("customer_confirmation_binding_changed")


def confirmation_deadline(connect: ConnectionFactory, case: CaseRecord) -> datetime:
    with connect() as connection:
        from psycopg.rows import dict_row

        connection.row_factory = dict_row
        row, authority = _authority(connection, case)
        _binding(case, authority)
        if (
            row["state"] != "confirmed"
            or authority.confirmed_at is None
            or datetime.now(UTC) >= authority.expires_at
        ):
            raise BusinessReview("customer_confirmation_required_or_expired")
        return authority.expires_at


def consume(connection: Connection[Any], case: CaseRecord, receipt: RefundReceipt) -> None:
    row, authority = _authority(connection, case, lock=True)
    _binding(case, authority)
    if (
        row["state"] != "confirmed"
        or authority.confirmed_at is None
        or datetime.now(UTC) >= authority.expires_at
    ):
        raise BusinessReview("customer_confirmation_required_or_expired")
    connection.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
        ("olist-intent-account-v1|" + authority.customer.username,),
    )
    account = connection.execute(
        "SELECT principal,enabled FROM olist_app.accounts WHERE username=%s",
        (authority.customer.username,),
    ).fetchone()
    if (
        not account
        or not account["enabled"]
        or Principal.model_validate_json(json.dumps(account["principal"])) != authority.customer
    ):
        raise BusinessReview("customer_confirmation_account_changed")
    authority.customer.require("customer")
    authority.customer.grant(case.order_id)
    if (
        authority.customer.tenant_id != case.tenant_id
        or authority.command.amount_minor != receipt.amount_minor
    ):
        raise BusinessReview("customer_confirmation_scope_changed")
    saved = authority.model_copy(update={"consumed_receipt": receipt})
    connection.execute(
        "UPDATE olist_intent.challenges SET state='consumed',document=%s "
        "WHERE tenant_id=%s AND case_id=%s",
        (Jsonb(saved.model_dump(mode="json")), case.tenant_id, case.case_id),
    )


class CustomerIntentStore:
    def __init__(self, cases: "CaseStore") -> None:
        self.cases = cases

    def issue(self, customer: Principal, case_id: str) -> dict[str, Any]:
        customer.require("customer")
        with self.cases.connection() as connection, connection.transaction():
            case = self.cases.load(connection, customer, case_id, lock=True)
            if case.command is None or case.action_digest is None or case.record_pin is None:
                raise BusinessReview("refund_not_eligible")
            if case.status != "approved" and not (
                case.status == "review_required" and not case.request.require_review
            ):
                raise BusinessReview("case_not_ready_for_customer_confirmation")
            fresh = self.cases._snapshot(customer, case)
            if fresh["action_digest"] != case.action_digest:
                raise BusinessReview("customer_confirmation_evidence_changed")
            previous = connection.execute(
                "SELECT state,document FROM olist_intent.challenges "
                "WHERE tenant_id=%s AND case_id=%s FOR UPDATE",
                (case.tenant_id, case.case_id),
            ).fetchone()
            if previous:
                old = Authority.model_validate_json(json.dumps(previous["document"]))
                if previous["state"] == "consumed" or (
                    old.customer.username,
                    old.customer.tenant_id,
                    old.customer.actor_id,
                ) != (customer.username, customer.tenant_id, customer.actor_id):
                    raise BusinessReview("customer_confirmation_owned_by_another_or_consumed")
            clock = connection.execute("SELECT clock_timestamp() AS now").fetchone()
            if clock is None:
                raise RuntimeError("database clock unavailable")
            now = clock["now"]
            authority = Authority(
                customer=customer,
                case_id=case.case_id,
                case_version=case.version,
                request_sha256=sha(case.request.canonical_json()),
                command=case.command,
                action_digest=case.action_digest,
                record_pin=case.record_pin,
                issued_at=now,
                expires_at=now + timedelta(seconds=CONFIRMATION_SECONDS),
            )
            token = secrets.token_urlsafe(32)
            connection.execute(
                "INSERT INTO olist_intent.challenges VALUES(%s,%s,%s,'pending',%s) "
                "ON CONFLICT(tenant_id,case_id) DO UPDATE SET token_hash=excluded.token_hash,"
                "state='pending',document=excluded.document",
                (
                    case.tenant_id,
                    case.case_id,
                    sha(token),
                    Jsonb(authority.model_dump(mode="json")),
                ),
            )
            return {
                "challenge": token,
                "case_id": case.case_id,
                "order_id": case.order_id,
                "action": "refund",
                "amount_minor": case.command.amount_minor,
                "unit": "SIM",
                "expires_at": authority.expires_at.isoformat(),
                "request_text": case.request.text,
                "committed": False,
            }

    def confirm(self, customer: Principal, case_id: str, payload: Confirmation) -> dict[str, Any]:
        customer.require("customer")
        payload = Confirmation.model_validate_json(payload.canonical_json())
        with self.cases.connection() as connection, connection.transaction():
            case = self.cases.load(connection, customer, case_id, lock=True)
            row, authority = _authority(connection, case, lock=True)
            self._token(customer, row, authority, payload)
            if row["state"] == "consumed":
                if (
                    case.status != "committed"
                    or not case.result
                    or case.result.receipt != authority.consumed_receipt
                    or not case.result.receipt
                    or not self.cases.business.verify_receipt(
                        customer.grant(case.order_id), case.result.receipt
                    )
                ):
                    raise BusinessReview("customer_confirmation_receipt_not_verified")
                return {"confirmed": True, "committed": True}
            _binding(case, authority)
            if datetime.now(UTC) >= authority.expires_at:
                raise BusinessReview("customer_confirmation_expired")
            if row["state"] == "pending":
                authority = authority.model_copy(update={"confirmed_at": datetime.now(UTC)})
                connection.execute(
                    "UPDATE olist_intent.challenges SET state='confirmed',document=%s "
                    "WHERE tenant_id=%s AND case_id=%s",
                    (Jsonb(authority.model_dump(mode="json")), case.tenant_id, case.case_id),
                )
                self.cases.event(
                    connection,
                    case,
                    customer.actor_id,
                    "customer_confirmed",
                    action_digest=authority.action_digest,
                )
            return {"confirmed": True, "committed": False}

    @staticmethod
    def _token(
        customer: Principal, row: dict[str, Any], authority: Authority, payload: Confirmation
    ) -> None:
        if (
            authority.customer != customer
            or not secrets.compare_digest(row["token_hash"], sha(payload.challenge))
            or payload.amount_minor != authority.command.amount_minor
        ):
            raise PermissionError("customer confirmation does not match the challenge")

    def execute(
        self,
        customer: Principal,
        case_id: str,
        payload: Confirmation,
        *,
        run_limit_minor: int,
        fault: FaultHook | None = None,
    ) -> CaseRecord:
        customer.require("customer")
        payload = Confirmation.model_validate_json(payload.canonical_json())
        case, _ = self.cases.detail(customer, case_id)
        with self.cases.connection() as connection:
            row, authority = _authority(connection, case)
            self._token(customer, row, authority, payload)
            if (
                case.status == "committed"
                and row["state"] == "consumed"
                and case.result
                and case.result.receipt == authority.consumed_receipt
            ):
                return case
        try:
            expires = confirmation_deadline(self.cases.connect, case)
        except BusinessReview:
            latest, _ = self.cases.detail(customer, case_id)
            with self.cases.connection() as connection:
                latest_row, latest_authority = _authority(connection, latest)
                self._token(customer, latest_row, latest_authority, payload)
                if (
                    latest.status == "committed"
                    and latest_row["state"] == "consumed"
                    and latest.result
                    and latest.result.receipt == latest_authority.consumed_receipt
                ):
                    return latest
            raise
        if case.command is None:
            raise BusinessReview("customer_confirmation_has_no_action")
        command = case.command

        def record(connection: Connection[Any], receipt: RefundReceipt) -> None:
            locked = self.cases.load(connection, customer, case_id, lock=True)
            if locked.status == "committed" and locked.result and locked.result.receipt == receipt:
                return
            if locked.request.require_review and (
                locked.status != "approved"
                or not locked.approved_by
                or locked.approval_version != locked.version
            ):
                raise BusinessReview("required_reviewer_approval_missing")
            if locked.status not in ("approved", "review_required") or locked.command != command:
                raise BusinessReview("customer_confirmation_case_changed")
            if self.cases._snapshot_pin_from_locked_order(connection, locked) != locked.record_pin:
                raise BusinessReview("customer_confirmation_evidence_changed")
            consume(connection, locked, receipt)
            result = WorkflowResult(
                outcome="refunded",
                reason="customer_confirmed_ledger_and_state_verified",
                message=(
                    f"Your full refund of {receipt.amount_minor // 100}."
                    f"{receipt.amount_minor % 100:02d} SIM is committed in the simulation ledger."
                ),
                receipt=receipt,
                usage=locked.result.usage if locked.result else None,
                usage_run_id=locked.result.usage_run_id if locked.result else None,
            )
            current = locked.model_copy(
                update={
                    "status": "committed",
                    "result": result,
                    "version": locked.version + 1,
                    "updated_at": datetime.now(UTC),
                }
            )
            self.cases.save(connection, current)
            self.cases.event(
                connection,
                current,
                customer.actor_id,
                "committed",
                ledger_id=receipt.ledger_id,
                action_digest=locked.action_digest,
            )

        grant = CallerGrant(
            tenant_id=customer.tenant_id,
            actor_id="customer-confirmed-refund-service",
            order_ids=(case.order_id,),
            capabilities=("read", "refund"),
        )
        self.cases.business.refund(
            grant,
            command,
            run_id=uuid.uuid4().hex,
            run_limit_minor=run_limit_minor,
            expires_at=min(expires, datetime.now(UTC) + timedelta(minutes=2)),
            record_commit=record,
            fault=fault,
        )
        return self.cases.detail(customer, case_id)[0]
