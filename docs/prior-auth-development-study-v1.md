# Prior Auth: completed criterion-extraction development study

On November 13, 2026, the owner-approved study completed **168 fresh Gemini Free calls**:
two passing canaries followed by 166 domain requests. All responses had valid structured
claims and known input/output token counts. No request was retried and no fallback
provider/model was used. All 24 scheduled case trials have reconstructed checked results.

This is a controlled development study on 12 authored notes and their proposed references.
It is not a clinically qualified reference set, natural-patient accuracy estimate or
release acceptance. The notes share constructed patterns; repeated criteria/trials
must not be counted as independent patient families.

## Actual results

| Observation | Result | Unit/meaning |
| --- | --- | --- |
| Canaries | 2/2pass | Representative approved requests before domain dispatch |
| Domain requests | 166/166 observed | Two of 168 logical criterion slots had no retrieval/request |
| Raw model state agreement | 160/166(96.4%) | Agreement with accepted constructed proposals |
| Checked state agreement | 128/168(76.2%) | All logical criterion slots after the frozen checker |
| Rules baseline agreement | 154/168(91.7%) | Same notes/proposed states, two deterministic trials |
| Always-review state agreement | 8/168(4.8%) | State agreement; this does not measure safe-review routing |
| Checked positive claims against proposed non-met states | 0observed | Constructed proposals only, not a clinical safety bound |
| Final assistive dispositions | 1 evidence-complete-for-review, 19 request-information, 4 qualified-review | Actual outputs; disposition gold is absent |
| Parent-side request p95 | 9.768seconds | Includes the spawned worker; not API or whole-case latency |
| Parent-side request median | 5.535seconds | Same controlled host/protocol |
| Known input tokens | 88,684 | All168calls including canaries |
| Known output including thinking tokens | 11,749 | Normalized SDK usage; no unknown-to-zero conversion |
| Observed model revision string | gemini-3.5-flash-lite,168responses | Provider-reported alias; no stronger version identity inferred |

The raw-model and checked denominators differ because the latter also includes two
retrieval-absent logical slots. They are not two estimates over an identical population.
All missing-request counts are zero for the actual166request schedule. Raw/checked
agreement is not clinical correctness, and an exact quotation alone is not semantic
support. Baseline agreement is not a release score or a reason to promote a baseline.

The data contains no independent disposition reference, independently established
patient-family count or provider billing cost. Those fields stay unknown. The owner's
Free-project attestation and absence of paid fallback do not constitute billing evidence.

## What failed and why

Six raw model disagreements occurred, twice each on three exposed development cases:

- Fractional boundary: model said severity met at14.5; the constructed method leaves
  the threshold/rounding interpretation insufficient.
- Same-measure conflict: model said met with two competing AHI values; the proposed
  reference is conflict.
- Short study: model said the event-count condition met; the proposed national method
  deliberately leaves its interpretation unresolved.

The frozen checker contained all six positive disagreements: four became insufficient
and two became conflict. It also introduced40disagreements against otherwise matching
proposed states:38insufficient results tagged `missing_or_unrecognized_support`, plus
two different-measure severity results tagged `conflicting_visible_rates`.

| Criterion | Checked/proposed agreements out of24 |
| --- | --- |
| Adult/OSA | 22 |
| Education | 24 |
| Clinical evaluation | 24 |
| Sleep test | 5 |
| Physician order/supervision | 17 |
| Severity | 20 |
| Event count | 16 |

Inspection of a few approved invented quotations narrowed the problem. In one sleep-
test trial the model cited only the attended-PSG sentence, omitting the separate
positive-result sentence. In both missing-education trials it cited the physician's
order but omitted the supervision sentence. An AHI14negative judgment cited the
number without its missing-symptom context. These are incomplete supporting citations
or limitations of the narrow negative-support grammar, not JSON transport failures.
The checker already joins multiple citations; this is not a missing concatenation fix.

Preserve the failure captures. The next candidate development should require complete
criterion evidence, including all applicable subconditions and relevant negative/
conflicting context, and separately investigate the national/local event-count and
AHI/RDI interpretation boundaries. Keep explicit abstention while support is missing.
Do not weaken the checker or relabel these cases to improve agreement. A changed prompt
or checker needs its own version; this run does not fund another provider comparison.

The [reference applicability audit](prior-auth-reference-applicability.md) also records
ambiguities in generic event counts and study intervals. Current constructed labels
are not clinically certified. The six-case disagreement description is a development
diagnosis; it does not establish which clinical interpretation is true for real records.

## Custody, budget and reconstruction

The provider execution used source `0eefbf27ef2b4255b88694abad113b43037f6218`,
the approved v2manifest and the original pinned CMS compilation. Exact source/lock
identity was verified after the run before any Python file was changed. The manifest
and old captures were not rewritten. Expected states were separate from model input.

The shared SQLite file now contains447unchanged historical attempts plus168new PA
reservations/settlements: **615/784lifetime attempts**, zero unsettled, no PA stop.
The original stopped routing scope and all its bound slots remain unchanged. The
two unused slots in the170attempt upper bound cannot be transferred to new requests.
The new cumulative marker is `prior-auth-784-external-pin.json` beside the original
ledger; the old frozen reader still reports its historical447/614scope.

The first independent readback was denied because it used the generic example tenant
instead of the approved demo tenant when reconstructing a completed case. Earlier
tests covered missing/canary-only captures but had not exercised a completed case.
Fix only the reader's explicit context binding, add that regression, then rerun it
without a provider. Three reader tests passed. The changed reader and its test are
the only post-run Python source differences; requests, provider controls, candidate,
policy, labels and all recorded outputs are unchanged. The old denial remains part
of the engineering record.

The corrected independent reader verifies the external scope pin, old logical SQL
history, immutable settlement hashes, artifact equality, raw parse/quote checks and
reconstructed checked decisions. Its report preserves failures/missing denominators
and has `clinical_qualified=false` and `release_allowed=false`.

Private paths:

- Approved packet: `D:/document/.cache/production-agents/prior-auth/release-readiness-2026-11-13-v2`
- Capture/readback: `D:/document/.cache/production-agents/prior-auth/development-capture-2026-11-13-v1`
- Independent report: `independent-readback-v2.json` in that capture directory
- Clinical inventory: `D:/document/.cache/production-agents/prior-auth/qualification-evidence-2026-11-13-v1`

## External payer and release status

The separately pinned official HL7 reference service passed actual submit, independent
Claim correlation, durable replay and inquiry. Its response was A3(not required) for
the invented service. This is an owned reference-server transport demonstration, not
commercial payer acceptance, complete PAS conformance or clinical adjudication.

Clinical qualification remains open: applicable permitted independent references or
an evaluator qualified against them, an accepted clinical risk/coverage method, a
fresh family-separated qualification cohort and final application evidence are still
required. All eight required clinical fields and holdout slices remain in force.
The completed model study and [reference packet](prior-auth-release-readiness.md)
provide evidence and concrete next work; issue51 remains open.
