"""Durable in-app notices from canonical evidence. No external delivery adapter."""

import hashlib
import json
from datetime import datetime, timedelta

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from supply_chain.action_contracts import Shipment, Snapshot
from supply_chain.console_contracts import IncidentContext, Notice, Principal
from supply_chain.operations import ConnectionFactory


def alert_state(context: IncidentContext | None, now: datetime) -> str:
    if context is None or context.alert is None:
        return "none"
    alert = context.alert
    if now < alert.captured_at or now < alert.sent or now < alert.effective:
        return "not_yet_available"
    if (
        now - alert.captured_at > timedelta(seconds=context.max_alert_age_seconds)
        or now >= alert.expires
        or (alert.ends is not None and now >= alert.ends)
    ):
        return "stale"
    if alert.status != "Actual" or alert.message_type not in ("Alert", "Update"):
        return "non_actual"
    return "current_snapshot"


def message(shipment: Shipment, state: str, snapshot: Snapshot | None) -> str:
    prefix = f"Shipment {shipment.shipment_id}: "
    if state == "committed" and snapshot is not None and snapshot.receipt is not None:
        receipt = snapshot.receipt
        money = f"{receipt.cost_minor // 100}.{receipt.cost_minor % 100:02d} SIM"
        return prefix + (
            f"SIM {receipt.command.action} command committed at {receipt.committed_at.isoformat()} "
            f"for {money}. This receipt does not establish shipment delivery."
        )
    bodies = {
        "pending": "SIM action proposed and awaiting separate review. No action receipt exists.",
        "approved": "Exact SIM proposal approved. No action receipt exists yet.",
        "rejected": "SIM proposal rejected. No action receipt exists.",
        "expired": "SIM proposal expired. No action receipt exists.",
        "stale": (
            "Proposal facts or budget changed. New exact approval is required before execution."
        ),
        "replan_limit": "The incident replan limit is reached. This proposal remains unresolved.",
        "awaiting_confirmation": (
            "SIM command committed; confirmation is pending. No delivery outcome is recorded."
        ),
        "confirmed": "SIM action confirmation recorded. No shipment delivery outcome is recorded.",
        "confirmation_failed": (
            "SIM confirmation failed; the committed debit is retained. "
            "No delivery outcome is recorded."
        ),
        "confirmation_timeout": (
            "SIM confirmation timed out; the committed debit is "
            "retained. No delivery outcome is recorded."
        ),
        "missing_facts": "Required shipment facts are missing. Execution is blocked.",
        "conflicting_facts": "Shipment alert facts conflict. Execution is blocked.",
        "stale_or_future_facts": (
            "Shipment observation is stale or not yet available. Execution is blocked."
        ),
    }
    if state == "unassessed":
        return prefix + (
            f"Observation recorded at {shipment.observed_at.isoformat()}; "
            f"estimated delay {shipment.estimated_delay_hours} hours. No SIM action is proposed."
        )
    if state not in bodies:
        raise ValueError("unknown notice state")
    return prefix + bodies[state]


def make_notice(
    shipment: Shipment,
    event: str,
    state: str,
    snapshot: Snapshot | None,
    context: IncidentContext | None,
    now: datetime,
) -> Notice:
    body = message(shipment, state, snapshot)
    alert_status = alert_state(context, now)
    if context is not None and context.alert is not None:
        kind = "Invented" if context.source_kind == "invented" else "Independent recorded"
        # This is recorded context, never a weather-shipment causal attribution.
        body += (
            f" {kind} alert context: {context.alert.event[:160]}; snapshot status {alert_status}. "
            "A weather cause for this shipment has not been verified."
        )
    evidence = dict(
        version="supply-notice-v1",
        tenant=shipment.tenant_id,
        event=event,
        shipment=shipment.shipment_id,
        state=state,
        body=body,
        facts=shipment.model_dump(mode="json") if state != "committed" else None,
        payload=snapshot.proposal.payload_sha256 if snapshot else None,
        receipt=snapshot.receipt.model_dump(mode="json") if snapshot and snapshot.receipt else None,
        alert=context.model_dump(mode="json") if context else None,
        alert_status=alert_status,
    )
    identity = hashlib.sha256(
        json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return Notice(
        notice_id=identity,
        tenant_id=shipment.tenant_id,
        event_id=event,
        shipment_id=shipment.shipment_id,
        state=state,
        body=body,
        created_at=now,
    )


class NoticeStore:
    def __init__(self, connect: ConnectionFactory) -> None:
        self.connect = connect

    def context(self, principal: Principal, event: str) -> IncidentContext | None:
        principal.grant(event)
        with self.connect() as connection:
            row = connection.execute(
                "SELECT document FROM supply_app.contexts WHERE tenant_id=%s AND event_id=%s",
                (principal.tenant_id, event),
            ).fetchone()
        if row is None:
            return None
        context = IncidentContext.model_validate_json(json.dumps(row[0]))
        if context.tenant_id != principal.tenant_id or context.event_id != event:
            raise PermissionError("incident context denied")
        return context

    def append(self, notice: Notice) -> None:
        notice = Notice.model_validate_json(notice.canonical_json())
        if notice.read:
            raise ValueError("new notice cannot contain caller read state")
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO supply_app.notices VALUES(%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                (
                    notice.notice_id,
                    notice.tenant_id,
                    notice.event_id,
                    notice.shipment_id,
                    Jsonb(notice.model_dump(mode="json")),
                ),
            )

    def list(self, principal: Principal, event: str) -> tuple[Notice, ...]:
        grant = principal.grant(event)
        with self.connect() as connection:
            connection.row_factory = dict_row
            rows = connection.execute(
                "SELECT n.document,(r.username IS NOT NULL) AS read FROM supply_app.notices n "
                "LEFT JOIN supply_app.notice_reads r ON r.notice_id=n.notice_id AND r.username=%s "
                "WHERE n.tenant_id=%s AND n.event_id=%s AND n.shipment_id=ANY(%s) "
                "ORDER BY n.document->>'created_at' DESC,n.notice_id LIMIT 100",
                (principal.username, grant.tenant_id, event, list(grant.shipment_ids)),
            ).fetchall()
        return tuple(
            Notice.model_validate_json(json.dumps(row["document"])).model_copy(
                update={"read": row["read"]}
            )
            for row in rows
        )

    def acknowledge(self, principal: Principal, notice_id: str) -> None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT document FROM supply_app.notices WHERE notice_id=%s AND tenant_id=%s",
                (notice_id, principal.tenant_id),
            ).fetchone()
            if row is None:
                raise PermissionError("notice unavailable")
            notice = Notice.model_validate_json(json.dumps(row[0]))
            grant = principal.grant(notice.event_id)
            grant.require(notice.tenant_id, notice.shipment_id, "read")
            connection.execute(
                "INSERT INTO supply_app.notice_reads VALUES(%s,%s) ON CONFLICT DO NOTHING",
                (principal.username, notice_id),
            )
