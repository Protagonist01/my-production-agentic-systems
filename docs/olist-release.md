# Olist offline release preparation

O8 adds an independent state scorer and a private report command after merged O6/O7 main `67e0349`. The user retained offline-only acceptance on 2026-10-20. **O8 release acceptance remains pending.** Neither passing these checks nor a three-trial mechanism report grants release approval.

The [source study](code-study-olist-release.md) explains the implementation. Existing [workflow](olist-workflow.md), [local console](olist-console.md), [shared scorecards](scorecards.md) and [fresh recording/release gates](release-evidence.md) retain their boundaries. This delivery adds no provider transport, model baseline, release thresholds, account integration or deployment.

## What is measured

| Priority | Existing requirement implemented here | Evidence and decision |
|---|---|---|
| P0 | Exact authorized refund once; no unrelated or excessive effects | Independent SQL before/after snapshots of **every tenant** in the isolated trial. An extra/missing/changed row, wrong payload, changed source facts, inconsistent balance/version/budget or substituted receipt fails state verification. |
| P0 | Truthful committed outcome | The O5 refund response must carry the exact current operation's committed receipt and fixed SIM wording. Returning another prior operation's valid receipt fails. Review carries no receipt and the fixed no-confirmation wording. |
| P0 | Eligible completion and required review | Literal private O3 labels supply expectations; runtime `propose()` and `verify_receipt()` never supply the scorer's judgment. Missing and interrupted observations remain in scheduled denominators. |
| P1 | Review burden | Required-review correctness, unnecessary review among eligible cases and observed review over all scheduled trials have explicit denominators. |
| P1 | Repetition and provenance | Exactly three distinct isolated mechanism trials per case; all-three-correct is reported over cases. Split, source kind and base/adversarial treatment remain separate. |
| Pending | Fresh provider reliability, cost and latency | Provider freshness is always false; cost and latency are null/unmeasured. Mechanism repetition is not fresh three-trial model correctness. |

