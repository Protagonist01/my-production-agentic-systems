"""Thin Inngest opaque-ID fanout/waits; payloads never authorize SQL writes."""

import asyncio
import hashlib
import uuid
from collections.abc import Callable
from datetime import timedelta
from typing import Any

import inngest
from agent_harness.contracts import Contract

from supply_chain.action_contracts import POLICY, Grant, Id
from supply_chain.workflow import SupplyWorkflow


class IncidentWake(Contract):
    tenant_id: Id
    actor_id: Id
    event_id: Id


class ShipmentWake(IncidentWake):
    shipment_id: Id


def event_for(wake: IncidentWake, name: str = "supply/incident.requested") -> inngest.Event:
    allowed = {
        "supply/incident.requested",
        "supply/shipment.requested",
        "supply/shipment.reviewed",
        "supply/shipment.confirmed",
    }
    if name not in allowed or (
        name != "supply/incident.requested" and not isinstance(wake, ShipmentWake)
    ):
        raise ValueError("declared event shape required")
    # Requested events are deduplicated. Review/confirmation wakeups may recur
    # after supersession; their event IDs are advisory, SQL always rereads state.
    key = hashlib.sha256((name + "\x00" + wake.canonical_json()).encode()).hexdigest()
    return inngest.Event(
        name=name,
        id=key if name.endswith("requested") else uuid.uuid4().hex,
        data=wake.model_dump(mode="json", exclude={"schema_version"}),
    )


class EventHandlers:
    def __init__(
        self,
        workflow: SupplyWorkflow,
        resolve: Callable[[str, str], Grant],
        incidents: Callable[[], tuple[IncidentWake, ...]],
    ) -> None:
        self.workflow, self.resolve, self.incidents = workflow, resolve, incidents

    def grant(self, wake: IncidentWake) -> Grant:
        grant = Grant.model_validate_json(
            self.resolve(wake.tenant_id, wake.actor_id).canonical_json()
        )
        if grant.tenant_id != wake.tenant_id or grant.actor_id != wake.actor_id:
            raise PermissionError("configured operator required")
        if not {"read", "propose", "apply"} <= set(grant.capabilities):
            raise PermissionError("configured operator capabilities required")
        return grant

    def fanout(self, wake: IncidentWake) -> tuple[ShipmentWake, ...]:
        grant = self.grant(wake)
        grant.require_event(wake.event_id)
        if len(grant.shipment_ids) > 100 or len(set(grant.shipment_ids)) != len(grant.shipment_ids):
            raise ValueError("incident burst limited to 100 unique shipments")
        return tuple(
            ShipmentWake(
                tenant_id=wake.tenant_id,
                actor_id=wake.actor_id,
                event_id=wake.event_id,
                shipment_id=key,
            )
            for key in sorted(grant.shipment_ids)
        )

    def reconcile(self, wake: ShipmentWake) -> dict[str, str]:
        grant = self.grant(wake)
        grant.require(wake.tenant_id, wake.shipment_id, "read")
        scoped = grant.model_copy(update={"shipment_ids": (wake.shipment_id,)})
        result = self.workflow.run(scoped, wake.event_id, "event-" + wake.event_id[:80])
        return {"status": result.statuses[0].outcome}

    def wait_seconds(self, wake: ShipmentWake, status: str) -> int:
        grant = self.grant(wake)
        grant.require(wake.tenant_id, wake.shipment_id, "read")
        proposal = self.workflow.store.current(grant, wake.event_id, wake.shipment_id)
        if proposal is None:
            return 1
        snapshot = self.workflow.store.snapshot(grant, proposal.command)
        deadline = (
            snapshot.receipt.confirmation_deadline
            if status == "awaiting_confirmation" and snapshot.receipt
            else proposal.expires_at
        )
        return max(
            1, min(POLICY.wait_seconds, int((deadline - self.workflow.store.now()).total_seconds()))
        )

    def sweep(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        # Trusted registry handles lost/early event delivery and process restart.
        for incident in self.incidents():
            for wake in self.fanout(incident):
                status = self.reconcile(wake)["status"]
                counts[status] = counts.get(status, 0) + 1
        return counts


def build_functions(
    client: inngest.Inngest, handlers: EventHandlers
) -> list[inngest.Function[Any]]:
    @client.create_function(
        fn_id="supply-incident-fanout",
        retries=3,
        trigger=inngest.TriggerEvent(event="supply/incident.requested"),
    )
    async def incident(ctx: inngest.Context) -> dict[str, int]:
        wake = IncidentWake.model_validate(ctx.event.data)

        async def gather() -> list[dict[str, Any]]:
            values = await asyncio.to_thread(handlers.fanout, wake)
            return [item.model_dump(mode="json") for item in values]

        rows: list[dict[str, Any]] = await ctx.step.run("scoped-incident-shipments", gather)
        if rows:
            await ctx.step.send_event(
                "fanout-scoped-wakeups",
                [
                    event_for(ShipmentWake.model_validate(row), "supply/shipment.requested")
                    for row in rows
                ],
            )
        return {"shipments": len(rows)}

    @client.create_function(
        fn_id="supply-shipment-waits",
        retries=3,
        trigger=inngest.TriggerEvent(event="supply/shipment.requested"),
    )
    async def shipment(ctx: inngest.Context) -> dict[str, str]:
        wake = ShipmentWake.model_validate(ctx.event.data)

        async def reconcile() -> dict[str, str]:
            return await asyncio.to_thread(handlers.reconcile, wake)

        result: dict[str, str] = await ctx.step.run("assess-canonical-shipment", reconcile)
        # Two replans can create up to three approval waits. Every wait is bounded
        # by SQL expiry and its result is only a wakeup, never an approval grant.
        for attempt in range(POLICY.max_replans + 1):
            if result["status"] != "pending":
                break

            async def approval_timeout() -> int:
                return await asyncio.to_thread(handlers.wait_seconds, wake, "pending")

            seconds: int = await ctx.step.run(f"approval-deadline-{attempt}", approval_timeout)
            await ctx.step.wait_for_event(
                f"approval-wakeup-{attempt}",
                event="supply/shipment.reviewed",
                timeout=timedelta(seconds=seconds),
                if_exp=(
                    "event.data.tenant_id == async.data.tenant_id && "
                    "event.data.event_id == async.data.event_id && "
                    "event.data.shipment_id == async.data.shipment_id"
                ),
            )
            result = await ctx.step.run(f"reconcile-reviewed-{attempt}", reconcile)
        if result["status"] == "awaiting_confirmation":

            async def confirmation_timeout() -> int:
                return await asyncio.to_thread(handlers.wait_seconds, wake, "awaiting_confirmation")

            seconds = await ctx.step.run("confirmation-deadline", confirmation_timeout)
            await ctx.step.wait_for_event(
                "confirmation-wakeup",
                event="supply/shipment.confirmed",
                timeout=timedelta(seconds=seconds),
                if_exp=(
                    "event.data.tenant_id == async.data.tenant_id && "
                    "event.data.event_id == async.data.event_id && "
                    "event.data.shipment_id == async.data.shipment_id"
                ),
            )
            result = await ctx.step.run("reconcile-confirmed", reconcile)
        return result

    @client.create_function(
        fn_id="supply-canonical-sweep", retries=3, trigger=inngest.TriggerCron(cron="*/5 * * * *")
    )
    async def sweep(ctx: inngest.Context) -> dict[str, int]:
        async def reconcile_all() -> dict[str, int]:
            return await asyncio.to_thread(handlers.sweep)

        return await ctx.step.run("sweep-canonical-incidents", reconcile_all)

    return [incident, shipment, sweep]
