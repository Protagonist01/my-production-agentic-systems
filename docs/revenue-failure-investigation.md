# Revenue failure investigation and engineering decisions

## Scope and evidence boundary

Started 2026-10-27 from merged main `95e8a1d`. The owner requested implementation of the
diagnostic recommendations and an extensive record for future employer and business
discussions. This investigation uses the already exposed, completed CUAD study. It does
not replace publisher labels, qualify a legal interpretation, or consume a fresh holdout.

Work in progress: preserve measured results separately from proposed explanations and
untested changes. The original 296-attempt study and operationally failed development run
remain authoritative historical results. New implementation and checks are recorded below
as they happen.

## Initial findings before implementation

The original validation has 288 scheduled observations: 237 correct, 28 valid but wrong,
22 rejected by citation checks and one provider failure. Those are disjoint final outcomes.
Before citation checking, 31 raw decisions disagree with the reference: three of these also
have invalid evidence. Nineteen citation-invalid responses have a reference-correct raw
decision. These overlapping diagnostic counts must not be added to the final denominator.

Across 144 validation families, 142 have the same raw decision on both trials. Fifteen
families have wrong raw decisions on both trials. Twenty-one families fail both final
trials; nine fail one. Repeated calls are not independent families, and consistency is not
correctness. Temperature zero does not establish determinism.

Inspection reveals a concrete ambiguity in the task contract. The existing prompt asks
whether the document contains an explicit answer. The publisher reference instead records
the presence of passages annotated for a category. A denial of an exclusive arrangement
answers a natural-language exclusivity question, but is not necessarily a positive
exclusivity annotation. Similarly, an express denial of third-party beneficiary rights is
an answer, yet the publisher marks the category absent. This observation supports a task
alignment hypothesis; it does not prove how much of the error rate it causes.

Some publisher-positive passages are indirect, and some publisher-negative cases contain
apparently relevant language. Treat these as reference-applicability questions, not proof
that the source is wrong or permission to relabel. No post-hoc alternative label can rescue
the original benchmark result.

## Construction log

Implementation and actual verification will be appended here. No new model-quality result
is claimed at this point.

## What the numbers actually say

The [reproducible diagnostic aggregate](data/revenue-failure-diagnostics-v1.json) separates
outcome accounting from explanation. The [original study](confidence-target-study.md) is
still failed:237/288validation correct,30/144families failed. Its target was a marginal
95%confidence upper bound of5%family error per class, conditional on independent comparable
families. Two trials of one family test consistency; they do not supply two independent
families. At the minimum72families per class, even one failed family exceeds that bound.
We saw20failed answerable families and10failed no-answer families. More calls on the same
candidate would estimate its deficiencies more precisely, not turn them into a pass.

| Disjoint final outcome | Observations | Interpretation |
| --- | ---: | --- |
| Correct decision with valid evidence | 237 | Passed the declared reference-relative checks |
| Valid response, wrong reference-relative decision | 28 | Interpretation/reference disagreement |
| Citation-invalid response | 22 | Evidence interface failed; some decisions also disagree |
| Provider failure | 1 | Execution failure, retained in denominator |
| Total | 288 | Complete scheduled validation denominator |

Raw-decision diagnostic axes overlap:31disagree with references;three are also citation
invalid. Nineteen citation-invalid responses have a reference-correct raw decision. Even
perfectly repairing those19cannot reach95%on this study. Do not present citation fidelity
as the sole cause. Across all296observations,21citation refusals change non-whitespace
characters and one involves overlap/other mapping refusal. Whitespace-only normalization
already has a separately versioned safe alignment path. Removing punctuation/negation or
using fuzzy matching would weaken evidence rather than solve generation fidelity.

| Context length in characters | Scheduled | Correct | Wrong decision | Citation invalid | Provider failure |
| --- | ---: | ---: | ---: | ---: | ---: |
| Up to20,000 | 120 | 105 | 13 | 2 | 0 |
| 20,001–35,000 | 108 | 88 | 13 | 7 | 0 |
| 35,001–50,000 | 60 | 44 | 2 | 13 | 1 |

