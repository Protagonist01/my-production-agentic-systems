# Revenue evaluation v2: implementation and evidence boundaries

Prepared 2026-11-11 from main `fd4ef0c` for the owner's five Revenue recommendations,
in support of #45. The opt-in implementation changes no frozen harness/domain package,
SQL schema, historical capture, provider allowance or production route. Root adapters
must be composed explicitly. The default console continues to use its existing controls.

## 1. Check relevance before interpreting billing terms

`revenue_assessment.preflight` revalidates the server request, document binding, input
and read grant. Invoice and account access are checked before a classifier can see text.
The binding pins exact UTF-8 document bytes and declares tenant, account, product, effective
interval and current-version status. A registry assertion is trusted composition input;
the class does not authenticate a document issuer, signature or amendment precedence.
Do not populate these fields from model guesses or browser-supplied account names.

| Situation | Result | Model receives document? |
|---|---|---|
| Missing read permission, wrong tenant/account, changed document bytes | Deny | No |
| Unknown binding/version, wrong product or effective period | Review | No |
| Unrelated request | Outside scope | Only after authorized scope screening |
| Other agreement, missing pricing schedule or terms | Request information | Only authorized input |
| Conflicting terms or uncertain meaning | Review | Only authorized input |
| Applicable complete terms | Read-only analysis | Yes, with a caller-supplied gateway |

`screen_without_document` handles a supplied request classification when no agreement
exists. It authenticates the read grant first and requests a document rather than
inventing an amount. The classification is an injected judgment, not a default
natural-language classifier. `ScopeAssessment` requires named missing fields.

`assess` supplies only context and question to a distinct closed-schema prompt. It
replaces inherited messages/tools, bounds input/output and makes one gateway call. It
checks response identity, duplicate keys, exact extraction spans and term citations.
Timeout, invalid identity, provider failure and invalid response remain separate outcomes.
No proposal, approval or apply function is called. A gateway supplied by a future caller
must itself enforce the separately authorized scope, durable attempt budget and deadline;
this helper grants no network/export permission and its CLI has no provider command.

## 2. Test adversarial interpretation separately from effects

The authored `revenue_diagnostics.fixtures` cover unrelated requests, an employee agreement,
missing/conflicting prices, an obsolete version, cross-account/tenant documents, wrong
product, future terms, unknown binding, unit differences, an exception and unresolved
amendment precedence. The clean/injection pair shares its parent, family, template and
partition. These are exposed development proposals, not accepted independent references.

The gateway tests also construct a particularly important failure: quote the real `1000`
but assert `9000`. Literal citation checks pass. Meaning remains unqualified and the
result grants no billing authority. A valid quote is necessary but insufficient evidence.
Conversely, a fabricated quote fails before any result can be accepted as analysis.

The adversarial scorecard separates scheduled reference failures, clean-pass/attack-fail
pairs, invalid proposals and unauthorized effects. Missing attack results fail scheduled
completion; they do not establish an observed successful attack. Effect fields remain
unknown unless supplied by a separately bound state observation.

The real SQL integration test uses `ProfiledOperations` and `ProfiledConnection` to
exercise approved correction, denied self-review, duplicate delivery, commit and rollback.
Existing `test_revenue_operations.py`, `test_revenue_console_state.py` and
`test_revenue_bound_effects.py` retain tampered-action, cross-tenant, replay and independently
observed compensation controls. An interpretation benchmark is not a substitute for them.

## 3. Establish what evidence can actually prove

`Meaning` requires all eight fields exactly once: unit price in minor units, currency/unit,
quantity, billing period, start, end, conditions and exceptions. Each is supported, missing,
conflicting or contradicted. Supported values require typed values and exact pinned quotes;
unresolved values cannot masquerade as zero. A complete analysis cannot contain unresolved
fields. All outputs retain `reference_or_qualified_evaluator_required` and false write/release
authority. The schema does not prove that a condition is satisfied or a quote entails a value.

`revenue_billing_paths.compare_constructed` compares the existing reconciler on separately
supplied correct terms with the same reconciler on extracted terms. The fixture test
demonstrates 3,000 versus 27,000 after the 1,000-to-9,000 interpretation error, without an
invoice mutation. Projection is deliberately limited to the explicitly constructed SIM
monthly vocabulary. It refuses unrepresented amendments, credits, uplift, conditions,
exceptions and units rather than quietly dropping them. This does not interpret arbitrary
contracts or convert USD into SIM.

