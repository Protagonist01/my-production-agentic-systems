# Paired model-quality development evaluation

## Why the previous canary stopped

The OpenRouter plan froze a maximum12invented calls and stop-on-first-failure. First actual
request returned HTTP429,so it stopped after one. Twelve was a ceiling,not an instruction
to generate twelve failures. The key was recognized by a subsequent read-only metadata
request and the provider reported Free0used/50limit;this does not identify the429cause.
No retries,fallback or contract-data export occurred. The separate ledger remains1/12.
The stop rule is recorded in the original plan/report and [case study](revenue-failure-investigation.md).

## Approved comparison, frozen before new responses

The owner approves same shared Gemini lifetimecap418for74newattempts:two invented canaries,
then72domaincalls. Previous341reservations and all grants remain. Three oldunusedslots
stay bound and are not reused. New74unique slots can consume at most415total,leaving three
legacy slots inaccessible even though global maximum418. Never reset/create another pool.

The [safe proposal](data/paired-quality-proposal-v1.json) has12already-exposedCUADfamilies:
6repeated raw disagreements,2citation failures with reference-correct raw decisions and
4previouslycorrect controls. Six publisher-answerable and six no-answer;four each in
<=20k,20–35k,and35–50kcharacter bands;12distinctcategories. Selection deliberately uses old
outcomes and therefore cannot supply prospective reliability or confidence evidence.
Original publisher labels stay unchanged;reference-applicability doubts remain unadjudicated.

Compare baseline,task-wording-only and evidence-selection-only on Gemini3.5FlashLite,
temperature0,LOWthinking,512outputtokens. Two trials per case/variant. Rotatevariantorder
percase and reverse ontrial2to avoid always testing baseline first. There is no new-model
comparison yet:holding model/settings fixed isolates the two implementation changes.
Capture labels in evaluator-only storage;model receives context/question or full source
catalog,never labels,roles,splits or expected publisher spans. All36requests bind exact
reviewed factories and all72scheduled pairs are pinned before responses. Sourcecohort
membership and input/target equality are verified against the original frozen artifact.

Firstcanary is invented arithmetic. Secondcanary uses a50,000character invented source
catalog and actual evidence-selection schema,including167IDs. It checks interface/long-input
compatibility,not semantic accuracy. Both need correctstrict outputs and matching settled
receipts before the ledger permits any domain reservation. SDKpayload preflight checks
all38distinctrequests and one constructed actualSDKHTTPexchange before funding/capture.

No automatic retries or paidfallback. Parent attempt deadline55seconds,adapterHTTPceiling30;
keep both timings. Minimum6secondspacing. Stop firstcanaryfailure;duringdomain stop auth,
quota or budget denial,or three consecutive timeout/unavailable results. Preserve missing
scheduled rows and every failed response. Model/parser failures are not relabeled or replaced.

## Report and decision boundary

Report pervariant complete24scheduled denominator,missing/decided/correct,raw reference
agreement,source integrity,positive/negative class outcomes,false accepts/rejects,tokens,
latency and unknown raw costs. Pair by family:both trials must pass to count a consistently
correct family. Report gained/lost families and regressions on the four controls relative
to the freshly captured baseline. Missing pairs are unassessed,not wins or regressions.
Do not add overlapping raw-decision and evidence-validity metrics.

No automatic winner or relaxedthreshold after observing responses. A better development
result motivates a frozen candidate and separately scoped fresh study;it cannot meet the
original5%confidence target,adjudicate legal meaning or authorize release. Exact source
copying still does not prove relevance. Fixedchunk boundaries/threeIDs remain limitations.

## Implementation and verification before capture

`PairedExtension` references all three historical pins and requires341settledrows,74unique
request/trialslots,12x3x2balancedstructure and two fixedinventedrequests. Newclients need
paired_extension_sha256;oldclients refuse. A SQL insertion trigger blocks even older
executables that ignore the extension unless the new request/context ticket has a matching
pairedslot. Immutable grant/slot/pass tables and atomic transactions prevent refund,
duplicate or foreignscope consumption. Both canary passes require correct actual response
pins already settled in attempts. Old341rows/grants/development slots remain identical.

