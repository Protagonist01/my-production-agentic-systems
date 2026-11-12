import pytest
from pydantic import ValidationError
from supply_chain.release_evaluation import ActionObservation, SimulationPlan, world_pin
from supply_chain.simulator import allocate, suite

from supply_scorecard import InterventionReference, OperationsObservation, ScorecardPlan, scorecard


def plan():
    worlds = suite()[:1]
    simulation = SimulationPlan(
        candidate_sha256="a" * 64,
        worlds_sha256=world_pin(worlds),
        scenario_ids=tuple(w.scenario_id for w in worlds),
        trial_ids=("one", "two"),
        origin="mock",
    )
    return ScorecardPlan(simulation=simulation), worlds


def test_empty_scorecard_preserves_every_missing_slot():
    proposal, worlds = plan()
    report = scorecard(proposal, worlds, ())
    assert report["operations"]["missing"] == 2
    assert report["operations"]["safe_completion_rate"] == 0
    assert report["operations"]["notices"]["accuracy"] is None
    assert report["provider_cost"] is None and report["telemetry"] is None
    assert report["sensitivities"]["100"]["observed_cost_minor"]["p95"] is None
    assert not report["release_allowed"]


def test_pairing_missing_state_notices_and_explicit_intervention_basis():
    proposal, worlds = plan()
    world = worlds[0]
    proposal = proposal.model_copy(
        update={
            "references": (
                InterventionReference(
                    scenario_id=world.scenario_id,
                    shipment_id=world.observed[0].shipment_id,
                    intervention_required=False,
                    basis="simulation_hindsight",
                    reference_id="authored-v1",
                ),
            ),
            "required_operations": ("state_verified", "completed", "unauthorized_effects"),
        }
    )
    actions = (
        ActionObservation(
            scenario_id=world.scenario_id, trial_id="one", actions=allocate(world.agent_input())
        ),
    )
    operations = (
        OperationsObservation(
            scenario_id=world.scenario_id,
            trial_id="one",
            completed=True,
            evidence_id="mock-readback",
            notices_checked=4,
            notices_correct=3,
            notice_checker_id="independent-template-check-v1",
            approval_requests=2,
            replans=1,
            unchanged_fact_replans=1,
        ),
    )
    report = scorecard(proposal, worlds, actions, operations, window_seconds=10)
    assert report["operations"]["safe_completed"] == 0  # No state/effect readback.
    assert report["operations"]["complete_observations"] == 0
    assert report["operations"]["notices"]["accuracy"] == 0.75
    assert report["operations"]["metrics"]["approval_requests"]["missing"] == 1
    paired = report["sensitivities"]["100"]["paired_baselines"]["estimate_solver"]
    assert paired["observed_pairs"] == 1
    assert paired["tie"] == paired["safe_pairs"] == 1
    assert report["sensitivities"]["100"]["safe_action_map_completion_rate"] == 0.5
    assert (
        report["sensitivities"]["100"]["intervention_by_reference_basis"]["public_policy_reference"]
        == {}
    )
    basis = report["sensitivities"]["100"]["intervention_by_reference_basis"][
        "simulation_hindsight"
    ]
    assert basis["scheduled"] == 2 and basis["unknown"] == 1


def test_operational_duplicates_unknowns_and_impossible_counts_refused():
    proposal, worlds = plan()
    row = OperationsObservation(
        scenario_id=worlds[0].scenario_id, trial_id="one", evidence_id="mock"
    )
    with pytest.raises(ValueError, match="duplicate"):
        scorecard(proposal, worlds, (), (row, row))
    for fields in (
        {"notices_checked": 1},
        {"replans": 1, "unchanged_fact_replans": 2},
        {"recovery_seconds": 1},
        {"wall_seconds": float("nan")},
    ):
        with pytest.raises(ValidationError):
            OperationsObservation(**row.model_dump(exclude_unset=True), **fields)
    for value in (0, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            scorecard(proposal, worlds, (), window_seconds=value)
