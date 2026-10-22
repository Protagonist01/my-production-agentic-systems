# Approval-bound Revenue operations

R5 adds a local Postgres backend for constructed SIM billing and CRM records. It does not contact a CRM, send an invoice, charge a customer or recover real revenue. Original CUAD quotations never authorize a monetary change.

The user-approved policy permits only surrounding-whitespace removal from an internal CRM note without human approval. Every invoice correction, account alias merge and compensation needs a reviewer distinct from both the proposer and the executing actor. The absolute correction is capped at 10,000 SIM minor units, or 100.00 SIM, regardless of the resulting invoice total. Approval cannot override that cap or missing/conflicting billing facts.

## Authoritative findings before changes

Trusted enrollment stores an immutable `BillingInput` with an invoice record and verifies matching tenant/account identity and the original issued amount. An invoice proposal must name the exact result of R4 reconciliation against these stored facts and the current invoice amount. The server repeats this computation during review and application. Browser/model amounts cannot substitute for computed commercial facts. A review disposition, missing source input, a zero adjustment or a change over the cap blocks the action.

The account-merge demonstration marks the donor account as an alias of a distinct canonical target. Both accounts require scope and exact expected versions. Existing aliases and self/cyclic merges are rejected. Original account records, invoices, invoice ownership and ledger history remain present. This is a bounded constructed alias operation, not an external account-data consolidation.

## Transaction and approval ownership

`OperationStore.propose` persists a closed `ChangeCommand`, its canonical SHA256, proposer, immutable signed adjustment and aware creation/expiry timestamps. A tenant/business-operation identity is stable across new run IDs. Reusing it with a different command or proposer fails. Identical redelivery returns the original proposal.

`review` checks exact scope, separation of duties, canonical payload integrity, current versions, deadline and action eligibility before recording approval. Rejection records the reviewer without a business effect and remains available when the underlying record has become stale. There is one stored review decision; a duplicate identical review is idempotent.

`apply` takes a transaction-level operation lock, locks affected records in deterministic resource order and repeats the code policy. State and append-only receipt commit in one database transaction. A before-commit failure rolls both back; an after-commit failure leaves one saved receipt, returned on retry. The receipt retains the original run, actor, reviewer, source command, before/after records and committed timestamp. A retry does not use a new run ID to create a second effect.

Store timestamps own proposal expiry. `sweep` may expire pending or approved-but-unapplied proposals after their deadlines; it cannot expire a committed effect. Application after expiry is blocked, while retrieval of an already committed identical receipt stays idempotent after the deadline. An event wrapper only wakes the store; it does not own a second approval checkpoint.

## Compensation

A compensation is a new exact proposal naming the original operation and expected current version. It requires separate approval. The server requires the current record to equal the complete original after-state, including its version, and also checks the saved target account snapshot for a merge. Restoring the same amount after another legitimate version change does not make an old compensation safe. A changed record or merge target requires fresh review rather than overwrite.

Successful compensation restores prior business values at a new incremented version, appends a new receipt and preserves the original receipt. A unique original-operation constraint permits only one compensation. Compensations cannot themselves be compensated through this demonstration API.

## Database and authority boundary

Trusted admin bootstrap applies an immutable version-1 SQL resource under a schema lock and records its digest. The runtime role may read scoped records, insert proposals/receipts and update state/proposal documents through the application. It cannot create schema objects, alter the immutable command hash, delete receipts or update existing receipts. Enrollment is an admin-only operation, never an agent tool.

Revenue grants use shared exact tenant/resource-kind/resource-ID/capability membership, with separate invoice/account ID sets and closed read/propose/review/apply/crm_trim capabilities. Grants and the connection factory are trusted server composition; they are not authentication. The authenticated R6 console must create grants from its local account configuration. Direct possession of runtime database credentials is outside this application authorization boundary.

All records here are constructed. Independent source labels, live provider behavior, production authentication/deployment and fresh release acceptance remain separate work. Tests establish only the stated invented mechanism and database invariants.


## Focused verification

At source `2688d82f3c66fa5767670c63e9872e928beb756a`, the focused command passed **30 checks in 165.90 seconds**: 11 offline and 19 required real-Postgres cases, Python 3.13.4, external `TEMP`/`TMP` at `D:/document/.cache/production-agents/test-temp`.

```powershell
uv run --locked --all-packages python -m pytest -q tests/test_revenue_operation_contracts.py tests/integration/test_revenue_operations.py -o 'addopts=--strict-config --strict-markers'
```

Both source modules passed strict mypy with workspace source paths; both modules and both test files passed Ruff check/format. The first run passed 27 tests and failed one negative-test expectation: use of the account-only automatic tool correctly raised `PermissionError` for an invoice command, while the test expected a business-review error. The final test accepts that correct authorization denial. The final passing run includes a real process exit after commit, concurrent duplicates and the absolute 100.00 SIM adjustment boundary. Parent integration owns broad suite/package/hosted verification. [Study the implementation](code-study-revenue-operations.md).

Read methods filter exact scoped results after loading tenant-local proposal/receipt documents inside the trusted service. This is not a database RLS or OS sandbox claim. Direct SQL credentials and administrators remain trusted.


Follow-up source `1bb4579dd5c9b38c851e131301d4de51ea3cedcc` adds actual-kind checks for every saved proposal return and a single-transaction `snapshot(grant)` for ledger-consistent UI projections. Two targeted real-Postgres regressions passed in 98.53 seconds (19 database cases deselected); changed-file Ruff and strict typing passed. The snapshot uses `REPEATABLE READ READ ONLY`, so an effect committed between logical record/ledger read phases cannot produce a mixed before/after digest. Existing public record/proposal/ledger readers remain available, while the console uses the consistent snapshot. This result supplements the earlier 30-case run; it does not claim a repeated complete 32-case run.


The private [29-case cohort drill](data/revenue-approved-effects-v1.json) independently exercised twelve eligible corrections through separate approval, apply, stable duplicate receipts and approved compensation. Seventeen review/no-change cases produced no effect. The capture revision precedes the separately tested resource-kind/snapshot follow-up; it is an arithmetic/transaction witness rather than final interface acceptance. Full per-case receipts stay external and its owned trial was removed.
