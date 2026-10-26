# Closure plan for Olist #33, CFPB #38 and Revenue #45

Base: verified #106 merge `21cfea9ca088a2923599f27732c21acdba1c5e45`.
This is the closure workstream, not a new release approval or claim that the issues are done.

The user subsequently requested an alternative to a standing reviewer team while retaining
the production goal. The [automated-review execution proposal](automated-review-execution-plan.md)
specifies field-level reference evidence, independent checks and qualified model evaluators.
It is a proposed successor evidence strategy; the current review requirements below remain
active until a concrete replacement policy is accepted and implemented.

## Decisions received on 2026-10-25

The user requested the work needed for actual closure, authorized **180 total Gemini Free
attempts across these three agents**, prohibited paid fallback, and requested private packets
while they identify independent reviewers. This is one shared allowance, not180per agent,
experiment or retry. Consume an attempt before each dispatch, including failed/unknown
attempts. Never reuse the exhausted historical36-call allowance. Calls, raw usage, derived
usage and any billing evidence must remain distinguishable. Unknown cost is not zero merely
because admission reserves0USD for a confirmed Free project.

No provider attempt from the new allowance has been used. Capture follows final source,
dataset, evaluator, baseline and protocol freeze. No labels, reviews, threshold approvals,
deployment or actual payment/invoice effect are supplied by this allowance.

## Concrete human-review handoff

Four private packets were created outside Git at the operator's
`closure-review-2026-10-25-v1` directory. They contain77items:

| Packet | Items | Required reviewer | Provenance and exposure |
| --- | ---: | --- | --- |
| Olist | 12 | Independent reviewer of the approved SIM policy | Existing six-source-group draft; user previously saw AI propositions; no provider capture on this draft |
| CFPB | 24 | Qualified complaint/risk-policy reviewer | Existing keyword/background pilot; historical model outputs and provisional AI labels |
| Revenue original | 12 | Qualified contract/domain interpretation reviewer | Fixed-hash family-unique, six publisher-answerable/six no-answer review sample; publisher answers withheld; exposure audit pending |
| Revenue SIM | 29 | Qualified independent reviewer of the approved fictional arithmetic, as required by the current Revenue profile | Existing nine-world cohort with historical mechanism outputs and provisional AI labels |

Only each `reviewer-only/` folder is intended for later authorized sharing. Nothing has been
sent. Administrator maps retain source IDs, split/group identity, selection strata and
exposure. Do not give them to reviewers. Reviewers receive complete inputs/facts and rubric,
not expected answers, consumer reference labels, publisher spans, AI propositions or model
outputs. Structured Olist intent/requested amount is withheld because it is a label; the
request text is shown. Reviewer identity, qualification, conflicts, time and prior exposure
are blank and must be supplied truthfully. `unsure` is a valid judgment, not an automatic pass.

Return new completed files; preserve blank originals. Verify case inventory, literal evidence
offsets, judgment shape and consistency before sealing. Keep first judgments separate from
later adjudication against historical/publisher references. Record actual disagreements; do
not claim inter-reviewer agreement from one reviewer. These packets support adjudication,
not representative release evidence. No old exposed pilot becomes an unseen holdout.

## Engineering and evidence needed for closure

The unmerged [engineering chapter](closure-engineering.md) now documents the executable
shared allowance/derived-cost controls, explicit deterministic approval, bound Olist crash
companion, CFPB durable provider composition and Revenue scoped/effect readers. Invented tests
exercise these paths. They do not supply the human judgments or final studies listed below;
the original table records the starting gaps and is not an issue-completion checklist.

