# Controlled wider Olist provider execution

Prepared 2026-10-31 against base `7981fd4`, continuing #33. Implementation authorization
covers code and fake HTTP tests, not real provider requests, data export, an allowance
amendment, hosting or release. Current live allowance remains417/468,51historical unused
slots bound elsewhere,0unsettled as last read. Tests construct their own invented histories.

## What changes at the execution boundary

`RoutingProviderFactory` is a separate explicit composition. Old `RoutingMockFactory`,
its live-route refusal and `RoutingProtocol`'s non-provider status remain unchanged.
The new factory reuses the real wider workflow, SQL observer and duplicate/resume collector.
It requires a scoped shared ledger, pinned Free tariff/project association, exact variant
behavior, complete current executable inventory, one attempt, fixed model/template and
recording budgets. It discovers no credential and offers no automatic dispatch CLI.

`RoutingCaptureControls` constructs the installed Gemini SDK through `BudgetedTransport`
and `AccountedTransport`. Its hash includes all historical scope pins, the prospective
routing extension, project and tariff. The API key is excluded from hashes and repr.
This remains a local credential/project association, not provider-verified cloud identity.
Tests may explicitly inject `httpx.MockTransport`; its presence forces mock origin.
The extension's authorized origin must agree, so removing the fake transport is refused
for a mock scope. Read-back also refuses an expected provider origin for mock evidence.

Provider-origin entrypoints require clean pinned source. Every case/reference and task is
matched to its exact prospective slot before recording. Agent requests contain only the
customer text plus fixed system prompt/schema; labels and SIM facts stay evaluator-side.
The record uses independently read complete SQL state, exact receipt/message, original-run
budget and duplicate/recovery observations. `ControlledRoutingScorer` stops later dispatch
on unsafe/unknown state or observation failure. Fixture setup/cleanup failures also stop.
This is an evidence mechanism, not independent validation of the reference meanings.

## Parent observation fence before the next trial

Follow-up to merged PR127 (`9088cbf`): a response can settle before SQL scoring/frame
return. The retained local trial timeout had no report; batch read-back rejected the
missing receipts only after later tasks were scheduled. That is a pre-dispatch control gap,
not a successful readiness run or proof of an unsafe business effect.

`RoutingParentFence` now runs in the parent after each raw row is durably journaled and
before the next sequential task. It recomputes the complete prefix of canonical SQL
observations using `verify_observations`, then requires known `state_safety` and
`routing_safe` scores of1without scorer failure. Row errors, missing frame/report,
missing/corrupt observations or unknown/unsafe state persist an immutable ledger stop.
The next SDK reservation is denied even when the preceding response was already settled.
Later scheduled rows remain visible, so stopping cannot improve the denominator.

The shared runner's new optional `after_trial` callback requires max_parallel1. Journal
or callback exceptions set its abort event before queued tasks proceed. Fresh/baseline
recorders forward the optional callback; legacy callers with no callback retain their
contracts and behavior. The controlled model recorder always installs the fence. For
separately executed zero-call baselines, controlled orchestration must supply the same
fence if an unsafe baseline should stop later provider work. An arbitrary manual caller
that bypasses this recorder is not an approved study orchestrator.

This is a live parent barrier, not durable per-domain acknowledgment or authorized crash
resume. If the parent itself dies after settlement but before observation, no continuation
is authorized: preserve the partial journal/ledger and investigate; never infer safety
from settlement or simply start the next batch. A future resumable orchestration requires
its own durable observed-prefix authorization. Canary receipts already have a separate
durable acknowledgment gate. Real run-host readiness is still pending.

The regression uses a real owned process exiting37after SDK settlement and committed SIM
action, before scorer/frame. Parent-owned SQL captures before dropping each owned database
prove the first effect, no later effect and cleanup. The shared ledger must consume exactly
one domain call, retain the failure/remaining rows and refuse subsequent reservations.
This is process death in an invented fake-SDK mechanism test, not host-loss recovery or
production semantics. Actual results belong to the final PR checks.

## One durable allowance, distinct prospective slots

`agent_harness.routing_budget.RoutingExtension` describes exactly two canaries and144domain
slots:24cases,2model variants,3trials. Each slot binds ordinal, phase, variant, tenant,
case/reference, run, business event, snapshot, trial and exact request hash. The extension
also binds code, environment, policy, candidate versions/behavior, analysis/population and
actual owner approval reference/interval. A hash is not proof that an approval was genuine:
the trusted caller must obtain and persist the owner's actual instruction before appending.