The longest band has14invalid/failed responses, but includes one provider failure; do not
call all14quotation errors. This is a small convenience sample with different categories
and class composition, so length is a diagnostic association, not an isolated cause.
Short inputs still produce13wrong decisions. A shorter cap cannot explain those away.

Of144validation pairs,142repeat the same raw decision. Fifteen pairs are wrong both times.
Twenty-one pairs fail both final trials and nine fail exactly one. This favors investigating
stable task/capability/reference mismatch before investing in retries or majority voting.
It does not prove the prompt is the only cause or that temperature zero is deterministic.

## Inspecting disagreements without manufacturing new truth

All16validation families with any raw reference disagreement have private technical notes,
preserved context/question, publisher target and pointers to original failed rows. Fifteen
have two wrong raw trials; one has one. Notes are explicitly AI-generated investigation
proposals, not human open coding, qualified legal judgments or independent adjudication.
They are not scored as fresh labels and are never projected into model inputs. Full source
text and original case IDs stay out of Git/publication.

The following examples are invented paraphrases of failure classes, not source quotations:

| Observed class | Invented example | Candidate explanation | What remains unresolved |
| --- | --- | --- | --- |
| Negative answer versus positive category | “Neither party receives exclusive rights.” Model accepts exclusivity | “Contains an answer” encourages a defensible negative answer, but category presence asks a different question | How the publisher applies the category across the whole corpus |
| Related clause substitution | Arbitration occurs in Cedar County; model calls that governing law | Location of proceedings is used as if it states applicable law | Whether other complete-context language establishes law |
| Scope substitution | Assignment of the agreement is restricted; question asks about transferring a granted license | Broad transfer language is substituted for a license-specific clause | Presence/scope of the underlying license |
| Equivalent wording missed | A seller has the first option to repurchase inventory | Functional first-option wording may be missed without exact category words | Complete-context applicability; no automatic relabeling |
| Relative term missed | Agreement ends on its fifth anniversary or an earlier ownership event | Calendar-date wording is interpreted too narrowly | Reference applicability and exact initial-term interpretation |
| Reference applicability unresolved | Publisher-negative item contains a conditional minimum service guarantee | Annotation convention, scope conditions or model interpretation could differ | No independent adjudication establishes which explanation is correct |

Several positive reference passages are indirect relative to the question; several negative
items contain apparently relevant language. Therefore “31raw model errors” is too strong:
“31raw disagreements with the published reference” is supported. Keep the benchmark result
as failed while investigating whether the reference measures the business claim we need.
Do not tune rules to memorize the sixteen exposed cases or delete difficult cases.

## Separate development changes and their limits

### A. Task wording only

`interpretation_request` retains the original Gemini3.5FlashLite route, temperature0,
LOWthinking,512output-token cap, full context/question and decision/quotes schema. It
appends an instruction to assess presence of the requested category, rather than mere
topic discussion or a negative answer. It also says a restriction can itself be the
requested category and warns against substituting a related clause type.

This is a general task clarification motivated by observed confusion. It has no reference
answers or source-specific examples. It is an untested hypothesis, not a demonstrated fix.
Some categories intentionally concern absence/restrictions; the clarification could harm
those. Measure regressions on previously correct exposed controls before fresh validation.

### B. Evidence selection only

`selection_request` retains the old task meaning/model/settings but replaces generated
quotations with selection of IDs from a catalog covering every source character. The
catalog uses contiguous, non-overlapping300character slices, including all whitespace and
Unicode. The model selects at most three IDs. `copy_selection` recomputes the expected
request from the exact input, rejects any changed request, validates response route/JSON,
refuses foreign or duplicate IDs and inconsistent decisions, then copies text locally.

This removes the model's need to reproduce characters perfectly. It does not make irrelevant
passages relevant. The regression deliberately accepts the integrity of a passage denying
a right even when an invented model incorrectly selects it as positive support. The result
therefore carries `semantic_support=not_assessed` and `release_allowed=false`.