| Issue | Present implementation | Remaining closure deliverables |
| --- | --- | --- |
| #33 Olist | Provider-capable H10 composition, independent SQL fields, zero-call comparator, before/after-commit process drills | Independently reviewed expanded cohort; adequate source/slice coverage; reviewed baseline/protocol; explicit deterministic-baseline release approval support; authoritative resource accounting; final paired fresh capture and bound fault evidence; reproducible report/model card/runbook |
| #38 CFPB | Typed routing/calibration and durable desk; partial mock-only H10 composition; independent queue mechanism artifact | Provider-capable full workflow composition; binding of actual privacy/injection/durable publication observations to each trial; qualified labels and representative/temporal/minority coverage; cheap-first/strong/rules/review comparison; fresh results, model card and runbook; #33 dependency |
| #45 Revenue | Original span gateway and independent metrics; separate SIM billing/approved effects; partial mock-only H10; independent invoice-state mechanism artifact | Separate original extraction and SIM reconciliation/effects studies with applicable-field denominators; qualified meaning/support review; representative family/no-answer coverage; source-linked support checks; bound authorization/compensation/crash evidence; fresh candidate and ablation results; model card/runbook; #33 dependency |

The current Revenue profile mixes original extraction fields with SIM business-state fields.
An original quotation cannot establish a fictional invoice delta, and a no-answer case has
undefined span recall. Resolve applicability explicitly with reviewed per-study profiles and
denominators; never replace unobserved checks withTrueor report undefined precision as1.0.
The current partial adapters' scorer errors remain failures until actual evidence is wired.

Likewise, standalone queue/ledger/crash artifacts do not complete a bound H10 study. They must
be linked to exact scheduled inputs, candidate/scorer/environment/fault pins and observed
results. Existing deterministic-baseline analysis support does not authorize silently
accepting that format at release. Any format extension needs exact approval identity,
compatibility/regression checks, explicit fresh-candidate requirements and negative tests.

## Study plan and budget feasibility before capture

Use separate development, regression and frozen holdout groups. Tune only on development.
Keep every related source/parent/language family in one partition. Distinguish workload
sampling from risk-enriched stress cases and preserve source-kind denominators. Review
selection, evaluator correctness and semantic independence before trusting coverage counts.

The current180attempt ceiling allows at most60case/trial sets at3attempts per case across
all three agents, before a second CFPB route, failures or diagnostics. It cannot be promised
to complete all three releases. Do not spend it on repeated known cases to inflate sample
size. Freeze an allocation only after reviewer availability, applicable metrics and sample-size
targets are approved. Do not add a larger allowance or relax a target without user agreement.

The existing uncertainty helper gives the following two-sided95% zero-failure upper bounds
for independent source groups (not repeated trials):

| Independent groups | Upper bound on group failure probability |
| ---: | ---: |
| 2 | 84.19% |
| 12 | 26.46% |
| 20 | 16.84% |
| 36 | 9.74% |
| 72 | 4.99% |

The same concern applies within each required risk slice. These calculations are conditional
on defensible independent sampling; they do not prove production safety or prescribe an
acceptable risk limit. The current two-group Olist holdout is insufficient for a strong
claim even if all three repetitions pass. A reviewed threshold/uncertainty target determines
the necessary expansion, not the desire to close an issue.

## Finish and close sequence

1. Receive independent judgments and verify/reconcile them without altering historical labels.
2. Finish missing full compositions and study applicability, with actual privacy/state/fault
   observations and complete accounting. Validate evaluators against independent judgments.
3. Prepare an explicit baseline/threshold/sample-size/resource proposal with exact pins and
   human decisions. Capture the reviewed baseline; obtain its explicit approval before the
   final candidate interval required by H10. Do not backdate approvals.
4. Freeze final code/config/cohort/protocol; run new bounded comparisons. Retain failures and
   missing usage; tune only with a new candidate/version and new required evidence.
5. Recompute artifacts offline; publish safe aggregates, actual limitations, reproducible
   operator steps, model cards and threat/failure reports. Verify all required cases/faults,
   approved limits and paired regressions. Passing CI alone does not establish model quality.
6. Submit the complete reviewable change/evidence package. After user merge, verify main and
   each issue's actual acceptance. Close #33 only when it passes, then accept #38/#45 only
   after their own results and dependency pass. If an experiment fails, fix/investigate or
   disclose the failed outcome; do not check off an unmet gate.

The reviewer packets and requested decisions are concrete handoffs; engineering work can
continue while review is pending. This plan makes no production deployment commitment.
