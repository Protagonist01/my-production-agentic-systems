"""Independent simulation, visible-only planning and hard policy boundaries."""

import itertools
from dataclasses import replace
from datetime import timedelta

import pytest
from pydantic import ValidationError
from supply_chain.action_contracts import POLICY, Command, ReviewRequired, Shipment, options
from supply_chain.simulator import (
    FAMILIES,
    NOW,
    HiddenOutcome,
    allocate,
    compare,
    make_scenario,
    realized_cost,
)
from supply_chain.source_adapter import hybrid_observation
from supply_chain.source_contracts import ShipmentFact


def fact(key="shipment", **updates):
    values = dict(
        tenant_id="invented",
        shipment_id=key,
        region="region",
        observed_at=NOW - timedelta(minutes=1),
        expires_at=NOW + timedelta(hours=2),
        estimated_delay_hours=12,
    )
    values.update(updates)
    return Shipment(**values)


@pytest.mark.parametrize(
    "split,family", tuple(itertools.product(("development", "holdout"), FAMILIES))
)
def test_reproducible_independent_worlds_and_denominators(split, family):
    world = make_scenario(split, family, 11)
    assert world == make_scenario(split, family, 11)
    assert world != make_scenario(split, family, 97)
    inputs = world.agent_input()
    assert all(
        set(s.model_dump()).isdisjoint({"hidden", "outcomes", "remaining_hours", "split", "seed"})
        for s in inputs
    )
    report = compare((world,))
    assert report["scenarios"] == 1
    for result in report["rows"][0]["results"].values():
        assert result["shipments"] == len(inputs)
        assert result["total_minor"] == result["intervention_minor"] + result["delay_minor"]


def test_holdout_changes_seed_namespace_portfolio_template_and_outcome_equation():
    dev = make_scenario("development", "correlated_delays", 11)
    hold = make_scenario("holdout", "correlated_delays", 11)
    assert dev.template != hold.template and dev.outcome_model != hold.outcome_model
    assert len(dev.observed) != len(hold.observed)
    assert {s.shipment_id for s in dev.observed}.isdisjoint(s.shipment_id for s in hold.observed)
    assert dev.hidden != hold.hidden


def test_hidden_target_changes_scores_without_changing_agent_input_or_plan():
    first = make_scenario("development", "routine", 11)
    second = replace(
        first, hidden=tuple(HiddenOutcome(s.shipment_id, (100, 100, 100)) for s in first.observed)
    )
    assert first.agent_input() == second.agent_input()
    plan = allocate(first.agent_input())
    assert plan == allocate(second.agent_input())
    assert realized_cost(first, plan) != realized_cost(second, plan)


@pytest.mark.parametrize("budget", [0, 2000, 8000, 10000, 16000])
def test_solver_matches_independent_exhaustive_public_objective(budget):
    rows = (fact("one", estimated_delay_hours=4), fact("two", estimated_delay_hours=12))
    plan = allocate(rows, budget)
    selected = [next(o for o in options(s, NOW) if o.action == plan[s.shipment_id]) for s in rows]
    objective = sum(o.estimated_total_minor for o in selected)
    oracle = min(
        sum(o.estimated_total_minor for o in pair)
        for pair in itertools.product(*(options(s, NOW) for s in rows))
        if sum(o.cost_minor for o in pair) <= budget
    )
    assert objective == oracle and sum(o.cost_minor for o in selected) <= budget


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"facts_complete": False}, "missing_facts"),
        ({"alert_conflict": True}, "conflicting_facts"),
        ({"expires_at": NOW}, "stale_or_future_facts"),
        ({"observed_at": NOW + timedelta(seconds=1)}, "stale_or_future_facts"),
    ],
)
def test_missing_conflicting_future_expired_facts_are_blocked(changes, reason):
    shipment = fact(**changes)
    with pytest.raises(ReviewRequired, match=reason):
        options(shipment, NOW)
    assert allocate((shipment,)) == {}