Tradeoffs: fixed boundaries can split clauses;three spans may be insufficient; catalog
serialization increases input size; selected spans may include unrelated text. This is
not a retrieval system, not an extraction-recall claim and not an automatic repair of the
old responses. Offsets are Python Unicode character positions, not UTF-8 byte offsets.
Two equal-looking spans have different IDs/positions; ambiguity is resolved by explicit
location, not by silently choosing a string occurrence. Existing runtime/parsers unchanged.

### Controlled experiment direction, not funded dispatch

1. Verify the selected actual provider/worker returns a usable constructed and live canary.
2. Freeze a development set containing repeated disagreements, citation failures and
   previously correct controls, balanced across answerability, category and length. All
   old study families are exposed. Preserve labels and explicitly mark applicability doubts.
3. Compare baseline against task-wording-only and evidence-interface-only variants on the
   same model/settings/inputs. Report decision agreement, evidence validity, coverage,
   tokens, latency, failures and unknown costs separately. Keep paired family denominators.
4. Only after these comparisons, test a model change with prompt/interface held fixed.
   Combining all changes first cannot establish which helped or harmed.
5. Freeze a candidate and new qualification protocol only after useful development evidence.
   Do not reuse the failed148families as fresh. The earlier corpus feasibility audit found
   only68unexposed families at the50kcap across remaining development and original holdout;
   new data/length/holdout policy and provider scope require explicit approval.

No new domain experiment or allowance is implied here. The remaining three Gemini slots
belong to the completed development scope; they are not a generic experiment fund. An
OpenRouter invented-only allowance does not authorize exporting CUAD/source material.

## Operational failure: what was ours and what was remote

The [later development run](remediation-development.md) produced no usable decisions.
Eighteen attempts were reserved and settled locally because I omitted the explicit Flash
worker flag. Offline payload preflight then found a second independent mismatch: the
legacy512output limit rejected the proposed2048budget. Admission checks alone had passed;
they did not exercise the selected worker's real payload construction. These were our
operator errors, not provider failures. All18remain consumed; no refunds or retries.

The correction now tests actual worker propagation and SDK serialization with a fake HTTP
transport before spending. Only six untouched scheduled rows continued:two actual timeouts,
one unavailable response, then three circuit-open denials. Those six were all no-answer
trial2rows; they could not validate positive evidence or rescue a two-class comparison.
Parent60second deadline also did not override the adapter's30second HTTP limit. Keep both
measurements and distinguish process cleanup from remote generation latency.

The original296attempt study had only one provider failure. Remote availability does not
explain its large interpretation/citation failure rate. Conversely, the later operational
failure cannot establish that the stronger model was inaccurate. Do not conflate them.

## OpenRouter canary: actual result and budget boundary

The owner approved at most12invented-only attempts. The public catalog listed
`liquid/lfm-2.5-2.6b:free` with zero prompt/completion prices and structured-output support.
Selection was for a small compatibility check, not a claim that this is the best contract
model. The catalog snapshot stays private for reproducibility. No random free-model router,
model-list fallback, paid variant, tools, response-healing plugin or source document is used.

Before the live reservation, all twelve actual payloads and constructed strict responses
were checked offline. The request requires structured output, disables provider fallback
and sets zero prompt/completion/request price ceilings. One owned spawned worker supplies a
55second total parent deadline and a45second HTTP inactivity timeout. HTTP inactivity is
not a total wall-clock guarantee; the parent owns that bound and child cleanup.

**Actual outcome: first request HTTP429/rate_limited, then stopped.** Separate ledger:
**1/12consumed,11remaining,0unsettled**. No retry, alternate model or paid fallback. Raw input,
output and monetary cost are unknown, not zero. The [safe canary report](data/openrouter-free-canary-v1.json)
records the result. Source inventory and settled response pin match the private reservation.
No API key, provider body, original source text or case identifier is published.

A subsequent read-only account-metadata request returned HTTP200, `is_free_tier=true` and a
reported daily free counter of0used/50limit/50remaining. This supports that the key is
recognized; it does not explain the429or prove remote capacity or billing. The rejection
could reflect upstream/model availability or another limiter. Without further evidence,
we cannot claim daily allowance exhaustion, a global outage or an invalid key. The
metadata read was not an inference attempt; our local conservative ledger still counts
the failed dispatch even if the provider daily counter does not. No account changes/top-up.

