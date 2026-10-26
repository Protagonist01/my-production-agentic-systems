"""S6 paired hidden-world reports with fixed missing-trial and sensitivity accounting."""

import json
from collections import Counter
from dataclasses import asdict
from datetime import datetime
from typing import Annotated, Literal

from agent_harness.contracts import Contract, NonEmpty
from agent_harness.evaluation_population import validate_matrix
from agent_harness.release_contracts import Sha256, pin, sha256
from pydantic import Field

from supply_chain.action_contracts import POLICY, Action, ReviewRequired, options
from supply_chain.simulator import (
    FAMILIES,
    NOW,
    Scenario,
    allocate,
    do_nothing,
    realized_cost,
    rules,
)


class SimulationPlan(Contract):
    version: Literal["supply-release-report-v1"] = "supply-release-report-v1"
    candidate_sha256: Sha256
    worlds_sha256: Sha256
    scenario_ids: tuple[NonEmpty, ...]
    trial_ids: tuple[NonEmpty, ...]
    sensitivities: tuple[Annotated[int, Field(ge=25, le=400)], ...] = (50, 100, 200)
    origin: Literal["mock", "provider", "deterministic"]


class ActionObservation(Contract):
    scenario_id: NonEmpty
    trial_id: NonEmpty
    actions: dict[NonEmpty, Action] | None = None
    failure_code: NonEmpty | None = None


class ObservationInventory(Contract):
    observations: tuple[ActionObservation, ...]


def world_pin(scenarios: tuple[Scenario, ...]) -> str:
    def encode(value: object) -> object:
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, Contract):
            return value.model_dump(mode="json")
        raise ValueError("unexpected world serialization")

    return sha256(
        json.dumps(
            [asdict(s) for s in scenarios], sort_keys=True, separators=(",", ":"), default=encode
        ).encode()
    )


