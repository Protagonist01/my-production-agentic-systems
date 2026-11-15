# Code study: payer actions belong to the operator

This chapter covers the opt-in root `prior_auth_payer_desk.py`, the demo web/CLI
composition and its SQL/browser witnesses on `codex/prior-auth-payer-desk`. It follows
Build Book Entry110. The adapter's FHIR serializer and correlation checker remain
those already tested before this composition. No fresh model calls are involved.

An invented execution starts with a reviewer opening case `demo-complete`, revision1.
`EvidenceStore.snapshot` attaches stored payer metadata through `PayerDesk.status`;
opening a case makes no remote call. The browser's explicit submit click posts only
revision1 and `confirm_synthetic_exchange=true`. `install.actor` verifies the same
origin, host, session cookie and CSRF token used by the inherited reviewer API.

`PayerDesk.current` requires assigned reviewer authority before accessing private
state. Its Postgres transaction locks the case, compares the current revision, and
checks the configured CaseBinding against the immutable intake binding SHA. It
constructs a Submission from canonical note/policy/date and trusted identities. The
browser cannot supply an alternate destination or use a model statement as authority.

The request identity includes revision and evidence pins. `pas_desk_packets` indexes
that identity before dispatch; earlier unresolved packets block replacement. The
existing `PasClient.submit` commits its reservation before sending a single POST.
If that POST loses its response, the receipt remains unknown; process death can
leave reserved. Repeating the same request returns the original receipt. A separate
inquiry calls only `$inquire` and independent readback, recording its observation
without rewriting submission history. All SQLite connections close explicitly.

The case row remains locked during I/O, which prevents a supplement race but can
delay an edit and produce a lock-timeout response for competing commands. This is
a deliberate local-demo consistency tradeoff. A production SQL outbox would need
its own durable authorization, version and dispatch semantics, not just shorter locks.

`renderPayerExchange` uses text nodes and fixed labels. It disables submit once a
receipt exists, explains A3 and uncertainty, and checks session epoch plus selection
before refreshing after an asynchronous action. API enforcement remains authoritative
when a caller ignores disabled buttons. Existing logout clears the entire detail.

Verified limits to explain in an interview: a journal replacement loses history;
an index-only crash is conservatively unresolved; the browser cannot yet inquire an
older revision; synthetic note hashes do not demonstrate clinical attachment handling;
reference-payer A3 does not prove insurer acceptance or clinical accuracy. SQL tests
and the actual-process workflow distinguish tested controls from these limitations.

Study exercise: let a POST succeed remotely but kill the worker before its local
receipt settles. Restart, click submit again, then inquire. A strong explanation
predicts no second submit POST, retained reserved history, and separately checked
inquiry evidence. Changing the case revision must not bypass that uncertainty.
