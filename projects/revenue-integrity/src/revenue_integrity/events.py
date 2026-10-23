"""Thin Inngest wakeups; Postgres alone owns approval/expiry/effect state.

Function outputs are bounded aggregate statuses. No note, password, invoice facts
or source contract text is sent to Inngest. SDK event deduplication is advisory;
the permanent Revenue operation key enforces effect idempotency.
"""

import asyncio
import hashlib
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import inngest

from revenue_integrity.console_contracts import Principal, Wake
from revenue_integrity.console_service import Operations
from revenue_integrity.operation_contracts import BusinessReview


def event_for(wake: Wake, *, reviewed: bool = False) -> inngest.Event:
    name = "revenue/proposal.reviewed" if reviewed else "revenue/proposal.requested"
    key = hashlib.sha256((name + "\x00" + wake.canonical_json()).encode()).hexdigest()
    return inngest.Event(
        name=name, id=key, data=wake.model_dump(mode="json", exclude={"schema_version"})
    )


class EventHandlers:
    def __init__(
        self,
        store: Operations,
        resolve: Callable[[str, str], Principal],
        operators: Callable[[], tuple[Principal, ...]],
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.store, self.resolve, self.operators, self.clock = store, resolve, operators, clock

    def snapshot(self, wake: Wake) -> dict[str, Any]:
        principal = self.resolve(wake.tenant_id, wake.actor_id)
        if (
            principal.tenant_id != wake.tenant_id
            or principal.actor_id != wake.actor_id
            or principal.role != "operator"
        ):
            raise PermissionError("configured operator required")
        proposals = [
            p
            for p in self.store.proposals(principal.grant())
            if p.command.business_operation_id == wake.operation_id
        ]
        if len(proposals) != 1:
            raise LookupError("proposal unavailable")
        proposal = proposals[0]
        return {"status": proposal.status, "expires_at": proposal.expires_at.isoformat()}

    def reconcile(self, wake: Wake, run_id: str) -> dict[str, str]:
        principal = self.resolve(wake.tenant_id, wake.actor_id)
        state = self.snapshot(wake)
        if any(
            r.command.business_operation_id == wake.operation_id
            for r in self.store.ledger(principal.grant())
        ):
            return {"status": "already_applied"}
        self.store.sweep(principal.grant())
        state = self.snapshot(wake)
        if state["status"] != "approved":
            return {"status": str(state["status"])}
        try:
            self.store.apply(principal.grant(), wake.operation_id, run_id=run_id)
        except BusinessReview:
            return {"status": "stale_or_ineligible"}
        return {"status": "applied"}

    def sweep(self) -> dict[str, int]:
        counts = {"expired": 0, "applied": 0, "unresolved": 0}
        for principal in self.operators():
            if principal.role != "operator":
                raise PermissionError("configured operator required")
            grant = principal.grant()
            counts["expired"] += len(self.store.sweep(grant))
            applied = {r.command.business_operation_id for r in self.store.ledger(grant)}
            for proposal in self.store.proposals(grant):
                if (
                    proposal.command.business_operation_id in applied
                    or proposal.status != "approved"
                ):
                    continue
                wake = Wake(
                    tenant_id=principal.tenant_id,
                    actor_id=principal.actor_id,
                    operation_id=proposal.command.business_operation_id,
                )
                result = self.reconcile(wake, "sweep-" + proposal.command.business_operation_id)
                counts["applied" if result["status"] == "applied" else "unresolved"] += 1
        return counts


def build_functions(
    client: inngest.Inngest, handlers: EventHandlers
) -> list[inngest.Function[Any]]:
    @client.create_function(
        fn_id="revenue-review-wakeup",
        trigger=inngest.TriggerEvent(event="revenue/proposal.requested"),
        retries=3,
        idempotency="event.data.tenant_id + ':' + event.data.operation_id",
    )
    async def review_wait(ctx: inngest.Context) -> dict[str, str]:
        wake = Wake.model_validate(ctx.event.data)

        async def read() -> dict[str, Any]:
            return await asyncio.to_thread(handlers.snapshot, wake)

        async def reconcile() -> dict[str, str]:
            return await asyncio.to_thread(handlers.reconcile, wake, "event-" + wake.operation_id)

        snapshot: dict[str, Any] = await ctx.step.run("read-proposal", read)
        if snapshot["status"] == "pending":
            remaining = max(
                1,
                min(
                    86400,
                    int(
                        (
                            datetime.fromisoformat(snapshot["expires_at"]) - handlers.clock()
                        ).total_seconds()
                    ),
                ),
            )
            await ctx.step.wait_for_event(
                "approval-wakeup",
                event="revenue/proposal.reviewed",
                timeout=timedelta(seconds=remaining),
                if_exp=(
                    "event.data.tenant_id == async.data.tenant_id && "
                    "event.data.operation_id == async.data.operation_id"
                ),
            )
        return await ctx.step.run("reconcile-canonical-proposal", reconcile)

    @client.create_function(
        fn_id="revenue-review-sweep", trigger=inngest.TriggerCron(cron="*/5 * * * *"), retries=3
    )
    async def sweep(ctx: inngest.Context) -> dict[str, int]:
        async def reconcile() -> dict[str, int]:
            return await asyncio.to_thread(handlers.sweep)

        return await ctx.step.run("sweep-canonical-proposals", reconcile)

    return [review_wait, sweep]