See OpenRouter's [provider routing](https://openrouter.ai/docs/guides/routing/provider-selection),
[structured-output](https://openrouter.ai/docs/guides/features/structured-outputs) and
[rate-limit](https://openrouter.ai/docs/api/reference/limits) documentation. Free capacity and
routing metadata are time-sensitive; recheck before any separately authorized experiment.
The Gemini ledger remains341/344 and Groq9/12, zero unsettled each. No shared allowance reset.

## Reproduce and verify

From an installed development environment, run the diagnostic with a new output path:

```powershell
python scripts/diagnose_revenue_failures.py --capture-root <private-study-directory> --output <new-output.json>
python -m pytest -q -p no:cacheprovider tests/test_evidence_selection.py tests/test_openrouter_canary.py
python -m mypy
python dev.py format-check
```

The diagnostic validates the saved cohort, schedule hash, request/context bindings, parsed
responses and saved observations before emitting aggregate counts. It does not validate
active allowance/billing; those are separate checks. It makes no provider calls and never
prints source passages. Its output creation is exclusive. Do not run under Python `-O`,
because its audit assertions are intentional checks. Do not rerun the live canary command:
its exclusive private directory prevents resetting/resuming this completed stopped run.

Initial focused79tests pass, including existing Groq, citation and development regressions;
whole-repo types pass198source files. Additional canary tests cover deadlines, timeout,
oversized output, bad usage, retained crash reservations and immutable SQL history. Final
full suite, installed package checks and hosted exact-head evidence follow on the PR.

Adding the OpenRouter optional extra changes lock metadata but adds no new dependency
version. Initial CI correctly refuses the old invented replay's dependency hash. Preserve
v1–v13bytes; generate invented-v14 with the new actual lock and explicit reviewed pin.
Regression checks require v13to refuse the changed environment;83replay tests pass. This
is synthetic replay maintenance, never a new provider recording or historical rebaseline.

## How to discuss this project with employers and businesses

### A truthful two-minute technical account

“We built a shared agent harness and tested a contract assessment component against pinned
publisher references. A296attempt study failed our declared confidence and accuracy gates.
We kept every failure and traced the problem to multiple layers:stable reference-relative
decision disagreements, altered evidence text, a mismatch between the task instruction and
what the benchmark labels meant, and a separate configuration failure in a follow-up run.
We separated task-wording changes from an evidence-selection interface that copies exact
source text locally. We added adapter-level preflight and durable, capped provider canaries.
The new hypotheses have integrity tests but still need model-quality evaluation. We did
not describe implementation merges, exact citations or model agreement as production
qualification.”

### Business implications and questions to ask

- **What decision is actually being made?** Answering whether a term exists, extracting
  relevant language and deciding legal/business acceptability are different claims. Agree
  on the claim before selecting a benchmark or calculating ROI.
- **What does a wrong positive cost?** A missed clause and a falsely asserted right can have
  different consequences. Keep class error rates and unresolved outcomes visible; a single
  blended accuracy can hide the risky failure class.
- **Which evidence is authoritative?** A public annotation can test benchmark-relative
  extraction. It does not automatically establish legal meaning, billing eligibility or
  current company policy. Applicability disputes require an accepted adjudication method.
- **Can the system prove its evidence trail?** Preserve exact input/request/response hashes,
  source positions, policy/candidate versions and failed outcomes. Hashes detect changes;
  they do not certify legal correctness or independent review.
- **What happens when the provider is unavailable?** Stop safely within a durable allowance,
  retain unknown usage/cost and do not silently route to a different model/account. Free
  canary availability does not establish production SLA or capacity.
- **What would permit deployment?** Applicable references, representative fresh families,
  frozen criteria, useful baselines and operational recovery evidence. A green software
  test matrix establishes software checks, not the unmeasured business outcome.

### Questions worth rehearsing for an engineering interview

1. Why were296attempts insufficient despite matching the sample-size proposal? Explain
   zero-error minimum, independent family count and the observed failures; no guarantee.
2. Why not retry until the model passes? Explain selection bias, exposed data, complete
   scheduled denominators, stable repeated errors and conservatively consumed allowances.
3. Why not relax citation matching? Explain permissible whitespace mapping versus changed
   punctuation/negation and the difference between evidence integrity and semantic support.
4. What was your mistake? State the missing worker flag and independent output ceiling,
   explain why admission-only checks missed them, and show the actual adapter preflight.
5. Why introduce another provider? To test a bounded availability/compatibility alternative,
   not to assume stronger judgment. First actual429failed; disclose it and the stopped cap.
6. What evidence would change your mind? A frozen paired development comparison with
   controls and then independent fresh validation; not a few selected successful examples.
7. How did you protect the result from self-deception? Immutable failures/references,
   exposed-set labels, disjoint accounting, explicit uncertainty, separate provider budgets
   and release gates that remain failed when evidence fails.

### Claims to avoid

Do not claim95%reliability, solved legal review, qualified human-equivalent judgment,
production readiness, validated savings or a working OpenRouter inference path. Do not
claim a source annotation is wrong because an AI explanation sounds plausible. The sound
engineering judgment here is the preserved evidence and controlled next experiment, not
pretending the target was reached. Current concrete results: a reproducible failure
analysis, tested prototype integrity, durable scope controls and an honestly failed canary.


### Local environment failure retained during verification

The first full local run ended55failed/1310passed. The failures shown across the source
preparation modules reject the default `C:/Users/wolas/AppData/Local/Temp` path because
this machine has a `C:/.git` marker. This is not permission to weaken source-storage guards
or delete that unrelated marker. Re-run with both TEMP and TMP set to the verified external
`D:/document/.cache/production-agents/s5-temp` path. A focused82test CFPB subset passes with
that setting. Record the corrected full-run outcome separately; do not erase the failed run.
Installed wheels independently verify82harness/37Revenue resources match the built archives,
twelve canary payloads and exact Unicode source copying with networking denied and no
Google/Groq provider SDKs or other industry packages. The synthetic replay consumes6recorded
calls/reproduces2timeouts/zero provider calls. None of these software checks proves model quality.


## Transfer the lesson to the other agents

These are engineering checks to apply, not claims that those agents have passed them:

| Agent | Task/reference mismatch to guard against | Evidence that must stay separate |
| --- | --- | --- |
| Olist support | A customer expressing refund intent is different from eligibility or authorization to issue a refund | Intent interpretation, policy predicates, exact SIM amount, distinct approval and committed state |
| CFPB triage | Product/topic classification does not establish urgency, vulnerability or appropriate resolution | Published taxonomy, separately justified risk labels, routing calibration, redacted evidence and authorized reviewer state |
| Revenue | A relevant contract passage does not itself establish legal effect or a billing discrepancy | Publisher extraction agreement, semantic applicability, deterministic SIM arithmetic and approved action |
| Prior Auth | Finding a clinical phrase is different from satisfying every current policy criterion | Source version, literal spans, missing/conflicting facts, criterion logic and qualified recommendation evidence |
| Supply chain | Estimated improvement and a committed SIM action do not establish realized freight savings | Visible estimates, evaluator-only simulated outcomes, spend/approval state and factual notification wording |

For each new evaluator, write the assertion being tested in one sentence. Identify which
part of the reference actually supports it, the risky error class, the unit of independence
and what to do when evidence is missing. Use executable checks for arithmetic, permissions,
source fidelity and state transitions; use applicable reference-based model evaluation for
language judgment. Do not let a useful deterministic check stand in for the harder semantic
claim. Keep failures, unknown usage and unobserved outcomes visible in the shared reporting.

For a new engineer joining the project, start with the failure aggregate and reproduce it
before editing prompts. Read Entry66to understand how the operator configuration failed;
read Entry67to understand how the diagnosis changed the experiment design. Run the invented
integrity tests, then explain which business claims they cannot prove. This gives a new
teammate a concrete review exercise without access to production personal data or API keys.


Final software verification and post-merge acceptance are recorded on
[PR120](https://github.com/Protagonist01/my-production-agentic-systems/pull/120).
Use the exact final head/main logs there; earlier failed/cancelled runs remain historical.
Neither a green matrix nor this investigation closes the outstanding release issues.
