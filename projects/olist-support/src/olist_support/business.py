"""Olist-owned Postgres transactions; all grants/connection factories are trusted inputs."""

import hashlib
import json
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from importlib.resources import files
from typing import Any

from psycopg import Connection, sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from olist_support.business_contracts import (
    BusinessReview,
    CallerGrant,
    RefundCommand,
    RefundReceipt,
)
from olist_support.policy import ScenarioConfirmation, SupportRequest, propose
from olist_support.views import OrderView

ConnectionFactory = Callable[[], Connection[Any]]
FaultHook = Callable[[str], None]


def sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def identity_hash(namespace: str, *parts: str) -> str:
    return sha(json.dumps([namespace, *parts], ensure_ascii=False, separators=(",", ":")))


def setup(connection: Connection[Any], runtime_role: str) -> None:
    """Trusted admin bootstrap, serial and immutable; runtime never invokes DDL."""
    ddl = files("olist_support").joinpath("business.sql").read_text(encoding="utf-8")
    with connection.transaction():
        connection.execute("SELECT pg_advisory_xact_lock(73412041)")
        connection.execute("CREATE SCHEMA IF NOT EXISTS olist")
        connection.execute("REVOKE ALL ON SCHEMA olist FROM PUBLIC")
        connection.execute(
            "CREATE TABLE IF NOT EXISTS olist.schema_pin (version integer PRIMARY"
            " KEY, sha256 text NOT NULL)"
        )
        current = connection.execute("SELECT version,sha256 FROM olist.schema_pin").fetchall()
        if current and current != [(1, sha(ddl))]:
            raise ValueError("Olist business schema differs from immutable version1")
        if not current:
            connection.execute(ddl)
            connection.execute("INSERT INTO olist.schema_pin VALUES(1,%s)", (sha(ddl),))
        connection.execute(
            sql.SQL("GRANT USAGE ON SCHEMA olist TO {}").format(sql.Identifier(runtime_role))
        )
        connection.execute(
            sql.SQL(
                "GRANT SELECT,INSERT,UPDATE ON olist.orders,olist.run_budgets,olist.sessions TO {}"
            ).format(sql.Identifier(runtime_role))
        )
        connection.execute(
            sql.SQL("GRANT SELECT,INSERT ON olist.refunds TO {}").format(
                sql.Identifier(runtime_role)
            )
        )


def enroll(
    connection: Connection[Any], view: OrderView, confirmation: ScenarioConfirmation | None
) -> None:
    """Trusted scenario provisioning, never an agent tool; no overwrite/upsert."""
    view = OrderView.model_validate_json(view.canonical_json())
    if confirmation is not None:
        confirmation = ScenarioConfirmation.model_validate_json(confirmation.canonical_json())
        if (confirmation.tenant_id, confirmation.order_id) != (view.tenant_id, view.order_id):
            raise ValueError("scenario confirmation belongs to another order")
        if confirmation.prior_refund_minor != 0:
            raise ValueError("new simulation starts with an explicit zero prior refund balance")
    with connection.transaction():
        connection.execute(
            (
                "INSERT INTO "
                "olist.orders(tenant_id,order_id,source_view,confirmation,source_pin)"
                " VALUES(%s,%s,%s,%s,%s)"
            ),
            (
                view.tenant_id,
                view.order_id,
                Jsonb(view.model_dump(mode="json")),
                Jsonb(confirmation.model_dump(mode="json")) if confirmation else None,
                sha(view.canonical_json()),
            ),
        )


