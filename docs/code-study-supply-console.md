# Supply console: scope, exact decisions and factual notices

Scope: unmerged `codex/s5-supply-console`, S5 #56, inspected 2026-10-23. Existing S4 SQL remains
the authority for effects. This chapter covers the console entrypoint, accounts, projections,
browser asset and notices; it makes no model-quality, delivery or production-readiness claim.

`console_cli.main` bootstraps the existing operations schema plus a separate immutable
`supply_app` schema. Admin connections provision accounts, invented demo facts and optional
verified alert context. Runtime connections have narrower SQL grants. `create_app` accepts
an explicit loopback origin, rejects foreign Host/origin mutation requests, checks CSRF,
limits body size and serves packaged assets under a restrictive content security policy.

`Principal.grant(event)` finds one server-provisioned incident scope. It constructs capabilities
from the stored role and includes only that incident's shipments. Browser JSON supplies IDs and
the exact proposal fingerprint; extra prices, tenant IDs and grants fail closed contract
validation. `AuthStore.authenticate` joins sessions to enabled accounts each time, so a browser
cannot retain revoked authority just by keeping a cookie.

Follow an invented reroute: the operator assesses a 12-hour-delay shipment. `SupplyWorkflow`
stores a pending 80.00 SIM proposal. `ConsoleService.selected` compares the selected fingerprint
to the current proposal; the S4 store rechecks the exact command and versions under lock.
The reviewer approves; the operator commits. The ledger receipt is permanent and the table
shows awaiting confirmation. A confirmer may record modeled acceptance. A SIM receipt or
confirmation never becomes an assertion of actual shipment delivery.

`OperationStore.workbench` locks the budget first, then sorted shipment rows. It reads proposals,
receipts and confirmation state under those locks and reconciles expiry using one clock.
`Portfolio` carries that budget and those rows together. This avoids mixing a pre-commit budget
with a post-commit receipt during concurrent refresh. Other incident budgets sharing a shipment
still follow the same budget-before-shipment lock order.

`ConsoleService.board` derives freshness and stale-version states, then calls `make_notice`.
Notice IDs hash canonical facts, state, receipt and alert context rather than poll time.
`NoticeStore.append` inserts idempotently. Notice writes deliberately follow canonical action
transactions: a failed notice write does not undo an effect. The next view reconstructs its
committed notice from the receipt. Read acknowledgments use a separate account/notice table
after tenant, incident and shipment checks. Historical messages remain dated previews.

The browser formats minor units with `BigInt`, renders facts with `textContent` and never
accepts client prices. Session epochs discard late authenticated responses after logout;
view versions discard late incident responses. Private DOM clears immediately on sign-out.
Only cookie-changing authentication calls are serialized; workbench reads cannot block logout.

Evidence: eight focused offline tests cover scopes, forbidden authority fields, deterministic
notice IDs, exact JSON amounts and the API perimeter. The actual browser asset Node harness
checks late refreshes, private clearing, stalled login/logout and signed-64 formatting.
The SQL acceptance test covers exact review, post-commit notice failure/reconstruction,
single-debit retry, confirmation wording, per-account read state, tenant denial, session expiry
and runtime deletion denial. Test presence is distinct from a successful run; see the Build Book
for completed results and remaining verification.

Tradeoff to explain in an interview: notices are eventually reconstructed from canonical state,
so a failure can delay the preview while preserving exactly-once SIM effects. This avoids an
external delivery protocol but does not provide notification delivery guarantees. Extending this
to email requires a separate authorized adapter/outbox and delivery semantics. Current S5
also needs a later production identity and deployment review.
