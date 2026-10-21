# Revenue integrity

Updated 2026-10-21. R1–R4 are merged and verified in #87/#88. R5/R6 is the current implementation candidate; fresh R7 release evidence remains pending.

## Delivered application

Real-contract extraction plus a separately reported billing simulation with deterministic calculations, approval-bound changes and conflict-safe compensation.

Framework direction: LangGraph with thin event orchestration where needed. Verify current integrations and pin tested versions under H1 before implementation. The application includes a usable API/operator workflow, scoped access, traces and an operational guide.

Contract extraction with citations → independent deterministic term reconciliation → findings and benign exception handling → limited hygiene/approved billing action → transactional ledger → audited digest. Compensation refuses stale-state overwrite.

## Data and boundary

Original CUAD contracts/annotations and suitable selected agreements if needed. Split contract/template families. Billing and CRM state is constructed; optional Maven data is fictional hardware-company CRM.

Report original-contract extraction independently from hybrid/generated billing reconciliation. Expected commercial terms and money/date schedules are reviewed outside the production engine. No actual recovered-revenue claim.

Each importer produces provenance/checksum/use notes and validated agent-visible data. Independent expected labels and hidden outcomes live in scorer-only storage. Development/regression/holdout sets are versioned and related records remain grouped. Original, hybrid and synthetic/adversarial results are separate.

## Implementation tasks

### R1: Build original-contract extraction corpus and family-level holdout

Priority: P1; provisional size M; prerequisites: H5. Status: Done.

Acquire CUAD plus suitable EDGAR agreements if needed; preserve original context and reviewed field/span labels. Keep constructed clauses in separate sets.

Acceptance evidence:

- [ ] Manifest records provenance, permissions and real-field coverage gaps.
- [ ] Contracts/templates do not cross development/holdout family boundaries.
- [ ] Numeric/citation gold labels are reviewed independently from extractor output.

### R2: Generate billing worlds with leakage and benign exceptions

Priority: P1; provisional size M; prerequisites: R1. Status: Done.

Seed accounts/subscriptions/invoices and construct seat/price/uplift/ramp/amendment cases. Maven, if used, is labeled a fictional hardware CRM fixture.

Acceptance evidence:

- [ ] Injected labels match independently hand-checked money/date examples.
- [ ] Benign ramps/credits/amendments are first-class negative cases.
- [ ] Hidden should-be schedules and leakage labels cannot be read by the agent.

### R3: Extract reusable access mechanisms from two demonstrated consumers

Priority: P1; provisional size M; prerequisites: O4, R2, F2. Status: Done.

Compare Olist and Revenue tool/catalog needs; move only common scope/registry/write mechanism into harness/access with migration contracts.

Acceptance evidence:

- [ ] Shared code names no domain-specific refund/invoice rules.
- [ ] Olist still passes its contracts after migration and Revenue has its own rules.
- [ ] In-process tools remain testable; MCP adapter exposes the same contracts when added.

### R4: Implement cited term extraction and independent reconciliation engine

Priority: P1; provisional size L; prerequisites: R1, R2, H10. Status: Done.

Build extractor/verifier and exact money/date/amendment reconciliation. Evaluate gold-terms and extracted-terms paths independently.

Acceptance evidence:

- [ ] Gold-terms tests catch logic bugs without invoking a model.
- [ ] A citation's existence alone does not validate the commercial meaning.
- [ ] Original extraction and hybrid end-to-end errors are separated in reports.

### R5: Implement approval-bound changes, ledger and conflict-safe compensation

Priority: P1; provisional size M; prerequisites: R3, R4, F4. Status: In progress.

Allow limited CRM hygiene, require approval for billing/merges, bind exact payload/version, enforce stable operation keys and compensating rollback.

Acceptance evidence:

- [ ] Stale/reused approval and unauthorized writes are blocked.
- [ ] Retry, duplicate webhook and partial batch failure cannot create duplicate effects.
- [ ] Compensation appends a ledger entry and refuses to overwrite an intervening legitimate change.

### R6: Deliver approval UI, digest and event-driven orchestration

Priority: P1; provisional size L; prerequisites: R5, H8. Status: In progress.

Build usable findings/review interface and ledger-reconciled digest; add thin Inngest event/sweep/approval wrappers after confirming current SDK support.

Acceptance evidence:

- [ ] Found/proposed/approved/applied/rejected simulated dollars are distinct and reconcile.
- [ ] One owner per wait/checkpoint; wrapper retry is idempotent.
- [ ] API/UI handles review rejection, stale data and long waits visibly.

### R7: Publish real extraction and simulated reconciliation release results

Priority: P1; provisional size M; prerequisites: R6, O8. Status: Backlog.

Evaluate precision, case/dollar-weighted recall, benign false alarms, unsafe effects, independent compensation and engine/catalog ablations.

Acceptance evidence:

- [ ] Real-source and synthetic results are separate; no real recovered revenue claim.
- [ ] Per-category results and completed/incomplete cases are visible.
- [ ] Release manifests, threat model, failure log, runbook and fresh evidence satisfy gates.


## Evaluation and release

Field/span extraction accuracy; case/dollar-weighted simulated recall and precision; benign false alarms; found/proposed/approved/applied/rejected simulated amounts; unsafe/duplicate effects; compensation correctness.

Gate: Real extraction and synthetic reconciliation results separated; independent gold-terms tests; benign exceptions handled; unauthorized changes blocked; ledger totals and safe compensation verified.

Use the shared strict-replay/fresh-evaluation/monitoring boundaries. Release requires merged implementation, independent case/state checks, complete fresh evidence and required fault cases. No critical observed violation can be hidden by improved averages.

[Architecture](README.md) · [Delivery plan](project-management.md) · [Backlog](backlog.json)


Current implementation commands and exact evidence: [source preparation](data/revenue-source.md), [billing worlds](revenue-billing-worlds.md), [read-only reconciliation](revenue-reconciliation.md), [approved operations](revenue-operations.md). Original extraction semantic accuracy and real recovered revenue are not established by these offline mechanisms.
