# Olist O8 follow-up model card

**Review evidence only; production release remains refused.** This is a separate 12-case hybrid pilot, not a rerun or rewrite of the [first fresh pilot](olist-model-card.md). Labels remain AI-provisional.

## Candidate and protocol

Frozen code `0be72b2ae227e81f341353e2478f854fcc8f4b6c` uses the unchanged `gemini-3.5-flash-lite` intent prompt and fixed 100.00 SIM policy. The shared adapter recovers reported output usage when totals exactly match prompt plus candidates. Local process diagnostics accompany each new model row. The pinned plan permits attempts of 60 seconds and runs of 90 seconds, one attempt per trial and at most 36 Gemini Free calls, with no paid fallback.

Six new exact source groups exclude all 12 earlier groups. Each development, regression and holdout split has four cases. Overall, there are six base and six adversarial cases; three permit a refund and nine require review. Only constructed request text enters the provider. Original fields, identifiers, customer/review text, expected labels and splits stay local. Source currency and timezone remain unverified; numeric amounts are reused only as fictional SIM amounts. The coverage sample does not represent support traffic or prove independence between consumers or similar orders.

The rules baseline knows the constructed request grammar. Always-review gets no eligible-completion credit. Each mode has 36 isolated database trials; the independent scorer checks the exact permitted change across every tenant and verifies truthful receipts. A new store and checkpointer repeat delivery without another model dispatch. Errors or missing state remain unresolved. No trial was rerun.

## Actual results

|Mode|Correct / scheduled|Unsafe|Unresolved|Eligible completed|Required reviews correct|Observed review|All three correct cases|
|---|---:|---:|---:|---:|---:|---:|---:|
|Template-aware rules|36/36|0|0|9/9|27/27|27/36|12/12|
|Always-review|27/36|0|0|0/9|27/27|36/36|9/12|
|Gemini|36/36|0|0|9/9|27/27|27/36|12/12|

|Gemini split|Correct / scheduled|Unsafe|Unresolved|Eligible completed|Required reviews correct|Observed review|All three correct cases|
|---|---:|---:|---:|---:|---:|---:|---:|
|Development|12/12|0|0|3/3|9/9|9/12|4/4|
|Regression|12/12|0|0|3/3|9/9|9/12|4/4|
|Holdout|12/12|0|0|3/3|9/9|9/12|4/4|

Failure codes: `{}`. Proposed pilot criteria met: **true**. This is not baseline/threshold approval or independent label validation. The changed cohort, environment, deadline and host conditions prevent a paired or causal improvement claim against v1.

## Process diagnostics and accounting

Timing was captured for all 36 model rows. No timeout occurred before or after worker entry. Generation returned and the response frame was ready in all 36 rows. Worker entry does not prove provider dispatch or billing.

|Local phase (seconds)|Observed rows|Minimum|Median|Maximum|
|---|---:|---:|---:|---:|
|worker_entry_seconds|36|6.329|8.225|36.348|
|generation_after_entry_seconds|36|3.807|4.831|10.587|
|parent_attempt_seconds|36|11.659|13.461|47.928|

Worker entry includes process spawn/bootstrap; generation after entry includes SDK import, provider waiting and parsing. These are local process measurements, not isolated API latency. Builds/installed checks finished during baseline-only work; no host test suite overlapped Gemini capture. Existing local Langfuse services were running. The first unsealed attempt stopped before a trial because Docker was unavailable; it produced only a plan and zero model calls. It is retained separately.

One worker entered after the previous 30-second attempt limit. This demonstrates that startup
can exceed that limit on this host. The old six timeouts had no phase diagnostics, so their
causes remain unproven. Increasing the deadline is an explicit experiment setting, not proof
that a production performance issue has been resolved.

The runner reports 36 model calls, 2,790 input tokens and 966 output tokens. Token usage is known for all 36 attempts; cost remains unknown for all 36. No cost-efficiency or savings claim is established. Free-project confirmation is an operator attestation.

Gemini duplicate delivery retained the original state and result in all 36 trials, and all 36 owned databases were removed. Full denominators and source-type/treatment breakdowns appear in the [aggregate](data/olist-followup-evidence-v2.json). Evidence byte pin: `2b8f76ce30ddf0cbec173a66f93873c5f44da9c4db53f4a30707aca504c9060e`. Offline independent read-back verified every JSON/receipt file and recomputed identical verdicts without another provider call.

## Remaining gates

There are only four unique constructed request texts. Templates repeat across splits; the disjoint source groups do not establish an unseen-language holdout or broad intent robustness.

The historical pilot and its six timeouts stay unchanged at the original candidate/lock. These new results are not evidence for that old candidate or production traffic. Independent label adjudication, reviewed baseline/thresholds, representative validation and H10 release requirements remain pending. Local artifacts trust the evaluator/operator; hashes do not provide hardware attestation. No real payment, shipping operation, public deployment or production release occurred. Keep #33 and downstream release dependencies open.

See [follow-up runbook](olist-followup-review.md) and [source walkthrough](code-study-olist-fresh.md). Exact-head local/hosted acceptance is recorded on the PR after checks finish.
