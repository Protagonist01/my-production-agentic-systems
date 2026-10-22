"""Independent invented worlds. Only public shipments enter policy calls.

This is a simulator stress test, not a causal model fitted to DataCo or NWS.
"""

import hashlib
import json
import random
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from supply_chain.action_contracts import POLICY, Action, ReviewRequired, Shipment, options

Family = Literal[
    "routine",
    "regional_disruption",
    "scarce_capacity",
    "conflicting_alerts",
    "expired_alerts",
    "correlated_delays",
]
FAMILIES: tuple[Family, ...] = (
    "routine",
    "regional_disruption",
    "scarce_capacity",
    "conflicting_alerts",
    "expired_alerts",
    "correlated_delays",
)
NOW = datetime(2026, 10, 22, 12, tzinfo=UTC)


@dataclass(frozen=True)
class HiddenOutcome:
    shipment_id: str
    remaining_hours: tuple[int, int, int]  # wait, expedite, reroute


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    split: Literal["development", "holdout"]
    family: Family
    template: str
    seed: int
    outcome_model: str
    observed: tuple[Shipment, ...]
    hidden: tuple[HiddenOutcome, ...]

    def agent_input(self) -> tuple[Shipment, ...]:
        # Serialize/revalidate so no metadata/hidden target object can reach the policy.
        return tuple(Shipment.model_validate_json(s.canonical_json()) for s in self.observed)


