# Project management

Updated: 2026-10-11. This is the delivery plan for the real application. Runtime implementation has not started.

## Scope and source of truth

Build one shared evaluation/resilience platform and five usable industry applications. Finish a source-grounded Olist release first; retain CFPB, Revenue integrity, Prior auth and Supply chain as subsequent releases. This is a complete project backlog, not a set of disposable demonstrations.

[Backlog manifest](backlog.json) records all 53 implementation tasks and 8 epics, including dependencies and acceptance evidence. GitHub issues will become the execution record once created; the manifest is the versioned planning snapshot. Until verified issue numbers exist, null links mean pending creation. Native Projects and milestones are tracked by L5; they have not been created.

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

Start F1 and O1. P1 source preparation is independently possible but stays Backlog until capacity is assigned. Nothing is In progress or Done yet. L5 is Blocked on native board administration capability.

## Capacity and planning

The user's 40 hours/week includes pairing, implementation, review, integration, labeling and documentation. Plan no more than three active implementation tasks/worktrees and no more than two verticals under integration. Size estimates are provisional: S 2–4 hours, M 4–8, L 8–16. Split a task that grows beyond two working days. Track actual hours and blocked time before committing calendar dates.

Plan weekly: review acceptance evidence and blockers; select Ready work within available capacity; reserve time for integration/data review. Reforecast from completed work, rather than dividing total scope by nominal parallel workers. At each stage gate, inspect newly failing required cases and open defects before scheduling expansion.

P0 = foundation/first-release critical path, P1 = remaining committed product scope, P2 = later enhancement/management infrastructure. Priority is separate from dependency readiness.

## Worktrees and ownership

Create implementation worktrees only after a verified contract baseline exists in Git. Use one issue-sized branch per worktree, based on the current reviewed main. Proposed streams:

| Stream | Owned paths |
|---|---|
| Gateway | harness/gateway and associated tests/recordings |
| Evaluation | harness/evals, faults, reporting and associated tests |
| Olist | projects/olist-support, domain policy, backend and tests |

The integrator owns shared interfaces, dependency lockfiles, root commands, CI, shared migrations and the Build Book. Request changes to these through a small prerequisite PR; do not build competing shared APIs. Merge working increments, update dependent branches and verify the complete flow after integration.

Each worktree/trial needs distinct database state, service names, ports, volumes, caches and temporary paths. A Git worktree alone isolates files, not services. Share immutable sanitized fixtures where useful; never share writable trial state. Keep a common live-provider budget/queue.

No implementation worktrees or runtime workers have been started by this planning setup.

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

L5 specifies a native Project with Status, Area, Priority, Size, Iteration and Blocker fields; views for current iteration, workstream, blocked work and roadmap. Add existing issues rather than duplicate them. Proposed milestones: foundation, first Olist release, CFPB, Revenue, Prior auth, Supply chain and operations. Do not add due dates until throughput is measured. Automate closed issues to Done and merged-PR completion only when acceptance evidence is present.

The connected GitHub MCP currently exposes issues/sub-issues and repository files but no native Project/milestone creation. A connector submission form is not a created issue: verify the server result and read back the actual hierarchy before claiming setup complete.
