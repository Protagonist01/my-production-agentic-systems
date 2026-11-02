# Olist customer transaction authority

Inspected base `7e7e823`, branch `codex/olist-intent-authority`, 2026-11-01; implementation
and tests in this change. The owner selected customer confirmation of the exact refund
action and amount. This implements a new loopback SIM service composition, not a new model
prompt or a rerun of the stopped study. Build Book Entry78 records construction and failures.

## Reason for the boundary

In the frozen development study, a valid, in-cap interpretation committed100.00SIM when
the accepted reference required clarification. A cap proves an amount is bounded; trusted
payment/cancellation facts prove conditional eligibility. Neither proves the customer wants
that transaction. Post-commit observation stopped subsequent calls but could not prevent
the first effect. The new composition therefore treats a suggestion as pending until the
authenticated customer explicitly confirms the displayed order, action and exact amount.
This follows the significant-data and server-enforcement principles in the
[OWASP transaction authorization guidance](https://cheatsheetseries.owasp.org/cheatsheets/Transaction_Authorization_Cheat_Sheet.html).

## Execution and code reading route

```mermaid
sequenceDiagram
  participant Staff
  participant API
  participant Customer
  participant PG as PostgreSQL
  Staff->>API: Submit proposed refund
  API->>PG: Save eligible pending case
  Customer->>API: Authenticate with scoped account
  Customer->>API: Request refund details
  API->>PG: Bind unique challenge to exact command and case
  API-->>Customer: Order, full amount, SIM, expiry
  Customer->>API: Confirm exact action and amount
  API->>PG: Save confirmation (no refund yet)
  Customer->>API: Execute using same confirmation
  API->>PG: Lock order; consume consent; receipt + case + audit
  PG->>PG: Deferred authority and balance guards
  PG-->>API: Commit once
  API-->>Customer: Verified SIM result
```

1. [`console_contracts.Principal`](../projects/olist-support/src/olist_support/console_contracts.py)
   adds `customer`. Its order grant has read capability only; it cannot call the refund tool.
   Account provisioning remains trusted administration. The API derives identity from the
   opaque session; a request body cannot choose an actor, role, tenant or order grant.
2. [`CaseStore.run_request`](../projects/olist-support/src/olist_support/console_cases.py)
   uses `ConfirmationRequiredStore`. Eligible automatic refund attempts become review-required
   proposals without an effect. Existing explicit reviewer approval is retained when requested.
   The service currently uses operator-selected intent with a fixed planner; it does not
   silently replace or qualify the frozen model candidate.
3. [`CustomerIntentStore.issue`](../projects/olist-support/src/olist_support/customer_intent.py)
   loads a scoped case under lock, checks readiness and fresh trusted evidence, and stores
   the SHA-256 of a random challenge. `Authority` binds customer identity/order scope, case
   version, canonical request hash, exact `RefundCommand`, action digest, evidence pin and
   policy version. Database time starts a maximum300second interval. Only the raw challenge
   response reaches the browser; it stays in memory, never in a URL or browser storage.
4. `confirm` accepts only refund/action, exact positive integer minor units <=10000, `SIM`
   and the challenge. Missing/rotated tokens, other customers and changed amount fail.
   Case/request/evidence binding and expiry are checked; server-side confirmation time is
   stamped by PostgreSQL. It returns `confirmed:true, committed:false`; consent alone does
   not claim an effect. Repeat confirmation does not extend its deadline.
5. `execute` checks the same authority, including required reviewer approval. The trusted
   service supplies refund capability only after these checks. `BusinessStore.refund` owns
   policy/version/budget/order locks and the transaction; its callback reloads the case,
   checks evidence, consumes consent, saves the committed case and appends the ledger-linked
   event. `CaseStore.resume` uses the same consumption path for reviewer execution.
   Planning usage/run metadata is retained in the final case. An exception before commit
   rolls everything back; loss after commit can return the same persisted receipt.
6. [`customer_intent.sql`](../projects/olist-support/src/olist_support/customer_intent.sql)
   installs deferred row constraint triggers. Receipt insertion needs matching consumed
   authority, exact command/case version/evidence/action, case result and audit event.
   Balance changes need the corresponding receipt and exactly one order-version increase.
   This catches an older writer omitting the callback. A runtime role cannot disable these
   triggers. The application/database credentials remain trusted: this is not a claim that
   arbitrary SQL using compromised service credentials cannot manufacture records.

`consume` takes an account-keyed transaction advisory lock before checking the current
enabled account and identical principal. An account UPDATE/DELETE trigger takes that same
lock. Revocation that wins the lock blocks new effects; execution that wins may commit
before revocation. Runtime account permissions stay SELECT-only. The original `FOR SHARE`
approach failed because PostgreSQL also requires UPDATE privilege for locking SELECT; see
[PostgreSQL SELECT](https://www.postgresql.org/docs/17/sql-select.html). Constraint checks run
at transaction end, per [CREATE TRIGGER](https://www.postgresql.org/docs/17/sql-createtrigger.html).

## Customer interface and access boundaries

[`console_api.create_app`](../projects/olist-support/src/olist_support/console_api.py)
serves `/customer` and minimal `/api/customer/cases` projections. Customer sessions cannot
access staff order/case/audit endpoints. Writes require same-origin JSON and the existing
session-bound CSRF token; cookies, CSP and no-store behavior reuse the service controls.
The customer view displays the order, original request, full refund amount and SIM unit.
Cancel discards the proposal without confirming. The confirmation click first saves consent,
then sends the execution request; neither request is automatically retried on failure.
Timeout language allows for an already-committed refund and directs a refresh.

[`customer.js`](../projects/olist-support/src/olist_support/web/customer.js) uses session
epochs and selection generations to discard late responses after logout/account change.
Authentication mutations serialize through a queue. Private fields are cleared immediately
on account transition; a pending confirmation response cannot dispatch execution as a new
customer. Server authorization remains authoritative even if browser code is changed.

## Migration, provisioning and recovery

1. Keep existing `business.sql` and `console.sql` immutable. Stop/drain old service writers,
   retain a private pre-change backup with its matching old code, then run the existing
   `python -m olist_support.console_cli --root <checkout> --trial <owned-trial> bootstrap`.
   This installs the separately pinned `olist_intent` schema and commit guards.
2. First install copies exact existing receipt rows into an admin-seeded, runtime-read-only
   `legacy_refunds` table. It is seeded once, not on every bootstrap. These are history,
   explicitly not retroactive customer consent. New receipts must carry new authority.
3. Prepare a private principal JSON outside Git with `username`, `tenant_id`, `actor_id`,
   `role:"customer"`, and verified `order_ids`. Use the existing `account --principal <path>`
   subcommand; it prompts for a password. Administrator verification of customer/order
   ownership is required. No public signup or commerce ownership integration is implemented.
4. Start the existing loopback `serve` command with an explicit run limit and new private
   telemetry output. Readiness checks the authority source pin, actual function bodies,
   function configuration and enabled trigger definitions. Visit `/customer`; staff use `/`.
5. New backups require all four Olist schemas, including authority/history. Fingerprints
   include actual function and trigger definitions. Restore is into a new owned trial using
   matching code; do not disable triggers or overwrite the source database. Historical
   consumed timestamps/receipts are preserved even if that customer was later revoked.
   New consumption is stamped within its transaction and must still be fresh/current.
   Trusted database clock/admin restore privileges are explicit assumptions.

Older three-schema snapshots fail the new inventory/fingerprint checks. Use their matching
historical recovery tool in isolation, then migrate forward; no downgrade compatibility is
claimed. Old binaries against the migrated service database cannot create unconfirmed
refunds; do not roll back by deleting the authority schema/guards. Graph proposal checkpoints
remain historical; authoritative completed service cases/ledger prevent re-execution.

## Evidence and limits

Invented tests in [`test_olist_customer_intent.py`](../tests/integration/test_olist_customer_intent.py)
exercise wrong suggestions with zero effects, exact confirmation, reviewer-only refusal,
customer/amount separation, expiry/token rotation, changed cases, revocation, concurrent
delivery, precommit rollback, response loss, HTTP role/CSRF and restore after revocation.
They also call the old raw writer and try an unreceipted balance update/trigger disable.
[`olist_customer_session_test.cjs`](../tests/olist_customer_session_test.cjs) drives the
shipped asset with late responses, account switches, cancel, exact amount and a failed
execution with no automatic retry. Contract tests reject extra fields and malformed money.
Actual final test counts and browser observations belong in the PR and Build Book; a planned
check is not a result.

**Design limits:** this is provisioned loopback HTTP/SIM, not public production identity,
payments, MFA, independent semantic gold, host-loss qualification or a full security audit.
Raw business/workflow primitives in their separate mechanism fixtures remain legacy; the
installed service migration is the commit enforcement boundary. User mistakes, compromised
accounts, misleading staff descriptions, database clock failure and trusted administrator
abuse require additional controls for production. No new provider calls occur. The stopped
447/614 experiment stays stopped, original artifacts/labels stay unchanged, and issues33,
58 and59 remain open. A future study must explicitly bind this changed interaction and
service composition; previous model scores do not transfer to it.

## Interview exercises

- Trace a mistaken refund suggestion on an eligible50.00SIM order. A strong answer separates
  conditional policy eligibility, authenticated customer consent and the committed receipt.
  Before the customer click, all effect observations must remain zero.
- Remove `record_commit` in a test against a migrated service trial. Explain why commit fails
  despite a valid business grant, and why it can still pass in a legacy business-only fixture.
- Lose the response immediately after commit. Explain idempotency keys, consumed authority,
  persisted case/receipt read-back and why timeout does not prove rollback.
- Restore after the customer is revoked. Explain historical consumed proof versus new
  authority, DB-stamped time, matching schema fingerprints and the trusted-admin boundary.
- Propose real commerce deployment. Identify customer/order ownership, secure hosting,
  reviewed transaction text, fresh end-to-end qualification and recovery cutover as remaining
  work; do not invent production traffic or money saved.
