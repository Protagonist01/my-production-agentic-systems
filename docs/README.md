# Architecture and implementation plan

Delivery state updated 2026-10-21. Verified main `5f73fc9` includes the merged R2/R3/R4 Revenue mechanisms; main passed 773 offline tests per matrix cell and 43 Postgres checks. R5/R6/S1 is the current unmerged batch: [approval-bound Revenue effects](revenue-operations.md), authenticated review/event orchestration and independent shipping/weather source preparation. R5 focused transaction/scope/snapshot evidence is integrated; interface/source and final broad acceptance follow. O8/R7 fresh release gates and human-adjudication limits remain pending. C2 #84 is a separate review with AI-provisional labels.

## Shared platform and vertical boundary

One Python monorepo contains a domain-independent harness and five domain applications. Harness code owns typed runtime/model/evaluation contracts, provider transport, deadlines/budgets, immutable recordings, strict replay, trial accounting, fault injection, telemetry and reports. Verticals own their imports, schema, business policy, tool permissions, workflows and independent scorers. Harness never imports a vertical; verticals never import one another.

F1 establishes a virtual uv workspace, one lockfile and six installable packages under `harness/src/agent_harness` and `projects/<vertical>/src/<import_name>`. See the root README for import names and verified commands. Import Linter enforces harness independence and static cross-vertical boundaries. LangGraph runs the Olist workflow; Pydantic AI is pinned and compatibility-tested for the CFPB path. H1 checks provider/framework/telemetry compatibility and pins tested versions before use. Use one telemetry backend initially.

Postgres holds operational records, checkpoints, reviews and action ledgers with isolated worktree/trial state. Gateway recordings use an immutable, exportable format (H3 uses reviewed exportable JSON). Source snapshots live outside Git with checksums and provenance. Thin Inngest wrappers are added only for demonstrated external-event waits; each wait/checkpoint has a single owner.

Olist and Revenue now demonstrate shared exact tenant/resource-kind/resource-ID/capability membership. Registry and write machinery require a second demonstrated use before extraction. Domain-specific refund, invoice, criterion and spend rules stay in their vertical.

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

Olist views, policy and hybrid cases are implemented; historical currency/timezone remain unverified. CFPB and original CUAD corpora are pinned outside Git. Constructed Revenue billing worlds have separate private inputs and evaluator stores. AI labels and source references do not establish human-adjudicated release quality.

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


O6/O7 are merged and verified through #86: the [scoped local support desk](olist-console.md) provides durable exact-action approval under the unchanged 100.00 SIM cap. The next user-authorized batch adds [offline Olist state reports](olist-release.md) and [original CUAD contract preparation](data/revenue-source.md), implemented in parallel and integrated for one review. Fresh provider/first-release acceptance remains pending by user instruction. C2 #84 is now merged and verified.

C2 #84 adds [provisional blind AI review and deterministic CFPB baselines](cfpb-risk-baselines.md), with a [source study](code-study-cfpb-baselines.md). It is merged/verified as95397c4; human adjudication and domain release evidence remain pending.

Supply-chain S2/S3/S4: [simulator, budgeted SIM actions and waits](supply-chain-operations.md), [source walkthrough](code-study-supply-operations.md). Invented mechanisms remain separate from S1 source observations and S6 release claims.


CFPB C3/C4: [typed triage and durable reviewer operations](cfpb-triage-operations.md), [source walkthrough](code-study-cfpb-triage.md) and [aggregate pilot evidence](data/cfpb-triage-evidence-v1.json). PR #94 is merged and verified. Labels remain AI-provisional and the pilot produced all-review results; no domain release.


O8 fresh review extension: [model card](olist-model-card.md), [aggregate evidence](data/olist-fresh-evidence-v1.json), [operator package](olist-fresh-review.md) and [execution/source study](code-study-olist-fresh.md). Gemini scored 30/36 correct with six unresolved timeouts and no observed unsafe effects. Proposed criteria were not met; final release approval and independent labels/baseline review remain separate.

The [separate diagnostic follow-up](olist-followup-review.md) investigates startup phases and
usage reconciliation under a newly authorized 36-call cap after verified #96. Original pilot
captures, labels and holdout are preserved; no release approval is inferred.
