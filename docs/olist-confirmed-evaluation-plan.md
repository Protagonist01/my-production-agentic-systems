# Evaluate the customer-confirmed Olist service

Preparation from merged d4bdf52 on branch `codex/olist-confirmation-evaluation`,2026-11-02.
The owner asked to prepare a separate study after the unsafe legacy SIM refund. This is an
implemented service bridge and a reviewable study proposal, **not a provider-frozen execution
package**. No new source labels, model calls, allowance amendments or production release are
authorized by this document. Machine-readable scope: [proposal](data/olist-confirmed-evaluation-proposal-v1.json).

## What inspection changed

The stopped study's `RoutingEnvironment` installs business/checkpoint schemas and runs
`SupportWorkflow` directly. It does not install the customer service or its commit guards.
The PR130 service, meanwhile, uses staff-selected `FixedPlanner`. Reusing the old recorder
would measure a different system. Mapping a six-way model result into the three-way staff
intent enum also loses clarification/unsupported semantics and requested amounts.

The opt-in bridge is `CaseStore(connect, planner=...)`, with candidate
`olist-customer-confirmed-routing-v1` and agent `olist-customer-confirmed-routing-sim`.
The default API/CLI still constructs `CaseStore(connect)` and loads no live model. Passing
an HTTP field cannot choose a planner, transport, principal or authorization.

## Follow the implementation

1. [`CaseRecord`](../projects/olist-support/src/olist_support/console_contracts.py) persists
   `intent_source` and the complete typed `IntentDecision`. The default operator values
   are omitted on serialization, preserving the previous staff wire shape. Planner records
   require an upgraded reader; no old-binary compatibility for those new records is claimed.
2. [`CaseStore.submit`](../projects/olist-support/src/olist_support/console_cases.py) derives
   source from trusted composition, checks the explicit profile, and uses a separate request
   hash domain for planner cases. An old operator event cannot silently become a model run.
   Application case/event IDs are derived before dispatch; a future provider scope must
   freeze these resulting context IDs rather than reuse old routing case IDs.
3. `run_request` preserves a planner case's original run ID, budget and deadline. Staff-only
   recovery retains its existing refreshed context behavior. A planner case cannot be resumed
   using an unconfigured operator store. This code does not itself authorize any provider
   attempt, parent-process resume or exception to a stopped scope.
4. After graph execution, read the durable checkpoint decision, not an in-memory callback
   that disappears after restart. A completed graph can be read after a failed case save
   without another planner call. Successful unversioned legacy plans are refused in this
   profile; an explicit failed planner decision stays review-only.
5. `_snapshot` uses the saved plan's fine intent and exact requested minor units. Clarify,
   unsupported, review or a failed decision creates no refund command, even when the staff
   request contains a refund placeholder. Partial/zero/over-cap amounts remain independent
   policy refusals. A successful full-refund command remains pending customer confirmation.
   An explicit staff review request also keeps a model-classified status answer in review;
   preserving the model's fine classification does not grant it authority to skip review.
6. Bind the plan into the action digest. A default customer-facing store can read the saved
   plan and enforce fresh evidence without owning a model. Required staff review is still
   additional to customer consent. Consumption, receipt, case and audit remain transactional.

This bridge is not a service-aware H10 recorder or scorer. Those components need distinct
versions and fingerprints before provider execution. The old `RoutingScorer` assumes direct
workflow outcomes; a pending customer proposal is not a completed refund under that contract.

## Keep four questions separate

| Question | Evidence | Claim it can support |
|---|---|---|
| Did the model understand the original text? | Saved fine intent/requested amount against separately pinned references | Agreement on those references, including failures even if consent later blocks execution |
| Was the proposed action conditionally eligible? | Trusted SIM facts and independent policy table | Policy compliance given those facts |
| Did the scoped customer authorize this exact transaction? | Session/account scope, challenge, exact confirmation, expiry and consumed authority | Transaction authority within the tested identity boundary |
| What actually committed and recovered? | Independent before/after SQL, receipt, case/audit, duplicate and fault observations | Observed effects and tested recovery cases |

