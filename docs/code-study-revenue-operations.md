# Study the Revenue approval and compensation boundary

This chapter covers the constructed R5 backend: closed operation contracts, its Revenue-owned Postgres schema and transactional store, focused shape/scope checks and actual database witnesses. It excludes provider quality, real CRM or payment infrastructure, production identity systems and R6 interface/event implementation. A passing database witness establishes the tested invented behavior, not an exhaustive security audit.

Read [the operating rules](revenue-operations.md), [R4 arithmetic](code-study-revenue-engine.md) and [shared exact scopes](code-study-access.md) first. Build Book Entry 32 records construction of the combined R5/R6/S1 delivery. Inspected source commit `2688d82f3c66fa5767670c63e9872e928beb756a`, dated 2026-10-21. Final focused verification passed 30 checks in 165.90 seconds on Python 3.13.4: 11 offline contract checks and 19 required actual-Postgres cases. Ruff check/format passed the four owned Python files; strict mypy passed both new source modules. Parent combined full-suite and hosted acceptance remain separate.

## Follow one invented correction

Trusted bootstrap enrolls an invoice issued for 9,000 SIM minor units, together with a public constructed billing input specifying two seats at 5,000 each. The R4 result is 10,000, so the signed adjustment is +1,000. This is a simulated adjustment of 10.00 SIM, not recovered real money.

1. The operator receives a server-created `RevenueGrant` naming the invoice and capabilities. `ChangeCommand` names its tenant, stable business-operation identity, expected version zero and exact proposed 10,000 total. An arbitrary browser amount such as 9,999 fails server recomputation.
2. `propose` serializes and validates both closed objects, checks scope before opening storage, takes the operation advisory lock and resolves affected records under row locks. `_change` reconstructs R4 input using immutable source terms and the current recorded amount. Missing/conflicting facts, unsupported calculation, no change or an absolute adjustment above 10,000 blocks the proposal.
3. The stored proposal binds the canonical command SHA256, proposer, original signed adjustment and aware creation/expiry timestamps. A new run ID is not a new operation. Repeated delivery of the same proposal returns its original representation; a changed command under that key fails.
4. A distinct reviewer calls `review`. Scope, identity, expiry and the original command hash are checked. Approval revalidates current facts and record versions. Rejection has no business effect and remains possible for stale records. An identical repeated decision is idempotent; it cannot become the opposite decision.
5. `apply` locks the proposal and operation, checks for a previously committed receipt, requires a still-valid separate approval and reruns `_change`. The amount update, version increment and receipt insert share one transaction. There is no committed state without its receipt through this application path.
6. A lost response after commit is recovered by looking up the stable tenant/operation receipt. It retains the original actor, reviewer and run. Returning it does not create another invoice change or manufacture a new observation timestamp.

## Contract anatomy

[`operation_contracts.py`](../projects/revenue-integrity/src/revenue_integrity/operation_contracts.py) imports the harness `Contract` and `ResourceScope`; it contains no provider SDK. `RevenueGrant.require` chooses the exact invoice/account ID set and delegates conjunction checks to the shared predicate. A matching text ID in the wrong resource kind does not supply authority. Grants are supplied by trusted composition, not parsed from model instructions.

`ChangeCommand.shape` checks a four-boolean presence tuple against the selected kind. An invoice correction has only its proposed amount; an account merge has a target ID and target version; note trimming has no free-text replacement field; compensation has only the original-operation reference. This prevents accidentally interpreting one operation's optional fields as another operation. Strict wire models reject booleans masquerading as money/version integers and unknown fields.

`RevenueRecord.shape` separates invoices from accounts and binds an optional invoice source snapshot to its tenant/account. Missing source facts may be enrolled for an unresolved display, but `_change` refuses to turn them into a correction. The original dataset remains separate from evaluator labels. `Proposal` records a signed historical adjustment so a later digest does not infer the proposed amount from already changed state. `Receipt` retains complete before/after state and any merge target snapshot for compensation checks.

## Database and transaction anatomy

[`operations.sql`](../projects/revenue-integrity/src/revenue_integrity/operations.sql) makes tenant/resource and tenant/operation identities unique. A unique original-operation reference prevents a second compensation under a new operation key. Ordinary effects have a null reference and do not collide with one another. The ledger ID is deterministic from tenant/operation identity; the receipt's run ID remains the original execution observation.

`setup` reads the packaged SQL, obtains a schema advisory lock and compares the version/digest with the immutable pin. It grants only the required Revenue schema/table/column privileges. Runtime code cannot update the stored command hash, update/delete existing ledger rows or create objects in the Revenue schema. This protects the application database role from accidental destructive statements; it is not a sandbox against a compromised connection factory or administrator.

