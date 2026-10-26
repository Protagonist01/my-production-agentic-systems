# Local Olist health and private recovery exercise

Prepared on `codex/olist-operations-recovery`, based on merged #108 (`b71f7f7`),2026-10-26.
This prepares #58/#59 on the existing local Docker host. Production release, external
deployment, RPO/RTO objectives, telemetry acceptance and the #33 prerequisite remain pending.
No paid service or provider call occurs in these operations.

## Service health

Use the locked setup (`python dev.py setup`) and existing `olist_support.console_cli`
bootstrap/account/serve commands. Bootstrap validates immutable business/console SQL,
installs the pinned checkpoint schema and grants the runtime role SELECT on schema pins.
Runtime DDL remains forbidden. Serve stays loopback only with bounded concurrency/body
size and access logging disabled.

Serve now calls [`require_ready()`](../projects/olist-support/src/olist_support/service_health.py)
before HTTP startup. It checks runtime database access, exact installed business/console SQL
pins, complete checkpoint migration versions and required columns. Errors expose fixed
reason/action strings, never credential/database-error payloads or case records. Existing
installations may need trusted bootstrap for the schema-pin SELECT grant; SQL bytes have
not changed. Investigate a mismatched/corrupt schema rather than overwriting its version pin.

`GET /health/live` touches no database. `GET /health/ready` returns200when checks pass and
503otherwise, with existing no-store/security headers. Statements have a two-second timeout;
connections inherit the existing five-second bound. Health does not prove provider/model
quality. CLI: `python -m olist_support.operations_cli --root <checkout> ready --trial <id>`.

## Private snapshot

[`capture()`](../projects/olist-support/src/olist_support/backup.py) first verifies source
database/role ownership markers. One read-only repeatable-read transaction captures `olist`,
`olist_app` and `olist_graph`: orders, receipts/run budgets, review cases/events and checkpoint
blobs/writes. Connection credentials are absent, but account password hashes/session digests
are database state. The archive therefore stays private and must not be published.

