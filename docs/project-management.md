# Project management

Updated: 2026-10-14. This is the delivery plan for the real application. F1/O1/F2 are merged and verified on main b46cf25. F3 portable commands and the updated study guide are prepared for review. Provider-backed/domain runtime and actual CI jobs remain unimplemented.

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

[F1 #10](https://github.com/Protagonist01/my-production-agentic-systems/issues/10) and [O1 #26](https://github.com/Protagonist01/my-production-agentic-systems/issues/26) are closed as completed. F1 merged through #63; O1 #64 merged into the former foundation branch, then [integration PR #65](https://github.com/Protagonist01/my-production-agentic-systems/pull/65) carried it into main a665d3d. Post-merge locked installation, 16 tests, both import contracts, Ruff and authentic-source verification passed. [F2 #11](https://github.com/Protagonist01/my-production-agentic-systems/issues/11) is closed as completed after the user reviewed/merged [PR #66](https://github.com/Protagonist01/my-production-agentic-systems/pull/66) and a clean merged-baseline installation/check passed 43 tests, strict types, lint/format and imports. [F3 #12](https://github.com/Protagonist01/my-production-agentic-systems/issues/12) owns codex/f3-command-entrypoints: one [portable command path](development-commands.md), locked mypy and the refreshed [study guide](../CODE_STUDY_GUIDE.md). The command runner passed 55 tests and the remaining checks; a fresh local clone with spaces passed setup/check/example/build from another caller directory. PR linkage follows. P1 source preparation stays Backlog until capacity is assigned. L5 #62 completed native administration. Live model evaluation and domain application behavior remain unimplemented.

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

F3 uses one attached managed worktree based on reviewed main b46cf25, with its own virtual environment/check caches. No runtime service or worker is running; database/trial/service isolation remains F4. The original checkout and its uncommitted study-guide changes were preserved; the user authorized including copies of those documents in F3.

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
