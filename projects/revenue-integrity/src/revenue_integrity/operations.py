"""Revenue-owned transactional SIM actions. No external CRM/payment integration."""

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

from revenue_integrity.billing_contracts import BillingInput, Invoice
from revenue_integrity.operation_contracts import (
    BusinessReview,
    ChangeCommand,
    Proposal,
    Receipt,
    RevenueGrant,
    RevenueRecord,
)
from revenue_integrity.reconcile import reconcile

ConnectionFactory = Callable[[], Connection[Any]]
FaultHook = Callable[[str], None]


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def setup(connection: Connection[Any], runtime_role: str) -> None:
    """Trusted immutable schema/bootstrap; the runtime role cannot migrate or erase."""
    ddl = files("revenue_integrity").joinpath("operations.sql").read_text(encoding="utf-8")
    with connection.transaction():
        connection.execute("SELECT pg_advisory_xact_lock(73412051)")
        connection.execute("CREATE SCHEMA IF NOT EXISTS revenue")
        connection.execute("REVOKE ALL ON SCHEMA revenue FROM PUBLIC")
        connection.execute(
            "CREATE TABLE IF NOT EXISTS revenue.schema_pin(version integer "
            "PRIMARY KEY,sha256 text NOT NULL)"
        )
        with connection.cursor(row_factory=dict_row) as cursor:
            pins = cursor.execute("SELECT version,sha256 FROM revenue.schema_pin").fetchall()
        if pins and pins != [{"version": 1, "sha256": digest(ddl)}]:
            raise ValueError("Revenue schema differs from immutable version1")
        if not pins:
            connection.execute(ddl)
            connection.execute("INSERT INTO revenue.schema_pin VALUES(1,%s)", (digest(ddl),))
        for statement in (
            "GRANT USAGE ON SCHEMA revenue TO {}",
            "GRANT SELECT,INSERT ON revenue.proposals,revenue.ledger TO {}",
            "GRANT SELECT ON revenue.records TO {}",
            "GRANT UPDATE(version,document) ON revenue.records TO {}",
            "GRANT UPDATE(document) ON revenue.proposals TO {}",
        ):
            connection.execute(sql.SQL(statement).format(sql.Identifier(runtime_role)))


def enroll(connection: Connection[Any], record: RevenueRecord) -> None:
    """Trusted fixture enrollment, never an agent action; no overwrite/upsert."""
    record = RevenueRecord.model_validate_json(record.canonical_json())
    if record.version != 0 or record.alias_to is not None:
        raise ValueError("new records require original unaliased version zero")
    if (
        record.billing_input is not None
        and record.amount_minor != record.billing_input.invoice.amount_minor
    ):
        raise ValueError("initial invoice amount differs from source")
    with connection.transaction():
        connection.execute(
            "INSERT INTO revenue.records VALUES(%s,%s,%s,%s,%s)",
            (
                record.tenant_id,
                record.resource_id,
                record.kind,
                record.version,
                Jsonb(record.model_dump(mode="json")),
            ),
        )


