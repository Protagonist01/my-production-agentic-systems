# Qualification evidence: concrete applicability decision

Prepared 2026-11-11 from main `fd4ef0c`. The owner requested completion of qualification
evidence alongside scheduled/off-host recovery. Existing accepted development references,
all eight required fields/slices, historical failures and the stopped provider ledger remain
intact. This audit narrows the evidence needed; it does not admit a new source, qualification
cohort, judge, budget, retrospective reference or release.

## Why published retail tasks cannot be copied into Olist gold

Pinned τ-bench source: `sierra-research/tau2-bench` commit
`c06b07dd7c4d4ec61ba6ff9bcdf0b15dd7ef36d4`. The
[metadata receipt](data/olist-retail-reference-applicability-v1.json) records five exact files
and hashes: MIT license, retail policy, retail tools, action evaluator and environment
evaluator. No task/dialogue/trajectory corpus or benchmark user simulator was loaded or run.
Private snapshot manifest:
`afc2896e13ed37832c014274ff010106b6f09ff668ff1180b010027ae8bcdac8`.

| Observed publisher behavior | Olist applicability decision |
|---|---|
| [Retail policy](https://github.com/sierra-research/tau2-bench/blob/c06b07dd7c4d4ec61ba6ff9bcdf0b15dd7ef36d4/data/tau2/domains/retail/policy.md) authenticates a user, requires explicit confirmation for writes, cancels pending orders and returns/exchanges delivered items. | Relevant design comparison for authority and tool use. It is not the Olist canceled-order full-refund SIM policy, with its cap and partial-refund review rule. Do not equate item exchange with reship intent or pending cancellation with an explicit requested refund amount. |
| [Action evaluator](https://github.com/sierra-research/tau2-bench/blob/c06b07dd7c4d4ec61ba6ff9bcdf0b15dd7ef36d4/src/tau2/evaluator/evaluator_action.py) searches predicted tool calls for each expected action and combines required matches. | Tool-action agreement within the publisher task. It supplies no reviewed mapping from an Olist customer's visible wording to requested intent/money role. Matching a call is not independent proof of the correct authorization or SQL effect. |
| [Environment evaluator](https://github.com/sierra-research/tau2-bench/blob/c06b07dd7c4d4ec61ba6ff9bcdf0b15dd7ef36d4/src/tau2/evaluator/evaluator_env.py) executes expected actions in modeled state and checks predicted state/assertions according to reward basis. Missing expected criteria can produce a default success. | Useful contrast with independent state witnesses. Preserve Olist's fail-closed missing-required-evidence rule; do not transplant a vacuous success default. Modeled state is not a PostgreSQL transaction/host-recovery witness. |
| [Retail tools](https://github.com/sierra-research/tau2-bench/blob/c06b07dd7c4d4ec61ba6ff9bcdf0b15dd7ef36d4/src/tau2/domains/retail/tools.py) compute item/payment/refund differences in its own data model. | Numeric tool behavior does not annotate the requested-money role in arbitrary visible customer text. No source task was inspected to assert coverage counts. |

Decision: **do not import τ retail as Olist qualification gold**. Preserve it as a documented
design/reference candidate. If a future narrow task projection is proposed, first admit
the exact policy/input/annotation mapping and exposure/family grouping; never infer that a
benchmark leaderboard validates our application or a judge.

## Field-by-field evidence to finish

| Required claim | Concrete existing evidence | Exact next artifact needed |
|---|---|---|
| Intent meaning | Owner-accepted Bitext mapping is development/calibration only; authored and controlled-grammar examples have their declared limits. The comparator's native-reference 9/36 agreement remains a failure record. | Applicable independently supported meanings on a fresh group-separated qualification population, covering refund/reship/status/clarification/unsupported behavior and the required slices. Record annotation task and scope; publisher names alone are insufficient. |
| Requested amount meaning | Accepted constructed grammar distinguishes payment mentions from refund requests; Decimal/policy arithmetic is independently executable. | Exact amount-role references for the qualification inputs, including no explicit amount, partial requests, multiple amounts and conflicts. Missing annotation cannot become an expected null amount. |
| Action/review reason | Independent SIM eligibility, predicates, exact customer authority and protected review/state checks exist. | Frozen candidate observations bound to the qualified semantic premises, expected action/reason and actual durable review/effect. Safe abstention does not prove useful completion or correct language understanding. |
| Truthful confirmation | Fixed templates can be checked against authoritative receipt/state. | Actual final-candidate messages, independent receipt readback and matching template/version; generated prose needs additional evidence scope. |
| Exact state/duplicate delivery | Independent scoped SQL readback and single-effect/original-receipt tests, including catalog recovery. | Complete fresh candidate trial observations on scheduled qualification cases, expected state deltas and fault pins. Repeated classifier answers are not effect deduplication. |
| Recovery | Process/response-loss and new-database restore mechanisms exist; encrypted local non-SQL canary now verifies transport bytes. | Actual selected-host scheduled/off-host restore through authenticated workflow, measured acknowledged data loss and outage-to-recovery times. Different failures retain separate denominators. |

Required slices remain `eligible_refund`, `required_review`, `missing_facts`,
`conflicting_facts`, `cap_boundary`, `unseen_wording`, `prompt_injection`, `crash_restart`.
This audit supplies no new qualification support counts for any slice.

## Execution order to avoid another uninformative study

1. Finish the independent state/arithmetic/template/fault proof adapters already covered by
   the accepted Olist v2 method design; bind actual candidate observations, not self-reports.
   Keep new transport evidence separate from semantic qualification.
2. Resolve the specific semantic applicability gap above. Choose an applicable external
   annotation source or an independently validated construction/evaluator for the claimed
   natural-language population. The existing closed grammar is development-only; broad
   language cannot be qualified merely by generating more variations of our own templates.
3. If using a model evaluator, assemble independently supported correct/incorrect examples
   for its exact field/slices, group related parents/templates, keep calibration and untouched
   validation separate, and measure false acceptance/rejection, abstention and uncertainty.
   A model cannot qualify itself by agreeing with another model. Preserve missing outcomes.
4. Freeze the full input/reference/evaluator/candidate/source/environment/scorer/policy and
   fault inventory plus sample-support, repetition, latency, cost and paired-regression plan.
   Required confidence depends on independent groups per class/slice, not total repeated calls.
5. Only then request one consolidated fresh provider/export allocation and exact stop/expiry
   decision on the same authoritative ledger. The old 447 consumed attempts, bound remaining
   slots and durable stop are not a usable new study. No key is loaded by this work.
6. Execute, independently read back and report complete scheduled denominators; keep failures
   visible. Operational recovery and semantic quality must both pass before issue/release
   acceptance. Neither is a substitute for the other.

[Langfuse dataset guidance](https://langfuse.com/academy/datasets) supports explicit input,
expected-output and metadata roles. Our existing qualification/method contracts already
require separate reference applicability and evaluator material; this audit does not create
a live dataset or active judge. Expert review is one possible evidence source, not the only
architecture. The missing requirement is independent applicable meaning, which this public
retail audit has not supplied. No false claim of completion or weakening of scope follows.
