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
