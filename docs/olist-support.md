# Olist support

Accepted scope, updated 2026-10-12. O1's authentic version-7 source snapshot is acquired and profiled. O2 adds [private order aggregates and conservative as-of views](data/olist-orders.md); no refund application or model evaluation result exists yet. See [source handling and commands](data/olist-source.md) and [checksums/schema/missingness manifest](data/olist-v7-manifest.json).

## Delivered application

A usable e-commerce application with authentic order context, policy-enforced refunds, durable review, restart recovery and independently verified results.

Framework direction: LangGraph. Verify current integrations and pin tested versions under H1 before implementation. The application includes a usable API/operator workflow, scoped access, traces and an operational guide.

Request → scoped historical order view → policy and bounded proposal → validated refund/reship or durable review → exact-action approval where needed → committed ledger → truthful reply.

## Data and boundary

Anonymized historical Olist orders, items, payments, delivery observations and reviews. Acquire a pinned source snapshot and record source/use conditions; preserve Brazilian currency and Portuguese or reviewed translations.

Support messages, refund/reship policy and expected actions are constructed. Hide facts not yet available at the request's as-of time. Use controlled transactions, never claim these are Olist's observed refund decisions.

Each importer produces provenance/checksum/use notes and validated agent-visible data. Independent expected labels and hidden outcomes live in scorer-only storage. Development/regression/holdout sets are versioned and related records remain grouped. Original, hybrid and synthetic/adversarial results are separate.

## Implementation tasks

### O1: Acquire Olist snapshot and validate source provenance/use conditions

Priority: P0; provisional size S; prerequisites: none. Status: Done. Original PR #64 and integration PR #65 are merged; main a665d3d passed post-merge source verification and the combined 16-test suite. Issue #26 is closed as completed.

Obtain original Olist source via documented access; record checksum, version, dates, language, currency, attribution/use conditions and required files.

Acceptance evidence:

- [x] Manifest and repeatable local acquisition instructions exist; raw files are outside Git.
- [x] Source publisher/version, schemas and missing values are recorded. Currency/timezone remain explicitly unverified.
- [x] Local noncommercial handling/export limits and credential-free invented test-fixture strategy are explicit; CI implementation remains F5.

### O2: Build orders_360 with correct joins and historical as-of views

Priority: P0; provisional size M; prerequisites: O1, F2. Status: In progress.

Import/aggregate orders, items, payments, delivery and reviews at declared grain; produce scoped snapshots that expose only facts known at case time.

Acceptance evidence:

- [ ] Key/cardinality/totals checks detect duplicate join inflation.
- [ ] Future delivery/review facts cannot leak into an earlier request view.
- [ ] Currency, missingness, provenance and Portuguese/translation handling are preserved.

### O3: Write refund/reship rules and independently reviewed case sets

Priority: P0; provisional size M; prerequisites: O2. Status: Backlog.

Version policy, eligibility/review rules and source-grounded support messages. Create development/regression/holdout splits grouped by order.

Acceptance evidence:

- [ ] Expected actions come from reviewed policy examples independent of runtime implementation.
- [ ] Original records, hybrid messages and adversarial edits have separate source labels.
- [ ] Case evidence includes valid refund, over-limit, missing-data and genuinely ambiguous outcomes.

### O4: Implement scoped order tools and transactional refund ledger

Priority: P0; provisional size M; prerequisites: O2, O3, F4. Status: Backlog.

Build typed reads/writes on the controlled business backend; enforce scopes, per-order/run limits and stable tenant/business-operation idempotency.

Acceptance evidence:

- [ ] Authorized refund changes state once; duplicate event in a new run returns the original result.
- [ ] Over-limit, unauthorized and payload-mismatched repeated-key requests cannot write.
- [ ] State transition and audit/ledger are consistent after transaction failure or timeout-after-commit.

### O5: Build the LangGraph workflow with bounded reasoning and validation

Priority: P0; provisional size M; prerequisites: O4, H2, H4. Status: Backlog.

Implement intent/context/policy/proposed-action/tool/result flow, checkpointing and step limits. Responses reflect actual committed state.

Acceptance evidence:

- [ ] Refund/status/review paths execute against source-grounded context.
- [ ] Model/tool input injection cannot relax code-enforced write rules.
- [ ] Claiming a successful refund without committed state fails output verification.

### O6: Implement durable review and exact-action approval/resume

Priority: P0; provisional size M; prerequisites: O5. Status: Backlog.

Persist review evidence and reviewer decisions. Bind approval to action payload, tenant/actor and record version; resume without restarting side effects.

Acceptance evidence:

- [ ] Human can inspect evidence, approve/reject and see the audited decision.
- [ ] Stale approval or changed record requires re-evaluation rather than writing.
- [ ] Restart preserves review state; repeated approval/resume cannot refund twice.

### O7: Provide authenticated API and usable support/review interface

Priority: P1; provisional size M; prerequisites: O6, H8. Status: Backlog.

Expose request/status/review routes, tenant/role checks and a usable operator interface. Include error/loading/empty states and health diagnostics.

Acceptance evidence:

- [ ] Complete request-to-review-to-outcome flow works through the application.
- [ ] A different tenant/role cannot read a case, approve or invoke writes.
- [ ] UI accurately shows pending, failed and committed actions and evidence.

### O8: Verify crash recovery and publish the first complete release evidence

Priority: P0; provisional size M; prerequisites: O7, H10, H7, F5. Status: Backlog.

Run state-based Olist scorers, commit-timeout/crash/restart scenarios, fresh held-out evaluation and a three-trial reliability subset; publish model card/runbook.

Acceptance evidence:

- [ ] State checks show no duplicate/over-limit/unauthorized effects across fault tests.
- [ ] Report separates source-grounded and synthetic/adversarial cases, review burden and incomplete results.
- [ ] Release artifact contains source/split/code/scorer manifests and a reproducible operational walkthrough.


## Evaluation and release

Eligible-case autonomous completion; required/unnecessary review; invalid/duplicate refund effects; truthful committed outcomes; fresh three-trial correctness; provider cost/latency.

Gate: Valid refund once; excessive/unauthorized action blocked; correct review with evidence; timeout after commit and restart cannot duplicate effects; real-source provenance and fresh held-out results.

Use the shared strict-replay/fresh-evaluation/monitoring boundaries. Release requires merged implementation, independent case/state checks, complete fresh evidence and required fault cases. No critical observed violation can be hidden by improved averages.

[Architecture](README.md) · [Delivery plan](project-management.md) · [Backlog](backlog.json)
