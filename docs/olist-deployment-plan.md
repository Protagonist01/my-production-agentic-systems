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

For an isolated demonstration, the following Python setup creates two clearly invented
orders and principal files. Run it after bootstrap, replace the paths/trial ID, and prepare
the private principal parent outside Git. Keep these fixture helpers out of production
customer enrollment; they intentionally supply fictional SIM confirmation, not verified
real-world facts. Rerunning with existing identities/files is not a reset procedure.

```python
from pathlib import Path
from agent_harness.local_services import Workspace, private_json
from olist_support.business import enroll
from olist_support.console_contracts import Principal
from olist_support.policy import ScenarioConfirmation
from olist_support.policy_cases import external
from olist_support.views import AmountTotal, OrderView

w = Workspace(Path("<clean-checkout>").resolve())
t = w.load_trial("<local-trial>")
orders = ("local-refund-order", "local-pending-order")
private = Path("<private-principal-parent>").resolve()
with w.server().connect(t.name) as admin:
    for order in orders:
        view = OrderView(
            tenant_id="invented-tenant", order_id=order,
            as_of_source_local="2026-10-19T00:00:00",
            source_manifest_sha256="invented-source", currency_unit=None,
            snapshot_details_visible=True, events=(), final_source_status="canceled",
            estimated_delivery_source_local=None, customer_city=None, customer_state=None,
            items=(), payments=(), reviews=(), item_count=0, payment_count=1,
            price=None, freight=None,
            payment=AmountTotal(known_minor=5000, total_minor=5000, missing_rows=0),
        )
        proof = ScenarioConfirmation(
            tenant_id="invented-tenant", order_id=order,
            available_at_source_local="2026-10-18T00:00:00", unit="SIM",
            payment_confirmed=True, undelivered_confirmed=True, prior_refund_minor=0,
        )
        enroll(admin, view, proof)
for role in ("operator", "reviewer", "customer"):
    principal = Principal(
        username="local-" + role, tenant_id="invented-tenant",
        actor_id="local-" + role, role=role, order_ids=orders,
    )
    private_json(external(private / (role + ".json")), principal.model_dump(mode="json"))
```

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

## Backup freshness implemented; scheduler and host-loss acceptance pending

The [encrypted recovery follow-up](olist-encrypted-recovery.md) implements a pinned one-shot
job, exact encrypted snapshot readback, private failure journal, health check and disabled
Windows task rendering. Restic/private R2 Standard plus a separate clean Linux restore host
are recommended. Actual account/configuration, activation, repeated cycles and measured
host-loss recovery are still pending; the local encrypted canary cannot supply them.

The standalone [backup catalog](olist-backup-catalog.md), added 2026-11-11, now provides
bounded private snapshot capture/discovery and an explicit freshness check. It retains
incomplete attempts and stale writer locks, selects the newest byte-verified snapshot,
and reports degraded health instead of silently hiding a failed newer capture. It reuses
the existing new-target-only restore; it installs no scheduler and deletes no backup.
Catalog health is not an actual restore or host-loss acceptance result.

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

The [November9aggregate](data/olist-local-deployment-exercise-v1.json) records a completed
exercise at source revision7a404e2:19real loopback HTTP requests,18successful responses and
one intentionally refused non-JSON write. Three distinct accounts approve/confirm/execute
one50.00SIMrefund while a second case remains in review. SQL checks require one refund,
consumed customer authority, original receipt across duplicates and unchanged source.
Both server lifetimes drain with zero active/interrupted requests. The four-schema archive
has18tables/70rows. Capture took0.498seconds; restore/verification/readiness took2.762seconds
against the60-second local exercise bound. These are one small local sample, not p95,
30-day availability, a power-loss test or host-loss RPO/RTO.

Prior v1 failed at a bodyless challenge request (403); v2 completed the refund/duplicate
flow but failed exporting PostgreSQL Decimal totals before restore. Both remain incomplete
with private observations/failure and verified cleanup. The successful v3 uses explicit
JSON, an intentional negative request and exact-integral minor-unit serialization. It
does not round fractional values. All three runs are zero-provider operations, not model
trials. The final read-only allowance is unchanged447consumed/0unsettled/1stop.

Successful cleanup removes the two owned databases/roles and its owned container/volume.
All53preexisting container identities survive and the six previously running containers
remain running. No always-on Olist server is left by this bounded exercise. The startup
commands above are the operator path for a persistent local instance, whose state must be
preserved until a separately chosen teardown. Private archive, reports, failure history,
frozen runner, HTTP observations and independent readback are retained under
`D:/document/.cache/production-agents/olist/local-deployment-exercise-2026-11-09-v1`,
`v2` and `v3` respectively (each shares the complete directory prefix).

Prior source-grounded demonstrations and completed baseline captures remain historical.
This plan changes no runtime package, frozen study, provider allowance or qualification
threshold. It supplies portable operator steps and measured local mechanism evidence;
semantic qualification, off-host recovery and release gates keep #33/#58/#59 open.
