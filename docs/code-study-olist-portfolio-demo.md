# Building and verifying the Olist portfolio demonstration

The owner clarified the product: a hosted portfolio demonstration with fictional orders
and SIM money. Start with [the acceptance plan](olist-portfolio-demo-finish.md). The old
production qualification records remain unchanged; this chapter does not mark them passed.

## References and measurements

Follow `cases()` in `olist_demo_acceptance.py`: six buckets, eight authored examples each,
six conservatively dependent groups. `prepare()` writes text-only inputs separately from
acceptable routes, amount-reference availability and fixture metadata, then hashes the
files. No amount reference becomes zero merely because it is unknown. These are declared
demo contracts, not independent language gold. Three trials describe repeatability without
creating new independent customers or a confidence bound.

`fixture()` in `olist_demo_fixtures.py` supplies fictional payment/status facts independently
of the model request. The partial request says 19.25 SIM after paying88.00SIM: interpreting
19.25correctly should still fail full-refund-only eligibility. Zero, over-cap, missing and
conflicting facts are separate policy paths. No fixture claims a real source-order link.

`summarize()` in `olist_demo_evaluation.py` validates scheduled identity and exact request/
route bindings. Missing and failed occurrences remain in the144slot denominator. Read the
verbatim-price test: a valid45.00SIMquote can still be the wrong semantic role. Parser
success is therefore separate from correct intent/amount, false refund routing and effects.
Unknown token or billing data remains unknown. Attempt latency excludes missing observations;
it must never describe the whole schedule as fast when only one request returned.

## Candidate to transaction authority

`DemoPlanner.plan()` sends the exact customer text through the unchanged inspected semantic
prompt/schema. It checks the response route and parses strict JSON/quote/arithmetic evidence.
`project()` maps unclear money and non-SIM explicit money to review; otherwise a missing
numeric refund amount may use the later policy's recorded total. It creates no provider,
grant, order fact, reviewer approval or customer consent.

Trace the resulting `RoutingPlan` through `CaseStore.submit`, `SupportWorkflow`, policy
proposal and `CustomerIntentStore`. Model choice is a proposal. A distinct reviewer is still
needed when requested; the customer must confirm the exact action/amount before the guarded
SQL transaction can create one receipt. Duplicate submission and a fresh application read
saved state. A checkpoint recovery proof is not a license to resend a provider request whose
response was lost before persistence.

The HTTP factory now supports an explicit canonical HTTPS opt-in. Default loopback behavior
is unchanged. Public cookies are Secure, HttpOnly for the session, SameSite strict and host
scoped; exact Origin/CSRF/Host checks still apply. A caller's forwarded host does not grant
identity. The deployment must disable arbitrary proxy-header trust and expose only its HTTPS
ingress. This factory is a seam, not a publicly deployed live-model runtime.

## Attempt admission and an accounting defect

Begin at `inspect()` in `olist_demo_budget_readback.py`. Four historical reservation stores
contain447+1+168+9=625attempts. The older PA report counted447+168+9=624and omitted the separate
Olist semantic canary. The new reader pins all schema/rows, reports unsettled reservations
and refuses unknown attempt namespaces. Do not edit an old receipt to make the totals fit.
That Nov17snapshot led to the owner-approved940ceiling. Preserve it as history. On Nov23
Revenue had added18calls under its separate50attempt scope: the complete count is643,
with169older plus32Revenue slots still bound. `inspect()` now verifies that namespace's
exact column/bounded-ordinal shape, counts NULL results as unsettled consumed reservations,
and preserves all50allocated slots across consumed/unused categories. The same146new Olist
calls need ceiling990and201retained slots. Unknown tables and changed Revenue schemas
still fail closed. This arithmetic prepares an amendment; it does not amend a grant.

`Scope.frozen()` in `olist_demo_study.py` binds exact requests, references, ledger path,
history, project, environment and limits. The expected schedule/reference cache stores only
immutable hashes; it never shares mutable request dictionaries. `initialize()` requires a
separate trusted owner grant for provider origin and touches only its new namespace.
`reserve()` runs under `BEGIN IMMEDIATE`, requires a settled prefix and both canaries before
domain work, and commits the reservation before I/O. A copied ledger has the wrong path.

