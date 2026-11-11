# Local backup discovery, freshness and failure reporting

Prepared 2026-11-11 from main `c5b265d` after #150/#151. This advances the selected local
deployment/recovery work for #33, #58 and #59. It does not qualify language references,
resume providers, install a scheduler, select a remote destination or authorize release.

## Use the catalog

Run the standalone [operator helper](../olist_backup_catalog.py) from its own clean locked
editable workspace. Existing `olist_support.backup` snapshot/restore bytes and database
schemas are unchanged. Prepare a private parent outside Git, choose a new catalog directory,
an existing owned source trial and an explicit capacity. Keep its returned marker hash in
the private operator configuration separately from the catalog. The marker binds the source
identity and capacity; initializing again refuses rather than resetting history.

```powershell
uv run --locked --all-packages python olist_backup_catalog.py --catalog <new-private-catalog> init --root <clean-checkout> --trial <source-trial> --max-entries <capacity>
uv run --locked --all-packages python olist_backup_catalog.py --catalog <private-catalog> capture --root <same-clean-checkout> --trial <same-source-trial> --catalog-sha256 <saved-marker-hash>
uv run --locked --all-packages python olist_backup_catalog.py --catalog <private-catalog> status --catalog-sha256 <saved-marker-hash> --max-age-seconds <explicit-limit>
```

Capacity is 1–1,000 entries; age limits must be finite, positive and at most 86,400 seconds.
These are software bounds, not a retention policy or a recommended recovery objective.
The accepted 15-minute planning RPO can inform a proposed 900-second local freshness alert;
it does not make same-machine archives sufficient for host loss. The earlier ten-minute
cadence remains a proposal. No recurring task or deletion/rotation is installed here.

`capture` checks that this entrypoint and editable harness/Olist imports belong to the
selected checkout. It checks clean Git HEAD and lock both before and after the SQL capture;
a changed source never gets a completion receipt. Existing ownership checks and the
read-only repeatable-read snapshot still cover all four schemas together. Do not use a
different checkout's Git revision to describe the executing installed packages.

The catalog creates an exclusive writer lock before SQL or capacity checks. Each capture
gets a new random directory. Archive bytes are bounded, exclusive-created, flushed/fsynced
and read back; canonical format, source identity, schema inventory and inner table digests
are checked. Only then is `complete.json` written and flushed/fsynced. Completion binds the
archive hash, catalog pin, snapshot/completion timestamps and table/row counts. A failed
or killed writer leaves its incomplete entry visible. A crash-left lock is never silently
cleared. The final lock release removes only the file whose filesystem identity this writer
created. Older archives are never overwritten or deleted.

## Read status correctly

Exit 0 means a fresh byte-verified snapshot is available, there are no incomplete/invalid
entries or writer lock, and capacity has not been reached. Exit 2 reports unhealthy state
or a fixed safe refusal. Neither means a production restore, model or business outcome was
validated. Errors do not print source records, passwords, session data or database errors.

The status scans only the bounded catalog entry inventory and revalidates every completed
archive against its receipt and source marker. It chooses the newest **snapshot timestamp**,
not directory name, publication order, completion time or mtime. Snapshot time is the
existing capture's conservative timestamp immediately before its read-only database reads.
Time before the snapshot/completion, a naive supplied clock or incompatible clock state
cannot yield a healthy result. Normal operation requires a trustworthy synchronized clock;
this does not certify cross-host time accuracy.

`fresh_snapshot_available` is separate from `healthy`: a prior valid backup remains visible
after a new partial/corrupt attempt, but failure is not hidden by selecting that prior copy.
Status includes completed/incomplete/invalid counts, lock/capacity flags, selected entry,
archive/completion hashes, age and table/row counts. Inner hashes verify bytes, not whether
those rows will restore on a particular server. The report explicitly keeps
`actual_restore_verified`, `host_loss_rpo_rto_verified` and `release_allowed` false.

An active capture temporarily makes status unhealthy because of its writer lock. Investigate
a persistent lock; age alone is not evidence that its writer died. Preserve failed entries
and operator findings. If a catalog cannot be safely resumed, retain it intact and create a
separate explicitly pinned catalog; do not reset its marker or erase failures to turn it green.
At capacity, stop and resolve storage/retention deliberately rather than deleting backups.

## Restore selection and independent verification

Keep status and its selected hashes in private recovery records. Inspect freshness and all
failure flags before explicitly choosing an archive. Join the selected safe `entry` name
and `archive.json` under that catalog; it contains no caller-controlled path traversal.
Use the existing restore command with that exact archive pin and a **new** target trial:

```powershell
uv run --locked --all-packages python -m olist_support.operations_cli --root <clean-checkout> restore-new --archive <private-catalog>/<selected-entry>/archive.json --archive-sha256 <selected-archive-hash> --new-trial <new-target>
```

The existing restore refuses an established target, checks exact PostgreSQL build/schema,
restores all tables and independently reads them back. Run readiness and authenticated
workflow/duplicate checks afterward. Restoring an older snapshot into a different target
does not rewind later source effects or compensate a refund. A status result never switches
the live database pointer or independently authorizes accepting data loss.

## Verification and limits

Focused tests cover stale/clock-invalid snapshots, ordering, source/marker changes, corrupt
outer/inner bytes, wrong schema inventory, exclusive initialization, capacity, simultaneous
writers, archive/receipt/fsync failures, fixed safe errors and a real child process exiting
37 during capture. The last valid archive remains available while incomplete/invalid/lock
state prevents a healthy result. The SQL integration exercise captures actual pending review,
committed receipt and checkpoint/customer-authority tables, commits newer source work, then
restores the selected archive into a separate owned target and checks readiness and duplicate
receipts without altering that newer source state. Final exact-head/main evidence belongs
in the PR delivery receipt, not an assumed result here.

The local Docker engine was unavailable during preparation; the required hosted SQL job is
the execution venue for this new database exercise. No unrelated local service is restarted
or stopped. This is mechanism evidence with invented SIM records, not population performance
or a host-loss exercise. The 20 MB raw/40 MB serialized archive and exact-build restrictions
remain; the capacity bound does not reserve disk space. Disk/OS failure can leave partial
artifacts. File fsync is used as documented by [Python](https://docs.python.org/3.12/library/os.html#os.fsync),
but no directory-persistence or whole-machine power-loss guarantee is claimed.

The external marker pin and archive/completion hashes establish custody under the trusted
local operator; they do not defend against a malicious filesystem administrator replacing
the catalog and its separately retained records. The catalog remains private: archives
contain account/session hashes, business rows and checkpoint state. Encryption, independent
failure-domain storage, secret/config recovery, selected retention/cadence and measured
full outage-to-cutover RPO/RTO remain open. PostgreSQL's [backup overview](https://www.postgresql.org/docs/17/backup.html)
and [transaction isolation guide](https://www.postgresql.org/docs/17/transaction-iso.html)
explain why a consistent logical snapshot is distinct from WAL/PITR or host-loss recovery.
