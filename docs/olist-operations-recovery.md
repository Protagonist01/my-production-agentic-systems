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
