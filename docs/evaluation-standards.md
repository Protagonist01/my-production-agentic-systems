# Evaluation standards for all five agents

Status: implementation/review branch based on merged main `418c917`; 2026-10-24.
These standards qualify evaluation methodology in addition to H10's evidence gate.
They do not approve a deployment, clinical decision, financial effect or freight operation.
The user requested stronger Olist evaluation and the same discipline for all five agents.
The old pilot thresholds are not promoted to production thresholds.

## Common requirements

1. Freeze dataset, source selection, input projection, independent labels, policy, scorer,
   baseline, execution conditions and risk-based thresholds before candidate output. Review
   records identify a reviewer, reference and time. AI labels and acceptance after results
   remain distinct from blind review. Use qualified domain review where the profile requires it.
2. Split correlated source records, parent/edited cases, document families and language
   templates together. Development fits prompts/calibration; regression checks known failures;
   a fresh holdout tests unseen source groups and wording. Do not recycle an evaluated holdout
   as untouched. Normalized exact-text checks do not replace semantic duplicate review.
3. Cover each agent's declared failure slices in holdout. A large set of template variants
   cannot substitute for distinct scenarios. Specify a minimum independent group count overall
   and per slice, with a sampling/sample-size rationale and uncertainty tolerance approved
   before evaluation. There is no universal sample size or accuracy threshold. Prior Auth is
   assistive: it does not require autonomous clinical actions. Its profile allows zero
   eligible-autonomy cases and leaves the unnecessary-review rate undefined, while requiring
   correct qualified review and accurate evidence assessment.
4. Schedule every case/trial pair in advance. Missing, failed and unresolved attempts remain
   in denominators. Repetitions measure stability; case and connected source-group counts
   measure coverage. Correctness includes required field checks and the expected disposition.
5. Keep zero unsafe effects and critical-case failures as hard blockers, regardless of average
   score. A previously passing paired baseline trial may not silently regress. Separate
   unnecessary review among eligible cases from missed review among required-review cases.
   The former 75% aggregate Olist pilot ceiling is not a cross-agent objective.
6. Report partition and holdout-slice scores, each field's numerator/denominator, all-repetition
   case success, paired regressions, missing results, latency, tokens and cost unknowns.
   Unknown cost is not zero, including a confirmed Free project. Latency uses the nearest-rank
   p95 of all scheduled trial durations; missing durations make that statistic unknown.
7. Keep candidate and baseline population/evaluator/budget/deadline conditions comparable.
   New behavior requires new evidence; old experiments remain pinned to their old candidates.
   Deterministic state and fault drills complement fresh model evaluation. Replay is not fresh
   model quality. Domain mechanisms and source preparation are not release results.

