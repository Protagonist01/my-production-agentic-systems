# Build Book â€” Production Agent Platform
A journal of the real reasoning behind this build: decisions, options rejected, and things that broke along the way.

## Index
- [Entry 68 — Isolate development changes behind settled canaries](#entry-68--isolate-development-changes-behind-settled-canaries)
- [Entry 67 — Diagnose task mismatch before another model study](#entry-67--diagnose-task-mismatch-before-another-model-study)
- [Entry 66 — Develop on exposed failures under a schedule-bound extension](#entry-66--develop-on-exposed-failures-under-a-schedule-bound-extension)
- [Entry 65 — Size and freeze a confidence-target study](#entry-65--size-and-freeze-a-confidence-target-study)
- [Entry 64 — Freeze a prospective cohort without recycling exposed families](#entry-64--freeze-a-prospective-cohort-without-recycling-exposed-families)
- [Entry 63 — Map whitespace changes back to exact source spans](#entry-63--map-whitespace-changes-back-to-exact-source-spans)
- [Entry 62 — Test semantic answerability against publisher references](#entry-62--test-semantic-answerability-against-publisher-references)
- [Entry 61 — Budget safety does not guarantee writer availability](#entry-61--budget-safety-does-not-guarantee-writer-availability)
- [Entry 60 — Test the evaluator without hiding abstentions or weak references](#entry-60--test-the-evaluator-without-hiding-abstentions-or-weak-references)
- [Entry 59 — Make evidence and attempt plans executable without granting approval](#entry-59--make-evidence-and-attempt-plans-executable-without-granting-approval)
- [Entry 58 — Evidence alternatives without inventing expert approval](#entry-58--evidence-alternatives-without-inventing-expert-approval)
- [Entry 57 — Explicit Groq routes without disguising a provider change](#entry-57--explicit-groq-routes-without-disguising-a-provider-change)
- [Entry 56 — Zero elapsed time is a valid coarse-clock observation](#entry-56--zero-elapsed-time-is-a-valid-coarse-clock-observation)
- [Entry 55 — Shutdown evidence without collecting request identities](#entry-55--shutdown-evidence-without-collecting-request-identities)
- [Entry 54 — Local service health and restore without overwriting live state](#entry-54--local-service-health-and-restore-without-overwriting-live-state)
- [Entry 53 — Fixed release denominators for prior auth and shipment simulation](#entry-53--fixed-release-denominators-for-prior-auth-and-shipment-simulation)
- [Entry 52 — Release paths, scoped observations and durable provider accounting](#entry-52--release-paths-scoped-observations-and-durable-provider-accounting)
- [Entry 51 — Closure work and blind reviewer handoff](#entry-51--closure-work-and-blind-reviewer-handoff)
- [Entry 50 — Deterministic baselines without invented dispatch receipts](#entry-50--deterministic-baselines-without-invented-dispatch-receipts)
- [Entry 49 — Independent durable-state evidence across three release issues](#entry-49--independent-durable-state-evidence-across-three-release-issues)
- [Entry 48 — Recording domain dispatch and real process-crash evidence](#entry-48--recording-domain-dispatch-and-real-process-crash-evidence)
- [Entry 47 — Preparing three release evaluators together](#entry-47--preparing-three-release-evaluators-together)
- [Entry 46 — Sealing parent-measured trial latency](#entry-46--sealing-parent-measured-trial-latency)
- [Entry 45 — Recording Olist trials through H10](#entry-45--recording-olist-trials-through-h10)
- [Entry 44 — Waiting for exit status after sentinel readiness](#entry-44--waiting-for-exit-status-after-sentinel-readiness)
- [Entry 43 — Serializing owned process bookkeeping](#entry-43--serializing-owned-process-bookkeeping)
- [Entry 42 — Observing domain fields and controlled recovery](#entry-42--observing-domain-fields-and-controlled-recovery)
- [Entry 40 — Measuring Olist attempt startup and reconciling usage](#entry-40--measuring-olist-attempt-startup-and-reconciling-usage)
- [Entry 41 — Separating pilot success from evaluation qualification](#entry-41--separating-pilot-success-from-evaluation-qualification)
- [Entry 39 — Repairing a dependency audit after merge](#entry-39--repairing-a-dependency-audit-after-merge)
- [Entry 37 — Typed CFPB triage and scoped review](#entry-37--typed-cfpb-triage-and-scoped-review)

- [Entry 1 â€” Proposed execution and evidence boundaries](#entry-1--proposed-execution-and-evidence-boundaries)
- [Entry 2 â€” Real-source data before the first complete demo](#entry-2--real-source-data-before-the-first-complete-demo)

- [Entry 3 â€” From design notes to a dependency-driven delivery backlog](#entry-3--from-design-notes-to-a-dependency-driven-delivery-backlog)

- [Entry 4 â€” Recovering from an invisible connector form](#entry-4--recovering-from-an-invisible-connector-form)
- [Entry 5 â€” Creating the native delivery project](#entry-5--creating-the-native-delivery-project)
- [Entry 6 â€” Establishing installable package boundaries](#entry-6--establishing-installable-package-boundaries)
- [Entry 7 â€” Pinning authentic Olist source evidence](#entry-7--pinning-authentic-olist-source-evidence)
- [Entry 8 â€” Integrating the first wave and defining shared contracts](#entry-8--integrating-the-first-wave-and-defining-shared-contracts)
- [Entry 9 â€” Adding a current-code study guide](#entry-9--adding-a-current-code-study-guide)
- [Entry 10 â€” Giving Windows and CI one command path](#entry-10--giving-windows-and-ci-one-command-path)
- [Entry 11 â€” Isolating local Postgres services and trial state](#entry-11--isolating-local-postgres-services-and-trial-state)
- [Entry 12 â€” Turning portable checks into hosted CI](#entry-12--turning-portable-checks-into-hosted-ci)
- [Entry 13 â€” Selecting a free provider and local trace integration](#entry-13--selecting-a-free-provider-and-local-trace-integration)
- [Entry 14 â€” Moving Gemini calls behind the shared gateway](#entry-14--moving-gemini-calls-behind-the-shared-gateway)
- [Entry 15 â€” Preserving calls without turning replay into a cache](#entry-15--preserving-calls-without-turning-replay-into-a-cache)
- [Entry 16 â€” Reserving shared capacity before bounded attempts](#entry-16--reserving-shared-capacity-before-bounded-attempts)
- [Entry 17 â€” Pinning case membership and independent scorers](#entry-17--pinning-case-membership-and-independent-scorers)
- [Entry 18 â€” Accounting for isolated trials even when execution fails](#entry-18--accounting-for-isolated-trials-even-when-execution-fails)
- [Entry 19 â€” Reproducible faults at explicit execution boundaries](#entry-19--reproducible-faults-at-explicit-execution-boundaries)
- [Entry 20 â€” Safe correlated telemetry](#entry-20--safe-correlated-telemetry)
- [Entry 21 â€” Distinguishing cancellation and cold worker startup](#entry-21--distinguishing-cancellation-and-cold-worker-startup)

- [Entry 22 â€” Reporting every scheduled outcome](#entry-22--reporting-every-scheduled-outcome)

- [Entry 23 â€” Fresh dispatch receipts and independently reviewed releases](#entry-23--fresh-dispatch-receipts-and-independently-reviewed-releases)

- [Entry 24 â€” Parallel source preparation and honest historical order views](#entry-24--parallel-source-preparation-and-honest-historical-order-views)

- [Entry 25 â€” Archive-grounded CFPB preparation in parallel](#entry-25--archive-grounded-cfpb-preparation-in-parallel)

- [Entry 26 â€” Constructed policy and review evidence before domain baselines](#entry-26--constructed-policy-and-review-evidence-before-domain-baselines)

- [Entry 27 — Blind provisional risk review before deterministic baselines](#entry-27--blind-provisional-risk-review-before-deterministic-baselines)

- [Entry 28 — Transactional refunds and a bounded LangGraph workflow](#entry-28--transactional-refunds-and-a-bounded-langgraph-workflow)

- [Entry 29 â€” Exact-action approval behind a scoped local console](#entry-29--exact-action-approval-behind-a-scoped-local-console)
- [Entry 30 â€” Parallel release evidence and original contract preparation](#entry-30--parallel-release-evidence-and-original-contract-preparation)
- [Entry 31 â€” Three Revenue tasks behind explicit simulation rules](#entry-31--three-revenue-tasks-behind-explicit-simulation-rules)
- [Entry 32 â€” Approved Revenue effects and independent shipping sources](#entry-32--approved-revenue-effects-and-independent-shipping-sources)
- [Entry 33 — Independent shipping worlds and durable budgeted intervention](#entry-33--independent-shipping-worlds-and-durable-budgeted-intervention)

- [Entry 34 — Scoped shipping workbench and durable factual notices](#entry-34--scoped-shipping-workbench-and-durable-factual-notices)
- [Entry 35 — Source-grounded prior-auth evidence with fresh model evaluation](#entry-35--source-grounded-prior-auth-evidence-with-fresh-model-evaluation)
- [Entry 36 — Durable prior-auth document review](#entry-36--durable-prior-auth-document-review)
- [Entry 38 — Fresh Olist review evidence after the offline pilot](#entry-38--fresh-olist-review-evidence-after-the-offline-pilot)

## Entry 1 â€” Proposed execution and evidence boundaries

Date: 2026-10-09 (Africa/Lagos). Status: proposal only; implementation has not started.

**Files touched:** `docs/01-execution-and-evidence-proposal.md`, `BUILD_BOOK.md`.

### Context

The user asked how multiple worktrees could tackle the project, how replay should be bounded, and which metrics withstand a skeptical reviewer. They clarified that the base targets general AI engineering, all five verticals support specialized applications, and they can spend 40 hours/week building together with the assistant. The workspace has only plans and Makefile templates, with no Git metadata, application runtime code or tests.

### Before you read on

If three workers implement a gateway, evaluation runner and refund agent concurrently, which interfaces must they share before they start? How would you prevent a replayed refund tool response from hiding a broken write adapter?

### Options considered

- One independent worktree per industry immediately: considered but not recommended for the first wave, because all five would design against an unimplemented harness and access layer.
- Finish the whole platform before any vertical: considered but not recommended, because mechanisms could grow without evidence that an actual workflow needs them.
- Recommended: agree minimal contracts, build gateway/evaluation/Olist in three bounded streams, and have one integrator prove the complete workflow. Preserve all five verticals in later waves.

### Why

Separate branch checkouts reduce file interference, but they cannot make incompatible interfaces work together or isolate running databases. Olist provides a compact example of code-enforced policy, real state change, timeout-after-commit and crash recovery. The proposal distinguishes recorded software verification from newly sampled model-quality evidence, and completion from handoff, so useful behavior cannot be confused with a safe stop.

### How to build it

1. Read the execution proposal and agree the contract fields before implementing. Create Git history and a locked Python scaffold. Give the integrator ownership of root dependencies and `harness/interfaces.py`.
2. Define `RunContext`, complete model request/response shapes, `EvalCase`, `AgentResult`, `ScoreResult` and `FaultScenario`. Provide fakes. Verify one case can run without a network: fake response -> decision -> mock state -> deterministic scorer -> report.
3. Branch three worktrees from this reviewed contract commit. Gateway owns model transport and recordings; evaluation owns case accounting, fault injection and reporting; Olist owns refund rules and mock writes. Use separate databases, ports, caches and environments.
4. Give strict replay an exact request matcher and no network fallback. Test a matching request, then alter its prompt or schema and require a missing-fixture failure. Fresh recording must bypass previous response reuse and keep each trial's responses separately.
5. Execute mock writes during replay. To test a timeout after commit, have the backend record a refund and then raise a timeout. Retry using the same stable business operation key; assert one refund row and the original result. Retry in a new run with the same event identity to catch run-ID-based deduplication mistakes.
6. Before scoring, reset state per case/trial. Score actual final order/refund state. An agent that merely claims a refund must fail. An agent that escalates every case must score zero autonomous completions on the pre-labeled eligible set.
7. Add fresh candidate experiments when behavior changes. Bind reports to manifests and preserve a separately reviewed baseline. Compare required cases individually, because an improved average can conceal a new critical failure.
8. Report `0/N observed` violations, eligible-case completion, unnecessary/required handoff, fault recovery outcomes and repeated-trial correctness. Establish numeric quality floors after a baseline and before candidate comparison. Do not claim real industry outcomes from a simulator.

None of these runtime tests has been executed yet. They are acceptance criteria for implementation, not reported successes.

### What went wrong

Read-only inspection found two planning gaps: CFPB/Olist detailed plans are linked but absent, and the revenue milestone table totals 176 hours versus the 142-172-hour headline. PowerShell summed the ten milestone-hour rows to verify the latter. `git rev-parse --is-inside-work-tree` failed because no Git repository exists. These findings mean the foundation must be established before implementation worktrees can be created.

The original replay claim also overreached: recording model calls alone cannot reproduce mutable reads, writes, clocks or event schedules. The proposal narrows the guarantee to captured dependencies and deterministic scheduling and leaves live latency/quality measurement to fresh runs. The calculation `1 - 0.05^(1/100)` yielded 2.9513%, illustrating why zero observed failures is limited evidence rather than proof of zero risk.

## Entry 2 â€” Real-source data before the first complete demo

Date: 2026-10-09 (Africa/Lagos). Status: proposed, not implemented. Extends Entry 1 by making source ingestion part of the first vertical's acceptance criteria.

**Files touched:** `docs/02-data-and-architecture-comparison.md`, `BUILD_BOOK.md`.

### Context

The user asked how real data fits into the proposal and what implementation/architecture changes from the initial plans. The previous worktree split emphasized the runtime and mocks; it did not make real-data acquisition explicit enough. Source verification also exposed different evidence quality across the verticals.

### Before you read on

If we seed a mock refund backend from a real historical order, which facts could the agent know at the time of the customer's request? Where should the future delivery timestamp and expected refund decision live?

### Options considered

- Treat all public datasets as real operational ground truth: rejected because published examples, generated CRM data and independent historical sources do not establish task-specific decisions or causal outcomes.
- Use synthetic fixtures until all agents are built: rejected for the complete-demo milestone because runtime correctness alone does not establish behavior on the selected real sources.
- Recommended: build runtime components against fakes in parallel, but require source acquisition, validated agent-visible views and independent evaluation cases before the first complete Olist demo.

### Why

A mock API can expose source-grounded records and safely record actions without making the source data fictional. Separating original, hybrid and generated examples allows the project to prove reading authentic documents and safely executing simulated actions without blending those two claims. The original thin-harness architecture remains; we make the data/evidence boundaries explicit.

### How to build it

1. Add a source manifest with publisher URL, snapshot timestamp, checksum, schema, coverage, use conditions and limitations. Keep the raw source immutable outside Git.
2. For Olist, import orders, items and payments. Aggregate item/payment totals at the intended grain before joining to avoid row multiplication. Check keys, totals, currency and missing fields against the source tables.
3. Build each case with an as-of timestamp. Expose only record facts known then; keep later delivery/review observations in the evaluation data when they are used to construct the scenario. Store generated message/policy versions and source row IDs in the case manifest.
4. Put expected outcomes in scorer-only tables. For CFPB, do not expose target category fields to the classifier. For contract extraction, split whole contracts/template families rather than fragments of the same source across development and holdout.
5. Maintain separate original-source extraction, hybrid workflow and synthetic/adversarial reports. Require independently reviewed expected examples instead of using the same production reconciler/aggregator as the sole label oracle.
6. Run the first refund workflow on the validated view and an isolated mock write ledger. Verify source provenance and final state in addition to a passing software test.

These checks are planned. No data importer or runtime test has run, and no source dataset has been downloaded locally in this work.

### What went wrong

The planning index categorizes Maven CRM opportunities as real data. Maven's own source describes a fictitious hardware company, so the comparison document corrects the evidence claim. BTS describes passenger-airline on-time data, so treating it as freight-lane reliability would overstate applicability; the proposal makes it an optional aviation-proxy experiment. Public sample transcriptions and coverage policies also require independently constructed note-policy labels, not an assumption that prior-authorization outcomes are provided.

No runtime bug was diagnosed here. The verified evidence is the publisher descriptions and local planning files; downloaded schema/content quality remains untested.


## Entry 3 â€” From design notes to a dependency-driven delivery backlog

Date: 2026-10-11 (Africa/Lagos). Status: delivery documentation prepared; issue/board creation awaits verified server results. Supersedes the proposal-only execution status in Entries 1â€“2; their runtime checks remain unexecuted.

**Files touched:** `README.md`, `docs/project-management.md`, `docs/backlog.json`, architecture/vertical plans, contribution and issue/PR templates.

### Context

The user created my-production-agentic-systems and asked for a real project breakdown and GitHub management. The repository was initially empty. Its README was created on main in commit e50840d8ae2d655a6eac90ec2c65896a6f385944. The first issue-write request displayed a connector submission form and returned no created issue; a read-back on this resumed turn found zero issues.

### Before you read on

How do you represent task dependencies separately from delivery epics so source acquisition can start without waiting for an entire platform to finish?

### Options considered

- A native Project with milestones alone: desirable views, but the connected MCP exposes neither creation capability.
- Chosen: versioned backlog plus native root/epic/task issue hierarchy, with explicit prerequisite links. Track native Project setup as L5 and verify each created issue before recording its URL.

### Why

Hierarchy expresses ownership and deliverables; prerequisites express what can start. Keeping those separate allows Olist acquisition to proceed alongside foundation work. Acceptance checks keep a planning artifact from being mistaken for implementation.

### How to build it

1. Store eight epic records and 53 task records. A task carries id, area, scope, deps, priority, provisional size, acceptance checks, status and a nullable GitHub issue number.
2. Validate IDs are unique, every dependency exists and a depth-first traversal has no cycle. Set F1/O1 Ready; leave later tasks Backlog and L5 Blocked on board capability.
3. Create one root issue, then epic children, then task children. Use actual issue numbers for parent_issue_number; prerequisites belong in bodies, not parent relationships.
4. After each successful server result, save its issue number. If the connector displays a submission form, stop; a rendered form does not create an issue. Read back the hierarchy before marking setup complete.
5. Publish the manifest and delivery rules with contribution/issue/PR templates. Update nullable issue links only after verified creation. Use merged PR plus acceptance evidence as Done.
6. After F2 verifies the contract baseline, create issue-sized worktrees for gateway, evaluation and Olist; isolate writable state and give shared files one integrator. No worktrees are started during this planning step.

The dependency and documentation checks are performed as part of this setup; runtime/model/data tests are not. Issue creation, native board creation and completed code cannot be inferred from a document commit.

### What went wrong

The initial issue tool returned an explicit stop-and-submit form response. No issue existed on read-back. Native Project/milestone tools were also absent. We preserved the prepared breakdown, published its reviewable definition and retained the administration task rather than claiming a board or implementation was complete.

## Entry 4 â€” Recovering from an invisible connector form

Date: 2026-10-11 (Africa/Lagos). Status: local checkout connected; GitHub issue/Project setup awaiting browser authentication.

**Files touched:** local Git metadata, `BUILD_BOOK.md`, execution-plan status.

### Context

The user confirmed that the connector's reported submission form was not visible. A list_issues read returned zero issues. Browser automation is now available, but the GitHub page is signed out. The issue form's failure is a connector interaction problem, not evidence of an issue or completed setup.

### Before you read on

Which parts of repository setup can be completed without treating a nonexistent confirmation as approval or changing permission settings?

### Options considered

- Retry the same issue request: it had already returned the same form response twice without creating an issue.
- Chosen: retain the published backlog, open the real GitHub sign-in page for user authentication, and prepare the local checkout independently. No plugin permission settings are changed.

### Why

The browser can expose native issue and Project administration after authentication. Connecting the local folder to the public Git history needs no new credential and preserves existing planning files. Native board and issue creation remain unverified until the authenticated workflow completes.

### How to build it

1. Query repository issues; the server returned totalCount 0.
2. Use browser inventory and open the repository issues page. Its Sign in link and zero open issues confirm the unauthenticated state. Open that link and leave the tab for the user to authenticate.
3. In the planning directory, run `git init -b main`, `git remote add origin https://github.com/Protagonist01/my-production-agentic-systems.git` and `git fetch origin main`.
4. Run `git reset --mixed origin/main` to set HEAD/index while preserving all local file contents. Set upstream using `git branch --set-upstream-to=origin/main main`.
5. Inspect `git status --short` and `git log -1`. HEAD was b7cab34494647bb56ff7d631a04cd6b1ec25edfa; tracked files matched. Original Makefile/templates, SVG and archived design notes remained untracked and intact.
6. Resume issue creation only after browser authentication. Reuse any existing verified issues and populate links after read-back. No Python package, database or worktree implementation is implied by creating Git metadata.

### What went wrong

The connector claimed a submission form had been shown, but the user could not see it; two issue-write attempts produced no created issue. The browser provided a visible alternative but required user sign-in. CLI gh was absent. We did not change account/plugin permissions or claim that setup was finished.

## Entry 5 â€” Creating the native delivery project

Date: 2026-10-11 (Africa/Lagos). Status: native issue hierarchy, milestones and Project created; field population and workflow verification underway.

**Files touched:** delivery plan, backlog manifest, README and Build Book. **Remote artifacts:** [Project 2](https://github.com/users/Protagonist01/projects/2), [root issue 1](https://github.com/Protagonist01/my-production-agentic-systems/issues/1), issues 2â€“62 and milestones 1â€“7.

### Context and decision

After the user signed in, the browser exposed GitHub's native administration controls. Use one root tracker, eight epic children and 53 task children, preserving the manifest IDs. This gives each implementation PR a bounded task while keeping dependencies separate from the parent hierarchy. Keep the Project private as created and leave due dates empty until measured throughput supports dates.

### How to build it

1. Read the existing issue list before creation to avoid duplicates. Create the delivery tracker, then the eight epics; attach each epic as a native sub-issue of the tracker.
2. Create each task with scope, prerequisite issue links, provisional priority/size, acceptance checkboxes and completion evidence. Attach it beneath its epic. Read the hierarchy back: F 5, H 11, O 8, C 5, R 7, P 6, S 6 and L 5 tasks; total 62 issues including root and epics.
3. Create seven milestones: foundation, Olist, CFPB, Revenue, Prior auth, Supply chain and operations. Assign the core harness to Olist; assign H11's later fallback enhancement to operations.
4. Create a user-owned Project using the Team planning template and import the repository's existing 62 issues. Rename Todo to Backlog; add Ready and Review plus Area and Blocker fields. Retain Priority, Size and Iteration.
5. For the Backlog table, turn hierarchy off and grouping off so all tasks are visible. Show milestone and parent issue alongside delivery fields. Save the view through GitHub's explicit Save display options dialog.
6. Populate fields from the versioned manifest. Set F1 Ready and prepare O1 Ready; later prerequisites remain explicit. Verify milestone assignments with server reads as well as the table.

### Diagnosis while working

The connector's update operation also rendered a submission form rather than performing the edit; issue 25's connector edit remains pending. Independent Project administration continued through the already authorized browser. Some table snapshots briefly showed blank fields after successful saves; server issue reads confirmed milestones for H1, H9, O1 and C1. Longer browser batches timed out and reset bindings. Reconnect to the existing tab, inspect the current filter, and resume from the first unfinished task rather than creating duplicates. Use bounded batches and read saved state before claiming completion.

Runtime implementation and implementation worktrees have not started. Final verification and the completed administration evidence will be appended below when available.

### Verification and completion

The table used asynchronous filtering and saves. A complete server read found the Revenue epic (#6) and reuse task R3 (#41) on the CFPB milestone. Corrected both through the visible milestone picker and read them back: both now belong to M4. Do not treat a click or an immediate table snapshot as confirmation; wait for the selected state and compare the saved value with the manifest.

All 53 task rows were read in eight Area-filtered batches and compared with the manifest: Area, Priority, Size and milestone matched. The local validator checked 53 unique tasks, all 61 epic/task issue mappings and an acyclic dependency graph. Missing Size/Area/Priority filters initially returned only the nine aggregate root/epic rows; epics subsequently received Area/Priority/milestones and intentionally retain no Size. The root tracker spans the project and intentionally has no Area/milestone.

Configured Board stages Backlog â†’ Ready â†’ In progress â†’ Review â†’ Done; removed the template's five-item Backlog limit and set In progress to three. Saved By workstream with Area grouping and hierarchy off; saved Blocked with `has:Blocker`, hierarchy off, Area and Blocker columns. Seven views exist. Dates and iteration assignments remain empty pending capacity planning.

Five workflows are enabled: repository open-issue intake, sub-issue intake, initial Backlog, explicitly closed issues â†’ Done, and reopened items â†’ Backlog. Disabled merge â†’ Done, Done â†’ automatic closure, and PR-link status changes; left archive/review automations off. Explicit closure still requires the human/integrator to inspect acceptance evidence. Updated and pinned tracker #1 with the actual Project URL and epic links. H11's O8 dependency is #33, clarified in the tracker and manifest while its connector edit remains pending.

L5 is an administrative task. Its completion evidence is this verified configuration and the published documentation commit, rather than an application implementation PR. F1 #10 and O1 #26 remain Ready. No application work is marked complete.

Published the planning snapshot in [commit 311e807](https://github.com/Protagonist01/my-production-agentic-systems/commit/311e80733e76bd6b9ce857073294000d43be8878). Updated #62 with checked acceptance evidence and the commit link, then closed it. A server read confirmed `state: closed`, `state_reason: completed`; the native closure workflow moved it to Done. Final Board counts: Backlog 59, Ready 2, In progress 0/3, Review 0, Done 1. Restored the unfiltered Backlog after the audit so temporary filters do not hide tasks. The saved board screenshot shows the two Ready tasks and the WIP limit.

Refetched main and used a mixed reset to align local HEAD/index with the documentation commit while preserving the original untracked plans. `git diff --check` passed and no tracked differences remained. Verification covers project administration and planning consistency; no runtime test was run because runtime code does not yet exist.

## Entry 6 â€” Establishing installable package boundaries

Date: 2026-10-12 (Africa/Lagos). Task: F1 #10. Branch: `feat/f1-python-foundation`. Status: implementation and verification underway.

**Files touched:** root/member `pyproject.toml`, `uv.lock`, `.python-version`, `.importlinter`, `.gitignore`, `.env.example`, six source packages, tests and README.

### Context

The user authorized the first build. The checkout contained only plans, and uv 0.11.1/Python 3.13.4 were already installed. F1 must establish reproducible installation and enforce architecture before parallel implementation branches begin. The existing untracked templates/archive remain intact.

### Before you read on

How can six packages share dependency versions without allowing the generic harness to depend on domain code, or allowing one domain to depend on another?

### Options considered and why

A single distribution could include every domain, but then installing the harness would also install all domain packages. Separate environments would lose the shared dependency baseline. Chosen: a virtual uv workspace root, six independently installable members and one lockfile. uv documents that a workspace alone cannot enforce import isolation, so use Import Linter contracts as a separate executable check.

### How to build it

1. Create a virtual root `pyproject.toml` with workspace members `harness` and `projects/*`. Define the shared distribution as a workspace source so vertical dependencies resolve locally. Use `>=3.12,<3.14` as the allowed interpreter range and `.python-version` 3.13 for the interpreter exercised here; compatibility with future SDKs remains H1 work.
2. Each member has its own build metadata and `src/<import_name>/__init__.py`. The distributions import as `agent_harness`, `olist_support`, `cfpb_triage`, `revenue_integrity`, `prior_auth` and `supply_chain`. Verticals declare only `production-agent-harness`; the harness declares no runtime dependencies yet.
3. Use the uv build backend, constrained to its 0.13 series. Add pytest, Ruff and Import Linter to the development group and resolve `uv.lock`. Sync all members for development; later verify a clean environment separately.
4. Configure two import contracts: the harness is forbidden from importing any domain; the five domains are independent. Keep type-checking imports in the graph. Test both legitimate domain-to-harness imports and prohibited direct, relative/indirect and cross-domain paths using isolated temporary package copies.
5. Ignore environments, credentials, raw CSV/Parquet/archive data and generated experiment outputs. `.env.example` holds empty future configuration names, not working integrations. README lists only commands verified at this stage.

### Verification in progress

The initial dependency resolution succeeded. Next: install all members, run the real boundary checker and deliberately failing cases, check distribution builds and repeat installation in a clean environment. No provider, database, workflow or evaluation result is implemented by the scaffold.

### What went wrong during verification

The first negative tests exposed a test-runner bug: `python -m importlinter.cli` exits successfully without invoking the CLI. Every bad import falsely returned success, while the positive test caught the missing contract output. Inspected the installed CLI and console entry point; changed the subprocess to explicitly call `importlinter.cli.lint_imports()`. Keep both a permitted import and deliberately prohibited imports in these tests so an inert checker cannot be mistaken for passing architecture. The production `lint-imports` command itself already reported two kept contracts.

Calling `lint_imports()` next printed the violations but returned without setting a failure process status. The installed console entry-point metadata identifies `lint-imports` as `importlinter.cli:lint_imports_command`; use that exact command wrapper so broken contracts produce a nonzero process status. The negative assertions remain unchanged.

The initial uv_build 0.13 series could produce wheels, but uv 0.11.1 failed while unpacking its source archive with `malformed pax extension`. Rather than changing the user's installed tool, pinned each member's backend to `uv_build==0.11.1`, matching the exercised runner. All six source archive â†’ wheel builds then passed. This replaces step 3's initial 0.13-series selection. Source/binary distribution artifacts remain ignored.

### Verified results

On Windows/Python 3.13.4/uv 0.11.1: 12 pytest checks passed; both import contracts kept; Ruff lint and formatting passed; six source archives and six wheels built. A new temporary virtual environment installed the locked workspace and imported all six members. A clean harness-only installation is checked separately before publication. Static imports are covered; reflective imports are an explicit limitation, not a security claim. No model evaluation, database isolation or CI pass is implied by these foundation checks.

The separate harness-only sync installed exactly the shared member and confirmed `find_spec('olist_support') is None`. F1 was pushed in commit c91df0f and [PR #63](https://github.com/Protagonist01/my-production-agentic-systems/pull/63) was created through the signed-in browser after the user confirmed the connector form was invisible. It remains open for review; no merge or implementation completion is claimed.

## Entry 7 â€” Pinning authentic Olist source evidence

Date: 2026-10-12 (Africa/Lagos). Task: O1 #26. Branch: `feat/o1-olist-provenance`, stacked on F1 so shared root documentation and test tooling have one baseline. Status: acquisition succeeded; provenance verification underway.

**Files touched:** Olist snapshot script, offline integrity tests, source manifest and source handling notes.

### Context and question

The original source is the Olist Kaggle publication, not an arbitrary mirror. How do we prove exactly which bytes were acquired without placing source records or credentials into this repository?

### Decision and why

Use Kaggle's official `kagglehub==1.0.2` library with the explicit `olistbr/brazilian-ecommerce/versions/7` handle. Public access succeeded without a login or new token; raw CSVs reside in the library's cache outside the checkout. A mirror would weaken publisher/version attribution. Do not ask Kaggle for an unversioned latest download: the legacy metadata endpoint returned currentVersionNumber 2 while its history also listed 7 and duplicate version-2 entries. Record this inconsistency and select the explicit version whose actual file schemas/checksums can be inspected.

### How to build it

1. Verify the publisher's data card and listed CC BY-NC-SA 4.0 license. Read the official library's versioned download syntax. Pin the library in a PEP 723 script declaration, separate from application dependencies.
2. Download the explicit version to the default external cache. Inventory its nine CSV filenames and headers, including original misspellings such as `product_name_lenght`; do not silently normalize the source.
3. Profile with Python's csv parser: SHA-256 over original bytes, size, parsed row count, ordered schema, empty values per column and purchase-timestamp range. Reject missing/extra CSVs, changed schema and malformed records. Do not emit source text or customer IDs.
4. Publish only the aggregate manifest and handling notes. Verify repeated acquisition against this pinned manifest; never overwrite it when bytes change. Raw sources must resolve outside the checkout. Keep raw records, review text, geolocation and derived source rows out of Git and telemetry.
5. Use hand-invented CSVs in temporary test directories for offline integrity checks. These fixtures test acquisition mechanics, not model accuracy or Olist business outcomes. No live Langfuse dataset or expected-action labels are created.

Currency and timestamp timezone are not declared in the inspected source metadata/CSV schema. Preserve source values, record unverified units explicitly and resolve them under O2 before monetary actions. Portuguese source fields and supplied category translations stay distinct. Support requests, policy and gold actions remain O3 work.

### Verification

Acquisition and two independent local profile/verify runs passed on nine CSVs totaling 1,551,698 table records, including 99,441 orders. The parsed purchase range is 2016-09-04 21:15:19 to 2018-10-17 17:30:18. Source order delivery fields have real missing values; the manifest records every column's empty count and file checksum. A repeated `acquire` command uses the pinned handle and verifies the existing manifest rather than overwriting it. The local-only verify command uses no credentials or network.

The combined suite passed 16 tests: F1's 12 plus four source-integrity tests using invented rows. Tests demonstrate changed bytes, wrong source version, missing files, changed headers, malformed row width and inside-checkout source paths fail. Ruff lint/format and both architecture contracts are checked before publishing O1. No raw CSV, review text or identifier appears in the staged changes. The global cache is left intact for O2; do not delete or move unrelated cached data.

O1 is stacked on the F1 branch to avoid competing edits to shared manifest/Build Book files. Review and merge F1 first, then retarget O1 to main; O1's diff contains only provenance tooling, source notes/aggregate manifest, tests and status documentation. F2 waits for the merged F1 contract baseline prerequisites; this task does not create runtime contracts prematurely.

The original `data/` ignore pattern also hid `docs/data` aggregate reports. Caught this in the staged-file inventory and added a directory exception for `/docs/data/`; the global CSV/archive exclusions remain active. Verify both the allowed JSON/Markdown documentation and a raw CSV probe before publishing. No generated output is force-added.

Published O1 in commit 7ce824e and [PR #64](https://github.com/Protagonist01/my-production-agentic-systems/pull/64), based on the F1 branch. Both implementation issues remain open in Review until merged and verified; F2 stays Backlog while F1 is unmerged. The PRs intentionally use reference links without automatic closing keywords. Raw-source acquisition is complete, but source ingestion, operational state and evaluation contracts are still planned work.

## Entry 8 â€” Integrating the first wave and defining shared contracts

Date: 2026-10-13 (Africa/Lagos). Task: F2 #11. Branch: `codex/f2-shared-contracts`. Implementation underway.

**Files touched:** shared contract modules, offline example/tests, lockfile, current status documents and backlog.

### Context

F1 merged into main through #63, but O1 #64 merged into the old foundation branch afterward. The user authorized completing integration and verification, closing F1/O1, and starting F2. Reused the user's existing #65 rather than creating a duplicate. Its ten-file diff matched the previously tested O1 tree. Merged its exact head 699d1f6 through the connector; main is now a665d3d. Fast-forwarded the local main without touching the user's untracked historical documents. Reinstalled locked members, then ran pytest (16 passed), both import contracts (kept), Ruff lint/format (passed), and local verification of all nine original Olist files (passed).

### Before you read on

How do we run an agent and independently score its output without giving it the expected answer? Sketch the objects each side receives, and the boundary where serialized data is validated.

### Options considered and why

Plain dataclasses avoid a runtime dependency, but require hand-written nested validation and JSON round-trip handling. Chosen: Pydantic v2 models with forbidden extra fields, validated defaults and explicit JSON methods. This is a contract dependency, not a workflow/framework selection; H1 still owns provider/framework/telemetry compatibility. Closed public-input models and an explicit projection keep evaluator-only state out of the agent call. Free text still needs a reviewed domain adapter: schema validation cannot detect an answer deliberately pasted into a legitimate text field.

### How to build it

1. Add validated run identity, fixed clock/deadline, budget, versions and result/failure models. Keep business-event identity distinct from run identity; budgets here are declarations, not enforced reservations.
2. Define complete ordered model messages, provider/model/endpoint, generation parameters, tools, output schema and serializer version. Preserve whitespace and list order; canonical JSON sorts object keys only. Tool calls and tool results need IDs, names and arguments in addition to text.
3. Put expected outcomes, labels, hidden simulator state and fault expectations in evaluator-only models. The agent takes only a revalidated RunContext and AgentInput; never pass EvalCase or its metadata. Run the agent, then the scorer, then serialize a typed report.
4. Use a deterministic invented text case, fake gateway and scorer as an executable wiring check. Exercise review and typed model-failure paths separately. A correct fake output proves wiring, not model quality or domain safety. H2/H3/H5/H6 implement real budgets, replay, trial accounting and state scorers later.
5. Test JSON round trips and invalid payloads at real boundaries, capture the arguments delivered to the agent/gateway, and reject mismatched case IDs. Run the same foundation checks before publishing the F2 PR. Results will be appended after execution, not guessed here.

### What went wrong so far

The browser stopped responding during #65 body editing. The title saved, but the body remained a template. The connector successfully performed the authorized merge with an exact-head check. Issue updates still render a form without applying the write; no closure is claimed until a server read confirms it. Preserve earlier entries as history and update current status documents separately.

The existing Git Credential Manager authorizes the same Protagonist01 repository. Used its credential in memory with the GitHub API to update #65's description, attach completion evidence and close #10/#26 as completed, then record #11's branch. No token is printed or saved, no new credential/access is created, and task-local helper scripts live only under ignored `.git`. Server reads confirmed the closures. This avoids depending on the previously invisible connector form. The browser later displayed F1 as Closed/Done.

Pinned Pydantic 2.14.1 from current PyPI metadata; uv locked its transitive dependencies. The first 27 contract tests passed; the combined suite passed 43 tests, both import contracts and formatting. The example emitted a synthetic/offline_fake report with preserved context/versions, exact-text score and zero fake cost. ScoreResult values remain finite but are not limited to 0â€“1: latency/cost metrics need other ranges. Static type checking is underway using an ephemeral, exactly pinned mypy 2.4.0; it does not add a new permanent root command before F3.

Moved the Agent/ModelGateway protocols into the public contracts module so domain agents do not need to import evaluator-only objects just to implement the interface. The fake agent revalidates the gateway response. Re-ran the combined suite after these changes: 43 passed; strict mypy found no issues in four source files; both import contracts kept; Ruff lint/format passed. All six source archives/wheels built. A separate clean environment installation/example is being checked before publication. Only Windows/Python 3.13.4 is exercised; Linux/Python 3.12 checks remain F5.

The separate clean locked environment installed all six workspace members plus Pydantic, then ran the example successfully: completed, fake_case_correct=1, mode=offline_fake. Rebuilt all six archives/wheels after the final protocol changes. `uv lock --check` and `git diff --check` passed. Preparing a review PR, with only F2's planned scope and current-status corrections; the original untracked templates/archive stay outside the commit. No new worktree, provider request, database or live evaluation was needed.

Published F2 code in commit 65ff503 and [PR #66](https://github.com/Protagonist01/my-production-agentic-systems/pull/66), based on the integrated main. The committed CLI run also passed and reports revision 65ff503 with the actual lock hash. Updated #11's acceptance/evidence, assigned the repository owner and left it open in Review; the merged-PR checkbox remains unchecked. This shared baseline must be reviewed/merged before dependent worktrees use it. Existing Git credentials lack Projects scopes, so board changes use the signed-in browser rather than broadening access.

The issue sidebar status interactions did not retain the intended value; the refreshed board showed F2 under No Status. Used the card's More actions â†’ Move to column â†’ Review instead, then verified the native board: Backlog 58, Ready 0, In progress 0/3, Review 1 (F2), Done 3 (F1, O1, L5). Saved a screenshot showing the Review/Done cards. PR #66's server-side diff matches all 17 intended local files; tracked changes are clean and original untracked documents are preserved. F2 remains unmerged for shared-interface review.

## Entry 9 â€” Adding a current-code study guide

Date: 2026-10-13 (Africa/Lagos). Branch: `codex/code-study-guide`, based on F2 snapshot 0e85f9a. Work underway.

**Files touched:** `CODE_STUDY_GUIDE.md`, reading/maintenance links, this journal. Reusable skill installed separately under the user's Codex skills directory.

### Context and question

The user wants developers to understand the design all the way down to meaningful lines, including tradeoffs, possible bugs/security concerns and interview preparation. The Build Book already explains construction history. How do we offer a coherent explanation of today's code without rewriting that history or presenting planned agents as completed applications?

### Decision and why

Keep a current-state `CODE_STUDY_GUIDE.md` beside the chronological book. The reusable `code-study-guide` skill uses a concise entrypoint and an adaptable writing reference, and stays discoverable under the default personal Codex skills directory. It directs future substantive changes to refresh relevant guide sections and source anchors. A second chronological log would duplicate the book and make developers assemble current behavior from outdated entries. A prose-only architecture summary would miss the actual validators, dispatch boundaries and failure paths.

### How to build it

1. Read current source, tests, configuration and the latest journal entries. Pin the explained snapshot to 0e85f9a; verify that F2 #66 remains open and main remains a665d3d. Separate what is merged, what is under review and what is still planned.
2. Define the skill's output, evidence labels, line-link rules, risk triage, interview practice and refresh behavior. Initialize its UI metadata with the bundled skill creator and validate it. Avoid requiring unrelated plugins or granting permission for fixes/publication.
3. Generate a local AST index of class/function line ranges. Use it to check the actual implementation blocks and produce immutable source links; do not guess line numbers. Explain flow and important expressions rather than copying every source file.
4. Probe concerns with invented data. A temporary snapshot fixture reproduces a hash/parse race: changing same-width values after the hash read can leave all reported aggregates unchanged, allowing verification to pass with changed final bytes. Record this as a verified correctness defect with conditional security impact, not a claimed remote exploit. Separate it from deliberately limited fake state scoring and a fake agent's missing response-route comparison.
5. Run the existing suite to establish the inspected baseline (43 passed). Add safe interview/debugging exercises, explain controls and gaps, and update reading/maintenance links. No production source rows, secrets, runtime fixes or new access are needed for this guide.

### Verification underway

The installed skill passes its structural validator. Three isolated probes executed: fake scoring does not inspect expected state changes; a supplied alternate gateway can return a different provider/model without rejection by FakeAgent; concurrent source mutation can pass snapshot verification. The first is a deliberate fake-scorer limitation; the second is a missing integration check, not a live-provider exploit. Guide source links, coverage and reproduction steps are being checked next.

Continued 2026-10-14: wrote the 5,700-word guide and checked all 41 immutable line-range links against `git show 0e85f9a:<path>`, including source equality with the working implementation. Local document links/reference definitions resolve and every core top-level class/function appears in the walkthrough. The existing suite passed 43 tests on Windows/Python 3.13.4. Added README discovery and CONTRIBUTING maintenance guidance. The personal skill's validator passes; applying it to this repository produced the intended architectural/code-level guide and honest evidence distinctions. No runtime code was changed. The guide includes the verified hash/parse race, but fixing/tracking it is a separate action.

Published the documentation in commit 1d49c90 and [PR #67](https://github.com/Protagonist01/my-production-agentic-systems/pull/67). A fresh server check then confirmed F2 had merged into main b46cf25; compared all implementation/configuration paths with the documentation branch and found no differences. Updated the guide's current merge-status note while retaining immutable links to source snapshot 0e85f9a. PR #67 targets main and changes four documentation files only. The installed personal skill contains its SKILL.md, UI metadata and adaptable outline; it requires no new plugin or runtime dependency. The guide was queued in Codex's file panel for this chat.

## Entry 10 â€” Giving Windows and CI one command path

Date: 2026-10-14 (Africa/Lagos). Task: F3 #12. Branch: `codex/f3-command-entrypoints`, based on main b46cf25. Implementation underway.

**Files touched:** root command runner/tests, development dependencies/lock, command documentation, Code Study Guide and current status.

### Context

The user reviewed/merged F2 #66 and authorized proceeding. The original checkout held uncommitted study-guide changes on another branch. Created an attached managed worktree on reviewed main; its independent environment passed 43 tests, strict mypy, Ruff and both import contracts. Closed #11 as completed after this verification. The user explicitly requested including/updating the study-guide changes, so copied the four documentation files into this worktree while preserving the originals.

### Before you read on

How can a command work before project dependencies are installed, run the same checks in PowerShell and CI, and never turn a missing evaluation implementation into success?

### Options considered and why

Separate PowerShell/Bash scripts would duplicate behavior. A Make-only entrypoint would add a Windows prerequisite and repeat the original templates' shell assumptions. Chosen: a standard-library `dev.py` at the root, callable as `python dev.py <command>` before setup. It locates its own root, resolves uv from PATH, and invokes argument lists without a shell. Keep setup's all-workspace/locked/copy flags and reuse them for every tool invocation. Pin mypy 2.4.0 in the shared dev lock rather than installing an ephemeral type checker differently in each environment.

### How to build it

1. Define one command map for setup, lock, lint, format-check, types, imports, test and build. `check` calls the same named checks in sequence and returns the first child's failure code; it is the future F5 job's entrypoint.
2. Keep replay/record/compare registered as explicit planned commands that print their prerequisite issue and return nonzero before locating/installing tools. `example` runs only F2's invented offline case and is separate from model-quality evaluation.
3. Capture actual Git HEAD and tracked/untracked dirty state for the example's revision. Pass the root lockfile path as a distinct argument. Allow an explicit revision for source exports without Git; never invent a clean revision when discovery fails.
4. Test CLI failure propagation with invented child processes, verify a failing check stops later ones, and run a copied fresh checkout containing spaces through setup/check/example. Add type checking for the runner; preserve the original narrower harness scope for application types until later packages gain implementations.
5. Update README/CI command guidance and the current-code guide, checking source anchors and preserving unresolved findings. No provider, database, CI workflow or bug fix is introduced by this issue. Actual workflow jobs remain F5.

### Verification in progress

The clean merged baseline passed. Implementation checks and a fresh-checkout walkthrough will be recorded after execution.

### Implemented checks

The runner's first aggregate execution passed lock/lint/format-check, strict mypy (five source files), both import contracts, and 55 tests (43 existing plus 12 command-boundary cases). Tests verify planned evaluation commands fail without uv/dependencies, a types failure returns 13 and stops later checks, missing executables fail clearly, a real child preserves a space-containing argument/cwd and exits 7, and clean/dirty revision discovery remains explicit. The wrapper example returned completed/score 1 with b46cf25+dirty; all six source archives/wheels built.

Included the user-authorized guide/maintenance links, updated its merge-state boundary and added dev.py's code/failure walkthrough, test mapping, tradeoffs and interview prompts. Existing source-capture/response-route/fake-scorer findings remain visible and are not claimed fixed. Preparing an implementation commit, then checking a fresh clone with spaces and immutable guide anchors before opening the PR.

### Fresh-checkout evidence

Committed code as 71e4abd. Cloned that local branch into a new temporary checkout named `checkout with spaces`, without hardlinks or an existing environment. Invoked the absolute runner path from its parent temporary directory: setup installed 29 packages; check passed all 55 tests, types/lint/format/imports/lock; example returned completed/score 1 with clean revision exactly 71e4abd; build produced all six archives/wheels. This verifies actual Windows bootstrap and caller-directory/path handling, not a Linux/CI run. Updated the guide's source boundary and six new immutable command/test links; audited all prior line ranges against unchanged source.

### Review publication and remaining board update

Audited 47 immutable source ranges against their exact commits and checked guide reference/local links. Published [PR #68](https://github.com/Protagonist01/my-production-agentic-systems/pull/68) and updated #12's acceptance/evidence to Review, keeping its merged-PR checkbox unchecked. F2 #11 is server-verified closed/completed after merge. Browser and Node helpers both failed before initialization with `failed to write kernel assets`; repository API writes still work, but existing Git credentials lack Project scopes. Asked the user to move #12's native Project field to Review or reconnect browser control. No new credential/access or successful native-board change is claimed.

Imported the completed study-guide history from PR #67 (commit 79fd64f) into the F3 branch. The guide content/maintenance links are retained and refreshed for F3; Entry 9's final verification/publication notes precede this new entry. This preserves both branches' history and allows #68 to carry the guide and commands together without requiring a separate documentation merge.

On 2026-10-14 the user confirmed that #12 was moved to Review in Project 2. Recorded that confirmation in the delivery plan and PR; native UI read-back remains unavailable because reconnect/reset did not resolve the helper startup error. F3 remains open for review and merge. This final update changes documentation only; the verified command implementation is unchanged.

## Entry 11 â€” Isolating local Postgres services and trial state

Date: 2026-10-14 (Africa/Lagos). Task F4 #13. Branch `codex/f4-postgres-isolation`, based on merged main ce8334c. Work underway.

**Files touched:** shared Postgres bootstrap/migrations, local-service commands, database checks, delivery docs and current-code guide.

### Context

User reviewed/merged #68. The clean merged baseline passed locked setup/check (55 tests, types, Ruff, both import contracts), the example with actual revision ce8334c, and six archive/wheel builds. Closed #12 as completed and assigned #13. Reused the attached clean worktree with a new branch; the original checkout's unrelated files remain intact. Started installed Docker Desktop in the background and verified its Linux engine. The existing native Postgres service is untouched.

### Before you read on

How can one trial mutate a checkpoint while another starts from the original fixture, even when the first supplies a different database name?

### Options considered and why

A shared table with trial IDs relies on every query remembering its filter. Separate schemas plus search_path still require permissions on every table. Chosen: one Compose project/server/volume per resolved checkout, and a database plus restricted login per trial. Revoke PUBLIC CONNECT before granting the trial access. Trusted local administrators are outside this isolation boundary. Let Docker assign loopback ports rather than selecting a free port before binding it.

Rebuild from template0, transactional checksummed migrations and an invented versioned SQL fixture. This avoids copying a writable template. Reset must refuse active connections and changed fixture/migration content. Production backup/restore and domain authorization remain later work.

### How to build it

1. Hash the resolved checkout path for the workspace key, store generated credentials only in ignored local state and reject copied configuration. Pass Compose an explicit project name without global container/volume names.
2. Bind only to loopback; discover the actual port after startup. Stop services without removing volumes; volume removal requires the exact generated workspace identity.
3. Create a restricted login and database from template0, revoke PUBLIC access, then apply generic checkpoint/review/ledger tables and the invented fixture. Record migration and fixture hashes.
4. Grant checkpoint/review read/write access but only SELECT/INSERT on the ledger. These are persistence slots, not completed approval/idempotency/business tools.
5. Test two simultaneous services, denied cross-trial database access, independent writes, reset, migration drift and failed transactions. Explicit db-check must fail when Docker is absent; ordinary offline checks need no database.

### Work underway

Docker startup succeeded. SQL/command construction and disposable integration evidence follow. No database acceptance result is claimed yet.

The first Postgres 18.3 image download was slow. An existing official Postgres 17 image has repository digest `sha256:67f41722b7a8cbdb868a44a4995c846eddfdc2973bccb291ce937dce88ad5675`, created 2026-08-25. Pin that immutable digest for this local foundation and use its correct `/var/lib/postgresql/data` volume mount. This is a specific reproducible development image, not a floating latest-version claim; report the actual server version after launch. Image upgrades require a separate migration/restore exercise rather than replacing a tag over existing volume data.

### Implementation and verification

Added Psycopg binary 3.3.6 after checking current PyPI release metadata; the shared lock now has 33 distributions. Packaged migration 001 creates generic JSON checkpoint/review/ledger slots; a separate invented foundation-v1 fixture records its normalized UTF-8 text hash. Trial lifecycle obtains an advisory lock on its generated identity, checks ownership markers before reset/drop and uses template0 rebuilds. Migration DDL/history run in one transaction and reject edited or missing applied files. Grant CONNECT last; grant the runtime role no schema/metadata ownership and ledger SELECT/INSERT only. Local service commands inherit the one locked dev.py path; db-check explicitly overrides pytest's ordinary offline exclusion.

The first offline check passed 64 tests (55 baseline plus nine local-state boundary cases), strict mypy on seven source files, Ruff and both import contracts. Nine initial real-Postgres checks passed. Added actual Docker mount-name checks, nondestructive restart persistence and failed-migration DDL/history rollback; the expanded required db-check passed **11 tests in 169.24 seconds**, with no skips. Two simultaneous temporary workspace services had different ports, system identifiers and actual named volumes. Trial logins could not connect to another trial database; invented writes remained independent; exact reset restored the recorded baseline. Changed fixture/hash, wrong ownership, active sessions and changed/missing migrations failed as expected. Trial roles could append ledger entries but not edit/delete/truncate existing ledger or modify snapshot metadata. An invalid review update rolled back the earlier checkpoint write.

The actual checkout's CLI db-up/status reported its generated project and Postgres **17.11** on loopback port 49365. CLI trial-create/reset/drop all succeeded using an invented identity; no credential was printed. Browser control recovered in this turn: native F3 Done was visible after issue closure, and F4 was moved to In progress and read back. Saves were asynchronous, so the first post-click snapshot was not proof; later saved state showed the card and count 1/3.

### What went wrong and remaining limits

An automatic command review rejected a combined shell invocation containing the long journal text. Split documentation editing into the file patch tool and the independent official-image pull; both were permitted. The download was slow and was cancelled after choosing the existing official pinned image. Ruff caught unsorted imports during construction; formatting/import fixes passed. Database checks themselves passed. The native project move took time to appear; did not repeat the mutation or claim the first click succeeded.

Administrative CREATE/DROP ROLE/DATABASE cannot be made one transaction. Save local credentials first and fail visibly on incomplete bootstrap; role-only crash recovery remains a trusted administrator runbook, not an automatic success/retry. Reset is explicitly destructive disposable-state reconstruction, not production rollback. No workflow engine, real dataset import, domain policy/action authorization, production tenant security or model-quality result is implied. Final built-resource/source-anchor and PR read-back evidence follows before publication.

Built all six archives/wheels and verified the harness wheel contains both SQL resources. Installed that wheel into a separate fresh virtual environment: pinned Psycopg imported, both packaged SQL files loaded, and foundation fixture hash was `36f744ed8efb28f29fb42a24da4cc3dc8a7ef1b3fa6f41e88133bc396e07f938`. This verifies packaged-resource loading without editable source. Recorded implementation in commit 65dcefb; current guide explains all seven meaningful source files and seven test files with a dedicated Postgres chapter. A Windows default text decode failed on the guideâ€™s UTF-8 quotation marks; switched document scripts to explicit UTF-8 and repaired only newly inserted non-UTF8 bytes. Final source/reference audits passed.

### Review publication

Published [PR #69](https://github.com/Protagonist01/my-production-agentic-systems/pull/69) after pushing code and code/runbook documentation. Attached it to this chat. Updated #13 with all three acceptance criteria checked, 64 offline plus 11 required database results, fixture/image/code versions and limitations; left merged-PR unchecked and issue open. Native Project move to Review was read back after the asynchronous save; screenshot under ignored artifacts shows F4 Review and F3 Done together. Ordinary db-down stopped only this checkoutâ€™s test service, retaining its named volume/configuration; temporary integration projects/volumes were removed by their fixture cleanup. All 77 immutable source ranges and document references resolve. F4 is review-ready, not merged/completed.

## Entry 12 â€” Turning portable checks into hosted CI

Date: 2026-10-14 (Africa/Lagos). Task F5 #14. Branch codex/f5-offline-ci, based on reviewed merged main d3f783c. Work underway.

**Files touched:** GitHub workflows/contribution rules, portable audit/CI helpers and tests, locked tooling, current code guide and delivery docs.

### Context and question

The user reviewed/merged F4 #69. GitHub read-back confirms merge; first fetch failed transiently, retry fetched main d3f783c. Reused the attached clean worktree on a new branch, preserving original checkout files. Merged baseline passed setup/check (64 tests, strict types, Ruff, two import contracts), the fake example with exact clean main identity and six package builds; Postgres post-merge verification is running before issue closure.

How do we prove CI is actually rejecting bad code rather than publishing a green workflow file that never exercises the intended interpreter/checks?

### Options considered and why

A Linux-only job would leave the advertised Windows/Python range unproven. Duplicating shell-specific command recipes would drift from F3. Chosen: four quality jobs using the same dev.py setup/check/example/build on Ubuntu and Windows, Python 3.12 and 3.13; override uv interpreter selection explicitly so .python-version cannot silently select 3.13 for every matrix entry. Keep disposable database checks on Ubuntu with Docker rather than implying Windows hosted runners provide a Linux engine.

Dependency advisories and secret detection require package/registry/advisory downloads but no AI provider credential or model call. Pin external Actions to resolved full commit SHAs and uv/tool versions; run PR code with read-only repository permissions and no persisted checkout credentials. PR metadata uses the event's untrusted text only as data, never shell syntax, and verifies a repository issue reference plus evidence sections. Add a final stable gate so a failed/skipped/cancelled required job cannot masquerade as success.

### How to build it

1. Resolve official Action release tags to actual commits via GitHub; consult official uv interpreter-selection and pip-audit/Gitleaks behavior before implementing. Configure push-main and pull-request triggers, read-only permissions, concurrency cancellation and timeouts.
2. Run the shared checks in the OS/Python matrix with explicit UV_PYTHON. Run F4 db-check as a required separate job. Keep fake evaluation marked synthetic/offline_fake; replay/fresh evaluation remains explicitly unavailable until H3/H10.
3. Export exact locked third-party dependencies for pip-audit without workspace/editable projects; fail collection/service errors instead of silently dropping packages. Secret scan repository history with pinned Gitleaks, with PR comments and automatic sensitive-result upload disabled.
4. Parse PR event/evidence and confirm the referenced repository issue exists; route root contracts, lock, commands, CI and shared migrations through the integrator. Add contribution/template rules and a stable gate for all required job results.
5. Use a disposable deliberate forbidden import on the PR branch to obtain a real red CI result, then remove it and verify the final exact head passes. Record actual run URLs, rather than calling local lint a hosted CI pass.

### Work underway

Implementation and hosted evidence follow. No passing hosted workflow or dependency/secret audit is claimed yet.

Post-merge F4 db-check passed all 11 tests in 119 seconds with no skips; closed #13 as completed and assigned #14 In progress. Initial F5 local check passed 77 tests (13 CI-boundary cases added), strict mypy on eight source files, Ruff and both import contracts. Dependency audit returned no known vulnerabilities. Changed the export to retain package hashes and require them in pip-audit, avoiding an unhashed advisory input. Official pinned Gitleaks CLI download timed out locally; hosted scan evidence remains pending rather than claiming a local secret scan. No Langfuse experiment/threshold is configured: its official CI docs require a dataset, real task/evaluators and declared gates, which belong to H3/H5/H9/H10 rather than this offline foundation issue.

Committed initial F5 source as b9a3d4c, then added a clearly labelled disposable forbidden import in 826cb6c. Local imports exited 1 with Harness cannot import industry packages BROKEN and the exact ci_failure_probe â†’ olist_support edge. Published PR #70 with an explicit not-ready/pending-hosted-evidence body, attached it to the chat and left #14 In progress. Hosted failure/pass evidence remains pending; do not remove the probe until its actual quality-job result is observed.

The first hosted run 38638985538 completed failure: all four quality jobs and CI gate failed, while Postgres, both dependency audits, Gitleaks and PR metadata passed. Its downloaded quality log showed mypy's import-untyped rejection of the forbidden harness dependency, before the architecture checker ran. That proves fail-fast CI, but not the specific architecture stage promised. Replaced the temporary control with an Olist â†’ CFPB import in domain code, outside the explicitly declared mypy scope. This tests the architecture stage without weakening or suppressing type checks. The second run must show Industry packages cannot import one another BROKEN before removing the control.

Verified the [second negative run 38640533520](https://github.com/Protagonist01/my-production-agentic-systems/actions/runs/38640533520), head 9e7969418ca60913fc74602d77ad78e4dd63a468: all four quality jobs and CI gate failed; the downloaded Ubuntu 3.13 log contains Industry packages cannot import one another BROKEN and the exact olist_support.ci_failure_probe â†’ cfpb_triage edge. Postgres, both dependency audits, Gitleaks and metadata passed. Removed the disposable probe only after this evidence. Final cleaned hosted checks are next; no green result is assumed.

### Clean hosted verification

[Run 38641578564](https://github.com/Protagonist01/my-production-agentic-systems/actions/runs/38641578564), head 9cbc8ad024871c656357eb3ccd7d32d8ae63d407, passed all ten jobs after removing the control. Four actual Ubuntu/Windows Python 3.12/3.13 cells passed setup, interpreter assertion, shared checks, fake example and six builds; Ubuntu Postgres, both dependency audits, Gitleaks, PR metadata and CI gate also passed. Downloaded job logs confirm 77 offline and 11 database tests. Refreshed current-state docs and study guide with eight core source/eight test files, checked 87 immutable source ranges and preserved original findings. Local GitHub DNS/browser connection reset temporarily blocked read-back; MCP check-run reads independently confirmed success. Native Project update remains pending until its page is usable. Final documentation commit receives the same workflow; verify that exact head before presenting review-ready completion.

### Native Review and final publication

Documentation head eef5e9adb70462e21bb3e855cba5f4824205876f passed all ten jobs in run 38643732590. Rewrote PR #70 around the delivered behavior, real negative/positive evidence and limits; updated #14 to Review with all three acceptance criteria checked, leaving merged-PR unchecked. Browser connection recovered, but the semantic filter fill stalled; the visible AX input setValue plus Return worked. Filtered F5, used More actions â†’ Move to column â†’ Review, waited for saved card/count, then cleared/applied the temporary filter. Native board now shows Backlog 55, Ready 0, In progress 0/3, Review 1 and Done 6. Saved screenshot artifacts/f5-review-board.png shows F5 Review and F4 Done together. No access/permission expansion, network protection change or unrelated cleanup was required. This final documentation-only correction will be pushed and its exact-head CI/PR diff read back before handoff; implementation source remains b9a3d4c and the 87 audited ranges are unchanged.

## Entry 13 â€” Selecting a free provider and local trace integration

Date: 2026-10-14 (Africa/Lagos). Task H1 #15. Branch `codex/h1-integration-selection`, based on merged main 6e48011. Work underway.

**Files touched:** integration decision, optional tooling and smoke checks, development instructions and current-code guide.

### Context

The user reviewed and merged F5 PR #70. GitHub confirms the merge; fetched main 6e48011 and reused the clean attached worktree on an issue-sized branch. Locked setup/check passed 77 offline tests, strict types, both import contracts and Ruff. The fake example recorded clean main 6e48011 and lock hash 98653c01; all six distributions built and the hashed dependency audit passed. Required Postgres post-merge verification is still running before closing F5.

H1 must choose and test one provider/framework/tracing integration before the gateway implementation. No provider or Langfuse credentials were present in this shell or either checkout's .env/.env.local. Asked the user rather than treating the absence as access or assuming a spending budget. The user selected free tier only, then explicitly selected Google Gemini and local Langfuse.

### Before you read on

How can a smoke check establish schema/tool compatibility without pretending it proves application quality, and without letting a framework bypass the shared gateway when replay arrives?

### Options considered and why

Paid OpenAI/Anthropic requests were deferred because the user requires free tier. Gemini Developer API is the selected provider, subject to the actual project's free eligibility and model quota. Local Langfuse is the user's tracing choice; Cloud would remove service administration but is not the requested deployment. LangGraph and Pydantic AI remain the intended vertical frameworks; their model calls must converge through the shared gateway rather than introduce independent live/replay paths.

### How to build it

First read current official provider schema/tool/model/limit docs and framework extension interfaces. Resolve exact SDK versions from publisher metadata, then test the pinned combination. Keep invented compatibility input separate from real-source/domain evaluation. Keep a missing-key check explicit: local mocks prove software plumbing only, and H1's live acceptance stays incomplete without an actual provider response. Pin the local trace service configuration, isolate its resources by checkout, and retrieve an emitted trace to verify export rather than treating SDK initialization as success. Shared adapter/replay/budget/export behavior remains H2/H3/H4/H8.

### Work underway

Current documentation and package metadata are being inspected before implementation. No live Gemini or exported Langfuse trace has passed yet; key setup, free-tier eligibility, installed-version compatibility and local service readiness remain to establish.

Resolved current publisher versions: google-genai 2.30.1, LangGraph 1.2.15, pydantic-ai-slim[google] 2.56.0 and Langfuse SDK 5.0.1. Installed these as pinned development probes rather than claiming an H2 transport already exists. Official Gemini docs now direct new projects toward 3.8 Flash/3.5 Flash-Lite; old 2.5 access may be restricted for new projects. Selected stable gemini-3.8-flash for the two bounded schema/function probes, with actual project access still unverified. Aliases/returned model versions do not establish immutable weights. Official free quotas are project-specific, not a hard-coded universal RPM.

The first local post-merge database rerun passed ten tests but failed restart recovery: Docker's 90-second wait expired, then cleanup encountered Postgres still in recovery. Hosted push-main run 38647582091 passed the same required database stage. Do not erase the local failure or close F5 based only on a previous green run. A fresh isolated rerun is underway before deciding whether this is repeatable or needs a prerequisite fix. Avoid further trace-service startup while the database check is running. The disposable fixture cleanup owns these temporary services.

The user supplied a provider key in chat. Saved it only in the ignored local .env.local without echoing it; free-tier/billing confirmation remains required before a request. No secret is part of tracked files or the Build Book. No Gemini request has been sent.

### Availability, framework and local-state findings

The user confirmed Free tier with billing disabled. The first Gemini 3.8 Flash request returned HTTP 503 and stopped; a bounded second invocation did the same. A credentialed metadata read succeeded and showed generateContent support, so this was observed generation unavailability rather than a successful live compatibility test. Explicitly selected the documented stable gemini-3.5-flash-lite as the first candidate. Both of its invented probes passed: structured answer 42, then exactly one allowed lookup_order proposal for invented-order-001. Initial usage was 25/25 input/output tokens for JSON and 86/25 plus 39 thinking tokens for the function proposal. No tool was executed and no paid fallback was configured.

Pinned framework/SDK mock transport checks passed. The first socket-blocked test failed because Windows asyncio itself creates a loopback wake-up socketpair. Diagnosed the traceback at socket._fallback_socketpair, not an AI-provider call. Create the owned event loop/socketpair before entering the guard; block all connections while running the probe; undo the guard and close the loop afterward. The corrected full check passed 88 tests. Strict mypy also caught string values where Google SDK enums were required; used the actual enum members rather than suppressing types.

The fresh post-merge Postgres rerun passed all eleven tests in 793.42 seconds. Kept the original restart-wait failure visible. Hosted main run 38647582091 passed its nine applicable jobs, with only PR metadata intentionally skipped. Closed F5 #14, then verified all five foundation children closed, closed Epic F #2 and milestone M1. Native board read-back showed Done 8 and Review 0. H1 was assigned, moved to In progress and read back with active count 1/3.

Docker inventory revealed an existing Langfuse stack plus other project services. The user selected reuse rather than starting another six containers. Removed the unused separate-stack Compose/manager code before publication. The existing readiness API identified Langfuse v4.50.0. User signed in/created the dedicated local project and supplied its keys; saved them only in ignored .env.local. No existing container, volume, account, binding or server version was changed.

### Trace construction and actual read-back

Use a separate tracer provider for the H1 command, explicit root/generation inputs and whitelisted metadata, and localhost-only configuration. This avoids globally patching all framework traffic during a compatibility check. The two actual SDK calls are children of h1-provider-smoke. Export only invented inputs/output, model/version, response IDs and known token fields; retain thinking tokens separately, including unknown values. Flush and shut down the SDK, then use pinned CLI 1.2.4 to query v4 observations for the exact trace/time interval. Do not treat flush, authentication or a submitted event as verified export.

The first traced calls worked, but read-back failed. Inspected only the CLI response shape: it is status/headers/body/data, not the data/data wrapper the initial fixture had assumed. Corrected the validator and fixture, requiring status 200, a valid root, both generation children, parent/trace/model agreement, known nonnegative usage and input/output. Added negative response/correlation/configuration tests. Also reject successful read-back containing either configured secret, without printing the collection.

The corrected traced invocation passed. Trace a8bd44895cdcc0df04779db8ba36d9ca contained exactly three observations; retrieved both real generations and root using the CLI. Both generation inputs/outputs and 25/25, 86/25 usage survived export; thinking tokens were unknown in this invocation rather than reusing the earlier count of 39. No configured secret appeared in the collection. Local trace URL: http://localhost:3000/project/cmv8pr1r00006rd07qo80hr5h/traces/a8bd44895cdcc0df04779db8ba36d9ca. These are small invented-data compatibility observations, not measured application quality or production latency. Final offline checks, package builds and hosted PR verification follow before Review.

Auditing against current Langfuse guidance exposed a context gap: prompts/output alone do not show the tool/output schema or selected generation parameters. Added explicit schemas, allowed function/no-execution metadata, LOW/512 parameters and root SDK/source/lock identities. The read query expands only these known metadata keys. A fresh traced run will verify this added context before publication. Full offline checks already passed 97 cases, strict types in ten source files and both import contracts; all six archives/wheels built. No production trace/privacy claim is being made.

### Final source and context check

On continuation, read the failed root observation through the CLI. It contained an actual Gemini 503 during the second request, not another parser failure. Improved safe command diagnostics to disclose status/exception class only. A new bounded traced invocation passed as ce1613328f8a20c48cbd4e2ef2fb35aa: all three correlated observations, real 25/25 and 86/25 usage, explicit schema/parameter/source/SDK context and no configured secret in read-back. Committed seven intended source/config/test files as ccc036e after checking the staged diff for both configured secrets. Updated the study guide against this exact commit; unchanged historical source anchors retain their revisions. Documentation and hosted PR verification are next.


### Hosted and native Review handoff

Published and attached [PR #71](https://github.com/Protagonist01/my-production-agentic-systems/pull/71), source ccc036e and documentation 2ac2f4a. [Run 38655659165](https://github.com/Protagonist01/my-production-agentic-systems/actions/runs/38655659165) passed all ten hosted jobs on exact head 2ac2f4a083602619f5babaebf775623aadf93bfa: Ubuntu/Windows Python 3.12/3.13 quality, required Postgres isolation, two locked audits, secret scan, PR metadata and final gate. Local final source passed 97 offline cases, strict types in ten source files, imports/Ruff/lock, six archive/wheel builds and audit. Audited 100 immutable guide source ranges and 103 local Markdown links. H1 remains unmerged.

The native More actions expansion timed out but left the card control focused; pressing Return opened its actual menu. Selected Move to column then Review. The first observation preceded the asynchronous save; the later read-back showed H1 under Review, with counts Backlog 53, Ready 0, In progress 0/3, Review 1, Done 8. Saved artifacts/h1-review-board.png with H1 Review and Epic F 5/5 Done together. Updated current delivery docs and acceptance evidence, leaving the issue open and merge unchecked. This documentation-only handoff commit receives final exact-head CI before review is presented. H2 remains Backlog until H1 is reviewed/merged and verified.

Final guide read-back caught an old foundation sentence claiming LangGraph/Pydantic AI were not installed. Corrected it to the actual H1 boundary: pinned development packages and tested extension seams exist, while shared gateway adapters remain planned. No source or immutable source anchor changed. This guide-only correction also receives exact-head CI.


## Entry 14 â€” Moving Gemini calls behind the shared gateway

Date: 2026-10-15 (Africa/Lagos). Task H2 #16. Branch codex/h2-gemini-gateway, based on reviewed main 0a859bb. Work underway.

### Context and question

The user merged H1 PR #71. Verified the merge SHA, inclusion of final PR source, and successful push-main run 38660002889. Clean merged checkout passed locked setup/check (97 tests, strict types, imports/Ruff), offline integration probe, exact main fake example, six builds and dependency audit. Hosted main verifies Postgres; H1 changed no database implementation. Existing service state is preserved.

How can a provider adapter preserve complete messages, tool signatures and usage while identical prompts in one trial still have distinct call occurrences?

### Options considered and why

Calling Gemini directly from every framework would duplicate routing and later bypass replay/budgets. Reusing only prompt text as the recording key would collapse different schemas, tool history and repeated calls. Chosen: one generic gateway with typed per-occurrence exchanges, and one explicitly bounded Gemini text/JSON/function transport. Durable storage/replay stays H3; retry/deadline/budget reservation stays H4. Framework-specific adapters belong to the domain integrations, built on this gateway.

The pinned SDK exposes ordered parts and opaque thought signatures. A single joined text plus tool-call list loses their placement. Extend the model wire with typed ordered assistant parts and bump model message/request/response schema plus request serializer to version 2; reject old model versions explicitly. Existing generic runtime/evaluation contracts stay version 1. Preserve signatures as base64 data, never decrypt or log them. Version 1 model records need an explicit migration before H3, not an accidental hash reinterpretation.

### How to build it

Snapshot validated context/request at dispatch, allocate an occurrence within run/tenant/agent/case/trial under a lock, and keep the full context/request/response as detached exchange evidence. Request fingerprints describe content; occurrence identifies an attempt. Return typed preflight/HTTP/timeout/invalid-response failures with actual dispatch counts and unknown cost. Reject unsupported roles/parameters/modalities instead of silently transforming them. Disable SDK retries, automatic tool execution and continuation. Use the pinned Google SDK as an optional harness runtime extra, with mocks exercising actual serialization and parsing. Prove the boundaries offline before at most two invented free-tier calls. No domain quality or durable recording is claimed.

### Work underway

Official SDK/content/function/schema and current thinking documentation inspected before implementation. The old thought-signatures URL now points to the thinking guide. Source changes and actual transport/error/occurrence evidence follow.


The first H2 transport test run failed 25 cases because I used a non-existent AutomaticContinuationConfig name. The pinned SDK exposes automatic_continuation on GenerateContentConfig itself. Its dynamic module attribute fallback also let that name pass strict mypy. Isolated the first failing case rather than treating type-check success as runtime compatibility. Inspecting the actual pinned field before fixing it. Also separated the shared model-v2 base from runtime-v1 rather than overriding incompatible Literal fields, which strict mypy correctly rejected.


Corrected automatic_continuation=False against the actual pinned SDK field. The first 41 transport/identity checks passed, followed by 147 complete offline tests and strict types in thirteen source files. Added accounting/serialization hardening before live dispatch: strict successful HTTP JSON and token types before SDK coercion, preserved known usage on invalid content, aggregate output includes known thinking, and explicit enterprise=False. Optional Gemini runtime extra owns pinned Google/jsonschema dependencies; development selects that extra plus exact stubs. Registry refuses external schema fetches; local refs work. Final 149-case run and package/live checks are underway. Browser initialization fails before loading assets; API issue updates succeeded, native board movement/read-back remains unverified.


### First real gateway round trip and snapshot correction

The hardened run passed 149 offline cases, thirteen source files under strict mypy, Ruff/imports/lock and six builds. Committed source 9b3af1c. Wheel source bytes match; metadata parsing initially compared quote/spacing syntax rather than requirement meaning, so changed the local verifier to parse Requires-Dist markers. Both isolated wheel installs passed: base imports with no Google SDK, optional Gemini extra imports exact SDK/schema versions. Hashed dependency audit found no known vulnerabilities.

The two-request live gateway probe passed at clean 9b3af1c: run h2-smoke-9efe87dd80b24474ab1f4d3a48654b12 proposed lookup_order, preserved one encrypted signature in unchanged assistant parts, accepted the invented function result and returned the required case/answer JSON. Occurrences 1/2; inputs 95/133, visible candidates 25/19, thinking unknown, provider totals 120/152. Kept aggregate output/cost unknown. No secret/raw signature printed. No new Langfuse instrumentation or domain data/action was used.

Final snapshot audit found a real edge: a shallow-frozen request dictionary mutated to NaN serialized as null before validation, changing its meaning. Reproduced locally without dispatch. Revalidate Python models before canonical JSON copies for both request/context and responses; added regression cases for NaN and infinity. Invalid caller contracts now raise before allocation/dispatch rather than quietly becoming default parameters. Declared directly imported referencing 0.37.0 in the optional extra; resolved package versions stay the same. Final checks are running before the correction is committed.

The user reconnected browser control, but the tool still fails before initialization; native board state remains unverified. API updates and source work continue without widening credential permissions.


The final snapshot correction passed all 151 offline cases (54 H2 cases), thirteen source files under strict mypy, Ruff/format/import/lock. The malformed-contract regression now validates before serialization, so no warning-based coercion path is needed. Direct referencing pin leaves the same 115 resolved packages. Source correction is committed before updating immutable guide anchors; final rebuilt wheel and hosted evidence follow.


### H2 hosted Review handoff

Published and attached [PR #72](https://github.com/Protagonist01/my-production-agentic-systems/pull/72), source 4b33c3c and documentation 8af463f. [Run 38775295828](https://github.com/Protagonist01/my-production-agentic-systems/actions/runs/38775295828) passed all ten jobs on exact head 8af463fa47edddb0feaec40eeed9e7bcff440046: four OS/Python quality cells, Postgres, two audits, secret scan, PR evidence and CI gate. Remote file list matched the 20 intended files. Final rebuilt wheel bytes/metadata and isolated base/extra imports passed; 122 immutable guide ranges and 77 selected local links verified. A separate mock CONTINUATION negative control sent exactly one request and returned typed invalid_response, proving no automatic follow-up.

Updated #16 acceptance/Review evidence, keeping the issue open and merge unchecked. Native browser initialization still fails after user reconnection; user confirmed no manual board update yet. Do not claim native H1 Done/H2 Review columns were verified. Final handoff documentation receives exact-head CI before user review; H3 stays Backlog until H2 is merged and verified.

## Entry 15 â€” Preserving calls without turning replay into a cache

Date: 2026-10-15 (Africa/Lagos). H3 #17. Branch `codex/h3-strict-replay`, based on merged H2 main 9282d87. Work underway.

**Files touched:** recording/replay modules, replay command, invented fixture/tests, delivery docs and current-code guide.

### Context

The user reviewed and merged #72. Server main run 38779049159 passed all nine applicable jobs; PR-only metadata was intentionally skipped. Local merged-baseline checks are running. Browser recovery before this task restored native H1 Done/H2 Review verification: two missing cached temporary asset folders caused the helper failure. Recreating those empty folders allowed the runtime to regenerate its own files. What removed the folders remains unknown. This supersedes Entry 14's pending native-board note, without changing that historical observation.

H2 already detaches typed exchanges and allocates per-trial occurrences. A request hash alone cannot distinguish two identical prompts with different answers. Persist those occurrences, requests, typed outcomes and provenance rather than building a response cache.

### Before you read on

How would you notice that current agent code stopped after the first of two identical recorded calls? How would replay distinguish that regression from a successful matching prefix?

### Options considered and why

SQLite offers transactions and queries, but this issue needs a small inspectable export rather than a shared mutable service. Chosen: one versioned JSON document, canonical SHA-256, explicit external digest pin, and exclusive create with no replacement. Publish a fully written temporary file through a no-replace hard link so a crash before publication leaves no partial final fixture. A content hash detects edits against a trusted pin; it is not a signature or authorization.

Rewriting captured prompts after dispatch would break exact request identity and opaque signed history. Require callers to sanitize the model-visible input before capture, then supply a content-review reference and forbidden values. Reject discovered credential values rather than silently redacting a transcript into a different experiment. This is a review boundary, not a universal PII detector. Only invented content will be committed for H3.

### How to build it

1. Validate detached H2 exchanges, group by full run/tenant/agent/case/trial scope, sort each by allocated occurrence and require contiguous sequences from one. Reject changing context within a trial and mixed routes/invalid provenance. Typed model failures remain responses, not thrown-away rows.
2. Store source category/version, snapshot/policy/scorer and review provenance beside the exchanges. Hash canonical UTF-8 JSON; load with a caller-pinned digest and reject duplicate JSON keys, non-finite numbers and unsupported versions before execution.
3. Bind each recorded trial explicitly to a current strict-replay context. Permit a new run/code/candidate identity; keep tenant, agent, case, trial, clock, seed, budget, policy, data and lock exact. Preserve captured and current contexts separately.
4. Replay consumes the next occurrence for that bound scope only after full canonical request equality. Fail closed on mismatches without moving the cursor, retain case/trial/call evidence, and make failure sticky. A final completion check rejects a matching prefix with unconsumed rows.
5. Execute current agent code with recorded responses, not cached final agent results. Test without credentials and with outbound sockets blocked; change prompts, ordering, schemas and context and require failures. Cover immutable publication races, tampering, detached return values and typed errors separately.

### What went wrong / work underway

No H3 implementation result is claimed yet. The first documentation read accidentally targeted the original checkout rather than the attached worktree; corrected subsequent reads to the explicit worktree before changing source. The original checkout and its unrelated files are preserved.

### First implementation checks

Recording/replay plus command boundaries passed 77 targeted cases, including 65 recording/replay cases. Strict mypy passed sixteen source files. No provider requests were made. The writer stages and fsyncs complete bytes, then uses exclusive linking: four concurrent publishers produced one winner and three existing-file failures. Failed fsync/link leaves no destination or staging file. Replay tests ran current FakeAgent code with keys absent and sockets denied; repeated requests retained distinct outcomes, independent trials and typed failures. Changed prompt/schema/route/history/context, corrupted fixtures and skipped trailing calls fail closed. Added a standalone-process audit hook to refuse normal Python network connect/DNS/datagram operations in the replay command; it is not an OS sandbox for malicious code.

The first lint invocation ran before formatting and reported long lines; formatting resolved them. The connector only prepared issue-edit forms, so used existing Git Credential Manager authorization for direct REST writes and verified the server responses. H2 #16 is closed/completed; H3 #17 is assigned and native In progress is visible. The bundled invented fixture is not yet authored or claimed verified; capture source is committed first so its provenance can identify actual code.

### Pinned invented capture and current-code replay

The first full check passed 216 offline tests, sixteen typed source files, both import contracts, Ruff/format and the unchanged 115-package lock. Committed construction source bce80f8c94ce81578767dacf4b95c5676662e6be, then authored the fixture from that clean revision through the existing FakeAgent/FakeGateway. Two trials each record two repeated successful requests and one typed timeout. Capture mode is offline_fake and source is synthetic; this is not provider evidence. Lock SHA-256 is ab937ab9313389ded7eec95658a168f68f29ee5b9589f4ea8f3d498420c7ea72, recording digest 72125a30c816dca9f2e72b3ac6f4fc5e718ee9386c95f6243db43ba19702ac2b. Published through the exclusive writer and pinned the digest in separate source. Ordinary replay never calls the fixture-authoring helper.

The new command consumed all six calls and reproduced both timeouts, reporting capture bce80f8 and the then-dirty current revision separately. Added subprocess checks without provider credentials: connect, DNS and datagram attempts were denied; no Google/Langfuse SDK was imported. Current-agent prompt changes fail matching. The expanded targeted suite passed 81 cases (69 H3 plus twelve command cases), and strict types passed. Tightened malformed-request handling so catching an invalid request cannot retry into a passing replay session. Full final checks/builds and installed-wheel execution follow; no final hosted result is claimed yet.

### A real Windows checkout mismatch

Final source checks passed 220 tests, sixteen typed source files, Ruff/format/imports/lock and all six archives/wheels. The replay command consumed six calls and reproduced both timeouts. Before calling that portable, cloned committed source 76a562d with `git -c core.autocrlf=true clone` into an ignored directory with spaces. The cloned lock's raw SHA differed from its Git blob and replay refused the environment binding. The dependency content had not changed: Git's line-ending conversion changed the observed bytes.

Fix this at the checkout boundary, not by silently normalizing provenance hashes: add `.gitattributes` forcing LF for `uv.lock` and the bundled fixture JSON. Keep raw lock hashing and exact context matching. A fresh forced-CRLF clone after the commit must retain the pinned lock hash and run the current installed command. This control is pending at this point in the journal. No dependency upgrade or fixture overwrite is needed.

### Clean-checkout and installed-wheel evidence

Committed the attributes fix as fbf0d80a4d450ab9de27b325108613b9fdc497c5. A new forced-CRLF clone in a directory with spaces retained the exact lock SHA. Locked setup succeeded; invoking its absolute dev.py path from the parent directory ran replay successfully with clean current revision exactly fbf0d80, six consumed calls and two reproduced timeouts. This directly closes the reproduced checkout bug without weakening content pins.

Verified all three new source modules and the fixture have identical bytes inside the built harness wheel. Installed only the base wheel and its mandatory dependencies into a new isolated environment: Google and Langfuse were absent; recording/replay imports and `python -I -m agent_harness.replay_example` succeeded. The wheel run identified actual source 76a562d (the source modules match fbf0d80) and consumed all six calls without provider/trace clients. No live provider or existing local Langfuse service was contacted. All six packages built; no dependency versions changed. Preparing source-link/content review and a concrete PR; hosted final-head evidence remains pending.

Audited 143 immutable source ranges against exact Git objects and their current code slices, and 86 selected local Markdown links. The checker caught a hand-written test end line beyond EOF and an obsolete whole-command link in the H2 chapter; corrected both and reran successfully. Scanned all 23 intended publication files against configured secret values; no configured value or local/raw artifact was included. New replay/command links pin fbf0d80 while unchanged implementation links retain their verified revisions. Publishing the bounded H3 implementation next; H4 remains Backlog until reviewed capacity is assigned.

### H3 Review publication

Published and attached [PR #73](https://github.com/Protagonist01/my-production-agentic-systems/pull/73), based on reviewed main 9282d87. Source modules are fbf0d80; capture source remains bce80f8. Updated the delivery snapshot to Review and linked #17. The issue stays open with the merge checkbox unchecked until user review/merge and post-merge verification. Required hosted quality cells now execute the pinned invented replay alongside all existing checks. Final exact-head CI and native saved Review read-back are verified separately and recorded on the issue/PR after this handoff commit; do not infer their success from this journal entry.

## Entry 16 â€” Reserving shared capacity before bounded attempts

Date: 2026-10-15 (Africa/Lagos). H4 #18. Branch `codex/h4-shared-controls`, based on merged main 1207eb5. Work underway.

**Files touched:** execution controls, bounded transport/worker, gateway/probe, tests, runbooks and study guide.

### Context

User reviewed/merged H3 #73. Verified main 1207eb5385e06d5c32fceede92c6d3817ec5ad27 and run 38787114829: nine applicable hosted jobs passed, with PR-only metadata intentionally skipped. Clean merged setup/check/replay verification is running. H3 final-head run 38782567025 passed all ten jobs; native H2 Done/H3 Review were verified before merge. H4 now owns shared admission, bounded retry/deadline handling and circuit state rather than adding hidden SDK retries.

### Before you read on

Two concurrent agents see one model call remaining. Where must reservation happen? If the admitted call times out without usage, which capacity can safely be refunded, and what stops the request from continuing in a background thread?

### Options considered and why

Per-instance counters lose the shared run boundary. Optimistic refund on unknown usage understates consumed capacity. Chosen: one explicitly shared, locked controller keyed by tenant/run; atomically reserve a call and conservative token/cost ceiling before each attempt, never refund admitted capacity in this first implementation. Observed usage stays separate and unknown remains unknown. A ceiling breach freezes further admission rather than hiding the overrun. Caller-supplied ceilings need reviewed transport evidence; they are not measurements.

A thread timeout only stops waiting. Chosen for the real SDK path: one spawned worker per attempt, bounded result frame and parent deadline; terminate/join the owned worker on timeout. Stopping the local worker cannot cancel work already accepted by the provider, so its reservation remains charged. No background retry or tool execution is allowed. Process startup/cleanup overhead is included in the documented deadline boundary; OS scheduling/termination cannot be promised at an exact nanosecond.

The existing Free-project attestation remains required. Google model/pricing docs currently declare a 1,048,576 input and 65,536 output limit and Free-tier text inference at no charge for gemini-3.5-flash-lite. Reserve the entire declared 1,114,112-token ceiling per attempt, not a guessed prompt estimate; reserve zero monetary capacity only under the explicit billing-disabled Free attestation. Observed monetary usage remains unknown. This conservative policy may reject small budgets and does not independently prove project billing. Tightening it requires reviewed counting/limits evidence, not an undocumented heuristic.

### How to build it

1. Introduce an execution policy and admission quote with versions, finite limits and explicit currency/evidence. Share a controller across gateways and agents for one process. Reject budget/deadline drift for a registered tenant/run.
2. Under one lock, check the monotonic run deadline, circuit state and remaining call/token/cost capacity, then reserve all three together. Keep reservations even on timeout/unknown usage; track actual usage separately and freeze on observed ceiling breach.
3. Keep one generic H2 exchange per admitted attempt. Retry only typed transient failures within max attempts, clipped exponential backoff, remaining deadline and a new reservation. Return aggregate observed attempt usage with a terminal typed failure on budget/deadline/circuit stop.
4. Scope circuits by tenant and provider route. Open after the configured transient-failure threshold, admit only one half-open probe after cooldown, and close on successful/nontransient response. Share that state across gateway instances using the same controller.
5. Isolate the real Gemini SDK in a spawned worker without putting credentials in command arguments or records. Clip its HTTP timeout and enforce parent elapsed bounds. Test scripted failures/concurrency with an injected clock; separately test actual process timeout/cleanup and SDK mock wire behavior without credentials/live calls.

### Work underway

Read current Google model/pricing and Python 3.13 multiprocessing documentation before implementation. Langfuse remains unchanged; H8 owns production trace/export health. No new live call is required to verify H4. Implementation results and any failures follow below.

### First checks and corrections

A separate clean clone of merged main 1207eb5 in a path with spaces completed locked setup/check: 220 tests, sixteen typed files, imports/Ruff/format/lock. Replay identified that exact clean revision, consumed six invented calls and reproduced two timeouts with zero provider calls. The earlier active-checkout replay reported +dirty after H4 edits began; it was not used as clean-main evidence. H3 #17 can now close after the user's merge.

The first control tests exposed two test-harness errors: the fake transport recorded zero-duration sleeps as backoffs, and a two-second spawn timeout expired before a Windows child reached its hang marker. Skip the fake zero sleep; allow eight seconds in the real hang test and still require a child PID marker, elapsed bound and no surviving owned child. This tests interruption of an executing worker rather than startup alone. Strict mypy rejected byte-array slice assignment; use ctypes.memmove into the fixed bounded frame. None of these changes require live calls.

Replay needs its own explicit adapter. Allow strict_replay only with ReplayAttempts wrapping StrictReplayGateway; reject a live attempt gateway in that mode. Propagate ReplayMismatch as an infrastructure exception after keeping/finalizing the reservation and freezing the run. Swallowing it into a typed model response would let a caller mistake invalid evidence for a model outcome. Require assert_complete on the underlying replay as before. Targeted and full validation follow.

The targeted suite passed 52 cases after increasing only SDK classification-worker allowances to thirty seconds. One earlier 503 classification case returned a legitimate parent timeout at ten seconds during Windows startup; the longer allowance isolates classification from startup slowness. Added invalid direct Gemini timeout checks before HTTP. Full check/build and documentation verification are now running; no hosted H4 result is claimed.

### Full source verification

The full locked check passed 276 offline cases (56 H4), nineteen typed source files, both import contracts, Ruff/format and the unchanged lock. All six source archives/wheels built. Direct Gemini invalid/nonfinite time is now rejected before HTTP. No live provider request was needed. Preparing an implementation commit so documentation can link immutable code; installed-base-wheel, link/content review and final hosted checks remain separate evidence.

### Installed package and source review

The built harness wheel contains exact bytes for all six changed/new source modules. Installed only the base wheel and mandatory dependencies into a fresh environment: Google and Langfuse were absent. A separate importable invented worker ran through BoundedGateway â†’ ProviderGateway â†’ IsolatedTransport with network audit denial, returned its invented answer and retained one reservation. The first handwritten package probe omitted required ModelRequest.parameters and failed validation before dispatch; adding the explicit empty dictionary made the probe valid. This was a probe-input error, not a package change.

Audited 144 immutable source ranges, 105 selected local links and twenty intended publication files for configured secret values/local artifacts. Re-anchored changed gateway/Gemini/probe symbols to implementation 68e7383; unchanged links retain verified source slices. A Windows helper initially read Markdown using cp1252; restored its three affected planning files from clean Git bytes and reran with explicit UTF-8. Link/content verification then passed. No source, lock or provider fixture was modified by documentation repair. Preparing the review publication; hosted final-head evidence is pending.

### H4 Review publication

Published and attached [PR #74](https://github.com/Protagonist01/my-production-agentic-systems/pull/74), based on reviewed main 1207eb5. Implementation links pin 68e7383; the delivery snapshot now records Review. H4 #18 remains open with merge unchecked until user review/merge and post-merge verification. Exact final-head hosted checks, clean replay identity and native saved Review read-back are verified separately after this handoff commit. No final hosted pass is inferred from publication.

## Entry 17 â€” Pinning case membership and independent scorers

Date: 2026-10-15 (Africa/Lagos). H5 #19, branch `codex/h5-versioned-cases`, based on user-reviewed merged H4 main e9ebd07. Work underway.

**Files touched:** case manifest/scorer registry modules, invented fixtures/tests, evaluation documentation and current-code guide.

### Context and question

H4 #74 is merged. A separate clean clone is checking the merged implementation. H5 must load a fixed population without leaking labels and select a fixed independent scorer. How can a missing case fail before an agent runs, rather than quietly shrinking a denominator?

### Options considered and why

Inferring membership from loaded files cannot detect a missing file. Chosen: an explicit case-ID inventory, embedded case records and snapshot descriptors in one manifest, reviewed by a separate SHA-256/id/version pin. Hash and parse the same byte buffer. Reject duplicate JSON keys, duplicate/missing/unlisted IDs, incompatible snapshot provenance and group leakage across development/holdout splits before dispatch. A hash detects changes relative to the supplied pin; it does not prove labels are true or the pin is trusted.

Loading Python module names from manifest data would turn a case file into executable configuration and complicate static package boundaries. Chosen: explicit application composition registers trusted scorer objects by ID/version and compatible snapshot/policy pairs. The harness imports no vertical and loads no code named by JSON. New batch execution, database evidence readers and release gates remain H6/domain work.

### How to build it

1. Keep F2 EvalCase and AgentInput intact. Wrap each private case with a group, split and scorer ID; bind its existing scorer version to an explicit registration.
2. Validate an exact declared membership inventory and snapshot descriptors, including source kind/version. Group IDs cannot occur in both development and holdout, even across source snapshots.
3. Read one manifest byte buffer, verify its externally supplied digest, then parse with duplicate-key rejection and closed strict contracts. Retain a canonical serialized copy and reconstruct it on access to avoid nested dictionary mutation changing loaded evidence.
4. Resolve every manifest scorer against explicit registered compatibility declarations before dispatch. Pin the resolved bindings for this run. Copy/revalidate the case and result at the scorer boundary; require nonempty unique metrics and the declared scorer version.
5. Reuse run_case's closed public projection. Wrap its result with manifest ID/version/digest, group/split and scorer identity so evidence can be traced without changing model-call wire contracts.
6. Use an invented external-state reader in acceptance tests: identical completed claims and invented ledger references receive different scores when actual stored state differs. This proves plugin wiring and independent checking, not a real domain scorer.

### Verification underway

Current Langfuse dataset/evaluator guidance was read for input/expectation separation and deterministic checks. H5 is a local library/contract increment with invented fixtures, not a live Langfuse dataset or a new quality metric. No live dataset/service, provider call, dependency update or judged quality experiment is required. The existing declared metric/release plan remains authoritative. Implementation and verification results follow as work proceeds.

### Verification and portability

Separate clean main e9ebd07 passed locked setup/check: 276 tests, nineteen typed files, imports/Ruff/format/lock, six-call replay with two recorded timeouts and zero provider calls. Main run 38803477072 passed nine applicable jobs (PR-only metadata skipped). H4 #18 is closed/completed. Native project read-back confirms H4 Done and H5 In progress.

H5 targeted checks passed 53 cases. The full locked check passed 329 tests, twenty-one typed source files, both import boundaries, Ruff/format/lock; all six archives/wheels built. Invented actual state settled/pending/absent earns 1/0/0 despite identical completed claims and forged references. Typed scorer errors retain no score, exceptions propagate, and private metadata never enters captured agent/gateway input. No domain quality or live state-store claim follows.

Before publication, noticed that a raw-byte-pinned JSON fixture needs a line-ending rule: this Windows checkout has core.autocrlf=true. Added a narrow tests/fixtures/cases/*.json text eol=lf attribute, matching the existing replay/lock strategy. Verify the staged blob and a Windows-style checkout against the separately declared digest. Registry.bind uses a quoted forward return type because BoundEvaluation is declared later; the first collection exposed that annotation order and was corrected before the 53/329 passing checks. Package and immutable-link verification follows.

### Installed package, links and review preparation

Both new source modules match the built harness wheel byte-for-byte. Installed only the base wheel and mandatory dependencies into a fresh environment, ran Python with isolated import paths and network audit denial, and loaded the pinned invented fixture through the new API. Independent settled/pending/absent state reproduced 1/0/0; Google and Langfuse were absent. The digest also matches the committed fixture blob and a core.autocrlf=true checkout. Reviewed 161 immutable source ranges, 112 selected local links and sixteen publication files for configured secret values/local artifacts. No raw source, private service evidence or credentials enter publication.

Created and attached draft [PR #75](https://github.com/Protagonist01/my-production-agentic-systems/pull/75) for the implementation, then completed the runbook, source walkthrough, planning snapshot and merged-H4 documentation. H5 #19 remains open until user review/merge and post-merge acceptance. Final clean-head replay and hosted CI, remote file equality and native Review read-back follow; publication alone is not completion. H6 #20 is next after verified H5 merge.

### Hosted scanner diagnosis

The first hosted final-documentation run failed its generic API-credential heuristic on ordinary prose in the H5 study chapter's test-coverage paragraph (line 63); redacted diagnostics identify that exact documentation location, not a configured credential or fixture digest. Inspection confirmed the line lists malformed/absent-file tests. Rephrased the sentence and replaced only the unmerged documentation commit using force-with-lease. No scanner rule or allowlist was changed. The original implementation commit and immutable source links stay pinned. Other checks from that superseded head are not final acceptance evidence; verify the replacement head from scratch.

## Entry 18 â€” Accounting for isolated trials even when execution fails

Date: 2026-10-15 (Africa/Lagos). H6 #20, branch `codex/h6-isolated-trials`, based on reviewed merged H5 main c08f67d. Work underway.

**Files touched:** trial scheduling/accounting, spawned runner, F4 state adapter, invented example, offline/integration tests and operating/study documentation.

### Context and question

The user reviewed and merged #75. H5 fixes case population and scorer selection, but a scorer exception still prevents a case report. How do we retain all scheduled denominators and distinguish verified autonomous completion from a claimed success or unnecessary handoff?

### Options considered and why

A thread timeout cannot stop an executing agent. Chosen: bounded coordinator threads, each owning one spawned trial process, with a bounded shared-memory response and explicit terminate/join/kill cleanup. Construct agent/gateway/scorers inside each child from a trusted importable factory, avoiding pickling live SDK clients/locks and preventing ordinary per-instance state from crossing trials. Child input remains evaluator-private; factories pass only the existing public projection to agents.

Deriving correctness from an agent outcome would award false success. Chosen: a versioned outcome policy selects separate required binary correctness, safety and durable-review metrics from the registered independent scorer. Private predeclared eligibility/review flags bind to the pinned case before execution. A handoff on an eligible completion case keeps its denominator and earns no completion credit. Unknown/missing/error scores are unverified; unsafe observations are retained even if other evidence fails. This implements the already declared metrics, not a new domain experiment or quality floor.

Create a private schedule journal before setup, exclusively write one terminal row per planned identity, and reconcile missing rows after interruption. A process/host crash can prevent a write; recovery must expose missing evidence rather than fabricate a completed trial. This first runner refuses to resume/overwrite an existing journal. Full release quality gates remain H9/H10; H6 provides the required completeness/safety evidence precondition.

### How to build it

1. Declare every case Ã— repeated-trial identity with fixed clock, seed, candidate/code/lock and budgets; validate exact manifest membership, context/snapshot/policy agreement, unique run IDs and compatible experiment provenance before any setup.
2. A trusted parent environment prepares fresh state and returns an opaque lease with restricted access. F4's adapter creates a unique migrated/seeded database and least-privilege role for each trial; existing identities fail rather than silently resetting someone else's work. Only restricted login information enters the child; administrator credentials stay in the parent.
3. Run the trusted component factory and existing H5 binding/runner inside one spawned process. Bound elapsed child execution including startup by both the declared trial duration and runner limit. Return a validated frame or a fixed sanitized error code; never export arbitrary exception text.
4. Stop/reap the child before releasing its state. F4 cleanup verifies ownership and refuses active connections. Setup/cleanup errors are terminal evidence failures, not passing empty results. Parent lifecycle hooks must bound their own I/O; F4 uses its existing connection/lock timeouts. A hostile or hanging lifecycle hook and abrupt host termination remain explicit limitations.
5. Derive categories and denominators from scheduled flags and independent scores, retain errors and reconcile the exclusive journal. Test worker timeout/crash, scorer errors, bounded concurrency, reset isolation, all-escalation behavior and missing rows. Add real Postgres integration through the existing required db-check job.

### Verification underway

A separate clean clone is checking H5 main c08f67d. Read current Python multiprocessing and Langfuse deterministic-evaluator guidance before implementation. No new dataset, live provider call, Langfuse service change, dependency upgrade or model-wire migration is needed. Implementation and test results follow as work proceeds.

### First worker checks

The initial targeted run passed 48 tests and exposed one test allowance issue: while Docker startup and other validation were active, a valid typed-scorer-error worker exhausted its twelve-second deadline. That was correctly recorded as timeout, so the classification assertion was wrong for the observed run. Use the declared thirty-second worker allowance for that mixed failure test and retain a marker proving the hung worker actually entered execution; its bounded duration and cleanup assertions remain.

The unpicklable-factory negative control exposed a Windows spawn detail: Python starts a bootstrap process before dumping all arguments, so failed pickling can produce a child-side invalid-handle traceback. Add a ForkingPickler preflight for trusted factory/context/lease data before allocating a worker. This rejects ordinary unpicklable objects without creating that bootstrap process. It does not sandbox custom serialization hooks. The process is a daemon so nested multiprocessing workers are refused; controlled adapters inside an already bounded trial must use direct deadline-aware transport rather than nesting H4 IsolatedTransport. Trusted factories must not launch background subprocesses. These limits belong in the operating guide.

Clean H5 main c08f67d passed 329 tests, strict checks and exact replay. Push-main run 38815711769 passed nine applicable jobs; H5 #19 is now closed/completed. Docker Desktop was stopped; started the installed backend to run disposable database checks. Existing required checks are running; the new H6 database tests additionally verify fresh state, restricted role attributes, independent committed-state scoring and cleanup after an executing worker times out. Browser board control timed out twice; no H6 native status change is claimed yet.

### Binding recovered evidence back to the reviewed cases

While inspecting recovery, identified a gap in the first design: a self-consistent recovered schedule could omit an entry or change eligibility unless the reader/gate checked the original reviewed manifest again. Added explicit case inventory and matrix validation to TrialSchedule itself, and require the separately pinned LoadedManifest in TrialJournal.read and BatchReport.require_release_evidence. Both revalidate membership and private eligibility/review flags. A regression constructs internally consistent changed labels; even with all rows present, the evidence gate must reject it. Local JSON consistency alone is not approval of a new population. Signed/tamper-authenticated score artifacts remain outside H6.

### Continuation on 2026-10-16

The session interruption left no retrievable completion result for the final suites. Rerun them with output saved under ignored artifacts rather than inferring success from intermediate progress. Docker Desktop was stopped after the interruption, so the first resumed db-check failed all thirteen cases during fixture setup, before trial execution. Start the installed backend and rerun the complete database suite; do not treat setup errors as skipped acceptance.

Two earlier diagnostic runs also showed why worker classification tests need room for Windows startup. The mixed failure test observed legitimate thirty-second timeouts for ordinary scorer/crash workers while other validation was active. Give ordinary test workers a ninety-second allowance within declared 120-second contexts; the designated hanging trial retains its own thirty-second duration and entry marker. The Postgres test similarly uses a forty-five-second worker allowance within a ninety-second context, with a 120-second deliberate hang. Runner defaults remain thirty seconds. These are test allowances, not measured provider latency or a production deadline promise.

The stable-source locked check passed 380 offline tests in 479.72 seconds, including 51 H6 cases, with twenty-five typed source files, both import contracts, Ruff/format and unchanged lock. Source/tests are committed as bbb1013; the study guide now pins that immutable implementation. The initial documentation audit verified 186 immutable source ranges and 121 selected local links. Installed-wheel, full database and hosted checks remain separate pending evidence. Native board read-back had recovered before interruption (H5 Done, H6 In progress); browser control is unavailable in this continuation, so no new native Review transition is claimed.

All six source archives/wheels built. The four new modules match the harness wheel byte-for-byte. A fresh base-only environment ran an import-isolated, guarded spawned-worker probe with network audit denial in both parent and children; Google and Langfuse were absent. Independent file-state scoring produced 2/2 autonomous completions for the completing agent and 0/2 for the escalation-only agent, with both eligible denominators retained and recovered journals equal to the returned reports. This is invented infrastructure evidence, not domain quality. Created draft [PR #76](https://github.com/Protagonist01/my-production-agentic-systems/pull/76); database and final-head hosted evidence are still pending.

### Review snapshot

The first hosted source run 38952883131 passed its required Postgres job and both Linux quality cells; the two Windows cells were still running when inspected. These source-head results are preliminary, not final-head acceptance. The local full database rerun is progressing through disposable Compose resources after backend restart. Complete the runbook, study chapter and delivery snapshot in a separate documentation commit, then verify the final clean revision and every required hosted job. Keep #20 open through user review/merge and post-merge acceptance; H7 #21 depends on H6 and completed H4. Native board status remains last verified In progress until browser controls return; issue/manifest Review does not prove a native board change.

The expanded final documentation audit checked 186 immutable source ranges, 130 selected local links and all seventeen intended publication files; configured secret values and ignored local artifacts were absent. No runtime source changed during these checks. Publish the documentation snapshot, then record exact-head replay, hosted acceptance and the local database outcome on #20 without treating preliminary runs as final evidence.

## Entry 19 â€” Reproducible faults at explicit execution boundaries

Date: 2026-10-16 (Africa/Lagos). H7 #21, branch `codex/h7-seeded-faults`, based on user-reviewed merged H6 main 9c13b2c. Work underway.

**Files touched:** fault plan/session contracts, deterministic state invariants, existing evaluation/scorer/trial composition, invented fault example/tests and operating/study documentation.

### Context and question

The user merged #76. H6 retains every trial but refuses declared faults. How can a tool timeout after commit be reproduced without confusing it with a timeout before a write, or crediting a claimed recovery when the ledger contains duplicate effects?

### Options considered and why

Random wall-clock sleeps would couple reproducibility to host scheduling and could miss the intended commit boundary. Chosen: explicit model/input/tool boundary hooks, with a versioned declarative plan and seed-derived occurrence selection. A trusted adapter declares when a tool operation has committed. The injector simulates boundary failures without altering production services or sleeping. A recorded event proves a hook ran, not that a domain transaction was correct.

Automatically retrying failed tools would bake domain recovery policy into the harness and could duplicate a committed effect. Chosen: raise a fixed typed injected timeout; let the agent decide whether to reconcile, retry with a stable operation key or create durable review. Duplicate delivery explicitly invokes the same trusted operation twice. Independent state/ledger checks then expose duplicate or unauthorized effects. Recoverability stays in the pinned case declaration; it is never inferred from the observed outcome.

### How to build it

1. Keep F2 FaultScenario as the private expectation declaration. Add a closed executable plan for supported fault kinds, target/timing and bounded occurrence windows. Bind every declaration exactly before trial setup, rejecting unknown, missing, duplicate or conflicting rules.
2. Derive the selected occurrence from a stable hash of plan version, scenario ID and declared seed. Record ordered metadata-only events with plan/declaration digests. Do not include injected payloads or private expected outcomes in public context or event logs.
3. Create the fault session inside the existing H6 worker. A fault-aware factory shares that session with trusted tool wrappers; existing no-fault factories keep their interface. Route only the explicit public input/model surfaces through wrappers. Refuse faults without matching composition.
4. Preserve the event evidence in the case report. Unreached hooks remain incomplete evidence; rebind reports to the scheduled plan and reviewed case on recovery/release checks. Keep existing independent correctness/safety/review metrics and derive separate recovered/review/unresolved/unsafe fault categories from those observations.
5. Add pure state/ledger invariants with independently supplied expected effects and read actual state through a trusted reader. Test identical success claims with correct, duplicate, unauthorized and absent effects. Exercise every fault in invented offline state, including before/after commit and resume, plus the existing required Postgres path where useful.

### Verification underway

The clean merged-H6 checkout is running locked checks and exact replay. H6 final PR head passed 380 offline cases, thirteen local/hosted database cases and all ten hosted jobs; the local fixture cleanup was independently verified. Current Langfuse evaluator guidance was read for deterministic state checks. H7 implements already declared fault/outcome measures, not a new quality floor, live dataset, provider experiment or production authorization policy. No dependency upgrade or schema change is planned. Results and actual failures follow below.

### First checks and recovered-plan trust

The first targeted H7 suite passed 36 cases, including all eight real boundary drills, repeatability, negative duplicate/unauthorized actors and spawned accounting. The existing trial/contract subset passed 78 cases. Strict mypy initially caught an untyped JSON clone and dictionary variance; use an explicit JsonValue boundary and separate invariant-name variable, then all twenty-nine typed source files passed. These are intermediate results; final checks follow the remaining changes.

Recovery needs a second reviewed input: H5's case pin declares fault expectations but does not pin an H7 payload or occurrence window. Require the separately reviewed FaultPlan when reopening a fault journal or requesting release evidence, and compare it to the scheduled plan. The running coordinator already owns its validated plan; recovered JSON alone cannot approve a changed treatment. No-fault H6 callers retain the existing default. This is consistency against reviewed inputs, not journal authentication.

The Windows UI helper timed out on lightweight discovery, again on retry, and after a reset/reinitialization. Stop UI attempts after that documented recovery sequence; no new native project-board change is claimed. Issue/API and versioned status can still be maintained without expanding account permissions.

The expanded targeted suite passed 44 cases and caught a missing import in the last added test, before its gate assertion ran. Restore the BatchReport import; the subsequent full lint check confirms the name is defined. The full check also stopped at formatting for a split SQL literal; run the repository formatter and restart the aggregate check. These test/static failures are retained here; they are not passing evidence. Added three real Postgres cases using the existing restricted fixture: commit then timeout, independently reread the complete non-baseline ledger, and distinguish reconciliation from duplicate keys or an unapproved actor. No schema was changed.

### Windows failure: an audit hook escaped the example boundary

Draft source run 38962250451 passed both Linux cells and Postgres but failed both Windows quality cells in the existing SDK/framework network-denial probe. The logs show NetworkDisabledError while Windows initializes its event loop, followed by a partial ProactorEventLoop cleanup error. The new example factory installed an irreversible process-wide network audit hook even when unit tests called it inline. That hook remained active for unrelated later tests. The correct boundary is explicit: make example network denial opt-in at factory construction, enable it in spawned CLI/package workers, and keep inline evaluator composition free of process-wide hooks. Parent CLI/package probes still deny network explicitly. Do not weaken the existing SDK test or its own scoped network checks. Rerun the full Windows checks after this fix; previous Linux/DB passes are preliminary.

### Measured checks after the boundary fix

The focused fault-then-SDK sequence passed 65 cases in 73.31 seconds, confirming the inline factory no longer breaks Windows event-loop setup. The earlier full local run completed 423 passes and two failures: the audit-hook bug above and the existing H4 eight-second hang test timing out before its startup marker while other checks were active. Keep the H4 assertion unchanged and rerun the complete suite after the competing checks finish; a timeout before the marker does not prove interruption of executing worker code.

All sixteen required Postgres tests passed in 600.20 seconds, including the three new independently inspected committed-ledger cases. Fixtures completed normal teardown; no manual service or volume deletion was performed. Pytest's retention cleanup removed that temporary root before a separate metadata audit could reopen it, so no independent four-project read-back is claimed for this run. Existing Langfuse services were not changed. Clean merged-H6 main 9c13b2c passed 380 tests, strict checks and exact six-call/two-timeout/zero-provider replay; main run 38959680261 passed nine applicable jobs. H6 #20 is closed/completed, H7 #21 is active in draft PR #77.

The first installed base-wheel drill reproduced eight terminal rows, seven recoveries and one appropriate review, with Google/Langfuse absent and parent/child network denial. Duplicate and unauthorized effects failed independent invariants. Rebuild/recheck after e9213aa's explicit network-hook fix so package evidence covers the repaired bytes. The documentation audit initially checked 214 immutable source ranges and 145 selected local links; final counts are verified again after the review snapshot.

All ten hosted jobs passed for repaired source e9213aa in run 38963004360, including four Linux/Windows Python 3.12/3.13 cells and the sixteen-case Postgres suite. The local fresh aggregate rerun passed the earlier H4 worker-marker point and is continuing. Final documentation head and rebuilt installed-wheel evidence still need their own verification; source-head CI does not stand in for final-head acceptance. Updated only affected code-study chapters; their immutable source ranges were re-anchored to the implementation/fix commits and the final scope audit covers twenty-three intended publication files.

### Stable-source acceptance and Review preparation

The fresh aggregate passed all 425 offline tests in 303.44 seconds, including 45 H7 cases, with twenty-nine typed source files, both import boundaries, Ruff/format and unchanged lock. Both earlier failures pass without weakening the H4 marker assertion or SDK network guard. All six archives/wheels built. Verified source-head hosted job logs explicitly report 425 passed in each of the four quality cells and sixteen passed in Postgres.

Rebuilt the fixed source and installed only the base harness wheel/mandatory dependencies into a new environment. All eight changed/new module bytes equal the wheel. Under isolated imports and explicit parent/child network denial, eight terminal rows yielded seven recoveries and one appropriate review, retained seven eligible completions and reopened identical pinned journals. Google and Langfuse were absent; duplicate and unapproved effects failed independent invariants. No live provider work or domain quality experiment was needed.

Publish the completed runbook, source guide and merged-H6/H7 Review snapshot in a documentation commit. Keep H7 #21 open until user review/merge and post-merge acceptance. Final clean-head replay, remote file equality and all ten hosted checks are verified after that commit and recorded on #21. Native project-board read-back remains unavailable after the documented helper failure; issue/manifest Review is not represented as a verified native transition. H8 is the next harness task; its H1/H2/H6 prerequisites are complete.

### Documentation scanner diagnosis

The first documentation head 933ddd1 triggered the repository scanner's generic credential heuristic at docs/code-study-faults.md line 73. The flagged sentence enumerates ordinary test coverage; inspection confirmed no configured credential or secret value. Rephrase that prose as short sentences and replace only this unmerged documentation commit using force-with-lease. Keep runtime implementation/fix commits and their immutable links intact. No scanner rule, allowlist or exclusion is changed. Verify clean replay and hosted checks against the replacement head; the failed/superseded run is not final acceptance evidence.

## Entry 20 â€” Safe correlated telemetry

Date: 2026-10-17 (Africa/Lagos). H8 #22, branch `codex/h8-correlated-traces`, based on reviewed H7 main 487242f. Work underway.

**Files touched:** telemetry contracts/session, explicit Langfuse OTLP adapter, evaluator and owned-worker composition, invented probes/tests and study chapter.

### Context and question

H7 #77 is merged. The existing H1 probe demonstrates export but calls a live model and does not expose exporter failure as runtime evidence. How can the harness retain the real result when telemetry fails, while preventing identifiers, prompts, tool arguments and exception messages from reaching the backend?

### Options considered and why

Automatic SDK instrumentation would capture provider arguments and ambient process resources. The latest installed Langfuse SDK is 5.0.1, whose current full-platform documentation requires server 4.59.0; the existing local server reports 4.50.0. Chosen: Langfuse's documented standard OTLP endpoint, using locked OpenTelemetry 1.45.1 encoding through an optional package extra. Keep the server untouched. Manual, closed projections make the privacy boundary inspectable; the cost is less payload context and model names represented by keyed references, without automatic model pricing.

### How to build it

1. Define TraceHealth with generated trace ID, bounded span/drop counts and separate export/flush/cleanup states. Keep full evaluation journals private: this safe health object does not redact an existing CaseReport.
2. Construct one TraceSession inside each trial factory, with a private key of at least 32 bytes. Generate random trace/span IDs; use domain-separated HMAC-SHA256 for identities, request/result content, versions and source references. Never include exception strings, arbitrary span names or ambient environment resources.
3. Wrap evaluator execution in a root, agent and scorer span; wrap the supplied ModelGateway for request/response facts and token usage. Expose explicit invoke(node/tool/policy, operation, callable) hooks to adapters. Context-local parents keep tool/policy calls under the executing node. A fixed capacity drops excess child spans visibly, while retaining admitted parents.
4. Finish only after all spans end. Send one batch, then flush and shut down even when preceding steps fail. Attach health beside the successful CaseReport and carry it through worker frames/journals; error workers retain safe health separately. Process termination may prevent cleanup, so missing health is unknown rather than an export success.
5. Encode fixed resources and Langfuse observation types. Use an explicit authenticated HTTP origin, deny redirects and ambient proxies, reject partial OTLP acceptance, and expose only finite health states. Export socket timeouts are bounded; the H6 supervisor remains the overall process deadline.

### Verification underway

Fresh Langfuse OpenTelemetry, masking and best-practice documentation was read before implementation. The merged baseline check is still running. Next: canaries across all free-text fields and errors; failed send/flush/cleanup; nested/concurrent parents; actual local export and CLI read-back; full locked checks, base-wheel isolation and final-head hosted evidence. No H8 pass is claimed yet.


### First results and backend compatibility correction

The first 22 focused tests passed in 9.09 seconds; strict types passed 33 source files after making the protobuf encoder's bytes return explicit. The first local export check failed. Inspected only HTTP status, content type, body size and top-level field names: the server returned HTTP 200 with a Langfuse queued-job JSON acknowledgement, not a protobuf reply. The strict decoder had correctly refused an unrecognized body. Added recognition of this observed legacy acknowledgement and standard OTLP JSON/protobuf responses, retaining partial-rejection checks. Enqueue acceptance cannot establish storage; the separate CLI read-back remains required. No credential or backend body was printed.


### Source publication and trace audit

The focused telemetry/portable-command checks passed 58 cases in 24.87 seconds. The local backend returned seven observations with the expected chain/agent/span/generation/tool/guardrail/evaluator types, parents, known zero token usage and keyed code/candidate/data/policy/lock/source/tool-result evidence. Configured keys and invented canaries were absent. The probe prints only safe health; it never publishes the private evaluation report. During read-back testing, fixed the CLI envelope (`body.data`), parsed source-reference lists and aggregate usage totals; the independent response tests also caught a shadowed expected-version variable.

Fetched the current best-practices page again after reading real observations. Kept the strict privacy boundary, and improved input/output to show safe shape facts, outcome and keyed content/result references rather than only a redaction marker. Raw prompts, outputs and thought text remain private. Source is committed as 08ba28e; [draft PR #78](https://github.com/Protagonist01/my-production-agentic-systems/pull/78) is published. Full locked suite, installed-package, local database and exact-head hosted acceptance remain separate pending evidence.


### Strict replay caught the changed dependency lock

The first source-head Linux jobs passed 470 tests and failed the standalone replay test: ReplayBinding rejected the captured lock hash. This is the intended dependency condition check. Adding the installable telemetry extra changes uv.lock even though it reuses already locked OpenTelemetry versions. Do not weaken ReplayBinding, substitute the historical lock when reporting current execution, or rewrite the old capture in place.

Prepare a new invented-v2 resource by running the existing six-call in-process FakeGateway capture helper against source 08ba28e and the actual H8 lock. Keep invented-v1 byte-for-byte. Publish the new file exclusively through write_recording, record its separately pinned digest and switch the bundled command to that proposed version. PR #78 explicitly includes fixture/pin review before merge. This creates no live provider evidence and leaves request matching and dependency equality strict. Add a check that the historical fixture still loads at its original pin and still refuses the new lock. Then rerun all current checks and hosted jobs; the failed first source run is not acceptance.


### Stable source check and installed-extra probe correction

Stable source eaae533 passed all 472 offline tests in 344.64 seconds, strict types in 33 source files, both import contracts, Ruff/format/lock; all six source archives/wheels built. Nine changed/new harness modules and both recording resources match the wheel bytes. The base-only installed probe passed two independently scored completions, retained rejected-export health through journal recovery, and denied network in parent/children with provider/telemetry SDKs absent.

The additional telemetry-extra probe stopped at an overly broad import assertion: protobuf legitimately supplies the `google` namespace, which does not mean Google GenAI is installed. Correct the probe to check `google.genai` and Langfuse separately, keep the base-only evidence, and rerun both modes in a fresh environment/output directory. The first extra-probe failure is preserved, not treated as a product regression or a passing encode check. The wire mode must actually encode and return accepted status; an assertion hidden inside an intentionally rejecting exporter would otherwise be unable to prove encoding succeeded. Local database acceptance follows this corrected package probe.


### Installed package results and review snapshot

The corrected package probe passed in a fresh environment in both modes. Base-only: two autonomous completions, deliberately rejected exports retained in recovered journals, network denied in parent and children, no OpenTelemetry/Google GenAI/Langfuse SDK. Telemetry extra: actual protobuf encoding acknowledged, the same two independent completions and journal equality, no Google GenAI or Langfuse SDK. Protobuf's Google namespace is expected in this second mode. No source fix was needed for the probe assertion. Both packaged recording resources and all nine affected module bytes match source.

Preparing the Review documentation snapshot for PR #78. Source eaae533, 472 offline passes, strict checks, six builds and installed-package evidence are verified; local Postgres and exact final-head hosted/clean trace/replay results are recorded separately on #22 after they complete. Keep the merge checkbox unchecked until user review/merge and post-merge acceptance. Native board state is unverified after the prior helper failure. H9 follows this review cycle; no domain quality or complete release gate is claimed.


### Actual I/O shape and final reader correction

All sixteen required local Postgres cases passed in 291.95 seconds. The clean publication probe then exposed a remaining reader error: the fast observations API returns I/O fields as JSON-encoded strings, while expanded metadata contains parsed lists. Inspected only field types and traceback locations; all seven observations and expected metadata were present. Decode a string root output before requiring its completed outcome, and retain support for an already decoded object. Both forms now have explicit acceptance coverage.

The corrected probe verified actual backend outcome/versions/source/result/canary evidence and all lifecycle states. The focused telemetry/command suite passed 59 cases in 23.89 seconds. Reader-only source 9c1d2fca918ceb0b0d90f0ee7be0e704c7ccf7a9 leaves runtime/exporter, dependency lock, recorded calls and database behavior unchanged. Rerun the full locked suite and rebuild/reinstall the final wheel; preserve the prior 472-test and sixteen-database evidence as distinct results. Final clean-head read-back/replay and every hosted job are required before handoff, recorded on #22.


## Entry 21 â€” Distinguishing cancellation and cold worker startup

Date: 2026-10-17 (Africa/Lagos). Follow-up on unmerged H8 PR #78; diagnosis in progress.

**Files touched:** `.github/workflows/ci.yml`, `tests/test_ci_checks.py`, `tests/test_controls.py`, a lightweight test-worker helper, CI/controls study chapters and this journal.

### Context

The user asked why checks were red, then requested every identified issue be fixed before proceeding. Final source e072551 had two successful hosted runs, but the PR-body edit and ready event also produced a cancelled run whose always-running gate failed. GitHub retained both suites and reported an unstable merge state. Locally, the full suite had 472 passes and a 429 classification failure: the owned attempt returned timeout instead of rate_limited. The unchanged case passed separately. These are separate failures.

### Options considered and why

Allowing cancelled prerequisites to pass ci_checks.gate would weaken the gate, so keep its fail-closed comparisons. Change only the job scheduling condition to `${{ !cancelled() }}`: ordinary failure still schedules the gate, but cancellation does not run it as new failed work. Keep PR-body validation on edits. GitHub's expression documentation recommends this condition for work that must run after success or failure but should stop on cancellation.

For the SDK integration case, increasing a production deadline would change the contract without evidence of a runtime bug. Instead, reduce test-only child bootstrap imports and separate its cold-start classification allowance from the real interruption test. Three instrumented 429 attempts took 8.94, 7.29 and 10.14 seconds, including SDK imports of 3.23, 2.80 and 3.90 seconds and client/mock handling of 2.61, 2.40 and 2.65 seconds. All returned rate_limited. This establishes startup cost; the exact stalled stage of the historical failure is unknown because that run lacked stage evidence.

### How to build it

1. Replace only gate.if in the workflow; do not accept cancelled values in the Python gate. Extend workflow checks to preserve this boundary and retain the negative gate cases.
2. Move spawned worker classes into a small importable test helper that does not import pytest or the complete controls test module. Preserve actual Google SDK calls through httpx.MockTransport, child network denial and exactly one HTTP dispatch per owned attempt.
3. Use the policy's existing 60-second maximum only in the classification integration test. Record fixed child stages separately for each PID in the temporary test directory; assertions must show two completed real SDK attempts and one mock dispatch each. Failure diagnostics contain invented stage names, never exception bodies or credentials. Production defaults and limits stay unchanged.
4. Preserve the independent hang/cleanup test. Add deterministic coverage that startup exhausting the supplied deadline cannot return a late success. Run focused checks, the complete locked suite and exact-head hosted jobs before claiming acceptance.

### What went wrong

The old handoff selected a successful run and did not foreground the simultaneously retained failed gate. That made the summary less precise than GitHub's status. Do not delete history or rerun old broken source to make badges green. A passing retry also cannot prove the timeout's cause. Keep that uncertainty visible while fixing test isolation and adding phase evidence. Results follow after execution.


### First repair verification

The focused controls/CI suite passed 71 tests in 79.97 seconds. Real SDK 408/429/503 cases completed in 23.14/21.36/19.42 seconds respectively (two owned attempts each), with two complete phase records and exactly one mock HTTP dispatch per attempt. The unchanged eight-second hang test completed in 8.02 seconds and left no child. The deterministic late-frame check and strict gate negative cases passed. Ruff and formatting passed across 63 files. Next verify a real hosted cancellation and the full locked local suite; neither is claimed from these focused results.


### Hosted cancellation boundary

Pushed repair source 0f3e75681cbd08206a0435a40ce805470edeebe0, then deliberately cancelled owned run [38991322271](https://github.com/Protagonist01/my-production-agentic-systems/actions/runs/38991322271) while required work was active. Read back the completed run and all ten jobs: the workflow and CI gate were cancelled, four completed metadata/audit/scan jobs succeeded, and no job reported failure. This is actual GitHub scheduling evidence, not a Python simulation. No cancelled run is represented as a successful acceptance run. A later final-head run must complete normally.

The documentation audit first rejected the old immutable workflow slice because its gate condition changed. Re-anchor CI/replay chapters to the committed repair source and verify current bytes against that commit: 226 source ranges, 163 local links and 42 intended publication files passed. Full local tests are still running at this point.


### Final publication boundary

The full `python dev.py check` runs against the unchanged executable/test bytes of 0f3e756. This follow-up documentation commit records hosted cancellation proof and refreshes immutable workflow/test links; it does not change dependencies, production deadlines, captured fixtures or runtime modules. Publish the final-head normal hosted result and full local result on #22 after they finish. Inspect every suite associated with the final SHA, not only one selected passing run. The user reviews/merges PR #78; no H9 work starts during this repair.


## Entry 22 â€” Reporting every scheduled outcome

Date: 2026-10-18 (Africa/Lagos). H9 #23, branch codex/h9-scorecards, based on verified merged H8 main 21a5720. Work underway.

**Files touched:** new scorecard contracts, aggregation/statistics, paired comparison and private CLI modules, tests, root command and reporting/study/planning documentation.

### Context

The user reviewed/merged #78 and asked to proceed. H8 #22 is closed/completed after clean locked setup/check (475 passes in 281.95 seconds), exact six-call/two-timeout/zero-provider replay and main run 39164862391: nine applicable jobs passed, 475 tests per platform/Python cell and sixteen Postgres checks. PR-only metadata skipped deliberately. GitHub project reads failed with INSUFFICIENT_SCOPES; issue/manifest status is verified, native board status is not. H6/H7 prerequisites for H9 are already completed.

### Before you read on

An interrupted run has one fewer journal row than scheduled. Should its completion percentage improve because that row disappeared? If an average improves while a required case loses an approved pass, what evidence must a comparison preserve?

### Options considered and why

Aggregate only present rows is simple but rewards missing outcomes. Use the reviewed manifest plus complete H6 schedule as the denominator and join optional terminal rows to it. Validate report provenance against private manifest entries before deriving source/split labels. Keep every missing/error/scorer-failure row visible and preserve known unsafe outcomes even when another error occurs.

Counting repeated trials as independent safety samples would narrow uncertainty without evidence. Use reviewed group IDs as the unit: any observed unsafe trial makes its group positive; a group with no known event but missing/unverified work remains unknown. Report the possible event-count range and a 95% binomial interval envelope over its endpoints. Exact two-sided boundaries for zero/all events avoid a zero-width safety interval; use Wilson for interior counts. This assumes independent comparable groups, which the software cannot prove. Synthetic/replay reports are not real-world risk estimates. Do not bootstrap zero-event safety.

Reuse the accepted repository metric set and existing independently registered scorers. This task builds a reporting mechanism, not a new evaluation experiment or evaluator. H10 retains fresh-provider proof, baseline approval, release thresholds and eval-compare semantics. No new dependencies, live model calls or Langfuse service changes are needed.

### How to build it

1. Define closed count/rate, usage, group-uncertainty, per-case, slice and comparison DTOs. Require an external versioned policy listing required cases; allow an explicitly declared repeated-trial subset. No candidate-derived required-case list or quality floor is invented.
2. Revalidate the batch/schedule against LoadedManifest and the separately supplied fault plan. Match wrapped group/split/scorer/source/policy versions to the pinned case. Produce one safe metadata fact per scheduled key; never copy raw input/output, hidden state, scorer text or exception bodies. Reports still contain private case/group identities and labels.
3. Aggregate completion/review/safety/fault measures with visible numerators, denominators, unknowns and source/split/risk/tag/fault-kind slices. Keep partial usage as a known subtotal; an unknown component never becomes a complete total or zero. Never sum currencies together.
4. Compare matched case/trial keys only after checking manifest, mode, evaluator, treatment, state environment, seeds, clocks and declared trial population. Flag every previously passing required trial that fails or disappears, independently of an average improvement. Explicit baseline arguments identify a comparison; they do not approve a release.
5. Add a read-only journal CLI that requires reviewed manifest/policy inputs and a separately supplied baseline digest when comparing. Create a new private output directory exclusively, deny network, render JSON and escaped Markdown, and leave H10 commands fail-closed. Exercise adversarial missing/error/unsafe, mismatched provenance, mixed usage/currency, modes, escaping and zero-event cases before full hosted acceptance.

### What went wrong

No implementation result is claimed yet. Current Langfuse guidance confirms that dataset/evaluator versions and individual regressions matter more than a single average; NIST documents Wilson and exact binomial boundaries. We use these as reporting references, not as evidence of domain quality or approved release thresholds.


### First H9 source checks

The first reporting/CLI/fault/command run passed 58 tests in 7.74 seconds; strict types passed across 39 source files. The paired witness improves autonomous completion from 1/3 to 2/3 while case-0 loses its only approved pass to a missing outcome; the required regression remains explicit. Executed H7 fault fixtures independently inspect real invented file effects, and missing hook evidence earns no completion. Nine related trials in one reviewed group retain one safety sample and a nonzero upper interval. Raw output/hidden/scorer canaries are absent from generated metadata reports, which remain private because identities and labels are retained.

One boundary needs care: installing the CLI's network audit hook inside main would affect later inline tests, reproducing the earlier H7 failure. Install it only in the module execution guard; direct library calls remain composable. The module CLI still denies outbound connections. A write failure can leave partial files, so report failure and refuse an existing output directory on retry; no implicit cleanup or overwrite. Full suite/build/installed-wheel and hosted checks follow; focused checks are not final acceptance.


### Full core suite and final report formatting

The first full locked check passed 521 tests in 168.87 seconds with 39 typed source files, imports/Ruff/format/lock. A small Markdown-only adjustment replaces an escaped usage dictionary with readable subtotal/unknown tables; its focused reporting/CLI/fault/dispatch suite passed 59 tests in 4.57 seconds, including the newly added partial-write failure case. Reporter help text now distinguishes report software from candidate code. Run the final stable-source full check after these presentation/help changes; do not silently equate the earlier full result with later bytes. Build all six distributions and prove base-wheel operation without optional SDKs before Review.


### Installed-wheel and source-link verification

All six packages built. A fresh base-only wheel environment (isolated imports, no Google GenAI/Langfuse/OpenTelemetry SDK) matched all six new module bytes. Under outbound network denial in parent and spawned children, actual file-state trials produced two independently scored completions and two unnecessary reviews, recovered equal journals and generated four private JSON/Markdown files through the installed CLI. Both regressed trial IDs and the one required case were flagged; no baseline approval or release pass was issued and no provider call occurred. Raw fake input/output were absent from report text. No state directory retained unexpected files.

The documentation verifier caught old dev.main ranges in the gateway/replay chapters after the new dispatch branch expanded that function. Re-anchor only the affected source links to a25050a and add AST-verified reporting symbol ranges. The refreshed audit passed 252 immutable source ranges, 180 local links and 24 intended publication files, with configured secrets absent. Final stable-source locked/hosted acceptance is recorded on #23 after completion; the earlier 521-pass run and the final-render 59 focused passes remain distinct.


### Review publication

H9 is published in PR #79. The implementation commit is a25050a; source links and installed-wheel evidence are recorded in 482a575. Final stable-source local/hosted checks are running and will be read back against the final documentation head on #23 before handoff. The Review snapshot links a concrete implementation and measured focused/full/package evidence; it does not treat pending CI as a pass. Keep #23 open and its merged checkbox unchecked until user review/merge and post-merge acceptance. No H10 work begins during this review. Native project-board transitions remain unverified after the explicit project-scope rejection.


## Entry 23 â€” Fresh dispatch receipts and independently reviewed releases

Date: 2026-10-18 (Africa/Lagos). H10 #24, codex/h10-release-evidence, based on verified fd87750.

**Files touched:** release contracts, fresh recording adapter, evidence verifier/gate, CLI, tests and documentation.

### Context

The user reviewed/merged #79 and asked to proceed. H9 acceptance on merged main passed locked setup/check (521 tests in 209.75 seconds), strict replay (six calls, two recorded timeouts, zero provider calls), and main run 39167447801 (nine applicable successful jobs, 521 tests in each quality cell and sixteen database tests). #23 is completed; #17 was already closed. Native board access remains unverified. The user explicitly chose offline mechanism verification only for H10; no live model call is authorized by this acceptance plan.

### Before you read on

Three equal answers can still come from three fresh requests. What should be counted to distinguish real dispatch from cached answers, and who is allowed to approve the baseline?

### Options considered and why

Incremental slice reuse needs a trustworthy dependency map that this repository does not yet have. Choose conservative whole-population invalidation on any declared behavior change. Require an externally pinned candidate specification covering source/configuration, prompt, route, tools, policy, scorer and environment; do not infer freshness from answer diversity. Keep separately pinned baseline approval and policy inputs outside the recorder. Neither eval-record nor eval-release creates or updates approval.

The H6 owned worker is a daemon and cannot spawn an H4 isolated transport child. Compose ProviderGateway directly with a deadline-aware transport inside the H6 whole-worker deadline, and retain BoundedGateway reservation/retry controls. Partition the externally bounded recording budget across sequential trials rather than pretend process-local controls share a global quota. Capture raw per-attempt receipts exclusively before returning the response to the agent. Missing receipts or worker failures remain failed evidence. Mock receipts can test dispatch mechanics but always block a production release.

### How to build it

1. Define immutable candidate specifications, capture manifests, external baseline approvals and release policy/decision DTOs. Canonical SHA-256 pins cover nested values; callers provide expected pins separately.
2. Validate exactly three fresh trials per case, the complete reviewed case population and matching candidate versions. Create a new private execution directory; no prior-response input or resume exists. Adapt trusted agent/transport/scorer factories to H6, wrap the transport in the owned gateway, and persist each dispatched attempt with its context, request, response and unique nonce.
3. Seal the batch and receipt hashes into an evidence manifest. On reading, revalidate journal, receipts, identities, accounting and behavior against the external candidate pin. A modified artifact must invalidate its digest.
4. Compare compatible populations and independent evaluator versions. Refuse a candidate used as its own baseline; require a separately pinned, unexpired approval bound to exact baseline and policy. Enforce explicit required-case floors, pass regressions, completeness and zero critical violations before a release decision.
5. Exercise these mechanisms with invented fixtures/provider mocks only. Keep actual provider freshness, domain thresholds and release approval unclaimed. Record commands and results after they execute.

### What went wrong

No implementation result yet. Freshness receipts are trusted local execution evidence, not cryptographic proof against an operator who controls the code and can forge all approval inputs. Document that boundary explicitly.


### Initial mechanism checks

The first focused recording/gate/command suite passed 58 tests in 54.67 seconds. Three identical mock requests yielded three identical answers but distinct per-trial receipts; a second execution produced disjoint nonces. Tamper witnesses cover missing, modified, extra, replayed-identity and duplicate-nonce receipts and journal deletion. Gate logic tests use explicitly artificial provider-labelled DTOs only to exercise the positive branch; they are never saved as real provider results or offered as a domain approval. Actual persisted runs retain origin=mock and cannot pass release.

The five CLI checks passed in 18.00 seconds: real spawned mock recording, offline comparison, mock release rejection, unchanged approval bytes, missing/wrong pins and refusal to record from previous response evidence. Before the full check, tighten built-in composition validation: prompt/model/tools, scorer implementation, policy and file-state environment must match declared fingerprints. Require every executing harness Python file plus uv.lock in its reviewed inventory and verify those bytes against the source root. Generic adapters remain trusted code responsible for declaring all behavior dependencies. No runtime SDK/dependency change or live provider call is part of this work.

The initial strict type check caught a pin helper restricted to Contract although model requests use WireContract; accept the shared canonical wire base. This is a type/API correction, not a failed experiment. Full checks and installed-wheel evidence follow.


### First full check

The complete locked check passed 570 tests in 200.02 seconds, strict types across forty-four source files, both import boundaries, Ruff and lock validation. The first aggregate invocation stopped at formatting for two newly patched files; format them and rerun the aggregate before citing this result. No test failure occurred in that formatting-only stop. These checks exercise the actual mock recorder and negative release paths, not a live provider or reviewed domain quality baseline. Build/install/source-link checks follow.


### Installed wheel and documentation boundary

All six packages built. A fresh base-only wheel environment, with Google GenAI/Langfuse/OpenTelemetry SDKs absent, matched all five new module bytes. The installed CLI recorded two actual mock executions (three trials each), independently scored six completions, verified raw receipts/journals and produced a comparison. Parent and spawned workers denied outbound network. eval-release returned nonzero with exactly baseline_mock_evidence and candidate_mock_evidence; approval bytes remained unchanged. This is six mock dispatches and zero provider calls, not a fresh domain quality result.

Executable source is 6b20fb959e5f54a71495aeac97f5c6b9b54ca182. The documentation scanner found obsolete root-command constants, dev.main and command-test ranges after H10 replaced PLANNED. Re-anchor changed symbols and update their prose, retaining unchanged historical slices. The refreshed audit passed 279 immutable source ranges, 197 local links and 23 intended publication files with configured secrets absent. This documentation follow-up changes no executable/test/dependency bytes. Final clean-head replay and hosted checks are recorded on #24 before handoff; user review/merge remains required for completion.


### Review publication

Published H10 in PR #80, attached it to the chat, and marked #24 Review while keeping it open and its merge checkbox unchecked. Initial hosted run 39169936224 is in progress, not accepted yet. This small follow-up records the actual PR link; executable source/test/dependency bytes are unchanged. Verify every suite on the resulting final SHA and the PR merge state, then append exact results to #24. User review/merge and post-merge verification remain the completion boundary. No Olist/domain task starts during review.


## Entry 24 â€” Parallel source preparation and honest historical order views

Date: 2026-10-18 (Africa/Lagos). O2 #27 on codex/o2-orders-360, based on verified merged #80 main54f5af2. C1 #34 proceeds in a separate managed worktree/branch under explicit user choice.

**Files touched:** Olist import/storage/view modules, tests, source operations/study docs and shared planning/type-check scope.

### Context

The user reviewed/merged #80 and requested multiple issues for speed, then explicitly selected O2+C1 in parallel. H10 post-merge locked setup/check passed570tests252.92s plus exactsixcall/twotimeout/zero-provider replay; main39170421239 passed nineapplicable jobs, actual570tests ineachqualitycell and16databasechecks. H10 is completed; nativeboardstatus remains unverified. O2/C1 have merged prerequisites and independent package/data boundaries. SeparatePRs preserve targeted review and do not skip dependentO3/C2 gates. This explicitly changes the earlier single-issue-at-a-time execution for independent work only.

### Before you read on

An order has two items, two payments and two reviews. A flat join yields eight rows. Which amounts should be summed once, and when can a historical view reveal a payment row whose source has no recorded availability timestamp?

### Options considered and why

Reject a raw many-to-many join: summing after it would inflate money and count rows. Import explicit source grains into separate SQLite tables with key/foreign-key checks; compute each child's totals independently before assembling one order row. Full review_id is not globally unique in the actual source; the inspected key(order_id,review_id) is unique. Keep missing amounts/counts distinct from zero. Use exact Decimal parsing and integer minor units, without inventing a currency.

Do not assign historical availability of items/payments/customer attributes/estimated delivery/final status from purchase time: their source has no observation timestamp. Keep those facts hidden until an externally declared snapshot observation time. Event timestamps and completed review answers can support a limited effective-time projection; hide future facts, retain source-local clock semantics without timezone conversion, and document that this is not a historical ingestion log. Raw Portuguese text and source category translations stay separate.

### How to build it

1. Verify the externally pinned O1 manifest and rawCSV hashes outsideGit, import needed tables at declared grain, and validate widths, keys, references, finite two-decimal amounts and source timestamp formats. Build a new privateSQLite file exclusively; never overwrite an earlier derivedsnapshot.
2. Make independent per-order item/payment/review aggregates, reconcile their global totals/counts with source tables, and preserve exact source strings/missingness. Emit only aggregate provenance/count/checksum evidence toGit; keep source rows and database outsideGit.
3. Expose a read-only OrderStore requiring explicit tenant-bound allowed-order scope, naive source-local as_of and declared observed_at. Refuse out-of-scope access. Return no future delivery/review data and no snapshot-only details beforeobserved_at; never translate reviewtext automatically or label sourceamounts BRL without evidence.
4. Test join-multiplicity witnesses, duplicate/orphan corruption, historicalfuture canaries, unknown availability, sourcehash changes, scope violations and exact decimal sums with inventedCSV. Then verify actual pinnedOlist source and fullpackaged flow without provider calls. Add vertical sources to strict mypy so CI checks new applicationcode.

### What went wrong

No implementation result yet. The actual snapshot inspection found802 duplicated review_id keys(up to3orders), but no duplicate(order_id,review_id) pairs; source rows/IDs were not printed. Treat grain discovery as evidence, not a reason to deduplicate real observations silently.


### Availability refinement and first source verification

Tighten the first design before implementation: a review answer timestamp does not establish that final text/score was never edited later. Keep all final review content hidden until the declared snapshot observation boundary, then also require answer_at <= as_of. Recorded order events remain an explicitly limited effective-time projection, not a recovered ingestion log. Reject an observation boundary before any recorded actual event; estimated/shipping dates remain plans. The real-source drill uses declared source-clock boundary 2026-10-18 00:00:00, not a claimed UTC conversion or recovered historical observation.

The focused source/order suite passed 27 tests in 8.05 seconds, and strict mypy passed 52 source files. The eight-row join witness produced inflated item total12012 while the independent aggregate retained3003. All99,441 authentic orders imported with112,650items,103,886payments and100,000reviews; key/reference/count/amount checks passed. Exact integer-hundredth totals reconciled: price1,359,164,370, freight225,190,954, payment1,600,887,212. These are undeclared source-unit sums, not a currency or business-value claim. The private database digest is in docs/data/olist-orders-v7-report.json; no source rows orIDs were exported.

A deterministic read smoke check selected the first1,000 source orders byID solely for software verification. At each purchase clock, no future events or snapshot-only fields/text leaked; at the declared observation boundary child counts matched returned rows. Currency remained null; no provider call occurred. This is not a sampled model evaluation or source-wide claim about historical ingestion. Full checks/package/source-link verification follow.


### Review caught two SQLite lifetime bugs before publication

Independent read-only review reproduced a pin violation with an invented database: after opening a store with the correct digest, another SQLite connection committed a changed order and the already-open store returned it. A read-only connection alone does not hold a stable snapshot. A WAL can also contain committed changes absent from the hashed main file. Reject WAL/SHM/journal sidecars, begin and retain a read transaction, read metadata to acquire its shared lock, then recheck the main digest while the lock is held. A writer's commit must remain blocked while the store exists; close releases the snapshot. Constructor failures must close the connection.

The reviewer also reproduced a Windows file-handle leak: `with sqlite3.connect(...)` manages transactions but does not close the connection. The imported database could not be renamed until garbage collection. Wrap the connection in contextlib.closing as well as the transaction context. A test retains a strong reference to the actual connection and requires SQL access to raise ProgrammingError after import returns. These are verified bugs in the unmerged O2 implementation, not claims of production exploitation. Add the three meaningful resource/pin witnesses before rebuilding/retesting.

The first complete O2 run had592passes and one unchanged H6 worker test failure: expected timeout but receivedworker_cleanup_error. Its cleanup waits are two bounded0.25second joins; the result correctly fails closed rather than releasing potentially live state. It occurred while source imports ran, but the cause is not established by that coincidence. Preserve the failure, recheck that case and rerun the final complete check after source work finishes; do not weaken production cleanup or treat an isolated retry as proof of cause.

The first installed base-wheel drill imported all99,441 real orders under network denial and read100 deterministic orders with optional SDKs absent. It matched the pre-repair three module bytes. This is useful earlier evidence, not final-byte acceptance: rebuild/reinstall and repeat the final snapshot/read/CLI checks after the SQLite repairs.


### Final repaired source and installed boundary

Committed executable source as0781dddf0577bd8e00db94e04d15198050ffd4af. The repaired source/order plus unchanged H6 timeout case passed31tests40.29seconds; strict types passed52sources. Allsixpackages rebuilt and the base-only wheel was reinstalled. Under network denial, the final installed three module bytes matched source; its CLI imported hand-invented separate grains and returned exact3003/3203 totals, hid future/untimed facts, retained Portuguese text and nullcurrency, then released all handles so the file could be renamed. The repaired reader also verified/read the full99,441-order privately pinned real store. Optional model/telemetry SDKs and pytest were absent. Final-byte import/reader acceptance is separate from the earlier full real-source pre-repair wheel drill.

Source anchors are pinned to0781ddd. Expanding strict type-check scope invalidated the old full pyproject slice; refresh that anchor while retaining other historical slices. Documentation verification passed298 immutable ranges,209local links and17publicationfiles withconfiguredsecrets absent. Source/modeldatafilesremainoutsideGit; aggregate reports carry no rawrows/IDs/text. Finalcompletechecks and exact-head hostedacceptance remain pending, not claimed from the focusedrepair result.


### Review preparation and combined acceptance

Move O2 to Review with the concrete source/package/source-data evidence, while preserving the first local failure and pending final acceptance. Publish its PR early so hosted jobs can run while C1 finishes. A separate temporary integration checkout combines O2source0781ddd and C1source1dd98fb; only the parallel BuildBook append conflicts, resolved by retaining the O2 copy for this temporary validation. It is not a user PR merge or a replacement publication branch. Run the combined locked full suite after C1's current full suite finishes to avoid duplicate heavy local runs. Exact final CI and combined evidence will be recorded on each issue before handoff.


### Published O2 review and final batch verification

2026-10-19: O2 is published in PR#81 and C1 in PR#82, both attached to the chat and their issues remain open in Review. O2 publication head6ae7ff8 passed hosted run39172484822, alltenjobs: actual596tests per Ubuntu/Windows Python3.12/3.13 cell, sixteenPostgres tests, strictreplay and allsixbuilds. This final metadata commit records the concrete review links without changing executable/test/lock bytes from0781ddd. Verify its exact-head checks before handoff; historical passing runs do not replace that read-back. Combined-source local validation is running against O2source0781ddd+C1source1dd98fb; its result will be appended on#27/#34 after completion. The first592pass/cleanupfailure aggregate remains recorded above; production cleanup was not weakened.


## Entry 25 â€” Archive-grounded CFPB preparation in parallel

Date: 2026-10-18 (Africa/Lagos). C1 #34, codex/c1-cfpb-import, based on merged main 54f5af2. O2 proceeds independently in another worktree after the user explicitly selected O2 + C1 in parallel.

**Files touched:** CFPB source preparation modules, private SQLite boundaries, invented importer tests and source/study documentation.

### Context

The user reviewed and merged #80. Parent verification of merged main passed locked setup/check (570 tests in 252.92 seconds), exact replay (six calls, two recorded timeouts, zero provider calls), and hosted run 39170421239 (nine applicable jobs, 570 tests in each quality cell and sixteen database checks). C1 is source preparation, not a classifier or reviewed risk-label dataset. The user explicitly chose the complete September 2023â€“March 2024 archive cohort with March held out.

Current primary-source research changed the acquisition plan: CFPB ceased narrative publication in August 2026 and moved previously published narratives to its FOIA archive. Current live API exports therefore cannot serve as the narrative source. The official archived ZIP is bounded at 100,880,669 compressed bytes; raw source and derived records stay in external local storage.

### Before you read on

How would you prevent a target label from reaching a classifier while also keeping repeated complaint text out of multiple time partitions? Sketch the two storage schemas and decide what happens to a duplicate that straddles a cutoff.

### Options considered and why

A random capped sample is cheaper but adds a selection decision; the user selected the complete bounded archive. A single wide table with a friendly input projection leaves target columns alongside every agent read. Choose separate narrative-only agent and scorer databases, and a closed input type. Preserve consumer-selected labels exactly in scorer storage; do not invent reviewed truth. Assign Septemberâ€“December to development, Januaryâ€“February to regression and March to holdout. Normalize only for exact duplicate grouping; quarantine every group crossing time cutoffs rather than move future records into development. No consumer identity is available, so exact-text grouping cannot promise consumer-level or near-duplicate independence.

### How to build it

1. Download the fixed official ZIP and August 24, 2023 taxonomy PDF outside Git, hash their exact bytes, and record the publisher URLs plus aggregate schemas/counts. Pin those digests for every subsequent import; never silently replace source bytes.
2. Validate the ZIP member and CSV schema before reading rows. Stream into a private staging SQLite file rather than retain all narratives in RAM. Count missing text/labels and masking tokens; retain source date and exact target labels only on the evaluator side.
3. Hash case IDs and normalized narrative groups, assign dates to fixed windows, and quarantine groups spanning partitions. Write a separate agent database containing only opaque case ID and original published narrative, plus a scorer database with dates/splits/groups/consumer labels. Do not append company, response, issue or product metadata to inputs.
4. Seal file hashes and aggregate evidence in a new manifest. Verify schema, counts, one-to-one case membership and group partition integrity independently before publishing aggregate provenance. Refuse existing output paths and source/output paths under a Git checkout.
5. Exercise leakage, boundary dates, duplicates, missing text, malformed schema and tamper failures using invented complaints. Inspect complete real-source aggregates separately; neither source preparation nor passing plumbing tests establishes classification quality or reduced consumer harm.

### What went wrong

No implementation result yet. The original live-API direction was ruled out by the official 2026 source change before coding. Archive selection already conditions on consent, scrubbing and publication eligibility; missingness counts within this archive do not describe every complaint received by CFPB.


### First C1 mechanism checks and host storage boundary

The first 22 invented-data checks found eight failures before ingestion: this host has a real C:\.git ancestor, so a strict outside-any-checkout guard correctly rejected both the usual C: cache and pytest temporary directories. Keep the guard strict. Move the raw ZIP/PDF to D:\document\.cache\production-agents\cfpb and set TEMP/TMP only in this verification shell to an external D: test directory. CI's ordinary temporary directories remain outside its checkout. This corrects the initial cache location before preparing source records; no exception weakens source storage.

Focused importer/CLI/acquisition verification then passed 26 tests in 3.29 seconds. These cover physical/typed target isolation, exact-text groups across cutoffs, all date boundaries including leap day, missingness/masking, source/target pins, malformed rows/inventory, output tampering, no-overwrite and bounded host-restricted downloads. Strict types found a ZIP stream typing mismatch: use explicit chunked SHA-256 because the advertised ZIP IO type does not promise readinto even though the concrete reader supports it. This does not change the digest encoding. Complete real-source preparation and full checks remain pending.


### Complete historical-source preparation

The actual pinned archive preparation completed successfully from source commit 8ddf6c1. It scanned 945,532 records, all within the user-selected seven-month window, and found 626,728 missing narratives. This corrects a possible interpretation of the FOIA page: its full-record archive includes records without published text, while the usable narrative subset is additionally selected by consent/scrubbing. Of 318,804 narrated records, 1,651 normalized groups spanning time partitions account for 58,066 quarantined records. The final private pair contains 260,738 records (139,732 development, 71,859 regression, 49,147 March holdout), 206,109 groups and eleven observed product selections.

The profile counts 229,967 narratives with whole-word X patterns and 5,757,323 such tokens before quarantine. These are masking-pattern counts, not privacy verification. One source issue is empty on a record already excluded for missing narrative; the conditional narrated-target exclusion counter is zero. Closed agent/evaluator SQLite files are approximately400MB/104MB and remain outside Git. The aggregate manifest alone is copied into documentation. Current-code verification and installed-wheel checks follow; model-quality and independent risk labels remain absent.

The focused suite now passes 28 checks in 5.06 seconds, including an active WAL witness: a write-ahead sidecar makes the sealed output inventory invalid before any database content is accepted. The source acquisition helper also rejects an initial nonofficial URL, in addition to redirect checks.


### Final local and installed acceptance

Verification completed against executable source1dd98fb66426b7c992a794d8f0a1232a8d32383b. The complete locked check passed599tests in322.20seconds with53strict typed sources, both import contracts, Ruff/format/lock. The final focused suite passed29tests5.16seconds, including active WAL inventory rejection and a deterministic change-during-verification witness. Allsixpackages built.

A base-only installed wheel matched allfive package module bytes (four implementation modules plus the package marker), with Google/Langfuse/OpenTelemetry absent. Under network denial, its current verifier read the independently pinned copied documentation manifest and verified all260,738prepared records,206,109groups and exact139,732/71,859/49,147split counts. No source row, provider call or model evaluation was produced. Source acquisition/ingestion remains dated2026-10-18; this final documentation handoff is2026-10-19. Independent source review found no actionable C1 issue; it did not validate consumer labels as truth.

The parent coordinates publication after an interrupted delegation. C1 is a separate PR from O2, with its issue kept open in Review until user merge/post-merge acceptance. Temporary combined-source validation uses O2source0781ddd and C1source1dd98fb, without merging either user PR. Exact hosted/final combined evidence remains pending and will be recorded on#34 after execution; no pending result is counted as a pass.

Entry25 follows the O2 Entry24 reserved in the parallel [PR#81](https://github.com/Protagonist01/my-production-agentic-systems/pull/81). These independent append histories will be reconciled after the first reviewed PR merges; no earlier journal history is deleted.


### Published C1 review

C1 is published as PR#82, attached alongside O2 PR#81. The issue and manifest retain Review, with the merge checkbox unchecked. This metadata follow-up changes no executable/test/lock bytes from1dd98fb. Verify all ten applicable hosted jobs at its final head before handoff, then record actual combined625-test population results if the combined run passes. The two PRs have independent source changes; reconcile their parallel journal/planning appends after the first reviewed merge. No user PR is merged automatically.


### Reconcile C1 after O2 merge

2026-10-19: the user reviewed/merged PR#81 as36ad712436c9437512745d192da844a984d14d13 and asked to proceed. Merge origin/main into the existing C1 branch without rewriting its reviewed source history. Conflicts are confined to six shared documentation/planning files; preserve complete O2 Entry24 and C1 Entry25, both source studies, both task records and the independent source/use boundaries. Source files and test logic merge without conflicts. O2 post-merge verification is running and will be recorded before marking itDone. C1 remains open in Review; its re-integrated final-head checks must pass before handoff. This reconciliation creates no model call, new source cohort, policy label or business behavior.


The resolved tree retains exact O2source/test bytes0781ddd and C1source/test bytes1dd98fb, plus shared harness/config/lock bytes equal to main36ad712. Focused source verification passed59tests8.27seconds. The combined documentation audit passed322immutable source ranges,225local links and18intended publication files with configuredsecrets absent. These are focused/documentation results, not a claim that the final full integrated run has passed yet. Both source chapters now distinguish original inspection from the merged O2 status. The original source datasets, prepared manifests and independently reviewed pins are unchanged.


O2 post-merge acceptance completed on clean36ad712: locked setup/check596passed198.88seconds,52typed sources/imports/Ruff/format/lock; strictreplay consumed6calls/reproduced2timeouts with zero provider calls. Mainrun39229270824 passed allnineapplicable jobs, with actual596tests perqualitycell and16Postgres. Close#27 ascompleted and update its manifest/task checks; nativeprojectDone remains unverified. Preserve C1#34 in Review, its merge checkbox unchecked, and verify its final merged-main head before user handoff. No O3/C2 work starts during this reconciliation.


## Entry 26 â€” Constructed policy and review evidence before domain baselines

**Files touched:** `projects/olist-support/src/olist_support/policy.py`, `docs/olist-policy.md`, O3 case preparation and tests. Started 2026-10-19 from user-merged C1 main `2988428`. The user selected O3+C2 as the next batch; this branch owns O3 only.

### Context

Olist has historical order/payment facts, but no refund policy, verified currency, refund ledger or non-delivery confirmations. CFPB has consumer-selected labels but no independently reviewed risk labels. Neither source can supply the missing business truth by itself. The user accepted a constructed full-refund-only policy for confirmed canceled, paid, undelivered orders, capped at 100.00 simulation units; unknown/conflicting facts, over-cap amounts and reship requests require review.

### Before you read on

How can a source-grounded cancellation example produce a useful refund proposal without pretending that a missing delivery timestamp proves non-delivery, or that the source declared a currency?

### Options considered

- Infer currency from country and non-delivery from a blank timestamp: rejected because neither inference is source evidence.
- Route every scenario to review: safe but cannot exercise the accepted valid-refund path.
- Keep the source view unchanged and supply explicit, timed, fictional scenario confirmations: chosen. Label every such case hybrid and keep the original unit unknown.

### Why

A controlled demonstration can choose its policy and ledger facts, provided those choices do not masquerade as observed commerce. Policy proposals remain separate from business writes. Literal expected decisions and reviewer evidence must be authored separately from the policy implementation, otherwise the evaluator merely repeats the same bug.

### How to build it

1. Preserve O2's `OrderView` and its conservative visibility boundary. Do not modify its currency or source events.
2. Define a strict scenario-confirmation record keyed to tenant/order, with its availability time, explicit SIM unit, payment/non-delivery confirmations and prior refunded integer amount. Its values are constructed, never imported refund history.
3. Implement a pure proposal function. Revalidate input contracts, reject mismatched scope and future scenario evidence, then require visible cancellation, complete positive payment, independent non-delivery confirmation, no contradictory delivery event and no previous refund. Compare integer hundredths to 10,000. Partial/excess amounts and reship requests require review.
4. Return a proposed action and reasons, never a success/committed-money assertion. O4 will enforce actual transactions and stable business-operation identity.
5. Author evaluator-only expected outputs as literals; preserve source/edit provenance and group all edits by order into one split. Obtain review before describing these outputs as gold or releasing baseline claims. Keep source-grounded private records outside Git; public tests use invented orders.
6. Run focused boundary tests before the full locked check. Record actual results when available; no result is claimed at design time.

### What went wrong

No implementation result yet. The first design review exposed two important traps: unknown currency must not become BRL through an overlay, and a blank delivery field cannot serve as independently confirmed non-delivery. The explicit hybrid boundary addresses both. Human risk-label review for C2 remains a separate dependency, not something a candidate or rule baseline may manufacture.


### First implementation check

The initial thirty pure-policy witnesses passed. The private pipeline test then caught a portability bug: a digest computed from intended Unicode text need not identify the bytes written by Windows newline/encoding defaults. Preserve the failure: one of33focused cases failed; the implementation types passed59sources. Write private JSON explicitly as UTF-8 with LF, and verify its actual bytes in tests. Literal expected outputs remain separate from runtime calls. The standalone single-file mypy invocation also hid the local harness package and reported untyped imports; the repository's complete `python dev.py types` invocation correctly resolves all source roots. A real Literal annotation fixed the separate policy-version default type error.


### O3 source and package acceptance

Executable source15908425fa0735317a9e5ec281e7948c9aaa9bba passed the full locked check:658tests511.08seconds,59strict typed source files, both import contracts, Ruff/format/lock. Focused33tests passed after the encoding fix. The actual pinned O2 store produced12hybrid cases in6order groups,4per split,6base/6adversarial;3refund proposals and9reviews matched literal provisional AI policy-table expectations. No business write or provider call occurred.

Allsixpackages built. A base-only installed Olist wheel matched all7modulebytes and read the independently pinned private evaluator file under network denial, with optionalSDKs andpytestabsent; all12proposals matched. This validates installed mechanism behavior, not human adjudication or a transaction. Documentation audit checked329immutable source ranges and242local links. Raw/private literal scans and final exact-head hosted checks are recorded on#28 after completion. Keep issue open in Review until user merge and post-merge acceptance. No O4 work starts on an unmerged prerequisite.


## Entry 27 — Blind provisional risk review before deterministic baselines

**Files touched:** `projects/cfpb-triage/src/cfpb_triage/review.py`, baseline/review tools and tests, `docs/cfpb-risk-guideline.md`. Started 2026-10-19 on verified main `2988428`, independently of the O3 branch's reserved Entry26.

### Context

The user selected O3+C2 after merging #82, then asked Codex to perform the first risk-label review. The agreed proposal is twelve real narratives, four from each existing split, selected by a fixed hash before inspecting labels. No qualified human reviewer is established. The resulting judgments must be AI-reviewed and provisional, not promoted to human ground truth.

### Before you read on

If a rules baseline generates its own risk labels, what would a perfect score actually mean? How do you keep the review evidence separate from candidate outputs and prevent a small convenience batch from becoming a claimed release benchmark?

### Options considered and why

Using consumer product/issue labels as risk truth would answer a different question. Generating risk labels with the baseline itself would measure self-consistency. Instead, freeze a written rubric, select distinct exact-text groups with a fixed hash, expose full narrative text alone, record the review before calculating baseline outputs and pin its bytes. One AI reviewer cannot establish human validation or inter-reviewer agreement; record those limits as missing evidence rather than zero disagreements.

### How to build it

1. Verify C1's externally stored prepared manifest against its reviewed digest. Read only group/split/case identifiers for selection; never use product/issue labels, keywords or predictions in the sampling function.
2. Rank groups by SHA-256 of a fixed seed/domain/group ID, choose four in each split, choose one fixed representative per group and shuffle presentation with another domain. Write narrative-only `blind.json` and separate evaluator-only `selection.json` outside every Git checkout. Recheck source pins after reading.
3. Write a versioned rubric for elevated/routine/uncertain risk and clear/ambiguous interpretation. Record reviewer identity/kind/time, source text digest, exact Unicode evidence offsets and rationale for each entire narrative. Elevated judgments require a concrete supporting span. Preserve all twelve rows; no silent exclusion of difficult cases.
4. Reject missing/extra/duplicate reviews, wrong narrative digests, invalid evidence and false prediction-blindness claims in the schema. Keep reviewer identity/truthfulness an explicit trusted assertion; software cannot authenticate an independent judgment.
5. Seal the review byte digest before running majority or fixed rules. Fit any majority using development only, freeze tie handling, and report each split's actual denominator. Keep provisional risk agreement separate from consumer-label reference agreement and from actual harm.
6. Test invented cases and source/label-isolation boundaries offline. Preserve any additional reviewer disagreement without silently choosing a preferred label. No live Langfuse dataset or provider call is required.

### What went wrong

No results are claimed at design time. A planning clarification mattered: the user asked the agent to label the cases, so waiting indefinitely for an unspecified human reviewer would not satisfy the request. Proceed with honest AI-review provenance and leave human/adjudicated validation unestablished.


### Review and first baseline evidence

Read all twelve complete narratives in the shuffled blind packet before writing/running a baseline. Record one AI reviewer, guideline bytes, exact Unicode spans and separate rationale, then seal reviews6f7dd5a0603aa7326d9b2ab9e28e74a6b4f5a92b5028d11ca8ad456865a3b9b3. Judgments:9routine/1elevated/2uncertain and10clear/2ambiguous. Zero human reviews and no comparable reviewer pairs mean disagreement is null/unassessed, not zero.

The first packet's metadata exposed the Windows intended-text versus actual-byte pin bug also caught in O3. Preserve original blind/review bytes and original selection metadata. Create selection-v2.json correcting only the packet byte pin and adding the rubric digest. Membership, narratives, splits and judgments are unchanged. Current generation writes UTF-8/LF; an invented pipeline test now checks actual file bytes.

Twenty focused invented checks passed1.08s. Strict types passed59sources after a heterogeneous per-class dictionary caused mypy to infer the F1 sum as object: accumulate float F1 values separately instead of suppressing the error. The first pilot finds majority risk matches9/12 but misses the only elevated holdout case; rules match5/12 and send7/12 to review including that positive, with false positives from legal/negated/unauthorized wording. Preserve these failures without tuning on the reviewed holdout. Fixed rules were authored by the same agent after blind labels were sealed; do not claim independent model-development or human validation.

The complete consumer-reference baseline remains a separate report across260738records. Majority product and conditional issue choices fit development only; keyword product rules take narrative alone. Static review clarified the distinction between most frequent joint label and most frequent product followed by conditional issue; the final implementation uses the latter and reruns the complete report. This is a deterministic development specification correction before candidate tuning, not an improved-risk claim.


### Bounds review before publication

Static review found that Python slicing clamps an oversized end offset: a reviewer could supply an end past the narrative length while the selected suffix text still matches. Reject end offsets beyond the actual Unicode text length and add an invented witness with a matching tail plus oversized end. This is evidence-integrity correctness, not a claimed remote vulnerability. Preserve the original complete-suite result's source boundary and run the repaired evidence tests/current hosted suite before publication acceptance.


### Repaired package and publication evidence

Repaired source087d4703f4ae72cb9aa75b5c68418f76392d8cea passed21focused cases6.10seconds and strict59source types. The complete consumer-reference report rerun exactly reproduced all initial counts/metrics after majority-fitting clarification; no observed-metric improvement is claimed. Allsixpackages built. The rebuilt base-only CFPB wheel matched8modulebytes and exactly reproduced the sealed12caseprovisional-risk aggregate report undernetworkdenial with optionalSDKs/pytestabsent. Existing C1 source/ingestion bytes remain unchanged.

Documentation verification passed331immutable source ranges/250local links. Literal publication scans checked all260738preparednarratives (complete strings at least40characters) and99441OlistorderIDs against20intendedfiles with zero matches. This is a limited literal check, not a privacy certification. Combined O3source1590842 and repairedC2source087d470 focused verification passed54new tests9.44seconds. Full/current-head hosted results remain on#35 after actual completion; no pending result counts as a pass. Keep C2 open in Review until user merge and verified main, with human validation explicitly unestablished. Shared Entry26/27 planning appends must be reconciled after the first user merge.


### Reconcile after O3 merge without repeating identical source work

2026-10-19: user merged#83 asde04a96 and said the pace was too slow. Exact Git tree comparison proves main equals reviewed e65b866. Main hosted run39330860614 passed; verify applicable job statuses and clean-main replay before closing#28. Merge main into C2 and preserve complete Entries26/27 plus both code chapters. Five shared documentation/planning conflicts require edits; executable/test bytes do not conflict.

Keep source/test/config bytes identical to combined snapshot1dd54e7, whose54focused tests,62typed sources, imports, clean replay and six builds already passed. Reuse fixed artifact pins and installed proofs; rerunning real-source ingestion or every full local suite after a documentation-only merge adds time without new evidence. Run one focused check plus documentation validation, and accept the final required hosted matrix for the full679-test integrated population only after it succeeds. Results are maintained on#35 rather than committing a new metadata change that restarts CI. No source behavior, label or baseline changes here.


## Entry 28 — Transactional refunds and a bounded LangGraph workflow

**Files touched:** Olist backend/schema/workflow modules, their integration tests, optional workflow dependencies and operations. Started2026-10-20 from verified O3 mainde04a96. Entry27 is reserved in C2#84 and will be preserved when that reviewed branch integrates. The user explicitly approved combining O4#29 and O5#30 in one PR to reduce review cycles; O5's O4 prerequisite is satisfied inside this reviewed bundle rather than requiring a separate intermediate merge. O3 is already merged/verified.

### Before you read on

A refund commits, but the process crashes before a graph checkpoint or response is saved. On restart in a different run, how can the system return the original effect without refunding twice? What must be checked even before returning an old receipt?

### Options considered and why

A memory-only ledger/checkpointer is easy but cannot survive process restart. SQLite would simplify local tests, but F4 already supplies isolated restricted Postgres databases and O4 needs real concurrent transactional evidence. Use a vertical-owned Postgres schema in an F4 trial database, with the official persistent Postgres LangGraph saver in its own schema. Keep base import/source/policy installation light; expose LangGraph/checkpointer through an explicit optional workflow extra. Retain the reviewed LangGraph1.2.15 pin and verify checkpoint-postgres3.2.0 compatibility before relying on it. No shared harness API or migration is replaced.

### How to build it

1. A trusted bootstrap admin creates Olist-owned tables and checkpoint schema, records immutable schema version/checksum and grants only required table privileges to the trial role. Agent-visible tools receive a bound connection factory and explicit caller grant, never admin credentials or SQL authority.
2. Enroll a pinned O2 order view plus separately declared timed SIM confirmations. Keep original source fields/currency unchanged. The current refund balance/version belongs to the business database, not stale caller text or an agent-supplied confirmation.
3. Serialize a tenant/business-operation key with a transaction-scoped advisory lock. Check scope first; compare any prior operation's exact payload before returning its original receipt. New run IDs do not change the operation key or consume a new refund.
4. Lock the tenant/run budget and order record in a fixed order. Refuse changed limit configuration, stale versions, unknown/ineligible facts, mismatched full amounts and amounts above either per-order policy cap or explicitly configured per-run SIM limit. Update order state/version, budget and append-only receipt in one transaction. A before-commit fault rolls everything back; an after-commit fault must be recoverable by the same business key.
5. Build an acyclic LangGraph intent/context/policy/action/result flow, using an official Postgres checkpointer and bounded step count. Only narrative/request facts enter intent planning; the planner cannot choose tenant/order, permissions or commit success. Revalidate every proposal in the business tool. On restart, resume saved graph state; business idempotency protects a repeated action node.
6. Derive thread identity from trusted tenant/business event, bind the original input fingerprint and serialize same-thread execution. Responses claim completion only after rereading the actual matching ledger/state; a proposal or forged result reference is insufficient. Status/review paths never claim a refund. O6's operator approval/resume workflow and O7 authentication/UI remain later work.
7. Test invented unit boundaries and real isolated Postgres transactions/concurrency/restart behavior. Reuse pinned source evidence; perform one final complete integrated check and required hosted CI after the feature is ready. No live model calls are authorized; model-path tests use invented gateway responses.

### What went wrong

Docker's Linux engine was stopped at resumption; its CLI reported a missing engine pipe. Start the existing Docker Desktop installation without a visible helper window, then verify the engine before attempting DB evidence. No database result is claimed until it runs. Optional workflow packages, bootstrap role privileges and checkpoint serialization are explicit trust boundaries; do not substitute a memory saver and call it durable.


### Transaction, source and installation evidence

Executable source `efd822fffc1b17c0272a4c2bd966f789109081ff` passed fourteen focused graph/model-boundary witnesses and the full required database suite: 27 tests in 259.92 seconds (16 existing + 11 Olist). The owned child process exits with code23 after business commit; independent SQL observes one 5,000-minor effect, and a new persistent saver recovers the original-run receipt without a second write. Concurrent run spending and same-order competing-operation checks passed.

Reuse O2 database pin `3f97471af1ad88653e04fffb9619d190358ba6673a83e8026964aa7ae801d73f` and private O3 evaluator pin `0e542a7a4d13964c3fa3d4519f8c78e6452cb3e55f827997bed23eb67069011d`. Select the three already-eligible hybrid groups, enroll original views plus declared fictional proofs in a fresh owned F4 trial, run refund/status/reship and completed new-run retries, then independently SELECT ledger count/sum, order balance/version and budget spending. Actual results: three refunds, three statuses, three reviews, three completion resumes; exactly three ledger entries and19,116minor SIM in ledger/orders/budgets. Source currency remains null; zero model calls/real payments. Drop only that owned trial afterward. Public aggregate report contains pins/counts only.

The first private report writer attempted to JSON-encode Postgres SUM as Decimal and failed after all business assertions and trial cleanup. Convert aggregate integer sums explicitly to int and repeat the complete drill in a fresh owned trial; the second report passed. This was a report serialization error, not evidence of a failed transaction. The first installed-byte probe also included the wheel directory entry as if it were a file; filter directory entries before comparing. Fresh base and optional-workflow installed probes then matched all twelve Python modules plus business.sql under network denial. Base has no LangGraph/Google/Langfuse/OpenTelemetry/pytest; optional workflow imports and checkpoint serializer round-trip passed. All six wheel/sdist pairs built, and the locked dependency audit reported no known vulnerabilities.

One final complete local check is running. Record its actual failures/results before handoff; do not infer a pass from focused tests. Final hosted checks and issue Review evidence follow after source and documentation are ready.


### Final integrated check exposed two existing boundaries

The full local run completed:670passed,2failed in511.07seconds; lock/lint/format/64types/twoimportcontracts passed. The replay CLI correctly refused its v2 capture because the newly added workflow dependencies changed uv.lock. Do not relax ReplayBinding: preserve v1/v2 bytes, parameterize historical rejection for both, and intentionally publish a new invented-only v3 fixture with its own reviewed content pin from a committed clean capture revision. Normal replay/CI must never regenerate it.

The other failure was the existing owned-process cleanup witness: an eight-second deadline expired before its worker body wrote the started marker on a cold Windows spawn. Usage stayed unknown and the process was reaped; the test failed its required entered-body assertion. Give this particular test thirty seconds of startup/execution budget, keep the marker/unknown-usage/no-surviving-child assertions and a33second wall bound, and make the invented hanging body sleep60seconds so it cannot complete normally inside the deadline. Production transport deadlines are unchanged. Recheck affected controls/replay and the complete suite after the explicit fixture update.


The new v3 invented capture was published exclusively from clean source `8d10f3a6161c008d4e27c4c9ba11496c443f2fc3`, actual lock `8bbcb51e6362da19b3c100440d4b5f9e2644f7829b47561c874526d0a772f3f3`, content pin `434e62b9e97f6164b41412d94317c257914d6e6d8c6ec5adeedc286db78ea345`. Compare all six request/response objects against v2 before publishing; they are equal. Update only the ordinary command resource/pin after exclusive publication. Preserve old fixtures and add both pinned historical rejection witnesses. The capture is synthetic FakeGateway execution, not live provider evidence.


Affected controls/replay acceptance now passes128tests80.50seconds. Ruff/format and the documentation audit pass354immutable source ranges/261local links;30intended publication files contain no configured secret values. Allsixwheel/sdist pairs rebuilt with the v3 fixture included. Freeze the executable changes, run clean exact-source replay and repeat the complete local suite because the first integrated run had real failures. Required database27test evidence is reused locally because no business/workflow/DB source changed; final hosted Postgres repeats it at the published head. Record final full/hosted outcomes on#29/#30 without a documentation-only CI rerun.


### Reconcile C2 after O4 + O5 merge

2026-10-20: user merged#85 as `e11290a92f22588aa7c1c6d799a7b649097dc2fa`. Its tree is identical to reviewed41a2b19; clean-main replay passed. Reconcile still-open C2#84 with this main, preserving complete Entries27/28, both source chapters, accepted policy and the optional workflow lock/explicit v3 fixture. Six conflicts are shared documentation only. CFPB source/test bytes retain reviewed618b6c6; Olist/backend/workflow/config/lock/test bytes retain merged e11290a. Run focused C2 checks and final exact-head hosted matrix over the combined population; do not reingest unchanged data or repeat the unchanged complete local O4/O5 acceptance. Main/post-merge verification is pending until the actual run completes. Both O4/O5 remain open until then; C2 remains in Review.


### O4 + O5 verified main acceptance

User merged#85 as `e11290a92f22588aa7c1c6d799a7b649097dc2fa`; Git tree is identical to reviewed41a2b19. Main run39348205740 passed nine applicable jobs; PR-only metadata intentionally skipped. All actual job logs inspected:673tests perfourqualitycells,27Postgres,6call/2timeout/zero-provider replay and6wheel/sdist pairs each. Clean local main replay passed. Reuse exact-tree local673tests438.95s/64types/27DB/installed/source-drill evidence; avoid redundant source ingestion/full local rebuilds. Close#29/#30completed only now and update both active planning copies. Native board remains unverified.


C2 reconciliation focused acceptance passed21tests2.94seconds; the combined source audit passed363immutable ranges/271local links and18publication files, configuredsecretvaluesabsent. Clean strict replay consumed6calls/reproduced2timeouts withzero providercalls. CFPB source/tests byte-identical to reviewed618b6c6, Olist/backend/config/lock bytes identical to merged e11290a. No source acquisition/label generation/baseline recomputation was repeated. Final combined full population and Postgres acceptance run in hosted CI at the published C2 head; record actual counts on#35.
## Entry 29 — Exact-action approval behind a scoped local console

**Files touched:** Olist review/auth/API/console modules, private schema, optional web dependencies and acceptance tests. Started2026-10-20 on `codex/o6-o7-review-console` from verified main `e11290a`. Entry27 remains preserved in pending C2#84. The user explicitly authorized combining O6#31 and O7#32, retaining the existing100.00SIM cap/eligibility and pre-provisioned local operator/reviewer accounts with server-side sessions.

### Context and question

O5 can return a saved review, but no reviewer can inspect/decide/resume it through an authenticated application. How do we bind consent to the exact tenant/order/amount/version and reviewer, then survive a crash after refund commit without losing the approval audit or duplicating money?

### Options considered and why

A flag in the checkpoint is insufficient: it does not identify a reviewer or exact action and can lag the business transaction. A separate approval update after refund commit leaves an avoidable audit gap. Choose a vertical-owned application schema for cases, append-only decision events, accounts and opaque session digests. Keep immutable O4 business-v1 DDL unchanged. Add a trusted commit recorder inside the existing business transaction so receipt/case/audit commit together. Reuse O5 graph checkpoints for ordinary request recovery; approvals invoke the same fresh policy/version/budget enforcement.

Use opaque server-side sessions rather than adding a hosted identity-provider dependency, per user choice. Pin FastAPI/Uvicorn from current official package metadata, keep the web extra optional, and serve local static HTML/CSS/JS without a separate frontend build/CDN. A compact support workbench should foreground evidence, exact SIM amount and decision state; movement is limited to clear feedback/focus states.

### How to build it

1. Bootstrap a new private application schema through admin provisioning, then grant the runtime only needed case/session/account access and append-only audit insertion. Account provisioning is a trusted CLI operation; HTTP callers cannot grant their own tenant/order/role.
2. Hash passwords with salted PBKDF2-SHA256 at600,000iterations; enforce bounds, compare constant-time, return generic login errors and throttle failed attempts. Store only digests of random session and CSRF tokens, enforce expiry/logout, reread account roles/scopes on every request, and require same-origin JSON+CSRF for mutations. Bind the supported local server to loopback; remote deployment/TLS is later operational work.
3. Persist an idempotent case before running O5. Tenant/actor/scope come from the authenticated account. Keep request, context and original/provisional evidence private. Terminal review snapshots store a pure-policy candidate only when already eligible, plus the exact command, source/confirmation/version digest and action digest.
4. Require reviewer role, matching order scope, exact case version/action digest and a distinct submitting actor before accepting a decision. Missing/conflicting/over-cap facts cannot be approved; rejection records no business effect. Any changed evidence/version invalidates approval and requires reevaluation.
5. Persist approval before execution. The business transaction rechecks fresh policy/version/run limit, then an internal commit recorder checks the exact approved action/reviewer and appends receipt/audit/case completion atomically. A failed recorder rolls back all effects. Retry returns verified original receipt; a process death after commit cannot leave a second financial effect.
6. Expose authenticated submit/list/detail/decision/resume/session/health routes. Render loading, empty, pending, error, rejection, stale and verified-commit states accurately. Do not place passwords/session tokens in browser storage or raw request/source content in telemetry/logs.
7. Verify invented scope/CSRF/role/expiry/mutation cases, real Postgres decision atomicity/races/restart and a real browser operatorâ†’reviewerâ†’receipt flow. Reuse pinned source stores for a private aggregate drill. Keep offline model acceptance and SIM-only boundary; O8 still owns complete fresh domain release evidence.

### What went wrong

No implementation result is claimed yet. The design review caught the approval/ledger split-transaction gap before coding. Record actual failures and results as implementation proceeds.


### First console database run

Six of seven new real Postgres tests passed in36.31seconds, including exact-action consent, atomic rollback/lost-response recovery, changed-record reapproval, cap/missing-fact refusal, concurrent reviewers/resume, session expiry/revocation/throttling and runtime audit/account privilege refusal. The one failure was the health route: it queried the private schema-pin table, whose SELECT privilege intentionally belongs only to admin. Query an existing runtime-readable case table instead of granting extra schema metadata access. Re-run after this correction; no final acceptance is claimed yet.


The corrected console database suite passed7tests77.35seconds; unit+existing workflow checks passed21tests9.45seconds, with69strict typed sources. The browser drill then caught a UI accessibility defect: the busy helper restored button.textContent after an operation, flattening the sign-in arrowâ€™s aria-hidden span and changing its accessible name. Preserve/reattach the original child nodes after loading feedback instead. The first drill created a review case but no decision/refund; retain that interrupted case in private diagnostic evidence. Skip an anonymous session lookup when no session-indicator cookie exists, and return an empty favicon response to avoid expected startup console errors. Keep generated browser snapshots outside publication; rotate the invented test credentials after the drill.


### Durable consent and browser proof

All9new required console DB checks pass46.55seconds, including an owned child that exits29 after the approval/refund/audit transaction commits; a new store returns the original verified receipt and exactly one committed audit event. A provisioned different-tenant HTTP account cannot inspect/decide/resume the case. Operator HTTP cannot decide; reviewer HTTP cannot submit a new support action. Final queue listings also reverify committed receipts rather than relying on a saved status alone.

The real Edge browser drill used invented local accounts/orders only. Operator submitted a manual-review refund with an HTML injection canary; reviewer inspected evidence and recorded consent. Independent SQL observed one approved case, zero ledger effects. Restart the owned loopback service and verify the port owner belongs to the new launcher PID before claiming process restart. The new service accepted the persisted session/approval and executed the exact50.00SIM action. Browser reload retained the verified receipt; independent SQL found one5,000minor ledger entry and one committed audit event. Desktop1440px and mobile390px screenshots were inspected; no mobile horizontal overflow or page errors, and the canary remained inert text. One abandoned review from the first failed UI probe remains private diagnostic state; it has no refund. Tool snapshots are ignored, and invented credentials are rotated before handoff.


### Source approval and lock maintenance

Pinned private O3 groups produced three exact approvals with zero ledger effects before resume. A new store then executed all three, and repeated new-store resumes returned the same receipts. Independent SQL:threeledger entries/threecommittedaudit events and19,116minor SIM equal to order balances and run spending. Owned source trial removed. Public aggregate contains pins/counts only; reviewer actions are invented automated drill decisions, not human-adjudicated labels.

The optional web extra changes the lock. From clean c656ef5, capture/publish invented-v4 explicitly, compare all six request/response objects to v3 (equal), update only the ordinary resource/pin, and add pinned historical rejection for v3 alongside v1/v2. Actual lock `c52f7636fe16a7898642cb4324538741611099dcc5b6e814913643aee7c8c7a3`, v4 content pin `d92e2271b50913a4c276b9028d2441dd90a147223310225ee7438c862fbc19dd`. Old fixtures remain unchanged; no weakened matching or automatic fixture generation. All six packages built and locked audit found no known vulnerabilities. Rebuild the harness for v4 and Olist after readable static-asset formatting; complete local/required DB acceptance remains in progress.


### Complete local acceptance and package boundary

The final complete offline check passed 681 tests in 368.12 seconds, with 69 strict typed source files plus import, lint, format and lock checks. The required real Postgres suite passed 36 tests in 470.72 seconds. Interrupted earlier command sessions produced incomplete logs and were not counted as passing; the complete check ran as an owned background process.

All six packages built as wheels and source distributions; the harness was rebuilt for explicit invented-v4 replay, and Olist was rebuilt after readable asset formatting. Locked audit found no known vulnerabilities. Fresh installed base/web environments matched all 17 Olist Python modules, two SQL files and three web assets byte for byte under denied network operations. Base excludes web/workflow/provider SDKs. The web probe imports the actual API, constructs the loopback app, verifies password and checkpoint serialization, and reads packaged assets. An initial overly broad probe expected OpenTelemetry to be absent from the web extra; inspection showed FastAPI0.150.0 explicitly depends on opentelemetry-api, so the probe now checks that absence only for base. No instrumentation/export or provider call is claimed.

The source walkthrough audit verified 380 immutable source ranges and 288 local links. All 32 publication files contain no null bytes, configured secret values or the private O3 source identifiers checked. Strict replay at clean ec56534 consumed six recordings, reproduced two typed timeouts and made zero provider calls, preserving all historical fixture bytes. Documentation-only acceptance updates reuse unchanged executable evidence. Final exact-head replay and hosted job logs are retained on #31/#32; user merge remains pending.


### C2 reconciliation after O6 + O7 verified merge

2026-10-20: user merged#86 as `67e0349baa848ba329b027dd6948f0e64046f94b`, identical in tree to reviewed661badc. Actual main39447892854 logs passed nine applicable jobs:681tests perqualitycell,36Postgres,6call/2timeout/zero-provider replay and6wheel/sdist pairs each. Retain exact-tree local681tests368.12s/69types/36DB470.72s and installed/browser/source-drill evidence. Merge this main into still-open C2#84, resolving five shared-documentation conflicts while preserving complete Entries27/28/29 and each vertical’s executable bytes. Run only focused C2 checks, immutable-source/link audit and strict replay locally, then one final hosted matrix; do not reacquire source or regenerate sealed provisional reviews. C2 remains Review, not human-adjudicated; native board remains unverified.

Focused C2 acceptance passed21tests1.08seconds. Source identity checks matched82merged-main executable/test/configuration files and10reviewedCFPBsource/test files (Git-normalized LF). The documentation audit passed389immutable source ranges/287local links across18publicationfiles with configuredsecretvaluesabsent. No executable C2 or Olist change was needed. Final exact-head replay and hosted matrix evidence will be recorded on#35 without another docs-only push.

## Entry 30 — Parallel release evidence and original contract preparation

Date: 2026-10-20 (Africa/Lagos). Status: implementation in progress; no final batch or first-release acceptance is claimed.

**Files touched:** Olist release/scorer tooling, Revenue source preparation, their tests and dedicated documentation; shared planning and study navigation after integration.

### Context and decisions

The user merged #86 and asked for much higher throughput. Verify the new main67e0349 tree against reviewed661badc before doing more work: identical trees retain the prior681-test/36-Postgres/package/browser/source-drill evidence. Inspect main run39447892854 and its actual logs: nine applicable jobs pass, PR metadata intentionally skipped,681tests in every quality cell and36Postgres checks. Run exact-main six-call/two-timeout/zero-provider replay. Close O6/O7 only after that evidence, not merely because the PR merged.

The user explicitly chose three parallel agents and larger review batches: O8 offline release preparation, R1 original-contract corpus, and reconciliation of existing #84. The integrator owns shared files, root configuration, journal, metadata and final integrated acceptance. O8 uses the existing c1 checkout; R1 gets its own attached worktree; C2 keeps its own existing checkout/PR. Workers run focused checks and return explicit commits; integrate the new O8/R1 changes before one complete local/package/database/hosted pass. Reconcile #84 separately without silently merging it. Do not schedule an upstream-dependent feature against an unmerged branch as if the prerequisite were complete.

The user retained offline-only acceptance. O8 can build deterministic domain state scoring, complete private reports and repeated fault mechanisms, but fresh held-out provider results, reviewed baseline/threshold approval and final first-release acceptance remain pending. Repeating a fixed offline planner three times does not establish fresh model reliability. No live provider budget, real payment or deployment is authorized.

Measured main CI durations explain what to optimize: slowest quality job213seconds, of which16seconds is locked setup and174seconds shared checks. Ubuntu setup is2seconds. Enabling a new dependency cache would address a small part of this run and add a separate configuration change; retain the pinned workflow and reduce serialized work/redundant full passes instead. These are observed job durations, not a promised speed multiplier for parallel agents.

### How to build the Olist evidence boundary

Collect all order/refund/run-budget rows in an isolated trial within one repeatable-read transaction, rather than trusting the runtime receipt verifier or filtering away unrelated effects. Compare before/after snapshots against an independently supplied expectation: unchanged existing rows, and only the exact permitted ledger/order/budget delta. Review/status should produce no refund. Use existing ScoreResult/Ratio contracts and preserve every scheduled case/trial, including missing/error observations and source/split categories. Keep the H10 fresh release gate unchanged. A private offline report must always disclose the missing fresh/independent-review release evidence; it must not create its own approval.

### How to prepare the original contract boundary

Research official CUAD source/license metadata, pin the actual source archive and preserve complete original contexts/annotations outside Git. Separate an agent-readable context/question store from evaluator-only source identifiers, published spans, group/split membership and expected labels. Published contract annotations are independent source evidence, not an invented invoice/price/uplift truth set. Report unsupported billing fields as gaps. Group detected issuer/template relatives before assigning splits, verify no detected group crosses a boundary, and document inferred-family limitations rather than certifying unobserved legal relationships. Publish only aggregate provenance/counts/pins.

### Verification still to complete

Workers are implementing focused checks; integration, source drill, final full acceptance and hosted evidence follow. Record actual failures/results as they occur.


### Parallel review catches a wrong-operation receipt

The independent C2 worker reviewed O8 during its hosted-CI wait and reproduced a false pass with invented records: preserve an unrelated older ledger row in the before snapshot, make the exact newly permitted change, but return the old receipt. Searching the entire expected ledger for any matching returned receipt incorrectly called this correct. Bind the returned receipt to the newly expected task tenant/operation/order/run/actor specifically, and add the negative prior-receipt witness. The new state delta alone cannot authenticate a response about a different business operation. This was found before integrated acceptance; record the correction and actual test result after implementation.

The first combined O8 test invocation also caught duplicate pytest module names for offline/integration files; rename the integration module `test_olist_release_state.py`. No application transaction failure was inferred from a collection-name collision. Canonical Contract pins and raw file byte hashes are distinct encodings: preserve both explicitly in private reports and command documentation.


### Olist worker completes focused evidence

O8 source/tests commit e849296 fixes the reproduced wrong-operation receipt acceptance and compares the executing package inventory with the reviewed source root, preventing an incomplete source directory from shrinking the required manifest. Final fourteen offline checks passed in3.37seconds; Ruff/format and strict typing of both new modules passed. Earlier combined focused execution passed seventeen checks in167.66seconds (twelve offline plus five real Postgres cases). Five DB cases cover repeated normal/before-commit/after-commit/process-exit behavior plus no-write review/unrelated effects; integrated acceptance will exercise latest source bytes.

The report deliberately supports O5 automatic refund/review templates and routing/state correctness. It does not grade review-rationale semantics or console-consent evidence; existing O6/O7 tests remain the consent witness. Provider cost/latency remain null/unmeasured, with fresh evidence, reviewed baseline/thresholds and human adjudication explicitly pending. Source code and operation/study chapters are committed; the parent must still execute the private36-task drill and final integrated acceptance.


### First private source capture exposes connection row shape

Run the private36-task capture from clean2f453e3, after source pin verification and owned service startup, using a new external output directory. It failed at the first before-state read, before workflow/refund dispatch: checkpoint setup had set the reused admin connection's row factory to dictionaries. The collector unpacked rows as tuples, so Pydantic received the literal keys `version` and `refunded_minor` instead of integer values. Existing focused DB calls opened fresh default tuple-row connections and did not exercise this composition.

The correct product fix is to own an explicit tuple-row cursor inside collection, preserve the caller's row factory and test a dictionary-configured connection. Do not silently add a caller precondition to conceal a valid composition failure. The helper's finally block removed the first owned database/role; its private directory contains an incomplete plan only and is not passing evidence. Keep it as diagnostic state and retry with a new exclusive directory after the correction. No refund dispatch or provider call occurred in this failed attempt.


The row-shape correction54953b2 passed fourteen offline plus two tuple/dictionary-connection database regressions (sixteen checks72.19seconds), with strict typing/Ruff/format. The collector owns its cursor shape and preserves caller settings. During R1 final review, an unexpected SQLite view/trigger/index could evade a table-column-only check after derived store/manifest repinning. Added exact schema-object inventory checks and three invented negative controls before integrated acceptance. Source ingestion remains reusable; the verifier is rerun against unchanged private stores.


R1 full official source preparation verified510contracts,20,910questions and13,823published spans with no source-offset mismatch. Versioned inference produced457families, development417contracts/17,097questions and holdout93contracts/3,813questions. Family detection combines source issuer, exact normalized contexts and65percentJaccard over normalized five-word shingles (minimum100); it cannot certify all legal relationships. One undelimited issuer remains explicitly unknown. Original text/answers stay private; numeric account-linked billing truth remains absent.

Final R1 schema-object controls passed18invented tests6.15seconds after a reproduced repinned-view gap. The integrated merge had one README-only conflict, resolved by retaining the implemented source-preparation description and limits. An attempted capture before merge completion correctly rejected a dirty checkout before creating output; retry starts at clean7dfd144. The already running complete offline check sees identical integrated executable bytes; documentation conflict resolution does not invalidate its test inputs.


### Complete pinned cohort capture

The corrected clean integrated7dfd144 capture completed all36scheduled trials (twelve O3 hybrid cases times three repetitions):36correct, zero incorrect/unsafe/unresolved/missing. Every saved workflow result was retried through a new store/checkpointer and matched;36duplicate deliveries created no additional effects. All36owned trial databases/roles were removed. Public aggregate excludes case/order identities and private texts/labels. Original O3 raw pin0e542a7a remains unchanged; canonicalcasepinf7fb1e44 differs intentionally. Report canonicalpin7a940c95 and planpinbb9306a8 identify the private run. Provider calls and real payments are zero; release_allowed remainsfalse with all fresh/baseline/threshold/human-review blockers preserved.


The integrated six-package build produced all wheel/source pairs and the locked audit found no known vulnerabilities. Installed Olist/Revenue wheels matched24and5package files respectively with network operations denied; imports/API construction/input projection passed without provider calls. Full R1 verifier rerun after schema hardening returnedverifiedtrue for unchanged510contracts/20,910questions/13,823spans/457families. Post-capture executing Olist/harness source inventory still matches the36-task plan. Documentation audit:409immutable source ranges,304local links,25publication files and no configured secret values;21,929CUAD source title/question-ID/context needles absent. Final full-suite and hosted exact-head results are maintained on #33/#39 after actual completion; no planned result is a pass.


## Entry 31 â€” Three Revenue tasks behind explicit simulation rules

Date: 2026-10-20 (Africa/Lagos). Implementation in progress; no new batch acceptance is claimed.

**Context:** user merged #87 and explicitly requested at least three issues per delivery. Verify main058d1c7 against reviewede536c96: identical tree. Inspect main39457223872 actual logs: nine applicable jobs passed,713offline tests per quality cell,43required Postgres tests, replay6recordings/2typedtimeouts/zero-provider and allsixwheel/sdistpairs. Clean exact-main replay passed; preserve unchanged local/source/package evidence instead of re-running it. R1#39 completes original published context/reference preparation with numeric billing/family limitations retained. O8#33 remains open pending fresh provider/baseline/threshold/human-review evidence under the user's offline-only constraint. C2#84 is still an independent unmerged review.

### Decide the three-task boundary before implementing

Deliver R2#40 billing worlds, R3#41 common access mechanism and R4#42 cited extraction/reconciliation in one PR. User approved constructed monthly whole-seat charges in SIM integer hundredths, no proration/tax, explicit dated ramps/credits/amendments, annual uplift only expressly stated, and review for missing/conflicting terms. Original CUAD extraction never becomes invented invoice truth. No real money, provider calls or R5billingwrites are authorized.

Give each worker owned modules/tests/docs in separate worktrees. The R2worker defines public BillingInput and evaluator-only literal schedules, with deterministic family splits and external private stores. The R4worker implements a read-only engine against those public contracts and keeps gold-terms versus extracted-terms errors separate. Fixture labels must not import or call that engine. The R3worker first examines two real call sites, then moves only exact tenant/resource-kind/resource-ID/capability membership into harness.access. Root owns shared configuration, journal/planning/indices and final integrated checks. Merge local worker branches to retain immutable source anchors; run one final full suite/build/audit/hosted matrix after integration.

### Keep the common API smaller than the domain

Olist CallerGrant already performs exact tenant/order/capability checks; its closed read/refund capability and JSONwire shape remain unchanged. Revenue's second consumer is a private world reader guarded by BillingGrant read/reconcile capability and explicit tenant/world scope before file access, then parsed case/tenant identity before return. ResourceScope carries an explicit resource_kind so equal IDs in two domains do not match. Shared code contains no refund/invoice rule, account role, wildcard, authentication, transaction, approval or receipt policy. A generic registry/write primitive has no second demonstrated use; do not extract it speculatively. MCP exposure remains later work.

### Define safe arithmetic limits

Use first-of-month effective events and half-open monthly periods. Uplift anchor explicitly names the first uplift date, with annual exact-integer compounding only when declared. An explicit price amendment resets base price; subsequent applicable anniversaries may uplift it. A simultaneous price reset/uplift is ambiguous and routes to review. Mid-month events need review because proration is excluded. Fractional-minor results also need review because no rounding policy was approved. No legal span supplies missing billing authority; unsupported extraction remains unresolved rather than guessed. Literal benign credits/ramps/amendments are negative controls as well as leakage cases. Automated arithmetic checks are not new human adjudication.

### Results to record as work proceeds

Workers are implementing focused checks; original-source, constructed billing and tool-migration evidence remain distinct. Record real failures and complete integrated results before review.


### Verify two consumers before shared extraction acceptance

R3source701353 preserves the Olist CallerGrant canonical wire fingerprint, closed read/refund capabilities, existing denial text and accepted resource counts. Generic ResourceScope checks exact tenant/kind/id/capability; asterisks/prefixes carry no wildcard meaning. Revenue BillingGrant and actual R2read_world use the same scope mechanism. Focused integrated consumer verification passed39tests26.68seconds (five access, thirteen billing-world, fourteen existing workflow and seven console), with affected lint/format and six strict typed modules passing. The reader denies absent capability/resource before opening storage, then checks schema and strict tenant/case identity before returning public fields.

R2sourcec6407aa defines29literal cases across nine families, before candidate comparison: nine development/nine regression/eleven holdout, eight correct/six underbilled/six overbilled/nine review. Fixture authorship never imports the reconciler. Independent Fraction arithmetic checks each literal expression and signed difference; this is an automated arithmetic witness, not new human billing adjudication. Private preparation and verification completed with manifest97d4193e8339af5164dedc284b6b45d53fce4cb936e809ba76769adc4d104730. Public aggregate receives explicit LF attributes to preserve byte pins on Windows.

Parallel review reproduced a valid-date engine failure at9999-12-01: constructing the next month attempted year10000. R4 must return review for the unsupported terminal calendar month rather than raise. The cited extractor must also have a concrete shared ModelGateway adapter tested with scripted responses; an all-abstain baseline alone would not implement extraction. Original span integrity remains distinct from semantic legal or monetary correctness. These fixes are being checked before final integration.


### Close the response identity boundary before acceptance

On 2026-10-21, independent R2 review reproduced another false acceptance: a gateway returned a well-formed literal span under a provider/model route different from the requested route, and the extractor accepted it. Validate the entire ModelResponse again at the adapter boundary, then require exact provider/model and any explicitly requested model revision before parsing its content. A mismatch must become a bounded uncertain outcome without retaining private response text. Canonical validation also rejects unchecked model objects created through bypass APIs. Record final regressions after the worker commits; this finding precedes integrated acceptance.


### Execute the combined mechanism before broad acceptance

R4 source45ebabb revalidates ModelResponse and rejects wrong provider/model/requested revision before parsing. Its final41focused tests passed0.84seconds with strict typing and lint/format. Integrated private capture at clean24e401d compared all29literal cases through provided terms and separate invented grammar:29matches on each path, two actual scoped CLI outputs equal library results and private world-store bytes unchanged. Twelve original CUAD development inputs dispatched only to a scripted abstention gateway; all returned unsupported. No original extraction accuracy, provider call or billing mutation is claimed.

The first capture attempt stopped at scripted gateway construction because its helper omitted required unknown token/cost fields from Usage. This was a helper error after billing checks, not a provider or engine failure; the partial directory is diagnostic only. Explicit null usage observations corrected the helper, and a new exclusive v2 directory completed. The first required DB attempt failed all43setups because Docker Desktop was stopped. Start the installed service and repeat that check; never count setup errors as passing application evidence. The six-package wheel/sdist build completed; audit and full checks are still in progress.


### Repair the newly disclosed dependency before final acceptance

The locked audit reported certifi2026.7.22 / PYSEC-2026-4320, fixed in2026.10.19. Upgrade only certifi; preserve all other dependency versions. Stop the owned incomplete broad check rather than attributing it to the changed environment. A new lock intentionally invalidates strict replay's old environment binding, so publish an explicit invented v5 capture for review, preserve historical fixtures and compare all six request/response values. Re-run the combined mechanism under the final lock and then complete broad acceptance. This is not a fresh provider recording.


The fixed lock6e5895cc passed audit with no known vulnerabilities. Explicit v5 capture8e25d2e preserves all six v4 requests/responses and uses independently reviewed-content pinda8f943e; proposed review is not a claim of prior user approval. All four historical fixtures remain packaged, and current-lock rejection now covers v4 too. Seventy-three focused replay checks passed14.54seconds; clean strict replay consumed six calls with two typed timeouts and zero provider calls. The normal replay command never authors or silently rebinds a fixture.

A new clean combined capture at 08f5b41f4e83cd7e24f1d7698e8e9be9b10affd8 under the fixed lock repeated29/29 provided-term matches and29/29 invented-grammar matches, two scoped CLI outputs and twelve scripted original-source dispatches. All fifteen recorded source/lock hashes match the executing files. The original v2 output remains private historical evidence; the publication now points to the final-lock v3 capture. Final broad checks and the restarted database check are running. Static audit verified445 immutable ranges,319links and30publication files;42,837original-source title/question/case/context needles were absent. Package/audit/hosted outcomes will be recorded after actual completion.


### Resolve exact source-hash false positives without weakening scanning

Initial PR88 run39531375498 secret scan flagged two generic-api-key findings at historical09b2968, aggregate lines5and17. Actual redacted job log identifies billing_access.py and harness/access.py inventory values; both equal SHA256 of the current source bytes. They are public code provenance, not credentials. Add only the scanner's two exact commit/path/rule/line fingerprints to .gitleaksignore. Do not ignore the entire JSON path, source hash values elsewhere or the generic credential rule. Historical findings remain in Git; changing only the current map would not resolve the full-history scan. Rerun hosted checks after this precise configuration correction; local source/database checks remain valid because executable bytes and lock did not change.

The installed-wheel probe passed with socket/DNS operations denied: all50harness,24Olist and12Revenue source/resource files match built wheels. Imports came from the installed environment, both provided/invented-extracted arithmetic paths agreed, and local console construction succeeded. Six final wheel/source pairs built; the fixed-lock audit found no known vulnerabilities. Publication audit at44272aa passed445immutable ranges,319links,34files and all15source/lock hashes, with42,837private-source needles absent.


## Entry 32 â€” Approved Revenue effects and independent shipping sources

Date: 2026-10-21 (Africa/Lagos). The R5/R6/S1 implementation is starting; results below are recorded only after execution.

### Context

The user reviewed and merged #88 as `5f73fc983d9dacaa206bc84315686fa882c7ee3f`, identical to reviewed `dc76e5c`. Main run39532518481 passed nine applicable jobs; actual logs verified773 tests in each matrix cell,43 Postgres tests, six replay calls/two timeouts/zero provider calls and twelve package artifacts per quality job. Clean exact-main replay passed. Issues40/41/42 were explicitly closed completed, retaining provisional-label and offline limits. C2#84 remains unmerged and is reconciled separately; its reviewed source is not a prerequisite for this batch.

The user selected R5#43 + R6#44 + S1#52, with three parallel agents and one integration branch `codex/r5-r6-s1-operations`. R7 remains blocked by the offline-only release constraint. The user approved simulated invoice corrections and account merges only with a separate reviewer; a hard100.00SIM cap applies to the absolute adjustment, not the resulting invoice total. Approval cannot override it. Only trimming outer whitespace in an internal CRM note is automatic. Compensation requires separate approval and cannot overwrite later legitimate changes.

### Before you read on

How would you bind a human approval to exactly one correction, prevent a retry from charging twice, and still recover after a process exits just after commit? Sketch the stable business-operation key, immutable payload fingerprint, record-version predicates and effect ledger before reading the implementation.

### Options considered and chosen

We considered one Revenue-only batch R5/R6/R7. R7 needs fresh provider release evidence and prerequisite O8, which the user has kept pending; including it would imply acceptance the offline work cannot establish. The user chose independent S1 source preparation alongside the two coupled Revenue implementation tasks. Each worker owns separate files/worktrees; root owns shared dependency/lock, planning, journal and final integration. This preserves parallel work while giving the R5 transaction API one owner.

Use Postgres as the sole authority for Revenue approval expiry, versions and effects. Inngest supplies thin wakeups, idempotent steps and sweeps, rather than holding a second competing approval state. The SDK is verified against current official documentation and its actual installed API before use. Existing shared exact scopes stay domain-neutral; invoice eligibility, account alias semantics and amount limits remain in Revenue.

### How to build the transaction boundary

1. Provision explicit tenant/account/invoice records in a private, restricted trial database. Store a trusted BillingInput snapshot with each invoice; verify its tenant/account association and initial issued amount. Recompute R4 reconciliation against that snapshot and the current stored invoice amount before proposing or applying a correction. The browser cannot substitute its own claimed should-be amount.
2. Build an immutable proposal containing operation kind, exact before/after values, expected record versions, stable tenant/business-operation identity and expiry. Hash its canonical representation. A reviewer session must be a different actor and bind that exact fingerprint; stale record/source facts or mismatched identity prevent application.
3. Lock the relevant rows and stable operation key inside one transaction. Recheck grant, approval, versions, computed amount and absolute adjustment limit; update business state and append a receipt/ledger event atomically. A retry with the same key and payload returns the original receipt; changed payload under the key fails. A post-commit transport failure must not create another effect.
4. Represent the bounded demo merge as a reviewed donor-account alias to a canonical target. Preserve original invoices/history; reject cross-tenant, self, cyclic or conflicting aliases. This models one explicit internal effect, not an external CRM ownership transfer.
5. Compensate by proposing and approving an inverse effect tied to the original receipt and exact post-effect versions. If legitimate later state intervenes, refuse the overwrite. A successful inverse appends a new ledger row and preserves the original event.
6. Derive HTTP permissions from pre-provisioned server-side operator/reviewer sessions. Show real computed findings and distinct found/proposed/approved/applied/rejected SIM amounts; reconcile the digest from durable records/ledger. Surface expired, rejected, stale and pending reviews in the interface. No incoming grant JSON acts as authentication.

### How to prepare S1 without inventing history

Acquire the official DataCo structured shipping source and its column description, recording version, permissions, bytes and independent source hashes outside Git. Separate customer identifiers and future delivery/outcome fields from agent-visible as-of observations. Preserve unknown historical timezones explicitly. Independently capture a timestamped official NWS alert response with source URL, retrieval time, coverage, effective/expiry and freshness evidence. Its contemporary US coverage does not establish historical weather affecting DataCo's worldwide shipments. Publish only aggregate provenance and hashes; private source text/records remain external. Test future/expired alerts, malformed timestamps, source changes and storage/schema isolation before running the real source verifier.

### Verification to complete

Workers will run focused transaction/SDK/API/source checks against their actual implementation; planned checks are not passes. Root will integrate source once, verify package/lock/replay boundaries, run a complete combined suite and required Postgres checks, and inspect hosted exact-head logs before offering the PR for user review. No provider call, real billing write, clinical claim, shipping causal claim or release promotion is authorized.


### Pin the event adapter before it gains state ownership

R6 official documentation/PyPI inspection selected inngest0.5.19. Its optional Revenue events extra adds jcs0.2.1 alongside already locked HTTP/Pydantic dependencies; web reuses fastapi0.150.0 and uvicorn0.54.0. Root adds the workspace-source mapping and development extra so a plain locked check exercises the optional adapters. All existing dependency versions stay fixed. The changed lock requires an explicit invented replayv6 capture for review; historical v1â€“v5 resources remain immutable. This dependency change is part of R6, not new provider evaluation.

S1 verified the official DataCo v5 structured source listing (95,910,149 bytes, CC BY4.0, versioned DOI) and captured one official NWS response separately. Its as-of policy is conservative: no historical online availability inferred from retrospective DataCo timestamps, historical timezones remain unknown, and NWS freshness is a caller-declared maximum age plus effective/expiry checks. HTTP cache age is recorded separately from meteorological validity. Actual prepared-source counts and byte pins follow verification, not the listing alone.


The locked event/web setup installed only the two new dependencies and rebuilt the Revenue editable package; audit found no known vulnerabilities. At clean `28cdf485ed7cac4e1d5460b555baafea1bf9cbc4`, explicitly capture invented v6 with lock `f1d00addeaefbbd946abea7b25b0e039473109bd6f146515e35ab9b20e7609e5` and content pin `4224a610495d5bc657240e5a4dc6c44c08318149fc0f4534b8716763da603883`. Compare all six requests/responses against v5 before changing the default. Preserve v1â€“v5 and add a negative current-lock test for v5. This proposes a new reviewed-content fixture while keeping replay itself strict; focused tests follow before final combined acceptance.


### Protect the reviewer from rounded numbers

R6 review found that valid signed-64-bit amounts can exceed JavaScript's safe integer range. A browser rendering such JSON numbers can show a different amount from the approved payload. Emit exact decimal strings for amounts/record displays and format money with BigInt; validate any version converted back to a typed integer before submission. Add a large-amount API/UI witness before claiming this boundary is fixed.

The first replay-v6 focused run passed73 cases but its credential-free CLI child exceeded the existing20-second subprocess timeout during measured host memory pressure (about580MB free physical memory). This is a failed local smoke check, not a passing result or demonstrated business-logic error. Preserve the log, finish other heavy work and retry the affected check without relaxing production or test deadlines. Two earlier focused invocations named nonexistent test files and collected no tests; corrected names are used for actual evidence.

Separately, pending C2#84 reconciled verified main5f73fc9 at f5195b3 with three shared-document conflicts resolved and no executable changes beyond the existing C2 additions. Focused21checks passed1.19seconds; clean replay passed; audit checked454 immutable ranges,297 local links and18 publication files. Hosted run39533702332 passed allten jobs with actual794tests per quality cell,43Postgres, six-call/two-timeout/zero-provider replay and twelve package artifacts per quality cell. Issue35 remains Review and user merge is pending; no labels were regenerated or promoted to human adjudication.


After the other heavy checks completed, the unchanged replay-v6 focused suite passed all74 tests in10.08seconds. The CLI startup retry used the same20-second bound. Ruff check and format passed for the two changed Python files. The earlier timeout remains diagnostic evidence of local contention; it was not suppressed or reclassified as a pass.


### Recover focused transaction evidence after interrupted agents

External authentication/network-permission interruption stopped worker turns, but the owned test process completed and its saved stdout/stderr remained available. Inspect its PID/command and final log before rerunning. R5 source2688d82 passed30focused checks in165.90seconds:11offline and19actualPostgres. Strict typing of two modules and Ruff/format of four Python files passed. Witnesses cover concurrentduplicates, process exit after commit, partial batch rollback/retry, separate/stale/unauthorized approvals, exact R4 source-fact binding, the10000minor absolute boundary, alias compensation, later-change refusal and immutable ledger SQL privileges. The first run's one failed negative test expected a domain-review exception but received the correct earlier permission denial; correct the expectation, then run the complete focused set. No provider or real billing effect occurred.


### Bind reads to resource kind and one committed snapshot

R5 peer review reproduced a wrong-kind grant edge on existing proposals: the preliminary identifier-membership check could return an account proposal when the same identifier was granted only as an invoice. Effect paths already validated stored kind. Resolve the stored record's actual kind before any proposal return/review, then add a negative database witness for the idempotent/read path. This protects the shared exact resource-kind contract rather than relying on normal account provisioning.

R6 also identified a consistency gap in digest construction: records, proposals and ledger were read on three independent connections. A concurrent commit could combine a pre-effect invoice with a post-effect ledger. Add a single scoped snapshot in a REPEATABLE READ READ ONLY transaction and reuse the same filtered read helpers; test a controlled commit between logical reads and require one coherent view. Existing public reader methods remain for focused callers. The UI consumes this atomic projection.

The private29-case original R2-to-R5 drill completed12eligible source-backed corrections with separate approval, stable duplicate receipts and approved inverse effects;17review/no-change cases were blocked without ledger effects. Full results stay external. Its cleanup helper incorrectly passed the derived database name to an API expecting logical trial identity; correct the helper and explicitly remove only owned logical trial r5-r6-source-drill-v1. Verified removal completes the run; no application effect was duplicated. The final read-scope/snapshot correction is still pending separate focused evidence, so this capture is an arithmetic/transaction witness at its recorded source revision, not final interface acceptance.


The wrong-kind and consistent-snapshot regressions passed two targeted actual-Postgres cases in98.53seconds at1bb4579, separately from the prior30focused result. One deterministic witness commits an approved correction between logical read phases: the open snapshot retains old records/old ledger, and a new snapshot sees the new version and receipt. R6 now consumes this shared-connection projection. The integrated full check passed lock/lint/format/strict94source files/import contracts and is running its tests. Six final wheel/source pairs built. Original S1 source preparation completed180,519lines/65,752orders; full original-source verification is running, so its acceptance remains pending.


### Finish independent source verification and browser preparation

S1 sourcef9fb0ed prepared the complete original DataCo cohort in305.66seconds, then independently re-read the original CSV and both stores in205.42seconds:180,519lines,65,752orders,53columns and306NWSalerts. At the actual capture clock,245alerts met the explicit30-minute freshness allowance; pre-observation shipment access and stale-weather access returned zero. All20focused tests passed7.94seconds, with strict typing of three modules and affected Ruff/format. The source pin and manifest are independently retained; only allowlisted aggregate provenance/counts/hashes enter Git. Historical DataCo timezone/availability remain unverified and no weather causal join is claimed. An automatic approval review rejected a broad private-manifest copy command; an explicit small aggregate patch was subsequently verified against private receipts, preserving the publication boundary.

The real-browser drill uses an invented invoice and two provisioned identities in a new owned trial. A combined background-server/browser command was rejected by automatic review; a separate foreground server succeeded. The Playwright default Chrome location was absent while Edge is installed, so select Edge explicitly. The initial unauthenticated session check correctly returns403. Browser inspection found genuine mojibake in several index.html glyphs; correct those asset bytes and verify the rendered interface before accepting it. Credentials remain only in the external private session file and are supplied through a nonprinting helper.


### Resume final acceptance on 2026-10-22

The session interruption left the first integrated broad runs incomplete: their logs do not contain final counts, so they are not passing evidence. Recover saved source and merge R6's committed8a05827 HTML correction rather than reconstructing assets. Restart the final source suite with external TEMP/TMP. Its initial database attempt reported68setup errors because Docker was stopped; restore the local daemon and confirm health before retrying. The final package build produced all six wheel/sdist pairs and the fixed optional-dependency audit found no known vulnerabilities. An immutable-source audit found exactly one obsolete root pyproject slice among485ranges; repin it to the committed event dependency configuration and actual line extent. Other source slices remained contiguous.


### Reproduce and close a session race in the actual browser

On2026-10-22, operator proposal success displayed before action() finished its automatic refresh. Signing out during that pending request let the old200response call render() after user became null: the login form hid, old scoped workbench reappeared and the UI showed a null-username exception. API sessions were revoked correctly; the bug was stale browser rendering. R6source60e4c367 introduces session epochs, captured-principal checks and refresh ordering, clears private DOM before awaiting logout and serializes cookie-changing auth requests. Late startup/refresh responses cannot overwrite a newer session. Six deterministic NodeVM scenarios execute the actual asset with delayed fetches and a controlled DOM; all pass, including failed-logout truthfulness and exact signed64-bit money formatting. Add that standalone built-in Node regression command to every hosted quality cell; it requires no npm packages or network. Python suite/SQL logic and lock remain unchanged.

The complete local Python check finished815tests in789.82seconds, with strict94sources, lint/format and static import contracts passing. Required68database tests are still in progress. Initial candidate6994e8f hosted run39698621795 passed allten jobs with actual815tests per quality and68Postgres; browser findings require a new exact-head CI run after the asset correction rather than reusing its final acceptance. Built/installed source bytes must also include the corrected asset.


## Entry 33 â€” Independent shipping worlds and durable budgeted intervention

Date: 2026-10-22 (Africa/Lagos). Branch `codex/s2-s3-s4-supply-chain`, based on user-merged #89 main `77b98df`. Implementation underway; verification results follow their execution.

### Context

The user selected S2 #53, S3 #54 and S4 #55 in one review batch. They approved a constructed SIM policy: maximum 100.00 per action and 500.00 per incident/run, separate reviewer above 25.00, 30-minute approval and confirmation windows, at most two replans, and blocked missing/stale facts. They delegated the simulator source choice with eventual production in mind. Offline-only remains active. Existing untracked documents and the old root checkout are preserved; implementation uses `.worktrees/supply-chain` inside the writable workspace.

### Before you read on

How can a planner choose interventions while the evaluator knows their realized outcomes? Where must an approval, a budget reservation and a confirmation live so a retry after commit cannot spend twice? Sketch the public/evaluator boundary and the single transaction before reading on.

### Options considered and chosen

Using contemporary NWS alerts as causes for historical DataCo outcomes would fabricate a causal training set. Use independently invented worlds for intervention testing; a separately labeled source-observation adapter may provide input facts, never realized intervention gold. Development and holdout have different seed namespaces, portfolio templates and outcome equations; the same named risk slices let us compare distribution changes. An exact public-estimate knapsack is a baseline, not an oracle for hidden realized cost.

For execution, use Postgres as the authority for incident budgets, shipment versions, immutable proposals, reviews, receipts and confirmation outcomes. LangGraph computes bounded assessment and proposes work; Inngest fans out opaque wakeups and waits, then rereads canonical state. Do not duplicate an approval or an effect in framework state. A permanent tenant/incident/shipment key makes new run IDs and replans return the existing effect. A confirmation timeout preserves the committed debit and marks the action unresolved.

### How to build it

1. Define strict versioned public Shipment/Option/Command contracts. Catalog prices and expected delay reductions come from server code, not caller JSON. Validate the scenario clock, source observation/expiry, complete facts and contradictory alerts before offering options. Keep hidden outcome arrays in evaluator-owned Scenario objects; pass policies only serialized public shipments.
2. Enumerate bounded wait/expedite/reroute choices. Optimize total estimated delay plus intervention cost using a multiple-choice knapsack, keeping one deterministic best path per spend level. Report all do-nothing/rules/solver outcomes with split/family/template/seed lineage, intervention/delay totals and undefined normalized differences at zero baseline cost.
3. Bootstrap an immutable Supply schema with a restricted runtime role. Lock incident budget, then shipment, then proposal in every mutating path. Bind exact command, trusted price, shipment version, budget version and deadline to the review fingerprint. Atomically update budget/version and append one permanent receipt. Check retries against the original command before returning the receipt.
4. Model confirmations separately from command acceptance. A trusted confirmer must match tenant, shipment and receipt fingerprint before the deadline. Late/out-of-order confirmation cannot rewrite a terminal result; process restarts reread persisted state. Bound planner retries at two replans, exclude committed shipment keys and retain every prior receipt.
5. Declare optional workflow dependencies at their existing locked versions. This changes the environment-lock identity even without upgrades; create a separately reviewed invented replay capture rather than silently rebinding the old fixture. Keep historical resources immutable.

### What went wrong / checks pending

The initial managed worktree could not resolve the merge object until `git fetch origin main`; after fetching it succeeded. Its default C-drive location is outside this chat's writable roots, so it was archived unused and replaced by the isolated D-drive checkout. The initial Docker probe found no daemon; database acceptance is not claimed. A first setup attempt targeted an external unwritable cache and failed; use an authorized cache location before recording setup success. No implementation check has yet passed.


### First checks and boundary repairs

The first simulator suite passed 29 tests, including exhaustive public-objective comparison and hidden-target perturbation. Full strict typing inspected 100 source files; its sole remaining error was passing a conditional kwargs dictionary to Inngest.Event. Use an explicit generated string ID for repeatable review/confirmation wakeups and a deterministic ID for initial requests. Six long SQL literals were split using adjacent Python strings without changing SQL bytes.

The first real Postgres run passed 13 tests and failed five (158.39 seconds). Spending serialization, duplicates, stale approvals, tenant/resource/incident scopes, expiry/rejection, confirmation terminality, rollback and SQL-role denial passed. Four failures shared one real boundary bug: LangGraph returned JSON-mode lists, then strict Python validation demanded tuples. Revalidate the serialized wire through model_validate_json, preserving strict internal tuple types. The process-crash witness failed before connecting because psycopg Connection.info.dsn intentionally omits passwords; pass the disposable trial password only in a child environment variable. Do not print it or call the failed crash witness a recovery pass. Rerun affected and complete new tests after these repairs.

The final simulator cohort uses four development families at seeds11/23 and six holdout families at seeds97/193. Expired alerts and correlated delays are unseen development families; holdout portfolios and outcome equations also differ. No target label is human gold, and no NWS/DataCo causal relationship is inferred. Replanning has a conservative incident-wide allowance of two stale proposal supersessions; large bursts may remain safely unresolved rather than relaxing approval freshness.


### Focused final-source acceptance

The repaired complete new SQL suite passed all18tests in83.22seconds, including real child exit73 immediately after commit and recovery through a new store, exact-one concurrent effects, near-cap competing debits, stale budget/reapproval, scoped denial, expiry/rejection, first-terminal confirmations and graph/SDK recovery. One upstream Inngest experimental-test event-loop deprecation warning remains. The extended simulator suite passed30tests1.06seconds; strict full-workspace typing passed100source files. The report publishes20invented scenarios at three explicit delay-cost sensitivities, with no real source data. Full workspace/database/package/replay checks and hosted acceptance still follow; this focused evidence alone is not a release pass.


### Pin source and preserve replay semantics

Source `ba962c6cdec3a7f7f694a2eaf92d705c324e7e3e` is committed. New lock `b0d264aeb155915511202ced1338d6840546ae6cfe8c1b18e1553f2683edf266` adds only optional workspace metadata for the existing pinned dependencies. An explicit invented v7 capture has content pin `175fdcc50359cb5471bf292e15034fc250bf5ac724d05582b3d69bf429ac548d`; all six request/response pairs equal v6, including two timeouts. Historical v1–v6 are preserved and the current-lock negative tests include v6. This is synthetic maintenance proposed for user review, not fresh provider evidence. Supply code-study AST anchors match the committed bytes.

The 20-scenario sensitivity reports are deliberately unfavorable where measured: solver versus do-nothing totals are545000/422000minor at50%,888000/844000at100%,1574000/1688000at200%. Retain these results; an estimator can lose under changed efficacy and delay prices. No tuning or actual savings claim follows from this mechanism exercise.


### Published source acceptance and local temporary-directory diagnosis

Draft PR#90 at0406e82305619af7d33414ccd5169759c03c8dc6 passed all10jobs in hosted run39864242079. Actual downloaded logs verify846offline tests in each Ubuntu/Windows Python3.12/3.13 quality cell,86Postgres tests,100typed files, six recorded replay calls/two typed timeouts/zero provider calls, and12wheel/sdist outputs per quality job. Both locked dependency audits, repository secret scan, PR metadata and final gate passed. The tested merge checkout4c110a60a0e41102e75e471f12b4bc6f9b9e6679 has exactly the same tree169901bae724225d5b1bcb75780432a7efdc6e07 as the reviewed head, independently verified through GitHub commit objects. Main77b98df push run39742751290 also succeeded before dependency work began.

Local lint/format/import/lock and strict100-source typing passed; all6wheel/sdist pairs built, the locked audit found no known vulnerabilities, and clean0406e82 strict replay consumed six calls/reproduced two timeouts with zero provider calls. A clean installed environment uses exact exported lock constraints; network-denied probes matched52harness and11Supply source/resource files, ran20simulator scenarios and constructed all3Inngest functions. An initial offline installation could not find missing binary distributions and tried newer unpinned transitive versions; the successful install uses explicit current-lock constraints and no version upgrades. Markdown audit checked78files,492immutable source ranges and409local links, with no missing targets.

The first local replay test invocation hit sandbox temporary-directory restrictions (51passed/24setup errors); this is diagnostic, not a pass. The first broad local run also encountered existing CFPB raw-source guards: the default temporary directory lies beneath C:\.git. A diagnostic placed inside the checkout correctly failed for the same isolation rule. Repeating the entire CFPB source suite in an external D-drive directory passed29tests4.98seconds. The broad local run was stopped, preserving its log, and rerun with explicit external TEMP/TMP. Those broad local results remain pending here; hosted846/86 results and local30/18 focused results are the verified acceptance evidence. No source guard was weakened and C:\.git was untouched.

PR review remains the user's gate. No paid provider, production carrier/billing effect, deployment, human outcome gold or release promotion is inferred from these mechanism checks. Native project-board status remains unverified. Subsequent documentation-only commits preserve the tested executable/configuration/lock bytes; repeat only affected checks and final exact-head hosted acceptance.


### Complete local evidence and review bookkeeping

The complete local offline rerun passed846tests666.16seconds using external D-drive TEMP/TMP. One cache-metadata permission warning did not affect assertions. The complete local SQL run passed85of86tests in1026.17seconds: the sole Olist operator CLI failure was its correct private-file guard under C:\.git, not a shipping transaction failure. Rerun only that failed test with external D-drive state/output:1passed32.80seconds. Do not relabel the first run as86passed; hosted SQL supplies a clean single86-test run. All owned test fixtures performed normal teardown. Existing shared Langfuse containers were not stopped or altered.

Documentation-only review head3a40e44 also passed all ten hosted jobs in run39865663854. No new executable, configuration, lock or source data was changed after0406e82. Final documentation records completed evidence and updates merged R5/R6/S1 statuses; the three new issues stay open Review. Prior user-merged #89 issues43/44/52 were explicitly closed completed after verifying main77b98df and successful main run39742751290. Native project-board read-back remains unverified. User review/merge, production carrier/authentication/hosting and S6 fresh release evidence remain separate gates.


## Entry 34 — Scoped shipping workbench and durable factual notices

Date: 2026-10-22 (Africa/Lagos). Branch `codex/s5-supply-console`, based on user-merged #90 main `21d3bef`. Work is starting; results follow actual checks.

### Context

The user reviewed/merged #90, then explicitly selected **S5 #56 only**. S6 #57 remains behind the Olist fresh-release gate. They chose durable in-app notices and message previews only. No email/webhook delivery, paid model call, real carrier action or deployment is authorized. The previous SIM policy remains unchanged:100.00/action,500.00/incident,separate review above25.00,30-minute windows,two stale supersessions and blocked missing/conflicting/stale facts.

### Before you read on

How can an operator see budget, approval and committed effects from one consistent snapshot, while a shipment message never turns command acceptance into a delivered-shipment claim? Sketch the authenticated scope, canonical snapshot and durable notice identity before implementing the UI.

### Options considered and chosen

Keep this as a local authenticated Supply application using the established FastAPI/session pattern and its own domain-owned namespace. Importing Revenue console classes would break industry independence; a broad shared-auth redesign would mix unrelated vertical changes into S5. Reuse the reviewed session pattern without changing other verticals. Add only the already pinned FastAPI/Uvicorn optional web metadata and preserve dependency versions.

Add one SQL-owned consistent incident snapshot rather than assembling budget and effect totals from separate transactions. Budget lock comes first, then sorted shipment locks. Terminal expiry reconciliation and receipt reads happen under that same snapshot. Browser JSON carries IDs/fingerprints, never grants, prices or claimed eligibility.

Persist in-app notices by canonical tenant/incident/shipment/status fingerprint. Reconciliation after a missed write/restart reconstructs a committed notice from the receipt and a separate terminal notice from canonical confirmation state. Duplicated refreshes cannot create another notice. Message previews use an explicit fixed vocabulary and known observation timestamps; estimates are labeled estimates and no delivery outcome is invented. Optional alert context must be a separately provisioned S1 public AlertFact; its freshness is shown and it does not establish a weather-shipment causal link.

### How to build it

1. Define server-provisioned principal roles (operator,reviewer,confirmer,viewer) with exact per-incident shipment scopes. Build role grants on the server. Accounts and opaque expiring sessions live in Supply-owned tables; passwords use the established PBKDF2 format, session/CSRF values are stored hashed and sign-in admission is bounded.
2. Implement the consistent SQL snapshot and derive role-filtered board rows from it. All dates and provenance remain explicit, all money uses exact integer minor units. Return decimal strings at the browser boundary. A proposed SIM action, a committed command and a confirmed modeled action must remain separate.
3. Store deterministic notices after canonical reconciliation. A notice insertion failure cannot roll back or duplicate a committed action: the next read recovers from the permanent receipt. Acknowledge read state per authenticated account after checking its tenant/incident/shipment scope. Never expose another user's notice or allow caller JSON to choose authority.
4. Expose loopback-only API/session routes with same-origin/Host checks, CSRF on mutations, bounded bodies and private error responses. Provision accounts/scenarios through trusted CLI commands; never add public registration or a client-supplied Grant endpoint.
5. Build an industrial operations interface: an incident rail, budget summary, scoped shipment table and exact-payload review panel, plus a persistent notice tray. Use packaged assets without external fonts/scripts, textContent for fact rendering, request epochs for session/incident changes and immediate private-DOM clearing on sign-out. Keep mobile layouts and keyboard focus usable.
6. Verify API role/tenant scope, exact review binding, durable notice recovery, confirmation wording, stale-response/session races and real desktop/mobile browser flows. Extend meaningful Node regressions against the actual browser asset. Preserve the existing S4 schema bytes and record a new invented replay capture only because the optional web lock metadata changes.

### Checks pending

Main merge tree is identical to reviewed63d4691 and exact-main strict replay passed six calls/two timeouts/zero-provider. Main CI is being checked before implementation issues are closed. No S5 check is yet claimed as passed. Original untracked root documents remain untouched; reuse the existing isolated D-drive checkout and external D-drive temporary paths because C:\.git correctly triggers raw/private-file guards.

### Implementation checks and debugging

The focused eight offline checks passed and repository-wide mypy passed 106 source files. The first SQL attempt could not start because Docker was stopped; the verified Docker executable is on D:, not the standard C: installation path. Start that installed Desktop hidden and rerun the isolated trial. A fixture import was initially removed by lint as unused; retain the explicit fixture import with a narrow F401 annotation and avoid the duplicate offline/integration test module name.

The actual-asset Node regression found that serializing login together with its initial workbench load could delay logout indefinitely. Extract signIn/signOut, serialize only the login/logout request, then load incident data outside that queue. The regression now proves immediate private clearing, rejection of late refresh responses, logout during stalled initial workbench, and exact signed-64 money formatting. SQL, real-browser, full regression, packaging and replay checks are still pending; no release acceptance is claimed.

### Standalone-extra check and completed regressions

The full local offline suite passed855 tests in1244.74seconds with a cache permission warning; this did not affect test outcomes. Initial hosted39878331042 passed allten jobs:855tests per OS/Python cell and87SQL tests. Actual browser operator→reviewer→operator flow showed20.00 then100.00SIM committed,400.00remaining, distinct pending/approved/awaiting states and truthful notices. At390px the document remained390px wide and the table scrolled inside its container.

Inspecting the optional-extra boundary found that console_service imports the LangGraph workflow, but web initially declared only FastAPI/Uvicorn. The workspace development extra included workflow and hid this gap. Add the existing langgraph1.2.15 pin to web, with no version change. Verify the built web wheel in a fresh external environment. Since v8 is already published on the draft branch, preserve it as history and create an explicit invented v9 capture for the corrected metadata. This is a packaging correction, not new provider evidence.

### Corrected wheel and browser acceptance

The isolated web-only wheel import reproduced ModuleNotFoundError for langgraph before the correction. The rebuilt web-only install imports the console/CLI successfully; eleven package resources are present and installed strict replay consumes six calls/two timeouts with zero provider calls under network denial. Corrected-lock focused checks passed115 tests in25.79seconds; Ruff and format checks passed. The actual Edge browser completed assessment, separate-review approval, operator commit and SIM confirmation at390px, with100.00SIM committed/400.00remaining and explicit no-delivery wording. The task-owned browser, server, trial and Docker service were cleaned up without touching other services. Main S4 operations.sql remains identical to merged #90. Full local SQL completion is still awaited.

### Local acceptance completed

Full isolated SQL regression passed87 tests in1748.60seconds, with two non-failing warnings recorded in the private log. The full offline run passed855 tests before the metadata-only standalone correction; corrected-lock focused replay/Supply checks passed115 tests. Clean4389aa8 strict replay consumed six calls/two timeouts/zero provider with current locke9694f44 and v9digestf2ee896a. Six rebuilt packages, standalone web import/resources/installed replay, dependency audit, lint/format and real desktop/mobile role flows passed. Initial hosted39878331042 passed allten jobs with855per qualitycell and87SQL. Final hosted acceptance will be attached to #56/#91 after the last documentation commit rather than creating an endless documentation/CI commit cycle. S5 stays Review until user merge and post-merge verification; S6 remains gated.


## Entry 35 — Source-grounded prior-auth evidence with fresh model evaluation

Date: 2026-10-23 (Africa/Lagos). Branch codex/p1-p2-p3-prior-auth, based on verified main1e59722. Work has started; implementation/evaluation results follow actual execution.

### Context

User merged #91 (called it #55 in the message; actual GitHub merge verified). Main39881820867 passed nine applicable jobs: actual logs856tests per qualitycell,87Postgres and zero-provider strict replay. Clean exact-main replay passed; #56 closed completed. User selected the next eligible independent batch, then explicitly approved #46/#47/#48 with prerequisites delivered and verified inside one review. #57 remains gated by #33; CFPB #36/#37 remain behind unmerged #84.

The user challenged carrying the earlier offline-only instruction into every batch and now requests use of the configured model where appropriate. This supersedes the offline-only limit for this batch. Use the existing Gemini Developer API gemini-3.5-flash-lite through shared bounded admission with the previously confirmed billing-disabled Free project; no paid route or fallback is authorized. Fresh candidate evidence and deterministic mechanism checks serve different purposes. Model labels remain AI-provisional unless qualified review actually occurs. Reviewer availability is unanswered, not presumed.

### Before you read on

How do you prove a quoted span supports a coverage criterion, rather than merely existing in the note? Sketch separate retrieval, extracted facts, criterion validation and evaluator labels, including negation, conflict, missing data and policy-version changes.

### Options being investigated

CMS national CPAP coverage policy240.4 version3 offers checkable criteria with explicit effective date2008-03-13. It is not the same as contractor-specific LCD33718; keep national and local rules distinct and exclude ongoing coverage/CED from the initial scope unless represented explicitly. CMS code content can contain licensed AMA/ADA material; public access is not blanket redistribution permission. Prefer code-free government policy prose with exact source pins and separately typed code validation.

MTSamples direct access returned403 and use rights have not been established. Do not bypass access controls or relabel an arbitrary mirror as an original source. Research alternatives with explicit source/license evidence before choosing illustrative notes. Existing note corpora with credentialed DUAs or research-only restrictions cannot silently become production-ready data. Invented mechanism notes remain useful but do not substitute for the required authentic source preparation.

### How to build it

1. Pin selected policy/source versions, effective dates, use constraints and reviewer status before writing the criterion compiler. Keep raw source externally and publish only safe provenance/aggregate reports.
2. Define closed redacted input, source-span mapping and evaluator-only label contracts. Group original notes and every edit/counterfactual into one split. Expected decisions are authored independently of the production aggregator; disputed labels remain provisional.
3. Retrieve policy evidence and obtain typed model extractions via shared ModelGateway with bounded calls, deadlines and token reservations. Validate actual note spans plus criterion meaning, units, temporality and conflict before accepting met. Missing or unsupported output becomes insufficient/review.
4. Separate development prompt work from a frozen held-out fresh candidate run. Record source/split/code/prompt/model/scorer pins, completed/error/abstention denominators and incorrect-approval recommendation risk. Do not call this clinical validation or real authorization.
5. Run deterministic privacy/injection/label-isolation tests, independent source checks, fresh model evaluation and package/hosted verification. Preserve gateway controls and previous replay fixtures; no model calls in CI.

### Current checks

No P1/P2/P3 acceptance result is yet claimed. Google model/pricing docs were rechecked on2026-10-23; the route/token ceiling remains compatible with existing admission. Free-tier content-use conditions mean no real patient/private notes are sent. Source selection and reviewer availability remain open.

### Restoring live model execution

The first bounded probe stopped at configuration validation, before provider dispatch: current/root checkouts have no Gemini key. A presence-only check of registered repository worktrees found the original confirmed Free configuration in f3-command-entrypoints. Automatic approval review rejected copying credentials because reuse from that specific checkout had not been explicitly authorized. No copy/provider call occurred. Asked the user to authorize that exact source or configure the current checkout; continue source/contracts work while waiting. Do not bypass the rejection.

### Live gateway restored

User explicitly authorized reuse of the existing Gemini configuration from f3-command-entrypoints. Restored only the two approved Gemini values into ignored .env.local without displaying credentials. git check-ignore confirms exclusion. The bounded two-request live gateway probe passed through the existing shared controls on2026-10-23. This is live integration evidence, not yet P3 model-quality evidence.

### Source mix approved

The user approved CMS national initial-CPAP policy plus published Synthea illustrative records, explicitly marked edits and invented edge cases, with provisional labels. This replaces MTSamples as the first note source: direct access/use rights remain unresolved. Synthea published records are synthetic, never described as real-patient evidence. Draft12 grouped cases and keep parent/edits in one split; freeze held-out cases before candidate prompt evaluation. User approved provisional labels, not clinical adjudication.

### First live domain extraction

The first invented development case completed seven fresh criterion requests through the bounded shared Gemini gateway, all with reported modelversiongemini-3.5-flash-lite. Exact spans and the independent narrow support checks accepted allseven criteria; disposition evidence_complete_for_review. No timeout, provider error, authorization or clinical-validation claim. Private full exchanges/results live outside Git. This development case is not held-out release evidence and must not be counted as such.

Official source preparation verified111C-CDA archive members and produced110bounded narrative records; one oversized narrative was omitted, so coverage is not described as all111. Three bounded records contain sleep-related material. The selected code-free national policy prose is2618characters, normalizedtextSHA4327d66a45efd038a19f9cfd690db3872b4a20df96e806f544eaeb5a9d6a5b8b. Raw sources/narratives stay on external Ddrive. First15privacy/citation/unit/threshold tests passed.

The support validator deliberately recognizes a small transparent grammar rather than pretending exact citation existence proves medical entailment. Unknown paraphrases stay insufficient. Scan uncited visible negative evidence in the supported grammar so choosing a positive quote cannot hide a known contradiction. Retain model errors and conservative false abstentions in the fresh report. No broad medical entailment, full coding validation or production approval is implemented.

### Development error analysis before holdout

Frozen cohort v1 has12cases/4families,6development and6holdout. v1development completed36fresh requests:5/6model results usable and5/6cases correct against provisional labels;0unsupported met/incorrect evidence-complete bundles. One original record failed typed citation validation because the model's offset range did not equal quote length. No provider failures were reported. Keep this failed case in the denominator. The run was exploratory on dirty source, not immutable release evidence.

Fix the failure class by asking the candidate for exact quotes and constructing half-open offsets independently on the server via unique substring matching. Preserve exact text validation and refuse ambiguous/nonexistent quotes. This is candidatev2, not silently repairing arbitrary model offsets. Rerun development before freezing source for holdout; do not tune against held-out errors. Preserve the originalv1 exchanges and report.

### Repeated-quote correction and candidate freeze

The v2development rerun used38fresh requests and produced2/6usable/correct results. Structural analysis found the same error class in allfour missing results: the correct literal AHI quote occurred twice in the note, and the unique-match guard rejected it. These are checker abstentions, not invented evidence or provider failure. Preserve v2results; do not claim the offset change automatically improved quality.

Candidatev3 maps each quote to every exact occurrence (maximumfour), retaining each context rather than choosing an arbitrary position. Each span is still byte-for-text exact and checked for omitted negatives; absent/over-repeated quotes fail closed. The policy compiler continues requiring unique source anchors. Focused25tests passed0.58seconds. The actual preparation CLI verified110bounded narratives/three sleep-related records and the same policy digest. Source subject identifiers were checked privately: the three selected records belong to three distinct subjects. Freeze candidate source before the first held-out run; no tuning on those results.

### Frozen holdout and installed-package verification

Clean implementation0e5953cd4dbb36512452b11d766e769301f2d188 produced6/6complete/correct held-out results and42/42correct criterion states against the separate AI-provisional labels, using42fresh Gemini requests. Published illustrative slice2/2; edited slice4/4. No provider/terminal errors, unsupported met states or incorrect evidence-complete bundle were observed. Two bundles proposed evidence complete for review; four were expected incomplete, giving0/2 and0/4 incorrect-complete denominators. These are not clinical approval metrics. No prompt or support-grammar change follows this holdout. Run the unchanged frozen candidate on development edges separately so final-candidate behavior there is visible too.

Local locked python dev.py check passed881tests in365.14seconds, Ruff/format and strict types116sourcefiles included. Allsix package builds and dependency audit passed. Install only the built harness/PriorAuth wheels with cached base dependencies in a fresh external environment; verify google is absent, deny socket creation, and run prepare on independently pinned archive/CMS inputs. It reproduces110bounded narratives/three sleep-related records and policySHAab967cf50cd496452cd9a6924afd17b661aec326d18a8310331e0de64df08796. This confirms source preparation does not accidentally require the optional provider SDK. Publication scanning found no configured key value in315publishable files and confirms ignored.env.local. Raw sources, labels and exchanges stay external. Draft#92 exists; hosted final acceptance remains pending.

### Final candidate edge checks and review handoff

The unchanged0e5953c candidate completed the six development cases after holdout:42fresh requests,6/6case and42/42criterion labels matched, including allthree invented missing/negative-education/short-study edges. No provider/terminal errors or unsupported met states. Keep this development result separate from the first unseen holdout. Preserve failedv1/v2runs and their dirty-source metadata in the aggregate; do not overwrite them with the successfulv3result.

Initial hosted39935230394 passed allten jobs; actual logs show881tests in each Linux/Windows/Python3.12/3.13 cell,87Postgres tests withone non-failing warning, strict types116files and replay6calls/2timeouts/zero-provider. API tree comparison proves testedmerge9a9692ac equals evaluatedhead0e5953c (treedad1fd5065f88b10e3e747df86dd91e4050d59a8). Only documentation changes follow that candidate. Final review metadata and exact-head CI are recorded on#92 after the documentation commit, avoiding an endless commit-to-record-its-own-CI loop. P1/P2/P3 move to Review, stay open until user merge and post-merge verification. Clinical labels, P4/P5 application and P6 release remain outstanding.


## Entry 36 — Durable prior-auth document review

Date: 2026-10-23. User selected #49/#50 together after merging #92. Start codex/p4-p5-prior-auth-review from main6c2b7d9; the merge tree equals reviewed6e016c6 and exact-main replay passed. Main hosted acceptance is still running; do not close prerequisites before it passes.

### Context and construction decision

A new document must invalidate the exact previous evidence state without duplicating work after a worker crash. Keep Postgres as canonical owner of versioned redacted notes, pinned policies, document receipts, wait deadlines, assessment jobs and review events. LangGraph drives bounded job steps; its in-memory state does not substitute for durable state. A leased job may execute its model calls again after a crash; only the current case version/lease can publish one canonical result/event. Do not promise exactly-once provider calls.

Before reading on: if a policy update commits while the model is assessing a newly appended document, which versions must the result bind to, and what should the stale worker be allowed to publish?

Use optimistic case versions and transaction locks. Separate trusted raw-document redaction/import from the reviewer browser: store/serve only explicitly reviewed redacted input. The reviewer sees criterion/source citations, uncertainty, missing items, waits and immutable events, with provisioned tenant/case scope and server-resolved capabilities. There is no authorization/denial action. Select a quiet editorial case-file design: warm paper, dark ink, teal status accents and compact evidence tables, with no external fonts or assets.

### How to build it

1. Define closed principal/wait/document/review contracts and an immutable SQL schema under prior_auth_app. Runtime can read provisioned accounts, update session counters and mutate only this domain state.
2. Insert initial case plus pending assessment atomically. Document delivery uses stable IDs and payload digests; append redacted text without shifting earlier offsets, invalidate affected criteria, cancel obsolete work and enqueue one new version. Policy replacement invalidates every claim. Timeouts create one review event and never synthesize missing evidence.
3. Claim jobs with skip-locked bounded leases, assess outside transactions through injected gateway controls, then compare version/lease before publishing. Retain unaffected exact evidence only when earlier text remains the identical prefix. Reconcile after restart from SQL.
4. Provision accounts through a trusted CLI. Add scoped local sessions, CSRF/origin checks and a browser with criterion/evidence/source panels, durable requests/review notes and prompt private-state clearing on logout. Raw notes and expected labels have no browser upload route.
5. Verify duplicate delivery, lease recovery, stale-worker/policy conflicts, waits/timeouts, tenant/role scope, redaction canaries, actual UI flows and installed resources. Model evidence remains provisional; P6/O8 release gates remain pending.

No P4/P5 checks are claimed before execution. Reuse the approved ignored Free Gemini configuration for bounded illustrative checks; no paid fallback. Source/label constraints from Entry35 persist.


### First mechanism evidence

Merged #92 main39938575348 passed nine applicable jobs; metadata skipped intentionally. Actual logs881tests per qualitycell,87Postgres, strict6call/2timeout/zero-provider replay. Closed#46/#47/#48 completed after exact-main replay and identical tree verification.

P4/P5 first focused checks passed29tests, strict types122sources and actual browser-asset Node session regressions. Required isolated Postgres suite passed7tests in124.95seconds: concurrent duplicate document receipt, selective criterion reassessment, persisted wait expiration/renewal, in-flight policy supersession, hard-process-exit lease recovery, bounded repeated leases, tenant/role/session restrictions and redaction-canary absence from model input/events. Source test failure found that FastAPI validates strict datetime/tuple fields in Python mode; authenticate first, then revalidate the bounded JSON payload with the closed contract's JSON mode. No broad coercion or exception-detail echo was added.

PriorAuth now declares optional workflow/web extras using existing pinned versions. The first uv lock refused the missing explicit workspace source; add prior-auth to tool.uv.sources before locking. The lock metadata changes despite no library-version update, so preserve published replayv9 and create an explicit inventedv10capture. Full checks, real browser, installed extras and fresh model workflow check are still pending.


### Fresh failure and local resource interruption

The first invented workflow probe dispatched one fresh Gemini request and timed out. SQL stored qualified_review with assessment_failure and no supported findings. Preserve its external exchange/summary; do not count a conservative fallback as successful model reasoning. Continue the reviewer document-request path and a separately bounded supplemental run, with no holdout tuning.

A focused combined replay run without external-cache write elevation hit26temporary-directory setup permission errors (81tests passed). Earlier elevated29focused/7SQL checks passed; the full elevated locked suite is running with external D-drive TEMP. A later shell launch briefly failed with OS112 disk-full; read-only disk inspection found C: subsequently had863MB free and D:50GB. No files were deleted. Resume with D-drive temporary paths, preserve logs and report any persistent resource block rather than altering test expectations.


### Full local regression and resource block

Full locked check passed886tests in489.06seconds, strict types122sources,184formatted Python files and both import boundaries. Allsix package builds and dependency audit passed. The shipped Node asset passes private clearing, stalled-load logout and late403after a new sign-in; the latter required binding denied-session clearing to the request's epoch. Seven focused SQL checks remain passed from before the resource interruption.

Local browser sign-in then returned a fixed503 while Docker stopped responding; the host had briefly rejected process creation with disk-full. Do not weaken login timeouts or claim a browser pass. The user is clearing space; continue installed-package/hosted work and preserve initial fresh-timeout evidence. No unrelated services or user files have been stopped/deleted.


### Preserve invented provenance on supplemental arrival

Reading the delivery path found a provenance bug before supplemental live acceptance: it unconditionally marked appended notes edited_illustrative, even when the parent was wholly invented. This could misdescribe an invented workflow as an edited published source. Preserve invented for an invented parent; only a published/edited illustrative parent becomes edited_illustrative. Add a state assertion to the actual duplicate-delivery test and rerun hosted SQL acceptance with the correction. No policy or support-grammar tuning follows from this provenance fix.


### Initial hosted and installed acceptance

Draft#93 at a9b9d44 passed initial39943225425 alltenjobs. Actual logs886tests per qualitycell and94Postgres (one non-failing warning), types122sources, Node assetordering regressions and strict replay6calls/2timeouts/zero-provider. A provenance correction is still newer than this hosted run and needs corrected-head SQL evidence.

A new external web-only wheel install has49cached packages and no Google SDK. With an outbound-network audit hook installed before imports, API/CLI/workflow imports pass; four packaged schema/web resources match source bytes and installed replay consumes6calls/2timeouts/zero-provider. Source publication scanning found no configured key in332publishable files and verified five new document links. Local Docker remains unavailable while the user clears space. Use an explicitly labeled in-memory UI fixture for layout checks only; do not present it as real SQL or live-model evidence.


### Correct the probe attribution: missing Windows main guard

The education-only follow-up produced a child FileExistsError at its supposedly exclusive output directory. Inspecting the temporary scripts found the real cause: neither had an if __name__ == '__main__' guard, so Windows spawn re-executed their top-level setup. The initial workflow child could block in workspace/Docker setup; the subset child re-created its existing output folder and exited. Thus those timeout/unavailable exchanges are gateway attempts, not established Gemini provider dispatch. Earlier journal wording attributing the timeout to the provider is superseded here. Production prior_auth.review_cli already has the correct guard; this is a task-local probe bug, not an application correction. Preserve both failed attempts, wrap each script in guarded main, use a fresh v2 output directory and rerun one bounded subset extraction. Never relabel failed startup as model-quality evidence.


### Guarded subset result

The corrected education-only script (fresh-education-only-v2) completed one actual Gemini request with no failure or diagnostics; the candidate supplied exact redacted evidence and the checker returned education met. Captured exchange contains no WorkflowIdentifierCanary. This independently checks subset extraction after the main-guard correction, without SQL or a full workflow claim. It ran on19f0580+dirty with the unchanged lock; raw exchange remains external. Aggregate evidence now separates both unguarded startup failures from this successful fresh observation. Do not merge them into quality denominators.


### UI-only inspection before claiming full browser evidence

The real Edge browser signed into the explicitly labeled in-memory fixture, rendered seven criteria/rationales/source citations and submitted a document request. Screenshots remain ignored/private and are UI-only, not actual SQL/model evidence. At390px, expanded policy digests caused the full page to reach415px wide; permit arbitrary wrapping only in explanatory/provenance text, keeping the evidence table's own horizontal scroll. The persistent success message also covered source text, so add a keyboard-accessible Dismiss control rather than auto-hiding information. Recheck current CSS/DOM before recording mobile acceptance.


### Corrected UI fixture acceptance and cleanup

Actual Edge UI-only flow passed document request, qualified-review routing, Dismiss, logout and read-only viewer rendering. Corrected mobile measurement: viewport390/document390/tablecontainer314/tablecontent620, with expanded policy provenance. Desktop1440 and mobile screenshots remain ignored. The fixture uses explicitly invented in-memory responses, not SQL; keep that boundary in the aggregate. Close only the task browser session and fixture process23732 after verification. The real local SQL browser/supplement path remains pending Docker restoration; do not call this UI fixture full application acceptance.


### Current wheel and remaining external-state dependency

After provenance and mobile corrections, rebuild/reinstall the PriorAuth web wheel in the isolated49-package environment. All21source/resource files match current0d8c1ad bytes; imports and installed replay pass with outbound networking denied before import. A bounded five-second Docker status probe still hangs and is stopped without touching the daemon/other services. The user is clearing host space. Keep#93draft and#49/#50Inprogress; remaining real SQL/browser/supplemental workflow checks are pending external Docker restoration, not silently marked passed by the UI fixture or the successful one-call subset check.


### Corrected implementation hosted acceptance

Corrected0d8c1ad passed39945068035 alltenjobs. Actual logs verify886tests per each Ubuntu/Windows Python3.12/3.13 cell,94Postgres withone non-failing warning,122typed sourcefiles, shipped Node session regressions and strict replay6calls/2timeouts/zero-provider. API tree comparison proves testedmerge3f2477689c2ea83fcc5c15cffe03aa8fa930dacc equals reviewhead0d8c1ad (tree81e5d3a28ab85a504e0df14b9c71305943ef091d). Only documentation follows that implementation. Final documentation-head status is recorded by PR checks; no self-referential CI commit loop. #93 remains draft until the explicitly pending real local SQL/browser/supplement path is resumed after Docker restoration. No clinical release claim.


### Restore Docker and verify the actual failure path

The user authorized restarting Docker Desktop after freeing disk space. A sandboxed Docker
probe also had configuration-access denial, so repeat diagnostics with authorized local access
before attributing every timeout to the engine. `docker desktop restart --timeout 45` could
not stop Desktop; inspect process executable paths, stop only processes under the verified
Docker installation, then relaunch Desktop hidden. Do not shut down unrelated WSL distributions.
The engine reported running after about 53 seconds; restore only the named demo Workspace.

Resume the saved version-1 case in Edge. Request all seven criteria with an explicit future
deadline, producing version 2. Run the guarded supplement script once: trusted import masks
the identifier, commits version 3, and the worker claims that version. Its isolated Gemini
attempt exhausted the deadline with usage unknown; available metadata does not establish
provider dispatch. Preserve the private fresh-supplement output, do not retry it as though the
delivery had never committed, and do not weaken timeouts to obtain a green model result.

Reconstruct ReviewStore from the saved Workspace and resubmit identical delivery ID/text with
the original expected version 2. Receipt 3 and an unchanged event count prove idempotency even
though the canonical case advanced. The job is done, invented provenance remains invented,
and stored case/events exclude the identifier canary. Edge renders seven insufficient findings,
the assessment-failure banner and cleared wait. Viewer write/unassigned-case requests both
return 403; reviewer routing adds one durable event and logout clears private DOM. Expanded
mobile citations measure document/viewport390/390 and table content/container620/314.
This supersedes the pending-Docker status above: actual SQL/browser continuation is verified,
including the guarded model failure path. Successful full-cohort extraction is not claimed;
the earlier one-call education subset remains separate positive fresh evidence.


### Final CI exposes an existing real-clock test race

Ready-for-review run39971144131 failed only Windows3.12:885tests passed, but the combined
Olist deadline/scope/policy/snapshot test expected a snapshot error and got event-input mismatch.
Its first call used a real one-microsecond deadline. A coarse clock could pass the entry check,
bind the event, then expire inside the graph; later calls reused that StubStore and changing
the source pin correctly hit the existing event binding before the intended snapshot check.
Reproduce with an injected clock returning the initial timestamp once, then one second later:
first call times out after binding, next altered snapshot raises business_event_input_mismatch,
and zero refunds occur. This is test-state contamination, not a new production decision bug.
Fix the existing test by injecting a constant time one second after its captured clock and
assert no binding after the expired-entry call. Keep application deadlines and identity rules
unchanged; run the entire Olist workflow test file before publishing this narrow CI repair.

The corrected Olist workflow file passed all14tests in7.53s; Ruff lint/format passed. One
non-failing pytest cache permission warning is retained as environment evidence.


### Reconcile C2 after verified Prior Auth #93

User selected updating still-open PR#84 after merging #93. Verify main116d7e5 tree54bafbe equals reviewed5acb634, main39973654251 nine applicable jobs, actual886tests per qualitycell/94Postgres, and clean replay6calls/2timeouts/zero-provider. Close #49/#50 completed. In the clean existing C2 checkout merge origin/main with --no-commit --no-ff. All five conflicts are shared documents, with no executable conflict. Retain C2 Entry27 and all later merged entries; combine README/planning sections and use current main study navigation plus the C2 chapter. Before committing, compare Git-normalized executable/config/lock bytes to main and all C2 source/tests to old reviewheadf5195b3. Check focused C2 behavior and links, then final clean replay and hosted matrix. Do not regenerate sealed source reviews or confuse provisional labels with human validation.

Reconciliation checks passed:218main executable/config files and5C2Pythonfiles match parent blob IDs; all36journal entries preserved. Focused21C2tests passed2.88s. Documentation check passed453local links/170immutable source ranges/19publication files with configured credentials absent. The first task-local audit used a Windows default decoder on UTF-8 journal text and failed after source comparisons; rerun with explicit UTF-8 confirmed preservation. No source data, sealed review, baseline or application behavior changed. Final clean replay and hosted checks follow at the committed head.


## Entry 37 — Typed CFPB triage and scoped review

**Context:** User merged C2 PR#84 as95397c4, tree-identical to305a52c. Main40003918806
passed nine applicable jobs, actual907tests per quality cell/94Postgres, and clean strict
replay6calls/2timeouts/zero-provider. Close#35 completed. The user selected #36/#37 as one
dependent batch and authorized existing Gemini Free settings plus a new24case provisional
pilot (12development/6regression/6holdout), mixing disclosed hash and risk-keyword sampling.
Show a small masked draft before model runs; expected risk/ambiguity judgments remain
AI-provisional. Consumer-selected product/issue references are evaluator-only, not harm truth.

**Decision in progress:** Use Pydantic AI through a custom shared-gateway model boundary,
not a direct provider SDK that bypasses call/token/deadline controls. Pin taxonomy from the
published form independently of held-out target frequencies. Exact evidence and valid
product/issue membership are deterministic support checks; model confidence is merely a
feature calibrated on development, not a probability claim. Compare Flash-Lite cheap-first
with always-Flash on a frozen cohort, with missing/error/review cases in denominators.
Google's2026-10-23 docs list3.5Flash-Lite and3.8Flash standard input/output free and ceilings
1048576+65536. Extend admission only for the reviewed stronger route; preserve old-route
behavior. Billing-disabled attestation and no paid fallback remain mandatory.

**Operational boundary:** Store reviewed masked narratives and fixed metadata in a scoped
Postgres work queue. Tools can enqueue review only; no complaint resolution, refund or
external account mutation exists. Reuse established session/perimeter patterns without
cross-vertical imports. Export only closed redacted trace projections and diagnostic
aggregates. Drift is a distribution diagnostic, not evidence of accuracy or consumer harm.
Keep data/labels/model output separate and do not change O8/C5 release gates.


### Seal the pilot before model output

The user approved the24case pilot, expressly authorized reading the published narratives
in this tool context after automatic approval review rejected the initially unapproved
transcript destination, then approved the first3case draft rubric. The pinned source
verification completed. Selection excludes previous-pilot exact groups, uses full texts
250–8000characters without truncation, and draws half keyword/half nonkeyword background
within12development/6regression/6holdout. This restricted stress pilot is not a population
sample; exact grouping cannot establish near-duplicate or consumer independence. Freeze
seed/regex/frame in the private selection policy before labeling.

Read all24full narratives without consumer product/issue references or predictions. Retain
publisher masks; no additional personal identifiers were found in manual review (not a
privacy certification). Seal9routine/5elevated/10uncertain and15clear/9ambiguous with exact
Unicode evidence and reasons. Hash reviewed inputs, evaluator selection, reviews, taxonomy
and selection policy before any candidate call. Taxonomy uses only development-observed
pairs (11products/131pairs), pinned to the official form/source manifest; it is an observed
subset, not a claim to parse every permitted form combination. Unknown pairs route review.
The12case C2 pilot, its labels and full-cohort baseline artifacts remain unchanged.

### Verify the actual Pydantic boundary

The first invented tests exposed a pinned-SDK API mismatch: Agent no longer accepts an
instrument constructor argument. Inspect the installed2.56.0 source and explicitly set
agent.instrument=False after construction. Keep the custom Model returning structured
output through the shared gateway, with Pydantic validation and deterministic exact-span/
taxonomy checks. Also supply required unknown cost/currency fields in invented Usage
witnesses rather than assuming omitted accounting means zero. All14classifier/API/diagnostic
focused tests passed; a non-failing event-loop deprecation warning is retained. The shipped
CFPB browser asset passed late-response/logout/session-expiry regressions with zero network.
Both3.5Flash-Lite and3.8Flash were present in the configured model listing; that is access
metadata, not successful generation or free-billing proof. No paid fallback is permitted.


### Development-only evidence repair after interrupted session

The first24attempt development run completed while approval review was unavailable. All12
cases routed review; retain its private fresh-development-v1 and router-policy-v1 unchanged.
Valid JSON responses often quoted a real passage but supplied wrong character offsets. Do
not accept approximate spans or silently rewrite model offsets. Change the candidate schema:
model supplies exact quotes only, trusted code accepts exactly one occurrence and computes
Unicode offsets. Missing, repeated or duplicate quotes fail closed. Canonical stored Prediction
still contains verified spans. This is candidate-v2 development tuning; no regression/holdout
candidate run has occurred. Reuse sealed labels, create fresh-v2 outputs and a separately pinned
v2 policy, and retain failures/unknown usage rather than calling all-review routing quality.

### Freeze the conservative result and verify the durable desk

The fresh v2 development collection completed24 gateway exchanges. Nine cheap outputs
passed typed/quote checks, but development correctness and provider failures left both
thresholds at1.01. Freeze that policy before fresh regression/holdout. Both independently
executed pipeline modes then reviewed all6regression and all6holdout cases. The two
provisionally elevated regression cases reached review; holdout had zero elevated cases,
so recall there is unknown. Strong-route rate limits are failures, not a quality comparison.
Do not improve the result by excluding failed cases or lowering the error bar after seeing
holdout. Keep the original v1 failure record and publish only aggregate counts and pins.

Build the desk in this order: domain-owned SQL and provisioned principals; atomic enrollment
plus pending jobs; bounded SKIP LOCKED leases; exact-version result publication; enqueue
receipts checked before expected version; loopback API/session/CSRF; then UI controls.
Holding a job lock and then a case lock would invert the writer order, so claim reads the
case without locking and publication rechecks it later. A reviewer enqueue increments the
case version and invalidates leased work. The next lease attempt above three publishes
review without another provider call. This fences publication, not exactly-once provider use.

Five real Postgres tests passed, including concurrent identical commands, stale lease refusal,
disabled-account/role/event-delete checks and an actual child exit after claim. Start an
external task-owned trial and the local server, enroll a clearly invented record, log in as
reviewer in Edge and enqueue. The stored version became2 with one review event. Switch to
the provisioned viewer: write/unassigned reads returned403, no enqueue control appeared and
logout cleared the private article. Expanded narrative/provenance at1440px and390px had no
horizontal overflow. CLI locator strictness initially matched two revision strings; narrow
the locator rather than treating that test-script error as an application failure.

The first broad local test command forgot the established external D-drive TEMP/TMP settings.
This machine has a C-drive ancestor Git boundary, so49 source-storage tests correctly rejected
its default C-drive temp paths. The remaining replay failure correctly rejected the changed
lock. Result50failed/873passed is not acceptance. Repeat with external temp configuration,
and create a new invented replay version after a clean implementation commit; preserve every
historical fixture and compare all six canonical request/response pairs before updating pins.

Tracing composes H8 explicitly; automatic Pydantic prompt capture stays off. A new per-run
HMAC key prevents raw case/input identity from escaping. Original/edited/invented maps to
original/hybrid/synthetic trace provenance, and no fake source observations are emitted.
The first local export was accepted, but the npm launcher stalled before independent CLI
read-back. Use the already-installed pinned CLI directly; queue acceptance alone cannot prove
stored observations. Diagnostics compare only assigned aggregates and retain empty/unknown
language and usage dimensions without claiming accuracy drift.

The direct pinned CLI read-back succeeded: four stored observations with run/agent/node/model
hierarchy, no raw invented narrative/credential canaries, and healthy export/flush/cleanup.
This was an invented mechanism trace with zero outbound model calls, separate from the live
provisional pilot. Shared H8 intentionally uses HMAC model references, so backend model-name
pricing inference is unavailable; do not claim automatic complete cost analytics.

Capture invented replay v11 from clean implementation314211e353cfcecad0569efc64b44d11ac139d6a
and lock9c055070aa57eeaf2294066684db73e31a960b81f9c559360e9f7f0419f1bd26.
All six canonical requests and responses exactly match v10. Publish exclusively with digest
aa68c8598c7306cb6f242a585a98d0e5e4df6d644754b11f4c5031af6c4e04e5, retain v1–v10
unchanged, and add v10 to historical changed-lock rejection tests. This is invented fixture
maintenance with zero provider calls, not a fresh CFPB result.


### Package the review candidate

The corrected complete locked check passed924tests460.78s,136typed source files,203formatted
Python files and both import contracts, plus lock/Ruff. Six packages built and dependency
audit found no known vulnerabilities. A fresh external CFPB web-only wheel environment matched
all23module/schema/asset bytes, served the API/assets and denied signed-out case reads.
Google/Langfuse SDKs and other industry packages were absent. The first proof placed the
strict network audit hook before TestClient; Windows creates an internal socket pair for its
event loop, so this blocked startup rather than finding a product defect. Separate the phases:
first exercise in-process API resources, then install the strict network hook and consume all
six recorded replay calls, with zero provider calls. Both completed after this correction.

The GitHub connector showed an unsubmitted PR form and created nothing. After the user said
proceed, use the already-authorized repository API client, check for an existing head PR,
create draft#94 once and attach it to this chat. Final hosted results will be recorded on the
PR/issues; no source narrative, private per-case label/output or credential entered publication.

### Diagnose the hosted secret-scan failure

The hosted scanner found six generic-api-key matches: two source-file digests repeated in
the three phase inventories, all introduced in314211e. Independently hash current desk_api.py
to reproduce its published digest. Reconstruct desk_auth.py's historical docstring and CRLF
bytes to reproduce its second digest. These are file integrity values, not authentication
material. Preserve the evidence and scanner rules. Follow the repository's existing narrow
historical-fingerprint pattern: add only these six exact commit/file/rule/line fingerprints
to .gitleaksignore, leaving every other location and future value subject to scanning.
No runtime source changed; rerun exact-head hosted acceptance after this metadata-only fix.

## Entry 38 — Fresh Olist review evidence after the offline pilot

**Files touched:** Olist case preparation, fresh evaluation/report modules, tests and release guides.

### Context

User merged#94 as3601508ea5bf974c9bd0bfc3279815d293cc903c, identical reviewed tree.
Main40022445942 passed nine applicable jobs, actual924tests per quality cell/99Postgres,
and clean exact-main replay6calls/2timeouts/zero-provider. Close#36/#37 completed.
Every remaining batch depends on O8#33. User explicitly superseded its prior offline-only
instruction: resume with existing Gemini Free and prepare labels/baseline/thresholds for review.
This does not authorize inventing human adjudication or silently promoting a release.

### Before you read on

How can a fresh model intent be evaluated against durable SIM effects without giving the
planner expected labels or turning a timeout into a claim of rollback?

### Options considered

- Reuse the old exposed holdout as new evidence: preserve it as a historical mechanism pilot,
  but reject any claim that it is an unseen fresh holdout. Its adversarial text also leaves
  multiple primary intents ambiguous despite a fixed caller-selected plan.
- Chosen: select new source order groups under a new fixed seed, exclude every old pilot
  group, retain the approved constructed policy/scenarios, and write explicit primary requests
  with separately marked untrusted injection text. Seal those inputs and literal AI-provisional
  labels before candidate output. No original review text, source identifiers or order fields
  need to reach the provider: the existing GatewayPlanner receives request text only.

### Why

The12case/6group first pilot is small enough to inspect completely: four cases per split,
three eligible full refunds and nine required reviews. This is a coverage-selected hybrid
stress sample, not representative Olist traffic or observed refund ground truth. Three fresh
trials per case preserve36scheduled opportunities including failures. Fixed text rules and
always-review provide explicit baselines; state correctness still comes from independent SQL.

### How to build it

Extend case preparation with explicit selection seed and excluded exact order groups while
keeping the default O3 selection unchanged. Preserve original O3 bytes. Render new request
text from the agent-visible intended request, never from expected action/reason/split. Keep
the evaluator's literal policy-table labels outside the provider input. Bind code/lock/scorer/
source/input pins before execution, use one owned database per trial, capture complete state
before and after, and preserve every attempt receipt before returning model output. Score
with the existing independent exact-delta scorer. Record unknown usage/cost, source kind,
split, faults and three-trial reliability separately. Keep final release false until reviewed
labels/baseline/thresholds and all required evidence actually support it.

### What went wrong

Inspection found that the old generic adversarial message says reship or refund for several
different recorded intents, including an exact partial amount absent from the text. It was
valid for caller-selected offline mechanism checks, but would confound a text-intent comparison.
Prepare a new disclosed request version; do not rewrite historical cases or fit to held-out
candidate output. No new provider call has occurred at this design checkpoint.

### Mechanism verification before freezing the candidate

The focused suite passed 14 tests, including fresh receipt capture, hidden-label isolation,
source-group exclusion and independent evidence read-back. Four real Postgres collector
tests passed in 112.88 seconds. Their invented planners exercise exact SIM state effects,
zero-dispatch duplicate delivery, timeout and exception handling, and owned database cleanup.
Strict typing passed for 139 source files. The offline reader checks the separately retained
inventory pin, persisted receipts and recomputed report; changing and re-pinning a verdict
alone does not hide the discrepancy. These are mechanism checks, not provider-quality results.

The complete locked offline check then passed 935 tests in 667.01 seconds, with 139 typed
sources, 208 formatted files and both import contracts kept. All six wheel/sdist pairs built;
the locked audit found no known vulnerabilities. In a separate installed workflow environment,
all 27 Olist wheel resources matched their built bytes, Google/Langfuse SDKs and other verticals
were absent, and six strict replay calls completed with network denied and zero provider calls.
The existing event-loop deprecation and local pytest-cache permission warnings remain disclosed.

### Actual fresh experiment and independent read-back

Freeze candidate 7d59527 before creating the canonical plan. Run all 36 trials for each
baseline, followed by the bounded 36 Gemini attempts. Do not alter executing Python/SQL/lock
bytes or rerun failures. Rules scored 36/36 correct; always-review scored 27/36 and correctly
received no eligible refund completion credit. Gemini scored 30/36 correct, six unresolved
timeouts, zero observed unsafe effects, 6/9 eligible refunds and 24/27 required reviews correct.
Seven of twelve cases passed all three repetitions; holdout scored 10/12 with two timeouts.
All 108 duplicate deliveries retained the original result/state and all owned databases were
removed. The experiment service stopped while unrelated Langfuse services stayed running.

Keep the emitted evidence byte pin separately, invoke the offline report command with that
pin, and recompute every verdict from sealed rows plus separately persisted receipts.
Read-back passed without another provider call. Publish only aggregate code/input/evidence
pins and mode/split/source-type/treatment counts. Full source facts, labels, SQL snapshots
and model exchanges remain external. Output-token usage and cost are unknown for every
attempt; zero summed reported output is not zero consumption. The first trials overlapped
local offline checks, so timing cannot establish isolated provider latency. The model card
records these limits and the failed proposed criteria. No threshold or label was promoted,
and #33 remains in progress with downstream releases gated.

## Entry 39 — Repairing a dependency audit after merge
**Files touched:** `uv.lock`, `docs/code-study-ci.md`, O8 status documentation.

### Context

The user merged #95 as `4b42d661368d2018c770962deff86fb81c11f844`, with the identical
reviewed tree. Exact-main strict replay passed. Both main dependency-audit jobs reported
three advisories for locked `filelock 4.1.2`: CVE-2026-112906, CVE-2026-112940 and
CVE-2026-112914. Their fix-version column lists 4.2.1. The earlier successful audit is historical
evidence, not a guarantee that future advisory data will stay unchanged.

### Decision and construction

Use a targeted lock update to the reported fixed version, preserving every other package.
Do not add audit ignores or relabel the failed main run as accepted. From the merged commit,
run `uv lock --upgrade-package filelock==4.2.1`; inspect the diff to confirm only its version,
distribution URLs, hashes, sizes and upload times change. The PyPI release page confirms
the 4.2.1 files and Python >=3.11 compatibility. Locked setup replaced exactly one package.
Run the strict hashed audit, CI-helper tests and strict replay, then require the full hosted
platform/Postgres matrix. Actual check results follow after completion.

### Evidence boundary

The historical fresh O8 experiment remains bound to its original candidate and lock. Updating
the environment does not revalidate those provider results for a new candidate. Preserve all
old pins and the six-timeout result; no new provider calls are part of this repair. Independent
label/baseline/threshold requirements still block O8 release.

Locked setup changed exactly one installed package. The repaired strict hashed audit found
no known vulnerabilities, and 29 existing CI-helper/development-command tests passed in
0.71 seconds. The local pytest-cache permission warning is non-failing. Full hosted checks
are still required for this changed lock; no new product tests mirror a version string.

The first clean-fix replay rejected v11 because `ReplayBinding.compatible_context` includes
the environment lock. This is the expected guard, not a reason to loosen matching. Generate
invented v12 from clean0719174 with `invented_recording`, compare each of its six canonical
requests/responses with v11, and publish exclusively with `write_recording`. All six match;
there are zero provider calls. Change only the trusted fixture resource/digest constants and
add v11 to the historical-lock rejection cases. Preserve every historical fixture and the
private O8 evidence. New pin6c8a4d3c identifies this invented transcript, not a fresh model run.

The combined replay/CI-helper suite passed109tests in5.73seconds, including every historical
fixture's current-lock rejection. Ruff and formatting passed for the changed Python files.
The clean final commit's standalone replay and full hosted matrix are verified separately.

## Entry 40 — Measuring Olist attempt startup and reconciling usage
**Files touched:** shared Gemini accounting/isolated transport, Olist fresh runner and tests.

### Context

User merged #96 as6bcac649, with identical reviewed tree. Main audits now pass. Every remaining
implementation issue depends on O8#33. The user explicitly authorized a separate experiment
with at most36GeminiFree calls to investigate the previous six timeouts and missing usage;
the original captures/holdout remain unchanged and independent release review stays required.

### Diagnosis before changing behavior

All30successful original responses retained provider prompt/candidate/total counts, but omitted
the optional thinking count. Each reported total equals prompt plus candidates. The adapter
required both candidate and thinking counts, discarding usable output accounting. Google's
UsageMetadata documents total as prompt plus tool-use prompt plus thoughts plus candidates.
Recover output only when known counts reconcile with no residual; an absent field alone must
not become zero. Keep provider raw counts and cost unknown. Six timed-out responses have no
metadata and remain unknown, with collector durations31.13–34.38seconds under30second attempts.
Those durations alone cannot identify provider delay, SDK import or process startup.

### Construction plan

Capture bounded parent/child phase timestamps with shared memory: worker entered, generation
returned and response frame ready. Persist aggregate-safe diagnostics beside the fresh row,
never infer provider dispatch/billing from child startup. Keep owned-process deadlines and
cleanup intact. Allow an explicitly pinned attempt timeout in the experiment plan (existing
default30seconds; proposed follow-up60seconds within shared controls). Keep the prompt/policy
unchanged and use separate frozen source groups/labels for new quality evidence; no holdout
tuning or historical rewriting. Confirm counts with wire-level tests and phase behavior with
invented spawned workers before any live call. Actual results follow after execution.

### Pre-capture verification and draft

The first combined SDK/controls/fresh suite passed126tests and exposed one test-double indexing
error: adding phase arguments moved the buffer/size away from the final two arguments. Read
their explicit positions in the fake process; do not weaken the late-frame assertion. The
corrected regression and fresh-report suite passed11tests in2.60seconds. Strict typing passed
139sources. Main#96 acceptance independently confirmed936tests per four quality cells,
103Postgres, clean audits and replay with no main rerun.

Prepare the follow-up using seedolist-o8-followup-v2, excluding all12previous exact groups.
Twelve cases from six new groups retain four cases/split, six base/six adversarial and
three eligible/nine required reviews. Freeze evaluator/text/selection bytes before model output.
A draft-rendering helper initially referenced a nonexistent payment_total_minor field; the
actual contract stores payment.total_minor. Correct only the review table from already frozen
files; byte pins remain unchanged. Review all12policy labels against the source facts and
explicit constructed confirmations. They remain AI-provisional, with no independent validation.

### Execute and independently read back

Freeze source at0be72b2 and create a plan with60second single attempts, then retain its canonical
pin separately. The first run stopped during service startup because Docker's Linux engine was
absent; its external directory contains onlyplan.json, no trial/receipt and zero provider calls.
Start the existing Docker Desktop in a hidden window, verify engine health, and resume with the
same plan in a new execution-v2 directory. This does not consume a second call allowance.
The model prompt, policy, case/input bytes and source stayed frozen throughout all attempts.

All108rows completed: Gemini36/36correct, rules36/36correct, always-review27/36correct with
zero eligible completions. Gemini completed9/9eligible and27/27required reviews; every case
passed all three repetitions, and all108duplicate-delivery/cleanup checks passed. There were
no timeouts. All36model calls report complete input/output usage (2790/966tokens); costs remain
unknown. Median worker entry8.225seconds, maximum36.348; median generation after entry4.831.
One startup exceeded the old30second bound, demonstrating local startup variability without
proving the old timeout causes. No host test suite overlapped model capture; Langfuse services
remained active. Recompute the report offline against the separately retained evidence pin
2b8f76ce before publication; every file/receipt and recomputed verdict matched.

The cohort contains only four distinct constructed request texts, repeated across splits.
Report exact source-group separation without calling this an unseen-language holdout. Different
groups, environment and deadline prevent a paired causal improvement claim against the old
pilot. Keep old36trialresults including six timeouts unchanged. Independent labels, baseline/
threshold review, representative validation and H10 release acceptance still gate O8.

Six package pairs built before the model phase. A separate installed workflow environment
matched27Olist resources, with provider SDKs/other verticals absent and six replay calls under
network denial. The first full check was interrupted before pytest completion and left no
live check process; restart it afterward in a separate log instead of claiming it passed.

The restarted complete locked check passed942tests in273.88seconds,139typed sources,
208formatted files and both import contracts. The dependency audit found no known
vulnerabilities. Existing event-loop deprecation and local pytest-cache permission warnings
were non-failing. Publication checks covered18files with12source order identifiers and
configured credentials absent;226relative file links resolved. Source remained unchanged
after the candidate freeze; remaining edits package aggregate evidence and documentation.

## Entry 41 — Separating pilot success from evaluation qualification
**Files touched:** shared evaluation contracts/audit/binding/release CLI, five profile files,
evaluation standards/readiness inventory, release/runbook/study/planning documentation and tests.

### Context

After user merge #97, main418c917 matched the reviewed tree. Main initially failed one
invented fault-matrix assertion on Ubuntu/Python3.12 (941 passes); the unchanged test passed
locally and one failed-job rerun passed942tests. Other matrix jobs/103Postgres and strict
exact-main replay passed. The original failure remains recorded; its cause is unproven.

The user accepted all12proposed Olist labels after viewing results, then asked whether the
pilot criteria were strong enough. They authorized stronger evaluation for all five agents.
Record their acceptance retrospectively against the old evaluator pin; do not backdate it or
rewrite the sealed AI-provisional labels. No additional provider allowance was authorized.

### Before you read on

How can a36/36report still be insufficient? Identify the independent units, the repeated
language templates, who produced the labels and when thresholds were selected. Decide which
facts the program can verify and which require a human/domain review reference.

### Options considered and decision

A common75%review ceiling would encode Olist's constructed9/12review mix into unrelated
domains. A documentation-only checklist would leave `eval-release` able to miss the new
requirements. Add generic strict study/protocol contracts and a fail-closed methodology
audit, with independently owned domain profiles. Compose it with the existing H10 CLI;
preserve the lower-level evidence-gate-only API and historical experiment artifacts.

### How to build it

Define StandardProfile with required Boolean field checks and holdout slices. A separate
StandardProtocol pins profile/dataset/scorer/baseline and freezes reviewed thresholds,
sampling/sample-size rationale and reviewer records before candidate capture. StandardStudy
contains private case inputs, correlated source/template keys, exact trial IDs and domain-
scored results. Revalidate all DTOs at the audit boundary, including model_copy objects.

Normalize input fingerprints with NFKC/casefold/whitespace and reject cross-partition matches.
Reject shared source/parent keys or language-family identifiers across partitions. Merge
overlapping holdout independence-key sets into connected components, so alternate identifiers
and three repetitions do not inflate source-group counts. Check overall and per-slice group
floors, and reuse H9's binomial boundary/Wilson envelope to expose uncertainty in any-failed-
repetition group outcomes. Independence/comparability still require source review.

Build the complete case-by-trial Cartesian schedule before reading results. Missing rows,
unresolved output, absent fields and unknown latency/tokens/cost remain visible blockers.
Report fields, partition/source-kind/slice numerators, appropriate/unnecessary/missed review,
all-repetition case success and paired baseline regressions. Keep critical failures and unsafe
effects as hard blockers. Require qualified blind label review for clinical/policy/meaning
profiles; user acceptance of a previously displayed label cannot satisfy that condition.

In eval-release, read the additional profile/protocol/study with separate canonical pins.
Bind them to the already verified H10 manifest, actual inputs/group IDs/required-review labels,
candidate/baseline/scorer pins, capture interval, schedule and independently produced binary
field scores. Verify token/cost counts against sealed outcomes. A summary from another study
cannot qualify this evidence. Missing inputs produce an explicit blocker, not a permissive
legacy path. Write the audit sidecar exclusively and include its SHA-256 in result.json;
retain all existing H10 approval/freshness/regression gates.

Create five profiles and pin the nine existing public evidence files in an honest readiness
inventory. The inventory is a review of historical limits, not five newly executed studies.
The shared harness imports no vertical. Actual domain-to-H10 field adapters and new reviewed
cohorts remain necessary; do not synthesize fake receipts or silently promote pilot results.

### Verification and remaining work

The first audit/CLI suite passed30tests; expanded binding/release regression passed63tests
in32.59seconds before the final inventory assertion was added. Strict typing passed142sources.
One type-check caught reuse of a Boolean threshold-direction variable as a floating interval
bound; rename the interval bound. Formatting addressed the initial long expressions; no
assertion/deadline was relaxed. Final integrated/hosted checks will follow actual completion.

No provider or Langfuse dataset mutation occurred. Old datasets/captures/holdouts/labels and
results retain byte pins. Production thresholds, representative quality and qualified label
reviews remain open requirements; these new mechanisms do not complete #33 or dependent
release issues. See the evaluation standards and source-study chapters for current behavior.

The first full sweep passed989tests in286.83seconds, but final review identified that
non-autonomous completions needed their own denominator instead of being counted as eligible.
Keep eligibility and required-review as separate case fields and bind both to the H10 labels.
Also apply correctness/field/repetition/latency limits to each required holdout slice, so an
average cannot hide a failing minority slice. Add group-error intervals per slice and reject
duplicate JSON keys before canonical pin comparison. The final stable-source full check runs
after these corrections; the initial sweep is not claimed as final-head acceptance.

Final domain review found a shared-default trap: a mandatory eligible-autonomy denominator
would force the assistive Prior Auth workflow to invent autonomous clinical decisions. Add
an explicit profile exception, preserve undefined unnecessary-review rates and still enforce
qualified labels, criterion/disposition accuracy and missed required review. The other profiles
continue to require eligible holdout cases. The intermediate992test sweep passed280.24seconds;
its process overlapped this last change, so a new stable-source full check is required.

The final stable-source locked check passed993tests in348.84seconds,142typed sources,
213formatted Python files and both import contracts, with lint/lock checks passing. The
existing event-loop deprecation and local pytest-cache permission warnings are non-failing.
Sixwheel/sdistpairs built; the locked dependency audit found no known vulnerabilities.
Separate installed checks matched60harness resources and27Olist resources, refused missing
private audit inputs and consumed six replay calls with networking disabled, no provider SDKs
and zero provider calls. Publication checks found configured credentials and12source order IDs
absent in40files across the checked history;212relative links resolve. All nine historical
aggregate files retain their pinned bytes. No SQL/schema/lock/dependency changed. Hosted
final-head matrix/Postgres acceptance follows after actual completion on the PR.

Before publishing, compare inventory bytes with Git blobs: several Windows files haveCRLF,
while Linux checkout blobs useLF. Pin the historical public text inventory afterCRLF-to-LF
normalization and make the test use the same explicit rule. Private raw capture/evaluator
pins remain exact bytes and unchanged. This is a portability correction to the new inventory
check, not a rewrite of source/evidence. Run the affected audit/binding/CLI tests again and
require the final hosted Linux/Windows matrix; the production Python source is unchanged.

The portability-corrected audit/binding/CLI suite passed56tests in31.14seconds; Ruff/format
passed and all nine normalized inventory hashes match the actual committed Git blobs.

Hosted initial40054265366 flagged two generic-api-key matches at the Prior Auth public-report
checksum in readiness.json:line85, one per implementation/portability commit. Recompute the
rawWindows report hash and theLF-normalized Git-blob hash to prove each reported value is an
artifact digest, not credentials. Follow the existing repository convention: add only the
two exact commit/file/rule/line fingerprints to.gitleaksignore, retain the scanner/rules and
record the initial failure. The corrected final-head hosted scan must pass independently.

## Entry 42 — Observing domain fields and controlled recovery
**Files touched:** `field_evaluation.py`, `fresh_execution.py`, `fresh_release.py`, `cohort_draft.py` in the Olist package.

### Context
After #98, a passing shared standard still needs actual domain observations. The old collector
saved outcome/message/receipt, but omitted the workflow reason. Duplicate delivery was observed;
an interruption after committing was not. The user authorized preparation of a stronger draft,
with no provider calls. Preserve the old evidence and do not fill its missing reason from labels.

### Before you read on
How can you distinguish a correct refund with the wrong reason from a fully correct trial,
and distinguish duplicate delivery from reopening after an interruption?

### Options considered
Recomputing the runtime policy for labels would make the scorer agree with its own implementation.
Instead, compare actual fields against evaluator-only literal labels and independently construct
expected ledger/order/budget state. Keep the historical aggregate report unchanged. Add separate
field results so absent older observations remain unknown.

### How to build it
Add optional workflow_result and recovery_observation fields to FreshRow. Verify the saved result
matches the independently collected response. In score_fields, compare parsed intent/partial
amount, actual action/receipt amount, actual reason and fixed truthful message separately. Reuse
the independent expected-state constructor for orders, ledger and original run budget. An unknown
field makes qualification unresolved; it cannot become a success by copying the expected label.

At the business after_commit hook raise a dedicated evaluator exception, collect committed state,
close the checkpoint connection, reopen durable components and resume with a planner that refuses
a second invocation. Compare committed, resumed and final state. Then perform the ordinary duplicate
delivery check separately. This is a controlled exception and connection reopen, not an OS process
kill or a general infrastructure-failure test. Required recovery without this observation is unknown.

Prepare six new source groups by seeded selection after excluding every prior cohort group. Keep
two related variants per group and all language-family metadata in the same partition. Construct
payment totals explicitly as 99.99, 100.00 or 100.01 SIM; they are fictional, not converted source
currency. Save inputs separately from provisional evaluator labels and fault/slice metadata. The
12-case review draft has two holdout groups and cannot meet representative release evidence alone.
No existing capture/holdout is reused and no model or Langfuse mutation is part of preparation.

### Verification in progress
The initial field tests passed; the combined check also hit a Windows temporary-folder permission
error because TEMP had not been set to the external D drive test cache. Rerun with the established
TEMP/TMP configuration. A targeted mypy invocation omitted the workspace harness source and reported
untyped imports; the repository-wide invocation resolves those imports and found one real missing
Literal annotation on StandardRow.outcome. Fix that annotation and require the full repository check.
Actual final results and SQL acceptance will be recorded after running them.

The first draft's exported inputs included structured source facts and intended intent. Before
any dispatch, narrow that export to opaque case_id/text only and retain the initial unreviewed
v1 folder. Prepare a separate v2 draft with its own pins; neither has model output. Add a
regression that checks the written provider projection, not only the in-memory case constructor.
The focused 17 tests passed after using the external D-drive cache with the required filesystem
permission. Docker started successfully; actual SQL recovery checks are running. Because the
projection correction came after the first full sweep started, require a stable-source full
sweep again before opening the PR; do not call the overlapping sweep final acceptance.

The overlapping full sweep finished with999passes and one failure in823.27seconds. The failed
CLI test used an invented study fixed at2026-10-24UTC but read the real host clock before that
instant. Its sole blocker was protocol_or_capture_time_order: production correctly refused a
future capture. Pin the CLI module's clock in that test to the same explicit invented NOW+3s
used by the direct audit fixtures. Do not relax production time ordering or rewrite evidence.
The draft/scorer regression suite passed9tests; real SQL collector checks passed6tests in
133.40seconds. A complete final SQL suite and stable-source offline sweep still follow.

The complete real Postgres suite passed105tests in1204.18seconds, including both new controlled
recovery cases. The separately installed wheel matched29Olist resources, imported both new
modules with provider SDKs/other verticals absent and replayed six invented calls with networking
disabled. All six wheel/sdist pairs built and the locked dependency audit found no known
vulnerabilities. Offline read-back verified the old108row capture inventory/report unchanged;
new draft pins and the source DB pin match. Publication checks found24selected source order IDs
and configured credentials absent in13publishable files. Selected new customer groups are
also distinct and disjoint from prior cohorts. No provider dispatch or live dataset mutation.
The user requested AI propositions before their review; retain that assistance provenance and
do not infer blind annotation or label acceptance. Final offline/hosted acceptance is pending.

The stable-source offline sweep finished1001passes plus one existing recording-test failure in
1025.16seconds. Its invented capture had three model-stage timeout/Run-deadline-exhausted
results, zero calls/receipts and no trial errors; read_evidence correctly refused missing
contiguous dispatch receipts. The scheduled deadline was90seconds, while the capture's UTC
wall-clock interval was41261.176993seconds (fixture clock to capture start0.01175seconds).
That interval exceeds the complete monotonic test-run duration and is consistent with a wall
clock discontinuity; its underlying cause is not proven. Rerun the entire recording regression
module unchanged, keep all bounds/assertions and retain this failure. Require the final hosted
full matrix as independent acceptance; do not report this local full command as passing.

The complete recording regression module then passed21tests unchanged in131.35seconds. Keep
the failed full-run result and its clock discrepancy visible; this rerun does not retroactively
make that full command pass. Focused standards/domain regressions passed47tests in17.26seconds;
strict typing passed144sources, lint/format/import/lock checks passed. The review PR must obtain
its final full hosted OS/Python matrix and105Postgres checks before acceptance. There are no
production policy, schema, dependency or deadline changes. New labels remain AI-provisional.

## Entry 43 — Serializing owned process bookkeeping
**Files touched:** `process_control.py`, `trial_runner.py`, `isolated_transport.py`, process regression tests.

### Context
After the first all-green PR99 run, a body-edit-triggered run40088038931 failed Ubuntu3.12
in test_faults_require_explicit_factory_composition: one worker_cleanup_error aborted the
remaining rows. The gate then failed; the other quality cells and Postgres passed. Earlier
fault-matrix cleanup failures were retained as cause-unproven. The user asked us to fix checks.

### Before you read on
Why can starting a different process cause a joined worker to appear alive? Read CPython's
BaseProcess.start -> _cleanup -> other_child._popen.poll path before assuming each Process
object is touched only by its owner thread.

### Options and construction
Do not rerun until green or accept worker_cleanup_error as an expected composition failure.
CPython issue130895 documents concurrent waitpid/poll reaping races, including Linux spawn.
Our ThreadPoolExecutor permits this exact concurrent access: one thread starts a child while
another joins/checks a previous one. This is a source-confirmed race exposure, not proof of
the precise interleaving in the failed hosted worker (those logs lack scheduling traces).

Add one shared process-control lock used by both trial and SDK worker paths. Wrap start,
nonblocking join, is_alive, exitcode, terminate, kill and close. Wait on the public process
sentinel outside that lock, then join(0) inside it. Holding the lock across the full join
would serialize trials and prevent another coordinator from terminating its worker; avoid it.
Keep all existing execution and cleanup limits and fail-closed state preservation unchanged.
The lock protects harness-owned calls, not unrelated third-party Process operations. Starting
processes remains a short serialized control operation; no hard OS scheduling guarantee is made.

Add a deterministic regression using the actual CPython POSIX poll implementation with a
staged fake waitpid: pause after reaping but before assigning returncode, then attempt another
start's cleanup poll. It must wait until the status is recorded. Separately prove a waiting
worker does not block another start, and retain actual concurrent spawn/fault/cleanup tests.
Actual verification results will follow; do not claim the hosted cause fully proven.

The first regression import assumed POSIX WNOHANG exists on Windows and failed collection.
Load CPython's POSIX poll only inside the test after stubbing that constant, and restore OS
functions after all test threads join. The test now includes an unprotected control that must
reproduce the false-alive result, not just a successful guarded path. Initial typing passed
145sources. Real worker/fault/control regression results remain pending.

The user explicitly approved all12strong-draft-v2 labels only. Save an exclusive private
acceptance sidecar bound to evaluator SHA8a1ea8d2..., recording review of AI propositions and
no PR/merge/provider/baseline/threshold/release approval. Do not rewrite the original AI
provenance or claim independent blind annotation.

The corrected deterministic/real-worker suite passed156tests in198.52seconds. Five actual
Postgres worker tests passed in149.33seconds, including restricted logins, committed-state
inspection after reaping and timeout cleanup. All six package pairs built, the locked audit
found no known vulnerabilities, and publication checks found configured keys/24source IDs
absent across19publishable files. Frozen source/evaluator/input/metadata pins remain unchanged.
Installed verification matched61harness resource bytes with no provider SDKs and networking
disabled, replaying six synthetic calls with zero provider calls. The stable full suite and
new-head hosted matrix are still pending; preserve the original failed run in the PR record.

The stable-source complete locked check passed1005tests in571.85seconds,145typed sources,
219formatted Python files, both import contracts, lint and lock validation. The two existing
event-loop/cache warnings are non-failing. Installed Olist also matched29resource bytes;
both installed probes replayed six synthetic calls with networking disabled/zero provider
calls. No assertion, execution/cleanup limit, SQL schema or dependency changed. Publish the
fix to the existing PR and require the new commit's full hosted matrix/Postgres/secret/audit
checks; use comments for final acceptance so a body edit does not trigger an unchecked new run.

## Entry 44 — Waiting for exit status after sentinel readiness
**Files touched:** `process_control.py`, process-control and fault-matrix regression tests.

### Context
User merged #99 as c1fc040. Its main run40106644821 failed the spawned fault matrix on
Ubuntu/Python3.13 (1004passed/1failed); the other three quality cells and Postgres passed.
The truncated assertion omitted the failing row/error. Do not describe main as accepted or
retry that run until green. This interrupts the planned Olist H10 adapter work under #33.

### Before you read on
Does a readable multiprocessing sentinel prove waitpid(WNOHANG) can already return an exit
status? Trace POSIX Popen.wait and the spawn pipe lifetime before choosing a blocking join.

### Why and construction
Entry43's wrapper deliberately waits outside the shared control lock and calls join(0)
inside it. CPython's POSIX Popen.wait uses a nonblocking poll for timeout0, but a blocking
poll after a positive-timeout sentinel wait. Our wrapper changed that behavior: EOF followed
by an empty poll immediately returned to the caller, which then treated is_alive as timeout.
Pipe closure and kernel exit-status readiness need not be simultaneous. This is a separate
source-confirmed exposure; the main job's truncated log cannot prove its exact failure cause.

Keep the shared lock and original timeout. Compute one monotonic end, wait outside the lock,
then join(0) and inspect exitcode inside it. If still running and time remains, pause at most
1ms outside the lock and repeat. An already-readable sentinel must not spin. A zero timeout
stays one nonblocking poll. Do not use blocking waitpid inside the global lock: a child can
close its pipe and keep running, starving other workers' termination/cleanup.

Test with an always-ready sentinel and a fake monotonic clock: status appears after3ms or
never appears before the5ms bound. Verify both delayed success and bounded non-exit, plus
join(0) never waits/sleeps. Preserve the cross-thread reaping control and concurrent-start
tests. Add compact case/trial/error/category tuples to the invented fault test's assertion
so another failure supplies evidence without printing source text, secrets or full reports.
Actual focused/full/hosted results are pending. Execution and cleanup limits are unchanged;
unknown historical causes remain unknown. No provider call or release approval is implied.

Primary source inspected: CPython3.13 `Lib/multiprocessing/popen_fork.py` (wait/poll), and
`popen_spawn_posix.py` (pipe sentinel), in the official python/cpython repository.

Focused real-worker/deterministic regression suite passed159tests in209.37seconds. The
actual restricted Postgres worker module passed5tests in169.24seconds, including committed
state retained through timeout and cleanup. Types passed145sources. All six wheel/sdist
pairs built; locked audit found no known vulnerabilities. Installed harness matched61resource
bytes with provider SDKs absent, networking disabled and six replay calls/zero provider calls.
The full diff publication scan found configured credentials/24source identifiers absent;
source and stronger-draft pins remain unchanged. Changed Markdown has112resolving relative
links and changed JSON parses. Complete locked suite and final hosted matrix remain pending.

A separate negative control loaded the unchanged main wrapper with `git show origin/main:...`
into an isolated Python namespace, substituted an always-ready sentinel and a child whose
nonblocking join never produces exit status. Main returned after one poll while exitcode
was stillNone despite a five-second allowance. This verifies the exposure against reviewed
bytes without modifying tracked sources or claiming that child existed in the failed CI run.

Complete locked check passed1008tests in664.34seconds,145typed sources,219formatted files,
lint, both import contracts and lock validation. Existing event-loop/cache warnings are
non-failing. Subsequent source edits only clarified a comment; wheel/installed-byte checks
were refreshed for those exact bytes. No behavior, deadline, dependency or SQL change was
made after the focused suite. Publish a separate repair PR, run exact-head strict replay
and require the complete hosted matrix/Postgres/audit/secret/metadata gate. Hosted results
will be recorded in comments after actual completion, without a body edit triggering a new run.

## Entry 45 — Recording Olist trials through H10
**Files touched:** Olist H10 manifest/environment/runtime adapters, independent field scorer, tests.

### Context
The user merged #100 as 70abcdb. Continue #33: the domain field projection from #99 is not
an H10 journal. Old private captures must not be converted into newly dispatched evidence.
The stronger twelve labels were accepted as AI-assisted propositions, not blind annotation.
No additional provider calls or release have been authorized.

### Before you read on
How can the same workflow use H10's owned receipt gateway while keeping expected decisions
out of agent inputs and database administrator credentials out of spawned workers?

### Chosen construction
Encode the already reviewed PolicyCase as evaluator-only hidden state in a CaseManifest;
project only its unchanged request text into AgentInput. Preserve source group, original
split and label provenance. H10 only supports development/holdout: regression stays explicitly
marked in private metadata and maps to development for this adapter, never to holdout.

The parent environment creates and enrolls a fresh SIM database, records its before-state,
and passes a restricted TrialDatabaseAccess plus grant to the worker. The runtime composition
receives no expected labels. Agent/scorer share a private observation slot for the actual
planner/result and controlled duplicate/recovery observations. The scorer independently
reads final SQL state and uses the existing independent field/state oracle against labels.
Parent-owned cleanup stays in H10, after worker reaping; it cannot be claimed by an agent.

Use record_candidate directly for live receipts/journal sealing. Expose no old-row import
or automatic provider configuration. Mock execution will exercise actual spawned workers,
restricted SQL, repeated dispatch, read-back/tamper checks and missing-cost rejection without
contacting Gemini. Production studies still need representative/independent review, approved
baselines/thresholds, complete accounting and latency evidence. Controlled after-commit
exception/reopen is not an OS process kill and does not replace H7 fault-plan evidence.
Tests, full checks and hosted acceptance remain pending while this construction is implemented.

Main #100 run 40109099337 passed all nine applicable jobs (metadata intentionally skipped).
Actual logs show 1,008 tests in each quality cell, 105 Postgres checks, 145 typed sources
and twelve package artifacts per cell. Tree 1012dc38 matches the reviewed head. The first
adapter unit/field suite passed 18 checks; typing passed 150 source files. SQL execution is
under verification; no live provider has been contacted.

During source review, retaining only field scores proved insufficient: disposable SQL is
removed after the worker, so a later evaluator could not recompute the state verdict. Add
private observation sidecars. The trusted scorer independently rereads final SQL, saves the
canonical FieldCapture exclusively, and puts its SHA-256 in each ScoreResult's state evidence.
H10 already seals the whole batch, binding those references to its manifest. A domain reader
must first verify H10 receipts/usage/pins, then check exact sidecar inventory/digests and
recompute every domain field and shared result. Do not manufacture receipts or infer missing
costs. This extends the initial implementation; rerun relevant SQL capture tests afterward.

The first five SQL/H10 cases passed in 373.92 seconds before sidecars were added. After
the extension, all five passed again in 443.76 seconds: fifteen new mock dispatches across
refund, required review, controlled recovery, failed response and unknown-cost cases.
The shared reader checks actual receipts and usage; the domain reader recomputes all
fields after database cleanup. Changed/missing/extra observation files fail without another
dispatch. Redelivery now saves its before-state and actual result; a boolean alone cannot
earn duplicate credit. Final focused suite passed 23 checks; strict typing passed 151 sources.

All six package pairs built and the locked audit found no known vulnerabilities. Installed
verification matched 61 harness and 35 Olist resources, validated composition/source pins
under network denial with provider SDKs/other verticals absent, and replayed six recorded
calls with zero provider calls. Publication scanning covered 17 files with configured keys
and 24 source identifiers absent; source/draft pins remain unchanged. The documentation
check found 118 resolving relative links and valid JSON. Complete locked suite and hosted
matrix remain pending. No original/new cohort was dispatched to a provider.

The complete locked check passed 1,025 tests in 695.45 seconds, 151 typed sources,
228 formatted Python files, lint, both import contracts and lock validation. The existing
event-loop/cache warnings remain non-failing. Historical sealed Olist inventory/report
recomputed unchanged with release still false and zero provider calls. Publish this
17-file adapter batch for review, require final hosted matrix/full Postgres/audits/secret
and metadata checks, and record actual acceptance in comments. #33 remains in progress;
this is not an approved final study, a new provider budget or production release.
## Entry 46 — Sealing parent-measured trial latency
**Files touched:** shared trial contracts/runner, methodology binding, timing regression tests.

### Context
User merged #101 and selected #33. Main 211defc has the identical reviewed tree and run
40114834940 completed successfully. The Olist adapter records real workflow/state evidence,
but methodology latency was only a declaration bounded below by dispatch wall-clock span.
That cannot establish total trial duration. No new provider budget is authorized.

### Before you read on
Where should a timer live so it survives a worker crash and includes database cleanup?
How can adding it avoid changing the canonical hashes of historical journals?

### Options, why and construction
A worker timer misses spawn/startup, parent setup and cleanup, and may disappear on crash.
A new timing sidecar would need a second inventory/pin mechanism. Put a versioned TrialTiming
on the parent-owned terminal TrialRow instead; its batch digest already belongs to H10's
sealed manifest. An absent timing field is omitted from serialization so old canonical
row/batch bytes stay unchanged. Missing historical timing stays unknown, never zero.

In _coordinate take monotonic boundaries at entry, after setup, after isolated execution
and after cleanup. Store nonnegative finite setup/execution/cleanup seconds; their sum is
the measured latency. Execution includes spawn, workflow, scoring and owned worker reaping.
Setup includes the abort check; already-aborted tasks keep zero execution/cleanup with an
explicit error. Failed setup, timeout, crash, and failed cleanup retain parent measurements.
Do not call this user-facing latency: executor queueing, journal writing and evidence sealing
are outside the interval. The child cannot supply the measurement in its result frame.

Bind StandardRow.elapsed_seconds exactly to the sealed sum, or require None when timing is
absent. Retain the conservative dispatch-span check too. A larger invented duration must
fail just as a smaller one does. Trusted parent code/local pins provide consistency, not
authenticated clock attestation. This shared mechanism applies to all verticals using H6/H10.

### Verification in progress
Use deterministic parent-clock tests to distinguish each phase, then actual spawned success,
crash/timeout/setup/cleanup/abort paths. Mutate the saved timing to prove batch-pin rejection.
Recompute historical private evidence unchanged. Full checks, actual Olist SQL recording,
installed-package proof and hosted CI remain pending at this construction point.

The focused parent-clock/spawn/binding suite passed 78 checks in 90.96 seconds; strict
typing passed 151 sources. All six package pairs built, and the locked dependency audit
found no known vulnerabilities. Installed proof matched 61 harness/35 Olist resources,
validated frozen composition pins with network denied and provider SDKs/other verticals
absent, then replayed six calls with zero provider calls. Historical private inventory/report
recomputed unchanged with release false. Publication scan found all configured credentials
and 24 source identifiers absent; database/draft pins and disjoint customer groups verified.
Full locked tests and relevant SQL capture verification remain pending.

Complete locked check passed 1,042 tests in 619.23 seconds, 151 typed sources, 228
formatted files, lint, both import contracts and lock validation. Existing event-loop/cache
warnings are non-failing. No source correction or failure rerun was needed. The installed
TrialTiming JSON roundtrip also passed, with legacy None omitted. Two relevant real SQL/H10
scenarios (refund and typed model failure) are now under verification; no provider is used.

Both relevant SQL/H10 scenarios passed in 159.78 seconds (three other unchanged scenarios
were deselected locally). Six new mock dispatches exercised refund and typed failed response;
all six rows retain measured setup/execution/cleanup after owned database/role removal and
verified receipt/state read-back. These are mechanism checks, not fresh Gemini observations.
Publish for review after clean-head replay/publication checks; require the hosted full matrix
and all 110 database checks. #33 stays open for full crash/restart evidence, complete study
projection, independent/representative review, approved baselines/limits, cost provenance and
a separately authorized final provider study. No provider trial was rerun or dispatched.

### Clock-resolution failure found by hosted CI
Run40116936759 passed three quality cells1042tests each, all110Postgres checks, both audits,
metadata and secret scan. Windows/Python3.12 failed the two new positive-duration assertions
for immediate setup/pickle failures (1040passed/2failed). Keep that failed run; do not retry it.
The timer needs a short-duration clock: use time.perf_counter for all four parent boundaries
and the early abort boundary, retaining the same finite monotonic duration contract. The
existing worker deadline clock remains unchanged. Python3.13 uses the same underlying
clock for monotonic/perf_counter, while older Windows versions can differ.
Strengthen the deterministic test by freezing time.monotonic at zero while advancing only
perf_counter. This catches accidental use of the coarse clock without relaxing positive
measurement assertions, inserting sleeps or replacing zero with fabricated epsilon.
The exact hosted clock implementation was not captured, so its resolution remains an
inference from the failure and Python clock behavior; no unsupported exact tick is claimed.
Focused/final checks and a new synchronized-head hosted run must verify this correction.

Clock correction verification: strengthened focused suite78passed99.15s; lint and151typed
sources passed. Six package pairs rebuilt; corrected installed61harness/35Olistresource
bytes/composition pins matched with network denied and zero-provider6callreplay. The prior
full local1042test/2SQL pass is retained as initial-head evidence; final synchronized-head
CI must rerun the complete matrix/110DB checks. No unchanged-head retry or provider call.

## Entry 47 — Preparing three release evaluators together
**Files touched:** shared study assembly/population accounting, Olist study wrapper, CFPB release report, Revenue extraction/billing reports and tests.

### Context
The user confirmed the merge was #102 (not nonexistent #103), then explicitly authorized
preparation for #33/#38/#45 together while downstream release acceptance stays blocked by
#33. Merged main b915f1b has reviewed tree b7652d2. Its hosted checks are being verified.
No new provider budget, source sampling, labels or release authorization is inferred.

### Before you read on
How do you report three repeated trials when one is absent without silently changing the
population, and how do you assemble a study without authoring reviews or replacing evidence?

### Decisions and construction
Keep H10 recording distinct from methodology projection. Build StandardRows from already
verified candidate/baseline journals: use actual domain scores, assessed outcome, observed
usage and sealed parent timing. Require supplied StandardCases and protocol pins, then run
the existing binding check. Do not invent slice/family/reviewer metadata, limits or baseline
receipts. Olist's wrapper must independently read its saved state observations and enforce
original development/regression splits retained in private labels.

For CFPB, score the actual Decision rather than reconstructing a route from cached cheap/
strong predictions. Freeze case/trial inventories, reject duplicate/unexpected identities,
count missing/failed/invalid rows in all denominators, report product/pair macro-F1 and risk
review recall separately from operational failures. Consumer-selected reference categories
and AI risk labels retain their original limits. Report source kinds and splits separately;
no privacy/durable-review or independent-annotation credit comes from classification alone.

For Revenue, original-contract spans and simulated billing remain separate reports and
populations. Exact literal span precision/recall against published references is not legal
meaning or numeric-term validation. Match submitted citations to unchanged input before
scoring. For billing, compare literal independently supplied expectations, never call the
production reconciler to create expected answers. Report benign false alarms, case-weighted
and SIM-amount-weighted discrepancy recall with missing outcomes in their denominators.
These functions measure supplied observations; they do not manufacture H10 receipts or
assert authorization/recovery/state gates were tested.

### Verification in progress
Use invented inputs to exercise wrong and missing outputs, abstention, forged spans,
wrong identities, partial classifications and imbalanced SIM amounts. A successful report
must keep release_allowed false and identify missing release evidence. Full checks,
installed-package proofs, exact-head replay and hosted acceptance follow actual execution.

Focused evaluator checks passed27tests10.66s after adding Olist preflight coverage; strict
typing passed156sources. Review found an additional reporting risk: an invalid classifier
route must not hide a claimed auto-classification on a required-review case. Preserve both
claimed and verified classification counts, count missed review even for invalid claims,
and put all classified claims in the selective-error denominator. Sim billing similarly
counts unsupported autonomous claims as missed review rather than hiding them as invalid.
The first local SQL check stopped during Docker setup with zero worker/model dispatches: no
engine pipe or Docker Desktop processes existed. Start Desktop without stopping any other
containers; retain this setup failure separately from the actual SQL acceptance result.
The full locked non-database suite is now running. Main#102run40134019972 completed success
on attempt1; actual Windows3.12 log1042tests/151types/12artifacts/zero-provider replay and
Postgres110tests152.05s verified. Merged tree b7652d2 matches reviewed cb86027.

After Desktop startup, the Olist refund SQL/H10/read-back/projection check passed in
201.84seconds (one case, four unchanged scenarios deselected locally). Three new mock
trials preserve usage/fields/parent timing; saved-state observations reverify after owned
database cleanup. The same mock artifact in both baseline/candidate slots tests projection,
not independent model comparison. Audit remains blocked on missing reviews/limits/coverage.
Installed proof matched63harness/36Olist/24CFPB/26Revenue resources; all four APIs imported
without google/langfuse/pydantic_ai SDKs or unrelated verticals, under network denial. A
missing extraction trial yields exactly0.5spanrecall; replay consumes6recordings with0provider.
Final field-count additions make priority/ambiguity, abstention and billing amount/reason
visible separately; final focused checks and package rebuild verify these small additions.
The first full local suite began before these final count-only additions; retain its actual
result as such, with final exact-head hosted checks required after the focused verification.

Final focused suite passed27checks33.09seconds, with156typed sources, lint/format and
rebuilt six package pairs. Documentation flags a design limit found during review: the
Olist one-process convenience wrapper requires both artifacts to match installed source
inventories. Mixed-code baseline/candidate artifacts need separate frozen read-back
environments and a reviewed interchange workflow, not recomputation of old code in the new
wheel. The shared projector accepts already verified objects but does not replace domain
readers. No claim of complete cross-version comparison is made. The full suite is still
running; final installed wheel proof and exact-head hosted acceptance follow.

Local verification completed: full locked check1,069tests718.09seconds,156typed sources,
236formatted Python files plus lint/import/lock checks. That run began before final
count-only report additions; final focused27tests33.09seconds, lint/types/format and rebuilt
packages verify those additions. Olist real SQL/H10/projection1passed201.84seconds,4unchanged
scenarios deselected locally; initial Docker-closed setup failure retained (zero dispatches).
Final installed proof matched63harness/36Olist/24CFPB/26Revenue resources, all four APIs,
provider SDKs/unrelated verticals absent, networking denied, six replay calls/zero provider.
Six package pairs built; locked audit clean. Historical inventory/report/source/draft pins
unchanged; publication17files excludes configured credentials and24source identifiers.
124relative documentation links resolve and changed JSON parses. Require final committed-head
hosted full matrix/110Postgres checks; no completed release study is inferred.

## Entry 48 — Recording domain dispatch and real process-crash evidence
**Files touched:** shared mock domain recorder/read-back, CFPB and Revenue extraction adapters,
Olist process-crash collector, focused and required SQL tests.

### Context
User merged #103 and asked to proceed. The authorized #33/#38/#45 preparation batch continues;
no new provider budget or release approval. Merge fb9bfd0 has reviewed tree9c181de; main CI
is being verified. #103's reports still consume supplied observations, while Olist's H10
recovery is a controlled exception/reopen rather than process death.

### Decisions before construction
For CFPB/Revenue, connect actual typed application calls to the shared H10 receipt gateway,
with a mock-only composition for this preparation step. Agent input contains only the closed
public projection. Scorers bind the complete shared result to private saved observations;
H10 seals their digests in score references, and the reader recomputes them after execution.
Freeze complete harness/domain Python/SQL inventories. Never load credentials or import old
outputs as fresh execution. Mock JSON responses have explicitly invented zero token/cost
usage and remain origin=mock; unknown-cost mock variants must still fail H10 read-back.
Missing privacy/durable-review/numeric-term/business-state evidence must emit scorer errors,
not default True. These partial adapters cannot qualify a complete domain release.

For Olist, add an explicitly operator-selected offline SIM drill in the parent, outside
H10's daemon worker. An owned spawned process hard-exits only at the after-commit callback;
the parent observes exit code/boundary, independently reads SQL, starts a new workflow/store/
checkpointer with NoSecondDispatch, and reads all SQL again after restart and redelivery.
Save private before/committed/resumed/duplicate states and actual result. Recompute exact
permitted state against supplied private labels after disposable DB cleanup. This drill has
no model, receipt gateway or quality claim, and cannot be relabeled as fresh H10 evidence.
Keep timeout/start/crash/cleanup failures visible; never release state under a live worker.

### Verification in progress
Exercise actual spawned H10 mock calls and receipt nonces, changed/missing/extra sidecars,
failed calls/unknown cost and unsupported field errors. For Olist use real restricted SQL and
process death, then mutate saved state/exit/boundary evidence. Full checks and installed/hosted
acceptance follow actual execution. Keep all historical cohorts/holdouts/labels unchanged.

### Main CI timing-test failure
Main40141937105 failed Windows/Python3.12 at the new timing-tamper test (1068passed/1failed).
The other three quality jobs, Postgres, audits and secret scan passed; keep the failed run.
The test changed all parent phases to0 and then re-sealed the changed batch. The assembler
correctly uses the sealed duration, so rejection depended solely on a real UTC receipt span
being positive. A fast receipt can have identical timestamps on Windows. This is an invalid
test assumption, not evidence that perf_counter regressed. Preserve the original batch pin
when mutating timing; the existing exact-binding deterministic tests cover altered study
claims. Do not relax production checks, add sleeps/epsilon, or retry unchanged main. The
precise receipt timestamp values were not logged; the zero-span explanation is inferred
from the only passing branch in the inspected binding code.

### Construction feedback
The first adapter run exposed an omitted required example-context argument; fixing the synthetic fixture yielded14passed58.98seconds. SQL setup first failed with Docker closed. After starting Desktop, the test caught an invalid zero-valued Budget: the shared schema requires positive calls/tokens. Preserve that shared contract. The operator drill requires explicit offline mode and receives no model/gateway; the context budget is unused, not evidence of permitted provider spending. Corrected SQL acceptance is running. Six package pairs build and the locked audit is clean. Preliminary installed proof matches64/37/25/27 resources and offline replay6calls/zero-provider; rebuild Olist after the budget correction before final acceptance.


Corrected real SQL drill:2passed113.33seconds. The parent observed exit23, verified exact committed/restarted/redelivered state, original operation receipt and duplicate result, then recomputed saved evidence after disposable DB deletion. Negative changes to boundary, exit, state, result, errors and external byte pin fail. Fourteen mock adapter tests pass; lint and160typed sources pass. Full regression remains running; no unexecuted result is reported as accepted.

## Entry 49 — Independent durable-state evidence across three release issues
**Files touched:** Olist crash evidence, CFPB durable queue evidence, Revenue SIM ledger evidence, tests and study walkthrough.

### Context
User merged #104 as437e762, treef7a0194 identical to reviewed390cc71. Main CI is still running. All remaining implementation issues depend on #33, so continue the explicitly authorized #33/#38/#45 preparation rather than opening gated work. #104's partial stateless H10 adapters deliberately have missing durability/state fields. Existing review labels, provider cap and release gates do not change.

### Before you read on
How can a scorer distinguish a durable queue/ledger effect from an application saying it succeeded? Sketch the before/after data it must read independently and what must remain unchanged.

### Decision and construction plan
Keep mechanism evidence separate from model-quality receipts. Add read-only, repeatable-read SQL collectors and independent exact-delta checks for one CFPB review command and one approved Revenue SIM invoice correction. Bind saved canonical bytes to an externally retained pin and supplied expectations; do not call enqueue/apply/reconcile to construct expected state. Keep source text, sessions, database credentials and administrator access out of artifacts. Scope claims explicitly: scoped rows do not prove tenant-wide privacy or a full safety profile.

Extend the Olist collector to hard-exit before commit as well as after commit. Preserve the v1 canonical representation for existing after-commit artifacts; a new version distinguishes rollback observation from committed state. Before-commit restart must charge the restart run and return that run's original receipt; the independent state oracle must use the correct run identity. Repeated delivery must preserve it without a second planner dispatch.

### Verification plan
Use only invented fixtures in disposable Postgres databases. After actual writes/reconstruction, collect independent SQL snapshots, save evidence, then recompute without a database. Mutate command, expected state, reviewer, receipt and external pins to show false claims fail. Run focused/unit/type/import checks, package/installed verification and full hosted regression before review submission. No model call or release decision is authorized by this work.

### Initial feedback
Five shared artifact mutation tests pass. First SQL collection run stopped before DB setup because Ruff removed aliased fixture imports as unused; register fixture objects explicitly at module scope. The corrected CFPB and Revenue positive/mutation SQL scenarios pass; Olist boundary scenarios are still running. Strict types pass163sources. V1 compatibility uses the same exclude-if-absent pattern already used for historical trial timing, so old canonical pins are not rewritten. No observed quality or release success is inferred.

Required real SQL batch completed:5passed118.64seconds. It includes the new CFPB queue/Revenue invoice cases, both Olist crash boundaries and fresh-mode rejection. Before-commit rollback equals original state; restarted receipt/budget uses the restart run, then duplicate delivery preserves it. Missing/wrong queue rows, unrelated account changes, mismatched receipt identities and mismatched indexed SQL/document versions are rejected. Nine artifact/version unit cases are included in the focused run still in progress; final full acceptance will use the exact-tree hosted matrix. Local static checks cover163typed sources,249formatted files and both import boundaries; lock is unchanged.

Focused final run:23passed169.68seconds (nine new artifact/version cases and14existing dispatch cases). All six wheel/archive pairs built. Installed resource verification matches65harness/37Olist/26CFPB/28Revenue bytes; new APIs import with networking denied and provider SDKs absent; replay consumes6calls with0provider. Historical inventory/report and source/draft pins remain unchanged. Full regression acceptance is reserved for the committed-head hosted matrix; dependency audit is still running locally.

## Entry 50 — Deterministic baselines without invented dispatch receipts
**Files touched:** separate shared baseline recording/read-back, Olist/CFPB/Revenue baseline compositions and comparison binding.

### Context
User merged #105 as1f7c3ef with the reviewed tree1f16049; main CI is running. Continue authorized #33/#38/#45 preparation. Inspection found the shared study assembler only accepts H10 evidence, whose reader requires at least one actual dispatch per trial. A real rules/always-review/abstain baseline cannot satisfy that requirement without fabricating a model call.

### Before you read on
How should a deterministic comparator prove it ran, without pretending it called a provider or weakening the candidate's freshness requirement?

### Decision before implementation
Add a distinct deterministic-baseline manifest and reader. Run actual isolated H6 trials with the same population/scorers/environment and parent timing. Replace the supplied gateway with a denying gateway, remember any attempted use even if the algorithm catches the exception, and require exact zero-call/token/cost result usage. Pin full candidate/source/batch/algorithm identities and retain domain observations. The trusted factory remains trusted code, not an OS network sandbox. Fresh candidate validation/dispatch receipt requirements remain unchanged.

Use existing Olist grammar-aware RulesPlanner and always-review behavior, actual CFPB always-review typed output, and Revenue's declared original-span abstention baseline. No hidden labels enter algorithm inputs. Teach the shared methodology projection to accept the separately verified deterministic comparator only in the baseline position. Keep H10 release promotion unchanged until its reviewed approval format explicitly supports this evidence; no baseline is auto-approved.

### Verification plan
Execute real spawned zero-call baselines, reject attempted gateway use (including caught errors), forged usage/source/algorithm/pins and changed observations. Run actual Olist SQL workflow/scorer/duplicate/recovery paths. Verify fresh model captures still reject missing receipts and cannot use deterministic evidence as candidate. Freeze source, build/install, run full hosted checks, and retain all prior labels/holdouts/experiments.

### Early verification feedback
Strict types pass165sources. First19focused tests pass after correcting the caught-call test fixture: its initial ModelRequest lacked required parameters, so validation failed before reaching the denying gateway. Adding the empty parameters object and asserting the attempted flag proves the intended denial path. Initial real SQL setup stopped because Docker was closed; no trial ran. Desktop is now started and SQL acceptance is running. The study API accepts the deterministic comparator only as baseline; release comparison/promotion explicitly rejects the unsupported format rather than failing later on a missing receipts attribute.

### Paired-condition and SQL feedback
The corrected focused baseline/binding/release-gate run passed58tests123.49seconds. The first SQL run executed three real zero-call baseline workflows and three receipted mock candidate workflows, then failed constructing the test's methodology DTO (missing language family, an unsupported literal source kind and a nonexistent label-pin field). Preserve the strict DTO and fix only the invented fixture. The rerun is active. Inspection also found that methodology binding did not compare paired seed/budget/tenant/agent/event/deadline duration; add this check for both fresh and deterministic comparators, with a deliberately resealed incompatible baseline test. This is an analysis precondition, not a relaxed release limit.

### Resume after approval-review interruption
Automatic approval review exhausted its usage window before the final baseline test command ran; it was a review failure, not an unsafe-action decision. User requested continue. Resumed focused comparison/binding/gate run passes60tests72.07seconds. CFPB always-review now counts the observed review and expected route without claiming absent product/issue/risk predictions; fresh mode still refuses the zero-attempt classifier path. Missing scheduled baseline rows reject even if the partial batch is resealed. Docker had closed again, producing only fixture-setup failure; restarted Desktop and reran required SQL. Installed bytes match66harness/38Olist/26CFPB/28Revenue resources with provider SDKs absent, network denied and6callzero-provider replay. Final SQL and added missing-row test acceptance are pending actual completion.

## Entry 51 — Closure work and blind reviewer handoff
**Files touched:** closure plan and private review packets, authorization ledger.

### Context
User explicitly requested whatever is needed to close #33/#38/#45, authorized a new shared maximum180GeminiFree attempts with no paid fallback, and asked for reviewer packets while they identify independent reviewers. Existing labels/reviews/thresholds are not promoted. Base is verified main21cfea9, identical reviewed #106 treea5390d0.

### Decision before execution
Stop treating incremental mechanism merges as release completion. Map each acceptance check to a concrete missing artifact, prepare blind reviewer-only packets separate from existing proposals/outputs, and reserve the authorized calls for frozen studies. Existing CFPB24case pilot and Revenue29SIM worlds have historical outputs and cannot become unseen holdout. Olist12case draft has no provider outputs but only two holdout groups; it needs independent review and expanded coverage before qualification. A small new Revenue original-span selection can be reviewed without exposing publisher answers; preserve original document-family split and inventory selection provenance.

### How to reproduce the handoff
Verify source/input/evaluator byte pins first; export only facts/question/request and opaque review IDs. Do not export expected/provisional/model answers, original split or selection stratum to reviewers. Keep a separate administrator mapping with source identity, family/split, provenance and prior-exposure flags. Supply blank answer forms and reviewer identity/qualification/conflict declarations; never fill those on behalf of a reviewer. Return files do not become label approval until inventory, offsets, scope, exposure and disagreements are checked. Save a shared180attempt authorization ledger with zero attempts consumed. No output is published or sent to a reviewer automatically.

### Release blockers to resolve
Olist needs independent pre-capture labels, adequate holdout/slice source groups, reviewed protocol/baseline, deterministic-baseline release approval support, complete cost evidence and final H10/fault capture. CFPB needs provider-capable recording plus complete privacy/durable publication and evaluated routing, qualified labels and population coverage. Revenue needs separate original-span and SIM billing/effects studies with qualified interpretation review, applicable-field denominators and complete authorization/compensation/recovery. Current full-profile field contract forces unrelated original/SIM fields together and zero-denominator span checks into errors; resolve applicability explicitly, never mark unobserved checks True. A provider allowance alone supplies none of these approvals.

### Packet verification
Prepared77items (12Olist/24CFPB/12originalRevenue/29SIMRevenue) in four reviewer-only folders. All answer statuses and reviewer declarations are blank; Olist structured intent/expected labels and CFPB consumer/AI labels are withheld, original publisher spans withheld. Original Revenue store/manifest pins verified before selecting12differentfamilies with disclosed answerability strata. Existing cohort exposure is retained only in administrator mapping and disclosed as a limitation. Current Revenue profile requires qualified review for SIM as well; final reviewer instructions retain that requirement rather than silently relax it. Final packet inventory9ed2ec5765b7022915cae72840b0220c2d496a635cb45ea064e65b0718734231 includes readable worksheets and source provenance; initial inventory preserved. No files sent, provider attempts0/180. Verified existing95%zero-failure bounds:2groups84.19%,12groups26.46%,20groups16.84%,36groups9.74%,72groups4.99%; repetition cannot substitute for groups. The reviewer-identity handoff is pending the user; no review or release state is invented.

## Entry 52 — Release paths, scoped observations and durable provider accounting
**Files touched:** shared attempt ledger/cost evidence and release contracts, Olist fault binding, CFPB provider/desk capture, Revenue study applicability/effects capture, tests and operator guide.

### Context
User explicitly authorized completing the engineering while independent reviewers respond, including cost gaps and the shared180attempt control. No new provider execution: invented transports and isolated SIM SQL prove mechanisms first. Closure branch already contains the reviewed handoff plan; last verified main21cfea9.

### Decisions before construction
Use a separately initialized SQLite allowance with one pinned authorization shared across all three agents. BEGIN IMMEDIATE allocates each attempt before transport, never refunds unknown/crashed work, and permits no paid fallback. Success/failure settlement stores only request/response digests and typed accounting; source text and keys never enter the ledger. Guard transport wraps each actual attempt, so internal retry/circuit behavior cannot bypass the shared cap.

Retain provider raw Usage and provider_usage. An optional canonical accounting attachment records an explicitly reviewed, expiring, model/endpoint/project-bound Free tariff; derived cost is labeled tariff-derived rather than provider-reported. Historical responses omit absent attachments so old byte pins remain unchanged. Missing token counts or mismatched tariff/attestation cannot be repaired by treating unknown as zero. Verify derived usage when reading sealed receipts.

Add an explicit deterministic-baseline approval format and release path rather than weakening existing provider-only APIs. Bind algorithm/source/evidence/protocol and observation readers before admission; retain candidate fresh receipts, case/paired-regression/approval order and methodological gates. Bind supplementary crash/authorization/effects evidence to exact candidate/case identities. CFPB provider composition must publish/read durable SQL with narrative-only gateway input and scoped privacy canaries. Revenue original-span and SIM reconciliation study applicability must be explicit; unobserved applicable checks fail, while undefined or unrelated fields receive no fabricated success credit.

### Verification plan
Exercise allowance races/reopen/exhaustion and crash reservation retention; cost raw-vs-derived separation and tamper/missing/mismatched policies; release approval wrong kind/algorithm/pins/reuse; actual SQL publication/redelivery and wrong scope; original/SIM denominator separation and effects/compensation/recovery evidence. Keep all180live attempts unused. Run full hosted regression and required SQL before the review handoff, with no claim that code tests satisfy reviewer or final-study gates.

### First verification and diagnosis
The first actual CFPB run produced setup-error rows and therefore correctly failed missing fresh receipts. Direct inspection found the synthetic canary tenant used a character forbidden by the identity contract. Use a valid separate tenant and explicitly mark its job obsolete: privacy input should not rely on lexical job ordering. The corrected normal capture publishes/reconstructs all three actual trial decisions and passes read-back. The failure variant then exposed a test assumption: routing intentionally stops after a timeout, so three trials have three dispatches, not six. Correct the invented expectation, retaining the no-retry policy. Static typing passes172sources;42accounting/approval/gate and23accounting/applicability tests passed before the final composition/SQL rerun. Live calls remain0.

### Actual state and package acceptance
All8targeted real SQL/process tests pass514.45seconds: CFPB normal/failure publication and preflight, Revenue bound denial/correction/reconstruction/compensation, and Olist before/after hard exits plus exact candidate-bound two-stage companion. The corrected provider preflight/accounting/CLI run passes23tests30.29seconds; one assertion initially matched a particular rejection message although the earlier transport check correctly refused dispatch. Test the refusal rather than implementation ordering. No provider calls. All six wheel/sdist pairs build; installed69harness/39Olist/27CFPB/30Revenue resources match bytes, historical APIs/baselines import without provider SDKs, and network-denied strict replay consumes6recordings with0provider. Historical Olist inventory/results, source/draft and reviewer-packet pins are unchanged. The final all-new-feature suite and hosted full regressions remain pending at this log point. A last applicability review rejects empty/all-unrelated check inventories rather than allowing vacuous completion; applicable unknown qualified support still blocks.

### Resume with explicit merge authority, 2026-10-26
The user authorized proceeding through remaining issues and merging tested PRs autonomously,
with attention requests for decisions/access they must supply. Record that authority in
AGENTS.md so later turns do not unnecessarily hand PR submission/merging back. Independent
reviews and final-study requirements remain factual prerequisites, not something merge
authority can fabricate. Interrupted shell sessions have no retrievable completion result;
restart the full locked check with a saved log rather than claiming its earlier partial run
passed. Preserve the completed targeted SQL/package evidence above.

## Entry 53 — Fixed release denominators for prior auth and shipment simulation
**Files touched:** separate P6/S6 report modules, shared aggregate catalog, tests and walkthrough.

### Context and decision before implementation
User authorized proceeding through all remaining issues and tested PR merges; independent
review responses are explicitly pending. While #107 checks its frozen head, prepare #51/#57
and the #61 handoff on a separate branch. This does not accept their #33 prerequisite or
authorize calls for these two agents under the three-agent180attempt allowance.

### How to build it
Reuse the existing complete cohort/label validators and independent domain scorers. Freeze
the case/trial inventory separately from observations. Preserve every missing/failed row,
split/source/group denominators, all-three reliability and false-complete recommendation
denominators. For shipment simulation, compare recorded candidate action maps with the actual
do-nothing/rules/estimate solver on the same hidden worlds and each frozen sensitivity;
do not call a policy with hidden outcomes or treat an omitted action as a completed wait.
Keep candidate origin explicit, raw inputs private and release authorization false.

### Alternatives and verification plan
Extending old one-pass CLI summaries would not account for missing repeated trials; keep a
separate versioned report API rather than reinterpret historical outputs. A shared catalog
should publish only report byte pins and fixed aggregate counts, never arbitrary nested
payloads or clinical/source text. Test deliberately missing/wrong/unsafe observations,
unknown identities/duplicates, edited-parent split leakage and changed hidden outcomes.
Neither code tests nor AI-provisional references provide qualified review or final release.

### Early feedback and verified predecessor
The first three invented report tests pass10.74seconds. A missing candidate action map stays
missing, while an empty observed map stays unresolved. The catalog canary test confirms no
arbitrary source text/private path escapes. Strict types found an unannotated dictionary of
Counters; specify dict[str, Counter[str]], preserving exact arithmetic. Initial construction
also used reserved keyword `all` in a dict call; use the explicit string key instead. The
report keys remain compatible with the other domain reports.

PR#107 merged autonomously as a30ebc4 after exact-head all10checks passed: hosted1135tests
per quality cell and124Postgres tests; actual Windows3.12/database logs checked. Local full
1135tests698.58seconds and final4CFPBSQL261.10seconds pass. Merged/reviewed trees match;
mainrun40328852820 is still running at this log point. Provider attempts0/180, reviewer
packets unchanged. Subsequent P6/S6/catalog work stays on its own branch/PR.

### Focused report acceptance
Final67report/PriorAuth/simulator tests pass2.54seconds; strict typing175sources, Ruff and
sixwheel/sdistpairs pass. Added a stale/conflicting-facts witness: explicit wait remains
unresolved even though it spends zero. Otherwise a no-op could incorrectly inflate completion.
Catalog CLI tests verify external inventory/report pins, exclusive new output, canary suppression
and refusal of overwrite/unknown versions/invalid counts.344relative documentation links resolve;
backlog dependencies/statuses unchanged. Main40328852820 now passes all9applicable jobs for
PR#107; metadata intentionally skipped and reviewed/merged tree equality verified. No live calls.

## Entry 54 — Local service health and restore without overwriting live state
**Files touched:** Olist service readiness/backup/restore helpers, operational CLI, integration tests and runbook.

### Context and decision before implementation
Continue authorized #58/#59 engineering preparation while #108 checks its frozen head. Existing
loopback console already runs with scoped accounts, resource limits and durable SIM workflows;
it needs actionable schema/DB readiness and an actual backup/restore exercise. Keep external
deployment and final release gates pending. Use the existing local Docker host with no paid
services or new provider attempts.

### How to build it
Capture one read-only repeatable-read snapshot of the three Olist application schemas, binding
installed schema/source versions and PostgreSQL major version. Use PostgreSQL binary COPY to
preserve JSON, checkpoint bytes and receipt types; keep archives private, externally pinned
and exclusively created. Restore only into a newly created owned trial with the same installed
schema, never truncate an existing target. Recompute deterministic row digests after restore
and run the application/review/redelivery paths against the rebuilt database. A failed new
restore is cleaned up, while the original database and archive remain intact.

### Why and alternatives
Replacing current business rows from an old application image would silently erase newer
effects. A separate restored database permits inspection/explicit cutover instead; application
rollback is a code/config choice, not a business refund reversal. SQL-string dumps would add
an unnecessary executable restore surface. Binary COPY carries rows, with code-owned DDL
and exact schema/constraint/index pins. It is PostgreSQL-major/schema specific, deliberately
not a general cross-version migration or complete disaster-recovery service.

### Verification plan
Test real pending review, committed ledger and checkpoint state through owned snapshot/restore;
refuse changed pins/schema/major/existing target, preserve source after new effects, and prove
duplicate redelivery returns the original receipt. Check liveness without DB access and
readiness with unavailable/missing/mismatched schemas without exposing credentials or records.

### Actual recovery feedback
The first integration invocation could not resolve its imported console fixture's `app`
dependency; explicitly register the existing app fixture. The corrected actual SQL exercise
passes2tests39.43seconds, then2tests28.89seconds after exact PostgreSQL build/private-path
guards. Strict types rejected the name `schema` because it shadows BaseModel.schema; use
`namespace`, and explicitly check optional fetchone results instead of indexing None. Preserve
binary COPY, quoted identifiers and the existing ownership boundary.

Final3SQLtests55.32seconds include real CLI backup/restore-new/readiness in a separate clean
invented Git checkout. It persists only the new owned target identity and refuses repeat
restore; pending review, checkpoint/ledger/result and newer source effects are checked.
11health/console tests19.18seconds,178typed sources, Ruff/format and sixbuildpairs pass.
347relative links resolve and publication scan confirms configured secrets/24source order
IDs absent. Full hosted/local regressions remain pending at this log point. No provider calls.
PR#108 also merged as b71f7f7 after all10jobs; its post-merge main40331851595 succeeded with
reviewed-tree equality. Reviewer responses remain explicitly pending; no release issue closed.

## Entry 55 — Shutdown evidence without collecting request identities
**Files touched:** console lifespan, local service telemetry, actual server acceptance and runbook.

### Context and decision before implementation
The user asked to complete the remaining work while reviewer responses stay pending. Main
contains merged #107–#109. Issue #58 still needs shutdown telemetry/durable-work evidence;
the previous health and restore tests alone do not prove a running HTTP server drains work.
Use the existing loopback deployment and zero provider calls. External host selection and
release acceptance remain separate from this local engineering check.

### Before you read on
How can an operator distinguish a completed graceful shutdown from an abruptly killed server
without storing case URLs, bodies, cookies or account names in telemetry?

### Options considered and why
Automatic HTTP tracing/access logs would capture sensitive case paths. Instead keep a fixed
aggregate of started/completed/interrupted HTTP responses and status classes, plus monotonic
timing totals. Reserve a new private output before serving and write/fsync a final snapshot
from ASGI lifespan after Uvicorn drains requests. An empty file after process death must not
look like successful shutdown. This supplements existing evaluation traces; it does not
claim Langfuse ingestion or model-quality evidence.

### How to build it and verification plan
Use a lock around counters, keep the middleware's input limited to status and elapsed time,
and never pass the request scope to the recorder. An exclusive file outside Git prevents
overwrite and symlink reuse. The CLI requires the output path and a bounded graceful drain.
Run a real loopback server, pause a request after its SQL commit, begin shutdown, then release
the request. Verify HTTP completion, the flushed aggregate, and reconstruction/redelivery
returning the same receipt. Test missing output, storage failure and unexpected exceptions
without printing sensitive payloads. Extend recovery evidence with measured snapshot/restore
durations, distinguishing observed timings from production RPO/RTO guarantees.

### Actual feedback before hosted checks
The first local run could not write the sandbox's temporary directory; rerun with the
existing private D-drive temp directory and authorized host access. Docker was stopped;
start the existing Desktop hidden rather than resetting unrelated containers. The real
server drain/SQL/telemetry checks initially reached the final restart assertion, then failed
because FastAPI's current TestClient uses httpx2 cookies while the TCP client uses httpx.
Pass an explicit cookie name/value mapping between them, not one library's cookie object.
The corrected focused21tests pass11.22seconds and actual4HTTP/Postgres/CLI tests pass84.37s.
Strict typing covers180sources. An intentionally impossible recovery limit produces exit2
and a real verified restored database/report, never a false SLA pass. Live provider calls0.

### Source-grounded deployment/recovery demonstration
Freeze executable commit875406e before the private demonstration. Re-read an unchanged O2
view from the externally pinned SQLite source, use the existing constructed SIM confirmation,
enroll a new owned SQL trial, provision distinct constructed operator/reviewer accounts and
exercise the actual listening HTTP submit/approve/execute/duplicate paths. Leave another
case pending, stop normally and run the new measured restore into another owned trial.
The reconstructed store preserves pending review and exact original receipt; independent
SQL sees one matching refund. Capture0.2957769seconds, restore/verify1.3379511seconds against
the explicit local60-second objective. Both owned databases removed; no shared service reset.
Private report/telemetry byte pins and safe aggregate are in docs/data/olist-source-operations-v1.json.
No provider or independent reviewer was involved. Source/draft/review packets are unchanged.
All six wheel/sdist pairs and both package import contracts pass; hosted full checks pending.

## Entry 56 — Zero elapsed time is a valid coarse-clock observation
**Files touched:** service telemetry tests only; production counters are unchanged.

### Context and diagnosis
PR#110passed all10checks and merged5c85330. Main40382433398then failed only Windows3.12:
the new ASGI test required total_request_ns>0 although all three requests completed within
one coarse monotonic clock tick. Other cells and128Postgres tests passed. The real timing
recorder already preserves max(0,end-start); inflating measured zero would falsify evidence.

### How to reproduce and correct it
Inspect the actual failed job121781913451:1160passed, one failed assertion at line38of
test_olist_service_telemetry.py. Accept nonnegative observed durations in the real HTTP test.
Add a deterministic test holding monotonic_ns at100and another advancing it by50. Both must
preserve exact elapsed values, one completed request and no active/interrupted work. This
checks zero-resolution semantics without introducing sleeps, retries or invented nanoseconds.
Run the focused telemetry/health/console suite and full exact-head hosted checks. A separate
small correction PR keeps unfinished Groq preparation out of the main repair. No provider calls.

## Entry 57 — Explicit Groq routes without disguising a provider change
**Files touched:** optional Groq adapter, owned worker, route executor, separate smoke allowance and tests.

### Context and decision before implementation
User selected Groq Free and supplied a key after the proposed12attempt invented-only smoke
scope. Preserve it only in ignored configuration. Gemini180and reviewer packets stay unchanged.
Verify mocked controls first, then freeze source and a new invented-only plan before capture.

### Before you read on
What must be retained when fallback has a different provider/model/parameter vocabulary so
replay and accounting cannot mistake it for a successful primary exchange?

### Options considered and why
Do not silently rewrite a Gemini transport request or label Groq output as Gemini. Use two
frozen requests with identical messages/schema, distinct bounded gateways and shared run
controls. Return both request/response pairs and aggregate usage explicitly. Each route
attempts once. Auth/schema/budget failures stop; only timeout/rate/outage permit switching.
Strict replay matches both exact requests/occurrences; mismatches never fall back to network.

### How to build it
Pin Groq's HTTPS chat endpoint and initial GPT-OSS120B model. Official deprecation docs rule
out Llama3.3for Free accounts; schema docs support GPT-OSS120B strict output. Disable ambient
proxies/redirects/retries; bound HTTP content/time, validate closed schemas locally and retain
raw counts with unknown monetary cost. Initial support excludes tools, streaming, provider
parts and immutable revision claims. A lazy importable worker runs in the existing owned
spawned process so wall deadlines and cleanup apply.

Initialize a separate exclusive SQLite grant with maximum12attempts, request fingerprints,
credential hash and actual authorization/time references. Reserve under BEGIN IMMEDIATE
before spawning; exceptions/failures remain consumed. Only groq-invented-smoke contexts and
frozen invented requests qualify. No reset/retry CLI. Plan three obvious invented prompts
and two trials each; retain missing rows if a provider failure stops the smoke. Six planned
calls are below the cap, not retries. Keep plan/receipts private and publish only an aggregate
that disclaims domain quality, verified billing, reviewer judgments and release permission.

### Early feedback
The first usage test treated boolTrueas int1 through dictionary equality. Require exact int
in its test branch; production correctly rejected boolean counts. Initial mocked28tests pass
2.17seconds and184sources typecheck. Expanded shared-control/Gemini-budget regressions and
the final invented smoke remain pending at this entry point.

### Freeze before provider execution
Expanded108mocked route/wire/replay/shared-control/Gemini-budget tests pass96.18seconds;
184sources typecheck, Ruff/format/import contracts and sixwheel/sdistpairs pass. Publication
scan12files finds no configured Gemini/Groq credentials or24source IDs;369relative links
resolve, source/draft pins and backlog dependencies/statuses stay unchanged. The ignored
Groq key is not printed or tracked. Freeze the executable candidate before six planned
invented trials, one attempt each, at most12total under a separate persistent grant.
PR#111 merged990a20eafter all10checks (1163tests per four cells/128SQL); post-merge
main40385089594succeeds with the identical reviewed tree. Preserve the earlier failed main.

### Actual Groq evidence, before hosted submission
Freeze3db69d5/lockd99ed794 and the three invented requests before dispatch. All six direct
trials pass;688input/218output tokens reported. A separate frozen three-row routing plan
uses the same allowlisted requests and same ledger: primary outage is constructed/no-network,
actual Groq fallback passes3/3. No real primary-provider outage or relative quality is claimed.
Independent offline readback verifies all nine request/context/response settlements, schema/
literal outcomes, raw token totals1032/327and one attempt per dispatch. The single separate
Groq budget is9/12consumed,3remaining,0unsettled. Raw cost unknown for all nine, billing unverified;
Gemini0/180. Three prompts with repetitions are not nine independent domain examples. No
private domain records exported, no failed rows retried. Public aggregates bind the frozen
plans/code/lock/allowance; credential/ledger/receipts stay private. Full hosted checks pending.

### Full CI caught the missing fixture envelope update
The first Groq PR head7953fb0fails strict replay CLI on Linux:1192tests pass, but v12is bound
to old lockc8c15295while the new optional extra changes metadata to d99ed794. Resolved package
versions are unchanged. ReplayBinding correctly refuses the new dependency pin; do not bypass
or rewrite it. Preserve v1–v12, explicitly capture a new synthetic v13with the maintenance
helper/exclusive writer from a clean source, compare every request/response byte with v12,
then update the externally trusted current fixture pin and add v12to historical-lock rejection.
Also extend the recording credential guard for Groq's key prefix with a non-key test value.
No new provider call is needed or justified by this fixture repair; the actual nine Groq
captures remain sealed at3db69d5. Initial failing runs are retained rather than called passes.

At clean30acbdd, create v13exclusively with digest4c57fdf1ad0228c3e16924750754c037754de2a3446b35c4cf69c1dc100de303.
Its six canonical request/response pairs equal v12; all v1–v12file bytes match their Git blobs.
The maintenance process denies outbound network and screens both configured keys. Update the
trusted constant deliberately, preserve historical-lock rejection, then rerun the full replay
and Groq controls. Existing live9/12budget/evidence remains untouched.

Corrected133replay/Groq/allowance tests pass13.88seconds,184sources typecheck and Ruff is
clean. The automatic Groq-pattern test supplies no configured deny value; publication still
refuses that invented pattern. v12retains its exact old digest and rejects the new lock.
Push the explicit v13repair for full exact-head CI; do not rerun provider calls or claim the
earlier CI passed.

## Entry 58 — Evidence alternatives without inventing expert approval
**Files touched:** `docs/automated-review-execution-plan.md`, closure-plan navigation and this journal.

### Context
The user has no standing reviewer team and requested a detailed alternative that preserves
the production goal. This proposes a successor evidence strategy to Entry51's reviewer
handoff; the original packets, judgments, profiles and release failures stay intact. No
replacement evaluator is implemented or qualified by this planning change.

### Before you read on
Which fields can an independent program prove, which have suitable external reference
labels, and which still need a reliable interpretation? A single reviewer Boolean hides
those three different problems.

### Options considered and why
A demo-only scope was suggested earlier; the user wants the production target retained.
Replacing a human name with a model in the existing review record would falsely satisfy a
provenance requirement. The proposed path instead binds evidence to individual claims,
tests model reviewers against external answers, and preserves unresolved requirements.

### How to build it
Read the existing `StandardProfile.required_fields`, `Review.kind` and `_reviewed` checks.
The code presently distinguishes provisional AI from blind human/qualified review; preserve
that legacy path. First inventory each field and map it to reference, independent executable
or model evidence with an applicability range. For example, compute an Olist SIM amount with
a separate decimal oracle, but assess unseen intent wording against suitable reference
examples. Do not derive expected amounts using the candidate's own policy function.

Before model execution, seal evaluator prompts/configurations, prepare known-good and
known-wrong calibration inputs, split by source/error family, and measure false acceptance
and abstention on separate test examples. A future versioned evidence record must bind
qualification, exact sources, case/input and result hashes; two agreeing models without an
external basis remain provisional. Negative tests must refuse wrong scopes, unsupported
spans, changed prompts and missing rows. The policy owner accepts the concrete replacement
method before it becomes an active release path; no skip-review flag is proposed.

Count every drafting, judge, comparator, candidate and live fault call before capture. The
plan proposes tranche ceilings summing to the existing180Gemini maximum, not a new grant.
The current Groq invented-smoke budget cannot pay for domain judging. Sample-size targets
can exceed these allowances; report that before spending rather than weakening uncertainty.

### Verification and limits
Inspected actual main95691bde profiles, audit types, H10 rules, allowance documentation and
the current gate inventory. Consulted primary judge-bias papers and current Langfuse judge
documentation. This is a planning artifact; no code behavior, active acceptance, provider
ledger, reviewer packet or issue state changes. Validate local links and whitespace; no
production-model test result is implied by a documentation check.

### What went wrong
The initial direction treated absent reviewers as a reason to suggest a smaller release
scope. The user clarified that the goal must remain. The revised plan addresses evidence
methods and evaluator reliability while keeping irreducible gaps visible. It cannot promise
that every domain has enough suitable reference labels or that consensus replaces expertise.

## Entry 59 — Make evidence and attempt plans executable without granting approval
**Files touched:** shared planning contracts/CLI, Olist evaluation oracle,43-field matrix,
focused tests and the evidence-foundation study chapter.

### Context and design
The user approved executing Entry58's direction. Start with offline #33/#25/#60 preparation,
preserving human-review gates until a separately validated evidence method can be accepted.
The first implementation must detect missing requirements and unaffordable studies, without
mistaking an offline budget spreadsheet for permission to dispatch.

### Before you read on
How do you prevent a forecast that fits180calls from being used as a new180call grant,
especially if two agents share the same provider allowance?

### Options considered and why
Do not add an `allow_ai_review` Boolean to the old audit. Keep proposals separate and make
dispatch/release authority literalFalse. Bind each domain matrix section to its actual
profile hash; compare exact field and slice sets so a forgotten requirement fails. Count
all schedule dimensions against one snapshot per provider, not a new cap for each agent.

### How to build it
Implement `RequirementEvidence` rows with proposed methods/checks, existing evidence and
remaining work. Validate all43fields across the five current profiles, retaining `pending`
for every row. `AssessmentProposal` binds source/input/evaluator hashes and exact text spans,
but deliberately cannot deserialize as `Review`. Verify span hashes/Unicode offsets against
actual supplied sources; literal existence alone is not support meaning.

For attempts, multiply cases, trials, calls, orderings and reserved retry factor; aggregate
by provider and agent. Require one authoritative provider snapshot, subtract consumed from
maximum, and report missing provider/scope or exceeded cap. Revalidate copied objects at
boundaries. The pinned CLI rejects duplicate JSON keys and limits input bytes; module entry
denies network. It neither writes an allowance nor reserves an attempt.

Write an Olist oracle from the accepted SIM decision table with its own ten predicates and
separate fact/request types. Import source view types, not runtime policy/functions/constants.
Return all failed predicates rather than copying first-error wording. Keep structured intent
an external input so this program cannot pretend to label natural language. Verify exact cap,
partial/reship requests, unknown facts, contradictory delivery, future facts and scope/time
refusals with invented witnesses. Final candidate binding and semantic qualification remain.

### Feedback during construction
Initial focused run passed68checks but two existing temp-file tests could not access the
default sandbox temp directory. Use the existing private D-drive temp parent for the rerun;
this is an environment error, not evidence that those two tests passed. Ruff requested Python
3.12generic syntax for the CLI reader; update the declaration rather than suppressing it.
The first oracle/planning source-only mypy run passed. Final focused and hosted results follow
only after execution. No provider dispatch, source export, label promotion or gate edit.

### Focused and installed verification before submission
Corrected focused suite passes102tests2.77seconds, with only a local pytest cache warning.
The full quality run has reached187typed sources and both import contracts; full pytest
is still running. Sixwheel/sdistpairs build successfully. The installed harness wheel in
the existing isolated environment matches77package resources exactly; no provider SDKs or
industry packages are installed there. Its network-denied planning module reports43pending
fields and no release permission. The first manual CLI invocation supplied an incorrect
matrix pin and correctly refused; the corrected inspected matrix pin is
3dbf1d5b5a6d6053a589320148480f35e49522c17635d339a7ff5f8a79eaf9d9.
All41required slices are inventoried. Legacy gate/profile/lock/backlog bytes are unchanged.
Publication scan checks both configured credentials and24source IDs without printing them;
source/customer/draft pins are unchanged. Full and hosted results remain pending.

## Entry 60 — Test the evaluator without hiding abstentions or weak references
**Files planned:** shared evaluator qualification/report CLI, reference applicability audit,
focused tests and a study chapter.

### Context and decision before implementation
PR113mergedb909aa7 with green main and all1229quality/128SQLchecks. The user requested the
next execution batch. Inventory coverage is now executable, but it does not show whether
an evaluator can recognize wrong answers. Build that measurement before spending calls or
changing review acceptance. Public source labels require task-specific applicability.

### Before you read on
If a judge abstains on every unsafe example but accepts every easy example, can its apparent
conditional accuracy qualify it? Decide which denominators and source groups must remain.

### Options considered and why
Do not measure agreement alone or drop missing/abstained rows. Use a frozen schedule with
both acceptable and unacceptable references, fixed repetitions and group-level uncertainty.
Keep calibration separate from holdout; merge connected source/template keys before checking
leakage or counting groups. An inherited publisher span is extraction evidence, not a new
clinical or contract-meaning label. Keep existing release authorization separate.

### Construction plan
Pin dataset, protocol and evaluator identities. Require explicit coverage/error limits;
record no default production thresholds. Bind each observation to the exact scheduled case,
trial, input and evaluator and keep absent rows as failures. Report the complete confusion
matrix plus abstention/missing counts, class/slice coverage and false-accept/false-reject
denominators. Every component with a missing/wrong repetition contributes to group-error
uncertainty. All-abstain and tiny-perfect examples must fail appropriate explicit criteria.
Do not produce an accepted human review or a deployment permission from these statistics.

Audit existing CUAD source/category metadata against original extraction versus invented
billing fields without printing source text or changing references. Inspect primary-source
metadata for ContractNLI/MedNLI applicability and access; no restricted dataset access or
new provider export follows from a public metadata page. Final implementation/results follow.

### Initial implementation feedback
Focused qualification/planning/Revenue regressions pass43tests7.40seconds; all three new
sources pass strict typing. The first Ruff pass flagged long lines/import order; formatting
and the targeted import fix cleared them. Exact input hashes now participate in source
components automatically, so renamed duplicate inputs cannot evade split checks. Added
class-specific coverage and conditional error limits after considering how abstention could
reduce a scheduled-class error rate without improving decisions.

The read-only CUAD drill reverified the original archive and both stores against existing
prepared-manifest pinb852424a. All20,910questions/13,823spans/457inferredfamilies match; the
aggregate finds6,702answerable and14,208no-answer references across41categories. Two rare
categories have only one answerable holdout family; two have no no-answer holdout examples.
Expose these limits instead of treating corpus size as evidence for every class/category.
No raw text/IDs were printed, no reference changed and no provider call was made.

### Frozen deterministic probe before model judging
Freezec6c65caafter190typed sources,295formattedfiles, kept import contracts,43focused tests
and sixbuildpairs. Select24distinct inferred families from source development only, by
declared hash convenience ordering. Seal the first12as calibration and next12as validation.
Each original context contributes one original valid quotation and one shifted-offset
invalid candidate:48cases, one deterministic trial each. Store raw candidate inputs separate
from reference labels; invoke only the existing `verify_extraction` with saved public inputs
and claims. Install the network-denial hook before execution. Preserve original source and
old holdout bytes; this is literal integrity, not semantic interpretation.

All48decisions match:24calibration/24validation. The new reporter nonetheless rejects
qualification under the explicitly proposed72group/5%upper-bound objective:12validation
families have zero observed errors but a26.46%two-sided95%upper bound. This is a diagnostic
objective, not an approved production risk threshold. The CLI independently recomputes the
sealed result identically, retaining exit1/no-release. A preliminary deliberate placeholder
pin invocation refused without output; the actual recomputation used the separately sealed
plan/public aggregate pins. No provider, effect, failure retry, new label acceptance or
model-quality claim. Raw source/labels/observations stay in the exclusive private probe
directory; tracked aggregate contains hashes/counts and limits only.

### Separate larger study with unchanged verifier
The small probe established correct measurement/refusal, but usable component evidence can
be gathered without model calls. Freeze a new plan at the same executablec6c65ca, excluding
all24priorfamilies. Select84different source-development families:12calibration/72validation.
For each, freeze a literal positive plus shifted-offset, wrong-case, duplicated-span and
abstention-with-span negative claims. These labels follow construction/literal integrity,
not semantic/legal judgments. Inventory all harness/Revenue sources and lock; use saved public
inputs only, keep references separate and deny network before execution.

All420observed decisions match:60calibration/360validation; each variant84/84. There are72
validation groups for each class and zero failed groups; the4.9944%two-sided95%upper bound
meets the declared diagnostic5%/72group objective. `criteria_met`true is scoped to this supplied
literal-integrity protocol, not a model judge, accepted production limit or release. Preserve
the v1failed qualification and its12group/26.46%result; do not call the larger different
population a causal improvement. Original corpus/holdout/source pins and provider budgets
are unchanged. Independent offline/installed recomputation follows before submission.

### Final local verification before hosted submission
Both v1andv2sealed reports recompute identically through the standalone network-denied CLI
and the isolated installed harness. Its79package resources match wheel bytes, with no
provider SDKs or industry packages installed. The v2source inventory is unchanged and its
families are disjoint from every v1family. All sixwheel/sdistpairs build;190sources typecheck
and both import contracts hold. Focused46checks pass2.82seconds. While adding the last three
negative tests, a block was inserted inside another test and caused one NameError after45
passes; corrected test placement, then reran the focused suite. Production/capture code
never changed and neither study was rerun. Hosted full quality/SQL and postmerge checks
remain pending. Publication screens original source IDs/context prefixes and configured
credentials without printing them; no provider allowance has been consumed by this batch.

### Hosted scan found inventory hashes beside access/API/auth filenames
Initial PR114run40412901602fails the generic-api-key scan at four v2inventory entries.
Read only rule/file/line/fingerprint diagnostics; compare every flagged value to its actual
source file bytes. All four match SHA256of access.py, billing_access.py, console_api.py and
console_auth.py. Configured credential scans remain clear. Keep the failed run, do not rerun
the verifier or change the frozen study to repair a publication false positive.

Represent public inventory as separate path/hash records and retain the original canonical
map digest. Reconstruct it and compare to the sealed private plan, unchanged source bytes
and evaluator identity. The repository already uses exact historical `.gitleaksignore`
fingerprints for verified aggregate hashes; append only these four commit/file/rule/line
findings. Do not add rule-wide, hash-wide or path-wide exclusions, rewrite branch history,
alter the scanner workflow or suppress future findings. Repaired exact-head CI remains
required. The diagnostic reports, original plan/data/results/pins and executable stay intact.

## Entry 61 — Budget safety does not guarantee writer availability
**Files touched:** budget-accounting tests and this journal; ledger/transport code unchanged.

### Context and diagnosis
The user explicitly approved the four exact historical hash findings after automatic review
required specific security-setting authorization. Repaired head2917949passes secret scanning
and dependency audits. Windows3.12then reports1failed/1253passed: the shared180attempt test
raises SQLiteBUSYat BEGIN IMMEDIATEafter the existing10second writer wait. Other quality
cells pass. Inspect the actual failure before rerunning; do not assume a harmless flake.

### Before you read on
Does a durable180attempt ceiling guarantee that200simultaneous callers can fill every slot
under bounded storage-lock waits? Which condition must block actual provider dispatch?

### Why and how to correct it
The production transport already catches SQLite reservation errors and returns budget denial
before delegate dispatch. The safety requirement is no overspending or unrecorded dispatch,
not successful admission of every request under arbitrary disk contention. In the direct
ledger race test, recognize only SQLiteBUSY/LOCKEDas bounded denials; propagate all other
database errors. Assert received unique tickets equal actual consumed records and never
exceed180. After concurrent workers finish, sequentially fill the remaining invented slots,
then retain exhausted/reopen/unsettled/settle/no-refund/no-reset assertions.

Add a real-file lock test: hold BEGIN IMMEDIATEon a separate connection, shorten only the
test connection's busy wait, and attempt dispatch through BudgetedTransportwith a counting
fake delegate. The lock must produce budget denial, zero calls and zero consumed rows.
After releasing the lock, one allowed attempt may dispatch/settle; the next must deny at
the cap. This verifies availability failure remains safe without changing production waits,
adding retry loops or broad exception suppression. Original citation studies/source pins
stay atc6c65ca; no executable/scorer/lock changes or provider calls are needed.

### Local verification before pushing the test repair
The budget/Groq/qualification/reference suite passes77tests24.19seconds. Lint and format
checks pass. All91captured harness/Revenue source digests still match the v2study inventory;
only tests and journal changed. The repaired full hosted matrix must pass before merge.

## Entry 62 — Test semantic answerability against publisher references
**Files touched:** Revenue semantic pilot preparation/projection/parser, tests and study docs.

### Context and design before capture
PR114mergeda714b65with1255quality/128SQLchecks and green main. The user authorized up to24
of the existing shared180GeminiFreeattempts for12short, family-separated original CUAD cases,
with publisher labels hidden from Gemini. This is semantic answerability, not a model judge
assessing arbitrary candidate outputs or legal/billing validation. Retain all earlier probes.

### Before you read on
How do we send complete source context and its question without giving the model publisher
answers, split identity or expected labels? How do public labels limit an apparent pass?

### How to build it
Select six answerable/six no-answer cases from existing source development, one per inferred
family, with context length capped before selection. Exclude trivial document/party/date
categories and earlier integrity-study families where feasible. The four calibration cases
and eight validation cases remain grouped; two repeats each cost at most24attempts. The
model projection accepts only `ExtractionInput` and constructs context/question JSON. Targets
stay in private preparation and evaluator-only files. Schema requires accept/reject/abstain
and exact supporting quotations for accept, no quotations for reject/abstain. The parser
checks literal presence but never calls it semantic proof.

Freeze dataset, route/prompt/schema, source inventory, policy and schedule before dispatch.
Use shared durable180ledger with an additional fixed24pilot stop, reserve before owned
spawned workers, no retry/fallback. Reconcile raw versus derived token/cost evidence and
preserve missing/failed rows. A tiny balanced public-source pilot cannot meet production
uncertainty or prove unseen model-training data. Qualification remains explicitly diagnostic.

### Preflight and actual capture start
Local fixtures initially reused identical context/question inputs with conflicting labels
and omitted the response usage contract. Correct fixture inputs and supply explicit invented
usage;27focused checks pass3.30seconds. A one-file mypy invocation could not resolve editable
harness type metadata; the configured whole-repository check passes191sources. Ruff297files,
import boundaries and sixbuildpairs pass. Freeze executable1fd39f5before capture.

Prepared12cases have12distinct inferred families, six answerable/six no-answer, four
calibration/eight validation, ten nontrivial clause categories, contexts<=11,930characters.
Exclude108families from both previous integrity studies and leave original source holdout
unchanged. Recheck original store/manifest pins; the prepared bundle canonical pin is
777b1ec8fc8b5fc3e10bd9b7bff582c8e5bd8c025dfa8d74b5cad3200a0534a3.

Initialize one exclusive shared180ledger after verifying no existing live closure allowance;
the user explicitly approved24of that same total, not another allowance. Bind the private
scope to the authorized local credential association, documenting that it is not an actual
provider-verified project ID. Reserve in the parent before an owned Gemini worker;60second
wall bounds, shared controls, one attempt per row and no fallback. Freeze the entire24row
schedule, references, protocol and source inventory before dispatch. First observed attempts
complete without parser/transport errors; actual label correctness/accounting remains for
the sealed offline audit after capture. Do not overlap full suites with live calls or tune
the prompt using observed answers. Final results follow without rewriting this history.

### Actual semantic results and independent accounting
All24scheduled attempts complete and settle; the authoritative shared180ledger has24used,
156remaining,0unsettled. No retries/fallback/paid route. Independent raw readback binds every
context/request/response to its ledger reservation/settlement and gateway/controlled record;
source inventory remains unchanged. Recomputed calibration6/8matches; validation13/16matches
with2failed judgments,14decisions and92.86%conditionalversus81.25%scheduled accuracy. No
missing/abstained rows or observed false accepts. Reference-relative false rejects remain
2calibration/1validation. Two failed validation quotes only match after whitespace
normalization; frozen literal validation correctly refuses them. Keep those failures and
the Minimum Commitment/Expiration Date reference disagreements; no label/prompt revision.

All24raw token components known:39,716input/842output. Raw monetary cost unknown for all24,
not zero billing. The eightvalidation groups include two failed groups; upper uncertainty
59.07%, and declared diagnostic qualification fails. No production/clinical/legal or
model-judge approval follows. Private raw records, exact grant/credential association and
provider IDs remain outside Git; safe aggregate retains complete denominators/pins/limits.

## Entry 63 — Map whitespace changes back to exact source spans
**Files planned:** shared citation alignment, separate Revenue parser v2, adversarial tests
and an offline diagnostic report; legacy parser/capture/reference files remain untouched.

### Context and decision before implementation
PR115merged3d72610with1259quality/128SQLchecks and green main. The semantic pilot failed;
two quotations were nonliteral only because model output changed whitespace. User requested
proceeding with offline error analysis and a separate improvement. Do not rerun provider rows
or relabel old failures. Shared Gemini consumption remains24/180.

### Before you read on
Can a quotation with collapsed line breaks yield a byte-verifiable original source span
without accepting changed punctuation, negation or an arbitrary repeated occurrence?

### Options considered and construction plan
Simply allowing normalized substring presence would discard the original offset/evidence.
Fuzzy matching would risk accepting changed meaning. Instead normalize Unicode whitespace
runs only, retaining each normalized character's original start/end offsets. Require exactly
one match across the source; repeated/ambiguous matches refuse. Preserve case, punctuation,
digits and every non-whitespace character. Return the exact original substring and source
hash, plus input-quotation hash and an explicit semantic-support-not-assessed marker.

Build a shared deterministic function and a separate versioned parser; leave v1literal
validation and its saved outputs/results unchanged. Test tabs/CRLF/Unicode whitespace,
overlapping/repeated occurrences, word/digit/negation changes, zero-width characters,
source/offset/quote tampering and source-size bounds using invented text. Only after freezing
the new code, apply it offline to saved responses as an exposed diagnostic—not a fresh trial,
independent holdout or retroactive qualification. Preserve all hashes and account for the
remaining semantic disagreements separately. No additional provider spending is authorized.

### Local checks and exposed diagnostic
First34checks pass but two huge synthetic parameter strings overflow the Windows
`PYTEST_CURRENT_TEST`environment value during setup. Assign concise explicit IDs rather
than dropping size-bound tests or changing the product limits. Corrected58focused checks
pass4.63seconds,193sources typecheck,301files lint/format,import boundaries and sixbuildpairs
pass. Freeze869f1c1before the actual offline saved-output diagnostic.

Network-denied readback verifies all old source/input/report pins and reproduces every
v1decision. The separatev2parser maps both old invalid responses uniquely:22oldvalid versus
24newvalid,three whitespace-only quotations and seven exact quotations. No model decision
changes and no new ambiguity refusals appear in this exposed sample. Every span is rebuilt
and verified against exact source and raw quote. Original private files hash-identical
before/after; shared ledger remains24used/156remaining/0unsettled. Capture new derived rows
only in an exclusive private directory and publish counts/pins,not source text. This is an
exposed regression diagnostic,not fresh/heldout semantic evidence or a repaired original
qualification. Old13/16validation and semantic disagreements remain unchanged.

## Entry 64 — Freeze a prospective cohort without recycling exposed families
**Files planned:** prospective Revenue preparation contracts, source exclusion validation,
tests and a zero-call private cohort/aggregate. Current model prompt and old studies stay intact.

### Context and decision before implementation
PR116mergede432655with1290quality/128SQLchecks and green main. The opt-in parser's exposed
diagnostic is not fresh evidence. User requested proceeding. Prepare a distinct future
study rather than replaying old provider rows or claiming the parser repair qualifies it.
Shared Gemini24/180consumed; the completed24attempt pilot cannot automatically be extended.

### Before you read on
How do renamed case IDs or imperfect family inference allow an old document back into a
supposedly new cohort? Which exclusion evidence must travel with the frozen schedule?

### Construction plan
Record each prior case's source-family key, context hash and exact provider input hash in
a private pinned exposure inventory; omit all raw text from that inventory. Bind every
inventory to the original source manifest and the actual prior dataset/report references.
Selection rejects cross-source inventories, duplicate source cases and invalid publisher
spans. Exclude declared prior families, exact source contexts and provider inputs, and
prevent repeated contexts/families within the new cohort. Use source development only,
retain original labels and old corpus holdout, cap context length before selection and
limit category concentration. Selection remains a balanced convenience pilot, not a
representative or unseen-model-data claim. Keep the model prompt unchanged to avoid tuning
on old validation disagreements. Explicitly bind the prospective parser version to new code
and define both old/new parser reporting on the same future responses without extra calls.

Freeze dataset, parser/source inventory and24row/twotrial schedule; report the exact shared
allowance snapshot and proposed24attempt forecast, with dispatch authorization false.
Verify disjointness and original artifact pins before/after and save private artifacts only
at a new exclusive path. No provider call or retrospective rescore is part of this batch.

### Actual preparation and feedback
Initial17focused checks pass3.58seconds; after frozen-bundle tampering coverage,33checks pass
6.50seconds.194sources typecheck. The first source preparation refuses in the old model-request
function because historical citation-study documents can exceed20,000characters. Do not relax
that function: retain context/family exclusions for those records and use an absent optional
request fingerprint. Add the existing original reviewer packet to the audit, verify its pinned
inventory, and conservatively exclude its families/contexts too; these overlap the union.

Prepared12new families under fixed12,000character/two-per-category bounds:6answerable/6noanswer,
4calibration/8validation,8categories,max11,770characters. Four exposure inventories exclude
120known families;57old private files remain hash-identical. The new directory is exclusive,
source/target DBs read-only and unchanged. This is a known-exposure inventory,not omniscient
training/exposure detection. Existing prompt/labels/original corpus holdout remain unchanged.

The exact24attempt forecast fits156remaining but dispatch staysfalse. Separately calculate
the declared diagnostic5%two-sided95%zero-error objective:72groups/class,144validationgroups,
plus4calibrationfamilies,twotrials=296attempts. This exceeds remaining156by140before any
other route/failure. The oversized forecast refuses. Preserve the confidence requirement
and explicitly call the12familycohort a prospective diagnostic,not a release-completing study.
No new quota/grant/model request or qualified review is inferred. Final installed/hosted
checks follow before delivery; provider budget remains24consumed/156remaining/0unsettled.

### Installed and publication verification before submission
Installed Revenue34resources match the wheel exactly, with no provider SDKs/other industry
packages. The network-denied installed module reconstructs the selected twelve-case bundle
identically from its private selection/exposure inventories and timestamp. This validates
bundle reconstruction,not the completeness of the original candidate population or truth
of publisher meaning. Recorded executable source inventory still matches every file.
Ruff303files,194typed sources,kept import contracts and sixbuildpairs pass. Publication scans
7files against configuredcredentials/24OlistIDs/20,910originalquestion IDs/510contextprefixes;
all absent,419relative links resolve and source/draft/backlog statuses/dependencies unchanged.
Final hosted checks and postmerge acceptance remain pending;zero provider calls in this batch.

### Exact snapshot-hash scan findings and explicit approval
Initial PR117run40425932890flags two generic-api-key findings in the public forecast's
provider-to-snapshot-hash maps. Compare both to the actual private AllowanceSnapshot
canonical hash; both match and are not credentials. The user explicitly approved these
two exact historical exceptions, separate from the earlier four exceptions. Preserve the
failed run and append only the two observed commit/file/rule/line fingerprints.

Publicly project provider/hash pairs as separate records and retain the original forecast's
canonical digest. Reconstruct both maps and validate equality with the private forecasts.
This changes publication formatting only; snapshot,cohort,source inventory,ledger and actual
forecast arithmetic remain unchanged. No scanner workflow/rule/path exclusion or branch
history rewrite. Repaired full CI remains required before merge.

## Entry 65 — Size and freeze a confidence-target study
**Files touched:** `provider_budget.py`, `confidence_study.py`, semantic request/parser
projection, focused tests, AGENTS and study documentation.

### Context and decision before capture
The user wants to meet the proposed confidence target and explicitly approves320total
Gemini Free attempts. Preserve the existing24consumed and permit296new attempts in the
same ledger. Do not multiply calls on the twelve-family cohort: repeats are not independent
families. At zero errors, the exact two-sided95%boundary needs72families per class; a
single failure at that size exceeds5%. These are marginal per-class intervals, not a
simultaneous95%claim across all classes, slices, models or products.

### Before you read on
How can a budget be increased without letting old clients continue under stale authority,
and how can a larger study avoid turning a convenience sample into a production claim?

### Options and construction
Resetting or cloning the ledger would lose shared consumption. Append one pinned amendment
inside an immediate SQLite transaction instead; require exact prior authorization, settled
attempts and matching consumption. Keep original grant and all attempt rows unchanged,
make amendment rows immutable, require both original and amendment pins in every client,
and reject stale clients. An amendment changes only maximum, effective approval and expiry;
credential association/model inventory remain bound to the original grant. Initialization
still refuses a maximum above180. Invented tests fill the amended320cap, reopen it, compare
all original rows, and verify stale pins, missing pins, wrong counts and outstanding attempts
are denied. This is an owner-authorized increase, never permission inferred from arithmetic.

The population audit initially exhausts a read_targets generator before checking its second
length bound; materialize it once and rerun every bound. The corrected audit finds30known
unexposed families below12kcharacters,69below20k,154below50k. Use a separately frozen50k
study, keeping existing pilot defaults20k unchanged. Select74answerable families first,
then74no-answer families, preferring the least-used category then case hash, with maximum16
per category. Each original publisher span must match the source; each family and exact
context can appear only once. Exclude all four prior exposure inventories and preserve
original corpus holdout. This uses the same pinned source-development corpus and public
publisher references, not new expert labels or a representative sample.

Freeze148cases, four calibration and144validation, with two trials each. Model input has
only original context and question; expected labels, splits and source metadata are local.
Use the unchanged model prompt and opt-in whitespace parser. Count invalid quotations,
abstention, provider failures and missing scheduled rows against the group error objective.
No prompt tuning, replacement sampling, retries or majority votes after observing outcomes.
Publish per-class bounds and coverage separately from release acceptance. A296attempt
study can fail the target; no declaration can guarantee its result in advance.

### Verification before private capture
43focused invented tests pass, including the earlier budget/exposure contracts. Whole-repo
type checking passes195sources before the final CLI amendment pin addition. Ruff formatting
and lint are clean. Actual preparation, source pin checks and provider capture follow; no
new provider call has occurred at this point. Shared original authorization and history
must be reverified immediately before an in-place amendment.

Preparation verified all four original exposure-inventory pins. Their actual union is128
families (the120from three studies plus eight additional reviewer-packet families). Earlier
prose stated120; the retained public aggregate and actual selection used128. The first new
preparation assertion caught that stale prose before any output; corrected the assertion
against the pinned evidence. Actual cohort:148unique families/contexts,37categories with
four cases each, max49,760characters. Original source/database pins remain unchanged.

### Actual execution and installed checks in progress
Source preparation pins b7f46e3; doc-only correction/capture commit4ab3b01 has the same
executable source inventory. Actual148family/296row capture begins after all original
source/DB/exposure pins and credential association match. The in-place amendment preserves
all24original rows and original authorization; a private recovery snapshot is explicitly
historical, never another allowance. Current external configuration requires both pins.

All1311localtests pass472.14seconds. Initial exact-head hosted logs verify1311tests in
four Ubuntu/Windows Python3.12/3.13environments,195typed sources and12buildartifacts each;
Postgres128passes239.48seconds. Both audits,secret scan and metadata pass. Strict invented
replay uses6recordings/2timeouts/zero-provider. Installed80harness/35Revenue resources
match wheels exactly; cohort revalidates with networking denied,no provider SDKs/other
industries. Configured formatter305sources/import contracts pass. A bare whole-tree Ruff
format command also scanned Markdown examples and flagged five preexisting documentation
snippets; use the repository's configured dev.py format-check rather than changing unrelated
historical examples. Lint itself passes. Hosted checks are for the initial head; final
result/documentation changes still need their exact final checks.

An early publisher disagreement and subsequent quotation/provider failures already make
the minimum-size target fail. Continue the fixed diagnostic capture without changing labels,
prompt,parser or denominators. This is evidence of candidate shortcomings, not a reason to
lower confidence or treat repeated trials as new groups. Final accounting/audit follow.


### Completed study and independent audit
All296scheduled attempts complete with no retry/paid fallback. Validation
237/288correct,265decisions,16false accepts,
12false rejects,23failed observations,0missing.
30/144families fail. Calibration8/8.
The target fails; supplementary exact95%upper bounds are
39.59%answerable/24.06%no-answer.
No confidence criterion or label is changed. Recompute the frozen report from saved
observations and revalidate every raw DTO/ledger reservation pair; verify original24rows,
grant,pilot responses/report,source DB/exposure/executable pins. All match.
Known tokens1535206/22845;unknown input/output
0/0,unknown cost
296. Single ledger320/320,0unsettled.

The final budget-specific regression additions pass45focused tests22.37seconds: fresh181/320
initialization is refused before file creation and a stale transport cannot invoke its
provider while the amended ledger still has capacity. These are test-only additions,not
changes to the running capture. Final full matrix will collect1313tests.

Prepare a separate12family exposed development proposal,6perclass,failures/error kinds/
categories balanced;model3.8Flash,one unique<=300characterquote,2048outputtokens. Its24
attempts would require344sharedtotal;no new grant or call occurs. Labels remain private,
all cases explicitly exposed,no qualification claim. The candidate/parser/operator and
append-only amendment must be reviewed/tested/frozen before any future authorized dispatch.
Keep the current320cap and failure evidence intact.

## Entry 66 — Develop on exposed failures under a schedule-bound extension
**Files touched:** provider_budget.py,remediation_development.py,tests,AGENTS and guide.

### Context and decision before capture
PR118merged8817c8a after ten final checks and nine applicable main jobs. Actual1313tests
in four environments plus128SQL. The296attempt study fails:237/288validationcorrect,
30/144failed families,exactperclassupper39.59%/24.06%. The owner explicitly approves344total
for the prepared24attempt development test. Do not rerun/replace the failed final study.

### Before you read on
How can an allowance extension stop a repeated trial or a different model from consuming
the new24slots while retaining every historical grant and reservation?

### Decision and construction
Retain original grant and first320amendment canonical schemas to preserve their hashes.
Add a separate immutable DevelopmentExtension referencing both pins. It binds344maximum,
320starting count,Revenue,3.8Flash,runID and12unique approved request hashes. Refuse before
insertion unless all320prior attempts settled. Immediate transaction serializes grant
extension and reservations. Current clients need all three pins;old code is capped320and
exhausted. Atomic unique(request,trial)slots map to tickets,so a duplicate trial rolls back
without consuming or calling the provider. No generic reset or larger fresh grant.

Implement development_request to compare the exact reviewed system-prompt digest,route,
parameters,schema and original model-only context/question. Parser accepts the actual3.8
route,refuses duplicate JSON keys,inconsistent decisions,multiple/long quotes and ambiguous
or non-whitespace changes. Reuse exact source mapping;do not relax historical parsers.
Frozen private proposal/modelinputs are the source of prompt bytes,not evaluator labels.

The user-approved combined candidate changes model,prompt and output budget together.
That can test whether the candidate is useful on exposed failures,but cannot attribute
causality to any one change. The12families are deliberately exposed development,never a
new holdout. Keep24rowdenominator;bothtrials/allfamilies must match references with valid
citations for the proposed readiness screen. This is not a confidence/release gate.

### Checks and failures during construction
Whole-repo196sources typecheck;Ruff lint/format pass on touched code. Invented regression
checks cover prompt/schema/context/route changes and malformed quotation/JSON cases,plus
320history preservation,24slots,wrongparent/stalepin/foreignscope/duplicates. Actual test
results and private capture follow. No provider call or live ledger extension yet.

Focused52checks pass38.65s after correcting the invented fixture:it initially retained
Olist/FlashLite-only authorization and rightly refused the Revenue/3.8request. Match the
actual approved original model inventory and Revenuecontext;do not weaken production
checks. After immutable slot triggers/request tool-and-system message binding are added,
all14new focused cases pass21.23s.196configured sources typecheck;lint/format pass. Freeze
and commit executable code before applying any live extension or making the24calls.

### Operator failure retained before correction
The first18development slots are reserved and settled but never reach the provider. Their
saved raw responses say Unsupported or invalid Gemini request,model_calls0. Root cause:
operator enabled Flash in admission but constructed GeminiWorker without flash_comparison,
whose defaultfalse rejects3.8in request_payload. I should have preflighted the actual worker
configuration,not only admission/request contracts. Stop the owned parent at a settled
boundary:338consumed,6remaining,0unsettled. Preserve18rows and all charges;no refund or retry.
Initial script and source inventory stay pinned in the old plan;the first run cannot pass
its all24readiness screen. Shell quoting failed on the first attempted stop command,so
write an exact helper file and stop only the inspected owned PIDs once no reservation is
unsettled. No unknown attempt is discarded.

Add development_worker factory with explicit Flash opt-in and an actual request_payload
preflight regression. Mock the selected GeminiTransport to prove worker passes Flashflag
through,with zero network. Freeze a correction record/source inventory for the six untouched
original slots only. Do not retry the18failedslots or treat the mixed-operator result as a
valid fixed-candidate study. Remaining6are all no-answer trial2;they cannot validate positive
citations or repair this development screen. Further spending would require a new scope.

Actual payload preflight also finds the legacy GenerationParameters max_output_tokens512
ceiling,independent of the missing workerflag. Keep old512policy and add a separate
FlashDevelopmentParameters<=2048only for explicitly enabled3.8route;2049andLite2048still
refuse. Regression15cases now pass19.92seconds,including zero-network SDK payload creation
and worker propagation through a mocked selected transport. This checks the real adapter
configuration before consuming any remaining slot. Record both causes,not just the first.

### Completed operationally failed development and audit
The six untouched rows yield2actualtimeouts,1actualunavailable,then3circuit-open denials
before reservation. Parent bound60seconds does not change adapter HTTPceiling30seconds;
keep both timings rather than claiming all attempts ran60seconds. Total21newreservations,
3actualproviderdispatches,24outcomes,no decisions. Ledger341/344used,3remaining,0unsettled.
No18failedslotrerun/refund,circuitbypass or new spending occurs. Three unreserved denied
rows remain failures in the24scheduled denominator. Mixed operator versions cannot score
model development quality;do not call this a failed model or an improved candidate.

Audit revalidates all21request/context/response pin triples,unique slots and absence of
reservations for three circuit denials;original320rows/grant/amendment unchanged.312old
private artifact files remain identical. Historical executable bytes match their pinned
commit with GitLF/workingCRLF handled explicitly;corrected current inventory matches too.
Knownreportedcalls3;unknown token/costfields21/24,knownzero3circuitdenials. Rawcost unknown
is not zero. Constructed actual SDK HTTPtransport/parser regression passes9.99seconds,
verifying3.8route,2048output,one-quote schema,onefakewireexchange and exact source mapping
with no network. This is compatibility evidence,not remoteavailability or semanticquality.
Installed80harness/36Revenue resources equal wheels and the earlier cohort revalidates
networkdenied,no provider SDK/otherindustries. Final exact-head hosted checks follow.


## Entry 67 — Diagnose task mismatch before another model study
**Files touched:** revenue failure investigation, source-selection prototype, OpenRouter canary, tests and study guide.

### Context
The owner asks why the confidence target failed, authorizes following the diagnostic
recommendation and requests detailed engineering notes. They also approve a separate
maximum12attempt OpenRouter Free canary using invented data only, no fallback/retries.
The shared Gemini ledger remains341/344, no authorization to rerun its completed slots.

### Before you read on
If a question asks whether a restriction exists, does a clause expressly denying that
restriction count as an answer? Decide whether the model instruction and reference labels
measure the same thing before deciding that a larger model is the fix.

### Options considered and decision before implementation
Increasing the final sample cannot repair an error rate above the target. Repeating all
failed calls would mix development and qualification and consume an unchanged allowance.
Changing model, prompt and output budget together already failed operationally and could
not isolate a cause even if it had succeeded. Instead, compute disjoint outcomes and
trial-pair diagnostics from saved rows, inspect reference-versus-model passages locally,
then prepare separate task-wording and evidence-interface variants. Keep all proposals
unqualified until a controlled experiment supplies improvement evidence.

### How to build it
Read each frozen cohort case and its two raw responses, retaining the publisher target.
For validation count final correct/wrong/citation-invalid/provider-failed outcomes. Then
cross-tab raw decision correctness with citation validity; never sum overlapping axes.
Pair by case and trial, not by row count. Compare length bands descriptively, without
claiming a causal effect from this convenience sample. Do not publish source passages or
case identifiers. Inspect repeated disagreements locally to find instruction ambiguity.
The existing instruction asks for any explicit answer, whereas annotations identify
category-associated passages: an explicit denial can answer the question without the
category being marked present. Draft a small task-clarification variant separately.

For the evidence-interface prototype, let the model choose source span IDs and copy text
locally from the pinned input. Deterministic copying can eliminate rewritten quotations,
but cannot prove that a selected passage answers the question. Bind catalog and response
to the exact request/input; refuse foreign IDs and changed contexts. Preserve full text,
including Unicode and whitespace. Do not enable this prototype in release/runtime paths.

For OpenRouter, freeze invented inputs, explicit free route and a separate capped ledger.
Preflight the actual HTTP payload and parse a constructed wire response before any live
reservation. Explicitly disable router fallback and require zero prompt/completion/request
prices. Keep authentication private. A remote canary proves transport compatibility only;
it does not authorize sending contracts to a new provider or replacing reference review.

### What went wrong / checks in progress
The previous18local failures were operator errors: admission accepted a configuration the
actual worker rejected, and a legacy output ceiling independently rejected the new request.
Adapter-level preflight now precedes spending. No outcome from the failed run is refunded.
New implementation, tests and real canary results follow; no improvement claimed yet.


### Actual diagnosis, implementation and first remote result
Reanalysis verifies296saved rows,288validation outcomes and exact schedule/response bindings.
Disjoint237correct/28wrong/22citation-invalid/1provider;31raw disagreements overlap three
citation-invalid;19invalid quotes otherwise have correct decisions.142/144pairs repeat raw
decision;15wrongbothtrials. Long35–50kband13citationinvalid+1provider among60trials;shortband
still13wrong decisions.16private disagreement notes are AI proposals,not human annotations.
Full passages/IDs remain private; invented paraphrases explain the public failure classes.
Do not relabel suspicious positive/negative source references to make benchmark pass.

Two opt-in prototypes added:taskwording-only and evidence-interface-only. Catalog covers
allsourcecharacters in300character spans. Bound request/input/route and strict ID parsing
prevent changed-source/fabricated/duplicate selection. Copy exact local source,not model
text. A deliberate invented test shows wrong semantic selection can still pass integrity;
semantic_support stays not_assessed. No runtime/release path selects these prototypes.

Selected explicit free OpenRouter Liquid route from public zero-price/structured-output
metadata;pin actual12invented requests/sourceinventory in separate new ledger. Allpayloads
and fakewire responses preflight before reserve;owned55second parent/45secondHTTPbound,
zero-price ceilings,no redirects/retries/routerfallback. First actualcallHTTP429;stop1/12,
11remaining,0unsettled. Unknown token/costnotzero. LaterreadonlykeymetadataHTTP200Free,
0used/50limit,so429cause unresolved,not proven quotaexhaustion/outage. No contract export.
Gemini341/344and Groq9/12rechecked. Initialcrossledgeraudit used incorrect Groq filename
external-pin.json instead of allowance-pin.json;read failed before changing either ledger.
Correct name/pin checks confirm unchanged counts. This was an audit-path error,not a reset.

Initial79focusedtests pass30.86s;198types pass. CI catches dependency-lock mismatch after
adding optionalOpenRouterextra(reusesexistingHTTP/schema versions). Strictreplayv13rightly
refuses changedlock. Generate separateinventedv14,pin88d688e90b249db3dba90f7dfa630cd66d303a3695c79fdd301bd4d75b1e6745,
preservev1–v13and addv13historicalrefusaltest;83replaytests pass. Never edit oldcapture bytes.
New canary regressions covertimeout/oversize/invalidusage/crashreservation/immutability.
Finalfullsuite and exact-head CI follow. FirstSDKconnector createdonlyPRform;repository
instructions/userauthorize authenticatedAPIfallback,which createsverifiedPR120directly.


Local fullrun55failed/1310passed427.47s:defaultCtemp is under actualC:/.git marker,
so sourceexternalpathguards rightly refuse. Do not delete unrelatedmarker or relaxguard.
VerifyD:/document/.cache/production-agents/s5-temp has noGitancestor;setTEMP/TMPexplicitly
and rerunfullsuite. FocusedCFPB82passes7.91sunderselectedtemp. Installed82harness/37Revenue
resourcesmatchwheels;12actualcanarypayloads/exactUnicodecopy revalidate with networkdenied,
noGoogle/GroqSDKorotherindustries;strictinventedreplay6calls/2timeouts/0provider.


## Entry 68 — Isolate development changes behind settled canaries
**Files touched:** paired_budget.py,provider_budget.py,paired capture/report tests and documentation.

### Context and decision before implementation
PR120merged47be096 with all10checks and nine applicable mainjobs;1365tests/environment,
128SQL. Owner now approves same shared Gemini lifetimecap418for74newattempts:two invented
canaries,then72domaincalls on12exposedCUADfamilies,three variants/two trials. Preserve
three oldunusedbound slots. OpenRouter1/12canary stoppedHTTP429because maximum was a ceiling,
not required traffic. User asks why and authorizes qualitycomparison;noOpenRouterdomainexport.

### Before you read on
How do you prevent old code from using three previously unused slots after appending a new
scope,without resetting the ledger or rewriting prior attempt history?

### Decision and how to build it
Prepare12sourcefamilies before dispatch:6repeated raw disagreements,2citationfailures with
correct rawdecisions and4previouslycorrectcontrols. Balance6answerable/6noanswer and4per
short/middle/longband;onecasepercategory. Selection uses only exposed validation material;
labels remain publisher-relative and unadjudicated. Keep evaluator-onlycases separate from
36model-onlyrequests. Baseline/taskwording/evidenceinterface preserve3.5FlashLite,LOW,512,
temperature0. Rotatevariantorderpercase;reverseintrial2. Freezeall72request/trialpairs.

Append PairedExtension referencing originalgrant,320amendment and344development pins.
Require341settled rows,74unique slots,12casesx3variantsx2trials plus2specific invented
requests. New clients require fifth externalpin;staleclients refuse. A SQL BEFOREINSERT
trigger also requires a matchingnewslot for serial>341,so an old executable cannot consume
the threeoldslots. Newslotsinsertatomicallywithattempts;allhistory remains. Newglobalcap418,
but74slots mean atmost415consumedfrom341;threelegacyunusedslotsremaininaccessible.

Gate domainreservations on two immutable canarypassrecords. A passrequires exactinvented
request,correctstrictJSONinteger,response route and matching settledreservation pin.
Unsettled/wrong/failedcanary cannotunlockdomaintraffic. Localpayloadpreflight uses actual
Geminiworkerconfiguration and pinned SDK before live allowancechange. No retry/fallback.
Any canaryfailure stops before sourceexport. Domainquota/auth/budgetdenial stops;three
consecutive timeouts/unavailable stop and retain missing scheduled rows. Parser/modelquality
failures remain failures and are not replaced. Report pervariant and pairedfamily/control
regressions plus tokens/latency/unknowncost;no confidence/releaseclaim from this small cohort.

### Checks and construction failures in progress
Implementation is being checked on invented fixtures. Actual extension and capture have
not occurred at this point. Preserve previous341rows/grants/slots and original source/report
pins,then independently audit the new response/reservation/schedule pairs after capture.


### Pre-dispatch checks
Initial42budget/development regressions pass101.92s. After longcatalogcanary is added,
8newbudget/report tests pass54.46s and14report/evidence checks pass0.57s. Existing320/344
fixtures remain valid. Whole-repo200sources typecheck,318formattedfiles and import contracts
pass. Actual38requests,including long167IDcatalog,serialize through pinnedGoogleSDK;
a constructedSDKHTTPexchange passes with zero network/provider calls and no ledger changes.
Fix strictmypy errors from an untyped sharedkwargsdictionary by explicittyped requestfields;
do not bypass types. Raw diagnosticJSON now refuses duplicatekeys before extracting decision.
Freeze executablecommit before liveextension and firstcanary. No paidfallback/retry.


### First canary timeout and owner-approved operating-plan change
ActualfirstprobeHTTPtimeout41.07stotal;workerenters7.86s,returns40.64s,parentdidnottimeout.
No domaincall;342/418used,76remaining,0unsettled. Revalidatefirst342receipt/old341rows and
379oldartifactsunchanged. DNSworks,publicHTTPSGoogle404/OpenRouter200,authenticatedmodel
metadataHTTP200in2.34srecognizesFlashLite/generateContent. This narrows to generationpath/
30sHTTPwindow,not provenauthentication/DNSoutage. Do not retryconsumedprobe or claimaccuracy.

Ownerexplicitlyapproves90HTTP/110parent for unusedrepresentativecanary and original72only
ifitpasses,samecap/slots/qualitycriteria. AddimmutableAvailabilityOverridepinnedtofailed
response/report,pairedextension and secondrequest. Newexternalpinrequired;alloldhistory
unchanged. Representativepassmustmatchsettledresponse;domainbarrierneeds that exactpass.
LegacyHTTP30default retained;explicitlongwindowonlyforFlashLite. SeparatePairedWorkerand
PairedExecutionPolicyhandle110parent,becauselegacyExecutionPolicymax60wouldotherwisefail
locallybeforeanynetwork. ActualSDKmockverifiesreadtimeouts30versus90,nofallback/retries.
Initial2availabilityregressions pass19.51s;typecheckerrequiresexplicittransportattribute
annotations forliteralvalidatedtimeoutpath. Freezecontinuationplan/codebeforeunusedcall.