`append_routing_extension` requires the exact settled417-attempt history and prior468scope.
It appends new immutable scope/slot/settlement/receipt/stop tables in the same database.
Old Python clients refuse the missing current external pin; a new SQL trigger also refuses
old binaries that try to insert attempts without the prospective routing slot. Existing
paired/model SQL guards remain active. New namespaced trace rows satisfy them without
altering historical rows or colliding when related cases repeat an identical request.

| Count | Meaning |
| --- | --- |
|417|Previously consumed attempts, preserved|
|51|Previously unspent allocations, still unavailable to this study|
|146|Proposed new allocations469–614|
|614|Proposed lifetime ceiling, not approved or applied|
|563|Maximum actual consumed-row count after417+146; no fictitious gap rows|
|51|Remaining historical allocations after all146new slots; routing still refuses dispatch|

Reservation uses `BEGIN IMMEDIATE`; the next exact slot is inserted before SDK dispatch.
There can be only one unsettled reservation. A worker crash leaves it consumed and blocks
subsequent dispatch. Duplicate, reordered, foreign or changed requests cannot reserve again.
Settlement records the canonical raw response privately, its hash, tokens and failure state.
Canary success additionally requires an exact successful accounted `AttemptReceipt` matched
to that reserved context/request/response. It is acknowledged durably before the next
canary/domain call is admitted. Missing receipt acknowledgment never becomes success.

Stop on first failed canary, auth/quota/budget denial, unknown/over-limit usage, three
consecutive timeout/unavailable responses, unsafe state, scorer failure or fixture failure.
The first stop is retained across clients. A stopped/unsettled/consumed request cannot be
retried implicitly. A monotonic dispatch watchdog refuses elapsed26100seconds or a clock
reset relative to the first reservation, under the single-host study clock assumption.
The elapsed guard is rechecked on every reservation; its refusal transaction rolls back,
so the guard remains effective even though that particular stop row is not committed.
This is not host-loss recovery or proof of a production SLO.

## Why the prospective protocol differs from planning v1

The original private proposal remains unchanged. Its SDK-only preflight verified50payloads,
not a provider-capable H10 composition. Implementation found two conflicts:

1. H10 requires three sequential trials per recording. Prospective v2 uses case/variant
   three-trial batches, alternating the first model variant by case. Deterministic
   comparators remain separate zero-call recordings. Counts stay24cases/288workflow trials,
  144model attempts plus2canaries. There are96recordings, each with3trials.
2. The existing `GeminiFreeAdmission` conservatively reserves the documented complete model
   ceiling,1,114,112tokens per request. A4096token context is denied before dispatch.
   Keep that admission rule. Prospective v2 reserves this ceiling per model attempt,
  3,342,336per three-trial recording and162,660,352over146attempts. These are conservative
   reservation ceilings, not expected consumption. Output remains512tokens and inputs
   remain the same short exact requests. Unknown consumption is never reported as zero.

The proposed HTTP limit is30seconds, owned worker90seconds, and batch context deadline
300seconds from admission of that three-trial batch. This accommodates the bounded workers
without stamping the whole hours-long study with expired short contexts. Do not refresh a
consumed request or extend a deadline after observing its output. Parent timing includes
setup and cleanup and cannot assess the accepted client-facing30second model-decision SLO.
The paid-spending limit remains0USD with no paid fallback, conditional on current Free
account/tariff attestation. Derived zero Free cost is not provider billing evidence.

`capture_canary` owns a90second child and clamps SDK HTTP to30seconds. It seals private
receipt/timing/control/origin files and verifies the raw settled response before acknowledging
the canary gate. A failed capture stops, not retries. A known-answer canary accepts runtime
optional defaults (omitted requested amount meansNone), but rejects extra/duplicate fields,
wrong routing version, boolean schema versions and unsupported answers. No semantic-quality
or capacity conclusion follows from those tiny invented probes.

## Accounting and full denominators

The additive optional `CostAccounting.capture_scope_sha256` binds new derived-cost evidence
to the exact extension. `control_pin` and canonical accounting bytes remain unchanged when
that field is absent, preserving legacy receipts. Verification recomputes the derivation
from raw usage and scope rather than trusting a claimed zero. The raw provider cost may
remain unknown; no billing result is invented.

`ControlledStudyProtocol` binds the prospective extension, origin, project, tariff and all
four comparator pins. `assemble_controlled` accepts separately domain-verified single-case
recordings. It checks exact reference membership, candidate/control/origin, three-trial
manifest and run identities before projecting binary/unknown fields. Missing or unreadable
recordings stay missing in the288-row denominator; rejected evidence must not be replaced
with fabricated successful rows. Per-field, case/all-three, cohort, route and parent-group
analysis remains development-only. Historical v1 assembly remains mock-only.

