# Revenue answerability confidence-target study

The owner approved320total Gemini Free attempts on2026-10-27:24already consumed and296new
attempts, shared through the existing ledger. No paid fallback or automatic retries. This
study tests original CUAD publisher-relative answerability; it cannot qualify billing,
legal advice, Olist, CFPB or production release by itself.

## Frozen design

Select148distinct known unexposed source-development families from the existing pinned
CUAD source, preserving original corpus holdout and all earlier failures. Each family and
exact context appears once. Exclude four historical exposure inventories (128known families).
The former12kcharacter cap leaves30families;20kleaves69. A new explicit50kcap provides154
families before final unique-context/request and category balancing. Existing pilot/default
request limits remain20k. No truncation, publisher-label edits or outcome-based resampling.

Choose74answerable families first, then74no-answer families, choosing the least-used category
then case hash. Exclude document/party/agreement/effective-date categories, maximum16per
category. Two of each class are calibration;72of each class are prospective validation.
Two trials per family give296scheduledattempts. Preserve the current prompt, temperature0,
512output-token cap, LOWthinking and Gemini3.5FlashLite route. Use the opt-in whitespace
parser with exact source-span reconstruction; compare old literal parsing on the same raw
responses without additional provider calls. Labels, split and family IDs stay local.

Freeze the source inventory, cohort, schedule, protocol and executable revision before
capture. No replacement rows, tuning or retries after outcomes. Infrastructure permission,
quota or budget denial stops capture and leaves unobserved scheduled rows missing. Other
provider/parser failures remain in the denominator. The ledger reserves before dispatch;
one shared append-only amendment preserves the original24attempts and original grant.
Both original and amendment pins are required; old clients refuse after amendment.

## Target and interpretation

Use the existing qualification report:144validationgroups,72perclass, full decision
coverage, at least95%scheduledaccuracy, no false accepts, at most5%false rejects and at
most5%group-error upper bound overall/perclass. With zero failed groups, the exact two-sided
95%binomial upper boundary at72groups is about4.9944%. One failed group at this size exceeds
the target. Either trial failing makes its family a failed group; repeats never increaseN.
These are marginal per-class confidence intervals, not simultaneous95%confidence across
all endpoints. Independent/comparable inferred families remain an unverified assumption.
Category-level bounds are descriptive; this sample cannot establish72groups/class/category.

The zero-event boundary follows the [NIST binomial confidence-interval equations](https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm).
The existing frozen reporter uses that exact boundary at zero/all events and Wilson bounds
otherwise. The offline audit also computes supplementary exact Clopper-Pearson per-class
intervals by binomial-CDF inversion, checked against NIST's25item/20success example. These
are labelled supplementary diagnostics; the primary frozen report and criteria are unchanged.

Treat publisher labels as reference-relative evidence; public corpora may have appeared in
model training. Category balancing/short-context eligibility is a convenience distribution,
not a production prevalence sample. A larger attempted sample cannot guarantee success.
Release gates and accepted legacy standards remain unchanged pending applicable evidence.

Raw costs remain unknown unless independently evidenced; token usage is reported separately.
Free configuration is an operator attestation, not provider-verified billing. Same approved
private credential association; no Groq domain use or alternate billing route.

## Execution status

Preparation and checks are in progress. No new provider response is claimed by this document.
Actual aggregate and exact CI/postmerge evidence will be appended after capture.

## Remediation direction if the target fails

More observations do not repair a candidate whose error rate exceeds the limit. Treat this
entire cohort as exposed development material after the study. First classify publisher
disagreements, schema/transport failures, ambiguous citations and non-whitespace quote
changes. Preserve publisher labels, original responses and failing primary report. Never
make matching more permissive solely to turn observed failures into passes.

Use exposed cases to develop a separately versioned candidate: shorter unique verbatim
evidence and sufficient structured-output allowance are testable hypotheses; a stronger
already-supported Free Gemini route is another. No improvement is claimed until tested.
Keep development attempts separate from a new frozen final cohort and retain failures in
both budgets. The current320total grant cannot fund calls beyond320; obtain a concrete new
cap/scope before dispatch. Do not automatically launch another296attempt run.

Plan the next sample against a plausible development error rate and desired statistical
power, not just the zero-error minimum. Retain the5%target. A small development pass cannot
establish that target, and a larger sample cannot make a genuinely excessive error rate
acceptable. Future reference data, family independence, source holdout use and model scope
must be resolved explicitly before consuming a new final cohort.

## Code walkthrough and limits

[`AllowanceAmendment` and `amend`](../harness/src/agent_harness/provider_budget.py) accept a
prior grant pin, explicit authorization reference,320maximum, approval/expiry and exact
consumed count. `BEGIN IMMEDIATE` serializes amendment versus reservations. Re-read the
original grant and current attempts; refuse outstanding attempts, stale counts or invalid
intervals before inserting the amendment. Original authorization/attempt rows are untouched.
The new table has immutable update/delete triggers. Its canonical pin lives separately in
private external configuration; `AttemptLedger.authorization` checks both pins and refuses
missing/extra amendments. `reserve` still binds provider, model, credential association,
deadline and shared count before dispatch; `settle` never refunds. The owner instruction,
private pin and source scope remain trusted operator inputs, not an authentication service.

