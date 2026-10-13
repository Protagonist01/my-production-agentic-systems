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
