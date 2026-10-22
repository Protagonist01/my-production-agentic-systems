"""Postgres-owned SIM effects, approvals and confirmations. No freight provider calls."""

import hashlib
import json
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from importlib.resources import files
from typing import Any

from psycopg import Connection, sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from supply_chain.action_contracts import (
    POLICY,
    Command,
    Grant,
    Proposal,
    Receipt,
    ReviewRequired,
    Shipment,
    Snapshot,
    options,
)

ConnectionFactory = Callable[[], Connection[Any]]


def setup(connection: Connection[Any], runtime_role: str) -> None:
    """Trusted administrator; schema DDL is immutable and not a runtime capability."""
    ddl = files("supply_chain").joinpath("operations.sql").read_text(encoding="utf-8")
    pin = hashlib.sha256(ddl.encode()).hexdigest()
    with connection.transaction():
        connection.execute("SELECT pg_advisory_xact_lock(73412053)")
        connection.execute("CREATE SCHEMA IF NOT EXISTS supply")
        connection.execute("REVOKE ALL ON SCHEMA supply FROM PUBLIC")
        connection.execute(
            "CREATE TABLE IF NOT EXISTS supply.schema_pin(version integer "
            "PRIMARY KEY,sha256 text NOT NULL)"
        )
        with connection.cursor(row_factory=dict_row) as cursor:
            pins = cursor.execute("SELECT version,sha256 FROM supply.schema_pin").fetchall()
        if pins and pins != [{"version": 1, "sha256": pin}]:
            raise ValueError("Supply schema differs from immutable version1")
        if not pins:
            connection.execute(ddl)
            connection.execute("INSERT INTO supply.schema_pin VALUES(1,%s)", (pin,))
        for statement in (
            "GRANT USAGE ON SCHEMA supply TO {}",
            "GRANT SELECT ON supply.budgets,supply.shipments TO {}",
            "GRANT UPDATE(version,spent_minor,replans) ON supply.budgets TO {}",
            "GRANT UPDATE(version,document) ON supply.shipments TO {}",
            "GRANT SELECT,INSERT ON supply.proposals,supply.ledger,supply.confirmations TO {}",
            "GRANT UPDATE(document) ON supply.proposals TO {}",
        ):
            connection.execute(sql.SQL(statement).format(sql.Identifier(runtime_role)))


def enroll(connection: Connection[Any], event_id: str, shipments: tuple[Shipment, ...]) -> None:
    """Trusted incident/fixture enrollment, never a client upsert or reset."""
    if not shipments or len({s.shipment_id for s in shipments}) != len(shipments):
        raise ValueError("nonempty unique shipments required")
    tenants = {s.tenant_id for s in shipments}
    if len(tenants) != 1:
        raise ValueError("one tenant per incident")
    # Validate the incident identifier using the same command wire boundary.
    Command(
        tenant_id=shipments[0].tenant_id,
        event_id=event_id,
        shipment_id=shipments[0].shipment_id,
        expected_shipment_version=0,
        expected_budget_version=0,
        action="wait",
    )
    with connection.transaction():
        connection.execute(
            "INSERT INTO supply.budgets(tenant_id,event_id) VALUES(%s,%s)",
            (shipments[0].tenant_id, event_id),
        )
        for item in shipments:
            item = Shipment.model_validate_json(item.canonical_json())
            if item.version != 0:
                raise ValueError("new shipments require version zero")
            connection.execute(
                "INSERT INTO supply.shipments VALUES(%s,%s,%s,%s)",
                (
                    item.tenant_id,
                    item.shipment_id,
                    item.version,
                    Jsonb(item.model_dump(mode="json")),
                ),
            )