Tables use PostgreSQL [binary COPY](https://www.postgresql.org/docs/17/sql-copy.html) through
[Psycopg's block interface](https://www.psycopg.org/psycopg3/docs/basic/copy.html). Sorting each
table by its JSON row projection gives reproducible row bytes. Each table has a digest/count;
the archive binds the full table/column/type/default/constraint/index inventory, PostgreSQL
major/build, source identity hash, application revision and dependency lock. Generated/
identity columns and sequences reject because their generation state is unsupported.
Raw data is capped at20MB. This is not a general PostgreSQL dump or cross-version migration.

Save a new archive outside every Git checkout, with a separately retained SHA-256. Exclusive
creation refuses overwrite; POSIX mode is0600and Windows inherits the private parent's ACL.
Base64 is encoding, not encryption. Protected private storage, encryption/rotation/off-host
retention and production recovery objectives remain deployment decisions.

```powershell
python -m olist_support.operations_cli --root <clean-checkout> backup --trial <source-id> --output <new-private-archive.json>
```

The CLI requires a clean checkout and records actual Git HEAD/lock hash. It prints only
archive pin, table count, elapsed time and zero provider calls. No existing snapshot changes.

## Restore without overwriting newer effects

```powershell
python -m olist_support.operations_cli --root <checkout> restore-new --archive <private-archive.json> --archive-sha256 <saved-byte-pin> --new-trial <new-id>
```

The API validates canonical/external archive pins and all table digests, then creates a new
owned trial. Any existing database identity rejects before bootstrap or truncation. Code-owned
bootstrap installs the current schema. PostgreSQL build/major and exact schema inventory must
match. Only the newly created target's Olist tables are emptied together; archived rows copy
in dependency order in one transaction. The source database is never opened for writing.
Failure removes only the new owned target; the source/archive remain intact.

After commit a new read-only snapshot must reproduce every table's bytes/count exactly.
The CLI then saves new trial credentials in the existing ignored workspace configuration;
configuration-write failure removes the new target. Printed elapsed time is a measurement,
not a production RTO guarantee. Source changes after the snapshot are not included: no WAL
replay, point-in-time recovery or automatic live cutover exists. Inspect/reconcile newer
effects before an explicitly chosen cutover. No command changes the live database pointer.

Application rollback selects compatible pinned code/dependencies/configuration; it does
not import old rows over newer business receipts. There is no overwrite/reset mode here.
Incompatible schema/build refuses instead of guessing a migration. No operation reverses a
refund or rewrites a ledger; business compensation is a distinct authorized operation.

## Actual exercise

`tests/integration/test_olist_operations_recovery.py` creates a pending review and committed
SIM effect/checkpoints, snapshots them, commits a later source effect and restores the old
snapshot into another owned database. It verifies pending review, exact committed result,
original receipt on duplicate redelivery, readiness and unchanged newer source state.
Negative checks refuse wrong pins/schema/existing target and verify failed-target cleanup.
Unit checks distinguish liveness, unavailable DB, missing schema and access denial without
echoing the private error canary. Run SQL explicitly with `-o addopts=''`.

These invented records prove a local mechanism, not production disaster recovery, real
payments, a finished source-grounded deployment or final release.

## Shutdown and private telemetry

The initial supported host remains the existing local Docker workspace with Python bound to
loopback. `console_cli serve` requires `--telemetry-output <new-external-private-summary.json>`.
ASGI lifespan exclusively reserves the output before serving; existing files, symlinks and
Git paths refuse startup. POSIX permissions are0600; Windows inherits the private parent's ACL.
No remote destination, new secret or paid service is required for this local aggregate.

[`service_telemetry.py`](../projects/olist-support/src/olist_support/service_telemetry.py)
counts HTTP starts, completed response bodies, interrupted/active requests, five status
classes, total request nanoseconds and uptime. It binds code/lock through a configuration
hash. The recorder never receives URLs, queries, bodies, headers, identities, sessions,
case/order IDs, exception text or response content. HTTP200is not proof of business success.

Uvicorn drains for at most30seconds, then invokes ASGI shutdown. Lifespan writes, flushes,
fsyncs and closes the aggregate. Storage failure raises a fixed safe error and attempts to
truncate the snapshot. Inspect both the process outcome and file; empty/missing/corrupt
output is incomplete telemetry. A finished snapshot with active/interrupted requests does
not prove a clean drain. Forced kill, disk failure, drain expiry and machine loss can lose
telemetry. PostgreSQL business/checkpoint durability does not depend on telemetry success.
Existing evaluation traces/export health are separate; no Langfuse ingestion is claimed.

Stop through Uvicorn's supported normal signal: Ctrl+C, Windows Ctrl+Break or POSIX SIGTERM.
Wait for exit, inspect the aggregate, reopen the same durable cases and verify receipts
before retrying. Do not replace the database to hide a timeout. A drain timeout does not
prove an admitted synchronous business action rolled back; its receipt/state remains primary.

`tests/integration/test_olist_service_shutdown.py` runs a real TCP server/restricted SQL role.
It holds an authenticated request after commit, requests Uvicorn's normal `should_exit`,
verifies the server still drains and the output remains unfinalized, then releases it. A
reconstructed store and second app lifespan observe the original receipt, one refund/event
and the separate pending review. This tests the normal server drain, not host-specific OS
signal/power-loss behavior. Unit tests cover private canaries, oversized requests, refused
output, interrupted sends and flush failure.

## Measured operator recovery exercise

From a clean pinned checkout, explicitly choose a local restore-time objective (finite,
positive, at most3600seconds). There is no default production SLA:

```powershell
python -m olist_support.operations_cli --root <clean-checkout> exercise --trial <source-id> --new-trial <new-id> --archive <new-private-archive.json> --report <new-private-report.json> --max-restore-seconds <operator-limit>
```

[`recovery_exercise.py`](../projects/olist-support/src/olist_support/recovery_exercise.py)
captures one consistent snapshot, saves pinned bytes, restores and independently verifies
all rows into a new target, checks runtime readiness, and reads the source again. It records
capture/restore-plus-verification durations, archive/schema/lock/code pins, table/row counts
and source/readiness results. A changing source explicitly gives `source_unchanged=false`;
use a quiescent source to check that invariant. Recovery includes only the snapshot, with
no WAL replay. Later commits remain excluded; production RPO/RTO is unverified.

Exit0requires all checks and the explicit time objective. Exit2can mean a completed restore
missed its objective: inspect its saved report/configuration before retrying. New targets
persist for inspection even when the time objective fails; no cutover occurs. Reusing any
target/output refuses. Restore/readback/report-write failure removes only the new target;
archive/partial report may remain as failed evidence. If configuration persistence fails,
the new target is removed and an existing report is not a live-target claim. Stdout contains
aggregate results and byte pins only. Keep report/archive/pins private; snapshots are encoded,
not encrypted. The SQL/CLI suite includes an intentionally impossible time limit and verifies
that it fails honestly while preserving the source and inspectable restored state.

References: [Langfuse lifecycle and masking guidance](https://langfuse.com/docs/observability/sdk/advanced-features).
The local aggregate follows explicit finalization/minimal-content principles; implementation
uses the locked Uvicorn0.54.0lifecycle verified against installed code. It does not add a new
SDK or remote export. Source-grounded demonstrations, invented SQL fixtures and final domain
release acceptance remain distinct evidence.
