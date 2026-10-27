# Model-only quality comparison

## Question and approved scope

Does changing only the model improve reference-relative answerability on the exposed
failure and control cases? The previous paired study found baseline13/24, wording12/24
and source selection15/24. Neither change was promoted. A contemporary baseline is needed:
provider behavior, timing and availability can differ from an older capture.

The owner explicitly approved increasing the SAME shared Gemini lifetime maximum from
418 to468 for50newattempts:one representative invented canary per model,then48quality
calls only if both canaries pass. Preserve415prior reservations and all grants. The three
legacy unused slots remain bound and cannot be reassigned. Fifty unique slots mean at most
465consumed if the run completes,even though the global maximum is468. No reset,newpool,
automaticretry,paidfallback,source relabeling,newholdout or release approval.

[Prepared proposal](data/model-only-proposal-v1.json):the same12already-exposedCUADfamilies,
six publisher-answerable and six no-answer,with six repeated disagreements,two historical
citation failures and four previously correct controls. Four cases per context-length band,
12categories. Original context,question,labels and family membership stay unchanged.

Compare Gemini3.5FlashLite against Gemini3.8Flash,two trials per case and model. Alternate
model order by case/trial. Keep the original baseline prompt,decision/quotes schema,
temperature0,LOW setting and512output-token cap. Only the model field differs. Do not use
the earlier3.8development prompt,short-quote rule or2048output budget. Identical named
settings do not imply identical internal reasoning across architectures. If512tokens prove
insufficient,the result is a failure in this experiment,not permission to retry or enlarge
it after observing outcomes.

The [Google model page](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash) lists
structured outputs and LOW thinking;the [pricing table](https://ai.google.dev/gemini-api/docs/pricing)
lists Standard input/output as Free. These are public route capabilities,not independent
verification of this account's billing,quota or availability. Existing private Free-project
attestation and credential association remain. No OpenRouter or Groq domain export.

## Operational gate and evidence separation

Each route first receives the same wholly invented50,000character source catalog and
strict selection-ID schema. Both must return the exact expected structured output with a
matching settled receipt. Stop on the first canary failure;do not send contract text unless
both pass. During domain capture,stop on authorization,quota or budget denial,or three
consecutive timeout/unavailable failures. Retain missing scheduled rows and all failures.
The HTTP window is90seconds and the parent deadline110seconds for both routes;minimum
six-second spacing. Legacy adapter default30seconds and general policy60seconds stay.

ModelComparisonWorker explicitly enables Flash and the long window. The Flash long-window
path permits only this study's512/LOW/temperature0 settings;it does not authorize older
2048development requests. Preflight validates all26distinct actual requests through the
SDK,constructed wire exchanges for both routes,and full shared admission/record read-back.
This avoids the worker-flag/output-ceiling/policy-revalidation gaps found in earlier work.
No actual credentials or network are used in preflight.

The model receives only context/question or invented canary text. Expected publisher labels,
control roles,source spans and family/split information stay in evaluator-only storage.
Exact source quotations are mapped with the existing unique whitespace-alignment rule.
Changed characters,duplicate keys,wrong response route and overlapping quotations fail.
Citation validity still does not establish relevant legal support or billing truth.

## Durable allowance and old-client behavior

ModelExtension binds the five prior grant/policy pins,exact415settled history,468maximum,
run ID and50unique request/trial slots. Currentclients require model_extension_sha256
alongside all earlier pins in the same private external-pin file. Stale clients refuse.
Fresh initialization above180still refuses;there is no new allowance pool.

New domain contexts use model-only-trial-1/2 namespaces. The original baseline request bytes
already appeared under older trial-1/2 names;new authorized observations must have their own
identity instead of overwriting or reusing those receipts. Model slots and attempts insert
atomically. New append-only trace rows satisfy the existing paired SQL guard without
changing it. A second SQL guard requires a matching model slot forserial>415. No old
security trigger is removed. Prior paired slots remain present and immutable.

Canary pass rows require the exact route's invented request,correct strict output and an
already settled matching receipt in the new model slots. One successful model cannot
unlock the other. Wrong,failed,unsettled or foreign receipts cannot open the domain gate.
The fixed50slots and duplicate constraints keep the three legacy slots inaccessible.

## Metrics and decision boundary

Report24scheduled observations per model,including missing/failed outcomes. Separate raw
reference agreement,valid evidence,coverage,class results,false accepts/rejects,tokens,
latency and unknown cost. Pair by family:both trials must pass to count a consistently
correct family. Show gains,losses and regressions on the four controls against the freshly
captured baseline. Missing pairs are unassessed,not gains or regressions. There is no
phantom third variant from the previous experiment's report shape.

A higher selected-set score is development evidence only. This cohort was deliberately
selected using old outcomes,so it cannot establish prospective confidence,production
prevalence,legal validity or qualified human-equivalent review. Do not compare its score
directly to the original82.29%from a different population. The original confidence failure,
all earlier failed studies and reference applicability doubts remain. No automatic model
promotion or new provider spending follows from a result.

## Reproduction and checks before live capture

[Capture operator](../scripts/run_model_comparison.py) verifies clean committed source,
original case/label equality,each request against the model-only factory and all48scheduled
pairs. It then preflights actual SDK/gateway behavior,checks credential association and the
same415settled ledger,creates a recovery-only backup,freezes the exact source/request/context
inventory,and appends the extension in place. The private capture directory must not exist.
There is no resume/retry/reset command. Crashes keep reserved attempts consumed.

The development proposal/capture folders are private outside Git under the Revenue cache.
Safe aggregates will be published after independently recomputing outcomes and matching
all receipt/source pins. Do not rerun a completed operator or treat recovery backups as
allowances. Whole-repo types pass204sources and13focused model/report/availability tests
pass41.56seconds. Actual26request preflight,two fakeSDKHTTPexchanges and full shared gateway
roundtrip pass with zero provider calls and ledger changes. Live results and exact final
CI/postmerge evidence will be appended;none are claimed yet.

See [Build Book Entry69](../BUILD_BOOK.md#entry-69--change-only-the-model-and-capture-a-contemporary-control)
for construction choices and the [previous paired result](paired-quality-evaluation.md)
for the negative findings motivating this comparison.
