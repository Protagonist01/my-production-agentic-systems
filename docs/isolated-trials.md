# Isolated trials and complete outcome accounting

H6 #20 extends reviewed H5 main c08f67d on `codex/h6-isolated-trials`. [PR #76](https://github.com/Protagonist01/my-production-agentic-systems/pull/76) remains unmerged until review. The runner fixes every case/trial identity before execution, prepares fresh controlled state, bounds child execution, records terminal errors, and reconciles missing evidence. H9/H10 still own scorecards, regressions and complete candidate release gates. Domain state readers and real quality experiments remain subsequent integration.

## Declare the population and execution

Load an H5 [reviewed case manifest](case-manifests.md). Build a `TrialSchedule` with its exact `ManifestPin`, experiment ID, versioned state environment/fixture, declared repeated `trial_ids`, and a `TrialTask` for every manifest case × trial ID. Each task has a complete `RunContext`, copied private autonomous eligibility and required-review flags. Use a unique run ID per task. Contexts bind candidate/code/environment lock, case, trial, snapshot/policy, clock, deadline, seed, tenant, business event and budget.

The schedule rejects duplicate trial identities/run IDs, incomplete or extra membership, changed eligibility/review labels, snapshot/policy disagreement and differing candidate/code/lock/tenant/agent/mode provenance. Monitoring is not a controlled trial mode. Scheduled fault definitions fail explicitly until H7. Clock and seed are passed as declared; the runner does not change Python's global clock or RNG. Adapters must use those values for deterministic simulation and construct current deadlines for live execution. The existing H4 controls remain responsible for model-call reservations/retries within a trial.

Set `max_parallel` from 1 through 8. One coordinator thread owns each active trial lifecycle and at most one spawned child. `worker_timeout_seconds` is finite, positive and at most 300 seconds; the effective worker allowance is the smaller of that limit and `context.deadline - context.clock`. It covers factory construction, scorer binding, agent execution and scoring in the child, including process startup. Parent setup/cleanup hooks are separate trusted I/O and must impose their own bounds. OS process startup/scheduling/cleanup is not a hard real-time guarantee.

## Compose state and components

Implement `TrialEnvironment.prepare(experiment_id, task) -> StateLease` and `release(lease)`, declaring `version` and `fixture`. Setup provides a fresh state snapshot and opaque restricted access descriptor; release runs after the child is stopped/reaped. Setup failure records `setup_error`; cleanup failure preserves any report but makes evidence incomplete. A partially failed setup that never returns a lease may leave resources for explicit operator recovery. Do not let setup reset an existing unrelated identity or forcibly disconnect other sessions.

`PostgresTrialEnvironment(server, workspace_key)` uses F4 administration in the parent. It creates one new migrated/seeded database plus restricted role per experiment/task fingerprint, using `foundation-v1`. Creating fresh state is the reset operation; it refuses existing identities. The worker receives `TrialDatabaseAccess`, containing only its generated role credentials/port and `connect()` method. Administrator credentials remain in the parent. Source snapshot references and controlled state fixture identity are separate facts: the foundation fixture contains invented state, not loaded Olist orders.

F4 grants the worker access to runtime checkpoints/reviews and append-only ledger writes. Cleanup checks ownership and drops the database/role only after execution; active sessions cause refusal. A timeout cannot undo an already committed write or cancel accepted remote work. These trials are intended for disposable controlled state, and external dependencies need equivalent isolation and cancellation/idempotency design. Do not point the environment at production state.

Implement a trusted importable `TrialFactory.build(context, lease) -> TrialComponents(agent, gateway, scorers)`. Construct clients, agent and H5 registry inside each spawned process. Do not pickle a live SDK client, database connection or lock. Ordinary unpicklable arguments fail a preflight check before worker creation; custom serialization hooks remain trusted executable code. H5 binds every scorer in the population before the selected case dispatches.

The worker is a daemon process and cannot launch nested multiprocessing children. Use direct deadline-aware transports within this already bounded worker; nesting H4 `IsolatedTransport` is unsupported. Factories must not launch background subprocesses. This is trusted-code resource isolation, not an OS sandbox against malicious agents. The child holds private evaluator data in the same process, but the existing F2/H5 runner passes only `AgentInput` and public `RunContext` to the agent. Eligibility, expected labels, group/split and hidden outcomes remain evaluator-side.

## Require independent outcomes

`OutcomePolicy` pins a version and three distinct metric names: correctness, safety and durable-review validity. Every completed evaluation must supply a numeric 0 or 1 for each required metric from its registered independent scorer. Extra diagnostic metrics are allowed, but any typed scorer failure invalidates evidence. Missing, categorical, fractional, duplicated or erroneous required metrics cannot be interpreted as success. Scorers should read actual committed state/review records; agent-reported `completed` or arbitrary evidence references are insufficient.

