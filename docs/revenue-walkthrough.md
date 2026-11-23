# Revenue Integrity: agreement to committed ledger

[Watch the recorded walkthrough](revenue-browser-walkthrough.gif). A fictional agreement sets the invoice at 30.00 SIM. The operator spots a charge of 35.00, a second person approves the exact correction, and the ledger records it once even after duplicate delivery.

The interactive walkthrough uses a deterministic parser and PostgreSQL. The separate [model comparison](#recorded-walkthrough-and-model-comparison) measures how Gemini routes requests before billing checks.

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

If startup failed **before a trial was created**, repeat the exact bootstrap command with
`--resume-bootstrap`. The private file must match the same root, trial and identities; its
original password is reused without rewriting the file. Existing trials still refuse
bootstrap. Inspect an interrupted trial explicitly rather than resetting or recreating it.

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

The Docker/PostgreSQL test exercised the authenticated HTTP workflow. Restarting the local server against the same database preserved the receipt and the single ledger change. All ten checks passed on [PR #167](https://github.com/Protagonist01/my-production-agentic-systems/pull/167), and [CI passed on main](https://github.com/Protagonist01/my-production-agentic-systems/actions/runs/44201584113).

[Release issue #45](https://github.com/Protagonist01/my-production-agentic-systems/issues/45) tracks evidence for interpreting unseen agreements, missed discrepancies and false alarms. This demonstration uses fictional amounts throughout.

## Recorded walkthrough and model comparison

[Watch the four browser checkpoints](revenue-browser-walkthrough.gif). The operator checked the overbilled 35.00 SIM invoice against the 30.00 SIM agreement. A second login approved the adjustment, the operator applied it, and a second delivery left one receipt for that invoice. The recording starts after sign-in. The earlier underbilling receipt belongs to a different invoice.

On November 18 both invented Gemini 3.5 Flash-Lite Free canaries passed. The first 16-case trial completed. The second reached its sixth case when Gemini returned HTTP 429. The runner stopped with 26 scheduled slots unrun.

| Method | Correct scope decisions on the same 22 slots |
| --- | ---: |
| Rules | 20 |
| Gemini with local access checks | 17 |
| Always request review | 8 |

Six of the 22 decisions came from local checks. Gemini returned 15 domain answers, 11 of which matched the authored reference. The denominator of 22 includes the failed provider call. Gemini admitted an invoice missing its unit price on both observed repetitions. It also treated the unrelated agreement as an unrelated request in both trials where it appeared. The reference calls for requesting the relevant billing agreement.

These are repeated observations from one authored fixture family. They measure scope routing. Contract interpretation and financial impact require additional evidence. Keep price completeness and registered-source checks ahead of any correction proposal.

The study used 18 provider attempts including both canaries. The shared lifetime count reached 642 of 843. Gemini reported 2,385 tokens across 17 responses. Actual billing cost is unknown. Domain provider requests had a measured p95 of 1.52 seconds including the failed request. See the [aggregate results](data/revenue-scope-demo-20261118.json).
