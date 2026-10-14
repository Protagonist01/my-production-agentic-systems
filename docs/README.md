# Architecture and implementation plan

Accepted delivery direction, updated 2026-10-13. This document replaces the older design overview; historical design notes are preserved locally under `docs/archive`. [F2 shared contracts](shared-contracts.md) are implemented for review. Provider/framework SDK pins, thresholds and remaining commands become final through their implementation issues.

## Shared platform and vertical boundary

One Python monorepo contains a domain-independent harness and five domain applications. Harness code owns typed runtime/model/evaluation contracts, provider transport, deadlines/budgets, immutable recordings, strict replay, trial accounting, fault injection, telemetry and reports. Verticals own their imports, schema, business policy, tool permissions, workflows and independent scorers. Harness never imports a vertical; verticals never import one another.

F1 establishes a virtual uv workspace, one lockfile and six installable packages under `harness/src/agent_harness` and `projects/<vertical>/src/<import_name>`. See the root README for import names and verified commands. Import Linter enforces harness independence and static cross-vertical boundaries. LangGraph serves the workflow verticals and Pydantic AI serves CFPB; neither is installed yet. H1 checks provider/framework/telemetry compatibility and pins tested versions before use. Use one telemetry backend initially.

Postgres holds operational records, checkpoints, reviews and action ledgers with isolated worktree/trial state. Gateway recordings use an immutable, exportable format (H3 selects storage). Source snapshots live outside Git with checksums and provenance. Thin Inngest wrappers are added only for demonstrated external-event waits; each wait/checkpoint has a single owner.

Extract reusable scope/registry/write machinery only after Olist and Revenue demonstrate reuse. Domain-specific refund, invoice, criterion and spend rules stay in their vertical.

## Three evaluation modes

| Mode | Boundary | Claim |
|---|---|---|
| Strict replay | Exact captured model requests, pinned reads/clock/schedule; current code and controlled writes run; no provider fallback | Software behavior under specified recordings |
| Fresh candidate | Every trial bypasses previous response reuse; execute candidate with new model output and pinned source state | Candidate quality, usage and live provider latency |
| Monitoring | Observe served requests and their cache status | Traffic trends and new error cases |

Requests include full ordered messages, parameters, model/provider, tool/output schemas and serializer version. Repeated identical calls retain trial/occurrence identity. Results bind to code/behavior fingerprints, data/scorer/policy versions and environment. Missing cases/scorer errors stay explicit and fail release completeness.

## Controlled actions

Validate permissions, payload and business limits in code. Reserve shared budgets before dispatch. Use stable tenant/business-event operation keys across retries and new run IDs. Commit state and audit ledger transactionally. Approval binds exact action and record version; stale approval requires reassessment. Compensation appends a ledger event and refuses to overwrite an intervening legitimate change.

Agent-reported success is insufficient: independent scorers inspect committed state. Labels and hidden simulator outcomes never enter agent-visible views. Durable review/restart behavior and timeout-after-commit are required workflow tests.

## Data and claims

Each domain produces a source manifest, importer, validated views, independently reviewed labels and grouped/temporal development/regression/holdout splits. Preserve language/currency and each case's historical as-of boundary. Report original real inputs, hybrid scenarios and synthetic/adversarial cases separately.

| Vertical | Source and boundary | Detailed plan |
|---|---|---|
| Olist | Real historical order context; constructed support messages/policy and controlled action ledger | [Olist](olist-support.md) |
| CFPB | Published narratives; consumer-selected taxonomy is reference data; reviewed risk labels separate | [CFPB](cfpb-triage.md) |
| Revenue | Original CUAD/selected agreements; generated billing worlds separate; Maven is a fictional hardware CRM fixture | [Revenue](revenue-integrity.md) |
| Prior auth | Selected policies and illustrative transcription examples; independently labeled note-policy pairs | [Prior auth](prior-auth.md) |
| Supply chain | DataCo shipping + captured NWS alerts; no assumed causal historical join; BTS only optional passenger-airline proxy | [Supply chain](supply-chain-disruption.md) |

O1's authentic version-7 Olist snapshot is acquired outside Git and verified against its aggregate manifest. Currency/timezone, joins and as-of views remain O2; policy/cases remain O3. Other sources await their acquisition tasks. No source is yet a reviewed domain evaluation set.

## Measurement and release

Primary measures are independently correct autonomous completion on eligible cases; required/unnecessary review burden; observed critical violations with denominators/uncertainty; fault outcomes; all-three-fresh-trial correctness; and cost per safe completion. Add domain measures such as classification macro-F1/risk recall, supported criteria and extraction/reconciliation error rates. No blended accuracy across industries.

Calibrate numeric quality floors from reviewed baselines, declare before candidate comparison and inspect paired required-case regressions. Critical violations and incomplete evidence block release. Zero observed events is reported as 0/N with uncertainty, never proof of zero risk. Optional judges follow reviewed-case calibration; deterministic state checks remain primary.

## Execution

[Project management](project-management.md) defines the 8 epics and 53 tasks, acceptance gates, ownership and worktree operation. F1/O1 are Done after merge and verification; F2's contracts/offline case are prepared for review. After its merged baseline, gateway/evaluation/Olist streams integrate small increments according to task prerequisites. Complete O8 first; prepare later data in parallel and integrate at most two verticals concurrently.

40 hours/week includes implementation, integration, labeling and review. Task sizes are provisional; fixed dates follow observed throughput. Working foundation/offline-example commands appear in the root README. No provider smoke test or model release score is claimed to pass yet.

[Planning index](00-planning-index.md) · [Execution rationale](01-execution-and-evidence-proposal.md) · [Data/architecture rationale](02-data-and-architecture-comparison.md)
