# Requested-money references and the next candidate comparison

Prepared 2026-11-11 from main `fd4ef0c` (#152). This follows the measured routing
weaknesses in [the native intent pilot](olist-native-reference-readiness.md). It adds an
exact licensed source snapshot, a strict applicability audit, a proposed language candidate,
single-use execution controls and independent readback. Provider results do not exist yet.

## What we actually found

The publisher's official GitHub history retains an entity-tagged training CSV **and its
license in the same immutable revision**:
[Bitext revision 8b6ca3d](https://github.com/bitext/customer-support-llm-chatbot-training-dataset/tree/8b6ca3d9559a4a9abab94f7978fae67019215a82).
The exact LICENSE.txt is CDLA Sharing 1.0. Original bytes and all publisher notices are
retained privately. This separately received source does not retroactively resolve the
earlier Hugging Face copy's permission gap. No source row or annotation was repaired.

| Check | Actual result |
|---|---:|
| Native rows |4,514|
| Native refund_amount annotations |63|
| Exact value at zero-based, end-exclusive native offsets |20|
| Native spans outside instruction bounds |16|
| Proposed direct-command references meeting every condition |5|
| Distinct number-masked wording templates among those five |4|
| Distinct requested numeric values among those five |2|

The proposed predicate requires native `get_refund`, exact full numeric value/span, the
publisher's documented context/model-role convention, and a whole instruction consisting
of `refund` or `reimburse` plus a dollar-marked number. No additional clause, payment-price
mention, negation, quoted instruction, conditional or malformed number is admitted.
The pinned README says `role` is the role the model should adopt; `instruction` is the
user request. Treating the role as the speaker would incorrectly exclude every row.

The five rows are **proposed limited external development references**, not independently
validated arbitrary-language gold. Their original ordinals are 2743, 2792, 2830, 2841 and
2864. A dollar sign or the word dollars does not establish USD, CAD or another ISO currency.
The proposed value means nominal dollar hundredths. There is no currency conversion to SIM
and these inputs cannot authorize a business action.

The strict subset cannot cover implied refunds, arbitrary payment/request distinctions,
numbers in words, reshipment, clarification, adversarial language or representative customer
traffic. Four masked templates do not prove four independent generation families. Public
data may also have been seen in model training. These remain explicit limitations, not
conditions silently removed from the release gate.

## A concrete development comparison

The private packet contains these distinct strata:

| Stratum | Inputs | Intent reference | Amount reference |
|---|---:|---:|---:|
| Proposed native direct commands |5|5 proposed|5 proposed|
| Native payment/request-role contrasts |3|Unknown|Unknown|
| Existing accepted native intent examples |4|4 conditional development|Unknown|
| Unchanged accepted constructed grammar |12|12 constructed development|12 constructed development|
| Total |24|21 conditionally scorable|17 conditionally scorable|

All examples are exposed development. A fresh model response is a new observation; it does
not turn an exposed example into fresh holdout. Keep the native and constructed strata
separate in reports. Three trials per input measure repeatability, not 72 independent
language samples. Unknown references stay in the inventory without becoming correct null
labels. Three price-role contrasts are diagnostic inputs, not repaired source labels.

The proposed candidate is Gemini 3.5 Flash-Lite with a fixed system prompt, exact input text
and strict output schema. It returns intent, explicit/no-explicit/unclear/not-applicable
money status, integer hundredths, currency class and a literal amount quote. It has no
tools, state, payment capability or authorization. JSON/schema/quote/arithmetic validation
can reject malformed evidence; it cannot prove the quoted number's requested-money role.
An invented regression deliberately demonstrates that distinction with a price quote.

Google's [structured-output documentation](https://ai.google.dev/gemini-api/docs/structured-output)
supports schema-constrained extraction. The [current model documentation](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite)
identifies the selected route. These capabilities establish neither model correctness nor
the reference labels. The private study keeps a current pricing snapshot and uses the
existing separately attested Free-project association; derived zero cost is not observed
provider billing, and missing usage/cost remains unknown.

Proposed execution: **two invented representative canaries, then 24 inputs × three trials**
= at most 74 fresh provider attempts. Both canaries must pass before any domain input.
Any provider/parse/usage/readiness failure stops later dispatch; failed and missing slots
remain visible. No automatic retries or paid fallback. Incorrect but mechanically valid
domain predictions are recorded as errors and do not silently change labels or prompts.
Deterministic comparator captures can run separately with no provider requests.

## The allowance amendment needed

The shared ledger was rechecked read-only: 447 consumed, zero unsettled and one original
stop. The old routing study expired. This proposal would transfer 74 of its 116 unattempted
bound routing slots to the new scope; it would **retain the same lifetime cap of 614**,
preserve 93 other bound slots, and retain the original stop and all historical rows.
No slot has been transferred and no new live scope has been installed.

A separately trusted owner grant must name the exact scope, accept the limited direct-command
reference method, approve this source export/reallocation, confirm the existing project is
still Free, and authorize an interval of at most seven days. Generic implementation autonomy
does not amend the old study. No new ledger, stop deletion or reuse under old permission.

## Trace the implementation

1. [olist_licensed_amount_audit.py](evaluation/olist_licensed_amount_audit.py) checks all four
   source/documentation byte pins, exact schema and row count; inventories every native
   amount annotation; and proposes only exact direct commands. Exclusive private output
   saves source frames, references and a manifest last. Separate readback recomputes all
   bytes and projections against an externally held manifest hash.
2. [olist_semantic_candidate.py](evaluation/olist_semantic_candidate.py) accepts only text.
   Its fixed prompt/schema never receive labels or publisher responses. `parse` rejects
   duplicate fields, wrong types, money fragments, invented quotes and arithmetic mismatch;
   it preserves ambiguity and cannot infer ISO currency or customer authority.
3. [olist_semantic_controls.py](evaluation/olist_semantic_controls.py) opens an **existing**
   ledger with `mode=rw`, validates the exact historical schema/row anchor and pending-slot
   arithmetic, then appends a new immutable scope/attempt/observation namespace only under
   a separately trusted grant. Each reservation commits before dispatch. Another reservation
   refuses an unobserved, failed, repeated, out-of-order, expired or wrong-origin slot.
   Observation can settle a consumed attempt after expiry; expiry prevents new dispatch.
4. [run_olist_semantic_comparison.py](evaluation/run_olist_semantic_comparison.py) verifies
   clean HEAD, editable imports, all harness/Olist Python bytes, lock/config, actual Python/
   OS/distribution environment, fixed requests, input packet and canary expectations. It
   uses a spawned owned worker, 90-second HTTP/110-second parent limits, raw response before
   derived accounting, and durable parent observations. Fake SDK mode denies socket/DNS
   access and cannot claim provider origin. There is no implicit scope installation,
   credential discovery, resume, retry, app startup or SQL business action.
5. [read_olist_semantic_comparison.py](evaluation/read_olist_semantic_comparison.py) checks
   external scope/completion pins, original requests, complete consumed/observed prefix,
   raw versus derived usage, canary results, parent continuation and reference/input pins.
   It recomputes field-specific denominators and reports native/constructed strata separately.
   Inputs whose money reference is unknown never receive a no-amount target.

These are trusted local research tools. Source hashes and grant transcriptions establish
custody and declared scope, not cryptographic owner identity, independently established
semantic truth or protection against a fully compromised host. Raw artifacts remain private.

## Reproduce the source step

```powershell
uv run --locked --all-packages --link-mode copy python -m docs.evaluation.olist_licensed_amount_audit --source <private-exact-source> --output <new-private-audit>
uv run --locked --all-packages --link-mode copy python -m docs.evaluation.olist_licensed_amount_audit --source <private-exact-source> --output <saved-private-audit> --verify-manifest <separately-held-pin>
```

Private source: `D:/document/.cache/production-agents/olist/licensed-amount-source-2026-11-11-v1`.
Corrected audit: `licensed-amount-applicability-2026-11-11-v3`, manifest
`ddeb9724f4c5bbf3c70014b4d68f3f1dc5711eed3d10f343d16f466453cd0aed`.
Method review: `semantic-reference-method-review-2026-11-11-v1/review.md`.
The original zero-candidate role-convention audit and subsequent unsupported USD inference
remain separate historical runs with frozen scripts; v3 corrects both without rewriting them.

## What this can finish and what it cannot claim

This supplies a concrete reference-development package and runnable prospective evaluation
mechanism. A completed authorized run can measure this candidate against applicable limited
references, show errors/unknowns and guide the next implementation decision. It cannot meet
general-language qualification by repetition or manufacture missing amount-role truth.
All eight fields and required holdout slices, ≥95% planning targets, zero critical effects
and independent operational/recovery evidence remain required for the unchanged release goal.
Customer confirmation is action authority, not proof that the original interpretation was
correct. The independent reference/evaluator qualification problem remains documented.

Interview exercise: explain why an exact publisher span may still label a price; why the
source's role column is not the speaker; why `$` cannot become USD; and why 74 fresh outputs
cannot be advertised as a representative language benchmark. Trace an SDK timeout from
durable reservation through unknown usage and the refusal of the next slot.