`capture()` in `olist_demo_capture.py` checks the clean source/import/environment binding
before dispatch, then uses `IsolatedTransport` with the explicit SDK worker. The parent
owns/terminates each process; the SDK gets no retry or paid fallback. Unknown usage or a
failed canary/provider stops later dispatch. A lost parent leaves a consumed outstanding
reservation and blocks a blind resend. Readback reparses stored JSON with the wire validator:
ordinary `json.loads` plus strict Python validation had incorrectly rejected tuple fields;
the regression preserves that discovered distinction. Domain interpretation errors remain
observations, rather than triggering a prompt repair or hidden retry.

The fake path runs real SDK serialization against a network-denied mock transport. Its
oracle answers test plumbing and cannot pass the real model-quality target. Keep source
freeze, readiness, fresh provider observations, SIM effects and public recovery separate.

## Card-free hosting and recovery

Render Free is the web target; Neon Free stores durable SQL. The host's local disk is not
an authoritative attempt ledger. Start with `DatabaseConfiguration.verify_transport()` in
`olist_demo_host.py`; keep DSNs private and require hostname-verified TLS. `preflight()` checks
schema pins, database guards and role privileges. A role can inherit powerful managed-service
memberships even when its own attributes are false, so membership checks are also required.
Create the runtime role through restricted SQL, not the managed console's admin default.

`bootstrap()` refuses an existing application schema and never runs implicitly at startup.
`olist_demo_recovery.capture()` reads a coherent snapshot; `restore()` bootstraps a fresh
target, checks exact build/schema/inventory, copies the table bytes in one transaction,
independently reads all rows, and revokes sessions. A failed target remains for diagnosis.
This does not migrate a model allowance or establish encryption/off-host durability. Managed
database upgrades can invalidate binary restore compatibility. A local clean-target test
does not prove that an actual cloud account restores within its proposed RPO/RTO.

## Reproduce and discuss

### A stopped study is also evidence

The [Nov 23 live capture](olist-portfolio-demo-evaluation-2026-11-23.md) passed both
canaries and seven refund interpretations before an HTTP server failure at ordinal 10.
The recorded worker exited normally and did not time out. Exact status/body were not
retained, so the adapter branch supports only a server-error category. Usage and cost
remain unknown for that call. All 136 later requests remain unattempted.

`olist_demo_continuation.prefix_pin` binds the original SQL definitions/triggers, parent
scope and stop, and every original reservation/response byte. `Continuation.check` checks
this prefix, the unchanged other namespaces, request order, route, environment, expiry and
passed canaries. Its constructor requires a new independently supplied grant pin for
provider origin. Preparation calls the read-only validator and creates no authority.

`reserve` takes an immediate transaction, requires a settled contiguous prefix, charges
each unknown row the full reviewed route ceiling, and commits only the next exact ordinal
before SDK I/O. Two competing orchestrators cannot reserve the same next occurrence.
The amended capture may pause and move past a scored HTTP server failure; it never sends
that occurrence again. A quota/timeout/transport/worker failure, unexpected cost or token
ceiling, three consecutive server failures or an eighth server failure stops dispatch.
`readback` combines the original failed slot with later observations on the same 144-slot
denominator, and keeps original-stop preservation visible. None of this is active until
the owner approves the exact amended policy and frozen source.

Design limitation: the continuation grant is an externally pinned private study artifact,
not a public-service authorization endpoint. It preserves one local study ledger; it does
not solve distributed public runtime accounting. Unknown usage is conservatively reserved,
not reconstructed as observed consumption. Ask in an interview why a failed call must stay
failed even when the next identical-looking trial later succeeds.

Run `python dev.py check` for portable checks, then the opt-in SQL integration tests with
Docker. `tests/test_olist_demo*.py` covers hand-counted scoring, complete146mock admission,
crash/stop/path/history refusals and two actual spawned SDK canaries with networking denied.
`tests/integration/test_olist_portfolio_demo.py` exercises all48fixtures, protected HTTPS
flows, reviewer/customer effects, role isolation and fresh-target restore. Test responses
are invented; run the approved live study separately before advertising model quality.

Interview exercises: why does matching a quote not prove its role? Why is a status request
misclassified as a refund still a quality failure if customer confirmation blocks it? Why
can an ephemeral host reset a naive cost cap? How can a role's inherited privileges bypass
checks of its own flags? Why are encrypted upload, exact row restore, model-budget recovery
and measured whole-host RPO/RTO four different claims?