[`prepare_confidence`](../projects/revenue-integrity/src/revenue_integrity/confidence_study.py)
validates same-source exposure inventories and literal publisher spans before selection.
Cache context/request hashes to avoid repeatedly serializing thousands of long documents
for every selected family. Choose answerable first because its family subset is smaller;
then select no-answer from remaining families. Updating exclusion sets immediately prevents
reuse under a renamed case or family. `ConfidenceCohort.bound` recomputes request/reference
pins, unique families/contexts, exact class/split balance and296scheduled case/trial/input
tuples when loading the saved artifact. The entire private cohort contains labels and must
never be sent to a model. The projection accepts only `ExtractionInput` context/question.

The named50klimit is explicit in this study's request/parser calls. Legacy defaults remain
20kand historical captures are unchanged. The model decision and original quote text are
preserved; the opt-in parser maps unique whitespace-only matches to exact source offsets.
Citation presence and successful mapping do not establish relevant semantic support.
Qualification compares decisions to publisher answerability references and treats invalid
outputs as failures, rather than scoring only successful responses.

Tests in [test_confidence_study.py](../tests/test_confidence_study.py) use invented cases:
substitute a family, context, reference, split or schedule hash and loading must fail.
Fewer independent families must refuse rather than resample. The amendment test consumes
and settles two rows, amends, fills318more, reopens at320, verifies old rows/grant unchanged,
and refuses one more call. It also tests stale/missing pins and outstanding reservations.
This is not an exhaustive security audit or a test of actual cloud billing.

An interview exercise: explain why296trials on twelve families cannot replace296trials
on148families, then trace a stale client's attempted reservation after amendment. A strong
answer distinguishes repeated reliability observations from independent group counts and
shows that refusal occurs before provider dispatch. See [Build Book Entry65](../BUILD_BOOK.md#entry-65--size-and-freeze-a-confidence-target-study).

## Actual completed study and decision

All **296 of 296 attempts** completed. The confidence target was **not met**.
The fixed candidate, original references and complete scheduled denominators are preserved.
See the [publication-safe result](data/confidence-target-study-v1.json).

| Measurement | Actual result | Frozen target |
| --- | --- | --- |
| Scheduled validation accuracy | 237/288 (82.29%) | At least 95% |
| Decision coverage | 265/288 (92.01%) | 100% |
| False accepts | 16 | Zero observed |
| False rejects | 12 | At most 5% of answerable observations |
| Failed validation families | 30/144 | Upper bound at most 5% per class |
| Answerable family-error upper bound, exact supplementary 95% interval | 39.59% | At most 5% |
| No-answer family-error upper bound, exact supplementary 95% interval | 24.06% | At most 5% |

Calibration: 8/8 correct; validation failures include
23 invalid/failed observations, 0 abstentions and 0 missing.
Always-accept and always-reject analytical diagnostics each score 50%; these are not approved
business baselines. The primary frozen report remains unchanged. Supplementary exact bounds
confirm the failure; they do not replace the primary methodology or authorize promotion.

Even before citation checks, only 264 of 295 schema-valid model decisions match the publisher
reference. Fixing quotation handling alone therefore cannot reach 95% accuracy on this study.
The next candidate needs better answerability decisions as well as reliable citations.

The audit re-parses every saved response, verifies request/context/response pins against
durable reservations, and reproduces the primary report. It checks the original 24 rows,
original grant, old pilot responses/plan/report, exposure inventories, source databases and
recorded executable files remain unchanged. Source labels and original corpus holdout remain.

Known token usage: 1,535,206 input and 22,845
output. Unknown input/output usage occurs in 0 and
0 observations respectively. Raw monetary cost is
unknown for 296 observations; it is not recorded as zero.
The single amended ledger is **320/320 consumed,
0 remaining, 0 unsettled**. No retries or paid fallback.
The separate Groq invented-only ledger is unchanged.

### Prepared next development proposal; no dispatch

The [safe proposal](data/remediation-development-proposal-v1.json) selects 12 exposed
families, six per class, covering failures before controls and balancing error kinds and
categories. All 12 selected families had a failing observation.
It proposes Gemini 3.8 Flash, one unique verbatim quote of at most 300 characters, and 2,048
output tokens. Model-only inputs stay separate from expected publisher labels. The provider
lists this route on its [Free pricing table](https://ai.google.dev/gemini-api/docs/pricing);
account billing remains an operator attestation, not independently verified evidence.

Two trials would require **24 additional development attempts**, raising the same shared
total from 320 to 344. This is a proposal, **not authorization**: the current cap remains 320.
No additional attempt or new final holdout is consumed. All 24 development decisions and
citations would need to pass the declared readiness screen before preparing a fresh final
study; even that would not establish the confidence target. A tested current-pin amendment,
actual parser/operator implementation, frozen executable protocol and explicit new cap/scope
are required before any dispatch. Do not silently fund another full qualification run.

Private proposal and model-only inputs are at
`D:/document/.cache/production-agents/revenue/remediation-development-proposal-2026-10-27-v1`.
No source text or original case identifiers are published. Final exact-head CI and postmerge
acceptance are recorded on PR #118. No release gate or issue is closed by a failed study.
