# Local Postgres and trial state — F4

F4 supplies disposable development/evaluation persistence. It does not implement domain tools, an evaluation scheduler, production tenancy, approved actions or a workflow engine. The F2 offline example still needs no database.

## Start and use a workspace

Install/start Docker Desktop with its Linux engine, or Docker Engine plus Compose v2. After `python dev.py setup`:

```powershell
python dev.py db-up
python dev.py db-status
python dev.py trial-create --trial invented-trial-a
python dev.py trial-create --trial invented-trial-b
python dev.py trial-reset --trial invented-trial-a
python dev.py trial-drop --trial invented-trial-a
python dev.py trial-drop --trial invented-trial-b
python dev.py db-down
```

`db-up` derives `pa-<16 hex characters>` from the resolved checkout path. Compose creates that project's Postgres service, default network and named volume; there are no global container/volume names. Docker binds an available host port to **127.0.0.1**; `db-status` returns its actual port, workspace identifier and server version. Identical trial IDs in two checkouts still select different server/database/login identities. Rename/move a checkout only after stopping its old service; copied `.agent-local` state is rejected.

The official image is pinned to `postgres@sha256:67f41722b7a8cbdb868a44a4995c846eddfdc2973bccb291ce937dce88ad5675`, exercised as Postgres **17.11**. Its data mount is `/var/lib/postgresql/data`. This is the reproducible local baseline; upgrading requires an explicit disposable migration/restore check and new configuration, not changing the image under an existing volume.

Generated administrator and trial credentials are stored in ignored `.agent-local/instance.json` and `.agent-local/trials/<database>.json`. Commands print identifiers, never passwords or connection URLs. `.env`/`DATABASE_URL` are not read. Do not copy local state into a worktree or commit/upload it. POSIX files are mode 0600; Windows relies on the user's existing directory ACLs. Local users with file/Docker/admin access are trusted. This is not a sandbox for hostile code on the same computer.

Trusted harness integration can load `Workspace(root).load_trial(trial_id)` and use `Workspace(root).server().connect_trial(trial)` as a context manager. The connection commits on normal exit and rolls back on exceptions. Do not pass administrator credentials or lifecycle methods to an agent. A stopped/restarted service can have a new port; discover it again rather than saving a URL.

## State and ownership

| Persistence | Owner and present behavior | Later implementation |
|---|---|---|
| `harness_meta.migrations`, `harness_meta.snapshot` | Trusted bootstrap/evaluator; trial login has no access. Applied migration text and fixture text have SHA-256 hashes. | Versioned domain snapshots and release manifests |
| `runtime.checkpoints` | One trial's runtime; key, object JSON payload and positive version. Trial role can read/write. | Workflow adapter owns checkpoint format and resume/CAS semantics |
| `runtime.reviews` | One trial's review component; key, object JSON payload, pending/resolved status and positive version. Trial role can read/write. | O6 owns exact-action approval, actor/scope, expiry and durable resume |
| `runtime.ledger` | One trial's action component; unique entry key and object JSON payload. Trial role can SELECT/INSERT, cannot UPDATE/DELETE/TRUNCATE. | Domain tools own business-operation identity, action/ledger transaction, approval limits and compensation |
| Domain schemas/tables | Not implemented here; each vertical owns its future migration/fixture definitions. | Olist order/refund state and later vertical state |

Trial roles are LOGIN/NOSUPERUSER/NOCREATEDB/NOCREATEROLE/NOINHERIT/NOREPLICATION. A database starts with connections disabled; bootstrap revokes PUBLIC database privileges, enables admin connections, builds the baseline, then grants its own trial role CONNECT. Another trial role is denied even when it knows the database name. Separate databases prevent a missing trial filter from exposing another trial's tables. Administrative and host access can bypass this boundary.

The baseline is **invented/synthetic**, ID `foundation-v1`, with one checkpoint at `step=start`, one pending review and one ledger entry with `effect=none`. It contains no source rows, labels, refund policy or model output. It is state-bootstrap evidence, not a model-quality dataset.

## Migration, reset and recovery

`trial-create` reserves the local credential file, creates a generated role/database from `template0`, applies ordered packaged SQL migrations transactionally, records their hashes and inserts the versioned fixture. Repeating create refuses replacement. Applied migrations cannot be edited or removed; append a new migration. Transactional SQL failure rolls back both new DDL and its migration-history entry.

`trial-reset` verifies database/role ownership comments, checks migrations and compares the recorded fixture ID/hash with current code. It then drops/recreates that **one disposable trial database** from template0, migrations and fixture. The role/password remain the same. Unknown ownership, changed applied files, changed fixture or active connections fail; reset never forcibly disconnects another session. Close trial connections before reset/drop. This rebuild is the verified restore path; no automatic destructive down migration exists.

`db-down` stops/removes only the workspace's containers/network and retains its volume and local configuration. `db-up` restores the same stored trial writes. The destructive alternative is `python dev.py db-destroy --confirm-workspace <exact identifier from db-status>`; it removes that project's volume. Drop trials first. Local credential files remain after volume removal, so old trial configuration must not be treated as proof its database exists. Preserve a stopped old workspace/configuration for investigation rather than repointing it to another server.

Creating/dropping roles/databases is administrative DDL spanning multiple transactions. A process crash can leave an incomplete bootstrap; errors never report success. Local credentials are saved before bootstrap to retain its identity. If the ownership-marked role/database exist, `trial-drop` permits explicit recovery; a partial role-only failure requires administrator inspection of this generated project. Do not reuse a failed trial ID as a successful run. Production backup/recovery and upgrades remain L2.

## Required verification

```powershell
python dev.py check
python dev.py db-check
```

`check` runs offline behavior and statically checks integration source but explicitly excludes `tests/integration` from execution. `db-check` overrides that exclusion and creates two temporary workspace services with separate volumes; it fails if Docker is unavailable and never skips required database evidence. Temporary services/volumes are removed in fixture cleanup; the real checkout's service and unrelated containers are not targeted. The pinned image may need one registry download; no model/provider network is used.

Integration checks cover actual server/port/volume separation, denied cross-trial connections, independent mutations, exact reset, restart persistence, migration idempotence/drift/missing-file rejection, transactional DDL/DML rollback, fixture/ownership refusal, active-session refusal and ledger/metadata privileges. See `tests/integration/test_postgres_isolation.py`. Windows/Python 3.13.4, Docker Linux engine/Compose v2 and the pinned Postgres image are exercised; F5 also verified the required database suite on Ubuntu/Python 3.13 in hosted CI. Its offline checks cover Python 3.12/3.13 on Ubuntu/Windows; Windows hosted Docker and other database/interpreter combinations are not claimed.

Design references: [Compose project names](https://docs.docker.com/compose/how-tos/project-name/), [Postgres database templates](https://www.postgresql.org/docs/17/sql-createdatabase.html), [database/object privileges](https://www.postgresql.org/docs/17/sql-grant.html) and [Psycopg installation choices](https://www.psycopg.org/psycopg3/docs/basic/install.html).
