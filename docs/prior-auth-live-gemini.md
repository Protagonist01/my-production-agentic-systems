# Gemini-only operational demo

This opt-in composition connects the existing protected evidence desk and durable
SQL worker to Gemini3.5Flash-Lite. The original scripted launcher remains available.
No allowance is created automatically, and no model was called to implement it.
Local Docker is the selected host; remote hosting and model comparisons are deferred.

## Finite next demonstration

`prior_auth_live_draft.py` prepares a private proposal using the already pinned CMS
policy and declared fictional education-wait scenario. It produces exactly nine
request slots: two complete-note canaries, six initial criterion requests, then one
education-only request after the fixed supplement. Both canaries must pass before
any case request. Education has no retrieved evidence initially and consumes no
initial model request. The request after supplementation contains the combined note.

The proposal asks for nine new Free attempts and a same-file ceiling of793:
615consumed +169old bound/unspent +9new. No old slot is transferred. The separate
168-call development comparison remains unapproved and is not dispatched by this
console. This nine-call path demonstrates integration; it cannot estimate clinical
accuracy or demonstrate that the larger cohort's citation problems are solved.

```powershell
uv run --locked --all-packages --link-mode copy python prior_auth_live_draft.py `
  --directory D:/private/prior-auth/live-demo-proposal `
  --policy-directory D:/private/prior-auth/pinned-source-v1 `
  --ledger D:/private/shared-existing-attempts.sqlite
```

This only reads the existing shared ledger. Review the exact requests, manifest,
source/environment fingerprint, limits and conservative seven-day expiry before
approval. The proposal explicitly says `authorized=false`. Its scope template has
an invalid placeholder grant pointer and cannot activate a provider. A new exact
owner decision and current Free-project confirmation are required. Preparing a
proposal does not initialize a live grant or load a credential.

## Authority and durable execution

After that decision, trusted administration validates `Grant`, records the actual
approval reference, and calls `prior_auth_live_gateway.initialize` on the existing
shared file. The additive four-table namespace preserves all original schema/rows,
stops and grants. It refuses an existing namespace; it cannot reset an allowance.
Retain the returned digest separately. Update only the scope's reciprocal grant
pointer and provision that exact scope using the existing trusted SQL provisioner.
The grant hashes the scope excluding only that pointer, avoiding a circular hash.

The live grant pins the full ordered request/case list, execution bytes, environment,
existing credential association, runtime scope, expiry, token bound and explicit
Free attestation. Ceiling validation includes the169old bound slots. The namespace
supports at most168new attempts, but the approved finite schedule can be smaller.
Never initialize it from a historical recovery copy of the shared allowance.

`prior_auth_live_console.open_runtime` refuses another checkout, dirty code, an
expired/changed grant or wrong runtime before credential access. It then loads only
the private ignored/untracked Gemini configuration previously authorized by the
owner. The configuration path and in-memory key hash must match the existing ledger
association. This is an operator-selected credential binding, not independent
verification of the provider's cloud project or billing tier. Keys never enter
arguments, output, source bundles or application logs.

The concrete transport is `ProviderGateway(IsolatedTransport(Worker(key)))`: the
existing pinned Gemini SDK adapter runs in an owned spawned process, with90second
HTTP and110second parent limits. There is no automatic retry, model/provider change
or paid fallback. Scope/context deadlines can shorten those limits.

The SQL worker first commits its immutable per-criterion reservation. The live
adapter verifies that one matching unsettled SQL reservation exists, then commits
the shared SQLite reservation before SDK work. A response is settled in SQLite,
then SQL. The two commits are not a distributed transaction. An interruption
between them stays unknown and is never silently resent, even if a private captured
response might exist. Reconciliation requires explicit inspection, not allowance reset.

Each next live request renews only the same still-active SQL job lease while holding
the existing case/job locks, up to five minutes or scope expiry. An expired/stolen
lease cannot be revived. Seven bounded requests can thus exceed the original
five-minute case duration without dropping lease fencing. A crashed worker still
has a finite lease, and unknown attempts remain blocked after lease recovery.

Canaries use only the fixed fictional complete note and adult/education requests.
Valid JSON or an exact but unrelated quote is insufficient: the existing evidence
checker must establish support. Failed canaries, missing usage, nonzero observed
cost, unexpected call count or interrupted work stop further admission. Unknown
provider cost remains unknown; Free attestation is not a billing receipt.

## Operating after an exact grant

Initialize a new synthetic education-wait trial through the existing demo launcher,
then provision its approved live scope. Keep the private source bundle separate
from the proposal and grant documents. The original scripted scope must not run
instead of the approved live scope. The live console never provisions allowances.

Use `prior_auth_live_console.py --help` for its explicit `canary`, `worker`, and
`summary` commands. Every command names root/trial/scope, the original shared ledger
and separately retained grant digest. Canary/worker additionally name the private
configuration; canary also names the pinned policy. Run each canary once. After both
pass, run the worker, inspect the protected desk, request education, import the fixed
supplement through the authenticated operator, and run the worker again. Restarting
with no pending job sends nothing. Existing explicit payer submission/inquiry stays
separate and retains its reference-service label and uncertainty controls.

Commands return bounded metadata, usage totals and payload-free local timings.
Timings describe the current invocation, not all historical spans or server billing.
Responses and reservations remain in the private stores for independent readback.
No document content is exported to Langfuse by this composition.

## Verification and limits

Local tests cover ordered admission, canary support, unknown usage, immutable history,
interruption, source/scope refusal before credential access, actual spawned fake SDK
plus SQL workflow/card readback, no-reservation refusal and slow-case lease renewal.
Fake SDK results are wiring evidence only. Required hosted checks still apply to
the final PR head. The source package, all eight production fields/slices, prior
model captures and clinical release requirements remain unchanged. Local parser and
clean-target restore evidence are documented in [the hardening guide](prior-auth-demo-hardening.md).
