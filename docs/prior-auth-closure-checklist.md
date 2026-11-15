# Prior Auth: one checklist to reach release

Prepared November 15, 2026 from the merged release-readiness implementation at
`c0a907817c5f494d6dceebe98daeaf875ab6f753`. This consolidates remaining work and
existing gates. It grants no new model study, data rights, spending, clinical
qualification or deployment activation.

## Destination and completed work

Deliver an authenticated adult initial-CPAP evidence assistant: import permitted
documents, verify patient/payer/plan/policy bindings, extract supported criterion
states with source citations, request missing documents and resume durably.
External submissions require independent operator authority. The assistant does not
issue its own clinical approval, denial or treatment recommendation.

Already verified; do not rebuild:

- [x] Bounded text, selected C-CDA/FHIR narrative, PDF and OCR adapters with source pins.
- [x] Unrelated/wrong-subject/unsupported-policy intake controls, protected reviewer
  sessions, durable Postgres handoff, document waits and source readback.
- [x] Fresh constructed study: 168 calls, two passing canaries, 166 domain requests,
  24 checked case trials and independent readback. Cumulative budget: 615/784.
- [x] Actual separate official HL7 reference service: submit, Claim correlation,
  durable replay and inquiry. This is not commercial-payer acceptance.
- [x] Merged implementation and passing PR/main tests.

Evidence: [actual study](prior-auth-development-study-v1.md),
[operator workflow](prior-auth-operator-workflow.md),
[release methods and payer adapter](prior-auth-release-readiness.md).

## Ordered engineering work and exit evidence

| Order | Deliverable | Done means | Dependency |
| --- | --- | --- | --- |
| 1 | Separately versioned candidate with complete citations | Every applicable subcondition and relevant negative/conflicting context is supported by exact source evidence, or the candidate abstains; original checker/captures preserved | Implement offline now; new provider comparison needs D3 |
| 2 | Opt-in durable model assessor in the operational worker | Authenticated import → assessment → source readback → document wait → supplement → reassessment works; budget, crash, version and tenant fences pass actual SQL/fake-SDK tests | Implement now; live operation needs D3 |
| 3 | Deployment bundle and isolated document worker | Clean-host install, protected accounts, health checks, restricted parser filesystem/network/resources and complete state/config recovery are exercised | Prepare alongside 1–2; actual host/activation needs D4 |
| 4 | Applicable independent clinical references | Every required semantic judgment has permitted, applicable evidence, or a separately qualified evaluator grounded in those references; unresolved cells remain explicit | D1 and D2 |
| 5 | Fresh frozen application qualification | Accepted references/limits, unseen family-separated cohort, frozen candidate/environment and complete field/slice report; meet limits or leave release blocked | 1–4 and exact D3 study grant |
| 6 | Target-payer sandbox connection | Actual target authentication, attachment handling, identity/correlation, inquiry/RFI mapping, stale rejection and durable unknown-outcome reconciliation pass | Reuse reference adapter; D5 supplies target/access |
| 7 | PA recovery drill and release acceptance | Restore all required PA state into a clean target, verify authenticated workflow/replay, measure data loss/restore time and accept against unchanged release gates | D4 plus passing clinical/integration evidence |

Immediate batch: steps 1 and 2, with step 3 preparation alongside them. Reference
acquisition and payer access are parallel external dependencies. Do not start another
broad research cycle unless it resolves a specific uncovered judgment or source right.

### Citation backlog

- [ ] Sleep-test support includes positive result plus permitted test type/channels.
  The last study had only 5/24 checked agreements for this criterion.
- [ ] Physician-order support includes the prior treating-physician order and required
  supervision. An order quote alone does not establish both conditions.
- [ ] Adult/OSA support includes both facts. Numeric claims include the relevant
  measure, interval, units and required context.
- [ ] Negative/ambiguous findings cite their context; unsupported negatives do not
  become verified truth. Cover omitted qualifiers, duplicate quotes, cross-document
  spans, missing subconditions and injected attachment instructions.
- [ ] Keep distinct AHI/RDI measures and same-study versus historical observations
  separate. National/local event-count interpretation and fractional rounding remain
  D2 questions; do not silently encode clinical answers in a prompt fix.
- [ ] Re-score old captures without providers where useful, explicitly as exposed
  development. A changed prompt/checker requires its own version and fresh evidence.

Preserve the original development comparisons: raw 160/166, checked 128/168, rules
154/168. These are constructed-reference agreements, not clinical accuracy.

### Durable model wiring backlog

The existing `ReviewWorkflow` leases jobs and publishes only against current state.
Its code also permits three leased attempts and explicitly notes that a crash can
repeat model calls. A job lease alone is not a provider-attempt budget or replay fence.

- [ ] Persist per-criterion attempt identity before I/O, bound to tenant/case,
  note/policy pins, candidate version and intended occurrence. Limit concurrency.
- [ ] Settle usage/response durably. Crash-left or unknown requests stay consumed;
  lease expiry must not automatically resend them.
- [ ] Enforce explicit run/lifetime budgets, expiry, route/model and approved retry
  behavior. No paid fallback. The completed study is not a standing runtime grant.
- [ ] Check current version/pins before dispatch and publication; reassess only
  invalidated criteria after supplemental delivery.
