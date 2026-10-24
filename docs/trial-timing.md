# Parent-measured trial timing

Inspected 2026-10-24, unmerged `codex/olist-trial-timing`, from verified main `211defc`
(#101). Scope: shared H6/H10 timing and methodology binding, including the Olist adapter.
This implements an existing operational metric; no threshold, provider run or release is
approved. [Entry 46](../BUILD_BOOK.md#entry-46--sealing-parent-measured-trial-latency)
records construction decisions. Operational measurements belong alongside quality and
safety checks; see [Langfuse's metric guidance](https://langfuse.com/academy/evaluate/choosing-what-to-evaluate).

## Trace an invented trial

The parent enters `_coordinate` at monotonic second 10, completes setup at 12, returns from
isolated execution at 17 and finishes cleanup at 20. `TrialTiming` stores 2 setup seconds,
5 execution seconds and 3 cleanup seconds. `elapsed_seconds` is their sum, 10 seconds.
These are an explanatory example, not a production benchmark.

The implementation uses `time.perf_counter`, Python's highest-resolution short-duration
clock, for every phase boundary. Older Windows `monotonic` implementations can give equal
ticks during a fast failure. Python 3.13 uses the same underlying clock for these two APIs;
the supported 3.12 interpreter needs the explicit performance-clock choice. See the
[Python clock documentation](https://docs.python.org/3.12/library/time.html#time.perf_counter).
Worker timeout/deadline accounting retains its original clock and allowance.

[`TrialTiming`](../harness/src/agent_harness/trials.py#L142) accepts finite nonnegative durations,
rejects an overflowing total and fixes the measurement version to `parent-trial-monotonic-v1`.
The parent measures three contiguous intervals in
[`_coordinate`](../harness/src/agent_harness/trial_runner.py#L188):

- Setup: abort check, environment preparation and fixture validation.
- Execution: spawn serialization/start, workflow/model activity, scoring and owned worker reaping.
- Cleanup: release of disposable state and its error handling.

The child result frame has no timing field. Timeout, crash, startup/setup errors and failed
cleanup still return terminal rows with parent measurements. After unreaped-worker failure,
state remains retained and later aborted rows have zero execution/cleanup, an explicit error
and measured abort-check setup. Zero execution in that path is not a successful trial.

This interval excludes executor queueing, journal I/O, source verification and final evidence
sealing. It is evaluation-trial elapsed time, not customer response time or provider latency.
Monotonic durations do not derive from RunContext's fixed simulation clock or receipt UTC
timestamps. They describe the measured host; replay timing is not fresh-provider timing.

## Binding and historical compatibility

The exclusive journal saves timing inside `TrialRow`; H10 already seals the complete batch
digest. Editing or removing timing changes that digest and blocks evidence read-back. This
does not provide authenticated clock attestation: the trusted parent, pins and executing
source inventory remain part of the evaluation trust boundary.

`TrialRow.timing` defaults to None and is omitted only when absent. Old canonical rows and
batch hashes therefore retain their exact meaning. Reading an old journal does not add a
zero measurement or backfill from receipt timestamps. Do not migrate sealed evidence.

[`verify_binding`](../harness/src/agent_harness/evaluation_binding.py#L18) requires each methodology
row's elapsed_seconds to equal the saved timing sum exactly. An absent timing requires None.
The existing conservative dispatch-span lower bound also remains. Increasing latency by a
plausible amount is rejected just like understating it. An old unknown value can bind, but
the methodology audit still blocks qualification on unknown latency. No qualification or
deployment decision follows from timing alone.

## Verify and explain the boundary

Run `python dev.py check` for the shared contracts, actual spawned success/crash/timeout,
setup/cleanup/start errors and unreaped-worker abort checks. Focused checks are in
[test_trials](../tests/test_trials.py), [binding mutations](../tests/test_evaluation_binding.py)
and [journal tampering](../tests/test_release_recording.py). Deterministic parent ticks make
it possible to catch a timer accidentally excluding setup or cleanup without fragile speed
thresholds. Real spawned tests establish that terminal timing survives actual failure paths.
The [Olist SQL/H10 checks](../tests/integration/test_olist_h10.py) verify measured setup and
cleanup while recording three mock dispatches per scenario in restricted Postgres databases.

Interview exercise: explain why a timer inside the worker cannot measure owned cleanup,
why a receipt span cannot replace the complete interval, and why omitting absent timing
preserves old pins. Then explain what this does not prove: representative quality, blind
labels, known costs, realistic user latency, full OS crash/restart evidence or release.

No provider calls occur in these tests. Complete study projection, representative source
coverage, appropriate label/baseline/threshold reviews, cost provenance and final-candidate
fresh evidence still gate #33 and downstream releases. Test results are recorded on the
implementation PR after execution.

Local verification: full locked check 1,042 passed in 619.23 seconds; 151 typed sources,
228 formatted files, lint/import/lock checks passed. Focused trial/binding suite 78 passed
in 90.96 seconds. Relevant refund/failure SQL/H10 scenarios 2 passed in 159.78 seconds
(3 unchanged scenarios deselected locally), with six new mock dispatches. Six package pairs
built; audit clean. Installed 61 harness/35 Olist resources matched, timing roundtrip and
legacy omission passed, provider SDKs/other verticals absent and network-denied replay made
zero provider calls. Historical inventory/report and private cohort pins remain unchanged.
Hosted full matrix and complete database-suite acceptance remain pending at this writing.

The initial hosted run 40116936759 passed three quality cells and all 110 database checks,
but Windows/Python 3.12 failed two new positive-duration assertions for immediate setup and
pickle errors (1,040 passed, 2 failed). The corrective change uses `perf_counter`; the
deterministic regression freezes `monotonic` at zero while advancing only the performance
clock. Assertions and budgets are unchanged; no sleeps or fabricated minimum durations.
The preceding local full-suite/SQL results describe the initial head. Focused checks and a
new synchronized-head hosted matrix must verify the clock correction; the failed run stays
part of the evidence history, with no unchanged-head rerun.

Clock correction verification: strengthened focused suite78passed99.15s; lint and151typed
sources passed. Six package pairs rebuilt; corrected installed61harness/35Olistresource
bytes/composition pins matched with network denied and zero-provider6callreplay. The prior
full local1042test/2SQL pass is retained as initial-head evidence; final synchronized-head
CI must rerun the complete matrix/110DB checks. No unchanged-head retry or provider call.