class OperationStore:
    def __init__(
        self, connect: ConnectionFactory, *, clock: Callable[[], datetime] | None = None
    ) -> None:
        self.connect = connect
        self.clock = clock or (lambda: datetime.now(UTC))

    def _now(self) -> datetime:
        value = self.clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("server clock requires timezone")
        return value

    @contextmanager
    def _connection(self) -> Iterator[Connection[Any]]:
        with self.connect() as connection:
            connection.autocommit = True
            connection.row_factory = dict_row
            connection.execute("SET statement_timeout = 5000")
            connection.execute("SET lock_timeout = 3000")
            yield connection

    @staticmethod
    def _grant(grant: RevenueGrant) -> RevenueGrant:
        return RevenueGrant.model_validate_json(grant.canonical_json())

    @staticmethod
    def _record(
        connection: Connection[Any],
        grant: RevenueGrant,
        resource: str,
        capability: str,
        *,
        lock: bool = False,
    ) -> RevenueRecord:
        grant.require_any(resource, capability)
        row = connection.execute(
            "SELECT version,document FROM revenue.records WHERE tenant_id=%s AND resource_id=%s"
            + (" FOR UPDATE" if lock else ""),
            (grant.tenant_id, resource),
        ).fetchone()
        if row is None:
            raise BusinessReview("record_missing")
        value = RevenueRecord.model_validate_json(json.dumps(row["document"]))
        grant.require(value.tenant_id, value.kind, value.resource_id, capability)
        if (
            value.version != row["version"]
            or value.resource_id != resource
            or value.tenant_id != grant.tenant_id
        ):
            raise BusinessReview("record_integrity")
        return value

    @staticmethod
    def _proposal(
        connection: Connection[Any],
        grant: RevenueGrant,
        operation_id: str,
        capability: str,
        *,
        lock: bool = False,
    ) -> Proposal:
        if capability not in grant.capabilities:
            raise PermissionError("Revenue capability denied")
        row = connection.execute(
            "SELECT command_sha256,document FROM revenue.proposals WHERE "
            "tenant_id=%s AND operation_id=%s" + (" FOR UPDATE" if lock else ""),
            (grant.tenant_id, operation_id),
        ).fetchone()
        if row is None:
            raise BusinessReview("proposal_missing")
        proposal = Proposal.model_validate_json(json.dumps(row["document"]))
        if (
            proposal.command.tenant_id != grant.tenant_id
            or proposal.command.business_operation_id != operation_id
            or row["command_sha256"] != digest(proposal.command.canonical_json())
        ):
            raise BusinessReview("proposal_integrity")
        grant.require_any(proposal.command.resource_id, capability)
        # Idempotent/status paths must check the stored resource kind too. Equal
        # text IDs in the wrong grant collection never authorize a saved action.
        OperationStore._record(connection, grant, proposal.command.resource_id, capability)
        if proposal.command.target_account_id is not None:
            grant.require(
                grant.tenant_id, "account", proposal.command.target_account_id, capability
            )
        return proposal

    @staticmethod
    def _receipt(connection: Connection[Any], tenant: str, operation: str) -> Receipt | None:
        row = connection.execute(
            "SELECT document FROM revenue.ledger WHERE tenant_id=%s AND operation_id=%s",
            (tenant, operation),
        ).fetchone()
        if row is None:
            return None
        value = Receipt.model_validate_json(json.dumps(row["document"]))
        if value.command.tenant_id != tenant or value.command.business_operation_id != operation:
            raise BusinessReview("ledger_integrity")
        return value

    @staticmethod
    def _lock(connection: Connection[Any], tenant: str, operation: str) -> None:
        key = int.from_bytes(
            hashlib.sha256(json.dumps([tenant, operation]).encode()).digest()[:8],
            "big",
            signed=True,
        )
        connection.execute("SELECT pg_advisory_xact_lock(%s)", (key,))

    def _change(
        self,
        connection: Connection[Any],
        grant: RevenueGrant,
        command: ChangeCommand,
        capability: str,
    ) -> tuple[RevenueRecord, RevenueRecord, RevenueRecord | None]:
        original = None
        if command.kind == "compensate":
            original = self._receipt(
                connection, grant.tenant_id, command.original_operation_id or ""
            )
            if (
                original is None
                or original.command.kind == "compensate"
                or original.command.resource_id != command.resource_id
            ):
                raise BusinessReview("original_effect_missing")
            prior = connection.execute(
                "SELECT operation_id FROM revenue.ledger WHERE tenant_id=%s AND "
                "original_operation_id=%s",
                (grant.tenant_id, command.original_operation_id),
            ).fetchone()
            if prior is not None:
                raise BusinessReview("already_compensated")
        target_id = (
            command.target_account_id
            if original is None
            else (original.target.resource_id if original.target else None)
        )
        # Deterministic row order for two-account operations avoids opposing-merge deadlocks.
        for resource in sorted({command.resource_id, *([target_id] if target_id else [])}):
            self._record(connection, grant, resource, capability, lock=True)
        before = self._record(connection, grant, command.resource_id, capability)
        if before.version != command.expected_version:
            raise BusinessReview("stale_record")
        target = self._record(connection, grant, target_id, capability) if target_id else None
        fields = before.model_dump()
        if command.kind == "invoice_correct":
            if (
                before.kind != "invoice"
                or before.billing_input is None
                or before.amount_minor is None
            ):
                raise BusinessReview("billing_facts_missing")
            source = before.billing_input.model_dump()
            source["invoice"] = Invoice(amount_minor=before.amount_minor).model_dump()
            result = reconcile(BillingInput.model_validate(source))
            if (
                result.disposition == "review"
                or result.should_be_minor is None
                or result.should_be_minor != command.invoice_amount_minor
            ):
                raise BusinessReview("correction_not_supported_by_facts")
            if not result.delta_minor:
                raise BusinessReview("no_change")
            if abs(result.delta_minor) > 10000:
                raise BusinessReview("correction_cap_exceeded")
            fields["amount_minor"] = result.should_be_minor
        elif command.kind == "account_merge":
            if (
                before.kind != "account"
                or target is None
                or target.kind != "account"
                or before.resource_id == target.resource_id
                or before.alias_to is not None
                or target.alias_to is not None
            ):
                raise BusinessReview("invalid_account_merge")
            if target.version != command.expected_target_version:
                raise BusinessReview("stale_target")
            fields["alias_to"] = target.resource_id
        elif command.kind == "crm_trim":
            if before.kind != "account" or before.alias_to is not None:
                raise BusinessReview("invalid_crm_hygiene")
            fields["note"] = before.note.strip()
            if fields["note"] == before.note:
                raise BusinessReview("no_change")
        else:
            assert original is not None
            if before != original.after or (
                original.target is not None and target != original.target
            ):
                raise BusinessReview("intervening_change")
            fields = original.before.model_dump()
        fields["version"] = before.version + 1
        return before, RevenueRecord.model_validate(fields), target

    def propose(
        self, grant: RevenueGrant, command: ChangeCommand, *, ttl_seconds: int = 86400
    ) -> Proposal:
        grant = self._grant(grant)
        command = ChangeCommand.model_validate_json(command.canonical_json())
        if command.tenant_id != grant.tenant_id:
            raise PermissionError("Revenue tenant denied")
        grant.require_any(command.resource_id, "propose")
        if command.kind == "crm_trim":
            raise BusinessReview("automatic_hygiene_uses_trim")
        if (
            isinstance(ttl_seconds, bool)
            or not isinstance(ttl_seconds, int)
            or not 1 <= ttl_seconds <= 86400
        ):
            raise ValueError("proposal TTL must be 1..86400 seconds")
        with self._connection() as c, c.transaction():
            self._lock(c, grant.tenant_id, command.business_operation_id)
            row = c.execute(
                "SELECT operation_id FROM revenue.proposals WHERE tenant_id=%s AND operation_id=%s",
                (grant.tenant_id, command.business_operation_id),
            ).fetchone()
            if row is not None:
                prior = self._proposal(c, grant, command.business_operation_id, "propose")
                if prior.command != command or prior.proposer_id != grant.actor_id:
                    raise BusinessReview("operation_key_conflict")
                return prior
            if self._receipt(c, grant.tenant_id, command.business_operation_id) is not None:
                raise BusinessReview("operation_key_conflict")
            before, after, _ = self._change(c, grant, command, "propose")
            now = self._now()
            proposal = Proposal(
                command=command,
                adjustment_minor=(after.amount_minor or 0) - (before.amount_minor or 0),
                proposer_id=grant.actor_id,
                created_at=now,
                expires_at=now + timedelta(seconds=ttl_seconds),
            )
            c.execute(
                "INSERT INTO revenue.proposals VALUES(%s,%s,%s,%s)",
                (
                    grant.tenant_id,
                    command.business_operation_id,
                    digest(command.canonical_json()),
                    Jsonb(proposal.model_dump(mode="json")),
                ),
            )
            return proposal

    def review(self, grant: RevenueGrant, operation_id: str, *, approve: bool) -> Proposal:
        grant = self._grant(grant)
        if type(approve) is not bool:
            raise ValueError("review decision must be boolean")
        with self._connection() as c, c.transaction():
            self._lock(c, grant.tenant_id, operation_id)
            proposal = self._proposal(c, grant, operation_id, "review", lock=True)
            if proposal.proposer_id == grant.actor_id:
                raise PermissionError("separate reviewer required")
            status = "approved" if approve else "rejected"
            if proposal.status != "pending":
                if proposal.status == status and proposal.reviewer_id == grant.actor_id:
                    return proposal
                raise BusinessReview("review_already_decided")
            if self._now() >= proposal.expires_at:
                raise BusinessReview("proposal_expired")
            self._record(c, grant, proposal.command.resource_id, "review")
            if approve:
                self._change(c, grant, proposal.command, "review")
            updated = proposal.model_copy(update={"status": status, "reviewer_id": grant.actor_id})
            c.execute(
                "UPDATE revenue.proposals SET document=%s WHERE tenant_id=%s AND operation_id=%s",
                (Jsonb(updated.model_dump(mode="json")), grant.tenant_id, operation_id),
            )
            return updated

    def _commit(
        self,
        c: Connection[Any],
        grant: RevenueGrant,
        command: ChangeCommand,
        capability: str,
        run_id: str,
        reviewer: str | None,
        fault: FaultHook | None,
    ) -> Receipt:
        before, after, target = self._change(c, grant, command, capability)
        receipt = Receipt(
            command=command,
            ledger_id=digest(json.dumps([grant.tenant_id, command.business_operation_id])),
            before=before,
            after=after,
            target=target,
            original_run_id=run_id,
            actor_id=grant.actor_id,
            reviewer_id=reviewer,
            committed_at=self._now(),
        )
        c.execute(
            "UPDATE revenue.records SET version=%s,document=%s WHERE "
            "tenant_id=%s AND resource_id=%s",
            (
                after.version,
                Jsonb(after.model_dump(mode="json")),
                grant.tenant_id,
                command.resource_id,
            ),
        )
        c.execute(
            "INSERT INTO revenue.ledger VALUES(%s,%s,%s,%s,%s)",
            (
                grant.tenant_id,
                command.business_operation_id,
                receipt.ledger_id,
                command.original_operation_id,
                Jsonb(receipt.model_dump(mode="json")),
            ),
        )
        if fault:
            fault("before_commit")
        return receipt

    def apply(
        self, grant: RevenueGrant, operation_id: str, *, run_id: str, fault: FaultHook | None = None
    ) -> Receipt:
        grant = self._grant(grant)
        with self._connection() as c, c.transaction():
            self._lock(c, grant.tenant_id, operation_id)
            proposal = self._proposal(c, grant, operation_id, "apply", lock=True)
            existing = self._receipt(c, grant.tenant_id, operation_id)
            if existing is not None:
                grant.require(
                    existing.before.tenant_id,
                    existing.before.kind,
                    existing.before.resource_id,
                    "apply",
                )
                if existing.target is not None:
                    grant.require(grant.tenant_id, "account", existing.target.resource_id, "apply")
                if existing.command != proposal.command:
                    raise BusinessReview("operation_key_conflict")
                return existing
            if proposal.status != "approved":
                raise BusinessReview("approval_required")
            if proposal.reviewer_id in (None, grant.actor_id, proposal.proposer_id):
                raise PermissionError("separate reviewer required")
            if self._now() >= proposal.expires_at:
                raise BusinessReview("proposal_expired")
            receipt = self._commit(
                c, grant, proposal.command, "apply", run_id, proposal.reviewer_id, fault
            )
        if fault:
            fault("after_commit")
        return receipt

    def trim(
        self,
        grant: RevenueGrant,
        command: ChangeCommand,
        *,
        run_id: str,
        fault: FaultHook | None = None,
    ) -> Receipt:
        grant = self._grant(grant)
        command = ChangeCommand.model_validate_json(command.canonical_json())
        if command.tenant_id != grant.tenant_id:
            raise PermissionError("Revenue tenant denied")
        grant.require(grant.tenant_id, "account", command.resource_id, "crm_trim")
        if command.kind != "crm_trim":
            raise BusinessReview("automatic_action_forbidden")
        with self._connection() as c, c.transaction():
            self._lock(c, grant.tenant_id, command.business_operation_id)
            existing = self._receipt(c, grant.tenant_id, command.business_operation_id)
            if existing is not None:
                if existing.command != command:
                    raise BusinessReview("operation_key_conflict")
                return existing
            if c.execute(
                "SELECT operation_id FROM revenue.proposals WHERE tenant_id=%s AND operation_id=%s",
                (grant.tenant_id, command.business_operation_id),
            ).fetchone():
                raise BusinessReview("operation_key_conflict")
            receipt = self._commit(c, grant, command, "crm_trim", run_id, None, fault)
        if fault:
            fault("after_commit")
        return receipt

    def records(self, grant: RevenueGrant) -> tuple[RevenueRecord, ...]:
        grant = self._grant(grant)
        if "read" not in grant.capabilities:
            raise PermissionError("Revenue capability denied")
        with self._connection() as c:
            return self._records(c, grant)

    def _records(self, c: Connection[Any], grant: RevenueGrant) -> tuple[RevenueRecord, ...]:
        rows = c.execute(
            "SELECT resource_id FROM revenue.records WHERE tenant_id=%s AND "
            "resource_id=ANY(%s) ORDER BY resource_id",
            (grant.tenant_id, list((*grant.invoice_ids, *grant.account_ids))),
        ).fetchall()
        values = []
        for row in rows:
            try:
                values.append(self._record(c, grant, row["resource_id"], "read"))
            except PermissionError:
                continue
        return tuple(values)

    def proposals(self, grant: RevenueGrant) -> tuple[Proposal, ...]:
        grant = self._grant(grant)
        if "read" not in grant.capabilities:
            raise PermissionError("Revenue capability denied")
        with self._connection() as c:
            return self._proposals(c, grant)

    def _proposals(self, c: Connection[Any], grant: RevenueGrant) -> tuple[Proposal, ...]:
        rows = c.execute(
            "SELECT operation_id FROM revenue.proposals WHERE tenant_id=%s ORDER BY operation_id",
            (grant.tenant_id,),
        ).fetchall()
        values = []
        for row in rows:
            try:
                value = self._proposal(c, grant, row["operation_id"], "read")
                self._record(c, grant, value.command.resource_id, "read")
                values.append(value)
            except PermissionError:
                continue
        return tuple(values)

    def ledger(self, grant: RevenueGrant) -> tuple[Receipt, ...]:
        grant = self._grant(grant)
        if "read" not in grant.capabilities:
            raise PermissionError("Revenue capability denied")
        with self._connection() as c:
            return self._ledger(c, grant)

    def _ledger(self, c: Connection[Any], grant: RevenueGrant) -> tuple[Receipt, ...]:
        rows = c.execute(
            "SELECT operation_id FROM revenue.ledger WHERE tenant_id=%s ORDER BY operation_id",
            (grant.tenant_id,),
        ).fetchall()
        values = []
        for row in rows:
            value = self._receipt(c, grant.tenant_id, row["operation_id"])
            assert value is not None
            try:
                grant.require(grant.tenant_id, value.before.kind, value.before.resource_id, "read")
                if value.target is not None:
                    grant.require(grant.tenant_id, "account", value.target.resource_id, "read")
                values.append(value)
            except PermissionError:
                continue
        return tuple(values)

    def snapshot(
        self, grant: RevenueGrant
    ) -> tuple[tuple[RevenueRecord, ...], tuple[Proposal, ...], tuple[Receipt, ...]]:
        """One committed MVCC view for ledger-reconciled operator projections."""
        grant = self._grant(grant)
        if "read" not in grant.capabilities:
            raise PermissionError("Revenue capability denied")
        with self._connection() as c, c.transaction():
            c.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            return self._records(c, grant), self._proposals(c, grant), self._ledger(c, grant)

    def sweep(self, grant: RevenueGrant) -> tuple[Proposal, ...]:
        grant = self._grant(grant)
        if "read" not in grant.capabilities:
            raise PermissionError("Revenue capability denied")
        changed = []
        for observed in self.proposals(grant):
            operation = observed.command.business_operation_id
            with self._connection() as c, c.transaction():
                self._lock(c, grant.tenant_id, operation)
                value = self._proposal(c, grant, operation, "read", lock=True)
                if (
                    value.status in ("pending", "approved")
                    and self._now() >= value.expires_at
                    and self._receipt(c, grant.tenant_id, operation) is None
                ):
                    expired = value.model_copy(update={"status": "expired"})
                    c.execute(
                        "UPDATE revenue.proposals SET document=%s WHERE tenant_id=%s AND "
                        "operation_id=%s",
                        (Jsonb(expired.model_dump(mode="json")), grant.tenant_id, operation),
                    )
                    changed.append(expired)
        return tuple(changed)
