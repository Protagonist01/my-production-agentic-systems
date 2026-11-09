# Olist local deployment and portable recovery plan

Prepared2026-11-09 from verified main3fe00b7 (#142). The owner selected the existing
local Docker host and a host-neutral plan. Scope is local SIM operations with invented
requests, existing pinned application/database versions and no provider calls. The
production goal and existing release gates remain; this is not release authorization.

## Deployment contract

| Concern | Local binding | Portable requirement / remaining evidence |
|---|---|---|
| Application | Locked Python3.12/3.13 environment, six versioned packages | Rebuild/verify wheel, lock, source/config/schema pins on the chosen OS; keep previous compatible artifacts |
| Database | Existing immutable PostgreSQL17 image in `local_services.POSTGRES_IMAGE` | Exact server build/schema for this snapshot format; explicitly tested migration for any change |
| Network | Application loopback only; PostgreSQL random loopback port | Private database, TLS ingress and trusted authentication/proxy configuration need separate implementation/tests before external exposure |
| Authority | Provisioned distinct operator/reviewer/customer accounts, scoped orders | Provision outside public request flow; least-privilege runtime role, customer exact action/amount confirmation and independent reviewer rules retained |
| Planning | Console's operator-supplied intent and fixed planner, zero provider calls | This is an information-advantaged operational comparator, not qualified model routing; any model composition requires its separate frozen study |
| State | Four schemas: business, console, checkpoints, customer authority | Preserve accounts/scopes, receipts, budgets, reviews, challenge consumption and checkpoints together |
| Backups | Private bounded logical table-copy archive, external SHA-256 pin | Protected/encrypted storage with independent failure domain, retention/rotation and exercised key recovery remain deployment work |
| Recovery | New target only; same build/schema; verify all rows/readiness | Full host-loss recovery includes backup discovery, provisioning, secret/config recovery, authenticated workflow and controlled cutover |
| Observability | Private aggregate per server lifetime; no request/session content | Monitor readiness, business outcomes, backup age/failure and recovery receipts; no30-day availability result is inferred |

The existing [operations runbook](olist-operations-recovery.md) explains snapshot privacy,
ownership checks, binary COPY and exact-build limits. [Accepted planning targets](data/olist-operating-targets-v1.json)
remain zero observed critical effects,95%quality/completion/review targets, p95API1s/model30s,
99.5%initial availability, process-crash durability and host-loss RPO15min/RTO60min.
Local exercises below do not certify those population or long-term targets.

## First local installation

Use a clean pinned checkout with its own workspace identity and private output directory.
Use a new trial ID; bootstrap on an established trial is not permission to overwrite state.
Start Docker Desktop if stopped, check available disk/RAM and record container states.
Do not restart, prune or delete unrelated containers/volumes. The earlier Langfuse pause
was completed and does not authorize another pause.

Run from the selected checkout; replace angle-bracket values before execution:

```powershell
python dev.py setup
uv run --locked --all-packages python -m olist_support.console_cli --root <clean-checkout> --trial <new-local-trial> bootstrap
uv run --locked --all-packages python -m olist_support.operations_cli --root <clean-checkout> ready --trial <new-local-trial>
```

Compose `up --wait` checks database health; application readiness separately verifies
runtime access and all schema pins. A running container is not sufficient readiness, as
[Docker's startup guidance](https://docs.docker.com/compose/how-tos/startup-order/) explains.
Refuse traffic on readiness failure; investigate the fixed reason without printing secrets.
`/health/live` is process liveness; `/health/ready` includes the database/schema checks.

Provision three role-scoped principals through trusted administration, using private
Principal JSON files and the interactive account command. Customer and reviewer identities
must differ. The command prompts for passwords; do not put passwords in command arguments.
Enroll an explicitly invented SIM order/facts through `business.enroll` for the exercise;
never interpret a made-up order as a source-grounded customer record.

```powershell
uv run --locked --all-packages python -m olist_support.console_cli --root <clean-checkout> --trial <local-trial> account --principal <private-principal.json>
uv run --locked --all-packages python -m olist_support.console_cli --root <clean-checkout> --trial <local-trial> serve --port 8765 --run-limit-minor 10000 --telemetry-output <new-private-telemetry.json>
```

Repeat account provisioning for each distinct principal. The sample run cap is100.00SIM;
it is not permission to spend money. The server binds127.0.0.1, disables access logging
and ignores proxy identity headers. Visit `/` for operators/reviewers and `/customer` for
customer confirmation. Use a new telemetry file on every start. Current CLI selects the
fixed operator-intent composition; it does not load a provider key or qualify language.

## Local acceptance exercise

1. Record code/lock/image/server build, OS/Python, four schema inventory, ownership and
   restricted-role readiness. Keep credentials and raw evidence private.
2. Authenticate separate accounts over a real loopback TCP listener. Submit an invented
   refund requiring review and a second request that remains in review. Record exact
   request/event/case identity privately. Assert no effect before required authorities.
3. Reviewer approves the exact action digest/version. Customer obtains a bounded challenge,
   explicitly confirms refund/amount/SIM and executes. Read trusted SQL state: one exact
   refund, one matching receipt, conserved run budget and consumed customer authority.
4. Redeliver the same confirmed request. Require the original receipt and unchanged effect
   count. Preserve the pending review and unrelated order. Customer confirmation is not a
   substitute for semantic correctness; this exercise uses constructed operator intent.
5. Shut down normally; verify the server exits, private telemetry finalizes and active/
   interrupted counts are zero. This is normal drain, not OS power-loss proof.
6. Capture/restore into a different owned target. Reopen the pending/completed cases and
   execute the duplicate again; require original receipt and exact independent SQL state.
   Verify the original source remains unchanged. Publish measured counts/times, not raw rows.
7. Remove only exercise-owned databases/roles/container/volume after inspection. Keep
   private archive/report/pins and cleanup receipt; ordinary app shutdown preserves state.

Use the existing new-target-only recovery CLI on a clean checkout:

```powershell
uv run --locked --all-packages python -m olist_support.operations_cli --root <clean-checkout> exercise --trial <source-trial> --new-trial <new-restored-trial> --archive <new-private-archive.json> --report <new-private-report.json> --max-restore-seconds 60
```

Here60seconds is a local exercise bound, not the accepted60-minute end-to-end host-loss
RTO. Exit2can mean a completed restore missed the bound; inspect and retain its report.
Do not rerun into an existing target, replace source rows or drop failed evidence.

## Port to another host without copying workstation identity

1. Reconstruct code/dependencies from the exact revision/lock and pinned artifact inventory.
   Check server build/OS assumptions before importing any snapshot. The current launcher
   uses Docker plus local Python; no portable application-container image is claimed.
2. Create fresh workspace/administrator/runtime identities on the target. Do not copy
   `.agent-local/instance.json` or trial credentials to a new root: they bind an absolute
   checkout path and workspace key. Inject secrets privately; never publish snapshots.
3. Bootstrap all four schemas. Use the protected archive with its separately retained
   digest and `restore-new`, targeting a new identity. A schema/build mismatch is a refusal,
   not an invitation to change the stored pin. Restore is transactional and readback must
   reproduce every table before application checks.
4. Verify restored accounts/scopes, outstanding reviews, consumed customer authority and
   original receipt on duplicate delivery. Define controlled credential/session handling
   and cutover before external use; the current CLI has no automatic live-pointer cutover.
5. Roll application code back only when compatible with the current schema/state. Never
   recover old rows over newer business effects as an application rollback technique.
6. Require actual TLS/ingress, OS-signal, backup access/key recovery and operational checks
   on that host. Preserve the eight-field/eight-slice semantic qualification requirement.

## Backup schedule and host-loss acceptance to implement later

For the15-minute planning RPO, propose a10-minute backup/check cadence with alerts when
the latest independently recoverable point approaches15minutes. This is a design proposal,
not an installed scheduler or a measured guarantee. Backups on C: and D: of the same
machine do not supply a separate host failure domain. No off-host destination, encryption
key store, retention schedule, deletion policy or cloud service has been selected here.

PostgreSQL distinguishes logical dumps, physical backups and continuous archiving;
the application's bounded table-copy archive is its own same-schema format. It is not
`pg_dump` or a WAL/base-backup solution. [PostgreSQL's backup overview](https://www.postgresql.org/docs/17/backup.html)
and [continuous-archiving requirements](https://www.postgresql.org/docs/17/continuous-archiving.html)
explain why logical exports cannot supply WAL-based point-in-time recovery.

Before claiming host-loss RPO/RTO, timestamp acknowledged canaries, lose an isolated
owned host, recover independently stored backups/config/secrets into a clean target and
measure from outage through authenticated successful workflow/cutover. Report actual lost
acknowledged time and full elapsed recovery, including failures. Keep current local evidence
separate. A future host-loss drill must not stop unrelated services on this workstation.

## Evidence and remaining limits

The November9local measurement will be recorded separately after execution, including
host startup failures, complete request/SQL outcomes and cleanup. Prior source-grounded
demonstrations and completed baseline captures remain historical. This plan changes no
runtime package, frozen study, provider allowance or qualification threshold. It supplies
portable operator steps and an explicit acceptance boundary; it does not close #33/#58/#59.
