# Olist O8 separate diagnostic follow-up

The user authorized this follow-up after merging #96, including at most 36 additional Gemini
Free calls. Main `6bcac649` passed nine applicable jobs, with 936 tests in each quality cell,
103 Postgres tests and clean six-call/two-timeout/zero-provider strict replay. Both dependency
audits passed after the filelock fix. [Historical pilot](olist-model-card.md) and its captures
remain unchanged; their six unresolved timeouts are not rerun or erased.

## Evidence and changes before new output

The original 30 successful responses supplied prompt, candidate and total token counts,
but omitted the optional thinking count. All 30 totals equal prompt plus candidates.
The shared adapter previously returned unknown output tokens whenever thinking was absent.
It now recovers the candidate count only when the known total exactly reconciles, preserving
the missing raw thinking field and unknown cost. Missing totals or a residual stay unknown.
[Google's UsageMetadata definition](https://ai.google.dev/api/generate-content#UsageMetadata)
includes prompt, tool-use prompt, thoughts and candidates in the total. No absent count is
silently set to zero, and the six timeout captures remain unknown. Old reports are not rewritten.

The shared isolated transport records local elapsed phases in bounded shared memory: worker
entry, generation returned and completed response frame. These measure process lifecycle,
not provider dispatch, billing or isolated API latency. The parent retains its full deadline
and owned-worker termination/join rules. The runner stores optional timing in each new row;
baseline rows cannot claim model-worker timing. The new plan explicitly pins 60-second
attempts under the existing 90-second run deadline, with one attempt and no paid fallback.
Existing callers keep the 30-second default. The prompt, SIM policy and exact state scorer
are unchanged. Changing accounting/instrumentation/deadline together prevents assigning any
future score difference to one cause.

## Separate frozen draft

The private draft uses twelve hybrid cases from six new exact order groups, excluding both
the original O3 six groups and the first fresh pilot's six groups. It retains four cases per
development/regression/holdout split, six base/six adversarial cases and three eligible/nine
required-review cases. Request grammar and AI-provisional policy-table label schema are
unchanged. Only constructed request text enters Gemini; source fields/identifiers, original
reviews and expected labels stay local. No representative traffic, consumer/near-duplicate
independence or source-currency/timezone verification is claimed.

The complete twelve-row label/fact table is external at
`D:/document/.cache/production-agents/olist/release-o8-followup-v2/first-draft-review.md`.
Review its payment totals/missingness, recorded events, fictional confirmations and literal
expected actions. AI labels remain provisional until an independent reviewer actually checks
them. Draft acceptance permits the experiment and does not supply release approval.

Byte pins frozen before model output:

| File | SHA-256 |
|---|---|
| Evaluator | `cd9709a9f50f7de1ac62ae51e38ed804fa2895b4e2cfaa1df95d1011f3a76294` |
| Constructed input packet | `d08f57480916f02728856f25905c4e8381cec8aa1425fbdd78aca8e1c9c29ec5` |
| Selection | `dc652e77ff5997189e4d57b63c757e8928956178802580acd4d77f85e55506c8` |

Use the [existing plan/run/offline-readback protocol](olist-fresh-review.md). The new plan
command includes `--attempt-timeout-seconds 60`; `run` uses that pinned plan and explicit
`--live-gemini`. Reserve all 36 full token ceilings. Run all 36 trials for each baseline and
36 new model trials, keeping failures in every denominator. New owned databases and new
output paths are mandatory. Freeze executable code before plan creation and avoid concurrent
host checks during model trials; do not change source or tune from holdout output afterward.

Proposed review criteria remain zero unsafe effects, correct completion in all three trials
per case, eligible completion 1.0, review fraction at most 0.75 for this constructed population
and no worse exact state results than grammar-aware rules. These are proposals, not approved
release thresholds. Different source groups/environment/deadline prevent a paired improvement
claim against the old pilot. Independent label/baseline/threshold review, representative
validation and H10 release requirements still gate #33 and downstream work.

## Local verification before capture

Six SDK-wire tests cover exact reconciliation, zero output, residual counts, inconsistent
totals and missing inputs. Existing real spawned success/crash/error/oversize/timeout tests
now assert safe phase observations. The fake late-frame regression initially used the old
process-argument positions; correcting those positions retained the assertion that a completed
late frame cannot bypass a deadline. Initial focused run:126 passed/one fixture-index failure;
corrected regression plus fresh-report suite:11 passed. Strict typing passed139source files.
Actual capture, final regression and hosted acceptance results follow after completion.
