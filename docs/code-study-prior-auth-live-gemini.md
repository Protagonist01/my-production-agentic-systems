# Code study: a live model behind two durable reservations

Inspected unmerged branch: `codex/prior-auth-live-gemini`, based on merged cf143ba.
Scope: root live gateway/console/draft and the existing demo worker's lease renewal.
Clinical packages, model prompt, checker and prior captures are unchanged. Build Book
Entry114 records construction and failures. This is not a full repository security audit.

Follow `prior_auth_live_draft.packet` with invented case `demo-education-wait`:
six initial requests omit education; the fixed supplement changes the note digest,
but only education is reassessed. Two separately pinned complete-note requests come
first as canaries. Normalization removes the original trailing newline, so canary
and imported requests have distinct fingerprints even when their facts look alike.
Never replace that byte comparison with text normalization at the admission boundary.

`Grant.bounded` combines consumed history, old bound slots and the new schedule when
checking the lifetime ceiling. `history` hashes the existing schema and every row,
excluding only the newly added live namespace. `initialize` requires615settled
historical attempts and the existing credential association. Its append-only tables
cannot replace a grant. This is trusted administration, not an authorization API
available to a model or browser.

`scope_binding` excludes the scope's reciprocal grant pointer. The grant still pins
all other scope fields; runtime validation separately checks the exact pointer.
Hashing both complete objects would create an impossible circular fingerprint.
`execution_pin` hashes tracked executable/SQL/dependency sources plus OS/interpreter;
the operational factory additionally requires the actual clean module checkout.

Trace `open_runtime` → `LiveGateway.validate` → `DemoWorker.step` →
`DurableGateway.generate` → `LiveGateway.generate` → `Ledger.reserve` →
`ProviderGateway` → spawned `Worker`. The SQL reservation commits before the shared
allowance reservation, which commits before I/O. Validation binds request route,
context, case/version, live scope, frozen bytes, existing project association and
expiry. SQLite admission serializes requests and requires every earlier reservation
settled; two supported canaries must precede domain requests.

Settlement order reverses the persistence concern: first preserve the provider
response in the shared file, then let the SQL layer settle its work identity. A crash
in either gap may leave an outstanding reservation. The system favors not resending
an uncertain attempt over automatic availability. A later operator could investigate
the private stores, but this code performs no implicit reconciliation.

Lease renewal is inside the existing active case/job lock, after validating the
original lease and live authority. It extends that same lease at each new live
criterion, bounded by scope expiry. A different worker or expired lease cannot be
revived. A test advances the store clock two minutes per response and verifies that
all seven criteria publish, which would outlast the original five-minute case lease.
The SDK itself still has a separate110second process bound; simulated store time is
not a measured provider latency.

**Design limitation:** local SQLite and SQL are separate stores. Shared allowance
recovery must never roll back consumed attempts; the application snapshot does not
grant permission to restore/reset the provider ledger. **Not assessed:** real-patient
clinical qualification, commercial payer credentials and remote-host controls.
**Verified fixture failures:** Windows text translation broke exact archive pins;
separately, a fake Usage response omitted its required unknown currency field.
The contract rejected both; no live key was loaded to diagnose them.

Reproduce wiring with the focused unit file and actual SQL integration file:
`tests/test_prior_auth_live_gateway.py` and
`tests/integration/test_prior_auth_live_gateway_state.py`. The latter uses owned
disposable Docker databases and a spawned invented worker, with no credentials.
Explain in an interview why a valid quote can fail support, why169old unused slots
are unavailable to this request list, and why a settled provider result plus an
unsettled SQL attempt is an availability limit rather than permission to retry.