[Capture operator](../scripts/run_paired_quality.py) requires clean committed source and
free-configuration credential association,performs actual SDKpreflight,freezes request,
context,source and priorartifact inventories,creates recovery-only backup,and appends in
place. No reset/resume command. A crash leaves reserved slots consumed. Do not rerun a
stopped completedcapture or use recovery snapshots as dispatch allowances.

Invented tests exercise complete74slotboundaries,stale pins,oldbinaryguard,missing/failed
canary barriers,duplicates,wrongscope,immutable history,hand-counted paired outcomes and
fixed missing denominators. All38actualrequests preflight and actual SDKconstructedwire
pass with zero provider calls/ledger mutations. Whole-repo types check200sources. Capture
and exact final CI evidence follow;no actual model-quality result is claimed here yet.

Private proposal/capture roots live outside Git under the Revenue paired-quality directories.
Raw inputs,source IDs,labels,credentials and provider bodies stay private. Summary results
will be published after independent response/ledger/source-pin audit. See
[Build Book Entry68](../BUILD_BOOK.md#entry-68--isolate-development-changes-behind-settled-canaries).


## First availability result and approved continuation

The initial30secondHTTPcanary timed out after41.07seconds including7.86secondworkerstartup.
Workerreturnednormally;55secondparentdeadlinewasnotexhausted. No domainrequest occurred.
All341priorrows/grants/slots and379oldartifactfilesverifiedunchanged;ledger342/418,76remaining,
0unsettled. DNS,publicHTTPS andauthenticatedmodelmetadata succeed;generationpath timeout
cause unresolved. The report remains immutable and cannotbeusedasmodel-qualityevidence.

The owner explicitly approved a separate continuation:only originalunusedrepresentative
canary,90secondHTTP/110secondparent,thenoriginal72domaincalls onlyifitpasses. No firstprobe
retry,paidfallback,qualitycriterionchange or capincrease. Allmodelrequests/settings/trials
remainexact;contextsusefrozennewoperatorrevision/time/deadline. ImmutableAvailabilityOverride
bindsfailedresponse/report,pairedextensionandrepresentativehash;currentclientsneedsixthpin.
Domainreservations requireexactsettledrepresentativepass. Historicaltwo-passgate/failed
capturepreserved;this is a disclosed owner-approved operationalprotocoldeviation,not a
retrospectivepassingqualityresult. LegacyHTTP30andgeneralExecutionPolicy60remainunchanged;
explicitPairedWorker90andPairedExecutionPolicy110areonlyusedhere. The longerHTTPwindow
holdsrequesttimeoutfixedacrossall72qualityvariants.

[Continuation operator](../scripts/continue_paired_quality.py) verifiesoriginalschedule,
source/modelinputpins,oldfailedcanaryandcleancommittedcode,then freezesaseparatesource/plan
inventoryanduntouched73slot schedule. Failedorunsettledrepresentativecannotunlockdomain.
No automaticresumeorretrycommand. The existingOpenRoutercanaryremains1/12inventedonly.


### Continuation construction failure retained

The first continuation operator constructed a specialized110secondpolicy,then shared
BoundedGatewayrevalidationrefuseditagainstthelegacy60secondcontract. No newreservation or
request occurred;ledger342/418with0unsettled. The v1plan/sourceinventory and emptyrowsfolder
remain. A corrected v2operator uses the same approvedoverrideanduntouchedslots after
explicitlycheckingnoadditionaldispatch. It doesnotretryaconsumedrequestorappendnewbudget.
The explicitversionedpolicy nowroundtrips throughgatewayadmissionandstoredControlledCall;
legacyExecutionPolicystillrefuses110. Actualfakegatewayexecutionispartofpreflightregression.


## Corrected continuation actually underway

Corrected source83ed244 freezes the v2operator;all73untouchedrequests preflight,including
actualSDK90secondtimeout and gatewaypolicyvalidation. Representativecanarypasses38.83s,
exactstrictdecision/IDandsettledreceipt;thisunlocks the original72domainrequests. First
30secondprobe remainsfailedandthev1localpolicyfailureconsumesnothing. Domaincaptureuses
90HTTP/110parentconsistentlyacrossallvariants. This shows the path works underthiswindow;
it doesnotproveallgenerationfailureswerecausedsolelybytheoldtimeoutorprovideravailability.

Initialfullgatewayregression usedoldinventedclock andreturneddeadlineexhausted;fixclockto
currentUTCandretaintestpurpose. Actualfakeattempt nowchecks60<remaining<=110,andstoredcall
roundtrips110/maxattempts1. LegacyExecutionPolicy110stillrefuses. All201sources typecheck;
initialhostedUbuntu logs1377tests perPython3.12/3.13,128SQLpass;finalheadresultsfollow.
Theobsolete localfullrunstartedbeforecorrectionisexplicitlystopped,notreportedpassing.
Use exactfinalhostedmatrixforfull-suiteacceptance. Installed84harness/38Revenue resources
matchwheels,12oldermodelrequests/12OpenRouterpayloads revalidatewithoutnetwork orprovider
SDKs;strictinventedreplay6calls/2timeouts/0provider. Thesearesoftwarechecks,notscores.


## Completed result: neither variant is ready for promotion

All 72 domain calls completed: 24 per variant, with no missing rows, abstentions, transport
failures or evidence-format refusals. Both trials and all 12 families remain in the
fixed denominators. The [safe result](data/paired-quality-result-v1.json) was independently
recomputed from saved responses and checked against ledger receipts, slot bindings and
historical code. This is an exposed, outcome-selected development comparison. Its scores
cannot be compared directly to the original 82.29% result from a different population.

| Measurement | Freshly captured baseline | Task wording only | Evidence selection only |
| --- | ---: | ---: | ---: |
| Reference-correct responses | 13/24 (54.17%) | 12/24 (50.00%) | 15/24 (62.50%) |
| Answerable correct | 8/12 | 8/12 | 8/12 |
| No-answer correct | 5/12 | 4/12 | 7/12 |
| False accepts | 7 | 8 | 5 |
| False rejects | 4 | 4 | 4 |
| Valid response/evidence interface | 24/24 | 24/24 | 24/24 |
| Consistently correct families (both trials) | 6/12 | 6/12 | 7/12 |
| Consistently correct preselected controls | 4/4 | 4/4 | 4/4 |
| Paired families gained versus baseline | — | 1 | 2 |
| Paired families lost versus baseline | — | 1 | 1 |
| Net consistently correct families | — | 0 | +1 |
| Known input tokens | 142,570 | 144,202 | 200,846 |
| Known output tokens | 2,153 | 1,355 | 586 |
| Sum of call elapsed seconds | 395.94 | 370.32 | 419.19 |
| Unknown monetary-cost rows | 24 | 24 | 24 |

Source selection uses **40.88% more input tokens** than baseline because the catalog adds
IDs and schema/input overhead. Lower output-token use does not prove lower monetary cost:
raw cost remains unknown, and account billing is not independently verified. Elapsed times
include local process phases; they are descriptive, not throughput or service guarantees.

Token usage is known for all 73 continuation calls, including the representative canary:
500,686 input and 4,109 output tokens. The first timeout adds one call with unknown token
usage and cost. All 74 new reservations are consumed, without retry or paid fallback.
The shared ledger is **415/418 consumed, three legacy slots remaining, zero unsettled**.
Those three slots are still bound to the old scope, not another experiment allowance.
Groq remains 9/12 and OpenRouter 1/12, with zero unsettled each. No contract was sent to
OpenRouter.

### What improved, regressed and stayed unresolved

Task clarification produces no net gain in consistently correct families. It fixes the
first-option/right-of-first-refusal family in both trials, but loses the Covenant Not To
Sue family that baseline gets right twice. It also changes a mixed baseline Cap On
Liability family into two disagreements. False accepts rise from seven to eight. This
rejects the hypothesis that the tested wording addition is sufficient. It does not prove
that no better instruction could help. Do not deploy it because it merely sounds clearer.

Source selection gains the first-option and Cap On Liability families, but also loses
Covenant Not To Sue. Its net gain is only one of 12 families. Exclusivity remains mixed;
Volume Restriction, Third Party Beneficiary and Non-Transferable License still disagree
with the reference in both trials. This small result supports investigation, not promotion.
Changing the evidence interface can itself change decisions; it is not a neutral format fix.

Both new variants preserve the four preselected controls, but regressions also occur
outside that subset. Report every paired regression, not only control regressions. A
candidate can preserve all named controls and still damage other previously working cases.

All 24 baseline citations pass in this capture, including the two families selected for
older citation failures. We therefore cannot claim that source selection reduced observed
citation failures in this comparison. Exact local copying remains an implementation
integrity guarantee; a quality gain from that guarantee was not demonstrated here.

Each variant has eight reference-positive accepts, and all eight overlap a published span.
That location check is diagnostic. Overlap does not independently establish semantic
relevance or legal meaning. Wrong positive decisions remain wrong despite exact citations.
No disputed reference is relabeled or silently excluded.

### Narrowed next engineering direction

**Promote neither variant and do not launch another large confidence run.** The remaining
problem in this comparison is reference-relative interpretation under the current
model/task pairing, rather than failed JSON or copied-source integrity. Keep baseline and
all historical failed studies intact.

The next useful comparison would hold the original baseline prompt and evidence interface
fixed and change only the model, using these exposed families and regression controls.
It needs a separate concrete model scope and budget; the three legacy slots cannot fund it.
Separately investigate the applicability of suspicious publisher categories without treating
new AI explanations as adjudicated labels. A stronger model could share the same ambiguity;
model agreement would not settle the reference question.

If development identifies a useful candidate, freeze it and an appropriate fresh cohort
and protocol before testing confidence again. These results authorize neither another
provider dispatch nor production release.

## Independent audit and verification record

The audit reparses all 73 continuation rows (one representative canary plus 72 domain
responses), reproduces the outcomes and complete report, and matches every context,
request and response hash to its reservation and unique slot. It verifies that original
requests and trials are unchanged and that exactly one approved representative pass exists.

It checks the original 341 rows, grants and old development slots; the first 342 rows
including the failed canary; and all recorded prior artifact hashes. Historical executable
inventories match their frozen Git commits, with explicit LF/CRLF handling. The first audit
lookup used Windows backslashes in a Git path and refused before publishing any result.
Correcting path syntax made the audit pass; no source bytes or results were changed.

The first continuation remains an empty-row local failure. The corrected continuation uses
separately frozen commit `83ed244`. The original confidence study remains failed, and this
small comparison is never scored as qualification. Initial hosted checks pass 1,377 tests
in each Ubuntu/Windows Python 3.12/3.13 environment, with 201 typed source files, 12 build
artifacts and 128 SQL tests. Installed checks confirm 84 harness and 38 Revenue resources
match the wheels; projections run with networking denied and strict replay uses six
recordings, reproduces two timeouts and makes zero provider calls.

Final documentation-head checks and post-merge verification are recorded on
[PR #121](https://github.com/Protagonist01/my-production-agentic-systems/pull/121).

## Engineering discussion: the hypothesis failed usefully

A truthful account for an employer or business discussion:

> We suspected wording ambiguity and quote rewriting. We isolated those changes on the
> same model, captured a contemporary paired baseline, and included previously correct
> controls. The wording change did not improve family accuracy. Source selection helped
> two cases, hurt one, and added about 41% input tokens. Because baseline citations all
> passed in this capture, we could not claim an evidence-format improvement. We kept both
> changes out of release and narrowed the next test to model capability, with prompt and
> interface held fixed.

That is evidence of how an attractive hypothesis was tested and rejected without weakening
criteria or erasing failures. The timeout repair is an operational improvement for this
run; it does not turn a 62.5% score on selected exposed cases into production reliability.
See the broader [engineering case study](revenue-failure-investigation.md) for business,
onboarding and interview questions.
