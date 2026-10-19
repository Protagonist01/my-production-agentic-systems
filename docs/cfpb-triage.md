# CFPB complaint triage

Updated 2026-10-18. C1 source preparation is implemented on an unmerged branch; no application or classification evaluation result exists yet. The user selected O2 + C1 in parallel and the complete September 2023–March 2024 archive cohort. [Source evidence and operations](data/cfpb-source.md) · [Code walkthrough](code-study-cfpb.md).

## Delivered application

A second framework and classification vertical on published complaints, with calibrated routing and risk review.

Framework direction: Pydantic AI. Verify current integrations and pin tested versions under H1 before implementation. The application includes a usable API/operator workflow, scoped access, traces and an operational guide.

Narrative → typed classification/evidence → calibrated cheap/strong route or review → enqueue-only review queue → scoped API and monitoring.

## Data and boundary

Published CFPB narratives and metadata with a pinned snapshot and taxonomy version. Use temporal/grouped holdout and document masking, missingness and population limitations.

Consumer-selected product/issue labels are reference targets, hidden from the agent. Independent reviewers label high-risk and ambiguous cases; classification correctness is not established customer harm reduction.

Each importer produces provenance/checksum/use notes and validated agent-visible data. Independent expected labels and hidden outcomes live in scorer-only storage. Development/regression/holdout sets are versioned and related records remain grouped. Original, hybrid and synthetic/adversarial results are separate.

## Implementation tasks

### C1: Import CFPB complaints and build a label-isolated temporal split

Priority: P1; provisional size M; prerequisites: F2, H5. Status: Review in [PR #82](https://github.com/Protagonist01/my-production-agentic-systems/pull/82).

Snapshot published narratives/metadata with source taxonomy versions. Store consumer-selected product/issue labels only in evaluation tables.

Acceptance evidence:

- [ ] Agent input excludes targets and other answer-revealing metadata.
- [ ] Temporal/grouped holdout and category changes are documented.
- [ ] Manifest records missing narratives, masking patterns and consumer-label limitations.

### C2: Review risk/ambiguity labels and establish deterministic baselines

Priority: P1; provisional size M; prerequisites: C1. Status: Backlog.

Write labeling rules, blind-label risk/ambiguous examples in batches and implement majority/rules baselines.

Acceptance evidence:

- [ ] Labels include reviewer/guideline/version evidence and disagreements.
- [ ] Risk labels are not derived from candidate predictions.
- [ ] Baseline results and slice denominators are published before tuning.

### C3: Implement Pydantic AI classifier and calibrated routing

Priority: P1; provisional size M; prerequisites: C2, H10. Status: Backlog.

Return typed product/issue/priority and evidence; calibrate routing/abstention on a development-only set and compare cheap-first with always-strong.

Acceptance evidence:

- [ ] Invalid taxonomy or budget failure routes safely with audit evidence.
- [ ] Coverage/error and high-risk recall are reported at a declared review fraction.
- [ ] Router thresholds never fit the final holdout.

### C4: Integrate scoped review, API, traces and drift monitoring

Priority: P1; provisional size M; prerequisites: C3, H8. Status: Backlog.

Expose classification/review workflow with enqueue-only tools; monitor input/output taxonomy mix, masked text and model/provider changes.

Acceptance evidence:

- [ ] Tenant boundaries and no-write scopes are enforced in tools.
- [ ] Category/length/language shifts trigger documented diagnostic outputs.
- [ ] API surfaces decision, uncertainty and review evidence accurately.

### C5: Evaluate routing tradeoffs and release the CFPB vertical

Priority: P1; provisional size M; prerequisites: C4, O8. Status: Backlog.

Run held-out classification/risk results, provider/injection faults and repeated-trial subset; publish model card, runbook and resource comparison.

Acceptance evidence:

- [ ] Macro-F1, minority slices and risk recall/review-load tradeoff are explicit.
- [ ] No label leakage or unsupported population/harm claim appears in the report.
- [ ] Fresh evidence and required-case gates pass; observed failures remain documented.


## Evaluation and release

Macro-F1 and minority-class results; high-risk recall at declared review load; coverage/error tradeoff; cheap-first versus always-strong cost and quality; fault outcomes.

Gate: No target-category leakage; temporal/grouped holdout; macro-F1 and high-risk recall at declared review load; routing compared with rules and always-strong baselines.

Use the shared strict-replay/fresh-evaluation/monitoring boundaries. Release requires merged implementation, independent case/state checks, complete fresh evidence and required fault cases. No critical observed violation can be hidden by improved averages.

[Architecture](README.md) · [Delivery plan](project-management.md) · [Backlog](backlog.json)
