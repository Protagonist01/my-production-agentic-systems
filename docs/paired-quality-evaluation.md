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
