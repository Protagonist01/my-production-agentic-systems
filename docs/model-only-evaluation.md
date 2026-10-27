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


## Actual result: stopped before quality evaluation

The frozen capture at commit `f084783` attempted both representative canaries and stopped
when the challenger timed out. **No contract call occurred.** There is no model-quality
comparison, winner, or evidence that either model is more accurate from this run.

| Observation | Result |
| --- | --- |
| Flash-Lite representative canary | Passed in6.67seconds |
| Gemini3.8Flash representative canary | HTTP timeout;94.36seconds total |
| Parent110second deadline exhausted | No;worker returned a settled timeout |
| Domain calls observed/scheduled | 0/48 |
| New reserved attempts | 2/50 |
| Shared lifetime ledger | 417/468consumed;51remaining;0unsettled |
| New canary passes | 1;both were required |

The challenger worker entered after2.87seconds and returned after93.97seconds;the parent
completed cleanup within94.28seconds. This is consistent with the90second HTTP window
being reached during generation. It is not a parent-process crash or a local preflight
rejection. We do not know whether upstream congestion,internal processing or another
provider-side factor caused the timeout. Do not claim a confirmed outage or that simply
allowing more time will guarantee success.

A subsequent read-only authenticated metadata request returned HTTP200in1.80seconds,
recognized `models/gemini-3.8-flash`,and listed generateContent support. That establishes
metadata reachability and recognized access to the model descriptor,not usable generation
capacity,quota or independently verified billing. The metadata request was not inference
and consumed no local generation attempt.

Known usage from the successful canary is13,068input and15output tokens. Input/output usage
for the timeout is unknown;raw monetary cost is unknown for both calls. Unknown is not zero.
The [safe result](data/model-only-result-v1.json) retains the complete48scheduled denominator
with48missing observations and0observed model outcomes. Its zero reference-correct count
is **not a measured0%accuracy**;no contract response exists to score. Both class and family
comparisons are unassessed. A report may be structurally complete while its evidence is
insufficient to answer the experiment's question.

## Audit, preservation and decision

Independent read-back reparses the two responses,matches their exact context/request/
response pins to two settled reservations and model slots,and verifies the sole successful
canary receipt. It checks all24domain request pairs differ only in model,all50frozen slots,
original case/target equality,all415prior attempts/grants,and all prior paired slot rows.
Every recorded prior artifact hash and historical executable inventory matches. Both old
SQL guards remain;the new guard rejects unaware executables after serial415. No baseline
or publisher label was rewritten,no contract was exported,and no previous failure removed.

Do not retry either consumed canary,skip the two-pass gate,substitute a model/provider or
spend the remaining51slots as a general pool. Of those slots,three remain bound to the old
scope and48belong to the stopped,unchanged model-only schedule. Proceeding with another
route requires a concrete approved revision;it cannot be inferred from unused capacity.
The earlier72call paired result remains baseline13/24,wording12/24,selection15/24,with neither
variant promoted. The original large confidence study remains failed. Release gates stay.

The immediate engineering decision is to stop this route-dependent capture,retain the
prepared comparison and seek a usable authorized challenger. Another Free provider or model
might be useful,but a connectivity success is not quality evidence,and switching provider
also changes delivery behavior. A follow-up needs explicit model/data scope,request and
budget binding,representative availability checks and a contemporary baseline. No further
inference dispatch is authorized by this stopped result.

## Engineering discussion: readiness gates can save the study budget

A truthful explanation for an employer or business discussion:

> We prepared a model-only comparison with an unchanged baseline and strict request pins.
> Before sending contract data,we checked both routes with representative invented inputs.
> The control route worked;the challenger timed out even with the approved longer window.
> We stopped before48planned contract calls,kept the timeout and unknown usage in the ledger,
> and reported that model accuracy had not been measured. We did not convert a provider
> availability problem into a model-quality claim or spend unused slots on unapproved
> retries. The next step is an explicitly scoped usable challenger,not another accuracy
> percentage derived from missing responses.

This also corrects a common misunderstanding:an attempt cap is an upper bound,not a target
to exhaust. A failed gate can make stopping the correct delivery outcome. Software tests
prove the gate and accounting work;they cannot make an unavailable remote model answer.
Final software checks and post-merge evidence are recorded on
[PR122](https://github.com/Protagonist01/my-production-agentic-systems/pull/122).