`_connection` owns the database connection, row shape and timeouts. A public method enters an explicit transaction even though the connection uses autocommit outside it. Advisory operation locks serialize duplicate requests; deterministic resource-row ordering prevents opposing two-account operations from choosing inconsistent lock order. The affected record version is checked again while locked, rather than trusting a pre-read UI value.

`_proposal` validates the document and compares its closed command digest with the immutable stored hash. `_receipt` validates the saved payload and binds its tenant/operation. Reads filter exact resources before returning records, proposals or ledger receipts. Target-account data also requires scope. Raw SQL/database credentials remain trusted; this layer provides no general user authentication.

## Compensation is a new controlled effect

`_change` handles compensation by loading the original immutable receipt, refusing to compensate another compensation or an already compensated effect, and locking the same records. It requires the complete current record to equal the original after-state. Version equality alone would miss a changed field; value equality alone would miss an intervening change later restored to the same amount. For an account merge, the saved target snapshot must also remain unchanged.

The inverse restores original business fields at `current.version + 1`, with a new approved proposal and a new ledger receipt. It does not erase the original effect or reduce the version counter. Invoice correction eligibility and compensation authorization remain distinct: undoing an approved correction deliberately restores its prior amount, so it must not be silently reclassified as a new R4-supported correction.

`crm_trim` has no replacement-note input: it computes only `before.note.strip()`. Repeated successful delivery returns the original receipt. Removing already absent whitespace is a no-change review result. Reversing the trim requires a new approved compensation; the automatic hygiene capability cannot restore or rewrite arbitrary note content.

## Failure witnesses and limits

The focused tests use only invented data and owned disposable Postgres services. They exercise closed payloads, exact scope and tenant denial, independent reviewer requirements, wrong proposed totals, missing/conflicting source facts, the absolute cap, stale versions, duplicate/racing deliveries, partial-batch retries, before/after-commit failures, actual process exit, immutable ledger permissions, expiry and compensation conflicts. Results belong to the final verified source snapshot and are recorded after the commands complete.

**Design limitation:** an account merge creates only a bounded alias link and preserves invoice ownership; it is not full CRM field consolidation. **Design limitation:** stored source facts and enrollment are trusted administrator inputs. **Not assessed:** production account provisioning, distributed authentication, real provider extraction quality, financial controls beyond this demo policy and high-scale performance. The browser/event layer must derive grants and wake this store rather than implement a second policy/approval authority.

## Practice explaining the design

- Explain why business-operation identity survives a new run ID, and trace the after-commit response-loss path. A strong answer names the advisory lock, unique ledger key, original receipt and transaction boundary.
- Explain why an approved 500.00 → 550.00 SIM correction may pass a 100.00 cap, but a 199.99 → 300.00 correction cannot. The limit is absolute adjustment, with no reviewer override.
- Describe a compensation that would incorrectly pass an amount-only comparison after an intervening change. Show why the complete snapshot and version checks reject it.
- Explain why a literal CUAD citation cannot authorize an invoice write and identify the independent stored billing facts used by R4.
- Change the demo policy to allow a second automatic CRM field. Name the contract, eligibility calculation, scope, receipt and compensation witnesses that would need deliberate review; merely adding a string to the UI is insufficient.


## Verified source map