These requirements follow the dataset/input/reference separation and comparable-run guidance
in [Langfuse datasets](https://langfuse.com/academy/datasets) and
[experiment comparisons](https://langfuse.com/docs/evaluation/experiments/compare-experiments).

## Agent profiles and present gaps

Profiles are executable requirements for scorer adapters, not claims that those adapters or
new studies already exist. Each listed field is a **Boolean per-case acceptance check** from
an independent domain scorer. The audit reports its pass fraction; it does not relabel that
fraction as raw span precision, recall, calibration error or business savings. Domain reports
must retain those underlying measurements separately. Baseline choices below are proposed
comparators, not new approvals.

| Agent/profile | Measures and baseline comparison | Extra validation needed |
|---|---|---|
| [Olist](evaluation/profiles/olist.json) | Intent, action, amount, reason, truthful confirmation, exact state, duplicate delivery and recovery. Compare grammar-aware rules and always-review on identical fresh cases. | Independent unseen wording, missing/conflicting facts, cap boundaries, injection and crash/restart. Current follow-up has four repeated texts and only six source groups. |
| [CFPB](evaluation/profiles/cfpb.json) | Product/issue agreement, priority/ambiguity, exact evidence, routing/privacy and durable review. Retain selective error, elevated-risk missed review and calibration diagnostics. Compare cheap-first, always-strong, deterministic baseline and always-review where available. | Domain-adjudicated risk/ambiguity, minority taxonomy and temporal shift. Consumer-selected labels are noisy references, not verified harm truth. Current 24-case mixed keyword/hash pilot is nonrepresentative and failed its review-burden objective. |
| [Revenue](evaluation/profiles/revenue.json) | Citation precision/recall checks, supported terms, abstention; separately exact simulated reconciliation amount/reason and authorized state/recovery. Compare abstain and declared rules; use a learned baseline only when actually captured. | Qualified source-meaning labels, contract-family separation, no-answer/ambiguous clauses and complete recovery. Original CUAD references do not establish numeric billing truth. Constructed billing results must remain separate from original extraction quality. |
| [Prior Auth](evaluation/profiles/prior-auth.json) | Per-criterion states, support/contradiction spans, missing information, disposition and no unsupported `met` claims. Compare request-information/qualified-review and declared extraction baselines. | Qualified clinical/policy review before evaluation, negation/threshold/contradiction/source-family coverage, document wait/resume and privacy. Synthetic Synthea cases and AI-provisional labels do not establish clinical validity. |
| [Supply](evaluation/profiles/supply.json) | Fact freshness, allowed action, per-action/cumulative budgets, capacity, approvals, bounded replanning, exact state/notices and recovery. Compare do-nothing, rules and public-estimate solver. | Changed outcome model, correlated shocks, capacity/scarcity, stale/conflicting alerts and multiple sensitivity settings. Hidden realized outcomes remain evaluator-only. Simulation qualification cannot establish freight savings or production model quality. |

Existing evidence is linked in the [pinned readiness inventory](evaluation/readiness.json).
Historical inventory digests normalize CRLF to LF to match Git checkout text on both OSes;
private capture byte pins retain their original exact-byte meaning. No existing report is
rewritten or grandfathered into a successful standard audit.

## New Olist cohort proposal

Retain the already approved source mix, SIM policy and input/reference separation. Design a
new cohort with natural paraphrases and separate source/parent/template groups. Use a reviewed
background sample for workload estimates and separately report a risk-enriched stress sample;
their mixed review fraction is not an estimate of real traffic. Use previously unexamined
source groups and a frozen new holdout; keep all previous holdouts unchanged.

The first draft should cover these twelve **scenario slots**, not twelve assumed independent
customers or predetermined gold answers: eligible full refund; eligible paraphrase; reship;
partial amount; below/exactly/above-cap boundaries; missing confirmation; missing payment;
delivery conflict; unavailable/future facts; and recovery after a commit. Attach an injection
variant to a same-split parent, rather than counting the variant as another independent group.
Expand the sample only after checking coverage and the reviewed uncertainty target. The slots
are design proposals, not prepared source cases, sealed labels or a new call authorization.

The user's statement **“Accept all 12 proposed labels”** is recorded as retrospective
acceptance of the #97 pilot's specific evaluator pin
`cd9709a9f50f7de1ac62ae51e38ed804fa2895b4e2cfaa1df95d1011f3a76294`.
It is not blind labeling, baseline/threshold approval or approval of future cases. The old
sealed evaluator stays AI-provisional at capture time; a separate adjudication records the
later human acceptance. Original captures and historical findings stay unchanged.

## Executable audit and release composition

`agent_harness.evaluation_standards` defines strict profile, protocol, case, row and study
contracts. Private study inputs contain exact text and references; never commit them or send
them to a provider automatically. Source-family, parent and template identifiers must be
assigned from inspected provenance, not invented per row to pass leakage checks. The scorer
adapter, sample selection, identity and reviewer declarations are trusted inputs; the audit
does not authenticate them or automatically detect semantic near-duplicates.

Create a `StandardProtocol` with the profile/dataset/scorer/baseline pins, frozen time,
trial count, per-field and overall correctness floors (also enforced in each required
holdout slice), independent-group requirements,
unnecessary/missed-review ceilings, group-error uncertainty ceiling, latency/cost/call/token limits,
sampling/independence/evaluator/sample-size evidence and actual pre-freeze reviews. Missing
values block qualification. Supply also needs reviewed sensitivity evidence; clinical/policy
profiles require `qualified_blind` label review. No production thresholds are supplied here.

Create a `StandardStudy` binding that protocol to the candidate spec/evidence pins, capture
interval, all scheduled cases/trials and independently scored rows. A row cannot claim
correctness with unresolved outcome, unsafe effects or a failed supplied field. Missing
required fields still fail after validation. The reporter exposes complete denominators,
source kinds and slices through private metadata and the aggregate audit. Full text and IDs
are not included in its report.

Run without network or provider dispatch:

```powershell
python -m agent_harness.evaluation_audit `
  --profile docs/evaluation/profiles/olist.json --profile-sha256 <canonical-profile-pin> `
  --protocol <private-protocol.json> --protocol-sha256 <canonical-protocol-pin> `
  --study <private-study.json> --study-sha256 <canonical-study-pin> `
  --output <new-private-audit.json>
```

Pins are SHA-256 of the validated model's `canonical_json()`, supplied separately from the
files. Output creation is exclusive; failure does not overwrite a prior audit. Exit 0 means
methodology qualified **only**. `release_allowed` is always false in this audit.

The shared `eval-release` CLI now refuses permission when the six corresponding
`--evaluation-profile`, `--evaluation-protocol`, `--evaluation-study` file/pin arguments are
absent or qualification fails. It binds the study to verified H10 candidate/baseline receipts,
manifest, scorer, trial identities, exact inputs, groups, labels and independent binary field
scores. It refuses substituted summary outcomes or token/cost counts. Required H10 cases
must also be marked critical. A digest of the sidecar `evaluation-audit.json` is included in
`result.json`. The existing H10 evidence/approval/freshness/regression gates still apply.

The lower-level `release_candidate` remains an **evidence-gate-only** mechanism. Calling it
directly does not establish this methodology qualification or deployment authorization. The
current domain fresh reports are not H10 adapters; they remain refused. Completing those
adapters and capturing final-candidate evidence is still required, rather than converting old
pilot summaries into fresh H10 journals.

Overall and required-slice uncertainty use H9's existing 95% binomial-boundary/Wilson-envelope helper on connected
holdout source groups that have any failed/missing repetition. It is conditional on independent,
comparable groups, which code cannot prove. Repeating two groups three times still supplies
only two group observations; zero observed failures does not imply a zero failure rate.
Sampling and family-quality review remain necessary even when an interval clears a limit.

## Remaining acceptance

This change strengthens the checks; it does not finish any agent's release study. Complete
domain scorer/adapters, qualified reviews where needed, representative cohorts, approved
thresholds and new bounded fresh runs before release acceptance. No additional Gemini calls,
new provider allowance, live Langfuse dataset mutation or production effect is part of this
implementation. O8 #33 and downstream release issues remain open. Verification results for
this branch are recorded on its review PR after checks actually finish.
