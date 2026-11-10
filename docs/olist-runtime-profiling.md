# Runnable Olist profiling and evaluation preparation

This continues the [expanded diagnostics](olist-expanded-evaluation.md) after merged #144.
The separate root `olist_profiled_runtime.py` entrypoint enables profiling for every request
it serves. Existing frozen packages, old entrypoints and study inventories are preserved.
The default composition uses operator intent and constructs no model transport.

## Run locally

Use the existing bootstrap/account/enrollment instructions in the
[deployment plan](olist-deployment-plan.md). Then, from the locked workspace checkout:

```powershell
uv run --locked --all-packages --link-mode copy python olist_profiled_runtime.py --root <checkout> --trial <existing-trial> --run-limit-minor 10000 --profile-output <new-private-file-outside-Git> --port 8765
```

The service binds only loopback, retains scoped sessions/CSRF and database role privileges,
disables access logs, and retains the existing16connection concurrency and30second shutdown
drain settings. Its profile file uses the existing exclusive private telemetry lifecycle:
an existing output refuses startup; normal drained shutdown writes and fsyncs the snapshot.
A forced exit can leave an empty file. This is shutdown persistence, not crash-durable tracing.

## What is measured

`connection_factory` opens a real `ProfiledConnection` using the existing trial credentials.
The cursor factory is a real psycopg Cursor subclass, preserving row factories and driver
semantics. No proxy, global monkeypatch or private driver hook is installed.

| Stage | Measured scope |
|---|---|
| sql_connect | Connect/authenticate to loopback PostgreSQL, including failure |
| sql_execute | Cursor execute/executemany; network and server wait are inclusive |
| sql_fetch | fetchone/fetchmany/fetchall result conversion/retrieval |
| sql_commit / sql_rollback | Explicit driver calls, including implicit connection-context exit |
| sql_transaction | Entire explicit transaction/savepoint scope, including caller work |
| sql_finalize | Driver transaction-context exit: commit, rollback or savepoint handling |
| response_send | Each awaited ASGI send, not complete client network delivery |
| startup | Readiness and app construction after workspace resolution |

Previously implemented request/auth/login/case/database-context stages remain available.
ProfiledPlanner still wraps planner/gateway/parser for an independently authorized composition;
this console creates no model gateway. Durations nest and must not be summed.
Pipeline execution can defer server work beyond execute into synchronization, so an execute
span is not always full server runtime. Cursor iteration, COPY, named/server cursors and
driver-internal commands are not comprehensively timed. Lock wait is included in SQL time,
not separately attributed. Queue time, SQL server CPU, provider internals, policy arithmetic,
OS process CPU/RSS and transport subphases remain gaps. All-subprocess coverage stays false.

The profile is bounded (default4096spans); dropped/active counts prevent false completeness.
Only fixed stage names, local sequence/parent numbers, elapsed times and failure flags are
saved. Query text, parameters, exception text, credentials and customer identities are absent.

## Prepare the next development packet

```powershell
uv run --locked --all-packages --link-mode copy python olist_profiled_runtime.py --prepare-evaluation <new-private-directory-outside-Git>
```

This creates24authored inputs separately from evaluator-only proposed references, a full
three-variant/three-trial plan, a report with216missing observations, an unreviewed judgment
form and a proposal-only scope. A manifest written last pins the six completed files. An
existing directory refuses; partial failures remain visible without a completed manifest.

The74attempt estimate is two proposed invented canaries plus72candidate development calls;
the two baselines would run locally with zero provider calls. This is not an allocation,
selected model, host binding, frozen study, new permission or reuse of stopped allowance.
Actual source/request/model/settings/environment pins and readiness must be fixed before
seeking approval for a bounded run. The original stopped/expired study remains untouched.

## Natural-language evidence still needed

These exposed references remain authored proposals. Preparing or reviewing this packet
does not create independently established language truth. Preserve the earlier native-intent
and controlled-grammar development methods, source/license applicability findings and unknown
requested-amount roles. A language evaluator needs a separately supported reference set,
field/slice-specific false-acceptance and abstention testing, and untouched grouped evaluation
before it can support qualification. No such qualified evaluator or production release is
created here. Objective SQL/state checks and language interpretation remain distinct claims.

## Verification and tradeoffs

Tests exercise real commits, nested savepoint rollback, recovery after a query error,
executemany/fetch variants, delayed SQL, protected HTTP login/read access and shutdown profile
persistence. Unit tests check suppression/finalization and input/reference separation.
These test instrumentation and authority preservation, not model quality or an optimization.
There is no before/after load study yet; future profiling overhead must be measured under
declared cold/warm concurrency before choosing performance changes.

Implementation references: [psycopg connection/cursor factories](https://www.psycopg.org/psycopg3/docs/api/connections.html),
[cursor execution scope](https://www.psycopg.org/psycopg3/docs/advanced/cursors.html), and
[Langfuse trace nesting](https://langfuse.com/docs/observability/best-practices), checked2026-11-10.
