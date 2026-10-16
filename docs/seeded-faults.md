# Seeded fault drills and state invariants

H7 #21 extends reviewed H6 main 9c13b2c on `codex/h7-seeded-faults`. It is unmerged. It executes explicit offline boundary faults and preserves their evidence through H6 accounting. It does not inject failures into production services, implement domain recovery policy, or establish a model-quality/release threshold. The invented example uses files; the required database checks independently inspect real disposable Postgres state/ledger rows.

## Declare a reviewed treatment

Keep expectations in the pinned H5 `EvalCase.faults`: each `FaultScenario` has an ID, target, timing, predeclared recoverability, expected safe behavior and required invariant metric names. Create a separately reviewed `FaultPlan(version, rules)` with exactly the scenario IDs in the population. Each `FaultRule` supplies a supported kind/target/timing, payload where applicable and an inclusive occurrence window from 1 through 100. At most 64 rules are allowed. Duplicate IDs, missing/extra rules, mismatched target/timing, empty/duplicate invariant names and conflicting selected hooks fail before state setup.

| Kind | Target | Timing | Injected behavior |
|---|---|---|---|
| `malformed_output` | `model` | `after_dispatch` | Call the delegate, then replace successful assistant output with declared text; preserve measured usage |
| `outage` | `model` | `before_dispatch` | Return typed unavailable without invoking the delegate; zero delegate calls, token/cost observations unknown |
| `stale_read` | `tool:<adapter-name>` | `after_dispatch` | Execute the real read, then substitute a cloned declared JSON value |
| `tool_timeout` | `tool:<adapter-name>` | `before_dispatch`, `after_commit`, `on_resume` | Raise `InjectedToolTimeout` at the explicit boundary; do not automatically retry |
| `duplicate_delivery` | `tool:<adapter-name>` | `after_dispatch` | Execute the same trusted callback a second time |
| `injection_content` | `input` | `before_dispatch` | Append declared untrusted text as a public observation; private expectations stay evaluator-side |

Occurrence is selected by SHA-256 of the JSON array `[plan.version, scenario_id, context.seed]`, reduced into the inclusive window. The implementation does not use global RNG state or wall-clock sleeps. Counts are local to a target/timing pair. Changing the window/payload changes the full plan digest. A new trial gets a new session with the same declared seed when exact treatment repetition is wanted. Different seeds may select the same occurrence; a seed is not statistical independence.

## Compose explicit hooks

Add `fault_plan` and exact `fault_case_ids` to the H6 `TrialSchedule`. The latter must equal the cases with fault declarations. The existing matrix, context, manifest/labels, process bounds and state isolation checks still apply. `run_trials` creates the session inside the owned worker. For a fault case the trusted factory must implement:

```python
def build_faults(context, state, faults) -> TrialComponents:
    # Build a fresh agent, gateway and independent scorer registry.
    # Give trusted tool adapters the same session.
    ...
```

No-fault cases still call `build(context, state)`. Fault-aware composition is explicit; a factory that only implements `build` produces terminal execution errors on fault cases. Binding the H5 case consumes a new session exactly once, projects public input, wraps the model gateway and runs the agent/scorer. Fault expectations and invariant labels are not serialized into public input. This is trusted in-process composition, not isolation from malicious Python introspection.

Wrap tools with `faults.invoke("tool:write", callback, committed=True, resume=False)`. A successful callback with `committed=True` declares that its transaction is already committed before the `after_commit` hook. The harness cannot discover the commit point for an arbitrary adapter. Do not set that flag around a lazy value or an open transaction. `resume=True` explicitly enters the resume hook; it does not restore a checkpoint or simulate an actual OS restart. The callback owns transaction semantics, stable operation keys and authorization. A timeout after commit leaves the effect present; reconcile actual state before retrying. Duplicate delivery calls the callback twice and does not supply idempotency automatically.

Hooks execute on the session's binding thread. Cross-thread calls fail rather than making occurrence ordering depend on thread scheduling. Across trials, H6's existing bounded process concurrency still applies. Sessions cannot be reused or exercised before binding. Do not compose a simulated outage as observed provider work or infer provider latency from these offline hooks. H4 admission/retry/circuit controls remain separately composed application machinery; this increment does not claim a live fault experiment against them.

## Inspect actual state and classify outcomes

