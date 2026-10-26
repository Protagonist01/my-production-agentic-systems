# Production evaluation without a standing reviewer team

Prepared 2026-10-26 against main `95691bde1c52447b2deff2ef8cf2ffd1020891f9`.
Status: execution proposal requested by the user; no release requirement has been waived,
no study or judge has been qualified, and no provider call is authorized by this document.

Execution has begun in the [offline evidence foundation](evidence-foundation.md): complete
profile-bound field/slice inventory, diagnostic contracts, attempt forecasting and an Olist
SIM oracle. Remaining stages below are still planned; this is not a completed review system.

## Outcome and boundaries

Keep the existing production objectives. Replace avoidable manual labeling work with
traceable reference evidence, independently implemented checks and tested model evaluators.
The production target remains; current SIM actions and assistive workflows do not acquire
real-world execution permission through a successful evaluation.

The important distinction is between a different way to establish a requirement and a
weaker requirement. A calculator can establish an exact SIM refund amount. Model consensus
cannot establish the clinical correctness of an unsupported interpretation. Where an
adequate alternative cannot be demonstrated, record the exact remaining requirement rather
than requiring an expert for every case or treating every case as automatically acceptable.

There are three separate authorities:

1. Evidence establishes observed behavior and the reliability of a particular evaluator.
2. The product/risk owner accepts operating limits and any proposed replacement review method.
3. Deployment authorization controls real users, environments and effects.

A model cannot grant the latter two. The operator can accept a business risk without being
represented as a qualified domain labeler. An explicit requirement for qualified review
remains unmet unless suitable qualified reference evidence or a validated replacement is
accepted for that particular requirement. This plan does not promise universal substitution.

## 1. Inventory claims before designing judges

Prepare one requirement/evidence matrix covering #33, #38, #45, #51 and #57. Each row records:

- agent, task, field, failure severity, applicable cases and operating assumptions;
- current acceptance wording and exact profile/protocol version;
- reference source and permitted use, its original annotation purpose and qualifications;
- whether the reference is original, an edited derivative, constructed or AI-provisional;
- planned check, limitations, calibration evidence and applicable domain/slice;
- proposed disposition: proven, failed, unresolved or not applicable with justification;
- the proposed replacement method, who may accept it, and the evidence needed first.

Split compound requirements. In Revenue, correct quotation, supported meaning and a correct
SIM invoice delta are three different claims. In Prior Auth, a matching policy citation,
correct criterion application and clinical validity are different claims. A text offset
check proves that a quotation exists, not that it supports the conclusion.

Deliverables: `requirement-evidence-matrix`, `source-register`, `residual-judgments` and a
versioned acceptance-method proposal. Store raw records privately and publish safe summaries.
Do not edit existing profiles to make the old audits pass.

Exit: every current required field has an evidence path or an explicitly identified gap.
Engineering proceeds on supported paths while research continues on the gaps.

## 2. Establish reference evidence and independent executable checks

First inspect existing licensed/public expert-labelled resources. For each candidate source,
record version/hash, source URL, license, privacy/export permission, annotation process,
label definitions, source families and known exposure. Public availability alone is neither
permission for redistribution nor proof that its labels match our task.

Keep publisher/reference labels outside candidate and judge inputs. Existing public labels
may have appeared in model training; use them as disclosed calibration evidence, not an
unseen production holdout. A modified reference case does not inherit the original expert
label. Verify each label's applicability; otherwise mark the derivative provisional.

Build separate executable oracles for objective facts. An oracle is a program that calculates
the expected result independently of the candidate. It must not call the candidate's own
policy or scoring function to derive its expected answer. Test boundary values, wrong
implementations, independent examples and realistic corruptions. Shared requirements can
still cause shared mistakes; document that limitation.