These deterministic metrics instantiate the already declared O8 requirements; they introduce no numeric quality threshold. The [Langfuse evaluator guidance](https://langfuse.com/academy/evaluate/writing-evaluators) supports checking observable state with code. No Langfuse service, dataset or evaluator is created by this command.

## Collect a private controlled observation

Use one fresh F4 trial database per case/trial. The collector is an evaluator operation, never an agent tool. Its supplied connection must be idle and able to read the complete isolated database. Collection owns a repeatable-read, read-only transaction; workers must finish or stop before the final snapshot. The collector reads business order source/facts/version/balance, refund payload/receipt/amount and run budgets. It does not inspect console consent tables; those retain their separate O6/O7 atomicity tests.

1. Verify the separately reviewed O2/O3 source byte pins. Load `PolicyCases` only in the evaluator. Preserve its complete case population, grouping and split labels. Do not create a smaller post-hoc set of successful observations.
2. Construct three `ScheduledTrial` objects per case with distinct run IDs and exactly the declared trial IDs. The trusted grant scopes the case tenant/order. A refundable evaluator expectation supplies the exact permitted `RefundCommand`; a review expectation can use `command=None`. This command is **evaluator-only** and must not be supplied as the agent's plan.
3. Create an `OfflinePlan` binding `pin(cases)`, code revision, lock byte hash, scorer byte hash and source inventory. Inventory every executing harness/Olist `.py` file and `uv.lock` by portable relative path and byte SHA-256. Pin the plan independently before capture. `verify_sources` compares both the reviewed checkout and actual installed package bytes, including the running CLI.
4. Bootstrap business/checkpoint schemas and enroll the case's unchanged `OrderView` and explicitly constructed `ScenarioConfirmation`. Use `collect_state(admin)` before execution. The scorer independently binds that initial enrollment to the private case, including the source pin.
5. Run `SupportWorkflow` using only `WorkflowRequest(order_id, text)`, the trusted grant/context, persistent saver and `FixedPlanner(IntentPlan(intent=request.intent, requested_minor=request.requested_minor))`. No expected action, amount, reason or split enters the planner. The caller-selected offline intent exercises mechanisms; it measures no natural-language model quality.
6. Repeat delivery/recovery using a new store/process and stable business event/checkpoints. Capture after **all attempts**. A new run must return the original receipt without another ledger/budget effect. For a failure with no trustworthy final state, set `after=None`; for a missing result, retain `outcome=None` and explicit generic error codes. Do not infer rollback from a timeout.
7. Save `Observation(case_id, trial_id, before, after, outcome, receipt, message, errors)` objects in one external JSON array. The `before` snapshot precedes the first attempt; an already completed operation is not a fresh first-attempt fixture. Remove only the owned trial databases after their final evidence is collected. Retain failed/interrupted observations; omitting one produces a missing scheduled row.

`tests/integration/test_olist_release_state.py` is an executable invented example of this lifecycle. It repeats normal commit, rollback-before-commit, lost response after commit and an owned child exiting 31 after commit three times each. New-store retries then undergo independent state scoring. A separate check proves that a required review writes nothing and an unrelated effect is detected.

## Generate the private report

From the locked checkout, use the installed module directly:

```powershell
uv run --locked --all-packages --link-mode copy python -m olist_support.release_cli --help

uv run --locked --all-packages --link-mode copy python -m olist_support.release_cli `
  --cases <external-evaluator.json> --cases-pin <reviewed-canonical-case-pin> `
  --plan <external-plan.json> --plan-pin <reviewed-canonical-plan-pin> `
  --observations <external-observations.json> --observations-sha256 <reviewed-byte-hash> `
  --source-root <reviewed-checkout> --output <new-external-report.json>
```

The placeholders require concrete reviewed values, not defaults. `pin(contract)` hashes its UTF-8 canonical JSON. Thus the CLI's case/plan pins and report `cases_sha256`/`plan_sha256` are **canonical contract hashes**; they need not equal a pretty-printed file's byte hash. The earlier O3 `evaluator_sha256` is a **raw file byte hash** and remains source provenance. Verify it before loading the original cohort.

`--observations-sha256` verifies the exact input bytes. The report stores that raw hash as `observations_file_sha256`, the case file byte hash as `cases_file_sha256`, and the canonical observation-array hash separately as `observations_sha256`. Array order is retained. Library-only reports leave raw file hashes null because they did not read files. Whitespace changes can alter a raw hash while leaving the canonical contract hash unchanged.

The CLI never dispatches a provider, writes approval, discovers a baseline or promotes a result. Output paths must be outside every Git checkout and must not exist. Output creation uses mode 0600 on POSIX; Windows inherits the parent ACL, so use a restricted external directory. It prints aggregate counts and `release_allowed:false`, never private case identities. Generic rejected-input diagnostics avoid echoing private labels or text.

Exit 0 means every scheduled **offline mechanism** trial was correct. Exit 2 means an invalid pin/path/source inventory, missing/unresolved/incorrect/unsafe trial, or other rejected input. An otherwise valid incomplete report is retained so its denominator can be inspected. Existing output is never overwritten. Both exit paths leave release acceptance pending.

## Read results without losing failures

`correct` requires the exact independently expected state and truthful output. `unsafe` is an observed forbidden state delta or unverifiable claimed result when final state is available. `incorrect` includes unnecessary review with no prohibited effect. `unresolved` retains execution/cleanup errors, missing result or unavailable final state; a known unsafe delta still takes precedence over an error. `missing` means no observation for a scheduled pair. None of the last four categories is a passing trial.

Every ratio keeps the declared population. Correctness has lower observed success and a possible upper bound that includes missing/unresolved rows. Observed review can be known even when cleanup failed; that known review is not counted again as an unknown. Three-of-three mechanism correctness requires all three complete correct verdicts for a case. A known failed trial prevents that case from being counted as an unknown possible all-three success.

The report separates development/regression/holdout, hybrid/synthetic and base/adversarial observations. O3 currently has no original-only support-policy cases: real order context plus constructed messages/facts remain **hybrid**. Expected labels remain AI-reviewed provisional judgments, not human gold or observed Olist refund decisions. Publishing only counts does not change their evidence quality.

## Reproduce implementation checks

```powershell
$env:TEMP = 'D:/document/.cache/production-agents/test-temp'
$env:TMP = $env:TEMP
uv run --locked --all-packages --link-mode copy pytest -q tests/test_olist_release.py
uv run --locked --all-packages --link-mode copy pytest -q tests/integration/test_olist_release_state.py -o addopts='--strict-config --strict-markers'
```

The focused offline suite includes negative controls for extra ledger effects, incorrect balance/version/budget/source facts, another tenant, a forged or prior unrelated receipt, incorrect outcome wording, missing/error observations, duplicate/unscheduled rows, altered pins, exclusive output and an underspecified fake source root. Full integrated checks and the pinned source-cohort aggregate are recorded separately with actual candidate acceptance evidence.

## Remaining release work

The module deliberately supports automatic O5 refund/review outcomes for the constructed SIM policy. Review correctness here measures required routing and unchanged state; it does not grade the semantic quality of a reason/rationale or evidence explanation. Status-only requests, approved-console response wording, console consent scoring and a general H6/H10 provider-composition adapter are not implemented here. Existing console tests remain the evidence for authenticated approval/recovery behavior. All supplied snapshots, pins and executable code are trusted local evaluator inputs; hashes do not defeat an operator who can forge the entire evidence chain. This is not a security sandbox or exhaustive security audit.

O8 still needs independent human label adjudication, a reviewed compatible domain baseline and thresholds, authorized fresh held-out provider captures, measured provider usage/latency, and the existing H10 gate's complete freshness/approval checks. The user's offline-only choice leaves those pending. The 100.00 SIM cap and all commit-time eligibility rules remain unchanged; no real payment or shipment occurs.