class OperationStore:
    def __init__(
        self, connect: ConnectionFactory, *, clock: Callable[[], datetime] | None = None
    ) -> None:
        self.connect = connect
        self.clock = clock or (lambda: datetime.now(UTC))

    def now(self) -> datetime:
        now = self.clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("aware server clock required")
        return now

    @contextmanager
    def _connection(self) -> Iterator[Connection[Any]]:
        with self.connect() as connection:
            connection.autocommit = True
            connection.row_factory = dict_row
            connection.execute("SET statement_timeout=5000")
            connection.execute("SET lock_timeout=3000")
            yield connection

    @staticmethod
    def _grant(grant: Grant) -> Grant:
        return Grant.model_validate_json(grant.canonical_json())

    @staticmethod
    def _budget(
        connection: Connection[Any], tenant: str, event: str, *, lock: bool = False
    ) -> dict[str, Any]:
        row = connection.execute(
            "SELECT * FROM supply.budgets WHERE tenant_id=%s AND event_id=%s"
            + (" FOR UPDATE" if lock else ""),
            (tenant, event),
        ).fetchone()
        if row is None:
            raise ReviewRequired("incident_missing")
        return dict(row)

    @staticmethod
    def _shipment(
        connection: Connection[Any],
        grant: Grant,
        shipment: str,
        capability: str,
        *,
        lock: bool = False,
    ) -> Shipment:
        grant.require(grant.tenant_id, shipment, capability)
        row = connection.execute(
            "SELECT version,document FROM supply.shipments WHERE tenant_id=%s AND shipment_id=%s"
            + (" FOR UPDATE" if lock else ""),
            (grant.tenant_id, shipment),
        ).fetchone()
        if row is None:
            raise ReviewRequired("shipment_missing")
        value = Shipment.model_validate_json(json.dumps(row["document"]))
        grant.require(value.tenant_id, value.shipment_id, capability)
        if value.shipment_id != shipment or value.version != row["version"]:
            raise ReviewRequired("shipment_integrity")
        return value

    @staticmethod
    def _proposal(connection: Connection[Any], tenant: str, operation: str) -> Proposal | None:
        row = connection.execute(
            "SELECT document FROM supply.proposals WHERE tenant_id=%s AND operation_id=%s",
            (tenant, operation),
        ).fetchone()
        if row is None:
            return None
        proposal = Proposal.model_validate_json(json.dumps(row["document"]))
        if proposal.command.tenant_id != tenant or proposal.command.operation_id != operation:
            raise ReviewRequired("proposal_integrity")
        return proposal

    @staticmethod
    def _receipt(connection: Connection[Any], tenant: str, operation: str) -> Receipt | None:
        row = connection.execute(
            "SELECT document FROM supply.ledger WHERE tenant_id=%s AND operation_id=%s",
            (tenant, operation),
        ).fetchone()
        if row is None:
            return None
        receipt = Receipt.model_validate_json(json.dumps(row["document"]))
        if receipt.command.tenant_id != tenant or receipt.command.operation_id != operation:
            raise ReviewRequired("ledger_integrity")
        return receipt

    @staticmethod
    def _save(connection: Connection[Any], proposal: Proposal) -> None:
        connection.execute(
            "INSERT INTO supply.proposals VALUES(%s,%s,%s) ON "
            "CONFLICT(tenant_id,operation_id) DO UPDATE SET document=EXCLUDED.document",
            (
                proposal.command.tenant_id,
                proposal.command.operation_id,
                Jsonb(proposal.model_dump(mode="json")),
            ),
        )

    def portfolio(self, grant: Grant, event: str) -> tuple[dict[str, Any], tuple[Shipment, ...]]:
        grant = self._grant(grant)
        grant.require_event(event)
        if "read" not in grant.capabilities or not grant.shipment_ids:
            raise PermissionError("read scope required")
        with self._connection() as connection, connection.transaction():
            budget = self._budget(connection, grant.tenant_id, event, lock=True)
            shipments = tuple(
                self._shipment(connection, grant, key, "read") for key in sorted(grant.shipment_ids)
            )
            return budget, shipments

    def propose(self, grant: Grant, command: Command) -> Proposal:
        grant = self._grant(grant)
        command = Command.model_validate_json(command.canonical_json())
        grant.require(command.tenant_id, command.shipment_id, "propose")
        grant.require_event(command.event_id)
        with self._connection() as connection, connection.transaction():
            budget = self._budget(connection, grant.tenant_id, command.event_id, lock=True)
            shipment = self._shipment(connection, grant, command.shipment_id, "propose", lock=True)
            previous = self._proposal(connection, grant.tenant_id, command.operation_id)
            receipt = self._receipt(connection, grant.tenant_id, command.operation_id)
            if previous is not None and previous.command == command:
                return previous
            if receipt is not None:
                raise ReviewRequired("already_committed_payload_conflict")
            now = self.now()
            choice = next((o for o in options(shipment, now) if o.action == command.action), None)
            if choice is None or choice.cost_minor > POLICY.action_cap_minor:
                raise ReviewRequired("option_unavailable")
            if (
                command.expected_budget_version != budget["version"]
                or command.expected_shipment_version != shipment.version
            ):
                raise ReviewRequired("stale_versions")
            if budget["spent_minor"] + choice.cost_minor > POLICY.event_cap_minor:
                raise ReviewRequired("budget_exhausted")
            if previous is not None:
                if previous.status in ("rejected", "expired") or now >= previous.expires_at:
                    raise ReviewRequired("terminal_proposal")
                old = previous.command
                if (
                    old.expected_budget_version == budget["version"]
                    and old.expected_shipment_version == shipment.version
                ):
                    raise ReviewRequired("payload_conflict")
                if budget["replans"] >= POLICY.max_replans:
                    raise ReviewRequired("replan_limit")
                connection.execute(
                    "UPDATE supply.budgets SET replans=replans+1 WHERE "
                    "tenant_id=%s AND event_id=%s",
                    (grant.tenant_id, command.event_id),
                )
            expires = min(shipment.expires_at, now + timedelta(seconds=POLICY.wait_seconds))
            payload = hashlib.sha256(
                (command.canonical_json() + choice.canonical_json() + expires.isoformat()).encode()
            ).hexdigest()
            proposal = Proposal(
                command=command,
                option=choice,
                proposer_id=grant.actor_id,
                proposed_at=now,
                expires_at=expires,
                payload_sha256=payload,
                status="pending" if choice.cost_minor > POLICY.approval_above_minor else "approved",
            )
            self._save(connection, proposal)
            return proposal

    def _locked(
        self, connection: Connection[Any], grant: Grant, command: Command, capability: str
    ) -> tuple[dict[str, Any], Shipment, Proposal]:
        grant.require(command.tenant_id, command.shipment_id, capability)
        grant.require_event(command.event_id)
        budget = self._budget(connection, grant.tenant_id, command.event_id, lock=True)
        shipment = self._shipment(connection, grant, command.shipment_id, capability, lock=True)
        proposal = self._proposal(connection, grant.tenant_id, command.operation_id)
        if proposal is None:
            raise ReviewRequired("proposal_missing")
        if proposal.command != command:
            raise ReviewRequired("payload_conflict")
        return budget, shipment, proposal

    def review(
        self, grant: Grant, command: Command, payload_sha256: str, *, approve: bool
    ) -> Proposal:
        grant = self._grant(grant)
        command = Command.model_validate_json(command.canonical_json())
        with self._connection() as connection, connection.transaction():
            budget, shipment, proposal = self._locked(connection, grant, command, "review")
            if grant.actor_id == proposal.proposer_id:
                raise PermissionError("separate reviewer required")
            if payload_sha256 != proposal.payload_sha256:
                raise ReviewRequired("approval_payload_mismatch")
            status = "approved" if approve else "rejected"
            if proposal.status != "pending":
                if proposal.status == status and proposal.reviewer_id == grant.actor_id:
                    return proposal
                raise ReviewRequired("review_already_terminal")
            if self.now() >= proposal.expires_at:
                proposal = proposal.model_copy(update={"status": "expired"})
            else:
                shipment.require_fresh(self.now())
                if (
                    budget["version"] != command.expected_budget_version
                    or shipment.version != command.expected_shipment_version
                ):
                    raise ReviewRequired("stale_versions")
                proposal = proposal.model_copy(
                    update={"status": status, "reviewer_id": grant.actor_id}
                )
            self._save(connection, proposal)
            return proposal

    def apply(
        self,
        grant: Grant,
        command: Command,
        *,
        run_id: str,
        fault: Callable[[str], None] | None = None,
    ) -> Receipt:
        grant = self._grant(grant)
        command = Command.model_validate_json(command.canonical_json())
        with self._connection() as connection, connection.transaction():
            budget, shipment, proposal = self._locked(connection, grant, command, "apply")
            receipt = self._receipt(connection, grant.tenant_id, command.operation_id)
            if receipt is not None:
                if receipt.command != command:
                    raise ReviewRequired("committed_payload_conflict")
                return receipt
            now = self.now()
            if now >= proposal.expires_at:
                raise ReviewRequired("approval_expired")
            if proposal.status != "approved":
                raise ReviewRequired("approval_required")
            shipment.require_fresh(now)
            if (
                shipment.version != command.expected_shipment_version
                or budget["version"] != command.expected_budget_version
            ):
                raise ReviewRequired("stale_versions")
            choice = next((o for o in options(shipment, now) if o.action == command.action), None)
            if choice != proposal.option or choice.cost_minor > POLICY.action_cap_minor:
                raise ReviewRequired("option_changed")
            if choice.cost_minor > POLICY.approval_above_minor and (
                proposal.reviewer_id is None
                or proposal.reviewer_id == proposal.proposer_id
                or proposal.reviewer_id == grant.actor_id
            ):
                raise PermissionError("separate exact approval required")
            if budget["spent_minor"] + choice.cost_minor > POLICY.event_cap_minor:
                raise ReviewRequired("budget_exhausted")
            updated = shipment.model_copy(update={"version": shipment.version + 1})
            receipt = Receipt(
                command=command,
                payload_sha256=proposal.payload_sha256,
                cost_minor=choice.cost_minor,
                committed_at=now,
                confirmation_deadline=now + timedelta(seconds=POLICY.wait_seconds),
                execution_run_id=run_id,
                shipment_version=updated.version,
                budget_version=budget["version"] + 1,
            )
            connection.execute(
                "UPDATE supply.budgets SET "
                "version=version+1,spent_minor=spent_minor+%s WHERE tenant_id=%s AND event_id=%s",
                (choice.cost_minor, grant.tenant_id, command.event_id),
            )
            connection.execute(
                "UPDATE supply.shipments SET version=%s,document=%s WHERE "
                "tenant_id=%s AND shipment_id=%s",
                (
                    updated.version,
                    Jsonb(updated.model_dump(mode="json")),
                    grant.tenant_id,
                    shipment.shipment_id,
                ),
            )
            connection.execute(
                "INSERT INTO supply.ledger VALUES(%s,%s,%s)",
                (grant.tenant_id, command.operation_id, Jsonb(receipt.model_dump(mode="json"))),
            )
            if fault:
                fault("before_commit")
        if fault:
            fault("after_commit")
        return receipt

    def confirm(
        self, grant: Grant, command: Command, payload_sha256: str, *, success: bool
    ) -> Snapshot:
        grant = self._grant(grant)
        command = Command.model_validate_json(command.canonical_json())
        with self._connection() as connection, connection.transaction():
            _, _, proposal = self._locked(connection, grant, command, "confirm")
            receipt = self._receipt(connection, grant.tenant_id, command.operation_id)
            if receipt is None:
                raise ReviewRequired("confirmation_before_commit")
            if payload_sha256 != receipt.payload_sha256:
                raise ReviewRequired("confirmation_payload_mismatch")
            self._terminal(connection, grant, proposal, receipt, success=success)
        return self.snapshot(grant, command)

    def _terminal(
        self,
        connection: Connection[Any],
        grant: Grant,
        proposal: Proposal,
        receipt: Receipt,
        *,
        success: bool | None = None,
    ) -> None:
        now = self.now()
        status = (
            "confirmation_timeout"
            if now >= receipt.confirmation_deadline
            else ("confirmed" if success else "confirmation_failed")
        )
        if success is None and now < receipt.confirmation_deadline:
            return
        connection.execute(
            "INSERT INTO supply.confirmations VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
            (
                grant.tenant_id,
                proposal.command.operation_id,
                receipt.payload_sha256,
                status,
                grant.actor_id,
                now,
            ),
        )

    def snapshot(self, grant: Grant, command: Command) -> Snapshot:
        grant = self._grant(grant)
        command = Command.model_validate_json(command.canonical_json())
        with self._connection() as connection, connection.transaction():
            _, _, proposal = self._locked(connection, grant, command, "read")
            receipt = self._receipt(connection, grant.tenant_id, command.operation_id)
            if receipt:
                self._terminal(connection, grant, proposal, receipt)
                confirmation = connection.execute(
                    "SELECT outcome FROM supply.confirmations WHERE "
                    "tenant_id=%s AND operation_id=%s",
                    (grant.tenant_id, command.operation_id),
                ).fetchone()
                return Snapshot(
                    proposal=proposal,
                    receipt=receipt,
                    outcome=confirmation["outcome"] if confirmation else "awaiting_confirmation",
                )
            if self.now() >= proposal.expires_at and proposal.status in ("pending", "approved"):
                proposal = proposal.model_copy(update={"status": "expired"})
                self._save(connection, proposal)
            return Snapshot(proposal=proposal, outcome=proposal.status)

    def receipts(self, grant: Grant, event: str) -> tuple[Receipt, ...]:
        grant = self._grant(grant)
        grant.require_event(event)
        if "read" not in grant.capabilities:
            raise PermissionError("read scope required")
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT document FROM supply.ledger WHERE tenant_id=%s ORDER BY operation_id",
                (grant.tenant_id,),
            ).fetchall()
        values = tuple(Receipt.model_validate_json(json.dumps(row["document"])) for row in rows)
        return tuple(
            r
            for r in values
            if r.command.event_id == event and r.command.shipment_id in grant.shipment_ids
        )

    def current(self, grant: Grant, event: str, shipment: str) -> Proposal | None:
        grant = self._grant(grant)
        grant.require_event(event)
        grant.require(grant.tenant_id, shipment, "read")
        identity = Command(
            tenant_id=grant.tenant_id,
            event_id=event,
            shipment_id=shipment,
            action="wait",
            expected_shipment_version=0,
            expected_budget_version=0,
        )
        with self._connection() as connection:
            return self._proposal(connection, grant.tenant_id, identity.operation_id)
