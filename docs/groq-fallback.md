# Groq Free fallback preparation

The user selected Groq Free on2026-10-26. This prepares #25 while #33 and final cross-provider
domain studies remain pending. The shared180Gemini allowance remains separate and unused.
Do not infer equivalent quality from API compatibility, strict JSON or a connectivity smoke.

## Supported route

Install `production-agent-harness[groq]`. Its extra adds the already locked HTTPX0.28.1,
JSONSchema4.26.0and referencing0.37.0; it needs neither Google nor Groq/OpenAI SDKs. Base imports
remain provider-free. [`groq.py`](../harness/src/agent_harness/groq.py) pins provider `groq`,
endpoint `https://api.groq.com/openai/v1/chat/completions` and model `openai/gpt-oss-120b`.
The model identifier is not a guarantee of immutable provider weights/revision.

Current [Groq deprecations](https://console.groq.com/docs/deprecations) exclude Llama3.3from
Free/developer routes. [Strict schema documentation](https://console.groq.com/docs/structured-outputs)
supports GPT-OSS120B, with all object properties required and additionalPropertiesfalse.
The adapter validates supplied schemas locally with no external references. Initial support
is text or strict object output, one completion, no streaming/tools/tool history/provider
parts/revision pin. Unsupported requests fail before HTTP. It does not weaken a schema to
make another provider accept it. Optional parameter defaults are versioned adapter behavior:
max_completion_tokens1024(up to2048), temperature0and reasoning_effortlow.

HTTP disables environment proxies, redirects and automatic retries, caps request/response
bytes and bounds IO time. Use [`GroqWorker`](../harness/src/agent_harness/groq_worker.py) inside
the existing IsolatedTransport for a parent-enforced wall deadline/owned-process cleanup.
Credentials have no ambient loader and are excluded from worker repr. Output is locally
validated; partial/ambiguous/wrong-model/refusal/tool/schema-invalid output fails. Valid raw
prompt/completion/total counts survive invalid content; missing counts/cost remain unknown.
Boolean/negative/inconsistent accounting rejects. No zero provider billing is inferred.

GroqFreeAdmission requires explicit billing-disabled Free-account attestation and reserves
the [published full input/output ceilings](https://console.groq.com/docs/model/openai/gpt-oss-120b)
(131072+65536tokens) and0USD. This is admission capacity, not observed usage or verified
billing. Actual account/organization limits can be lower; [rate limits](https://console.groq.com/docs/rate-limits)
produce failures, with no hidden retry or paid fallback.

## Explicit provider change

[`provider_routing.py`](../harness/src/agent_harness/provider_routing.py) accepts a byte-pinned
RoutePlan with two different providers and exactly equal messages/tools/schema. Parameters
remain separate because Gemini and Groq use different vocabularies; freeze each explicitly.
Two BoundedGateway instances must share the same SharedControls and allow one attempt each.
Their provider/endpoint/model/tenant circuit keys remain separate. A total run cap/deadline
applies across both. Only timeout/rate/unavailable failures permit a fallback; authentication,
schema, policy and exhausted-budget failures stop. Business authorization remains outside
model routing, and this adapter never invokes tools.

FallbackRouter.execute returns RouteResult with both requests/responses, selected provider,
context/plan pins and combined usage. It deliberately is not a drop-in ModelGateway alias:
no Groq response is relabeled as Gemini. Keep each ProviderGateway exchange and controlled
call for independent quality/cost analysis. With strict replay, both use ReplayAttempts on
the same StrictReplayGateway; exact occurrence/request mismatch propagates, and assert_complete
is still required. A replay run cannot silently call a live route.

## Separate invented-only smoke budget

[`groq_smoke_budget.py`](../harness/src/agent_harness/groq_smoke_budget.py) is a narrow smoke
mechanism, not the Gemini grant or an authorization for private domain records. Freeze a
SmokeAllowance with actual user authorization/Free-attestation references, credential hash,
exact invented request fingerprints, interval and at most12total attempts. Exclusively
initialize one private SQLite file; retain its external grant pin. There is no reset CLI.
Use SmokeTransport around IsolatedTransport(GroqWorker(...)), then ProviderGateway and
BoundedGateway. Reserve before dispatch under BEGIN IMMEDIATE; failures, throws, crashes and
unsettled attempts remain consumed. Reusing a file refuses; wrong key/request/agent/expiry
refuses before dispatch. Only fresh_candidate/groq-invented-smoke scopes qualify.

For reproduction, prepare three invented prompts: exact marker text, answer42for19+23in a
closed integer schema, and review/refund routing where the invented policy requires known
payment and the supplied payment is unknown. Seal expected values/requests before responses;
schedule two distinct trials each, with one attempt and a60second parent bound per trial.
Stop on a provider failure, preserve scheduled missing rows, and never rerun failed rows.
This six-call plan is below the12cap; duplicate trials measure smoke consistency, not new
source groups. Keep the key/plan/grant/ledger/receipts/timing private outside publication.
Publish only aggregate pins/counts with unknown raw cost and no domain/release claim.

## Verification and limits

Invented tests cover strict payloads, malformed/truncated/schema-invalid content, retained
usage, no redirects/retries/error echoes, changed routes/schema, outage routing, per-provider/
tenant circuits, shared run caps, exact two-provider replay and mismatch failure. SQLite
tests race final reservations, retain failed/unsettled attempts, refuse wrong scope/key/time,
and prevent accidental allowance reset. These are trusted-owner/single-ledger controls, not
protection from a malicious database administrator or a distributed quota system.

Live smoke and final exact-head hosted acceptance are recorded after actual execution.
Private CFPB/Olist/Revenue/PriorAuth/Supply records have not been authorized for this smoke.
Closing #25 still requires #33 and separately frozen/reviewed domain quality/cost/schema
comparisons; a smoke pass supplies no clinical or business-accuracy claim.
