# Offline evidence foundation: first execution batch

2026-10-26, branch `codex/evidence-foundation`, inspected base95691bde. This branch implements
the first offline portion of the [execution plan](automated-review-execution-plan.md),
advancing #33, #25 and #60 preparation. It does not complete any release or qualify a judge.

## What is executable

[`evaluation_planning.py`](../harness/src/agent_harness/evaluation_planning.py) supplies strict,
versioned contracts for proposed evidence paths, provider allowance snapshots, planned call
dimensions, exact source spans and diagnostic assessments. It imports no provider worker.
The [planning CLI](../harness/src/agent_harness/evaluation_plan_cli.py) installs the existing
network-denial hook when run as a module. It reads supplied files, validates pins and prints
aggregate JSON; it cannot reserve, dispatch, reset a ledger or approve a release.

The [43-field matrix](evaluation/evidence-paths-v1.json) binds all five current profiles by
canonical hash. It covers every required field and holdout slice. Every field remains
`pending`, with a proposed check, existing documentation and explicit remaining evidence.
`validate_matrix` refuses duplicate/missing/extra agents, changed profiles, missing fields
and changed slices. This proves inventory completeness, not reference accuracy or adequate
sampling. Profile hashes are not recomputed into trusted values at release automatically.

`AssessmentProposal` carries an input/evaluator hash, evidence sources, literal spans and a
diagnostic judgment. Text-based supported/contradicted judgments require cited spans. A
span verifies its exact UTF-8 source hash and Unicode code-point offsets; finding those
characters does not establish semantic support. Even a qualification-report hash remains
a pointer, not authenticated qualification. A proposal cannot claim `qualified_blind`,
change `diagnostic_only`, enable release or deserialize as the existing `Review` contract.
Assessment instances still require explicit span verification against the actual source;
constructing the record alone does not perform source IO or establish correctness.

## Independent Olist policy table

[`evaluation_oracle.py`](../projects/olist-support/src/olist_support/evaluation_oracle.py)
does not import/call the runtime policy or its constants. It evaluates its own predicates
against `OrderView` and separate `OracleFacts`/`OracleRequest` contracts. It returns all
failed rules instead of reusing the runtime's first-error reason. Scope mismatch refuses;
times retain their unverified source-local basis. Unknown payment, unit, non-delivery or
previous-refund state blocks a proposal. Exactly10,000minor SIM units can be proposed;
10,001requires review. An explicitly partial request requires review. There are no effects.

Example flow: a complete5,000minor-unit payment plus visible cancellation, available SIM
confirmation, verified non-delivery and zero previous refund gives a5,000proposal. Changing
the requested amount to2,000makes `full_payment_requested` fail. This is policy behavior
conditional on the structured request; the oracle does not derive intent or requested
amount from language. It cannot label those fields independently for a fresh text case.

The oracle is an independently written implementation of the already accepted fictional
[SIM decision table](olist-policy.md). Shared specification mistakes remain possible. Literal
boundary/missing/conflicting/future-fact witnesses test its mechanics; final policy-evidence
acceptance and candidate-bound scoring remain future work. Its rule names are not verified
natural-language review reasons. It is not automatically wired into H10 or production tools.

## Reference source register and residual judgments

This is an audit of existing prepared sources and documentation, not a new search/download,
license opinion or assertion that a suitable external benchmark has been found for each field.
Original private packets remain unchanged. New data acquisition/export needs source review.

| Scope | Existing source/reference | What it can support | Remaining limitation/action |
| --- | --- | --- | --- |
| Olist | Original order context plus separately constructed SIM facts; accepted policy table | Source facts, exact policy calculations and stored effects | No independent unseen language labels. Build an applicable intent/amount reference set; existing user-accepted AI propositions remain exposed. |
| CFPB | Published narratives and consumer-selected taxonomy; AI-provisional risk rubric | Disclosed noisy taxonomy reference and literal narrative evidence | Risk/ambiguity are not expert-verified labels. Find an applicable qualified reference source; otherwise semantic qualification stays unresolved. |
| Revenue original | Pinned CUAD extraction corpus with publisher annotations; see [source/use notes](data/revenue-source.md) | Applicable extraction spans with attribution, original annotation purpose and exposure caveats | Audit mapping/coverage; do not infer general contract interpretation or SIM invoice truth. No new license assessment was performed in this batch. |
| Revenue SIM | Invented billing worlds and declared arithmetic | Separately implemented calculations and exact authorized effects | Independent arithmetic oracle and semantic assumption checks still needed; historical AI labels remain provisional. |
| Prior Auth | Pinned CMS initial-CPAP policy and Synthea illustrative/edited/invented cases | Exact policy text, supplied fact boundaries and workflow state | No qualified clinical labels have been acquired. Policy provenance cannot establish interpretation accuracy or clinical validity. |
| Supply | Invented worlds plus separate public observations, visible estimates and hidden outcomes | SIM constraints, realized outcomes under declared formulas and sensitivity | No external validation of real-world dynamics. Implement independent constraint checks and investigate assumptions; no freight-savings inference. |

