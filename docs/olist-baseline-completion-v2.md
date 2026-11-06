# Olist service baseline capture and parent diagnostics

Prepared 2026-11-05, Africa/Lagos, on `codex/olist-baseline-readiness` from verified main
`3483484` (#139). Executable capture source: `0e324129887d9c691902ae06fc4fbf6734f26a39`.
This chapter covers parent trial diagnostics and the separate zero-model development run.
It does not establish language qualification, production-host performance or release.

## Failure that motivated the change

The [earlier capture](olist-evidence-method-audit.md#interrupted-baseline-observations-and-honest-denominators)
has27verified reports, one setup error and26abort placeholders, with no sealed baseline.
The old runner intentionally avoided exposing arbitrary exceptions, but saved no bounded
cause detail. Both queued aborts and physical worker-reaping failures shared the legacy
`worker_cleanup_error` code. Reading that code as26failed process cleanups would be wrong.
The original journal, output inventory and unknown outcomes remain unchanged.

## Code path and privacy boundary

In [trials.py](../harness/src/agent_harness/trials.py), `TrialDiagnostic` declares an actual
error code, origin, optional fixed exception category and optional SQLSTATE. Origins are
`exception`, `prior_trial_abort` and `identity_mismatch`. A caught exception needs a category;
other origins cannot invent one. SQLSTATE requires the database category. Abort/identity
origins bind their original legacy error codes, and `TrialRow` rejects diagnostics whose
code is absent from its actual errors. This is causal metadata, not a correctness score.

The new tuple is omitted when empty. Historical canonical rows without diagnostics therefore
round-trip byte for byte, retaining their original hashes. New error rows bind diagnostics
in their own canonical journal hash; historical rows are not retroactively annotated.

In [trial_runner.py](../harness/src/agent_harness/trial_runner.py), `_coordinate` keeps the
existing setup/execution/release/abort order. Each caught parent-side exception calls
`_exception_diagnostic`; a prior abort records its distinct origin without entering another
worker. If abort arrives after setup, release still runs. An unreaped worker still sets
abort and withholds state release; no diagnostic makes that resource safe to reuse.
An invalid returned report identity retains `invalid_frame` with `identity_mismatch`.

`_exception_diagnostic` classifies known exception families using `isinstance`. It never
calls `str(error)`, saves arbitrary class names, copies SQL/connection details or records
traceback locals. For database exceptions, only a recognized library SQLSTATE is emitted:
look up the class code and use the known class's canonical value. Unknown codes remain null.
Client-side connection errors may have no server SQLSTATE. This uses the documented
[Psycopg error API](https://www.psycopg.org/psycopg3/docs/api/errors.html), verified against
the installed locked3.3.6; the current documentation is3.3.8. No dependency was upgraded.

For example, an invented parent setup `DiskFull` becomes `setup_error`, origin`exception`,
category`database`, SQLSTATE`53100`. Its password/source-like message stays absent. This
tests classification; it does not establish that disk exhaustion caused the old capture.
Worker-internal exceptions retain their existing generic codes. The new cause metadata
covers parent setup, execution coordination and cleanup, not full distributed diagnosis.

## Host readiness and separate capture

Docker was stopped at continuation. Starting Desktop under existing authorization restored
engine29.8.2. Only about0.65GBRAM and0.8GBonC:were free. The owner explicitly authorized
temporarily stopping the six existing Langfuse containers and restoring them afterward.
Record original immutable IDs/names/running states privately before stopping anything;
no data/volume deletion is part of that authorization. Free RAM then measured about3.2GB.
Those readings describe this host, not a proven cause of the old failure.

All25new diagnostic checks pass, alongside64existing trial checks from the earlier focused
run. Six actual PostgreSQL/service readiness checks pass in122.71seconds: exact amount and
customer confirmation, prefix/partial request handling, wrong amount/intent withheld without
effect, response-loss recovery, three-trial H10 recording/readback and owned-trial cleanup.
Their gateway responses are invented; they make no provider-quality claim.

The new capture has its own source inventory, code revision, manifest, protocol, task IDs,
time interval and output directory. The eighteen wholly fictional development scenarios
and five dependent parent/order groups are unchanged. Schedule54rules and54always-review
rows using three isolated trials per scenario. Keep54model-candidate rows absent rather
than populating them with invented decisions. `DenyModels` and usage guards require zero
model/token/cost consumption by both executed algorithms.

Before each algorithm, recheck exact executable sources. After each, perform strict H10
and domain observation readback and verify all54owned database/role pairs are absent.
After successful workspace teardown, verify its container/volume labels are absent, then
write completion. A failure keeps its journal, bounded failure diagnostic and private parent
stdout/stderr streams; no automatic retry/resume or synthetic seal is allowed.

Private run: `D:/document/.cache/production-agents/olist/service-development-baselines-2026-11-05-v2`.
Readiness/pause/parent streams: `D:/document/.cache/production-agents/olist/baseline-host-readiness-2026-11-05-v1`.
The old v1 capture and provider ledger are not execution inputs to be resumed.

## Completed observations and independent readback

The separate capture completed on 2026-11-05. Strict readback on 2026-11-06 revalidated
the original packet and executable source hashes, reread both sealed baseline captures,
recomputed every observation and reproduced the saved comparison exactly. The original
interrupted v1 inventory is unchanged. The [public aggregate](data/olist-service-baselines-development-v2.json)
binds the package, protocol, manifest, baseline and report hashes.

| Measure | Rules | Always review |
| --- | ---: | ---: |
| Observed / scheduled trials | 54 / 54 | 54 / 54 |
| Whole-service correct | 0 / 54 | 0 / 54 |
| Routing/state safety | 54 / 54 | 54 / 54 |
| Joint intent and amount agreement | 0 / 54 | 0 / 54 |
| Eligible completion | 0 / 12 | 0 / 12 |
| Required review with expected routing/reason | 0 / 39 | 0 / 39 |
| Observed review | 54 / 54 | 54 / 54 |
| Cases passing all three repetitions | 0 / 18 | 0 / 18 |

Both algorithms send every case to review. Observed review alone does not satisfy a
required review's expected action and reason, or complete an eligible action.
These results establish observed containment but fail useful whole-service behavior on
this constructed package. They do not approve either baseline or change any threshold.
The model candidate has **0 observed and 54 missing** rows; missing observations are not
measured incorrect predictions. Overall, 108 of 162 scheduled comparison rows are observed.
Neither baseline has trial errors or diagnostics in this completed capture.

All 108 owned trial database/role pairs were checked absent during capture, and workspace
container/volume teardown completed before the completion receipt. The six original
Langfuse containers were restored at 17:20 UTC on 2026-11-05. Today's readback also verified
that each previously running container's immutable ID was running after Docker was started.
These receipts are private host-operation evidence, separate from production recovery.

The provider ledger was opened read-only: **447 of 614 consumed, zero unsettled, one
original stop**. Both algorithms used zero model calls. No allowance, stopped schedule,
candidate, source labels or release gate changed. The first readback attempt on 2026-11-06
hit a local file-access restriction before score verification; a separately named readback
directory holds the successful check after authorized access. It did not rerun any trial.

## Verification and interpretation

Run `python -m pytest tests/test_trial_diagnostics.py tests/test_trials.py -q` in the locked
environment; the new25cases include sensitive-message masking, an exception whose stringifier
raises, known/unknown SQLSTATEs, caught coordinator failures, early/late abort, identity
mismatch, legacy row bytes and malformed/misbound diagnostics. The current source also
passes229-file typechecking, CI-scoped lint/format and six real service SQL checks.
Full hosted PR/main results are delivery evidence recorded separately.

Baseline state safety, semantic correctness, eligible completion, review burden and unknown
outcomes remain separate. The closed grammar, actor scripts, exposed inputs and dependent
groups do not establish natural-language gold, fresh unseen wording or independent samples.
Recorded group uncertainty is conditional on unverified independence assumptions. Parent
setup/execution/cleanup timing is not API latency or a provider-decision latency result.
Neither executing a baseline nor owner acceptance of the v2 evidence-method design approves
baseline usefulness, thresholds, a qualification cohort or production release.

Interview exercise: a journal contains54rows but half are abort placeholders. Explain which
denominators stay unknown; why an SQLSTATE is useful without a full error string; why
diagnostic metadata cannot pass an invariant; and why an old failed run remains historical
even when a separate new run completes. [Build Book Entry88](../BUILD_BOOK.md#entry-88--keep-diagnostic-causes-separate-from-aborted-trial-placeholders)
records the construction and observed failure paths.