- [ ] Keep clinical text, credentials and arbitrary exceptions out of logs/traces;
  retain unknown usage/cost as unknown.
- [ ] Test denied auth, quota/timeout, malformed output, crash before/after response,
  concurrent workers, expired leases and duplicate delivery using SQL/fake SDK first.

## One decision and access register

Fill this once and refer to it from implementation. Prepare a concrete reviewable
proposal before asking for its final approval; do not repeatedly request the same grant.

| ID | Required input | Verified gap | Engineering prepares first | Owner/external input |
| --- | --- | --- | --- | --- |
| D1 | Independent clinical references | Old labels provisional; benchmark applicability unestablished; some sources gated | Source/use-rights and field/slice matrix, narrow samples and uncovered cells; qualified-evaluator proposal if warranted | Permitted source/access or qualified adjudication; acceptance of a concrete replacement method if changing reviewer requirements |
| D2 | Clinical interpretation and risk limits | PA-specific error/confidence, useful-completion, latency and recovery limits not accepted; policy ambiguities remain | Specific clinical questions, proposed limits and sample-size arithmetic tied to risks | Responsible clinical/risk acceptance before qualification outputs |
| D3 | New study/runtime model scope | Last study complete at 615/784; old stopped scope and bound slots preserved | Exact requests/inputs, candidate/environment pins, attempt/token limits, expiry, stop/accounting rules and readiness tests | Exact new scope and current Free confirmation; no unused-slot transfer |
| D4 | Deployment/recovery environment | PA host, backup destination, spending and activation unconfirmed | Portable bundle, secrets/state inventory, parser isolation, health/alerts and restore-drill plan | Exact host, private configuration, spending ceiling, activation and PA-specific recovery limits |
| D5 | Target payer/plan sandbox | Official reference service passes; commercial target/access absent | Reusable adapter/auth interface, attachment/reconciliation tests, target mapping checklist | Named payer/plan, sandbox docs/access and permitted test-data scope; credentials in private configuration |

Earlier deployment option numbers and Olist planning targets do not establish the
PA host or limits. No real-patient export follows from the invented-data grant.
Keep secrets and patient records out of this checklist/chat; system names and private
configuration locations are sufficient for access intake.

## Clinical qualification checklist

- [ ] Establish permitted access/use before acquiring or exporting a reference corpus.
- [ ] Map every required field/slice to applicable independent references. Agency
  policy prose, workflow task labels and AI consensus do not fill all semantic cells.
- [ ] Resolve interpretation with attributable evidence: national/local scope, measure,
  event definition, time interval, test method, units and deliberate contradictions.
- [ ] If using an evaluator, qualify its own errors/abstention against applicable
  independent references while blind to candidate answers; freeze it before final scoring.
- [ ] Accept risk/coverage/confidence limits before final outputs.
- [ ] Freeze unseen source/study groups; keep related edits in one split. Exposed
  development cases cannot become a fresh qualification holdout.
- [ ] Report scheduled/observed/failed/missing units. Repeated trials and correlated
  criteria do not create new independent patients.
- [ ] Preserve all eight fields: criterion state, support span, contradiction, missing
  information, disposition, no unsupported met, privacy and review durability.
- [ ] Preserve all eight slices: supported criteria, missing evidence, contradictory
  evidence, policy boundary, negation, source-family shift, prompt injection and document resume.

Existing [PA profile](evaluation/profiles/prior-auth.json) and release requirements
remain authoritative. The [source audit](prior-auth-reference-applicability.md)
records what current research does and does not establish.

## Deployment and target-payer acceptance checklist

- [ ] Record exact installed build/schema/config, provision scoped accounts and verify
  protected sessions. Admit hostile uploads only after native-worker isolation.
- [ ] Verify retention/access rules and content-free signals for queue age, model
  failure, known/unknown usage, stage latency, backup freshness and restore failure.
- [ ] Inventory legacy review tables, intake receipts/bindings/documents, recoverable
  exact sources, policies, provider-attempt state, payer journal, accounts and secret/config recovery.
- [ ] Restore into a clean target, verify rows/source pins and pending waits, then run
  authenticated import/review/resume/replay. Preserve unresolved payer/model outcomes.
- [ ] Measure host-loss data loss and restore time against accepted PA limits. An
  Olist restore or in-process synthetic test is not a PA host-loss drill.
- [ ] Verify actual target auth/scopes, attachment/document binding, response correlation,
  inquiry/RFI, stale evidence and timeout recovery without blind POST retry.
- [ ] Never translate processing-complete or A3/not-required into our clinical approval.
- [ ] Record full-conformance/commercial-onboarding gaps and the final release decision.

## Keep execution finite

Each item is ready, in progress, waiting for a named D1–D5 input, or verified with
an evidence link. A prepared packet is not an executed test, and passing software
tests do not establish clinical qualification. An invented demo may run separately;
it does not waive the original production requirements. Do not run new studies to
exhaust an allowance, relabel failures, or close release gates with missing evidence.

Next: citation completeness and opt-in durable assessor implementation, with fake/SQL
verification and deployment packaging. Then request the concrete consolidated inputs
needed for the next actual study or activation.