def make_scenario(split: Literal["development", "holdout"], family: Family, seed: int) -> Scenario:
    if split not in ("development", "holdout") or family not in FAMILIES or seed < 0:
        raise ValueError("declared split/family/nonnegative seed required")
    # Separate hash namespaces prevent seed collisions between families/splits.
    digest = hashlib.sha256(f"supply-world-v1:{split}:{family}:{seed}".encode()).digest()
    rng = random.Random(int.from_bytes(digest, "big"))
    count = 3 if split == "development" else 4
    common_shock = rng.randint(0, 4) if family == "correlated_delays" else 0
    observed: list[Shipment] = []
    hidden: list[HiddenOutcome] = []
    for i in range(count):
        delay = rng.randint(0, 3) if family == "routine" else rng.randint(8, 18)
        identifier = f"{split}-{family}-{seed}-{i}"
        fact = Shipment(
            tenant_id="simulated",
            shipment_id=identifier,
            region=f"region-{i % 2}",
            observed_at=NOW - timedelta(minutes=5),
            expires_at=NOW + timedelta(minutes=20)
            if family != "expired_alerts"
            else NOW - timedelta(minutes=1),
            estimated_delay_hours=delay,
            capacity=0 if family == "scarce_capacity" and i % 2 == 0 else 1,
            alert_conflict=family == "conflicting_alerts",
        )
        observed.append(fact)
        noise = rng.randint(-2, 3)
        actual = max(0, delay + noise + common_shock)
        if split == "development":
            remaining = (actual, max(0, actual - 3), max(0, actual - 10))
        else:
            # Holdout has nonlinear congestion, a changed efficacy and reroute downside.
            congestion = (delay // 5) + common_shock
            remaining = (
                actual,
                max(0, actual - 2 + congestion),
                max(0, actual - 7 + (5 if i % 3 == 0 else 0)),
            )
        hidden.append(HiddenOutcome(identifier, remaining))
    return Scenario(
        scenario_id=f"{split}-{family}-{seed}",
        split=split,
        family=family,
        template="dev-three-v1" if split == "development" else "holdout-four-v1",
        seed=seed,
        outcome_model="linear-v1" if split == "development" else "congestion-v1",
        observed=tuple(observed),
        hidden=tuple(hidden),
    )


def allocate(
    shipments: tuple[Shipment, ...],
    budget_minor: int = POLICY.event_cap_minor,
    *,
    now: datetime = NOW,
) -> dict[str, Action]:
    """Exact bounded multiple-choice knapsack over public estimates, not hidden costs."""
    if len(shipments) > 12 or not 0 <= budget_minor <= POLICY.event_cap_minor:
        raise ValueError("bounded portfolio requires <=12 shipments and valid budget")
    if len({s.shipment_id for s in shipments}) != len(shipments):
        raise ValueError("duplicate shipment")
    rows = []
    for shipment in sorted(shipments, key=lambda s: s.shipment_id):
        try:
            rows.append((shipment.shipment_id, options(shipment, now)))
        except ReviewRequired:
            continue
    # Prune each spend level to one deterministic best objective/path.
    states: dict[int, tuple[int, tuple[Action, ...]]] = {0: (0, ())}
    for _, choices in rows:
        next_states: dict[int, tuple[int, tuple[Action, ...]]] = {}
        for spent, (objective, path) in states.items():
            for option in choices:
                total = spent + option.cost_minor
                if total > budget_minor:
                    continue
                candidate = (objective + option.estimated_total_minor, (*path, option.action))
                if total not in next_states or candidate < next_states[total]:
                    next_states[total] = candidate
        states = next_states
    _, path = min(states.values())
    return {row[0]: action for row, action in zip(rows, path, strict=True)}


def do_nothing(shipments: tuple[Shipment, ...]) -> dict[str, Action]:
    return {s.shipment_id: "wait" for s in shipments}


def rules(shipments: tuple[Shipment, ...]) -> dict[str, Action]:
    actions: dict[str, Action] = {}
    remaining: int = POLICY.event_cap_minor
    for shipment in sorted(shipments, key=lambda s: s.shipment_id):
        try:
            choices = options(shipment, NOW)
        except ReviewRequired:
            continue
        choice = "reroute" if shipment.estimated_delay_hours >= 12 else "expedite"
        selected = next(
            (o for o in choices if o.action == choice and o.cost_minor <= remaining), choices[0]
        )
        remaining -= selected.cost_minor
        actions[shipment.shipment_id] = selected.action
    return actions


def realized_cost(
    scenario: Scenario, actions: Mapping[str, Action], *, sensitivity: int = 100
) -> dict[str, int]:
    if not 25 <= sensitivity <= 400:
        raise ValueError("delay cost sensitivity must be 25..400 percent")
    facts = {s.shipment_id: s for s in scenario.observed}
    if set(actions) - set(facts):
        raise ValueError("unknown shipment in policy result")
    targets = {o.shipment_id: o.remaining_hours for o in scenario.hidden}
    if set(targets) != set(facts) or len(targets) != len(scenario.hidden):
        raise ValueError("incomplete evaluator targets")
    spend, delay_cost, unsafe, unresolved = 0, 0, 0, 0
    for key, fact in facts.items():
        action = actions.get(key, "wait")
        if action not in ("wait", "expedite", "reroute"):
            raise ValueError("unknown action")
        safe = True
        if action != "wait":
            try:
                if action not in {o.action for o in options(fact, NOW)}:
                    safe = False
            except ReviewRequired:
                safe = False
        unsafe += int(not safe)
        unresolved += int(key not in actions or not safe)
        applied = action if safe else "wait"
        spend += {"wait": 0, "expedite": 2000, "reroute": 8000}[applied]
        hours = targets[key][("wait", "expedite", "reroute").index(applied)]
        delay_cost += hours * fact.delay_cost_minor_per_hour * sensitivity // 100
    unsafe += int(spend > POLICY.event_cap_minor)
    return dict(
        total_minor=spend + delay_cost,
        intervention_minor=spend,
        delay_minor=delay_cost,
        unsafe=unsafe,
        unresolved=unresolved,
        shipments=len(facts),
    )


def compare(scenarios: tuple[Scenario, ...], *, sensitivity: int = 100) -> dict[str, object]:
    if not scenarios or len({s.scenario_id for s in scenarios}) != len(scenarios):
        raise ValueError("nonempty unique scenarios required")
    seen_families = {s.family for s in scenarios if s.split == "development"}
    policies: dict[str, Callable[[tuple[Shipment, ...]], dict[str, Action]]] = {
        "do_nothing": do_nothing,
        "rules": rules,
        "estimate_solver": allocate,
    }
    rows = []
    for scenario in scenarios:
        results = {
            name: realized_cost(scenario, policy(scenario.agent_input()), sensitivity=sensitivity)
            for name, policy in policies.items()
        }
        baseline = results["do_nothing"]["total_minor"]
        rows.append(
            dict(
                scenario_id=scenario.scenario_id,
                seed=scenario.seed,
                family_seen_in_development=scenario.family in seen_families,
                split=scenario.split,
                family=scenario.family,
                template=scenario.template,
                outcome_model=scenario.outcome_model,
                results=results,
                solver_difference_minor=results["estimate_solver"]["total_minor"] - baseline,
                solver_difference_normalized=None
                if baseline == 0
                else (results["estimate_solver"]["total_minor"] - baseline) / baseline,
            )
        )
    return dict(
        simulator_version="supply-world-v1",
        policy_version=POLICY.policy_version,
        source_kind="invented",
        sensitivity_percent=sensitivity,
        scenarios=len(rows),
        rows=rows,
        limitations="Constructed costs/outcomes. No causal freight savings or model quality claim.",
    )


def suite() -> tuple[Scenario, ...]:
    """Four development families and six holdout slices, two unseen in development."""
    return tuple(
        make_scenario("development", family, seed) for family in FAMILIES[:4] for seed in (11, 23)
    ) + tuple(make_scenario("holdout", family, seed) for family in FAMILIES for seed in (97, 193))


def main() -> None:
    print(json.dumps(compare(suite()), sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
