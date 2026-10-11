# Supply chain disruption response

Accepted scope, updated 2026-10-11. Planned implementation; no application or evaluation result exists yet.

## Delivered application

A source-grounded logistics simulation with bounded interventions, budget allocation, approval waits and resilient execution.

Framework direction: LangGraph with thin external-event orchestration where needed. Verify current integrations and pin tested versions under H1 before implementation. The application includes a usable API/operator workflow, scoped access, traces and an operational guide.

Observed shipment + versioned alert facts → bounded options → portfolio allocation → scoped spend validation → exact-action approval/confirmation waits → bounded replanning → verified notifications.

## Data and boundary

DataCo shipping observations and timestamped NWS alert snapshots. Coverage/timezones/freshness are manifest fields. Optional BTS experiment represents passenger-airline patterns separately.

No unverified shipment/weather historical causal join. Interventions and realized outcomes are modeled in a controlled simulator with hidden outcome state, independent holdout families and sensitivity checks. No actual freight-savings claim.

Each importer produces provenance/checksum/use notes and validated agent-visible data. Independent expected labels and hidden outcomes live in scorer-only storage. Development/regression/holdout sets are versioned and related records remain grouped. Original, hybrid and synthetic/adversarial results are separate.

## Implementation tasks

### S1: Import shipping records and capture versioned weather snapshots

Priority: P1; provisional size M; prerequisites: H5. Status: Backlog.

Prepare DataCo shipping observations and NWS alert snapshots with coverage/timezones. Keep BTS passenger-airline proxy optional and separately labeled.

Acceptance evidence:

- [ ] No unverified historical weather-shipment causal join is claimed.
- [ ] Manifest records alert freshness, expiry and independent source lineage.
- [ ] Agent-visible facts respect the scenario clock and available source coverage.

### S2: Build an independent holdout simulator and baseline policies

Priority: P1; provisional size L; prerequisites: S1. Status: Backlog.

Specify intervention outcomes/costs, held-out scenarios, do-nothing/rules/solver policies and sensitivity parameters.

Acceptance evidence:

- [ ] Hidden realized outcomes are not available to the agent.
- [ ] Different seeds/template/scenario families and a holdout outcome model test simulator overfit.
- [ ] Total realized simulated cost and absolute/normalized baseline differences are defined.

### S3: Implement options, portfolio allocation and transactional spend tools

Priority: P1; provisional size M; prerequisites: S2, R3, F4. Status: Backlog.

Generate bounded options; allocate budget and enforce per-action/run limits with stable event identity and fresh record checks.

Acceptance evidence:

- [ ] Concurrent executions cannot overspend or double execute.
- [ ] Over-threshold actions require exact approval; stale budget state blocks commit.
- [ ] Failure after commit returns the original effect on retry.

### S4: Implement assessment, approvals, confirmations and bounded replanning

Priority: P1; provisional size L; prerequisites: S3, H10. Status: Backlog.

Build LangGraph assessment and thin Inngest event/fan-out/wait orchestration, with one state owner per concern.

Acceptance evidence:

- [ ] Approval/confirmation timeouts have explicit safe terminal outcomes.
- [ ] Replanning terminates and preserves already committed effects.
- [ ] Region bursts and duplicate/out-of-order events have deterministic tests.

### S5: Build operations interface and truthful shipment notifications

Priority: P1; provisional size M; prerequisites: S4, H8. Status: Backlog.

Show affected shipments, proposals, budget, approvals, confirmations and failures; messages use verified shipment/alert facts.

Acceptance evidence:

- [ ] Operators can see pending/unresolved/committed actions distinctly.
- [ ] Budget/approval access is tenant/role scoped.
- [ ] Notifications cannot state unconfirmed execution or invented delivery outcomes.

### S6: Release held-out cost, budget and recovery evaluation

Priority: P1; provisional size M; prerequisites: S5, O8. Status: Backlog.

Compare simulated realized cost with all baselines, fault recovery and scenario sensitivity; record proxy and causal limits.

Acceptance evidence:

- [ ] Completed, unresolved and unsafe outcomes are all counted.
- [ ] No actual freight savings claim is made from the simulation.
- [ ] Spend/duplicate invariants, fresh candidate evidence, model card and runbook meet gates.


## Evaluation and release

Total realized simulated cost and absolute/normalized differences versus do-nothing, rules and solver; budget and duplicate-action violations; recovery/review/unresolved outcomes; scenario sensitivity.

Gate: No unapproved/over-cap spend or duplicate effect; costs compared with do-nothing/rules/solver baselines on separate held-out simulator scenarios; aviation proxy claims clearly separated.

Use the shared strict-replay/fresh-evaluation/monitoring boundaries. Release requires merged implementation, independent case/state checks, complete fresh evidence and required fault cases. No critical observed violation can be hidden by improved averages.

[Architecture](README.md) · [Delivery plan](project-management.md) · [Backlog](backlog.json)