def test_capacity_and_catalog_caps_and_minor_units():
    assert [o.action for o in options(fact(capacity=0), NOW)] == ["wait"]
    assert all(o.cost_minor <= POLICY.action_cap_minor for o in options(fact(), NOW))
    with pytest.raises(ValidationError):
        fact(estimated_delay_hours=True)
    with pytest.raises(ValidationError):
        POLICY.model_validate({"event_cap_minor": 50001})


def test_operation_identity_survives_versions_actions_and_run_replanning():
    first = Command(
        tenant_id="tenant",
        event_id="incident",
        shipment_id="shipment",
        expected_shipment_version=0,
        expected_budget_version=0,
        action="wait",
    )
    assert (
        first.operation_id
        == first.model_copy(update={"action": "reroute", "expected_budget_version": 4}).operation_id
    )
    assert first.operation_id != first.model_copy(update={"tenant_id": "other"}).operation_id


def test_incomplete_invalid_or_duplicate_evidence_cannot_silently_pass():
    world = make_scenario("development", "routine", 11)
    with pytest.raises(ValueError, match="targets"):
        realized_cost(replace(world, hidden=()), {})
    with pytest.raises(ValueError):
        compare((world, world))
    with pytest.raises(ValueError):
        realized_cost(world, {"unknown": "wait"})
    with pytest.raises(ValueError):
        allocate(tuple(fact(str(i)) for i in range(13)))
    with pytest.raises(ValueError):
        allocate((fact(), fact()))


def test_zero_baseline_difference_is_undefined_and_sensitivity_is_explicit():
    world = make_scenario("development", "routine", 11)
    zero = replace(
        world, hidden=tuple(HiddenOutcome(s.shipment_id, (0, 0, 0)) for s in world.observed)
    )
    assert compare((zero,))["rows"][0]["solver_difference_normalized"] is None
    one, two = realized_cost(world, {}, sensitivity=100), realized_cost(world, {}, sensitivity=200)
    assert two["delay_minor"] == 2 * one["delay_minor"]


def test_unsafe_actions_and_abstentions_stay_in_denominators():
    world = make_scenario("holdout", "conflicting_alerts", 97)
    unsafe = realized_cost(world, {s.shipment_id: "reroute" for s in world.observed})
    unresolved = realized_cost(world, {})
    assert unsafe["unsafe"] == unsafe["shipments"] == unsafe["unresolved"]
    assert unresolved["unresolved"] == unresolved["shipments"]
    assert unsafe["intervention_minor"] == 0


def test_source_observation_requires_explicit_assumptions_and_clock():
    source = ShipmentFact(
        source_key="a" * 64,
        observed_at=NOW,
        recorded_order_time=NOW.replace(tzinfo=None),
        destination_country="invented",
        destination_region="invented",
        shipping_mode="invented",
        scheduled_days=2,
        quantity=1,
        category="invented",
    )
    args = dict(
        tenant_id="tenant",
        shipment_id="shipment",
        region="region",
        clock=NOW,
        estimated_delay_hours=12,
        delay_cost_minor_per_hour=1000,
        max_age_seconds=1800,
    )
    observation = hybrid_observation(source, **args)
    assert observation.provenance == "source-observation-hybrid"
    assert observation.source_ref == "dataco-v5:" + source.source_key
    assert "recorded_order_time" not in observation.model_dump()
    with pytest.raises(ReviewRequired):
        hybrid_observation(source, **{**args, "clock": NOW - timedelta(seconds=1)})
    with pytest.raises(ValueError):
        hybrid_observation(source, **{**args, "max_age_seconds": 1801})


def test_suite_reserves_unseen_families_and_distinct_holdout_seeds():
    from supply_chain.simulator import suite

    worlds = suite()
    dev = [w for w in worlds if w.split == "development"]
    held = [w for w in worlds if w.split == "holdout"]
    assert {w.seed for w in dev}.isdisjoint(w.seed for w in held)
    assert len({w.family for w in held} - {w.family for w in dev}) == 2
    assert len(worlds) == 20
