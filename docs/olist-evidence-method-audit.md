# Olist v2 evidence-method coverage audit

Updated 2026-11-05, Africa/Lagos. Inspected `codex/olist-release-method-decision` from
verified main `6ca379d` (#138). Coverage: the new module/tests, actual development-readiness
projection and an interrupted local baseline capture. No completed qualification or deployment.

## Accepted decision, preserved history

The owner replied **“Approve this Olist v2 evidence-method design”** to the
[proposal](olist-release-evidence-method-v2-proposal.md). Its original
[proposal data](data/olist-evidence-method-design-proposal-v2.json) stays unchanged as
history. The separate [acceptance receipt](data/olist-v2-method-design-acceptance-v1.json)
records the exact reply, proposal pin and limited scope. Recording time is not an
authenticated time of the owner's action.

All eight fields/slices and existing planning targets remain. The matrix permits
independently executed checks for objective claims and applicable external references,
validated constructions or separately qualified evaluators for semantic claims. Approval
covers design/implementation only: no cohort, statistical protocol, baseline, threshold,
provider call or release. Legacy `Review` / `_reviewed` behavior is unchanged.

## Interface and execution

[evidence_methods.py](../projects/olist-support/src/olist_support/evidence_methods.py)
is a pure library. `audit_methods` receives a pinned Olist profile, explicit cases,
claims/scopes, actual acceptance bytes, trusted pins and an aware clock. It reads no source
files, queries no database, calls no model and authenticates no source content or identity.

The caller must obtain `trusted_scope_pins` from a separate trusted control plane and
`verified_claim_pins` from domain readers that actually checked the artifacts.
**Never build either trusted set from the submitted bundle's own claims.** A URL or hash
alone establishes no trust. A future endpoint must keep these inputs outside user control.
There is currently no public endpoint or automatic qualification-grant registry.

1. Revalidate every contract, including unchecked `model_copy` updates. Bind the complete
   original Olist profile and raw receipt to separately trusted pins. Removing requirements
   or reformatting the receipt refuses the audit.
2. Expand fields into claim parts. Amount needs `requested_meaning` and `arithmetic`;
   action needs `eligibility` and `observed_action`; review reason needs failed predicates
   and semantic applicability. Ten parts per normal case, eleven for `crash_restart`.
3. Reject duplicate/unscheduled claims; another support row cannot vote away contradiction.
   Connect identical inputs and all declared source keys transitively before counting groups
   and checking split leakage. Counts are declared groups, not authenticated independence.
   Every required slice must exist in holdout; development evidence cannot qualify.
4. Match each full canonical claim hash against externally admitted proof pins. It includes
   disposition and evidence, so changing a failed claim to supported loses admission.
   Also require an externally admitted qualification scope with matching field/part,
   slices, exact input/reference/source/evaluator hashes and valid observation/audit times.
   Unknown, contradicted, future and expired claims block.
5. For `qualified_model`, require the actual separate dataset/protocol/study. Recompute
   `qualification_report` and compare its hash, criteria, exact Olist `field.part`,
   evaluator and slices. Qualification must finish before the scope grant. A report pointer,
   different field or failed report is insufficient.
6. Return counts and sorted blockers. Even full invented admitted coverage leaves
   `qualification_allowed`, `human_review_supplied` and `release_allowed` false. This is
   method coverage after domain verification, not a full statistical/release audit.

Example: payment100.00SIM plus requested refund25.00SIM needs a supported distinction
between those roles. Decimal arithmetic can verify2500minor units and the partial-refund
policy; it cannot establish which phrase the customer requested. Removing just the
`requested_meaning` claim blocks coverage despite passing arithmetic. Positive grants and
model reports in tests are invented logic fixtures with permissive tiny-sample limits,
not real Olist qualifications.

## Actual readiness and remaining integration

The eighteen current development scenarios require **181 claim parts over five dependent
groups**. No qualification scope/proof is admitted. The
[readiness aggregate](data/olist-method-readiness-v2.json) reports zero admitted claims and
false coverage. All eight holdout slices remain missing because every case is development.
Accepted controlled meanings stay accepted only for development.

A full v2 path must still compose frozen statistical/sampling requirements, independently
supported references, complete candidate/baseline schedules, critical-effect checks,
accounting/performance and host recovery evidence, then separate release authorization.
No v2 production-release command is enabled here. Historical studies retain original rules.

## Interrupted baseline: observations and honest denominators

The baseline plan froze executable source `6ca379d` before this new module existed. It
scheduled54rules plus54always-review trials and54absent candidate rows. `DenyModels` and
the mock composition forbid model use; no candidate/provider was run.

The rules journal contains54terminal rows: **27 independently reread service reports,
one setup error and26 later coordinator-abort placeholders**. `worker_cleanup_error`
also represents an abort sentinel; it does not prove26 physical cleanup failures.
The fence stops on missing checked state. No `baseline.json` sealed; always-review never
started. There is no completed108-row comparison or verified whole-run cleanup receipt.

The27observed prefix rows all report review, all fail whole-service correctness and all
pass observed routing/state safety. The remaining27rules rows have unknown service quality/
safety. Execution order/interruption selects this prefix; it is not representative accuracy
or baseline approval. The [interruption aggregate](data/olist-service-baseline-interruption-v1.json)
retains those denominators. No model-quality comparison can be inferred.

At diagnosis Docker's engine pipe was unavailable and no runner remained. The generic
setup code does not preserve its low-level exception: **root cause is unestablished**.
Do not infer that source edits or disk pressure caused it. Preserve the private run and
file inventory; no retry/resume or synthetic completion occurs. Before a separately frozen
new capture, verify engine/database readiness and persist parent stderr, then require
strict sealing/readback and owned-resource cleanup.

Private diagnosis/coverage:
`D:/document/.cache/production-agents/olist/evidence-method-readiness-2026-11-05-v2`.
Original capture: `D:/document/.cache/production-agents/olist/service-development-baselines-2026-11-05-v1`.
Read-only ledger stays447/614, zero unsettled and one original stop. No key load, call,
slot reuse, allowance change or stop removal.

## Verification and discussion

Run the locked Python with `-m pytest tests/test_olist_evidence_methods.py
tests/test_evaluator_qualification.py tests/test_evaluation_standards.py -q` (one command).
The focused84checks pass: amount-role gap, development scope, external trust, hash changes,
contradiction/duplicates, expiry/future times, transitive leakage, exact acceptance,
unchanged retrospective-review refusal and recomputed exact-field model qualification.
Full hosted delivery evidence is recorded separately on the PR and main.

Interview exercise: an evaluator supplies perfectly consistent hashes and says every field
passed. Which independent component admits its scope/proof pins? Explain why hashing
preserves integrity without proving semantic truth; why arithmetic differs from requested
meaning; why state safety can pass while a decision is wrong; and why an interrupted safe
prefix cannot erase unknown later outcomes. [Build Book Entry87](../BUILD_BOOK.md#entry-87--measure-service-baselines-before-accepting-a-replacement-evidence-policy)
records construction and failures as they happened.