| Agent | Objective evidence to implement or reuse | Meaning that needs additional evidence |
| --- | --- | --- |
| Olist | Independent eligibility/amount table; missing/conflicting/future-fact checks; exact SQL effects, caps, permissions, duplicate and recovery checks | Intent, requested partial amount and reason interpretation in unseen wording |
| CFPB | Taxonomy validity, literal evidence offsets, masking, routing transitions, durable queue and failure handling | Elevated risk and ambiguity; consumer-selected product/issue is a noisy reference, not a verified harm label |
| Revenue | Original extraction against applicable publisher annotations; separately independent decimal arithmetic, authorization, compensation and state checks | Clause meaning, exceptions and whether a quotation actually supports an extracted term |
| Prior Auth | Exact policy version, supplied facts, literal support/contradiction spans, numeric boundary tests and document version/resume checks | Policy application on realistic records; policy text and invented records alone do not establish clinical validity |
| Supply | Independent budget/capacity/freshness/replanning checks; separate public-estimate baselines and hidden outcome evaluation | Validity of simulator assumptions and transfer to actual freight operations |

Metamorphic tests specify what should change when an input changes: a paraphrase should
preserve a decision; crossing a policy cap should change the applicable outcome. Establish
the relation from a rule/reference first. Passing these tests supports consistency and
boundary behavior, not the correctness of every semantic label.

Exit: independent checks detect seeded errors, reference applicability is documented, and
untestable claims remain visible. Run these tests without provider calls where possible.

## 3. Build and qualify model reviewers

Use models for residual text interpretation and evidence-supported critique. Candidate
generation, reference preparation and evaluation are separate roles. Prefer different model
families for candidate and judge, where access and domain exports are authorized. Different
providers or prompts do not establish statistical independence; retain their identities and
test their shared errors. The available Gemini and Groq routes are possibilities, not proof
that either is a suitable domain reviewer.

Two operations must remain distinct:

- **Reference drafting:** judges separately read the input, policy and source material without
  proposed labels or candidate answers; outputs remain AI-provisional absent an external basis.
- **Candidate assessment:** a judge sees the candidate answer and permitted source evidence,
  without candidate identity or other judges' assessments. Known-answer comparison occurs
  separately so hidden answers do not leak into the prompt.

Require structured outputs: field-level judgment, exact supporting/contradicting spans,
policy/source identifiers, rule applied, missing evidence and an explicit abstention reason.
Validate schema, offsets and versions by code. Self-reported confidence is a diagnostic,
not an approval condition. Treat source text and candidate output as untrusted data; neither
can override evaluator instructions or execute tools.

Freeze the judge prompt, model configuration, schema and evidence policy before calibration.
Use development examples to improve it, then a separate reference-labelled test partition.
Include correct, incorrect, ambiguous, unsupported and deliberately manipulated answers.
Use held-out error templates so a judge does not qualify by memorizing development mutations.

Measure confusion matrices, false acceptance of incorrect answers, missed unsafe outcomes,
false rejection, abstention, slice coverage and group-level uncertainty. Evaluate missing
citations, plausible wrong amounts, negation, changed dates, omitted exceptions, fabricated
support, answer-length changes, prompt injection and response-order swaps where pairwise
comparison is used. Report both conditional accuracy and the fraction it can actually judge.

There is no universal 85% or 95% judge-accuracy release rule. Freeze severity-specific error
limits and uncertainty requirements before testing. A small perfect calibration set is a
pilot, not production qualification. Qualify each domain/field/slice explicitly; a judge
qualified for literal extraction is not qualified for medical or contract interpretation.

Evidence decision order:

1. A failed authoritative check fails the relevant field; judges cannot overrule it.
2. An applicable external reference supports a reference-based determination, with its limits.
3. Only a qualified model evaluator may contribute a semantic judgment in its tested scope.
4. Model agreement without external support remains provisional; disagreement, invalid output
   or unsupported reasoning remains unresolved. Another model may investigate, not vote it away.

Exit: a pinned evaluator qualification report identifies supported scopes and failed scopes.
An evaluator that fails qualification stays diagnostic and cannot confer a release pass.

## 4. Implement a versioned evidence path without disguising human review

The current `Review.kind` in
[`evaluation_standards.py`](../harness/src/agent_harness/evaluation_standards.py) permits
`ai_provisional`, `human_retrospective`, `human_blind` and `qualified_blind`. `_reviewed`
accepts only actual blind human/qualified review, depending on profile. Keep that behavior
and all historical profiles intact.

Design a separate versioned evidence contract rather than writing a model name into
`qualified_blind`. Its proposed record includes:

| Field group | Required content |
| --- | --- |
| Identity | Domain, criterion, case/input hash and claim scope |
| Evidence | Reference/oracle/model evidence type, source and output hashes, versions and applicability |
| Evaluator | Code/prompt/model/schema hashes, qualification report and allowed fields/slices |
| Result | Supported, contradicted, unresolved or justified not-applicable; evidence spans and failure reasons |
| Provenance | Real creation time, exposure record, authority and superseded evidence links |

A separately accepted evidence policy specifies which methods can establish which claims.
Baseline approval, threshold acceptance, label evidence and deployment permission remain
different records. No model result manufactures an approval identity or backdates acceptance.

Test refusal for missing evidence, wrong source/version, changed prompt, inapplicable
qualification, forged review type, invalid spans, unsupported agreement, stale approvals,
missing scheduled rows and unknown required accounting. Preserve old failures and require
new evidence for changed candidate/evaluator/protocol versions. Recompute reports offline.

Exit: a proposed v2 policy and implementation pass positive and negative tests. Promotion
requires explicit acceptance of the concrete substitution matrix. No `skip_review` switch,
relaxed legacy gate or rewritten historical label is part of the design.

## 5. Run fresh studies with complete denominators

Start with Olist #33 as the integration proving ground. Then execute CFPB #38 and Revenue
#45 using the same mechanism with separate domain qualification. Prior Auth #51 and Supply
#57 preparation can proceed, but their live studies need their own authorized provider scope.

For each study:

1. Freeze source/family/template groups, development/regression/holdout splits and permitted
   exposure. Freeze background sampling separately from risk-enriched stress sampling.
2. Establish references, validate the evaluator and seal labels before candidate output.
3. Set operating limits, required risk slices, critical cases and sample-size rationale.
   Derive sample size from the chosen uncertainty target; repetitions do not add independent
   source groups. Count connected parent/template variants together.
4. Freeze and run applicable comparators: Olist rules/always-review; CFPB cheap-first,
   strong-route, rules/always-review; Revenue extraction/abstain and separate SIM engine/catalog
   ablations; Prior Auth extraction/request-information; Supply do-nothing/rules/solver.
5. Complete and accept the pinned baseline before the final candidate interval, as H10 requires.
6. Capture fresh candidate outputs, actual raw usage, wall time and bound privacy/state/fault
   observations. A failed or unknown attempt consumes budget and remains in the schedule.
7. Recompute paired outcomes, required-slice error and uncertainty, unresolved/missed-review
   rates, actual state/effect violations, latency, calls, tokens and known/unknown costs.

An always-review system can be safe yet fail useful completion/review-burden requirements.
Abstentions remain in scheduled denominators and cannot improve accuracy by disappearing.
No-answer extraction metrics and original/SIM business metrics have explicit applicability;
never blend them into a single apparent accuracy. Supply outcomes remain simulation results.

Stop qualification on any critical effect/privacy/authorization violation, failed evaluator
scope, missing required evidence or exceeded allowance. Diagnose offline first. Do not tune
against the frozen holdout; changed systems require a new version and the necessary new data.

Exit: each issue has a reproducible report with an actual pass/fail/unresolved decision
against the frozen policy. Passing engineering CI alone does not close a domain release.

## 6. Budget and permissions

At planning time: Gemini closure allowance **0/180 consumed**, covering Olist, CFPB and
Revenue only. Separate Groq invented-smoke allowance **9/12 consumed**, three remaining,
no unsettled attempts. Recheck the authoritative ledgers before execution; do not reset them.

Proposed Gemini feasibility envelopes, not a live grant or a promise of release completion:

| Purpose | Maximum attempts |
| --- | ---: |
| Reference/evaluator feasibility within the three authorized domains | 36 |
| Olist paired study preparation and candidate capture | 48 |
| CFPB route comparisons and candidate capture | 48 |
| Revenue original/SIM comparisons and candidate capture | 24 |
| Unallocated contingency, never automatic retries | 24 |
| **Shared ceiling** | **180** |

Before dispatch, compute exact scheduled calls: reference drafting plus calibration plus
candidate/comparator trials plus live fault companions plus every judge pass. Two reviewers
cost two calls; swapped comparisons cost additional calls; model baselines also count. A
single call cannot become several independent examples. Stop before capture if the frozen
design cannot meet its evidence target under the remaining allowance. Reduce wasted work,
not the required confidence; show any necessary incremental budget as a concrete decision.