def simulation_report(
    plan: SimulationPlan,
    scenarios: tuple[Scenario, ...],
    observations: tuple[ActionObservation, ...],
) -> dict[str, object]:
    plan = SimulationPlan.model_validate_json(plan.canonical_json())
    observations = tuple(
        ActionObservation.model_validate_json(o.canonical_json()) for o in observations
    )
    if (
        world_pin(scenarios) != plan.worlds_sha256
        or tuple(s.scenario_id for s in scenarios) != plan.scenario_ids
        or not plan.sensitivities
        or len(set(plan.sensitivities)) != len(plan.sensitivities)
    ):
        raise ValueError("frozen world/sensitivity inventory differs")
    validate_matrix(
        plan.scenario_ids, plan.trial_ids, tuple((o.scenario_id, o.trial_id) for o in observations)
    )
    splits: dict[str, str] = {}
    for scenario in scenarios:
        if scenario.family not in FAMILIES or scenario.split not in ("development", "holdout"):
            raise ValueError("unknown world family/split")
        if not scenario.observed or len({s.shipment_id for s in scenario.observed}) != len(
            scenario.observed
        ):
            raise ValueError("nonempty unique world shipments required")
        if any(len(target.remaining_hours) != 3 for target in scenario.hidden):
            raise ValueError("three hidden action outcomes required")
        for fact in scenario.observed:
            if fact.shipment_id in splits and splits[fact.shipment_id] != scenario.split:
                raise ValueError("shipment crosses world splits")
            splits[fact.shipment_id] = scenario.split
        if any(
            type(h) is not int or h < 0
            for target in scenario.hidden
            for h in target.remaining_hours
        ):
            raise ValueError("hidden realized hours must be nonnegative integers")
    lookup = {(o.scenario_id, o.trial_id): o for o in observations}

    def measure(selected: tuple[Scenario, ...], sensitivity: int) -> dict[str, object]:
        counts: Counter[str] = Counter()
        comparisons: dict[str, Counter[str]] = {
            name: Counter() for name in ("do_nothing", "rules", "estimate_solver")
        }
        for scenario in selected:
            public = scenario.agent_input()
            baselines = {
                "do_nothing": do_nothing(public),
                "rules": rules(public),
                "estimate_solver": allocate(public),
            }
            targets = {
                name: realized_cost(scenario, actions, sensitivity=sensitivity)
                for name, actions in baselines.items()
            }
            all_pass = True
            for trial in plan.trial_ids:
                counts["scheduled"] += 1
                counts["scheduled_shipments"] += len(public)
                observation = lookup.get((scenario.scenario_id, trial))
                actions = observation.actions if observation else None
                counts["missing"] += actions is None
                failed = bool(observation and observation.failure_code)
                counts["failed"] += failed
                if actions is None:
                    counts["unresolved_trials"] += 1
                    counts["unresolved_shipments"] += len(public)
                    all_pass = False
                    continue
                measured = realized_cost(scenario, actions, sensitivity=sensitivity)
                counts["observed"] += 1
                counts["unsafe_events"] += measured["unsafe"]
                unresolved_ids = set()
                for shipment in public:
                    try:
                        choices = {o.action for o in options(shipment, NOW)}
                    except ReviewRequired:
                        choices = set()
                    if failed or actions.get(shipment.shipment_id) not in choices:
                        unresolved_ids.add(shipment.shipment_id)
                unresolved = len(unresolved_ids)
                counts["unresolved_shipments"] += unresolved
                complete = not failed and not measured["unsafe"] and not unresolved
                counts["completed"] += complete
                counts["unresolved_trials"] += not complete
                all_pass &= complete
                # Both sides of every cost comparison have identical observed trial scope.
                for name, baseline in targets.items():
                    comparisons[name]["paired_observed"] += 1
                    comparisons[name]["candidate_total_minor"] += measured["total_minor"]
                    comparisons[name]["baseline_total_minor"] += baseline["total_minor"]
                    comparisons[name]["difference_minor"] += (
                        measured["total_minor"] - baseline["total_minor"]
                    )
                    comparisons[name]["baseline_unsafe_events"] += baseline["unsafe"]
                    comparisons[name]["baseline_unresolved_shipments"] += baseline["unresolved"]
            counts["all_trials_completed"] += all_pass
        keys = (
            "scheduled",
            "scheduled_shipments",
            "missing",
            "failed",
            "observed",
            "unsafe_events",
            "unresolved_trials",
            "unresolved_shipments",
            "completed",
            "all_trials_completed",
        )
        return dict(
            scenarios=len(selected),
            **{k: counts[k] for k in keys},
            comparisons={k: dict(v) for k, v in comparisons.items()},
        )

    return dict(
        version=plan.version,
        plan_sha256=pin(plan),
        candidate_sha256=plan.candidate_sha256,
        observations_sha256=pin(ObservationInventory(observations=observations)),
        origin=plan.origin,
        unit="SIM",
        policy_version=POLICY.policy_version,
        sensitivities={
            str(sensitivity): dict(
                **{"all": measure(scenarios, sensitivity)},
                by_split={
                    s: measure(tuple(w for w in scenarios if w.split == s), sensitivity)
                    for s in sorted({w.split for w in scenarios})
                },
                by_family={
                    s: measure(tuple(w for w in scenarios if w.family == s), sensitivity)
                    for s in sorted({w.family for w in scenarios})
                },
                by_outcome_model={
                    s: measure(tuple(w for w in scenarios if w.outcome_model == s), sensitivity)
                    for s in sorted({w.outcome_model for w in scenarios})
                },
            )
            for sensitivity in plan.sensitivities
        },
        business_state_verified=False,
        release_allowed=False,
        limitations=(
            "Constructed outcome equations and SIM costs; no real freight savings or causal/"
            "model-quality claim. Action maps do not establish authorization, ledger, duplicate, "
            "recovery or provider freshness evidence."
        ),
    )