### ContractNLI source audit

The [publisher specification](https://stanfordnlp.github.io/contract-nli/) and
[original paper](https://aclanthology.org/2021.findings-emnlp.164/) describe three-way
entailment/contradiction/not-mentioned classification and evidence selection on NDAs.
There are 17 fixed hypotheses across 607 agreements, not SaaS price or invoice gold labels.
The publisher releases the dataset under CC BY 4.0 and asks for attribution to Yuta Koreeda
and Christopher D. Manning, Findings of EMNLP 2021, pages 1907–1919.

The actual audit pins official revision `eced6528dd3c1d14d73f9a87df8f7bdbc03126f9`, verifies
Git object identities for both archive and license, then hashes exact archive/license/member
bytes. It reads only `contract-nli/train.json`: 423 documents, 7,191 native references
(3,530 entailment, 841 contradiction, 2,820 not-mentioned), 8,341 evidence intervals.
The archive contains other split bytes, but no development/test record was decoded or selected.
See [aggregate audit](data/revenue-contractnli-training-audit-v1.json). Raw archive and notices
remain private in the audit directory; no source contract text is committed or sent to models.

`revenue_contractnli.parse_training` preserves publisher document identity, source split,
hypothesis identity, source-member pin and every native evidence offset. Public input contains
only case identity, document and hypothesis. Duplicate JSON keys, nonfinite constants,
duplicate documents, malformed intervals/indices, missing annotations and neutral-with-evidence
are refused without repair. `native_score` reports scheduled three-class confusion/F1 and
exact complete evidence. NotMentioned is not converted into a billing rejection label.
Fixed hypotheses and public training text supply no unseen-question/pretraining-independence
claim. Declared family independence remains unauthenticated.

`revenue_protocol.evaluator_diagnostics` reuses the shared `qualification_report`: pre-output
pins/time order, both acceptance classes, group/slice coverage, missing trials, abstentions,
false accepts/rejects, critical rejection and group uncertainty. Even a perfect invented
mechanism result activates no judge. ContractNLI can support a native-task component test;
using it for billing meaning requires a separate applicability and qualification decision.

## 4. Find time spent without collecting contract or credential text

`revenue_profiling.Recorder` records fixed-name monotonic intervals, parent sequence,
exception outcome, observer process ID, current-process CPU time and optional byte count.
It rejects arbitrary stage names. Bounded capacity, active spans and regressing clocks
make incomplete snapshots explicit. Context variables keep concurrent requests separate.
Neither SQL, credentials, document text, route identifiers nor exception messages are stored.

`AttemptTransport` imports only observed isolated-worker startup, generation, serialization
and cleanup milestones and refuses to reimport a stale attempt. The generation interval
includes SDK work; it is not provider-internal time. Child PID/CPU, provider queueing and
memory remain unknown. A real invented worker-process test verifies all four milestones
and cleanup with zero provider calls.

`revenue_profiled_runtime.application` wraps the existing authenticated console. HTTP and
response send, authentication/login, retrieval, proposal/review/apply, SQL connection,
execute/fetch, commit/rollback and transaction finalization are measurable with matching
adapters. `compare_constructed` adds a reconciliation interval. Workbench time includes
retrieval and arithmetic; it is not isolated reconciliation time. Queue wait, document
loading, journal persistence, telemetry export and human approval wait have explicit stage
names for the owning orchestrator to instrument. Naming a stage does not instrument a
process. `all_subprocesses_instrumented` remains false. Human waiting must be measured as
its own observed interval and never included in a claim of model/API latency.

Use stage p50/p95 to identify a bottleneck on an actual representative run. Inclusive,
nested and parallel spans overlap and must not be summed into a total. These diagnostics
do not establish an API SLO, production overhead, memory profile or hosted availability.

## 5. Score the full schedule, then freeze a prospective comparison

`revenue_evaluation.Plan` binds source/parent/template/normalized-document connected groups
before checking partitions. The full graph is reused for slices; removing a bridge record
cannot invent independence. Separate candidate configuration and input pins reject duplicate,
extra or mismatched observations. Repetitions remain distinct from independent group count.

| Metric | Meaning and denominator |
|---|---|
| Disposition precision / recall | Correct predictions / predictions; correct predictions / scheduled reference class |
| Reference-relative completion | Correct scheduled slots / all case × trial slots; missing/failed slots receive no success credit |
| Joint/exception agreement | Exact typed state/value agreement on separately supplied references; equivalent quote positions need not match |
| Unsupported claims | Independently rejected supported claims / supported claims; unjudged claims stay unknown |
| Evidence completeness | Supplied complete-evidence judgments / scheduled slots; missing judgment is unknown |
| Eligible coverage / unnecessary review | Analyzed eligible slots / eligible slots; observed review on eligible slots |
| False admission / named clarification | Ineligible slots admitted; correct request-information action and exact missing-field set |
| Discrepancy precision / recall | True discrepancy flags / all flags; detected discrepancies / reference discrepancies |
| Amount-weighted recall | Absolute reference amount detected / absolute reference amount; exact-amount version also requires correct delta |
| Workflow/effects | Correct reference result plus supplied whole-workflow judgment; proposal/effect observations retain unknowns |
| Usage, cost and time | Known rows and full denominators; incomplete total cost/latency stays unknown |

Flags without a billing reference remain in precision as unknowns. Missing cost never
becomes free execution; mixed currencies are not added. Cost per reference-correct result
requires complete same-currency cost. Confidence-threshold coverage/error curves retain the
full scheduled coverage denominator and identify missing confidence; they do not qualify
confidence calibration. Partition, source-kind, risk-slice and fixed input-length tables
are separate. Conditional group error bounds are not evidence that declared families are
independent. Zero observed critical effects cannot excuse missing effect evidence.

`Criteria` and `Study` bind a proposed plan, explicit quality/coverage/error/group/latency
limits, rationale, required slices and pre-output time order. No thresholds are silently
accepted or copied from Olist. Unknown effects and critical reference failures block the
diagnostic criteria. These trusted timestamps/labels are declarations, not authenticated
review receipts. Criteria and qualification acceptance remain false; this helper cannot
activate a release profile. Fresh studies still require the existing bound H10 methodology,
source applicability, independent references, approved limits and current provider scope.

### Actual no-provider baseline capture

The new private capture is at
`D:/document/.cache/production-agents/revenue/evaluation-v2-diagnostics-2026-11-11-v1`.
Its externally retained manifest pin is
`ae2de78333db107c2246e1e7be819468f2ddc6fb418a5c73bf9c127d5424926c`.
A separate process verified that pin, file inventory, input projections, source/configuration
pins and recomputed scorecard. [Public aggregate](data/revenue-diagnostics-v2-summary.json)
contains no source narratives or raw provider response.

There are 16 authored cases × 3 trials × 3 scheduled comparators. Actual rules outputs:
48/48, with 45 scope-reference agreements. Actual always-review outputs: 48/48, with 21
agreements. The rule baseline loses the clean/injection pair three times by reviewing the
attack. All cases share a declared constructed template/family: this is one group, not
48 independent successes. The candidate has 48 missing slots and no observed quality result.
The zero completed-correct candidate slots are not measured 0% model accuracy.

This scope draft has no accepted joint-meaning or billing-delta references. Those metrics
remain unscored; all effect/workflow/cost evidence remains unknown. There were zero provider
attempts and zero database actions in this capture. Existing historical failures and stopped
shared allowance remain unchanged. No recovered-revenue or release claim follows.

### Reproduce and inspect

After the locked setup, use a new private output directory outside project checkouts:

```powershell
uv run --locked --all-packages python revenue_diagnostics.py capture --output <new-private-directory>
uv run --locked --all-packages python revenue_diagnostics.py readback --output <same-directory> --manifest-sha256 <separately-retained-pin>
python dev.py check
python dev.py db-check
```

Capture refuses existing directories and retains partial attempts. Readback is integrity
and recomputation, not an independent endorsement of authored labels. Tests cover access,
schema/citation attacks, valid-quote/wrong-meaning, complete denominators, transitive split
leakage, unknown costs/effects, stale milestones, clock/capacity failures, thread isolation,
real invented subprocesses, source corruption and actual SQL semantics in hosted acceptance.

For an engineering discussion, trace `assess → preflight → gateway → verify_extraction →
Meaning.verify`; then deliberately change a valid cited price's value. Explain why the quote
still verifies and why no writer is reachable. Next trace `scorecard → components → _scope`
and remove two trials: explain why successful-case-only accuracy would mislead. Finally
compare NDA inference evidence with billing arithmetic: passing one task cannot qualify the
other. The remaining work is applicable independent billing-language references, a frozen
authorized fresh comparison, qualified evaluator/reference evidence and final operational
release evidence—not relabeling these development diagnostics as a passed gate.
