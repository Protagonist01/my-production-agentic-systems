# Project management

Updated: 2026-10-23. User-merged #92 is verified as main6c2b7d9 with an identical reviewed tree, nine applicable main CI jobs, actual881tests per qualitycell/87Postgres and clean exact-main replay. P1#46/P2#47/P3#48 are closed completed; provisional source/clinical limits remain. The user selected P4#49/P5#50 as the next dependent batch. P6 and S6 remain behind the pending O8 release gate. C2#84 is a separate review. Native project-board state remains unverified.

## Scope and source of truth

Build one shared evaluation/resilience platform and five usable industry applications. Finish a source-grounded Olist release first; retain CFPB, Revenue integrity, Prior auth and Supply chain as subsequent releases. This is a complete project backlog, not a set of disposable demonstrations.

[Backlog manifest](backlog.json) records all 53 tasks and 8 epics, including dependencies, acceptance evidence and verified issue links. [GitHub Project 2](https://github.com/users/Protagonist01/projects/2) is the execution board; the manifest is the versioned planning snapshot. The [root tracker #1](https://github.com/Protagonist01/my-production-agentic-systems/issues/1) contains eight epic sub-issues, each containing its tasks. Seven native milestones are created and assigned.

## Delivery sequence

| Stage | Exit evidence |
|---|---|
| Foundation | Locked setup, portable commands, shared contracts and one fake end-to-end case; isolated state and offline CI |
| Gateway + evaluation + Olist | Integrate small increments; authentic source ingestion, scoped tools, durable review, exact-action approvals, usable API/UI |
| First complete release | O8 verifies committed state, crash/restart recovery, held-out fresh results and release manifests |
| Expansion | CFPB routing; Revenue extraction/reconciliation; Prior auth evidence assessment; Supply chain controlled interventions |
| Operations | Deploy, restore/rollback exercises, monitoring and per-vertical release documentation |

Data selection/label preparation may overlap earlier work. Task dependencies, rather than entire epic completion, determine readiness. O8 precedes the later vertical releases; it does not block their independent preparation.

## Task workflow

Backlog → Ready → In progress → Review → Done. Use a separate blocker field/section for blocked work.

- **Ready:** prerequisites merged and verified, scope understood, acceptance evidence defined, owner/paths agreed.
- **In progress:** one task owner and branch, linked issue and bounded implementation.
- **Review:** concrete PR, relevant verification output and known limitations attached.
- **Done:** merged PR and verified acceptance evidence. A written plan, open PR or issue creation is not implementation completion.
- **Blocked:** record cause, responsible follow-up and what unblocks it. No silent dependency skip.

[F1 #10](https://github.com/Protagonist01/my-production-agentic-systems/issues/10) and [O1 #26](https://github.com/Protagonist01/my-production-agentic-systems/issues/26) are closed as completed. F1 merged through #63; O1 #64 merged into the former foundation branch, then [integration PR #65](https://github.com/Protagonist01/my-production-agentic-systems/pull/65) carried it into main a665d3d. Post-merge locked installation, 16 tests, both import contracts, Ruff and authentic-source verification passed. [F2 #11](https://github.com/Protagonist01/my-production-agentic-systems/issues/11) is closed as completed after the user reviewed/merged [PR #66](https://github.com/Protagonist01/my-production-agentic-systems/pull/66) and a clean merged-baseline installation/check passed 43 tests, strict types, lint/format and imports. [F3 #12](https://github.com/Protagonist01/my-production-agentic-systems/issues/12) is closed/completed after user review/merge of [PR #68](https://github.com/Protagonist01/my-production-agentic-systems/pull/68). Verified main ce8334c: locked setup/check, 55 tests, strict types, both imports, example revision and six archive/wheel builds. Browser recovery allowed native Done read-back. [F4 #13](https://github.com/Protagonist01/my-production-agentic-systems/issues/13) is closed/completed after user review/merge of PR #69 and main d3f783c verification: 64 offline checks, 11 required database tests, types/imports/Ruff, exact example revision and six builds. [F5 #14](https://github.com/Protagonist01/my-production-agentic-systems/issues/14) completed after user review/merge of [PR #70](https://github.com/Protagonist01/my-production-agentic-systems/pull/70). Verified main 6e48011 and [push-main run 38647582091](https://github.com/Protagonist01/my-production-agentic-systems/actions/runs/38647582091), nine applicable jobs passed with PR metadata intentionally skipped. Local setup/check passed 77 tests, types/imports/Ruff, exact clean-main example, six builds and dependency audit. The initial local restart-wait failure is retained; a fresh complete Postgres rerun passed all 11 tests in 793.42 seconds. Verified every foundation child closed before closing Epic F and M1. Native board shows both completed. [H1 #15](https://github.com/Protagonist01/my-production-agentic-systems/issues/15) is closed/completed after user merge of [PR #71](https://github.com/Protagonist01/my-production-agentic-systems/pull/71) and main 0a859bb verification. [Main run 38660002889](https://github.com/Protagonist01/my-production-agentic-systems/actions/runs/38660002889) passed nine applicable jobs; PR-only metadata intentionally skipped. Local 97 offline tests, strict types/imports/Ruff, SDK/framework mock probe, exact-main example, six builds and audit passed. Original real Gemini/local Langfuse evidence remains in the ADR. H2 #16 completed after user merge of #72 and verified main 9282d87 / run 38779049159. Clean setup/check passed 151 tests, strict types/imports/Ruff/lock. Browser control recovered; H2 native Done and H3 In progress were verified. [H3 #17](https://github.com/Protagonist01/my-production-agentic-systems/issues/17) completed after user merge of #73 and exact main 1207eb5 verification: clean setup/check passed 220 tests and replay consumed six invented calls/reproduced two timeouts with no provider dispatch. Main run 38787114829 passed nine applicable jobs. Native Done was read back. H4 #18 completed after user merge of #74 and exact main e9ebd07 verification: 276 tests, nineteen typed files, imports/Ruff/lock and six-call offline replay. Main run 38803477072 passed nine applicable jobs; PR-only metadata skipped. Native Done was read back. H5 #19 completed after user merge of #75 and clean main c08f67d verification: 329 tests, twenty-one typed source files, imports/Ruff/format/lock and exact six-call replay. Main run 38815711769 passed nine applicable jobs; PR-only metadata skipped. Native Done read back. H6 #20 completed after user merge of #76 and verified main 9c13b2c: clean setup/check passed 380 tests and exact replay; main run 38959680261 passed nine applicable jobs. Native board read-back unavailable after helper recovery failed. H7 #21 completed after user merge of #77 and main 487242f verification: nine applicable hosted jobs passed. Clean local check passed 424 tests with one pre-start eight-second Windows timeout; that unchanged case passed separately. Exact replay passed. H8 #22 completed on main 21a5720 after user merge of #78; H9 #23 completed on verified fd87750 after user merge of #79; H10 #24 completed on verified54f5af2; O2 #27 is merged/verified and completed; C1 #34 is merged/verified and completed; [telemetry operations](telemetry.md) document its privacy and health boundary; [shared execution controls](controls.md) document the implementation boundary. [Recording/replay runbook](replay.md) documents the model-only boundary, immutable publication, reviewed pins and completion requirement. P1 source preparation stays Backlog until capacity is assigned. L5 #62 completed native administration. Live model evaluation and domain application behavior remain unimplemented.

## Capacity and planning

The user's 40 hours/week includes pairing, implementation, review, integration, labeling and documentation. Plan no more than three active implementation tasks/worktrees and no more than two verticals under integration. Size estimates are provisional: S 2–4 hours, M 4–8, L 8–16. Split a task that grows beyond two working days. Track actual hours and blocked time before committing calendar dates.

Plan weekly: review acceptance evidence and blockers; select Ready work within available capacity; reserve time for integration/data review. Reforecast from completed work, rather than dividing total scope by nominal parallel workers. At each stage gate, inspect newly failing required cases and open defects before scheduling expansion.

P0 = foundation/first-release critical path, P1 = remaining committed product scope, P2 = later enhancement/management infrastructure. Priority is separate from dependency readiness.

## Worktrees and ownership

Create implementation worktrees only after a verified contract baseline exists in Git. Use one issue-sized branch per worktree, based on the current reviewed main, unless the user authorizes a tightly coupled delivery bundle (O4 + O5 below). Proposed streams:

| Stream | Owned paths |
|---|---|
| Gateway | harness/gateway and associated tests/recordings |
| Evaluation | harness/evals, faults, reporting and associated tests |
| Olist | projects/olist-support, domain policy, backend and tests |

The integrator owns shared interfaces, dependency lockfiles, root commands, CI, shared migrations and the Build Book. Request changes to these through a small prerequisite PR; do not build competing shared APIs. Merge working increments, update dependent branches and verify the complete flow after integration.

Each worktree/trial needs distinct database state, service names, ports, volumes, caches and temporary paths. A Git worktree alone isolates files, not services. Share immutable sanitized fixtures where useful; never share writable trial state. Keep a common live-provider budget/queue.

The user authorized independent O2+C1 work in parallel after merged H10 verification. O2 reuses the existing managed checkout on codex/o2-orders-360; C1 uses the separate managed c1-cfpb-import checkout on codex/c1-cfpb-import. Both start from verified54f5af2. Each owns its vertical package, tests, source/operations/study documentation and acceptance evidence. Shared planning/Build Book/index changes may need reconciliation after the first PR merges; rebase the remaining PR and recheck affected evidence. Source data and writable derived stores remain private and separate. No shared database/service or live-provider budget is used. Retain user review/merge gates for dependent O3/C2; no native board transition is claimed.

## Architecture and evaluation boundaries

The harness owns generic model transport, replay/recording, budgets, trial accounting, fault injection, telemetry and report mechanisms. A vertical owns imports, domain tables, policy, tools, expected labels and deterministic scoring. Extract common access machinery after Olist and Revenue demonstrate actual reuse.

- Strict replay executes current code against exact captured requests, pinned reads, clocks and reset controlled write state. Missing recordings fail without network fallback.
- Fresh candidate evaluation bypasses prior response reuse and records new trials, complete provenance and observed usage.
- Monitoring observes served traffic; it is separate from controlled release experiments.
- Scorers independently inspect actual state. Expected labels/hidden outcomes are unavailable to agents.
- Stable tenant/business-event operation keys survive new run IDs. Approvals bind exact payload and record version. Compensation refuses to overwrite intervening changes.

Raw datasets and secrets stay outside Git. Record source snapshots/checksums/use conditions; separate original real, hybrid and synthetic/adversarial evidence. Authentic ingestion is required for the first complete Olist release.

## Headline metrics and release gates

| Metric | Required interpretation |
|---|---|
| Autonomous completion | Independently correct completion / pre-labeled eligible cases; escalating everything earns no credit |
| Review burden | Required and unnecessary handoffs, with reviewed-case correctness |
| Critical violations | Observed events / relevant opportunities, uncertainty and severity; critical event blocks release |
| Fault outcomes | Recovery, appropriate review, safe unresolved and unsafe outcomes separately |
| Repeated-trial correctness | All three fresh trials correct on a declared subset; disclose case count |
| Cost per safe autonomous completion | Total experiment cost / verified autonomous completions; undefined when zero complete |

Report denominator, source category, slice and mode for every result. Quality floors follow baseline measurement and are declared before candidate comparison; averages cannot conceal newly failing required cases. Missing cases, scorer errors, incompatible evidence or critical violations block release. Live provider latency cannot be inferred from replay timing. Each vertical adds its domain metric; avoid a blended cross-industry accuracy.

## GitHub administration

Use a root delivery tracker → eight epic sub-issues → 53 task sub-issues. Task bodies contain ID, priority, size, scope, dependency links, acceptance checks and completion evidence. Native hierarchy is distinct from dependency edges; record prerequisites explicitly.

The native Project has Status, Area, Priority, Size, Iteration and Blocker fields; Backlog, Board, Current iteration, Roadmap, My items, By workstream and Blocked views. All 53 tasks have Area, Priority and Size. Epics have Area and Priority but no aggregate size. Board stages are Backlog → Ready → In progress → Review → Done, with an In progress limit of three. The Blocked view uses `has:Blocker`; ordinary dependency waits stay Backlog. Iterations and dates remain unassigned until capacity is planned from observed throughput.

| Milestone | Scope |
|---|---|
| [M1 — Verified foundation](https://github.com/Protagonist01/my-production-agentic-systems/milestone/1) | Foundation epic and F1–F5 |
| [M2 — Complete Olist release](https://github.com/Protagonist01/my-production-agentic-systems/milestone/2) | Harness/Olist epics, H1–H10 and O1–O8 |
| [M3 — CFPB release](https://github.com/Protagonist01/my-production-agentic-systems/milestone/3) | CFPB epic and C1–C5 |
| [M4 — Revenue integrity release](https://github.com/Protagonist01/my-production-agentic-systems/milestone/4) | Revenue epic and R1–R7 |
| [M5 — Prior auth release](https://github.com/Protagonist01/my-production-agentic-systems/milestone/5) | Prior auth epic and P1–P6 |
| [M6 — Supply chain release](https://github.com/Protagonist01/my-production-agentic-systems/milestone/6) | Supply chain epic and S1–S6 |
| [M7 — Operations and portfolio release](https://github.com/Protagonist01/my-production-agentic-systems/milestone/7) | Operations epic, L1–L5 and H11 |

Five workflows are enabled: add matching open repository issues, add sub-issues, initialize new items in Backlog, set explicitly closed issues to Done, and return reopened items to Backlog. Auto-close from a board move, automatic Done on PR merge, and automatic status changes on PR linkage are disabled. Review and acceptance remain explicit. Close implementation issues only after checking their evidence; avoid PR closing keywords when acceptance must be checked after merge. Archive and review automations stay off.

The Project is private and linked to this public repository. Creation and updates used the signed-in browser because the connector rendered submission forms rather than applying writes. A form is not proof of success: verify server results and native saved state. Issue #25's connector edit remains pending; its actual milestone assignment is verified independently.


## O3 + C2 batch

The user selected O3+C2 after verified main2988428. Root owns both issue-sized branches: O3 reuses the existing c1-cfpb-import checkout on codex/o3-refund-policy; C2 uses the separate managed c2-risk-baselines checkout. O3 owns Olist policy, case preparation, tests and chapter; C2 owns CFPB review/baselines, tests and chapter. Shared planning/index/Build Book appends require reconciliation after the first reviewed merge. Entry26 is O3; Entry27 is C2. Retain complete journal history. Raw/private source records and per-case labels stay external.

The user accepted a constructed full-refund-only SIM policy capped at100.00; missing/conflicting facts, over-cap and reship require review. Olist's actual currency stays unknown. The user asked Codex to label the twelve-case CFPB blind batch. Those judgments are explicitly AI-reviewed/provisional; no human/adjudicated labels or agreement evidence is invented. Baselines use development-only fitting, show split/slice denominators and preserve uncertain cases. Neither task authorizes live provider calls, business writes or release promotion. O4/C3 stay Backlog until prerequisite user merge and verification. Native project-board state remains unverified.


## Authorized O4 + O5 delivery bundle

The user approved one PR for scoped transactional refund tools (#29) and the dependent LangGraph workflow (#30). Both use `codex/o4-o5-refund-workflow` in the existing managed c1-cfpb-import checkout, based on verified O3 main `de04a96`. O4 is verified inside the same review bundle before the O5 delivery rather than requiring an intermediate user merge. One primary `Refs #29` satisfies contribution metadata; the body also links #30. Both issues remain open in Review until user merge and post-merge acceptance. C2 #84 remains independent; preserve Entry27 when reconciling journal/planning appends.

Reuse unchanged pinned source stores and previous exact-source evidence. Perform one final complete integrated offline check, the required database suite, package checks and one hosted matrix at the final head; repeat only checks affected by new failures/changes. No live provider calls, real payment writes or release promotion are authorized. Source-backed tests use declared hybrid SIM facts and explicit offline intent. O6 reviewer approvals, O7 authentication/API/UI and O8 complete release acceptance remain Backlog. Native project-board transitions are unverified.


## Authorized O6 + O7 delivery bundle

The user approved one PR on `codex/o6-o7-review-console`, based on verified #85 main `e11290a`. O6 consent/recovery is implemented before O7 API/UI acceptance within this bundle. Both issues enter Review together and remain open until user merge and main acceptance. One primary `Refs #31` accompanies a link to #32. Local pre-provisioned accounts use opaque server-side sessions; the 100.00 SIM cap and missing/conflicting-fact rules are unchanged. Approval cannot override eligibility. [Commands and limits](olist-console.md), [source study](code-study-olist-console.md), Build Book Entry29 and the aggregate source drill preserve evidence. C2 #84 stays a separate review; O8 complete release scoring/fresh repeated trials remains Backlog. No live provider or real payment is authorized.


## Higher-throughput batch after #86

The user explicitly authorized up to three parallel agents plus integration: O8 offline release/state evidence, R1 original-contract preparation and independent reconciliation of existing C2#84. O8/R1 use separate owned paths/worktrees and consolidate into one new review candidate on `codex/o8-release-evidence`; #84 remains a separate existing review. Root configuration, lock, planning, study indices and Build Book have one integrator. Each worker verifies its changed behavior with focused checks; the final integrated candidate receives one complete local/database/package/hosted pass. Repeat a completed broad check only when changes/failures invalidate it. Reuse exact unchanged evidence after a documentation-only reconciliation or identical-tree merge.

Main job timings show the slowest quality cell took213seconds, including16seconds setup and174seconds checks; no speed multiplier is promised. Improve throughput through parallel independent work and fewer serialized review/retest cycles while preserving required checks and user merge control. Preflight source/licensing/labels and decisions while code progresses. Keep at most three implementation streams active and surface concrete blockers promptly.

O8 fresh held-out provider results, baseline/threshold review and first-release acceptance remain pending by explicit user choice to stay offline. An offline report or three repeated fake-planner executions cannot satisfy that gate. R1 source-family/label coverage must disclose inference and unsupported billing fields. No live provider/payment/deployment is authorized.


## Three-issue Revenue delivery

R2/R3/R4 share `codex/r2-r3-r4-revenue-engine` from verified058d1c7. Two isolated Revenue workers own fixture contracts and reconciliation/extraction; the shared access worker preserves Olist wire/policy behavior and adds only the demonstrated common exact-scope mechanism. Root integrates shared planning, journal, navigation and final acceptance once. The user-approved SIM billing policy and safe unsupported cases are documented in Build Book Entry31. Prerequisite R2 verification occurs inside the explicitly authorized bundle before R3/R4 acceptance; source R1 is merged/verified. No actual invoice mutation or release promotion is included.


The combined R2/R3/R4 candidate is ready for final acceptance and user review. Its current source and offline aggregate are linked from the Revenue runbooks; final local/database/hosted results are maintained on #40/#41/#42. Keep all three issues open until user merge and exact-main verification. Provisional fixture agreement, scripted original extraction and strict replay do not satisfy fresh domain release gates. Certifi's new advisory was repaired before acceptance, with an explicit reviewed-content v5 invented replay capture for the changed environment lock.


## Authorized R5 + R6 + S1 batch

The user selected R5#43/R6#44/S1#52 after verified main5f73fc9 and closure of R2/R3/R4. Revenue transactions and the dependent review UI/events are verified inside one bundle; independent shipping/weather source preparation runs in parallel. Root integrates on codex/r5-r6-s1-operations. The approved absolute correction cap is100.00SIM with no approval override, separate reviewer, automatic outer-whitespace CRM-note trimming only and approved conflict-safe compensation. Build Book Entry32 records construction decisions and source/privacy limits. R7 remains pending offline release prerequisites; no live provider, real billing operation or release promotion is authorized. C2#84 remains a separate unmerged review.


## S2 + S3 + S4 batch

The user selected #53/#54/#55 after merging #89 as main77b98df, identical to reviewed0bdc7eb. Work is isolated on codex/s2-s3-s4-supply-chain. They approved SIM100.00/action,500.00/incident, separate review above25.00,30-minute approval/confirmation limits, two stale supersessions and blocked missing/stale facts. Source choice was delegated with eventual production in mind: use independent invented worlds with unseen holdout families/formulas and a separately labeled S1 observation adapter, without manufacturing historical weather causality. SQL owns budget, approvals, receipts and confirmation outcomes; frameworks provide bounded assessment/wakeups. No paid provider, real carrier effect, deployment or release promotion is authorized. S5/S6 remain later work; keep these issues open until user merge and verified acceptance. Native project-board status unverified.


## S5-only follow-up

The user merged #90 and selected S5 #56 only, with durable in-app notices and previews. Main21d3bef matched the reviewed tree and its nine applicable checks passed; #53/#54/#55 are complete. S5 review is #91 on codex/s5-supply-console. Approval policy is unchanged. S6 #57 remains behind O8 fresh-release acceptance. No external message delivery, paid provider or deployment is authorized.


## Authorized P1/P2/P3 batch

User merged #91, verified main1e59722/CI39881820867; S5#56 is complete. The user selected the next independent batch and approved #46/#47/#48 together, with prerequisites delivered/verified inside the bundle. Source mix: CMS national initial-CPAP policy, published Synthea illustrative records, explicit edits and invented edges. Labels remain AI-provisional; no qualified review is invented. User superseded offline-only for this batch and explicitly authorized reuse of existing Gemini free-project settings. Fresh candidate assessment uses the shared bounded gateway; no paid fallback, real patient data, authorization effect, deployment or release promotion. S6/O8 gates and separate unmerged C2#84 remain unchanged. Build Book Entry35 and the prior-auth evidence chapter track actual results.

P1/P2/P3 review is [PR #92](https://github.com/Protagonist01/my-production-agentic-systems/pull/92).
Frozen v3 matched all six held-out cases and all six development cases against provisional
labels in separate 42-request fresh runs. Local 881-test regression and initial ten-job hosted
acceptance passed. That review is now merged/verified and all three issues are closed completed; this does not
satisfy P6 clinical/domain release acceptance.


## Authorized P4/P5 document-review batch

The user selected #49/#50 together after #92 merge verification. Branch codex/p4-p5-prior-auth-review reuses the isolated D-drive checkout. Postgres owns document receipts, exact note/policy versions, waits, lease recovery and fixed review events; the protected loopback desk serves explicitly reviewed redacted evidence. Fresh model checks use the previously approved Free Gemini configuration through shared controls, without paid fallback. P4 verification occurs inside the authorized bundle before P5 acceptance. First29focused/7Postgres checks and full886-test regression passed. Temporary probe scripts initially lacked Windows main guards; their startup failures do not establish provider dispatch. A corrected one-request redacted education-only Gemini check passed, separately from the earlier P3 holdout. An actual Edge UI-only fixture passed document/routing/viewer and390px layout checks; real local SQL/browser continuation remains interrupted by host disk pressure/Docker unresponsiveness. The user is clearing space while packaging/hosted checks continue. No release promotion or real clinical action.
