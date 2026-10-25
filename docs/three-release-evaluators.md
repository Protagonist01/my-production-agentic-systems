# Preparing Olist, CFPB and Revenue release evaluations

Inspected 2026-10-24 on unmerged `codex/three-release-evaluators`, from merged main `b915f1b`
(#102). The user explicitly authorized preparing #33, #38 and #45 together, retaining the
#33 dependency gate for downstream release acceptance. This batch implements study assembly
and fixed-denominator reports. It does not finish three release issues or authorize new
provider calls, sampling, label changes or deployment. [Entry 47](../BUILD_BOOK.md#entry-47--preparing-three-release-evaluators-together)
records construction and actual checks as they occur.

## Evidence boundaries

| Issue | Implemented preparation | Still required |
| --- | --- | --- |
| #33 Olist | Shared StandardStudy projection from H10 rows; domain wrapper rechecks receipts/private observations and original regression split. | Full OS crash/restart evidence, independent/representative review, approved baselines/limits, known costs and authorized final-candidate fresh study. |
| #38 CFPB | Actual Decision path validation, product/product-issue macro-F1, per-class counts, risk routing/review burden, incomplete trials, split/source breakdown. | Domain H10 runtime/state adapter, complete privacy/durable-review/fault evidence, qualified labels, reviewed calibration/limits and fresh release study after #33. |
| #45 Revenue | Separate original-span and SIM-billing reports, per-category/treatment breakdown, discrepancy recall and benign false alarms. | Domain H10 adapter, validated numeric-term/state/auth/compensation/recovery evidence, independent engine/catalog ablations, qualified review and fresh release study after #33. |

The domain reports always return `release_allowed: false`. They measure supplied observations;
they do not authenticate their origin. Freeze and independently review plan bytes before
capture, then retain original observed outputs with their candidate/code/scorer/source pins.
The returned canonical `plan_sha256` identifies the declaration used; computing it does not
prove it was frozen before outputs. These reports cannot be substituted for H10 receipts or
the [bound methodology audit](evaluation-standards.md).

## Olist: assemble without inventing evidence

Call [`assemble_olist_study`](../projects/olist-support/src/olist_support/h10_study.py) with
the loaded manifest, profile, protocol, supplied StandardCases and independent external pins
for candidate and baseline roots. Use the executing frozen packages for both readers. The
wrapper requires all eight Olist fields and exact original development/regression/holdout
splits before reading observations. It calls `read_olist_evidence` for both artifacts, which
checks H10 receipts, complete usage and saved SQL-state observations after database cleanup.

This convenience wrapper requires both source inventories to match the installed runtime;
it can compare compatible route/configuration variants, but cannot recompute an older code
baseline using changed installed packages. Mixed-code comparisons need each artifact read
in its own frozen environment and a separately reviewed interchange path; that operational
workflow remains future work. The shared projector accepts already verified evidence and
does not replace those domain-specific readers.

The shared [`assemble_study`](../harness/src/agent_harness/evaluation_study.py) checks compatible
population, evaluator, policy, environment and batch pins. It projects actual result outcome,
independent field scores, baseline correctness, usage and sealed parent timing. Missing
reports or nonbinary/scorer-error fields cannot be fabricated. Cases/slices/families/reviews
come from explicit supplied metadata; none is authored automatically. It runs `verify_binding`
before returning. Run `audit_study` separately to see design/review/coverage/limit blockers;
binding is not methodology qualification, and qualification alone is not deployment approval.

Example flow, with already reviewed private objects and paths:

```python
study = assemble_olist_study(
    profile, protocol, cases, loaded,
    baseline_root=baseline_root,
    baseline_evidence_sha256=baseline_pin,
    baseline_candidate_sha256=baseline_spec_pin,
    candidate_root=candidate_root,
    candidate_evidence_sha256=candidate_pin,
    candidate_sha256=candidate_spec_pin,
    required_case_ids=required_ids,
)
audit = audit_study(profile, protocol, study, now=now)
```

These are existing-artifact reads, not generation calls. Historical recordings stay unchanged;
unknown historical timing remains None. Old recordings without H10 journals cannot be imported
as new H10 executions. Mock recordings remain mock even when projection succeeds.

## CFPB: quality and routing have separate denominators

[`EvaluationPlan`](../projects/cfpb-triage/src/cfpb_triage/release_evaluation.py) contains private
reference cases, taxonomy/router/source bindings and the fixed trial inventory. `Observation`
contains the actual Decision from execution, not cached per-route predictions replayed into a
different policy. `evaluate(plan, observations)` rejects duplicate/unexpected rows, changed
source/policy identities and source groups crossing splits.

The independent route oracle validates exact narrative evidence, route order, threshold/risk
stopping and failure stopping; it does not call production `route` or fit thresholds. Invalid
decisions remain unresolved. A timeout routed to review earns no successful risk-routing
credit. Claimed classification counts stay visible even when the route is invalid; a high-risk
auto-classification cannot disappear from missed-review counts. Selective error uses all
claimed classifications, including invalid claims, as its denominator.
Priority and ambiguity agreement counts use the full scheduled denominator separately.

Product and product-issue pair macro-F1 includes every scheduled trial; absent/invalid/failed
predictions produce false negatives. Classes are the union of references and valid emitted
labels, including predictions on reviewed cases; this is classification quality across the
schedule, not autonomous coverage. Per-class support/predicted/true-positive/F1 exposes minority
classes. Pair labels use a JSON tuple encoding so punctuation cannot merge distinct pairs.
Report review fraction, eligible/required-review counts, unnecessary/missed review and elevated
review recall separately. Empty denominators remain None; repeating a case does not create
another source group. Consumer-selected categories and AI risk judgments remain reference
labels, not adjudicated harm truth. Counts of qualified-review declarations do not authenticate
reviewer identity or establish timing; the complete audit still owns those gates.

```python
report = evaluate(frozen_plan, observed_decisions)
```

Keep this private: inputs contain narratives/labels and output class names can be sensitive
in other settings. No model text is sent to a provider by report generation.

## Revenue: do not blend original extraction with SIM arithmetic

[`extraction_report`](../projects/revenue-integrity/src/revenue_integrity/release_evaluation.py)
takes an ExtractionPlan with original inputs/published targets and observed ExtractionClaims.
It validates reference spans against unchanged context and rejects cross-split document
families. Literal predicted spans must match context and may not overlap/duplicate. Exact-span
true positives match both Unicode offset and full text. Missing/failed trials retain all
reference spans in recall's denominator; all submitted spans, including invalid ones, remain
in precision's denominator. No-answer cases have a separate denominator and only explicit
unsupported abstention can pass; uncertain/failure is unresolved. Zero submitted spans means
undefined precision, not perfect precision. This does not score partial overlap, legal meaning
or extracted prices. Publisher annotations retain their documented scope and limitations.
Supported/unsupported-abstained/uncertain counts stay separate; failed uncertainty is still
unresolved. Missing, failed and invalid diagnostics can overlap and should not be summed as
disjoint outcomes.

`billing_report` accepts a separate BillingPlan with literal BillingExpected references. It
does not call the production reconciler to create expected answers. It validates amount/
disposition consistency, issued amount and result arithmetic, then reports exact amount/reason
correctness separately from discrepancy-direction detection. Case recall gives equal weight
to each discrepancy trial; SIM amount-weighted recall weights by absolute reference delta.
For example, detecting a 100-SIM-cent discrepancy while missing a 1,000-cent discrepancy is
1/2 case recall and 100/1,100 amount recall. These invented numbers teach the calculation;
they are not measured financial outcomes. Report benign false alarms and required/optional
review separately, including unresolved trials in the scheduled population. No real currency
or recovered revenue is inferred.
Amount and reason correctness are visible separately as well as jointly.

```python
original_report = extraction_report(original_plan, observed_claims)
sim_report = billing_report(sim_plan, observed_reconciliations)
```

The reports never read or mutate invoice ledgers. Authorization, exact state, compensation,
independent-engine agreement and crash recovery need separately observed evidence.

## Verify the implementation

```powershell
uv run --locked --all-packages python -m pytest tests/test_evaluation_study.py tests/test_cfpb_release_evaluation.py tests/test_revenue_release_evaluation.py -q
uv run --locked --all-packages python -m pytest tests/integration/test_olist_h10.py -k refund -o "addopts=--strict-config --strict-markers" -q
python dev.py check
```

These tests use invented inputs and explicit mock transports. The SQL test uses the same
mock artifact in baseline/candidate slots only to verify read-back and projection; it is not
an independent comparison or release study. The methodology audit remains blocked on missing
review/coverage/limits. Test results and final CI acceptance are recorded on the batch PR.

Interview exercise: explain why always-review can have no missed-review risk yet fail useful
completion; why missing predictions reduce recall even with no false-positive spans; and why
an exact billing-direction detection can still have the wrong amount. Trace how private
labels stay outside agent input, and identify the additional evidence needed for release.

Local verification completed: full locked check1,069tests718.09seconds,156typed sources,
236formatted Python files plus lint/import/lock checks. That run began before final
count-only report additions; final focused27tests33.09seconds, lint/types/format and rebuilt
packages verify those additions. Olist real SQL/H10/projection1passed201.84seconds,4unchanged
scenarios deselected locally; initial Docker-closed setup failure retained (zero dispatches).
Final installed proof matched63harness/36Olist/24CFPB/26Revenue resources, all four APIs,
provider SDKs/unrelated verticals absent, networking denied, six replay calls/zero provider.
Six package pairs built; locked audit clean. Historical inventory/report/source/draft pins
unchanged; publication17files excludes configured credentials and24source identifiers.
124relative documentation links resolve and changed JSON parses. Require final committed-head
hosted full matrix/110Postgres checks; no completed release study is inferred.

## Partial dispatch and process-death preparation

The [adapter and crash walkthrough](domain-dispatch-and-crash.md) covers shared H10 mock recording, CFPB classifier and Revenue extractor adapters, private read-back checks and the zero-model Olist SIM process-death drill. Missing domain evidence remains a scorer error; #33/#38/#45 remain open and release-blocked. Main after #103 failed one timing-tamper test; this batch corrects the test seal without weakening production checks. Final acceptance is recorded on the review PR.

## Deterministic comparison preparation

The [executed baseline walkthrough](deterministic-baselines.md) traces zero-call Olist rules/review, CFPB review and Revenue abstention through separate sealed manifests, owned trials and independent domain read-back. Study comparison accepts the verified comparator without changing fresh-candidate receipts or release approval. #33/#38/#45 remain open.
