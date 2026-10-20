# Architecture and implementation plan

Accepted delivery direction, updated 2026-10-16. This document replaces the older design overview; historical design notes are preserved locally under `docs/archive`. [F2 shared contracts](shared-contracts.md) and F3 commands are merged and verified. [F4 local Postgres](local-postgres.md) is merged and verified; [F5 Foundation CI](ci.md) is merged/verified and the foundation milestone is complete. [H1 integration ADR](adr/0001-first-integration.md) and [smoke commands](integration-smoke.md) record merged Gemini/framework/local-tracing compatibility. H2 transport is merged; H3 [reviewed model recordings and strict replay](replay.md) is merged/verified on main 1207eb5. H4 [shared execution controls](controls.md) are merged/verified on main e9ebd07: 276 tests, clean replay and nine applicable hosted jobs. H5 [pinned private case manifests and registered independent scorers](case-manifests.md) are merged/verified on main c08f67d: 329 tests/replay and nine applicable hosted jobs. H6 [isolated trials and complete accounting](isolated-trials.md) is merged/verified on main 9c13b2c: 380 tests/replay and nine applicable hosted jobs. H7 adds [seeded fault drills and state invariants](seeded-faults.md) in [PR #77](https://github.com/Protagonist01/my-production-agentic-systems/pull/77), awaiting review/merge. Independent domain quality thresholds remain subsequent work.

## Shared platform and vertical boundary

One Python monorepo contains a domain-independent harness and five domain applications. Harness code owns typed runtime/model/evaluation contracts, provider transport, deadlines/budgets, immutable recordings, strict replay, trial accounting, fault injection, telemetry and reports. Verticals own their imports, schema, business policy, tool permissions, workflows and independent scorers. Harness never imports a vertical; verticals never import one another.

F1 establishes a virtual uv workspace, one lockfile and six installable packages under `harness/src/agent_harness` and `projects/<vertical>/src/<import_name>`. See the root README for import names and verified commands. Import Linter enforces harness independence and static cross-vertical boundaries. LangGraph serves the workflow verticals and Pydantic AI serves CFPB; neither is installed yet. H1 checks provider/framework/telemetry compatibility and pins tested versions before use. Use one telemetry backend initially.

Postgres holds operational records, checkpoints, reviews and action ledgers with isolated worktree/trial state. Gateway recordings use an immutable, exportable format (H3 uses reviewed exportable JSON). Source snapshots live outside Git with checksums and provenance. Thin Inngest wrappers are added only for demonstrated external-event waits; each wait/checkpoint has a single owner.

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

[Project management](project-management.md) defines the 8 epics and 53 tasks, acceptance gates, ownership and worktree operation. F1–F5/O1/H1–H5 are merged and verified. H2 adds the bounded [provider gateway](gateway.md); H3 adds [immutable model recordings/replay](replay.md), with [portable commands](development-commands.md) and [current-code study guide](../CODE_STUDY_GUIDE.md) maintained alongside it. Gateway/evaluation/Olist streams integrate small increments according to task prerequisites. Complete O8 first; prepare later data in parallel and integrate at most two verticals concurrently.

40 hours/week includes implementation, integration, labeling and review. Task sizes are provisional; fixed dates follow observed throughput. Working foundation/offline-example commands appear in the root README. Invented H1/H2 provider compatibility probes passed. No domain model-quality release score is available yet.

[Planning index](00-planning-index.md) · [Execution rationale](01-execution-and-evidence-proposal.md) · [Data/architecture rationale](02-data-and-architecture-comparison.md)

H4 [operating boundary](controls.md) and [code study](code-study-controls.md) cover reservations, retries/circuits, monotonic time and owned workers; merged acceptance evidence is recorded on closed #18.

[H8 telemetry operations](telemetry.md) cover explicit tracing, pseudonymous evidence and export/flush/cleanup health; [source study](code-study-telemetry.md) follows the implementation.


H8 #78 is merged/verified on main 21a5720. H9 #23 implements private [scorecards and paired case-level comparisons](scorecards.md) with complete scheduled denominators, unknown usage and conditional group-level safety uncertainty. [Source study](code-study-scorecards.md) traces the mechanism. H9 is merged/verified on fd87750. H10 adds [fresh dispatch and release evidence](release-evidence.md) with an independently pinned baseline approval; [source study](code-study-release.md) traces it. Verification stays offline by user choice. No domain quality result is claimed.


The user-approved O2+C1 batch follows verified H10 merge54f5af2. O2 adds [private exact-grain orders and conservative source-clock views](data/olist-orders.md), with a [source study](code-study-olist-orders.md). C1 proceeds in its own worktree and PR with the complete September2023–March2024 narrative archive and March holdout. These source-preparation mechanisms do not establish domain model quality or business actions.


C1 [CFPB source preparation](data/cfpb-source.md) uses a pinned official FOIA archive because the current live database removed narratives in 2026. Separate private agent/target stores and exact-text grouped temporal partitions preserve label isolation; [source study](code-study-cfpb.md) traces implementation and limits. The complete archive is scanned, missing narratives are counted, and groups crossing date windows are quarantined. Consumer targets remain unreviewed references; no classification or consumer-harm result is established.


O3 is merged/verified after user merge of #83. The authorized combined O4 #29 + O5 #30 delivery adds a [transactional SIM refund backend and persistent LangGraph workflow](olist-workflow.md), with [source walkthrough](code-study-olist-workflow.md). Source-backed offline refund/status/review and recovery checks use fictional scenario facts; no real payment or model-quality result is claimed. C2 remains a separate review in #84. O6 approval and O7 authenticated UI/API remain next.


C2 #84 adds [provisional blind CFPB review and deterministic baselines](cfpb-risk-baselines.md), with [source study](code-study-cfpb-baselines.md). It remains a separate unmerged review after reconciliation with O4 + O5 main. AI-review labels are provisional, and consumer targets remain reference labels; no human-validated risk/model-quality claim.