Existing provenance: [Olist](olist-policy.md), [CFPB](cfpb-triage.md),
[Revenue](revenue-integrity.md), [Prior Auth](prior-auth-evidence.md),
[Supply](supply-chain-disruption.md). Neither model agreement nor source availability changes
these limitations. The matrix retains them as actionable gaps rather than a blanket wait.

## Attempt forecasting and authorization boundary

`AttemptLine.maximum_attempts()` multiplies cases × trials × calls-per-trial × orderings ×
(1 + extra attempts per call). Include every drafting, calibration, comparator, candidate,
fault and judge call as appropriate. Two model reviewers count twice. The planner cannot
discover an omitted stage or prove that a declared workload is complete; freeze the actual
workflow and review its mapping before using the forecast. A retry reservation is not retry
permission. Zero-call baselines need no provider line and should be recorded separately.

`forecast_attempts` revalidates objects, sums all agents against one snapshot per provider,
and refuses duplicate schedule lines/snapshots. Missing providers, unsupported agent/purpose
scope and plans exceeding maximum-minus-consumed add blockers. There is no cross-provider
transfer, new allowance or automatic quota reset. Snapshots must come from the authoritative
ledger at execution; the offline function does not authenticate them or check freshness.

Even when `fits_declared_snapshots` is true, `dispatch_allowed` and `release_allowed` remain
false. A diagnostic forecast cannot establish source-export permission, Free billing status,
review acceptance, live grant roles, or future quota. Runtime reservation remains the existing
durable attempt-control mechanism. Scope must actually permit any proposed evaluator role.

Planning status carried forward: Gemini0/180, Groq9/12consumed with three invented-smoke
attempts remaining. This batch makes zero provider calls and does not reinterpret Groq smoke
permission as domain judging. No new executable Gemini grant or authority snapshot is fabricated.

## Reproduce

Use the canonical matrix pin recorded in the PR acceptance evidence, not a new pin learned
from a substituted file. The five profile pins are embedded in that matrix. From a locked
checkout with all workspace packages installed:

```powershell
python -m agent_harness.evaluation_plan_cli matrix `
  --matrix docs/evaluation/evidence-paths-v1.json --matrix-sha256 <accepted-matrix-pin> `
  --profiles docs/evaluation/profiles

python -m agent_harness.evaluation_plan_cli forecast `
  --plan <private-plan.json> --plan-sha256 <separate-plan-pin> `
  --snapshots <private-snapshots.json> --snapshots-sha256 <separate-snapshot-bundle-pin>

python -m pytest -q tests/test_evaluation_planning.py tests/test_olist_evaluation_oracle.py `
  tests/test_evaluation_standards.py tests/test_olist_policy.py
```

The CLI rejects duplicate JSON keys, inputs above1MB, pin mismatches and invalid contracts.
It emits a generic error without echoing malformed source content. Exit0means inventory
coverage or fit to declared snapshots only. Forecast cap/scope blockers and invalid input
exit1. Raw narrative text, labels and credentials do not belong in planning files.

## Next integration and remaining boundaries

Implement measured evaluator qualification and a separate accepted evidence policy before
any promotion path. Prepare Olist text/reference applicability and actual workflow call
forecasts next; research specific external semantic references for CFPB/Prior Auth and audit
CUAD field mapping. Compare source groups and sample-size targets to budget before capture.
Model calibration and source acquisition have not run in this batch. Legacy review gates,
profiles, issue statuses, reviewer packets, allowance databases and past captures are unchanged.

Tests cover mechanics, not domain qualification. Required exact-head CI and postmerge results
are recorded on the delivery PR when completed. [Build Book Entry59](../BUILD_BOOK.md#entry-59--make-evidence-and-attempt-plans-executable-without-granting-approval)
records construction and actual failures; this chapter describes current implementation.