`inspect_state(StateObservation, StateExpectation)` compares independently read state, effects and durable reviews with reviewed expectations. An `Effect` carries a stable operation key, target, actor and payload digest. The expected allowlist is supplied by evaluator policy, never by the agent result. The checker requires:

- At most one observed effect per operation key (`effects_once`).
- Every observed effect exactly matches an allowed key/target/actor/payload (`authorized_effects`).
- Exact final state plus exactly one effect for each required operation key for correctness.
- Unique durable review references with the expected business event and an allowed reason for valid review evidence.

These are comparison primitives. A real adapter must read the complete relevant state/ledger scope, derive actors/payload digests from authoritative records and obtain an independent policy allowlist. A false allowlist or a reader that omits effects invalidates the conclusion. The library does not implement production permission checks, business operation keys or tamper-proof ledgers. Missing/malformed read evidence raises an error; it does not become a zero-risk pass.

Independent scorers return H6's distinct correctness, safety and review metrics plus every declared invariant as numeric 0/1. A missing/categorical/errored invariant makes evidence incomplete. A known zero invariant is unsafe even if other evidence is incomplete. Existing eligibility denominators remain fixed. `fault_category(row, assessment, recoverable=...)` keeps `recovered`, `appropriate_review`, `safe_unresolved`, `unsafe`, `incorrect` and `unverified` separate; completion on a case declared unrecoverable is `unexpected_completion`. Supply recoverability from the separately reviewed case. A safe unresolved outage is not recovery, and a handoff earns no autonomous completion credit.

## Preserve and recover evidence

`CaseReport.fault_evidence` stores plan version/digest, private-declaration digest, seed, expected scenario/invariant IDs and ordered metadata-only events. Each event identifies kind, target, timing and selected occurrence; it omits payload text, tool results and private labels. This additive evaluator-report field changes strict serialized report readers; update readers together. Model request/response wire version 2 and existing no-fault invocation interfaces remain unchanged.

An unreached hook yields a report with incomplete fault evidence, even when the agent claims completion and ordinary scores pass. A thrown exception still follows H6 terminal error accounting. H6 recovery checks event identities, occurrence, invariant inventory and declaration digest against the reviewed case/plan. Reopen a fault journal with:

```python
report = TrialJournal(path).read(loaded, fault_plan=reviewed_plan)
report.require_release_evidence(loaded, fault_plan=reviewed_plan)
```

The separately reviewed plan is required; accepting a changed journal's own embedded plan would authorize an altered treatment. The running coordinator already holds the plan it validated before setup. Missing rows, missing fault evidence, scorer failures, unreached hooks, incompatible plans or unsafe results cannot pass this evidence precondition. No signed journal, automatic resume, quality floor or full H9/H10 release decision is added. Private reports can still contain model/state/scorer text, so H6's privacy and export limitations remain.

## Run the invented drill

Use a new ignored output directory and an actual source identifier (include `+dirty` if applicable):

```powershell
uv run --locked --all-packages python -m agent_harness.fault_example --root artifacts/my-new-fault-drill --code-revision <actual-source-identifier> --lockfile uv.lock
python dev.py check
python dev.py db-check
python dev.py build
```

Eight invented cases cover the six kinds plus distinct tool timeout boundaries. The careful agent should produce seven recovered outcomes and one appropriate durable review, with seven eligible autonomous completions. The factory restricts the example to `offline_fake` and uses fresh file state. The CLI explicitly enables network audit denial in its spawned workers and parent; ordinary inline factory composition leaves global audit hooks unchanged. Audit hooks are process-wide and irreversible, so enable that example option only in the intended isolated worker. The scorer reopens state/ledger rather than trusting the agent's `invented-ledger` reference. This narrow fixture establishes mechanism behavior, not industry quality or prompt-injection resistance in a real application.

Acceptance includes repeatability, seeded occurrence windows, unreached hooks, missing/tampered metadata/plan, ordinary and spawned trials, duplicate writes, an unauthorized actor and claimed success during outage. Real Postgres additions commit an effect before the injected timeout and inspect it through another restricted connection; negative duplicate/unapproved-actor cases must fail the independent checks. Final results are recorded in [Build Book Entry 19](../BUILD_BOOK.md#entry-19--reproducible-faults-at-explicit-execution-boundaries), the PR and #21. See the [source walkthrough](code-study-faults.md), [H6 runbook](isolated-trials.md), [case manifests](case-manifests.md) and [deterministic evaluator guidance](https://langfuse.com/academy/evaluate/writing-evaluators).
