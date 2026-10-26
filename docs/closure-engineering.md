# Closure engineering: resource accounting and bound observations

Unmerged `codex/release-closure`, based on verified main `21cfea9` (#106), inspected
2026-10-25. This chapter describes code and invented acceptance runs, not completed
Olist/CFPB/Revenue release experiments. See [the closure plan](release-closure-plan.md)
for the independent review and study gates that remain.

On 2026-10-26 the user authorized autonomous implementation PR merges and left independent
reviewer responses pending. This authorizes merging verified code, not inventing review
judgments. CFPB import now preserves the actual masking-review reference and original/edited/
invented provenance; non-synthetic cases without that reference reject before database setup.

## One shared allowance

[`ProviderAllowance` and `AttemptLedger`](../harness/src/agent_harness/provider_budget.py)
describe one Gemini Free allowance, capped at 180 across Olist, CFPB and Revenue.
Every dispatch, including internal classifier escalation, needs its own reservation.
The allowance is not 180 per agent or experiment. The live allowance remains unused.

The initialization inputs are an allowance ID, the actual human authorization reference,
a hash identifying the configured project, the approved models, and an explicit validity
interval. Do not infer a billing project from an API key's spelling. Confirm its identity
and Free configuration in the operator account; keep the key and project evidence private.
Do not fabricate review references or dates to fill a sample file.

To prepare the frozen configuration without dispatching:

1. Serialize a `ProviderAllowance` as canonical JSON outside Git; hash it with `pin()`.
2. Call `initialize(private_path, allowance)` once. The parent directory must already
   exist. Exclusive creation refuses to overwrite an existing or exhausted allowance.
3. Construct `AttemptLedger(private_path, separately_recorded_allowance_sha256)` and
   share **that same path and pin** across all workers and all three compositions.
4. `ledger.summary()` returns maximum, consumed, remaining and unsettled counts. Reading
   status makes no provider calls. Archive the allowance and status with the study manifest.
5. Freeze the tariff and `GeminiCaptureControls.sha256` in `CandidateSpec` before recording.
   Review the candidate/cohort/protocol and human judgments before any final capture.

The equivalent preparation/status CLI is `python -m agent_harness.provider_budget initialize
--ledger <private-db> --allowance <canonical-file> --allowance-sha256 <external-pin>`;
use `status --ledger <same-db> --allowance-sha256 <same-pin>` to inspect it. These commands
cannot dispatch, reset an allowance or approve a study. Replace placeholders with actual
reviewed values; no real allowance was initialized by the invented test fixtures.

`reserve()` opens the existing SQLite file in read/write mode and uses `BEGIN IMMEDIATE`.
Within that transaction it checks the authorization pin, fresh agent/route/model/project
scope, validity and deadline, then counts and inserts one reservation. The transaction
commits before the delegate runs. This is why simultaneous workers cannot each see the
same last slot. Opening the ledger after restart retains consumed attempts.

`settle()` adds the raw response digest once. A timeout, exception, process death, parse
failure or lost response never refunds a reservation. Unsettled means unknown outcome,
not permission to retry without consuming another slot. SQL triggers reject ordinary
deletion/rebinding and repeated settlement. The trusted filesystem owner could replace or
edit the database: these controls prevent accidental overspend through these compositions,
not malicious administrator tampering or calls made outside them. Keep one authoritative
private ledger; do not copy it to create independent spending capacity.

## Raw, derived and missing costs

[`cost_accounting.py`](../harness/src/agent_harness/cost_accounting.py) does not rewrite raw
provider billing as fact. Successful text attempts with complete token accounting can carry
an explicit tariff-derived zero USD cost, with the original unknown `Usage`, raw provider
usage metadata, exact request hash, tariff document/hash, derivation time and shared
allowance pin retained. The basis says `not-provider-billing`. Failed responses and missing
token counts stay unknown and cannot satisfy complete release usage evidence.

`FreeTariff` requires the pricing-source snapshot hash, actual project hash, operator Free
attestation reference, review reference, model allowlist and expiry. The official
[Google pricing page](https://ai.google.dev/gemini-api/docs/pricing) lists Free input/output
for the configured Flash-Lite and Flash text models at inspection. This does not establish
the operator project's tier. Save/review that source snapshot and project attestation before
use; no live tariff review or billing inspection was performed by the invented tests.

[`GeminiCaptureControls`](../harness/src/agent_harness/provider_capture.py) composes:

```text
bounded gateway -> AccountedTransport -> BudgetedTransport -> GeminiTransport
                    preflight tariff     reserve before SDK; settle raw response
                    retain raw + derived usage after SDK
```

Its hash binds allowance, tariff and project; credentials are excluded from that hash
and object representation. Each domain's provider factory requires this exact hash in
the candidate specification. The receipt reader recomputes the accounting attachment
and matches its control hash to that externally pinned candidate. Unattached raw provider
costs remain readable; a derived attachment without a candidate control pin is rejected.
Absent new optional fields are omitted so historical response/spec bytes remain stable.

## Explicit deterministic baseline approval

The release API accepts the separately verified deterministic baseline only with
`DeterministicBaselineApproval`, which names the algorithm, dataset and source/spec pin
as well as the actual baseline evidence and release policy. The command requires
`eval-release --baseline-kind deterministic`; ordinary provider comparison remains explicit.
The deterministic baseline never becomes a fresh provider candidate.

Capture/approval order, current candidate dispatch receipts, same paired population,
scorer/policy/environment/seed/budget/event conditions, required-case failures, regressions,
age limits and methodological checks still apply. `ReleaseDecision` remains an
`evidence_gate_only` decision. Choosing a comparator does not supply human approval or
production release. This follows the explicit-baseline and case-regression approach in
[Langfuse's comparison guidance](https://langfuse.com/docs/evaluation/experiments/compare-experiments).

## Olist supplementary crash binding

[`fault_binding.py`](../projects/olist-support/src/olist_support/fault_binding.py) reads a
canonical, externally pinned `FaultBundle`. It binds candidate spec/evidence, dataset,
scheduled context and each before/after-commit artifact. The operator supplies the required
context hashes from the separately frozen protocol; the bundle cannot choose its own
coverage requirement. Duplicate, missing, unexpected or differently scoped boundaries reject.
Each underlying crash artifact is independently recomputed against the frozen policy case.

Artifacts live under `<context-sha256>/<before_commit|after_commit>/crash.json`, beside
`bundle.json`. Drills use the scheduled context with offline mode and a stage-suffixed run
ID. They execute an operator-selected SIM refund and owned process hard exit, then verify
SQL rollback/commit, restart and duplicate results. The report explicitly marks mechanism
only, zero provider calls, incomplete full fault matrix, and no release authorization.
This is supplementary evidence, not a replacement for model behavior or all required faults.

## CFPB durable capture

[`workflow_recording.py`](../projects/cfpb-triage/src/cfpb_triage/workflow_recording.py)
adds a distinct `cfpb-durable-h10-v1` scorer/composition. The trusted parent prepares a new
database/role for each trial, imports only the selected reviewed input and seeds another
tenant with an invented private canary. That canary's job is ineligible for classification;
the workflow never depends on tenant sort order to claim its own work.

The worker receives restricted access and closed complaint input. It claims the current
job, runs the existing classifier through a gateway that allows exactly the pinned prompt,
taxonomy, route/parameters and narrative-only public projection, and publishes the typed
decision. It reconstructs the store, reads the persisted result, attempts duplicate
publication, and checks unauthorized resource scope. It records scoped before/after/rebuilt/
duplicate snapshots, public requests and persisted content pins. No session/key is recorded.

The independent scorer reconstructs the exact expected job, event and status delta, requires
unchanged version/commands, compares persisted source/result hashes, checks restart/duplicate
equality and canary absence in actual requests and decision. Read-back also requires the saved
requests to equal actual dispatch receipts. It recomputes scores/results and rejects changed,
missing or extra sidecars. Tests use invented transport output with `origin=mock`; only the
provider composition can produce provider origin, and it requires shared controls.

Privacy scope is the declared model-input/output and one scoped access-denial probe. This
does not claim a universal privacy audit, masking correctness or a complete injection suite.
Those require their reviewed populations and final studies. A correct durable failure decision
does not count as a correct classification.

## Revenue scopes and bound SIM effects

[`provider_recording.py`](../projects/revenue-integrity/src/revenue_integrity/provider_recording.py)
provides the original-span provider factory with shared controls, closed context/question,
existing literal-span verification and pinned private observations. It keeps the partial
scorer's unobserved semantic/business fields as errors. No original quote can authorize
an invoice mutation.

[`study_evidence.py`](../projects/revenue-integrity/src/revenue_integrity/study_evidence.py)
provides separate original-extraction, SIM-billing and SIM-effect checks. `ApplicableCheck`
requires a reason and no pass value for N/A, and a bound reference for an observed result.
An applicable missing judgment stays unobserved. Original zero-span precision/recall are
undefined with no pass credit; missing answers still fail recall, and execution health
remains applicable even when a denominator is zero. Literal citations and arithmetic never
fill qualified `supported_terms` review automatically.

`EffectTrial` binds candidate and full context to invoice expectations and SQL snapshots.
`assess_effects()` checks wrong-tenant/missing-capability/self-review denials left all state
unchanged, recomputes the exact correction/ledger/result, checks reconstruction/redelivery,
and verifies a separately approved compensating receipt. It requires the exact inverse amount,
version, resource, operation link, actor/reviewer, validity, run ID and deterministic ledger ID;
all unrelated records/proposals/ledger rows remain unchanged. Missing compensation is unobserved.
This recovery scope is store reconstruction/redelivery, **not hard process death**. The module
does not relax the current whole-profile gate or qualify a final scoped release profile.

## Verification and exercises

The targeted suites are `test_provider_budget_accounting.py`,
`test_deterministic_release_approval.py`, `test_revenue_study_applicability.py`, and the
three SQL suites `test_cfpb_workflow_recording.py`, `test_revenue_bound_effects.py`,
`test_olist_crash_evidence.py`. Run SQL explicitly with `-o addopts=''`; the normal offline
suite excludes `tests/integration`. Hosted CI also runs the required database suite.

Try changing a tariff hash, copying an approved algorithm name onto another dataset,
requesting more crash scopes than the bundle contains, removing a CFPB duplicate guard,
or altering an undo ledger ID. Explain which external pin or independent state check must
reject each change. Then explain why an ordinary passing test, derived Free cost, literal
citation or operator crash drill cannot substitute for independent reviewer judgments.
