"""Bounded LangGraph assessment; SQL remains the owner of every durable decision."""

import json
from collections.abc import Callable
from datetime import datetime
from typing import Any, Protocol, TypedDict

from agent_harness.contracts import Contract
from langgraph.graph import END, START, StateGraph
from langsmith import tracing_context

from supply_chain.action_contracts import POLICY, Action, Command, Grant, ReviewRequired, Shipment
from supply_chain.operations import OperationStore
from supply_chain.simulator import allocate


class Planner(Protocol):
    def __call__(
        self, shipments: tuple[Shipment, ...], budget_minor: int, *, now: datetime
    ) -> dict[str, Action]: ...


class ActionStatus(Contract):
    shipment_id: str
    outcome: str
    operation_id: str | None = None


class WorkflowResult(Contract):
    event_id: str
    statuses: tuple[ActionStatus, ...]
    committed_operations: tuple[str, ...]
    spent_minor: int
    replans_used: int


class FlowState(TypedDict, total=False):
    actions: dict[str, Action]
    statuses: list[dict[str, Any]]
    result: dict[str, Any]


class SupplyWorkflow:
    def __init__(self, store: OperationStore, planner: Planner = allocate) -> None:
        self.store, self.planner = store, planner

    def run(
        self,
        grant: Grant,
        event_id: str,
        run_id: str,
        *,
        fault: Callable[[str], None] | None = None,
    ) -> WorkflowResult:
        grant = Grant.model_validate_json(grant.canonical_json())
        if len(grant.shipment_ids) > 12 or len(set(grant.shipment_ids)) != len(grant.shipment_ids):
            raise ValueError("workflow requires <=12 unique scoped shipments")

        def assess(state: FlowState) -> FlowState:
            budget, facts = self.store.portfolio(grant, event_id)
            committed = {r.command.shipment_id for r in self.store.receipts(grant, event_id)}
            pending_facts = tuple(f for f in facts if f.shipment_id not in committed)
            try:
                actions = self.planner(
                    pending_facts,
                    POLICY.event_cap_minor - budget["spent_minor"],
                    now=self.store.now(),
                )
                if set(actions) - {s.shipment_id for s in pending_facts}:
                    raise ValueError("planner returned unscoped shipment")
                if any(
                    action not in ("wait", "expedite", "reroute") for action in actions.values()
                ):
                    raise ValueError("planner returned unknown action")
            except (ValueError, TypeError):
                actions = {}
            return {"actions": actions}

        def act(state: FlowState) -> FlowState:
            statuses: list[ActionStatus] = []
            for shipment_id in sorted(grant.shipment_ids):
                # Each iteration either returns an existing canonical state, commits,
                # or spends one of the incident's two persisted supersession attempts.
                for attempt in range(POLICY.max_replans + 1):
                    previous = self.store.current(grant, event_id, shipment_id)
                    if previous is not None:
                        snapshot = self.store.snapshot(grant, previous.command)
                        if snapshot.receipt is not None or snapshot.outcome in (
                            "expired",
                            "rejected",
                        ):
                            statuses.append(
                                ActionStatus(
                                    shipment_id=shipment_id,
                                    outcome=snapshot.outcome,
                                    operation_id=previous.command.operation_id,
                                )
                            )
                            break
                    try:
                        budget, facts = self.store.portfolio(grant, event_id)
                        fact = next(s for s in facts if s.shipment_id == shipment_id)
                        if previous is not None and (
                            previous.command.expected_budget_version == budget["version"]
                            and previous.command.expected_shipment_version == fact.version
                        ):
                            proposal = previous
                        else:
                            # On stale retry, reassess the actual remaining budget/facts.
                            selected = (
                                state["actions"].get(shipment_id)
                                if attempt == 0
                                else (
                                    self.planner(
                                        (fact,),
                                        POLICY.event_cap_minor - budget["spent_minor"],
                                        now=self.store.now(),
                                    ).get(shipment_id)
                                )
                            )
                            if selected is None:
                                raise ReviewRequired("no_safe_plan")
                            command = Command(
                                tenant_id=grant.tenant_id,
                                event_id=event_id,
                                shipment_id=shipment_id,
                                expected_shipment_version=fact.version,
                                expected_budget_version=budget["version"],
                                action=selected,
                            )
                            proposal = self.store.propose(grant, command)
                        if proposal.status == "pending":
                            statuses.append(
                                ActionStatus(
                                    shipment_id=shipment_id,
                                    outcome="pending",
                                    operation_id=proposal.command.operation_id,
                                )
                            )
                            break
                        self.store.apply(grant, proposal.command, run_id=run_id, fault=fault)
                        snapshot = self.store.snapshot(grant, proposal.command)
                        statuses.append(
                            ActionStatus(
                                shipment_id=shipment_id,
                                outcome=snapshot.outcome,
                                operation_id=proposal.command.operation_id,
                            )
                        )
                        break
                    except ReviewRequired as error:
                        if str(error) == "stale_versions" and attempt < POLICY.max_replans:
                            continue
                        statuses.append(ActionStatus(shipment_id=shipment_id, outcome=str(error)))
                        break
                else:
                    statuses.append(ActionStatus(shipment_id=shipment_id, outcome="replan_limit"))
            budget, _ = self.store.portfolio(grant, event_id)
            result = WorkflowResult(
                event_id=event_id,
                statuses=tuple(statuses),
                committed_operations=tuple(
                    r.command.operation_id for r in self.store.receipts(grant, event_id)
                ),
                spent_minor=budget["spent_minor"],
                replans_used=budget["replans"],
            )
            return {"result": result.model_dump(mode="json")}

        graph = StateGraph(FlowState)
        graph.add_node("assess_public_facts", assess)
        graph.add_node("reconcile_canonical_actions", act)
        graph.add_edge(START, "assess_public_facts")
        graph.add_edge("assess_public_facts", "reconcile_canonical_actions")
        graph.add_edge("reconcile_canonical_actions", END)
        # No automatic external tracing of shipment facts or grants.
        with tracing_context(enabled=False):
            result = graph.compile().invoke({}, config={"recursion_limit": 6})
        return WorkflowResult.model_validate_json(json.dumps(result["result"]))
