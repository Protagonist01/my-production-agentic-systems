# Build Book — Production Agent Platform
A journal of the real reasoning behind this build: decisions, options rejected, and things that broke along the way.

## Index

- [Entry 1 — Proposed execution and evidence boundaries](#entry-1--proposed-execution-and-evidence-boundaries)
- [Entry 2 — Real-source data before the first complete demo](#entry-2--real-source-data-before-the-first-complete-demo)

- [Entry 3 — From design notes to a dependency-driven delivery backlog](#entry-3--from-design-notes-to-a-dependency-driven-delivery-backlog)

- [Entry 4 — Recovering from an invisible connector form](#entry-4--recovering-from-an-invisible-connector-form)

## Entry 1 — Proposed execution and evidence boundaries

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

## Entry 2 — Real-source data before the first complete demo

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


## Entry 3 — From design notes to a dependency-driven delivery backlog

Date: 2026-10-11 (Africa/Lagos). Status: delivery documentation prepared; issue/board creation awaits verified server results. Supersedes the proposal-only execution status in Entries 1–2; their runtime checks remain unexecuted.

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

## Entry 4 — Recovering from an invisible connector form

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
