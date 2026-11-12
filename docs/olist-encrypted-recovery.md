# Encrypted scheduled backup and separate-host recovery

Prepared 2026-11-11 from main `fd4ef0c`. The owner requested qualification evidence and
scheduled/off-host recovery, then asked for a destination recommendation. Recommended:
**Restic 0.19.1, private Cloudflare R2 Standard, and a separate clean Linux restore machine**.
The source-bound [catalog](olist-backup-catalog.md) remains the SQL snapshot boundary.
The new [one-shot runner](../olist_remote_recovery.py) is executable preparation, not an
activated cloud destination or a completed host-loss exercise.

## Recommendation and concrete activation inputs

Restic provides an established encrypted repository format with S3-compatible and local
backends. Its [repository documentation](https://restic.readthedocs.io/en/stable/030_preparing_a_new_repo.html)
requires retaining the repository password: losing it can make the backup unrecoverable.
As checked 2026-11-11, [R2 Standard pricing](https://developers.cloudflare.com/r2/pricing/)
includes 10 GB-month storage, 1 million Class A and 10 million Class B monthly operations,
with free egress. Usage above the allowances is billable; this is not a hard free-only cap.
Backblaze B2 is another S3-compatible option, with different [storage/egress terms](https://www.backblaze.com/cloud-storage/pricing).
R2 is the recommended initial backend for frequent small backup/restore checks; only an
actual approved configuration and measurements can establish suitability for this workload.

To activate, supply these **private file locations and host details**, not credentials in chat:

1. Existing/private R2 account, bucket and repository prefix, bucket-scoped credentials,
   explicit spending limit and confirmed billing/region requirements. No purchase or remote
   repository initialization is inferred from the recommendation.
2. A persistent local source trial and frozen checkout; the previous bounded drills removed
   their owned databases. The local Docker engine must be healthy before the job can capture.
3. A separate Linux restore machine with pinned application/PostgreSQL build and Docker,
   enough private disk, time synchronization and authenticated access. A second directory,
   VM or disk on the source workstation does not prove independent host-loss recovery.
4. An independently retained Restic password, repository ID, latest successful receipt and
   its hash, marker/config pins and required application/config recovery material. Keep
   encryption-key recovery separate from loss of the source machine.
5. Agreed cadence, cycle deadline, storage/capacity and retention plan. The initial concrete
   proposal is 600-second cadence, 240-second maximum cycle, 900-second snapshot age. These
   are proposed operational settings for the accepted 15-minute planning target, not a
   proven RPO. Independent freshness alerting is still required if the source host disappears.

Do not enable public access or copy application/provider `.env` files into a bundle. The
bundle contains private database state, not credentials for arbitrary external services.
Manage any required application secret/config recovery separately and exercise it.

## Pin and prepare the job

Install a reviewed Restic release and verify the release archive checksum before executing
it. Pin the actual extracted executable separately in each host's private configuration.
The local canary used the official Windows/amd64 0.19.1 asset; exact source, archive and
executable hashes are in the [aggregate canary receipt](data/olist-encrypted-recovery-canary-v1.json).
The checksum records custody through the official release source; it is not an independent
software-supply-chain attestation. No executable is committed.

Create private `repository-location` containing:

```text
s3:https://<account-id>.r2.cloudflarestorage.com/<bucket>/<prefix>
```

Create a separate strong random password file and a bucket-scoped private credentials JSON
with exactly `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION` (R2: `auto`).
Protect parent-directory ACLs; file mode 0600 alone is not Windows ACL isolation. Initialize
the selected repository once through trusted administration only after account authorization.
Use `restic cat config` to record its actual full repository ID. The runner never initializes,
unlocks, repairs, forgets, prunes or deletes remote data. Restic's internal lock lifecycle can
require object deletion; a write-only credential or blanket immutable bucket policy needs
compatibility testing and is not silently configured here.

Serialize a canonical `Job` through the Pydantic contract, then retain SHA-256 of the exact
bytes separately. The schema in `olist_remote_recovery.Job` requires explicit absolute paths:

| Field | Value/source |
|---|---|
| `repository.executable`, `executable_sha256` | Verified host-specific Restic binary and its actual byte hash |
| `repository.repository_file`, `repository_id` | Private location file and actual initialized full repository ID |
| `repository.password_file`, `credentials_file`, `backend` | Private files above; backend `r2` |
| `root`, `trial` | Actual clean locked editable checkout and persistent owned trial |
| `catalog`, `catalog_sha256` | Existing private source-bound catalog and external marker pin |
| `journal` | New private attempt directory, separate from catalog |
| `interval_seconds`, `max_cycle_seconds`, `max_snapshot_age_seconds` | Explicit settings; interval + cycle must fit age objective |
| `max_attempts` | Explicit 1–1,000 cycle limit; stop rather than reset/delete at capacity |

At 600 seconds, 1,000 entries are roughly 6.9 days of attempts. The same bounded catalog
capacity must be planned. This software is deliberately not an indefinite retention system;
capacity/archival/rotation must be resolved before claiming continuous production operation.
No automatic backup deletion is introduced to hide this requirement.

```powershell
uv run --locked --all-packages python olist_remote_recovery.py init-journal --config <private-job.json> --pin <job-hash>
uv run --locked --all-packages python olist_remote_recovery.py run --config <private-job.json> --pin <job-hash>
uv run --locked --all-packages python olist_remote_recovery.py health --config <private-job.json> --pin <job-hash>
uv run --locked --all-packages python olist_remote_recovery.py render-task --config <private-job.json> --pin <job-hash> --operator <actual-windows-account> --output <new-private-task.xml>
```

The task is **disabled and unregistered**, least privilege, interactive-account-only, with
overlapping instances ignored and a bounded execution time. It is not an always-on Windows
service; logout, sleep and workstation loss can prevent runs. Before enabling, validate the
XML using [TASK_VALIDATE_ONLY](https://learn.microsoft.com/en-us/windows/win32/taskschd/taskfolder-registertask),
which checks syntax without registering a task, and inspect the concrete paths/account.
The corrected XML passed this actual Windows validation on 2026-11-11; the original failed
because its UTF-8 declaration conflicted with COM's Unicode input. Both attempts are retained.
No task was registered by either validation.
Registration/activation and observation of actual repeated cycles still remain. An
independent monitor must observe missing/stale uploads; local task logs disappear with a host.

## What each cycle proves

The external job pin binds configuration. An exclusive journal lock serializes cycles.
Create a private attempt before transport/source work, verify the pinned Restic executable
and exact repository identity, then invoke the existing catalog CLI. That CLI checks the
actual clean checkout/editable imports and lock before/after a consistent SQL snapshot.
Only a completed catalog entry can form the bounded bundle: catalog marker, archive and
completion receipt. Publisher labels, provider keys and unrelated files are never added.

The whole payload is materialized and verified before passing it to Restic stdin. Its
[stdin warning](https://restic.readthedocs.io/en/stable/040_backup.html#reading-data-from-stdin)
matters: success cannot be inferred from a pipeline whose source failed. Here the source
capture must exit successfully, and a full snapshot ID plus exact dump/readback equality
are required. All nonzero Restic exits—including partial-data code 3—and ambiguous/missing
snapshot IDs fail. The runner uses no automatic retry. See the official [exit-code/JSON guide](https://restic.readthedocs.io/en/stable/075_scripting.html).

Only exact readback within the cycle and snapshot-age limits publishes `success.json`.
Keep its printed SHA-256 in independent recovery records. The receipt binds repository ID,
snapshot ID, bundle bytes/hash, source archive/completion pins and times. Errors expose a
fixed safe code. A failed/unfinished cycle blocks later dispatch; a crash-left lock stays
for investigation. Partial writes and remote uploads without a success receipt are not
silently promoted or automatically deleted. Investigate and preserve history before a new
explicitly pinned job/journal; do not reset a stopped journal to conceal the failure.

`health` reports the age of the last **verified uploaded snapshot**, not upload completion,
and refuses future/invalid timestamps, failed attempts, locks and capacity. It checks local
records; it is not a current remote availability query. Local-canary jobs always report
`healthy=false`, even with verified bytes. A true `r2` result in a fake transport test is
control-flow evidence only. No report sets actual host-loss recovery or release true.

## Separate-host recovery and measured acceptance

On the clean Linux host, prepare a new externally pinned `Repository` JSON with that host's
absolute binary/private-file paths, the **same actual repository ID**, and recovered private
password/credentials. A source Windows `Job` is not reused as a Linux path configuration.
Copy the independently retained cycle receipt and its external hash through trusted recovery
records, then fetch the exact snapshot—not a mutable `latest` selector:

```bash
uv run --locked --all-packages python olist_remote_recovery.py recover --config /private/repository.json --pin REPOSITORY_CONFIG_HASH --receipt /private/copy-receipt.json --receipt-pin SAVED_RECEIPT_HASH --seconds 240 --output /private/new-recovered-catalog
```

The output directory must be new. Recovery verifies repository/snapshot, exact bundle bytes,
safe file inventory, original catalog marker and archive/completion hashes before returning
the selected archive. It does **not** restore a database or switch traffic. Run the existing
`operations_cli restore-new` with the returned exact archive pin and a new owned trial, then
readiness plus authenticated customer/operator/reviewer, duplicate-receipt and pending-work
checks. Preserve later source effects and explicitly reconcile any lost acknowledged work.

Before claiming the accepted RPO ≤15 minutes/RTO ≤60 minutes, perform the isolated exercise
from outage detection through key/config discovery, host provisioning, archive retrieval,
database/readiness/authenticated workflow and explicit cutover decision. Record acknowledged
canary times and actual lost work, including failed attempts; a fast dump/download is not
that measurement. Do not stop unrelated services or destroy the source as a shortcut.

## Actual evidence and limits

The real pinned Restic local canary uploaded/read back 2,846 bytes of explicitly invented
non-SQL fixture data, recovered the exact bundle into a new private directory, passed
`check --read-data`, and refused the wrong password. Its source snapshot has four declared
schema fixture tables, not PostgreSQL COPY validity. No R2 endpoint, scheduled task or second
machine was used. Its receipt remains historical and pins the exact runner bytes used;
later changes require a separately named new exercise rather than rewriting the receipt.

Focused tests verify journal failures, stale/future clocks, wrong job/repository/binary pins,
partial upload, ambiguous snapshot selection, changed readback, safe recovery paths, disabled
task XML and actual writer death. The unchanged real-SQL catalog restore remains a separate
required CI witness. Frozen runtime packages, model study/ledger and pending mappings remain
unchanged. Snapshot file fsync is not directory/power-loss certification. Local operator/admin
tampering, malicious Restic binaries and loss of independent key/receipt escrow are outside
the byte-custody claim. No population quality, business savings or completed release follows.


## Required combined encrypted/SQL witness

The PostgreSQL CI job downloads the official Linux/amd64 Restic0.19.1 archive, checks its
fixed published SHA-256 before extraction/execution and runs the required encrypted-recovery
integration test. It captures real four-schema SQL state, encrypts and independently fetches
the exact bundle, commits later source work, restores into a new owned database and checks
pending review, original duplicate receipt, runtime readiness and untouched newer source.
It then runs real Restic check --read-data. This joins SQL and encrypted transport mechanisms;
it remains an isolated one-host SIM test, not R2 or a host-loss drill. Missing Restic fails
rather than skips acceptance. For local SQL checks, install that reviewed host-specific
binary and set OLIST_RESTIC_CANARY_EXECUTABLE to its absolute private path. CI installs its
pinned Linux executable under ignored artifacts/tools/restic-canary. Final PR/main job logs
must establish the actual result; preparation alone does not report the new witness passed.