There is no independent semantic gold or fresh holdout here. Labels were accepted by the
owner for development, not blind review. Preserve separate ABCD/constructed-fixture and
fully authored stress reports; do not blend them into a production accuracy headline.
The accepted95%planning targets do not convert this small exposed cohort into qualification.

## Reproduce the bounded checks

```powershell
python -m pytest -q tests/test_routing_provider_controls.py tests/test_provider_budget_accounting.py
python -m pytest -o addopts='' -q tests/integration/test_olist_controlled_provider.py
python dev.py check
```

Use the locked environment and, on this Windows host, the existing D-drive private TEMP/TMP
directory. The unrelated `C:/.git` marker must not be removed to weaken path guards.
The first test helper constructed512token requests with an inherited100token run budget;
the planner correctly clamped them to100 and the frozen request guard refused reservation.
Correct the test helper's reviewed admission budget, not the guard. Focused tests passed
after correction. Local SQL again failed at Docker Compose startup before any new body;
hosted PostgreSQL must execute both new tests before merge. No local SQL pass is claimed.

The tests use invented417-row histories and copied invented databases only. They never read
or clone the real allowance, load a real key or export source cases. Network-denied SDK
checks and owned child tests retain mock origin. Hosted SQL exercises actual parent/worker/
SDK fake HTTP/ledger/accounting/receipt/state/read-back and an injected unsafe semantic
decision that must stop further fake dispatch. Actual final results are recorded on the PR.

The initial hosted audits failed on four reported vulnerabilities in the existing pyasn10.6.4
dependency (CVE-2026-119194–119197). A scoped lock update selects0.6.5; no audit suppression
or policy change. The [upstream release](https://github.com/pyasn1/pyasn1/releases/tag/v0.6.5)
describes fixes for pathological decoding CPU growth. Audit and full final-head results
must be checked again after the update; the earlier failed run is retained.

## Before actual calls

Freeze a new v2 execution plan against verified clean final code, exact accepted packets,
three-trial batches, request hashes, conservative resources and all comparator behaviors.
Reference the earlier planning proposal as history. Approval timestamps and the final
authorization envelope must reflect the real owner reply, not a backdated proposal date.
Full control/candidate hashes include that envelope and are finalized deterministically
after approval, without changing the reviewed behavior/requests/labels/resource rules.

Obtain explicit authorization for the precise text export, at most146new Free attempts,
614shared lifetime ceiling, expiry and stop conditions. Verify current Free/account evidence
and route availability under that scope. Only then append the reviewed amendment in the
same real ledger and publish the new external pin privately. Do not initialize another
allowance, reuse the51old slots or run a canary from implementation approval. Final release,
reference/holdout validation and deployment/recovery acceptance remain separate.

References: [Langfuse input/reference separation](https://langfuse.com/docs/evaluation/experiments/datasets)
and [Gemini structured output](https://ai.google.dev/gemini-api/docs/structured-output).
The implementation uses the installed SDK and local deterministic scoring; no Langfuse
dataset upload, API migration or new dependency is introduced.

The lock repair intentionally invalidated the old invented replay environment. Preserve
invented-v14 and add a synthetic v15 capture with the new lock; all six fake requests and
responses are unchanged. The CLI uses an explicit reviewed v15 digest, while v14 joins the
historical refusal tests. No runtime dependency-equality check or fixture trust rule is
weakened. The repaired-head failed quality job is retained along with the initial audits.
Local Windows SQL artifacts also retain a90second worker timeout; hosted PostgreSQL passes
are separate evidence. Real execution still needs readiness on its selected run host.

The retained local fake canary also exposed a test spawn dependency: its HTTP callback
imported the full history fixture module before worker entry. The unchanged callback now
lives in the small json/httpx-only `tests/routing_sdk_fake.py` helper. Owned startup limits
stay90seconds; the callback's old import path is re-exported for existing parent callers.
This removes unnecessary test imports, not evidence of real provider/model availability.


The parent-fence SQL process-death test passed locally (1test,2deselected,299.29seconds).
It proves only that invented after-action death path and denial/cleanup observations.
A separate targeted rerun passed all four new unit regressions while the existing SDK
child again timed out at60seconds (4passed/1failed/85deselected,191.80seconds). The helper
move therefore does not certify local run-host readiness. Preserve both results and use
final hosted PR/main checks for merge acceptance; live evaluation still needs its own
complete selected-host readiness and actual scope/account approval.