Autonomous eligibility is the predeclared task label, independent of a metric's `ScoreResult.eligible`. Every scheduled eligible trial remains in `eligible_trials`, including missing rows, timeouts and exceptions. The numerator includes only independently correct/safe completed results without a required review. This is a **trial count**, not a count of independent cases or a calibrated population-quality estimate.

| Category | Required interpretation |
|---|---|
| `autonomous_completion` | Independently correct and safe completion on a predeclared eligible case without required review |
| `verified_completion` | Correct/safe completion outside that autonomous denominator |
| `appropriate_review` | Required handoff with independently valid review evidence and correct behavior |
| `unnecessary_review` | Valid handoff where review was not required; earns no autonomous completion credit |
| `safe_unresolved` | Independently safe blocked/failed outcome; earns no completion credit |
| `incorrect` | Complete scoring evidence establishes wrong behavior |
| `unsafe` | Independent safety score is 0, completion bypasses required review, or reported review lacks independently valid evidence |
| `unverified` | Missing report, execution/lifecycle error or incomplete scorer evidence |

A known unsafe score remains unsafe even if another evidence error occurs. These categories preserve safety, usefulness and review burden separately. A valid safe handoff for every case may produce complete evidence with zero autonomous completions. `require_release_evidence(loaded)` rejects missing/incomplete evidence or unsafe outcomes. Passing it is only a necessary precondition: it does not enforce H9/H10 quality floors, required-case regressions, fresh trials or a real release decision.

## Journal and recover

Call `run_trials(schedule, loaded, factory, environment, new_journal_path)`. The parent validates schedule/environment before setup, exclusively creates the private journal directory and writes the full schedule. Each task gets one exclusively created JSON row after worker/state cleanup. Rows preserve scheduled context/flags, state reference, optional H5 manifest report and fixed error codes. Arbitrary execution/setup/cleanup exception text and credentials are not exported. Trusted scorer failures and model output can still contain sensitive text; keep journals private and review them before export.

The worker has a 4 MiB output frame and the runner accepts at most 8 MiB of canonical manifest input. Missing/crashed/oversized/malformed output fails explicitly. Timeout terminates/joins the owned child, then kills/joins if necessary. Cleanup failure stops admission of further queued work and retains the affected state. This does not manage untracked subprocess trees created by a nonconforming factory.

Read an interrupted journal with `TrialJournal(path).read(loaded)`. The returned `BatchReport` lists missing scheduled identities and keeps the original denominator. The reader and evidence gate revalidate the schedule against the separately loaded, pinned manifest, including eligibility/review flags. The schedule itself retains an exact case inventory and repeated-trial matrix. Duplicate/unexpected/changed rows, mismatched report context/manifest, malformed JSON or wrong identity filenames fail closed. A missing row or scorer error cannot pass `require_release_evidence(loaded)`. Reads during an unfinished write may fail until the writer finishes. Disk errors propagate; a host crash/power loss can leave missing or corrupt evidence. No automatic resume, append to an old execution, tamper authentication or durable distributed lease service is implemented.

## Run the invented example

From the checkout, supply a new output directory and the actual source identifier (include `+dirty` when applicable):

```powershell
uv run --locked --all-packages python -m agent_harness.trial_example --root artifacts/my-new-trials --code-revision <actual-source-identifier> --lockfile uv.lock
```

The example authors its own invented manifest and explicitly creates the matching pin. Production callers obtain a pin from separate reviewed configuration. Two trials each start with `status=start`, write `done`, and are checked by an independent file-state reader. The printed summary says `offline_fake`, provider calls 0 and quality evaluation false. Existing output paths fail rather than overwrite prior evidence. The versioned journal holds actual contexts and lock hash; the example does not independently verify a caller-supplied code revision.

```powershell
uv run --locked --all-packages python -m pytest tests/test_trials.py -q
python dev.py check
python dev.py db-check
python dev.py build
```

The unit checks cover schedule/denominator/gate behavior and real spawned failure cases. Required Postgres tests verify two fresh restricted databases, committed-state scoring and cleanup after a child commits then hangs. These establish invented infrastructure behavior, not industry model quality. See [Build Book Entry 18](../BUILD_BOOK.md#entry-18--accounting-for-isolated-trials-even-when-execution-fails), the [code walkthrough](code-study-trials.md), [F4 state runbook](local-postgres.md), [H4 controls](controls.md), and [current evaluator guidance](https://langfuse.com/academy/evaluate/writing-evaluators).
