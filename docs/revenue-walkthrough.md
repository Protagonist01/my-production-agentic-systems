# Revenue Integrity: agreement to committed ledger

This opt-in walkthrough finishes the operational integration selected by the owner on
November 17, 2026. It starts from main `1e1b8fe` and preserves the frozen runtime packages,
schemas and previous evaluation captures. It makes **zero model calls**. The page labels
its execution mode as a constructed parser demonstration, not live AI or legal analysis.

## What you can demonstrate

1. Sign in as the scoped operator and choose a registered fictional invoice/agreement.
2. Check the exact source and extract the complete explicit field grammar with citations.
3. Compare source-derived monthly arithmetic with independently provisioned stored facts.
4. Request a correction for an eligible discrepancy, without changing the invoice.
5. Sign in as a different reviewer and approve or reject the exact displayed action.
6. Return as the operator and apply the approved correction. Observe the committed receipt.
7. Reconstruct/restart the application and redeliver the operation. Observe the same receipt
   and a single invoice version change, not a second adjustment.

The six fixed scenarios are underbilling, overbilling, an already-correct invoice, missing
price, conflicting terms and an above-cap adjustment. The source/question controls also
demonstrate changed-byte refusal, an unrelated request and an unsupported/uncertain request.
Only the declared question vocabulary is handled by this deterministic demonstration.
It does not classify arbitrary natural-language requests or upload arbitrary contracts.

## Start in a clean owned trial

Use the existing locked setup and Docker/PostgreSQL service prerequisites. Choose a new
trial identity and a new private credentials path outside every project checkout:

```powershell
python dev.py setup
uv run --locked --all-packages python revenue_demo_cli.py bootstrap --root . --trial <new-demo-trial> --credentials <private-credentials.json>
uv run --locked --all-packages python revenue_demo_cli.py serve --root . --trial <same-demo-trial> --port 8878
```

Open the printed loopback `/walkthrough` address. The private file contains the operator
and reviewer usernames and their generated demo password. Never commit, print on a shared
screen or embed that password in the page. Bootstrap refuses existing trials/credentials;
it never resets or overwrites existing work. A failed attempt retains its credentials/trial
for explicit diagnosis. Invoice and account provisioning is trusted setup, not an agent tool.
The fixture records and accounts are enrolled atomically once the new trial exists.

To restart, stop only this server and repeat `serve` with the same root/trial. The server
loads the existing database and verifies its source facts and provisioned identities before
listening. It performs no model inference or re-enrollment on startup. Port binding is
loopback only; this does not expose an internet-hosted financial service.

## Execution and authority boundaries

`revenue_demo.cases` contains only invented normalized agreement fields. Each exact document
is pinned to a fixed invoice/account/product/period in trusted composition. `DemoService.source`
checks invoice and account read grants before returning any source. `_record` requires the
stored billing input to match the registered fixture. Client amounts, inferred ownership,
free-form source edits and model-produced permission are never accepted as stored facts.

`analyze` uses the existing v2 preflight and the existing constructed-grammar parser. The
current stored invoice amount is reconciled against extracted terms. Missing terms remain
unknown, conflicts require review, and adjustments above the existing 100.00 SIM cap cannot
be proposed. Parsed terms and stored typed facts must yield the same proposed amount.
An `analysis_digest` binds the exact displayed finding, source pin and invoice version.

`propose_checked` redoes these checks before calling the original `ConsoleService.propose`.
The inherited `/api/proposals` route refuses the shortcut around assessment in this opt-in
composition. The existing transactional `OperationStore` remains the only owner of proposals,
reviewer identity, expiry, exact approved payload, invoice version and permanent receipts.
An exact operation-key retry can reconstruct its original assessed view; a changed key payload
or stale new operation cannot authorize a second write. No second approval database is added.

The page retains the existing session cookies, origin/CSRF checks, closed request schemas,
wire integer strings and independent reviewer API. DOM source text uses `textContent` and
money uses BigInt. Session/assessment generations prevent delayed responses from repopulating
private state after sign-out or after a source change. A timeout does not claim a mutation
failed: refresh SQL state and retry with the same operation identity. No automatic retry occurs.

`revenue_profiling.Recorder` and the profiled SQL connection measure requests, extraction,
citation checks and reconciliation without storing source, passwords, SQL or provider bodies.
These overlapping inclusive intervals are diagnostics, not an SLO or performance evaluation.

## Evidence and remaining limits

The focused tests cover all six constructed outcomes, source/tenant mismatch, named request
handling, stale versions, forged digests, extra payload fields and proposal bypass refusal.
The Node VM regression executes the actual new browser asset to check exact money, delayed
private responses, session expiry, CSRF and source-change invalidation without network calls.
The required SQL/HTTP integration test exercises real sessions, denied self-review, changed
approval digest, approval-before-apply, reviewer apply refusal, stored receipt and reconstruction.

Record actual test/CI/browser outcomes in the delivery receipt before calling those checks
passed. The prior evaluation baseline remains separate: this operational walkthrough does
not fill its missing candidate outputs, independent language labels or unknown evaluation costs.
It establishes no real recovered revenue, qualified contract meaning or production release.
Fresh model evaluation and its exact provider authorization remain the next separate deliverable.