class BusinessStore:
    def __init__(self, connect: ConnectionFactory) -> None:
        self.connect = connect

    @contextmanager
    def _connection(self) -> Iterator[Connection[Any]]:
        with self.connect() as connection:
            connection.autocommit = True
            connection.row_factory = dict_row
            connection.execute("SET statement_timeout = 5000")
            connection.execute("SET lock_timeout = 2000")
            yield connection

    @staticmethod
    def _order(row: dict[str, Any]) -> tuple[OrderView, ScenarioConfirmation | None, int]:
        view = OrderView.model_validate_json(json.dumps(row["source_view"]))
        if sha(view.canonical_json()) != row["source_pin"]:
            raise ValueError("enrolled source view differs from its stored pin")
        facts = (
            ScenarioConfirmation.model_validate_json(json.dumps(row["confirmation"]))
            if row["confirmation"]
            else None
        )
        if facts is not None:
            facts = facts.model_copy(update={"prior_refund_minor": row["refunded_minor"]})
        return view, facts, row["version"]

    def order(
        self, grant: CallerGrant, tenant: str, order: str
    ) -> tuple[OrderView, ScenarioConfirmation | None, int]:
        grant = CallerGrant.model_validate_json(grant.canonical_json())
        grant.require(tenant, order, "read")
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM olist.orders WHERE tenant_id=%s AND order_id=%s", (tenant, order)
            ).fetchone()
            if row is None:
                raise LookupError("order is absent from this controlled backend")
            return self._order(row)

    def refund(
        self,
        grant: CallerGrant,
        command: RefundCommand,
        *,
        run_id: str,
        run_limit_minor: int,
        fault: FaultHook | None = None,
        expires_at: datetime | None = None,
    ) -> RefundReceipt:
        grant = CallerGrant.model_validate_json(grant.canonical_json())
        command = RefundCommand.model_validate_json(command.canonical_json())
        grant.require(command.tenant_id, command.order_id, "refund")
        grant.require(command.tenant_id, command.order_id, "read")
        if (
            not run_id.strip()
            or len(run_id) > 256
            or type(run_limit_minor) is not int
            or not 0 <= run_limit_minor <= 2**63 - 1
        ):
            raise ValueError("explicit run ID and nonnegative SIM run limit are required")
        if expires_at is not None and (
            expires_at.tzinfo is None or datetime.now(UTC) >= expires_at
        ):
            raise TimeoutError("refund deadline is invalid or exhausted")
        payload = sha(command.canonical_json())
        tenant, order = command.tenant_id, command.order_id
        with self._connection() as connection:
            with connection.transaction():
                connection.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                    (identity_hash("refund-lock", tenant, command.business_operation_id),),
                )
                prior = connection.execute(
                    (
                        "SELECT payload_sha256,receipt FROM olist.refunds WHERE tenant_id=%s "
                        "AND operation_id=%s"
                    ),
                    (tenant, command.business_operation_id),
                ).fetchone()
                if prior is not None:
                    if prior["payload_sha256"] != payload:
                        raise BusinessReview("repeated_operation_payload_mismatch")
                    return RefundReceipt.model_validate_json(json.dumps(prior["receipt"]))
                connection.execute(
                    (
                        "INSERT INTO olist.run_budgets(tenant_id,run_id,limit_minor) "
                        "VALUES(%s,%s,%s) ON CONFLICT DO NOTHING"
                    ),
                    (tenant, run_id, run_limit_minor),
                )
                budget = connection.execute(
                    "SELECT * FROM olist.run_budgets WHERE tenant_id=%s AND run_id=%s FOR UPDATE",
                    (tenant, run_id),
                ).fetchone()
                if budget is None:
                    raise RuntimeError("run budget disappeared inside its transaction")
                if budget["limit_minor"] != run_limit_minor:
                    raise BusinessReview("run_limit_configuration_changed")
                row = connection.execute(
                    "SELECT * FROM olist.orders WHERE tenant_id=%s AND order_id=%s FOR UPDATE",
                    (tenant, order),
                ).fetchone()
                if row is None:
                    raise LookupError("order is absent from this controlled backend")
                view, facts, version = self._order(row)
                if version != command.expected_version:
                    raise BusinessReview("stale_order_version")
                proposal = propose(
                    view,
                    SupportRequest(
                        intent="refund",
                        message="Trusted commit-time full-refund validation.",
                        requested_minor=command.amount_minor,
                    ),
                    facts,
                )
                if (
                    proposal.action != "propose_full_refund"
                    or proposal.amount_minor != command.amount_minor
                ):
                    raise BusinessReview(proposal.reason)
                if budget["spent_minor"] + command.amount_minor > run_limit_minor:
                    raise BusinessReview("run_refund_limit_exceeded")
                receipt = RefundReceipt(
                    tenant_id=tenant,
                    business_operation_id=command.business_operation_id,
                    order_id=order,
                    ledger_id=identity_hash(
                        "refund-receipt", tenant, command.business_operation_id
                    ),
                    amount_minor=command.amount_minor,
                    order_version=version + 1,
                    original_run_id=run_id,
                    actor_id=grant.actor_id,
                )
                connection.execute(
                    (
                        "UPDATE olist.orders SET "
                        "refunded_minor=refunded_minor+%s,version=version+1 WHERE "
                        "tenant_id=%s AND order_id=%s"
                    ),
                    (command.amount_minor, tenant, order),
                )
                connection.execute(
                    (
                        "UPDATE olist.run_budgets SET spent_minor=spent_minor+%s WHERE "
                        "tenant_id=%s AND run_id=%s"
                    ),
                    (command.amount_minor, tenant, run_id),
                )
                connection.execute(
                    "INSERT INTO olist.refunds VALUES(%s,%s,%s,%s,%s,%s)",
                    (
                        tenant,
                        command.business_operation_id,
                        order,
                        payload,
                        Jsonb(receipt.model_dump(mode="json")),
                        command.amount_minor,
                    ),
                )
                if expires_at is not None and datetime.now(UTC) >= expires_at:
                    raise TimeoutError("refund deadline exhausted before commit")
                if fault:
                    fault("before_commit")
        if fault:
            fault("after_commit")
        return receipt

    def verify_receipt(self, grant: CallerGrant, receipt: RefundReceipt) -> bool:
        grant.require(receipt.tenant_id, receipt.order_id, "read")
        receipt = RefundReceipt.model_validate_json(receipt.canonical_json())
        with self._connection() as connection:
            row = connection.execute(
                (
                    "SELECT "
                    "r.receipt,r.payload_sha256,r.amount_minor,o.refunded_minor,o.version"
                    " FROM olist.refunds r JOIN olist.orders o USING(tenant_id,order_id) "
                    "WHERE r.tenant_id=%s AND r.operation_id=%s"
                ),
                (receipt.tenant_id, receipt.business_operation_id),
            ).fetchone()
            return bool(
                row
                and row["receipt"] == receipt.model_dump(mode="json")
                and row["amount_minor"] == receipt.amount_minor
                and row["refunded_minor"] == receipt.amount_minor
                and receipt.ledger_id
                == identity_hash("refund-receipt", receipt.tenant_id, receipt.business_operation_id)
                and row["payload_sha256"]
                == sha(
                    RefundCommand(
                        tenant_id=receipt.tenant_id,
                        business_operation_id=receipt.business_operation_id,
                        order_id=receipt.order_id,
                        amount_minor=receipt.amount_minor,
                        expected_version=receipt.order_version - 1,
                    ).canonical_json()
                )
                and row["version"] >= receipt.order_version
            )

    @contextmanager
    def session(
        self, grant: CallerGrant, *, tenant: str, order: str, event_id: str, request_pin: str
    ) -> Iterator[None]:
        grant.require(tenant, order, "read")
        identity = identity_hash("session-lock", tenant, event_id)
        with self._connection() as connection:
            connection.execute("SELECT pg_advisory_lock(hashtextextended(%s,0))", (identity,))
            try:
                connection.execute(
                    "INSERT INTO olist.sessions VALUES(%s,%s,%s) ON CONFLICT DO NOTHING",
                    (tenant, event_id, request_pin),
                )
                existing = connection.execute(
                    "SELECT request_sha256 FROM olist.sessions WHERE tenant_id=%s AND event_id=%s",
                    (tenant, event_id),
                ).fetchone()
                if existing is None:
                    raise RuntimeError("workflow session disappeared during binding")
                if existing["request_sha256"] != request_pin:
                    raise BusinessReview("business_event_input_mismatch")
                connection.commit()
                yield
            finally:
                connection.execute("SELECT pg_advisory_unlock(hashtextextended(%s,0))", (identity,))