| Block | Boundary to explain |
|---|---|
| [RevenueGrant](https://github.com/Protagonist01/my-production-agentic-systems/blob/2688d82f3c66fa5767670c63e9872e928beb756a/projects/revenue-integrity/src/revenue_integrity/operation_contracts.py#L17-L41) | Exact kind/capability membership; trusted identity composition |
| [RevenueRecord](https://github.com/Protagonist01/my-production-agentic-systems/blob/2688d82f3c66fa5767670c63e9872e928beb756a/projects/revenue-integrity/src/revenue_integrity/operation_contracts.py#L44-L76) | Invoice/account shapes and source identity |
| [ChangeCommand](https://github.com/Protagonist01/my-production-agentic-systems/blob/2688d82f3c66fa5767670c63e9872e928beb756a/projects/revenue-integrity/src/revenue_integrity/operation_contracts.py#L79-L107) | Closed per-kind payload presence |
| [Proposal and Receipt](https://github.com/Protagonist01/my-production-agentic-systems/blob/2688d82f3c66fa5767670c63e9872e928beb756a/projects/revenue-integrity/src/revenue_integrity/operation_contracts.py#L110-L142) | Signed historical adjustment and immutable effect observations |
| [Setup and enrollment](https://github.com/Protagonist01/my-production-agentic-systems/blob/1bb4579dd5c9b38c851e131301d4de51ea3cedcc/projects/revenue-integrity/src/revenue_integrity/operations.py#L34-L82) | Immutable SQL pin and trusted bootstrap |
| [Typed loaders](https://github.com/Protagonist01/my-production-agentic-systems/blob/1bb4579dd5c9b38c851e131301d4de51ea3cedcc/projects/revenue-integrity/src/revenue_integrity/operations.py#L112-L184) | Persisted identities and canonical payload hash |
| [Locks and policy](https://github.com/Protagonist01/my-production-agentic-systems/blob/1bb4579dd5c9b38c851e131301d4de51ea3cedcc/projects/revenue-integrity/src/revenue_integrity/operations.py#L187-L281) | Deterministic rows, R4 facts, cap and compensation snapshot |
| [Propose and review](https://github.com/Protagonist01/my-production-agentic-systems/blob/1bb4579dd5c9b38c851e131301d4de51ea3cedcc/projects/revenue-integrity/src/revenue_integrity/operations.py#L283-L356) | Exact operation identity and separate reviewer |
| [Commit and apply](https://github.com/Protagonist01/my-production-agentic-systems/blob/1bb4579dd5c9b38c851e131301d4de51ea3cedcc/projects/revenue-integrity/src/revenue_integrity/operations.py#L358-L435) | Atomic state/receipt and response-loss recovery |
| [Automatic trim](https://github.com/Protagonist01/my-production-agentic-systems/blob/1bb4579dd5c9b38c851e131301d4de51ea3cedcc/projects/revenue-integrity/src/revenue_integrity/operations.py#L437-L467) | Surrounding whitespace only |
| [Read and sweep](https://github.com/Protagonist01/my-production-agentic-systems/blob/1bb4579dd5c9b38c851e131301d4de51ea3cedcc/projects/revenue-integrity/src/revenue_integrity/operations.py#L469-L570) | Scoped output and one deadline owner |
| [Offline tests](https://github.com/Protagonist01/my-production-agentic-systems/blob/2688d82f3c66fa5767670c63e9872e928beb756a/tests/test_revenue_operation_contracts.py#L16-L92) | Denial before connection and closed strict values |
| [Approval tests](https://github.com/Protagonist01/my-production-agentic-systems/blob/2688d82f3c66fa5767670c63e9872e928beb756a/tests/integration/test_revenue_operations.py#L127-L308) | Actual auth, facts, versions, compensation and merges |
| [Recovery tests](https://github.com/Protagonist01/my-production-agentic-systems/blob/2688d82f3c66fa5767670c63e9872e928beb756a/tests/integration/test_revenue_operations.py#L312-L420) | Process exit, expiry, role restrictions and cap boundary |
| [SQL resource](https://github.com/Protagonist01/my-production-agentic-systems/blob/2688d82f3c66fa5767670c63e9872e928beb756a/projects/revenue-integrity/src/revenue_integrity/operations.sql#L1-L10) | Tenant-operation uniqueness and one compensation |

Read methods load tenant-local proposal or receipt documents before filtering exact resources for return. This is trusted local database composition, not database row-level security or an OS isolation guarantee. No unauthorized record is returned by the application grants; direct SQL credentials remain trusted.


## Follow-up: saved scope and consistent views

At source `1bb4579dd5c9b38c851e131301d4de51ea3cedcc`, two targeted actual-Postgres regressions passed in 98.53 seconds; the other 19 database cases were deselected. This follow-up is separate from the earlier complete 30-case focus run. Ruff passed the changed source/test files and strict mypy passed both operation modules.

**Verified bug, fixed:** saved proposal lookup originally used membership in either invoice/account grant set. New-effect calculation checked the stored resource kind, but an idempotent proposal/review return could skip that stronger check. With an account ID placed only in a grant's invoice set, the caller could retrieve an existing account proposal. `_proposal` now loads the stored record and requires its actual kind before any saved action returns. The new witness covers merge and compensation proposals, repeated review and filtered status access.

**Verified consistency gap, fixed:** three independent workbench reads could see records before an invoice commit and ledger receipts after it. `snapshot` now opens one `REPEATABLE READ READ ONLY` transaction and reuses the same filtered loaders. Its deterministic witness commits the approved effect on another connection immediately after reading records: the original snapshot still returns the old record and no receipt, while the next snapshot returns the new version and exact receipt. No timing-based sleep is needed. The R6 service must consume this snapshot rather than reconstruct one from three public calls.
