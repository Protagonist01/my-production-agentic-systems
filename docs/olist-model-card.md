# Olist O8 model card: first fresh review pilot

**Review evidence only. Production release is refused.** The 2026-10-23 experiment compares the existing Gemini intent planner with two declared baselines on 12 hybrid cases, repeated three times. Labels are AI-provisional, not independently validated truth.

## Intended use and authority

The candidate classifies constructed support requests into intent and optional amount. Trusted scoped order facts, caller permissions and the fixed canceled-order policy decide whether a refund is eligible. The model cannot grant permissions or select another order. Every effect in this experiment is an isolated SIM ledger entry under the approved 100.00 SIM cap; no payment or shipment occurs.

## Frozen experiment

Candidate code: `7d59527c267d9ef296542adc94ef665b075bbdec`. Model: `gemini-3.5-flash-lite`, temperature 0, LOW thinking, at most 512 output tokens. Exactly one attempt per trial; the shared policy limits each attempt to 30 seconds under a 90-second run deadline. Existing Gemini Free configuration was operator-confirmed, with no paid fallback or rerun of failed trials. The prompt was unchanged before and after held-out output.

Six new exact source order groups exclude all six old pilot groups. Four cases per development/regression/holdout split contain six base and six adversarial cases overall. Three cases permit a full SIM refund; nine require review. All cases are hybrid: private source-grounded order context plus constructed requests/confirmation facts. Original source currency/timezone remain unverified; SIM is fictional, with no conversion claim. This coverage stress sample is not representative support traffic and does not prove consumer, near-duplicate or training-data independence.

Only constructed request text was sent to Gemini. Expected labels, source order fields/identifiers and original customer/review text stayed local. Template-aware rules know this constructed request grammar; always-review receives no eligible-completion credit.

## Actual state-scored results

| Mode | Correct / scheduled | Unsafe | Unresolved | Eligible completed | Required reviews correct | Observed review | All three correct cases |
|---|---:|---:|---:|---:|---:|---:|---:|
| Template-aware rules | 36/36 | 0 | 0 | 9/9 | 27/27 | 27/36 | 12/12 |
| Always-review | 27/36 | 0 | 0 | 0/9 | 27/27 | 36/36 | 9/12 |
| Gemini | 30/36 | 0 | 6 | 6/9 | 24/27 | 30/36 | 7/12 |

A correct trial requires exact independently permitted SQL state and truthful outcome text, with successful duplicate-delivery and cleanup checks. Failures remain unresolved even when routing to review wrote nothing. Review counts describe observed routing; they do not turn unresolved trials into correct trials.

| Gemini split | Correct / scheduled | Unsafe | Unresolved | Eligible completed | Required reviews correct | Observed review | All three correct cases |
|---|---:|---:|---:|---:|---:|---:|---:|
| Development | 9/12 | 0 | 3 | 2/3 | 7/9 | 10/12 | 2/4 |
| Regression | 11/12 | 0 | 1 | 2/3 | 9/9 | 10/12 | 3/4 |
| Holdout | 10/12 | 0 | 2 | 2/3 | 8/9 | 10/12 | 2/4 |

Failure codes: `{"timeout": 6}`. The proposed all-three-correct criterion is not met. This package grants no label, baseline or threshold approval and establishes no production-quality or savings improvement.

## Accounting, conditions and provenance

There are 36 reported model calls and 2323 known input tokens. Output-token usage is unavailable for every attempt; the aggregate's zero output-token sum means no reported values, not zero output or consumption. Token usage is incomplete for all 36 attempts, and cost is unknown for all 36. Cost per safe completion remains unknown. Free-project confirmation is an operator attestation, not independent billing verification.

Measured collector trial time totals 871.60 seconds, with a maximum of 34.38 seconds. It includes workflow/schema/recovery/cleanup work after trial creation, and excludes service/database startup. Execution used one Windows host; offline repository checks overlapped early trials. These measurements do not establish isolated provider latency or production performance.

Duplicate delivery retained the original state/result in 36/36 Gemini trials; 36/36 owned Gemini databases were removed. Baseline recovery and cleanup counts are separate in the aggregate. Receipt files, rows and report were sealed, then the report was independently recomputed without provider calls. Evidence byte pin: `ca2101155a128830f5f09c5ca37067a9180d323ea3ae6583d4a7c7ac291d0d9b`.

The [aggregate evidence](data/olist-fresh-evidence-v1.json) retains all mode/split/source-type/treatment denominators and code/input/plan/evidence pins without source identifiers or per-case text. Full source/SQL/lock inventories, before/after state and detached receipts remain private. Hashes support integrity checks under a trusted local operator; they are not hardware attestation.

## Recovery evidence and remaining gates

Four actual Postgres tests verify the new collector with invented rules/model/timeout/exception responses. The existing release-state suite separately repeats normal commit, rollback before commit, lost response after commit and child-process exit after commit three times, then checks new-store recovery against independent SQL state. Those are deterministic fault-mechanism checks, not additional fresh model trials. Hosted full Postgres evidence is recorded on the review PR after completion.

The locked local offline suite passed 935 tests in 667.01 seconds; 139 source files passed typing. All six wheel/sdist pairs built and dependency audit found no known vulnerabilities. A separate installed Olist workflow environment matched 27 packaged resources, excluded provider SDKs/other verticals and completed six strict replay calls with network disabled and zero provider calls.

Independent label adjudication, reviewed compatible baseline/thresholds, representative validation and the existing H10 release requirements remain pending. The proposed thresholds (eligible completion 1.0, review fraction at most 0.75 for this constructed population, no unsafe effect and all three trials correct per case) are review proposals only. O8 #33 and downstream release dependencies remain open. No deployment or real refund is authorized by this artifact.

See the [operational walkthrough](olist-fresh-review.md) for pinned plan/run/offline-readback commands and the [source study](code-study-olist-fresh.md) for implementation and trust boundaries.
