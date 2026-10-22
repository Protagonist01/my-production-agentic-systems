# Revenue review workbench and event recovery

R6 is a local operator/reviewer application over the R5 Postgres SIM ledger. It uses authoritative stored billing facts and R4 arithmetic; no browser field supplies the corrected invoice amount, role, tenant or grant. It does not connect to a real billing/CRM system. The user-approved cap is **100.00 SIM absolute adjustment per invoice**, not a cap on the invoice total, and approval cannot override it.

## Prepare a private local workspace

From the checkout, install the locked development environment with `python dev.py setup`. For an installed application use the Revenue `web` extra; the optional `events` extra pins Inngest 0.5.19. Web dependencies are FastAPI 0.150.0 and Uvicorn 0.54.0. Docker must be running for Postgres. Choose a new trial name owned by this work:

```powershell
uv run --locked --all-packages --link-mode copy python -m revenue_integrity.console_cli --root . --trial revenue-demo bootstrap
```

Bootstrap creates the checkout-isolated service/trial when absent, then pins the independent Revenue operations and application SQL schemas. The runtime role can read accounts and update sessions/throttle counters; it cannot provision identities, alter schemas or erase the append-only business ledger. No public account-registration route exists.

Enrollment is trusted administrator work. Prepare a private R2 billing snapshot as documented in [billing worlds](revenue-billing-worlds.md). Read its aggregate to select an invented tenant/case; pass those exact identities to `seed-world`:

```powershell
uv run --locked --all-packages --link-mode copy python -m revenue_integrity.console_cli --root . --trial revenue-demo seed-world --database D:/private/worlds/inputs.sqlite --case-id <invented-case-id> --tenant <invented-tenant-id>
```

This checks the real scoped reader, enrolls the case invoice and creates its account only if absent. Existing invoice identities are never upserted. Its original BillingInput is preserved as the finding's source baseline. To enroll a second constructed account or other explicit original record, use `record --input D:/private/record.json` with the strict RevenueRecord schema; this is not an HTTP mutation endpoint.

Create two private Principal JSON files: username, tenant_id, actor_id, role (`operator` or `reviewer`), invoice_ids and account_ids. Give each account exactly the invented records it needs. Use different actors for proposer/apply operator and reviewer. Provision each with `account --principal D:/private/operator.json`; the CLI prompts twice for a password of 15–128 characters. Do not put passwords in JSON, command arguments, source control or screenshots.

```powershell
uv run --locked --all-packages --link-mode copy python -m revenue_integrity.console_cli --root . --trial revenue-demo account --principal D:/private/operator.json
uv run --locked --all-packages --link-mode copy python -m revenue_integrity.console_cli --root . --trial revenue-demo account --principal D:/private/reviewer.json
uv run --locked --all-packages --link-mode copy python -m revenue_integrity.console_cli --root . --trial revenue-demo serve --port 8876
```

Open `http://127.0.0.1:8876`. The server binds only loopback, disables proxy trust and access logs, serves packaged assets and uses no remote fonts/CDNs. It is a controlled local application, not a remote production identity/deployment design.

## Use the operator and reviewer views

The findings view shows current amount, exact should-be amount, signed difference, disposition and current record version. The server derives corrections from the stored public billing facts and rechecks eligibility in R5. Missing/conflicting facts, ambiguous date rules, over-cap adjustments and stale versions cannot become writes through approval.

An operator proposes a correction. A separate reviewer opens the exact action, including payload/version, adjustment, proposer and action digest, and approves or rejects. An operator then applies the approved action. Apply and retry retain the stable business-operation key; a lost response does not justify inventing a second key. The browser keeps the key for that resource/version/action in session storage and removes it on sign-out. A changed record version requires a new reassessment and proposal.

Account merges are approved aliases from donor to canonical target, preserving original invoice/history records. Both account versions and scopes are checked. Only trimming surrounding whitespace in the internal account note is automatic; arbitrary note editing is unavailable. Compensation is a new approved proposal referencing an original operation and exact current version. It appends a receipt and refuses intervening changes, rather than deleting or rewriting history.

Pending, approved, rejected, expired and applied states remain distinct. Deadline passed means reassess or reconcile expired waits; it does not imply approval. Refresh obtains a new authoritative view. A 409 conflict asks for reassessment. A 503 or lost relay means an action may already be saved; refresh and retry the same key. If server logout fails, the local view is cleared and explicitly reports that server sign-out is unconfirmed.

Sign-out hides and clears the private workbench immediately, before waiting for server revocation. Every asynchronous response is bound to the session epoch that issued it; a delayed operator response cannot restore private views after sign-out or replace a newly signed-in reviewer's view. Cookie-changing login/logout requests are serialized, and signed-out actions do not fetch a workbench. The parent reproduced and repaired this timing bug during actual browser acceptance; it was not established by the original Python API tests.

