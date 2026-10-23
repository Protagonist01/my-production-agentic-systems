"""Role-scoped workbench, exact decisions and reconstructable in-app notices."""

import secrets
from typing import Any

from supply_chain.action_contracts import POLICY, Option, ReviewRequired, Snapshot, options
from supply_chain.console_contracts import Confirmation, Decision, Principal, Selection
from supply_chain.notices import NoticeStore, alert_state, make_notice
from supply_chain.operations import OperationStore
from supply_chain.workflow import SupplyWorkflow


class ConsoleService:
    def __init__(self, store: OperationStore, notices: NoticeStore) -> None:
        self.store, self.notices = store, notices

    def board(self, principal: Principal, event: str) -> dict[str, Any]:
        principal = Principal.model_validate_json(principal.canonical_json())
        portfolio = self.store.workbench(principal.grant(event), event)
        context = self.notices.context(principal, event)
        snapshots = {s.proposal.command.shipment_id: s for s in portfolio.snapshots}
        rows: list[dict[str, Any]] = []
        for fact in portfolio.shipments:
            snapshot = snapshots.get(fact.shipment_id)
            fresh = "current"
            choices: tuple[Option, ...] = ()
            try:
                choices = options(fact, portfolio.as_of)
            except ReviewRequired as error:
                fresh = str(error)
            state: str = snapshot.outcome if snapshot else "unassessed"
            if snapshot is None and fresh != "current":
                state = fresh
            if (
                snapshot is not None
                and snapshot.receipt is None
                and state in ("pending", "approved")
            ):
                command = snapshot.proposal.command
                if (
                    command.expected_budget_version != portfolio.budget_version
                    or command.expected_shipment_version != fact.version
                ):
                    state = (
                        "replan_limit" if portfolio.replans_used >= POLICY.max_replans else "stale"
                    )
            if snapshot is not None and snapshot.receipt is not None:
                self.notices.append(
                    make_notice(fact, event, "committed", snapshot, context, portfolio.as_of)
                )
            self.notices.append(make_notice(fact, event, state, snapshot, context, portfolio.as_of))
            rows.append(
                dict(
                    fact=fact.model_dump(mode="json"),
                    freshness=fresh,
                    state=state,
                    options=[o.model_dump(mode="json") for o in choices],
                    snapshot=snapshot.model_dump(mode="json") if snapshot else None,
                )
            )
        return dict(
            event_id=event,
            as_of=portfolio.as_of.isoformat(),
            label=context.label if context else event,
            context=context.model_dump(mode="json") if context else None,
            alert_state=alert_state(context, portfolio.as_of),
            budget=dict(
                cap_minor=POLICY.event_cap_minor,
                spent_minor=portfolio.spent_minor,
                remaining_minor=POLICY.event_cap_minor - portfolio.spent_minor,
                version=portfolio.budget_version,
                replans_used=portfolio.replans_used,
            ),
            shipments=rows,
            notices=[n.model_dump(mode="json") for n in self.notices.list(principal, event)],
        )

    def assess(self, principal: Principal, event: str) -> dict[str, Any]:
        if principal.role != "operator":
            raise PermissionError("operator required")
        SupplyWorkflow(self.store).run(
            principal.grant(event), event, "console-" + secrets.token_hex(12)
        )
        return self.board(principal, event)

    def selected(self, principal: Principal, value: Selection) -> Snapshot:
        grant = principal.grant(value.event_id)
        grant.require(grant.tenant_id, value.shipment_id, "read")
        proposal = self.store.current(grant, value.event_id, value.shipment_id)
        if proposal is None:
            raise LookupError("proposal unavailable")
        if value.payload_sha256 != proposal.payload_sha256:
            raise ReviewRequired("exact_payload_changed")
        return self.store.snapshot(grant, proposal.command)

    def review(self, principal: Principal, value: Decision) -> dict[str, Any]:
        if principal.role != "reviewer":
            raise PermissionError("reviewer required")
        snapshot = self.selected(principal, value)
        self.store.review(
            principal.grant(value.event_id),
            snapshot.proposal.command,
            value.payload_sha256,
            approve=value.approve,
        )
        return self.board(principal, value.event_id)

    def apply(self, principal: Principal, value: Selection) -> dict[str, Any]:
        if principal.role != "operator":
            raise PermissionError("operator required")
        snapshot = self.selected(principal, value)
        self.store.apply(
            principal.grant(value.event_id),
            snapshot.proposal.command,
            run_id="console-" + secrets.token_hex(12),
        )
        return self.board(principal, value.event_id)

    def confirm(self, principal: Principal, value: Confirmation) -> dict[str, Any]:
        if principal.role != "confirmer":
            raise PermissionError("SIM confirmer required")
        snapshot = self.selected(principal, value)
        self.store.confirm(
            principal.grant(value.event_id),
            snapshot.proposal.command,
            value.payload_sha256,
            success=value.success,
        )
        return self.board(principal, value.event_id)