Confirm that new evaluator roles fit the authorized grant before adding executable contexts.
Do not silently repurpose a fresh-candidate grant or transfer allowances across providers.
Groq's three remaining smoke attempts do not authorize domain review or source exports.
Prior Auth/Supply live evaluation, Groq domain use, changed data destinations or paid usage
need specific authorization. Prepare exact data/model/attempt plans before asking.

Free-tier admission is not observed zero billing. Keep raw token counts, estimated costs,
derived prices and verified billing separate. Unknown required accounting blocks the relevant
qualification; fix capture/reconciliation or obtain an explicit applicable accounting method,
rather than filling unknowns with zero.

## 7. Delivery batches and issue closure

These are sequential integration milestones, with dependent preparation inside each batch.
They do not create new GitHub issues or change existing dependency rules automatically.

| Batch | Issues advanced | Concrete delivery | Acceptance |
| --- | --- | --- | --- |
| A: evidence foundation | #33, #25, #60 | Requirement matrix, source audit, independent oracles, evaluator contracts/negative tests and exact attempt forecast | Offline correctness; explicit residual gaps; no claimed domain qualification |
| B: first domain proof | #33, with #38/#45 preparation | Olist evaluator qualification, accepted replacement-method proposal, frozen baseline/protocol and affordable fresh study | All existing substantive Olist requirements plus accepted evidence method; close #33 only on actual pass |
| C: cross-domain studies | #38, #45, #25, #60 | Separate CFPB/Revenue studies; scoped fallback comparison where authorized; tested judge monitoring | Own domain gates and #33; adapter smoke does not satisfy fallback quality |
| D: remaining verticals | #51, #57, #60 | Policy/source qualification, simulation sensitivity and fresh protected workflow studies | Own criterion/simulation limits; unresolved semantic requirements remain explicit |
| E: operational release | #58, #59, #61 | Actual target-host readiness/drain/fault acceptance, recovery objectives and exercises, final manifests/cards/runbooks | Required domain dependencies, verified recovery and final deployment decisions |

For every implementation PR: run meaningful focused checks, required hosted checks, merge
only the exact verified head under existing authority, and verify main. For domain acceptance:
attach the exact reports and blockers, update the issue checklist truthfully, then close only
when requirements and dependencies pass. Close epics/root only after their child acceptance.

If qualified reference data cannot support a field and model evaluators cannot qualify,
return a specific residual requirement with evidence of the attempted alternatives. The next
decision is targeted data/expert acquisition or an explicitly accepted product decision;
there is no automatic model-majority escape hatch. This preserves the production goal while
making the remaining need small, concrete and demonstrable.

## Immediate next execution

Begin Batch A without provider dispatch: inspect each existing required field, map available
reference sources, specify independent oracle interfaces, draft evaluator records and build
an exact schedule/budget calculator. Present the first Olist evidence matrix and refusal
examples before changing active acceptance. Keep original reviewer packets untouched.

This proposal changes the planned evidence strategy from a standing reviewer dependency to
field-specific demonstrated evidence. It does not assert that all expert judgment is already
replaceable, that the existing allowance is sufficient, or that any release gate has passed.

## Basis and related documents

- [Current standards](evaluation-standards.md), [closure plan](release-closure-plan.md),
  [remaining gates](remaining-delivery-status.md), [H10 evidence](release-evidence.md) and
  [Groq scope](groq-fallback.md) establish the current implementation and permissions.
- [Langfuse LLM-as-a-Judge documentation](https://langfuse.com/docs/evaluation/evaluation-methods/llm-as-a-judge)
  describes rubric-based evaluators and calibration against labelled examples. It does not
  make unverified labels authoritative or certify our domains.
- [Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena](https://arxiv.org/abs/2306.05685)
  studies judge biases and agreement on its chat benchmarks, not our production tasks.
- [Large Language Models are not Fair Evaluators](https://arxiv.org/abs/2305.17926)
  demonstrates order sensitivity and calibration methods. Order checks here are a design
  precaution, not proof of domain validity.