Run the dependency-free JavaScript regression when Node is available:

```powershell
node tests/revenue_console_session_test.cjs
```

The VM executes the actual packaged script with a minimal DOM and controlled deferred fetches. All six checked scenarios pass with no network calls. This targeted mechanism check is separate from the Python suite and real-browser layout/interaction verification.

## Read the digest without inventing a funnel

All amounts are SIM hundredths, never real recovered revenue. Found is the absolute original discrepancy derived from each stored immutable original BillingInput. Current findings substitute the current invoice amount, so a successful correction resolves the current discrepancy without erasing the historical found amount. Proposed sums immutable invoice-correction proposal adjustments; rejected/reproposed attempts can make it exceed found. Approved includes historical approved amounts even after unapplied approval expires. These stages overlap and are not summed as exclusive balances.

Applied is gross absolute invoice-correction movement from permanent receipts. Compensated is gross absolute invoice compensation movement. Net ledger movement sums signed invoice receipt changes, including compensation. Retry deliveries do not create another receipt. Account alias and note hygiene receipts have no invented monetary recovery. The workbench obtains records, proposals and receipts from R5's single repeatable-read read-only snapshot, avoiding an interleaved old-record/new-receipt display. Stage and ledger totals are computed by the server.

Signed 64-bit integer values are returned as decimal strings in browser-facing projections. The browser formats money with BigInt; large amounts are not rounded by JavaScript Number. Browser mutation versions must be safe integers; larger versions require trusted administrator review. Reviewer authorization binds the server's exact command digest, not the formatted amount alone.

## Optional local Inngest wrappers

Current official [Python SDK](https://www.inngest.com/docs/reference/python), [function creation](https://www.inngest.com/docs/reference/python/functions/create), [step.run](https://www.inngest.com/docs/reference/python/steps/run), [wait_for_event](https://www.inngest.com/docs/reference/python/steps/wait-for-event) and [testing](https://www.inngest.com/docs/reference/python/guides/testing) documentation were checked before implementation. SDK 0.5.19 is pinned; its new jcs dependency is locked by the parent integration.

The default console requires no event server. To attach a separately operated **local** Inngest server, configure its event/signing keys privately in `INNGEST_EVENT_KEY` and `INNGEST_SIGNING_KEY`, then add `--events-origin http://127.0.0.1:8288` to `serve`. The origin must be loopback. Signed `/api/inngest` execution is registered with unauthenticated sync disabled; configure the local server to sync that endpoint. Keys and signed server execution are not needed for the default offline console.

Postgres alone owns proposal/approval/expiry/effect state. Inngest owns only its memoized wakeup steps. Requested/reviewed events carry tenant, provisioned operator actor and stable operation IDs; they do not carry authority, notes, passwords, source contracts or billing facts. The handler resolves the current enabled configured actor and re-reads canonical state. A wakeup is not approval. Event ID deduplication lasts only the SDK/server window; the permanent transactional operation key owns exactly-once effects.

The requested wrapper reads the proposal, optionally waits for a matching review event, then reconciles canonical state. A decision can arrive before wait registration; the eventual timeout or five-minute sweep re-reads the approved row and safely continues. Rejected/expired rows make no billing effect. Already applied receipts return `already_applied`; sweeps skip ledger-known operations. A race can still return a confirmed applied receipt to both callers, so a wrapper status is not evidence of two newly created effects. The ledger is authoritative.

If a relay call fails after a proposal/review commits, the HTTP response says `pending_recovery`; it does not roll back saved consent or invent a delivery acknowledgement. Explicit apply remains available. A scheduled sweep can discover approved/unapplied proposals even when the event was lost. No hosted Inngest deployment or real-server wait/restart acceptance is claimed by the supplied SDK-mocked tests.

## Evidence and remaining boundaries

Focused offline checks cover closed roles/payloads, password hashing, origin/CSRF/session restrictions, bounded private errors, packaged assets, exact 64-bit wire amounts, authoritative corrections, action digests, duplicate/retry projections and actual Inngest SDK function/step/wait composition. Required SQL tests cover provisioned sessions, reviewer/operator separation, rejection/reproposal, compensation/net digest, duplicate apply, missed wakeup recovery, expiry, disabled accounts and throttling. The final focused run passed ten offline tests in **20.29 seconds**, four real SQL composition tests in **131.27 seconds**, and strict typing of six modules. Ruff check/format passed eight owned Python files and `node --check` passed. Parent integration records final complete checks, browser interactions and hosted evidence after execution.

Inngest's experimental mocked harness stubs the wait event or timeout and simulates steps in process; this is mechanism evidence, not real durable-server execution. Default API/console work uses no provider calls. Fresh extraction quality, human-adjudicated labels, real account linkage, remote authentication and production release remain pending. See [source study](code-study-revenue-console.md), [R5 operations](revenue-operations.md) and the existing [release gates](release-evidence.md).