A scripted customer must not create semantic credit for a wrong model prediction. A
reference-driven scripted consent can test conditional completion but is evaluator-supplied
behavior, not evidence that a real customer wanted or understood the action. Report these
conditions explicitly. A new confirmation does not erase the original interpretation error.

This follows Langfuse's separation of goal, guardrail and operational metrics and its
input/reference/metadata boundaries. See [metric decisions](https://langfuse.com/academy/evaluate/choosing-what-to-evaluate)
and [dataset design](https://langfuse.com/academy/datasets). No live Langfuse dataset is created
or uploaded; pinned dependencies remain unchanged for study compatibility.

## Metric table: retain the accepted targets

The owner accepted [operating targets](data/olist-operating-targets-v1.json) on2026-10-30.
The following operationalizes those existing targets; it does not approve a new statistical
protocol or claim they have been met.

| Priority | Status | Metric / target | Source or evidence | Decision and measurability |
|---|---|---|---|---|
| Guardrail | Existing | Zero observed critical effects | Independent ledger/order changes, receipt/case/audit and customer authority | Stop on unsafe or unknown state; refuse release. Missing observations cannot pass. Scope conditional customer scripts separately. |
| Goal | Existing | Joint intent/amount agreement >=95% | Fine plan against evaluator-only references; 72 scheduled model decisions in optional development run | Diagnose model quality; no credit from customer filtering, abstention or missing rows. Current references cannot qualify production. |
| Goal | Existing | Eligible completion >=95% | Eligible cases with separately declared exact-consent input and verified single receipt | Detect workflow regressions; report conditional scripted denominator, never unconditional real-customer success. |
| Goal | Existing | Required-review routing >=95% | Reference-required review plus observed route, zero effect and preserved review state | Block regression/promotion; an unconfirmed refund proposal is not automatically a correct clarification route. |
| Guardrail | Existing | No acknowledged commit loss; duplicate has one effect | Actual process/response-loss tests and fresh state/receipt readback | Block release on lost/duplicated effect; distinguish graph checkpoint from authoritative service completion. |
| Operations | Existing | p95 non-model API <=1s; model-assisted decision <=30s | Client/API timing and proposal phase timing with denominators | Include timeouts. Report cold-worker/parent totals separately. Customer thinking time is not a measured machine latency; do not claim end-to-end customer latency. |
| Operations | Existing | Complete attempts, usage and accounted Free scope | One authoritative ledger plus scoped responses and complete token usage | Stop on scope/accounting failures. No paid fallback; tariff-derived zero is not raw billing proof. |

Initial99.5%availability over30days and host-loss RPO15min/RTO60min stay separate operational
acceptance. Unit/SQL passes do not establish these targets.

## What the existing reference inventory really contains

A private read-only validation combined the two accepted populations without editing either:
12ABCD-derived hybrid cases and12authored stress cases, all development. It found16declared
groups,14language families,14refund/4clarify/3unsupported/2status/1reship references. Conditional
policy outcomes are7refund-eligible,15review-required and2status, with1after-commit recovery
case. Groups/families are declared, not independently validated sampling units. All text
is exposed; the accepted mappings remain owner-reviewed AI projections, not independent gold.

Preserve both original populations, owner acceptance receipts and grouped variants. A new
private preparation packet may pin/copy those existing bytes; it must not rename them into
holdout, count related variants as independent families or export labels in model input.

Even if all16groups were independent/comparable and every group passed, the two-sided95%
exact-binomial success lower limit would be `0.025 ** (1/16) = 0.79409`, not95%. This is an
illustration under assumptions, **not a valid population confidence claim for these selected,
provisional cases**. Repeating each text three times does not create new independent groups.
Method: [NIST exact binomial limits](https://www.itl.nist.gov/div898/software/dataplot/refman2/auxillar/exacbici.htm).

## Optional diagnostic allocation, not qualification

A bounded development proposal could use one versioned model candidate,24existing cases,
three trials each, plus two representative canaries: **74actual attempts maximum**. Matched
rules and always-review baselines each add72zero-provider decision trials:216decision rows
in total. Consent/fault branch observations are separate mechanism observations, not additional
independent model decisions. Canary attempts count against spending but not quality denominators.

The authoritative ledger remains447/614, zero unsettled, with the old routing stop intact.
Of167unspent slots,51belong to earlier scopes and116to the stopped routing study. Only if
separately approved, reassign74of those116through a new append-only scoped allocation:
447+74=521consumed at most;51older+42other stopped slots remain bound; lifetime cap stays614.
This proposal does not reserve or reassign a slot. Never update old rows, remove the stop,
reinitialize the ledger or run the old execution driver with changed files.

This is an optional diagnostic, **not the recommended next provider spend**. First finish
service-aware observation/scoring and establish which fresh references can support the
qualification claims. Otherwise another perfect exposed-case result still cannot close#33.

## Qualification source and sampling work comes first

For illustration only, a separately-per-endpoint two-sided95%exact-binomial lower bound
of95% needs at least72independent all-success families in each applicable denominator.
Consider a design that deliberately samples **disjoint families** for eligible-refund and
required-review strata, with separate calls per applicable case:72+72=144families before
adding status/other required slices. At three trials per family this design needs at least
432domain calls+2canaries=434attempts. This is a design-specific floor, not a universal
minimum. A paired-family or reused-response design has different arithmetic and must make
its conditional endpoints and dependence explicit; it cannot count paired variants as
new independent families. Errors, label uncertainty and simultaneous confidence requirements
can increase sample needs. Neither design is an approved protocol, available cohort or
spend request; the source evidence must establish which claims can actually be supported.

Freshness means new independent source groups with a documented sampling frame, not new
edits of these24texts. Source work must examine whether publisher annotations establish
meaning from the exact visible conversation prefix, keep future agent/actions hidden,
check group overlap with all exposed material, and preserve original annotations alongside
project-specific mappings and disagreements. Conditional SIM amounts do not supply real
customer amount/preference gold. If sufficient external reference evidence is unavailable,
report the claim as unsupported rather than manufacturing labels or lowering the target.

## Execution checklist before any model call

1. Finish the service-aware H10 factory/observer/phase scorer and matched baselines. Install
   all service/checkpoint/intent schemas; provision invented scoped actors through trusted
   setup. Keep evaluator-only labels and customer scripts outside candidate/model input.
2. Freeze reference eligibility and case order; version the language-quality and service-state
   observations separately. Include complete scheduled denominators and all missing/failed
   rows. Required recovery and customer-authority observations cannot be omitted to pass.
3. Freeze actual merged source, source-file/lock hashes, host/interpreter, prompts/schemas,
   request/context bytes, profile, scoring, limits, deterministic actors and expiry. The
   current packet is a preparation draft; PR130's old study fingerprints do not cover it.
4. Implement any new allowance scope and stale-client SQL guards using fake HTTP first.
   Apply no live amendment until the owner approves its concrete allocation and Free account
   scope. A budget proposal is not dispatch permission.
5. Run full selected-host fake-SDK/real-SQL readiness. Require both representative canaries
   with accounted receipts before domain calls. Proposed transport bounds remain30sHTTP,
   90sworker/300sbatch, one concurrent trial, no automatic retry or paid fallback; freeze
   final limits against actual readiness rather than silently changing them during a run.
6. Journal each observation before admitting the next provider attempt. Unsafe/unknown state,
   missing/corrupt evidence or parent death stops the new scope. No implicit resume. Preserve
   the prior incident, all previous receipts/labels and the original stopped scope.

## Verification and interview practice

[`test_olist_planner_service.py`](../tests/integration/test_olist_planner_service.py) uses
invented decisions without an SDK: six-way routing versus staff placeholder, exact/partial/
zero/over-cap amounts, required review and independent customer consent, wrong-profile
rejection, durable graph/case-save failure, unchanged run/deadline and legacy-plan refusal.
The unit counterpart pins the old operator wire keys and typed decision round-trip. These
tests establish mechanisms, not model accuracy, fake-SDK readiness or qualification.

Explain why the first wrong refund was within cap yet still wrong, why a customer click
cannot turn that original classification into a correct prediction, and why a restored
checkpoint should avoid a second model dispatch. Then calculate74development attempts
versus the434attempt qualification floor and identify which reference/sampling assumptions
are still missing. A strong project explanation states those limits alongside the working
consent/transaction controls.
