# Evaluation qualification: design through release

Inspected base `418c9179321ca287dd392b700ecb138c92ff39d4`; unmerged branch
`codex/strong-evaluation-standards`, 2026-10-24. Scope: new shared qualification contracts,
audit, evidence binding and CLI composition; five domain profiles and historical inventory.
Source data, provider output, clinical/legal correctness and production behavior are outside
this inspection. [Build Book Entry41](../BUILD_BOOK.md#entry-41--separating-pilot-success-from-evaluation-qualification)
records the decision and actual test history. [Operator standards](evaluation-standards.md)
describe policies and remaining review requirements.

## Trace an invented study

1. [StandardProfile/Protocol/Study](../harness/src/agent_harness/evaluation_standards.py)
   separates domain-required checks from approved numerical limits and observations. A protocol
   is pinned before the study; field floors, review-error limits, sample-size rationale,
   baseline review and threshold review have no permissive release defaults. A profile sets
   qualified review and simulation claims without importing a domain implementation.
2. `audit_study` serializes/revalidates all inputs, so a `model_copy(update=...)` cannot bypass
   identity/schema validation. It compares canonical profile/protocol pins, reviews and capture
   time order before scoring. AI-provisional and retrospective label records remain rejected
   for a pre-output blind study; qualified domains require qualified review explicitly.
3. `text_fingerprint` normalizes Unicode compatibility characters, case and whitespace. Source
   independence keys and assigned language families are separate checks. Text normalization
   detects formatting duplicates; assigning correct families and finding semantic duplicates
   remains trusted reviewer work. The algorithm does not estimate similarity with another LLM.
4. The audit merges connected holdout key sets before counting groups. For example `{orderA,
   parentX}` and `{orderB,parentX}` are one component, even with distinct case IDs. `_measure`
   walks all scheduled case/trial pairs. A missing row contributes to denominator and failure,
   never to success. An eligible case sent to review and a required-review case automatically
   completed use distinct denominators. Field successes use the full scheduled denominator.
5. Reuse `scorecard_stats.binomial_bounds` for the proportion of holdout components with any
   failed/missing repetition. Three passes on each of two groups still means two observations;
   the95%upper bound at zero observed group failures exceeds0.8. This is a conditional interval,
   not proof that chosen groups are independent or representative. Approved group floors,
   per-slice coverage and uncertainty ceiling are all required.
6. [read_audit/CLI main](../harness/src/agent_harness/evaluation_audit.py) loads private files
   and requires separately supplied canonical pins before exclusive output creation. Reports
   omit raw case text, source identifiers and review-reference content. Exit0 means methodology
   qualified; its `release_allowed` remains false. A pin mismatch or an existing output fails
   without altering old files. Module invocation denies network using the existing audit hook.
7. [verify_binding](../harness/src/agent_harness/evaluation_binding.py) connects this study to
   H10's already verified manifest/receipts. It verifies dataset/scorer/baseline/candidate pins,
   capture times, exact inputs, source groups, source kinds, required-review labels, agent and
   trial identities. H10 required cases must remain critical. Field results must equal binary
   scores in the sealed domain report; tokens/cost must equal its usage. A human-approved
   summary cannot replace actual H10 results. The ordinary audit trusts its domain adapter;
   this binding supplies the additional independent-evidence cross-check for release.
8. [release_cli.main](../harness/src/agent_harness/release_cli.py) composes that result with
   the original H10 decision. Without all required audit inputs, it adds
   `evaluation:evaluation_standard_inputs_missing`. A supplied but mismatched study fails
   before output creation. It writes an audit sidecar whose exact bytes are hashed into
   `ReleaseDecision.evaluation_audit_sha256`. Original H10 blockers remain; qualification
   cannot clear them. The direct `release_candidate` function still has its explicit
   evidence-gate-only meaning and does not authorize deployment.

## Domain ownership and limits

Profiles under [evaluation/profiles](evaluation/profiles) declare required field/slice checks.
The [readiness inventory](evaluation/readiness.json) pins nine historical evidence files and
records per-agent limits. It is metadata reviewed from those files, not five standard studies
or new provider calls. None of the current domain pilot reports is silently converted into an
H10 journal. New domain field scorers/adapters and approved protocols remain work to complete.

The Boolean fields are acceptance checks, not raw continuous measurements. In particular,
Revenue span-precision/recall checks require independently specified acceptance logic and
raw span measurements in the domain report. Prior-auth `no_unsupported_met` means a pass when
no unsupported-met claim occurred. A high pass fraction is not clinical or legal validation.
Supply has simulation-only claim scope and requires reviewed sensitivity evidence.

**Design limitations:** hashes check correspondence, not reviewer identity or honest source
selection. Source keys, language families, review qualifications, rationale references and
ordinary audit row scores are trusted declarations. H10 binding verifies available sealed
evidence but does not prove latency metadata or domain scorers match real-world truth. There
is no semantic duplicate detector, signature infrastructure, production telemetry audit or
clinical reviewer in this change. Unknown cost remains unknown; no Free attestation overrides
the existing usage completeness gate. Raw private datasets and original customer text remain
outside Git. No production effect or deployment follows from a positive methodology audit.

## Tests and interview exercises

[Audit tests](../tests/test_evaluation_standards.py) use invented inputs for disjoint/group/
text/family leakage, retrospective/qualified reviews, missing rows/fields, unsafe and newly
failing trials, unknown accounting, review-error denominators, uncertainty and exclusive CLI
output. They validate all five profiles and historical evidence byte pins.
[Binding tests](../tests/test_evaluation_binding.py) capture the existing invented mock H10
workflow and reject changed agent/input/group/criticality/field/usage/population/pins. The
toy is not a domain study and cannot qualify a release. [Existing CLI tests](../tests/test_release_cli.py)
also verify missing-audit refusal and exact sidecar digest while retaining mock-evidence
refusal and untouched baseline approvals. Final suite evidence is recorded in the PR.

Explain why12cases/36repetitions do not imply36independent observations. Trace a required-review
case that gets completed: expected-disposition checking prevents a supplied `correct=true`
from rescuing it. Explain why a successful audit from yesterday's candidate cannot qualify
today's changed candidate. Finally, identify which claims still need a real qualified reviewer
even after every software test passes.

The Prior Auth profile sets `requires_eligible_cases=false`: clinical assistance can require
review on every case without inventing autonomous treatment/authorization. Eligibility and
required-review are separate case fields, both bound to H10 labels. Other profiles require
eligible holdout cases, and undefined rate denominators remain explicit rather than zero.

Verified local stable-source check:993tests passed in348.84seconds,142typed sources,
213formatted Python files, both import contracts/lock/lint. Six package pairs built, audit
clean; separate installed60harness/27Olist resource-byte checks and network-denied replay
passed with zero provider calls. Existing event-loop/cache warnings remain non-failing.
Hosted final-head evidence is recorded on the PR rather than asserted before execution.
