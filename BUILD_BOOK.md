# Build Book — Production Agent Platform
A journal of the real reasoning behind this build: decisions, options rejected, and things that broke along the way.

## Index

- [Entry 1 — Proposed execution and evidence boundaries](#entry-1--proposed-execution-and-evidence-boundaries)
- [Entry 2 — Real-source data before the first complete demo](#entry-2--real-source-data-before-the-first-complete-demo)

- [Entry 3 — From design notes to a dependency-driven delivery backlog](#entry-3--from-design-notes-to-a-dependency-driven-delivery-backlog)

- [Entry 4 — Recovering from an invisible connector form](#entry-4--recovering-from-an-invisible-connector-form)
- [Entry 5 — Creating the native delivery project](#entry-5--creating-the-native-delivery-project)
- [Entry 6 — Establishing installable package boundaries](#entry-6--establishing-installable-package-boundaries)
- [Entry 7 — Pinning authentic Olist source evidence](#entry-7--pinning-authentic-olist-source-evidence)
- [Entry 8 — Integrating the first wave and defining shared contracts](#entry-8--integrating-the-first-wave-and-defining-shared-contracts)
- [Entry 9 — Adding a current-code study guide](#entry-9--adding-a-current-code-study-guide)
- [Entry 10 — Giving Windows and CI one command path](#entry-10--giving-windows-and-ci-one-command-path)
- [Entry 11 — Isolating local Postgres services and trial state](#entry-11--isolating-local-postgres-services-and-trial-state)
- [Entry 12 — Turning portable checks into hosted CI](#entry-12--turning-portable-checks-into-hosted-ci)
- [Entry 13 — Selecting a free provider and local trace integration](#entry-13--selecting-a-free-provider-and-local-trace-integration)
- [Entry 14 — Moving Gemini calls behind the shared gateway](#entry-14--moving-gemini-calls-behind-the-shared-gateway)

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

## Entry 5 — Creating the native delivery project

Date: 2026-10-11 (Africa/Lagos). Status: native issue hierarchy, milestones and Project created; field population and workflow verification underway.

**Files touched:** delivery plan, backlog manifest, README and Build Book. **Remote artifacts:** [Project 2](https://github.com/users/Protagonist01/projects/2), [root issue 1](https://github.com/Protagonist01/my-production-agentic-systems/issues/1), issues 2–62 and milestones 1–7.

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

Configured Board stages Backlog → Ready → In progress → Review → Done; removed the template's five-item Backlog limit and set In progress to three. Saved By workstream with Area grouping and hierarchy off; saved Blocked with `has:Blocker`, hierarchy off, Area and Blocker columns. Seven views exist. Dates and iteration assignments remain empty pending capacity planning.

Five workflows are enabled: repository open-issue intake, sub-issue intake, initial Backlog, explicitly closed issues → Done, and reopened items → Backlog. Disabled merge → Done, Done → automatic closure, and PR-link status changes; left archive/review automations off. Explicit closure still requires the human/integrator to inspect acceptance evidence. Updated and pinned tracker #1 with the actual Project URL and epic links. H11's O8 dependency is #33, clarified in the tracker and manifest while its connector edit remains pending.

L5 is an administrative task. Its completion evidence is this verified configuration and the published documentation commit, rather than an application implementation PR. F1 #10 and O1 #26 remain Ready. No application work is marked complete.

Published the planning snapshot in [commit 311e807](https://github.com/Protagonist01/my-production-agentic-systems/commit/311e80733e76bd6b9ce857073294000d43be8878). Updated #62 with checked acceptance evidence and the commit link, then closed it. A server read confirmed `state: closed`, `state_reason: completed`; the native closure workflow moved it to Done. Final Board counts: Backlog 59, Ready 2, In progress 0/3, Review 0, Done 1. Restored the unfiltered Backlog after the audit so temporary filters do not hide tasks. The saved board screenshot shows the two Ready tasks and the WIP limit.

Refetched main and used a mixed reset to align local HEAD/index with the documentation commit while preserving the original untracked plans. `git diff --check` passed and no tracked differences remained. Verification covers project administration and planning consistency; no runtime test was run because runtime code does not yet exist.

## Entry 6 — Establishing installable package boundaries

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

The initial uv_build 0.13 series could produce wheels, but uv 0.11.1 failed while unpacking its source archive with `malformed pax extension`. Rather than changing the user's installed tool, pinned each member's backend to `uv_build==0.11.1`, matching the exercised runner. All six source archive → wheel builds then passed. This replaces step 3's initial 0.13-series selection. Source/binary distribution artifacts remain ignored.

### Verified results

On Windows/Python 3.13.4/uv 0.11.1: 12 pytest checks passed; both import contracts kept; Ruff lint and formatting passed; six source archives and six wheels built. A new temporary virtual environment installed the locked workspace and imported all six members. A clean harness-only installation is checked separately before publication. Static imports are covered; reflective imports are an explicit limitation, not a security claim. No model evaluation, database isolation or CI pass is implied by these foundation checks.

The separate harness-only sync installed exactly the shared member and confirmed `find_spec('olist_support') is None`. F1 was pushed in commit c91df0f and [PR #63](https://github.com/Protagonist01/my-production-agentic-systems/pull/63) was created through the signed-in browser after the user confirmed the connector form was invisible. It remains open for review; no merge or implementation completion is claimed.

## Entry 7 — Pinning authentic Olist source evidence

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

## Entry 8 — Integrating the first wave and defining shared contracts

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

Pinned Pydantic 2.14.1 from current PyPI metadata; uv locked its transitive dependencies. The first 27 contract tests passed; the combined suite passed 43 tests, both import contracts and formatting. The example emitted a synthetic/offline_fake report with preserved context/versions, exact-text score and zero fake cost. ScoreResult values remain finite but are not limited to 0–1: latency/cost metrics need other ranges. Static type checking is underway using an ephemeral, exactly pinned mypy 2.4.0; it does not add a new permanent root command before F3.

Moved the Agent/ModelGateway protocols into the public contracts module so domain agents do not need to import evaluator-only objects just to implement the interface. The fake agent revalidates the gateway response. Re-ran the combined suite after these changes: 43 passed; strict mypy found no issues in four source files; both import contracts kept; Ruff lint/format passed. All six source archives/wheels built. A separate clean environment installation/example is being checked before publication. Only Windows/Python 3.13.4 is exercised; Linux/Python 3.12 checks remain F5.

The separate clean locked environment installed all six workspace members plus Pydantic, then ran the example successfully: completed, fake_case_correct=1, mode=offline_fake. Rebuilt all six archives/wheels after the final protocol changes. `uv lock --check` and `git diff --check` passed. Preparing a review PR, with only F2's planned scope and current-status corrections; the original untracked templates/archive stay outside the commit. No new worktree, provider request, database or live evaluation was needed.

Published F2 code in commit 65ff503 and [PR #66](https://github.com/Protagonist01/my-production-agentic-systems/pull/66), based on the integrated main. The committed CLI run also passed and reports revision 65ff503 with the actual lock hash. Updated #11's acceptance/evidence, assigned the repository owner and left it open in Review; the merged-PR checkbox remains unchecked. This shared baseline must be reviewed/merged before dependent worktrees use it. Existing Git credentials lack Projects scopes, so board changes use the signed-in browser rather than broadening access.

The issue sidebar status interactions did not retain the intended value; the refreshed board showed F2 under No Status. Used the card's More actions → Move to column → Review instead, then verified the native board: Backlog 58, Ready 0, In progress 0/3, Review 1 (F2), Done 3 (F1, O1, L5). Saved a screenshot showing the Review/Done cards. PR #66's server-side diff matches all 17 intended local files; tracked changes are clean and original untracked documents are preserved. F2 remains unmerged for shared-interface review.

## Entry 9 — Adding a current-code study guide

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

## Entry 10 — Giving Windows and CI one command path

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

## Entry 11 — Isolating local Postgres services and trial state

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

Built all six archives/wheels and verified the harness wheel contains both SQL resources. Installed that wheel into a separate fresh virtual environment: pinned Psycopg imported, both packaged SQL files loaded, and foundation fixture hash was `36f744ed8efb28f29fb42a24da4cc3dc8a7ef1b3fa6f41e88133bc396e07f938`. This verifies packaged-resource loading without editable source. Recorded implementation in commit 65dcefb; current guide explains all seven meaningful source files and seven test files with a dedicated Postgres chapter. A Windows default text decode failed on the guide’s UTF-8 quotation marks; switched document scripts to explicit UTF-8 and repaired only newly inserted non-UTF8 bytes. Final source/reference audits passed.

### Review publication

Published [PR #69](https://github.com/Protagonist01/my-production-agentic-systems/pull/69) after pushing code and code/runbook documentation. Attached it to this chat. Updated #13 with all three acceptance criteria checked, 64 offline plus 11 required database results, fixture/image/code versions and limitations; left merged-PR unchecked and issue open. Native Project move to Review was read back after the asynchronous save; screenshot under ignored artifacts shows F4 Review and F3 Done together. Ordinary db-down stopped only this checkout’s test service, retaining its named volume/configuration; temporary integration projects/volumes were removed by their fixture cleanup. All 77 immutable source ranges and document references resolve. F4 is review-ready, not merged/completed.

## Entry 12 — Turning portable checks into hosted CI

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

Committed initial F5 source as b9a3d4c, then added a clearly labelled disposable forbidden import in 826cb6c. Local imports exited 1 with Harness cannot import industry packages BROKEN and the exact ci_failure_probe → olist_support edge. Published PR #70 with an explicit not-ready/pending-hosted-evidence body, attached it to the chat and left #14 In progress. Hosted failure/pass evidence remains pending; do not remove the probe until its actual quality-job result is observed.

The first hosted run 38638985538 completed failure: all four quality jobs and CI gate failed, while Postgres, both dependency audits, Gitleaks and PR metadata passed. Its downloaded quality log showed mypy's import-untyped rejection of the forbidden harness dependency, before the architecture checker ran. That proves fail-fast CI, but not the specific architecture stage promised. Replaced the temporary control with an Olist → CFPB import in domain code, outside the explicitly declared mypy scope. This tests the architecture stage without weakening or suppressing type checks. The second run must show Industry packages cannot import one another BROKEN before removing the control.

Verified the [second negative run 38640533520](https://github.com/Protagonist01/my-production-agentic-systems/actions/runs/38640533520), head 9e7969418ca60913fc74602d77ad78e4dd63a468: all four quality jobs and CI gate failed; the downloaded Ubuntu 3.13 log contains Industry packages cannot import one another BROKEN and the exact olist_support.ci_failure_probe → cfpb_triage edge. Postgres, both dependency audits, Gitleaks and metadata passed. Removed the disposable probe only after this evidence. Final cleaned hosted checks are next; no green result is assumed.

### Clean hosted verification

[Run 38641578564](https://github.com/Protagonist01/my-production-agentic-systems/actions/runs/38641578564), head 9cbc8ad024871c656357eb3ccd7d32d8ae63d407, passed all ten jobs after removing the control. Four actual Ubuntu/Windows Python 3.12/3.13 cells passed setup, interpreter assertion, shared checks, fake example and six builds; Ubuntu Postgres, both dependency audits, Gitleaks, PR metadata and CI gate also passed. Downloaded job logs confirm 77 offline and 11 database tests. Refreshed current-state docs and study guide with eight core source/eight test files, checked 87 immutable source ranges and preserved original findings. Local GitHub DNS/browser connection reset temporarily blocked read-back; MCP check-run reads independently confirmed success. Native Project update remains pending until its page is usable. Final documentation commit receives the same workflow; verify that exact head before presenting review-ready completion.

### Native Review and final publication

Documentation head eef5e9adb70462e21bb3e855cba5f4824205876f passed all ten jobs in run 38643732590. Rewrote PR #70 around the delivered behavior, real negative/positive evidence and limits; updated #14 to Review with all three acceptance criteria checked, leaving merged-PR unchecked. Browser connection recovered, but the semantic filter fill stalled; the visible AX input setValue plus Return worked. Filtered F5, used More actions → Move to column → Review, waited for saved card/count, then cleared/applied the temporary filter. Native board now shows Backlog 55, Ready 0, In progress 0/3, Review 1 and Done 6. Saved screenshot artifacts/f5-review-board.png shows F5 Review and F4 Done together. No access/permission expansion, network protection change or unrelated cleanup was required. This final documentation-only correction will be pushed and its exact-head CI/PR diff read back before handoff; implementation source remains b9a3d4c and the 87 audited ranges are unchanged.

## Entry 13 — Selecting a free provider and local trace integration

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


## Entry 14 — Moving Gemini calls behind the shared gateway

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
