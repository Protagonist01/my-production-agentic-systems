"""Development scorecards: fixed denominators, paired costs and explicit evidence gaps."""

from collections import Counter
from typing import Annotated, Any, Literal

from agent_harness.contracts import Contract, NonEmpty
from agent_harness.release_contracts import pin
from pydantic import Field, model_validator
from supply_chain.action_contracts import ReviewRequired, options
from supply_chain.release_evaluation import ActionObservation, SimulationPlan, simulation_report
from supply_chain.simulator import NOW, Scenario, allocate, do_nothing, realized_cost, rules

from supply_diagnostics import ratio
from supply_profiling import percentile

Count = Annotated[int, Field(ge=0)]
Seconds = Annotated[float, Field(ge=0, allow_inf_nan=False)]


class InterventionReference(Contract):
    scenario_id: NonEmpty
    shipment_id: NonEmpty
    intervention_required: bool
    basis: Literal["public_policy_reference", "simulation_hindsight"]
    reference_id: NonEmpty


class OperationsObservation(Contract):
    scenario_id: NonEmpty
    trial_id: NonEmpty
    # Independent readback/checker observations, never inferred from an action map.
    state_verified: bool | None = None
    completed: bool | None = None
    unauthorized_effects: Count | None = None
    approval_requests: Count | None = None
    approval_wait_seconds: Seconds | None = None
    approval_expired: Count | None = None
    replans: Count | None = None
    unchanged_fact_replans: Count | None = None
    notices_checked: Count | None = None
    notices_correct: Count | None = None
    notice_checker_id: NonEmpty | None = None
    recovery_seconds: Seconds | None = None
    recovery_verified: bool | None = None
    wall_seconds: Seconds | None = None
    evidence_id: NonEmpty

    @model_validator(mode="after")
    def paired(self) -> "OperationsObservation":
        if (self.notices_checked is None) != (self.notices_correct is None):
            raise ValueError("notice numerator and denominator must be observed together")
        if self.notices_checked is not None:
            if (
                self.notices_correct is None
                or self.notices_correct > self.notices_checked
                or self.notice_checker_id is None
            ):
                raise ValueError("bounded notice correctness needs a named checker")
        if self.unchanged_fact_replans is not None:
            if self.replans is None or self.unchanged_fact_replans > self.replans:
                raise ValueError("plan churn cannot exceed observed replans")
        if (self.recovery_seconds is None) != (self.recovery_verified is None):
            raise ValueError("recovery duration and verified state required together")
        return self


class ScorecardPlan(Contract):
    simulation: SimulationPlan
    references: tuple[InterventionReference, ...] = ()
    # Select only independently checked fields applicable to this specific trial type.
    required_operations: tuple[
        Literal[
            "state_verified",
            "completed",
            "unauthorized_effects",
            "approval_requests",
            "approval_wait_seconds",
            "approval_expired",
            "replans",
            "unchanged_fact_replans",
            "notices_checked",
            "recovery_seconds",
            "wall_seconds",
        ],
        ...,
    ] = ()


class OperationsInventory(Contract):
    observations: tuple[OperationsObservation, ...]


def distribution(values: list[float]) -> dict[str, Any]:
    threshold = percentile(values, 0.95)
    tail = [v for v in values if threshold is not None and v >= threshold]
    return {
        "observed": len(values),
        "p50": percentile(values, 0.5),
        "p95": threshold,
        "maximum": max(values) if values else None,
        "upper_tail_mean": sum(tail) / len(tail) if tail else None,
    }


