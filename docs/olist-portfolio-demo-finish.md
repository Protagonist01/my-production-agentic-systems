# Olist hosted portfolio demonstration: acceptance and finish plan

Accepted scope on2026-11-17: a hosted demonstration using fictional orders and SIM money.
The owner approved the concrete five-step plan and selected free hosting. This is the
demo finish line; the earlier real-customer qualification requirements remain separately
documented and unmet. No payment processor or shipping integration is needed for this demo.

| Step | Concrete acceptance evidence |
|---|---|
| Reference contract |48authored cases in six buckets, separate input/expected metadata, explicit ambiguous amount exclusions and visible limits; review before freezing provider requests |
| Live evaluation |Two passed canaries, then48cases×3trials; all146scheduled attempts reported, failures preserved; actual model results separate from scripted/fake outputs |
| Complete SIM app |Actual model-derived requests enter durable scoped cases; customer exact action/amount confirmation, required reviewer, single exact effect, stable duplicate receipt, no work repeated on restart |
| Free hosted service |Configured account and free-only resource verification, canonical HTTPS origin, private PostgreSQL, persistent model accounting, isolated visitor state, hard call/concurrency limits and no paid fallback |
| Recovery and presentation |Encrypted off-host backup, clean-target restore and authenticated workflow/readback, actual timing/data-loss report, walkthrough, model card, URL and limits |

The proposed demo target is≥95%agreement on the frozen suite and zero observed unauthorized,
duplicate or over-limit effects. That percentage is an empirical score on declared demo
examples, not a population accuracy/confidence claim. Each advertised walkthrough must
work end to end. Do not waive state/privacy/customer authority because money is simulated.

## Reference construction

`olist_demo_acceptance.py` defines eight cases each for refund/status/reship/clarify/unrelated/
adversarial requests. Its48items are authored exposed contract tests. The six conservative
bucket parents are dependent groups, not proven independent language families or a fresh
holdout. Expected outputs and fixture types stay evaluator-only. Unknown amount references
are excluded from amount accuracy but retained in full scheduled counts. The original
five accepted publisher direct commands, conditional native intent references and earlier
source/licensing defects remain separate evidence; this suite does not relabel them.

The live study will freeze exact candidate, prompt/schema, input/reference packets,
environment, ledger history, trial order, limits and canary expectations. The146attempt
estimate is not a new grant. Current lifetime history has advanced through other agents;
the old447/614reader cannot authorize or describe the current aggregate allowance.

## Free-host constraints and proposed target

Research checked2026-11-17:

- [Render Free](https://render.com/docs/free) is an option for a demo web process, but its
  lifecycle/persistence limits require a separately durable database and accounting store.
- [Hugging Face Spaces](https://huggingface.co/docs/hub/spaces-overview) now requires a paid
  plan for newly created compute Spaces; this is not the card-free target.
- [Oracle Always Free](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm)
  offers eligible compute/storage that can fit the existing Docker architecture. Exact
  current account shapes/quotas must be verified; regional capacity and idle reclamation
  can prevent reliable availability. Account verification can require a payment card;
  do not upgrade to paid or provision trial-only resources.
- [Neon plans](https://neon.com/docs/introduction/plans) offer a possible external database
  for an ephemeral web host. Compatibility with this app's roles, schemas, checkpoints and
  exact-build archive format must be demonstrated, not assumed from the word PostgreSQL.

The owner subsequently required no card verification, so the target is **Render Free web
plus Neon Free PostgreSQL**, with the supplied HTTPS hostname. The earlier VM option is
rejected for this requirement. [Neon pricing](https://neon.com/pricing) explicitly offers a
card-free Free plan. No account is currently connected. Render may sleep, restart or suspend
at its limits; its filesystem is disposable. Cold starts do not meet the warm API latency
target and will be reported separately. Keep the sole database and authoritative model
accounting outside that filesystem. Account-specific signup checks still need confirmation;
stop if either service asks for a card or paid upgrade.

`olist_demo_host.py` checks remote hostname-verified TLS, exact application schemas and a
runtime role that cannot own/change guarded state or inherit managed administrator groups.
Its explicit bootstrap only initializes an empty dedicated database; it never runs on web
startup or overwrites a partial installation. Local SQL witnesses establish the role/schema
path; actual Neon connectivity and resource-limit behavior still need verification.

`olist_demo_recovery.py` captures the four application schemas and restores only into an
empty target with the exact same database build/schema, independently compares all rows,
then revokes old sessions. This does not recover a model budget or verify off-host encryption.
A managed-service build upgrade can invalidate this binary restore path; retain that limit
until a separately verified portable logical restore is available.

Public hosting is not activated by a template or this document. No paid domain, paid
storage, cloud purchase, account upgrade or unbounded model use is authorized.

## Bounded live-study implementation

`olist_demo_study.py` requires the exact 146 ordered requests, the same ledger path, a
complete historical snapshot, source/environment/reference/project bindings, seven-day
expiry and a separately pinned owner grant with current Free confirmation. Both canaries
must pass. It commits admission before dispatch, preserves failures and unknown usage,
refuses a resend after an unsettled crash, and stops on provider/usage/canary failure.
Domain interpretation errors are scored as errors without prompt edits or retries.

`olist_demo_capture.py` uses one spawned SDK process per attempt, with 90-second HTTP and
110-second parent bounds. `olist_demo_worker.py` has a separate network-denied SDK mode
for readiness. Mock origin cannot claim actual provider attempts or a model-quality pass.
The status canary repeats one declared domain text: this exposed suite is not blind.

Read-only audit found 447 base, one separate semantic, 168 PA and nine PA-live reservations:
**625 consumed**, all settled. The old total624omitted the semantic canary. Keep169old bound
slots and all historical failures. The new146attempt proposal therefore requires ceiling
**940**, rather than939. This is a proposal, not permission to amend any old grant. Actual
consumption remains below the old793ceiling; retained allocations overcommit it by one.

Readback keeps all144domain slots in the denominator, reports per-bucket joint intent/known
amount agreement, unknown amount exclusions, unsafe refund routing, parse/provider failures,
abstention, trial consistency, attempted p95 latency and known/unknown usage/cost. A correct
language route does not prove a safe effect. The 95% suite target needs at least137correct
joint slots, complete observations and real provider origin; it is not population accuracy.
Guardrails, cloud recovery and hosted acceptance remain separate required evidence.

## Delivery sequence

Build/verify the contract and application adapter first, then actual isolated SQL/HTTP
guardrails and the exact live-study proposal. Package the free-host ingress/persistence/
backup configuration concurrently. Run live calls only after the final owner grant and
selected-host readiness. Publish measured results and incomplete cases honestly. Finish
with one actual hosted workflow and one clean-target restore, then a demo model card and
walkthrough. Existing real-customer release gates remain separate and unchanged.
