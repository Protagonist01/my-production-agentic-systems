# Prior authorization evidence assessment

Accepted scope, updated 2026-10-23. P1â€“P3 are merged/verified through [PR #92](https://github.com/Protagonist01/my-production-agentic-systems/pull/92), with pinned source preparation and bounded fresh Gemini assessment. [Source, operation and evaluation evidence](prior-auth-evidence.md) records the provisional cohort and results. The user-selected [P4/P5 document workflow and reviewer desk](prior-auth-review.md) is merged and verified through PR #93. P6 clinical/domain release remains pending.

## Application direction

The target is an educational evidence-assessment application for selected policies, with reviewed criteria, isolated labels and durable document waits. P1â€“P3 currently deliver source preparation, provisional labels and criterion checks; P4/P5 add durable waits and a protected reviewer desk in PR #93.

The P4/P5 durable workflow uses LangGraph and the merged H1 integration. The delivered P1â€“P3 slice provides source/evaluation CLIs and an injected shared model gateway. PR #93 implements the API/operator workflow, scoped reviewer access and durable waits.

Redacted note + selected policy â†’ retrieval â†’ met/not_met/insufficient criterion assessments with evidence â†’ deterministic aggregation â†’ recommendation/review/request information â†’ durable document wait and affected-criterion reassessment.

## Data and boundary

Selected versioned coverage-policy sources and illustrative transcription examples. Verify content/use conditions and code types. Independent note-policy labels and counterfactual edits remain distinct.

Recommendation and qualified review only. There is no denial or real authorization tool. Span existence alone does not prove criterion support; missing/conflicting information routes to information request or review. Domain-review availability and label limitations are explicit.

Each importer produces provenance/checksum/use notes and validated agent-visible data. Independent expected labels and hidden outcomes live in scorer-only storage. Development/regression/holdout sets are versioned and related records remain grouped. Original, hybrid and synthetic/adversarial results are separate.

## Implementation tasks

### P1: Select suitable policies and verify source/use and reviewer constraints

Priority: P1; provisional size M; prerequisites: none. Status: Done, verified #92 merge.

Choose checkable coverage policies and transcription examples; record effective dates, code-content restrictions, illustrative status and domain review availability.

Acceptance evidence:

- [x] CMS NCD 240.4 v3 initial-CPAP scope, source hashes, synthetic-record provenance and use limits are documented.
- [x] No qualified review has occurred; user-approved labels and criterion wording remain AI-provisional.
- [x] Diagnosis versus procedure/equipment-code requirements are explicit; code-only claims and catalog validation are outside this slice.

### P2: Build redacted spans and independent note-policy labels

Priority: P1; provisional size L; prerequisites: P1, H5. Status: Done, verified #92 merge.

Segment illustrative notes with stable offsets; label met/not_met/insufficient and supporting spans, plus marked counterfactual pairs.

Acceptance evidence:

- [x] Published illustrative records, edits and invented edges are identified separately; related records stay in one split.
- [x] Expected states/dispositions are authored in a separate evaluator packet and checked for consistency, without calling the production aggregator. They are not clinically adjudicated labels.
- [x] Exact Unicode offsets, explicit redaction maps, closed note input and detached model input have focused checks.

### P3: Implement retrieval, criterion assessment and supporting-evidence checks

Priority: P1; provisional size M; prerequisites: P2, H10. Status: Done, verified #92 merge.

Evaluate selected policy criteria with structured evidence; validate both span integrity and criterion support, code types and policy version.

Acceptance evidence:

- [x] Exact citations plus narrow support/negation/unit checks reject unsupported met claims.
- [x] Missing/stale policy or conflicting evidence routes to qualified review; no approval disposition exists.
- [x] Retrieval counts, gateway failures, typed assessment errors and quote-mapping errors are recorded separately. The first frozen holdout matched 6/6 provisional case labels and 42/42 criterion labels over 42 fresh requests.

### P4: Implement recommendation-only policy flow and durable document waits

Priority: P1; provisional size M; prerequisites: P3, F4. Status: Done, merged/verified PR #93.

Aggregate criteria, request information or route to qualified review; persist exact policy/version/document state and re-evaluate affected criteria.

Acceptance evidence:

- [x] There is no deny_request or real authorization tool/API route.
- [x] Document arrivals/timeouts and restarts resume without duplicate queue effects.
- [x] Policy version change invalidates obsolete candidate decisions.

### P5: Build reviewer interface and protected evidence access

Priority: P1; provisional size M; prerequisites: P4, H8. Status: Done, merged/verified PR #93.

Show criterion/evidence/rationale table, missing information, review events and policy provenance under tenant/role access.

Acceptance evidence:

- [x] Only redacted views are model-visible; identifier canaries do not leak to traces.
- [x] Unauthorized reviewer cannot inspect/change another case.
- [x] Reviewer can identify uncertainty, conflicts and pending document waits.

### P6: Release criterion, recommendation-risk and abstention evidence

Priority: P1; provisional size M; prerequisites: P5, O8. Status: Backlog.

Evaluate incorrect approval recommendations with both denominators, criterion support, appropriate routing and required-information behavior.

Acceptance evidence:

- [ ] Incorrect recommendations/all recommendations and /non-approvable cases are both reported.
- [ ] Illustrative versus edited examples and clinical-label limitations remain explicit.
- [ ] Fresh results, policy manifests, privacy/injection faults and runbook meet gates.


## Evaluation and release

Criterion assessment and supporting evidence correctness; incorrect approval recommendations / all approval recommendations and / non-approvable cases; abstention/review appropriateness; missing-information handling.

Gate: No denial or real authorization tool; incorrect approval recommendation measured; supported evidence checked; missing information handled; illustrative and counterfactual inputs reported separately.

Use the shared strict-replay/fresh-evaluation/monitoring boundaries. Release requires merged implementation, independent case/state checks, complete fresh evidence and required fault cases. No critical observed violation can be hidden by improved averages.

[Architecture](README.md) Â· [Delivery plan](project-management.md) Â· [Backlog](backlog.json)
