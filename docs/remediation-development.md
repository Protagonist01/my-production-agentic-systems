# Exposed-case Revenue development test

2026-10-27. The user explicitly approved24additional Gemini Free attempts, increasing the
same shared lifetime allowance from320to344. This is development on12exposed failure
families,twotrials. It is not new qualification or production release. PR118's failed
296attempt study and all original source/publisher/reference artifacts remain preserved.

The [prepared proposal](data/remediation-development-proposal-v1.json) selects six answerable
and six no-answer families across12categories,covering false decisions,invalid citations
and the provider invalid-response case. No expected publisher labels go to the model.
The approved combined candidate changes model to Gemini3.8Flash,asks for one unique
verbatim quotation<=300characters,and permits2048outputtokens. This experiment tests that
combined candidate;it cannot attribute any change to one component or establish general
quality from twelve exposed cases. Keep temperature0,LOWthinking,no tools/retries/fallback.

## Ledger and projection walkthrough

[`DevelopmentExtension`](../harness/src/agent_harness/provider_budget.py) binds the original
grant pin,320amendment pin,344maximum,320starting consumption,Revenue,3.8Flash,run ID,
12unique request pins and approval/expiry. `extend_development` holds an immediate SQLite
transaction,checks the current authorized state and refuses unsettled reservations before
creating an immutable extension row. Original grant,amendment and attempts stay unchanged.
All three pins are required by current clients. Older code retains a320cap and is exhausted;
new stale clients refuse missing extension pins before provider dispatch.

`AttemptLedger.reserve` checks the extension scope before inserting an attempt. The
`development_slots` table has a unique(request pin,trial ID)key and ticket:each of the24
approved slots can reserve once. Both tables update atomically;duplicates roll back rather
than consuming a second attempt or dispatching. Death after reservation still consumes
budget;settlement never refunds. Local pins and the operator's authorization are trusted
inputs,not a provider-verified billing identity or authentication service.

[`development_request`](../projects/revenue-integrity/src/revenue_integrity/remediation_development.py)
accepts only the model-only private request and original `ExtractionInput`. It revalidates
the reviewed prompt digest,route,decoding policy,schema and exact context/question projection.
`parse_development` requires the actual3.8Flash response,strict JSON without duplicate keys,
consistent accept/reject/abstain schema and exactly one short accept quote. Existing unique
whitespace alignment maps raw quotes to exact original offsets without changing punctuation,
case,digits or negation. Literal presence is not semantic support. The v1/v2parsers and
historical reports remain unchanged.

Freeze the proposal/model-input pins,actual executable inventory,parser/operator protocol
and exact24slot schedule before capture. Report all24scheduled rows,including missing,
invalid,abstained and failed responses. The development readiness screen requires all
decisions/citations complete and both trials correct for all12reference families. Failure
means no new final qualification capture. Success also cannot establish5%error confidence:
this cohort is small and fully exposed. Raw cost remains unknown absent billing evidence.

Tests in [test_remediation_development.py](../tests/test_remediation_development.py) use
invented data:prompt/context/model/schema/parameter substitutions refuse;long,multiple,
ambiguous,changed or duplicate-key quotes refuse. Ledger tests preserve320rows,fill24slots,
refuse stale/foreign/duplicate slots and compare history after reopen. No tests make provider
calls or establish semantic/legal/billing validity. No full security scan is claimed.

An interview exercise:trace a duplicate trial through BEGIN IMMEDIATE,scope validation,
the unique slot insert and reservation rollback. Explain why a process crash consumes a
slot and why success on twelve exposed families cannot establish a final confidence bound.

## Current execution

Implementation/checks precede capture. Actual results/accounting and hosted/postmerge
acceptance will be recorded after completion. No promotion or additional spending beyond
344follows from this development authorization.

## Actual result and operator correction

The development screen **failed operationally**, with no usable model decision. The
[audited result](data/remediation-development-result-v1.json) preserves24scheduled outcome
rows:18local unsupported-request refusals,two dispatched timeouts,one dispatched unavailable
response and three circuit-open denials. Those last three stop before reservation. The
same ledger is **341/344consumed,three remaining,zero unsettled**. No failed slot was retried
or refunded;three remaining attempts are not permission to replay completed denied rows.

The first operator constructed GeminiWorker with default Flashflagfalse while enabling
Flash in admission. All18local failures reported model_calls0. I stopped at a settled
boundary after identifying the mistake;these reservations still count. Actual offline
payload preflight then also detected the legacy512output ceiling. Correct both before
continuing:use `development_worker` with explicit Flashflagtrue,and a separate
`FlashDevelopmentParameters` contract permitting<=2048only for opted-in3.8requests. Legacy
Lite512limit remains. Tests prove2048Flash accepted and2049orLite2048refused without network.

Freeze a separate correction record at9280486with the unchanged original24rowrequest/
context schedule and a new executable inventory. Only six untouched original no-answer
trial2rows are eligible. Two actual requests time out at the adapter's existing30second
HTTPceiling despite the parent's60secondbound,then one reports unavailable. Shared circuit
protection blocks the finalthree before reservation. Do not bypass the circuit or infer
that increasing timeout would fix availability. Preserve every failed outcome and both
operator versions. This is not an intact fixed-operator two-class study or model comparison.

Independent audit matches all21new reservations to context/request/response pins and
unique slots,checks the three unreserved denials,verifies the original320attempts/grant/
amendment unchanged,and rechecks312old artifact files. The prior candidate scored2/24on
these deliberately selected exposed observations;the new run supplies no valid comparison.
Three provider calls report unknown token usage. The18local refusals also have unknown
token fields;zero reported calls do not turn those unknowns into measured token counts.
Across24rows,21token/cost observations are unknown;three pre-reservation circuit denials
carry known zero usage. No monetary zero-billing claim is made.

The actual pinned Google SDK is also tested through a mock HTTPtransport:its3.8request
contains2048outputtokens andone-quote schema,a constructed response parses and maps to
exact source evidence,one request occurs and no network connection is used. This verifies
local serialization/parsing;it does not verify remote availability or candidate quality.

Further work must begin with a bounded operational canary and an affordable new protocol
before another24case development run. No new calls are authorized by this document.
The prior5%confidence target,failed296attempt study and release gates remain unchanged.