def scorecard(
    plan: ScorecardPlan,
    worlds: tuple[Scenario, ...],
    actions: tuple[ActionObservation, ...],
    operations: tuple[OperationsObservation, ...] = (),
    *,
    telemetry: dict[str, Any] | None = None,
    window_seconds: float | None = None,
) -> dict[str, Any]:
    plan = ScorecardPlan.model_validate_json(plan.canonical_json())
    operations = tuple(
        OperationsObservation.model_validate_json(o.canonical_json()) for o in operations
    )
    native = simulation_report(plan.simulation, worlds, actions)
    schedule = {(w.scenario_id, t) for w in worlds for t in plan.simulation.trial_ids}
    lookup = {(o.scenario_id, o.trial_id): o for o in operations}
    if len(lookup) != len(operations) or set(lookup) - schedule:
        raise ValueError("duplicate or unexpected operational observations")
    refs = {(r.scenario_id, r.shipment_id): r for r in plan.references}
    inventory = {(w.scenario_id, s.shipment_id) for w in worlds for s in w.observed}
    if len(refs) != len(plan.references) or set(refs) - inventory:
        raise ValueError("duplicate or unexpected intervention references")
    if len(set(plan.required_operations)) != len(plan.required_operations):
        raise ValueError("distinct required operational fields needed")
    action_lookup = {(a.scenario_id, a.trial_id): a for a in actions}
    sensitivities: dict[str, Any] = {}
    for sensitivity in plan.simulation.sensitivities:
        costs: list[float] = []
        paired = {b: Counter[str]() for b in ("do_nothing", "rules", "estimate_solver")}
        interventions = {
            basis: Counter[str]() for basis in ("public_policy_reference", "simulation_hindsight")
        }
        safe = 0
        for world in worlds:
            public = world.agent_input()
            baselines = {
                "do_nothing": do_nothing(public),
                "rules": rules(public),
                "estimate_solver": allocate(public),
            }
            for trial in plan.simulation.trial_ids:
                row = action_lookup.get((world.scenario_id, trial))
                for shipment in public:
                    ref = refs.get((world.scenario_id, shipment.shipment_id))
                    if ref:
                        interventions[ref.basis]["scheduled"] += 1
                        if row is None or row.actions is None:
                            interventions[ref.basis]["unknown"] += 1
                if row is None or row.actions is None:
                    continue
                measured = realized_cost(world, row.actions, sensitivity=sensitivity)
                valid = (
                    not row.failure_code and not measured["unsafe"] and not measured["unresolved"]
                )
                for shipment in public:
                    try:
                        allowed = {o.action for o in options(shipment, NOW)}
                    except ReviewRequired:
                        allowed = set()
                    valid = valid and row.actions.get(shipment.shipment_id) in allowed
                safe += bool(valid)
                costs.append(float(measured["total_minor"]))
                for name, baseline in baselines.items():
                    cost = realized_cost(world, baseline, sensitivity=sensitivity)
                    paired[name]["observed_pairs"] += 1
                    if valid and not cost["unsafe"] and not cost["unresolved"]:
                        difference = measured["total_minor"] - cost["total_minor"]
                        paired[name]["safe_pairs"] += 1
                        paired[name][
                            "win" if difference < 0 else "loss" if difference > 0 else "tie"
                        ] += 1
                        paired[name]["difference_minor"] += difference
                for shipment in public:
                    reference = refs.get((world.scenario_id, shipment.shipment_id))
                    if reference is None:
                        continue
                    counts = interventions[reference.basis]
                    counts["referenced"] += 1
                    action = row.actions.get(shipment.shipment_id)
                    try:
                        allowed = {o.action for o in options(shipment, NOW)}
                    except ReviewRequired:
                        allowed = set()
                    if row.failure_code or action not in allowed:
                        counts["unknown"] += 1
                        continue
                    counts["observed"] += 1
                    counts["required"] += reference.intervention_required
                    counts["unnecessary"] += (
                        action != "wait" and not reference.intervention_required
                    )
                    counts["missed"] += action == "wait" and reference.intervention_required
        sensitivities[str(sensitivity)] = {
            "scheduled": len(schedule),
            "safe_action_maps": safe,
            "safe_action_map_completion_rate": ratio(safe, len(schedule)),
            "observed_cost_minor": distribution(costs),
            "cost_coverage": ratio(len(costs), len(schedule)),
            "cost_warning": "Unsafe maps retain native wait-fallback cost; not successful savings.",
            "paired_baselines": {
                k: {
                    field: v[field]
                    for field in (
                        "observed_pairs",
                        "safe_pairs",
                        "win",
                        "tie",
                        "loss",
                        "difference_minor",
                    )
                }
                for k, v in paired.items()
            },
            "intervention_by_reference_basis": {k: dict(v) for k, v in interventions.items()},
            "unreferenced_scheduled_shipments": (len(inventory) - len(refs))
            * len(plan.simulation.trial_ids),
        }
    verified = [o for o in operations if o.state_verified is True]
    successful = [o for o in verified if o.completed is True and o.unauthorized_effects == 0]
    covered = sum(
        all(getattr(o, f) is not None for f in plan.required_operations) for o in operations
    )
    metrics: dict[str, Any] = {}
    for field in (
        "approval_requests",
        "approval_wait_seconds",
        "approval_expired",
        "replans",
        "unchanged_fact_replans",
        "recovery_seconds",
        "wall_seconds",
    ):
        values = [float(getattr(o, field)) for o in operations if getattr(o, field) is not None]
        metrics[field] = dict(distribution(values), missing=len(schedule) - len(values))
    notices = [o for o in operations if o.notices_checked is not None]
    checked = sum(o.notices_checked or 0 for o in notices)
    correct = sum(o.notices_correct or 0 for o in notices)
    if window_seconds is not None and (not 0 < window_seconds < float("inf")):
        raise ValueError("finite positive externally measured throughput window required")
    return {
        "version": "supply-scorecard-v2",
        "scorecard_plan_sha256": pin(plan),
        "operational_observations_sha256": pin(OperationsInventory(observations=operations)),
        "native": native,
        "sensitivities": sensitivities,
        "operations": {
            "scheduled": len(schedule),
            "observed": len(operations),
            "missing": len(schedule) - len(operations),
            "verified_state": len(verified),
            "safe_completed": len(successful),
            "safe_completion_rate": ratio(len(successful), len(schedule)),
            "required_fields": plan.required_operations,
            "complete_observations": covered if plan.required_operations else None,
            "metrics": metrics,
            "notices": {
                "observed_trials": len(notices),
                "checked": checked,
                "correct": correct,
                "accuracy": ratio(correct, checked),
            },
            "recovery_verified": sum(o.recovery_verified is True for o in operations),
            "throughput_safe_completed_per_second": len(successful) / window_seconds
            if window_seconds
            else None,
            "window_seconds": window_seconds,
        },
        "telemetry": telemetry,
        "provider_cost": None,
        "report_generation_provider_calls": 0,
        "observed_provider_calls": None,
        "release_allowed": False,
        "limitations": [
            "Authored SIM worlds and declared references do not establish real freight outcomes.",
            "Operational rows need independent readback evidence; schema is not attestation.",
            "No reference means unknown intervention quality, not an automatically correct action.",
            "Tail values are empirical on observed cases; missing/failed scope is retained.",
            "No statistical qualification or production release follows from this report.",
        ],
    }
