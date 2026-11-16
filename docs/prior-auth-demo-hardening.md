# Local Docker demo hardening

The immediate target is local Docker with Gemini3.5Flash-Lite. OpenAI model comparison
and remote hosting are deferred by the owner. This batch implements recovery and
restricted parsing without loading a model key or changing any provider allowance.
Actual-container and restore checks must pass on the final PR head before treating
these mechanisms as verified. They are not real-patient production qualification.

## Restricted document parsing

Build a minimal image from the immutable official Python base and five hash-locked
Python packages from the current `uv.lock`. The context builder copies only the
normalizer, profiler, worker and two contract modules, with no configuration or
credentials. Poppler and Tesseract are installed at image build. Package versions
are fixed by the resulting image ID; native apt resolution is not a fully
reproducible historical package snapshot. Rebuild and reverify for security updates.

```powershell
python containers/prior-auth-parser/build.py --context artifacts/pa-parser-build-v1
```

Keep the produced `image-id.txt`. Runtime accepts an exact local image ID, never
an arbitrary tag, and refuses automatic pulling. An absent image/daemon fails
closed; it does not fall back to a host parser.

Use the existing authenticated import command with `--isolated-parser-image`
and that image ID. Do not combine it with `--native-tools`. The source is opened
only after reviewer/case/tenant checks. Native parser output remains evidence for
review; a container does not make an OCR result clinically correct.

The complete document is sent over stdin. There are no bind mounts, project files,
API keys, Docker socket or published ports. Runtime uses network none, read-only
root, non-root UID, all capabilities dropped, no-new-privileges, default seccomp,
32PIDs,512MiB memory/no extra swap, one CPU, file limits and a64MiB bounded tmpfs.
The parent enforces elapsed-time/output limits, validates returned source/text/region
pins and removes only its unique container on exit/deadline. A daemon outage during
cleanup can leave unknown state; inspect task-owned containers before retrying.

The required Linux check executes actual text-PDF extraction and OCR, tests blocked
network/root writes, non-root/default-seccomp/no-capability state and actual cgroup
limits, then deliberately overruns a parent deadline and verifies container removal.
This is tested Docker containment, not proof against every kernel/container escape.
Keep the Docker daemon trusted and do not expose a public upload endpoint merely
because this adapter exists.

## Private complete-state backup and clean-target restore

Stop the desk, worker and operator commands first. Capture requires explicit
quiescence and locks all PA tables while copying the payer journal. The trust boundary
is the application composition: a separately invoked SQLite adapter outside that
composition is not coordinated by Postgres locks. Do not run it during capture.

The private snapshot contains all three PA schemas, accounts, sessions, case/version/
wait state, jobs, imported document locations, scopes, attempts and settlements,
plus a checked SQLite backup and the private launch bundle. The bundle's source and
case binding must match the imported case. Archives contain sensitive records and
password hashes; they are outside Git and created exclusively with restrictive POSIX
permissions. Windows filesystem ACLs remain the host administrator's responsibility.

```powershell
uv run --locked --all-packages --link-mode copy python prior_auth_recovery.py `
  --root . --trial pa-demo-wait backup `
  --journal D:/private/prior-auth/demo-wait/payer.sqlite `
  --bundle D:/private/prior-auth/demo-wait `
  --output D:/private/prior-auth/recovery/snapshot.json --quiescent
```

Keep the returned digest separately. A digest learned from an untrusted archive
does not establish authenticity. The snapshot is plaintext private local storage;
encrypted/off-host copies and a host-loss exercise remain separate work.

Restore uses the same source/schema/dependency lock and PostgreSQL build. Choose
an unused trial, a nonexistent journal and a nonexistent bundle directory:

```powershell
uv run --locked --all-packages --link-mode copy python prior_auth_recovery.py `
  --root . --trial pa-demo-restored restore `
  --snapshot D:/private/prior-auth/recovery/snapshot.json `
  --snapshot-sha256 <separately-retained-digest> `
  --new-journal D:/private/prior-auth/recovery/restored-payer.sqlite `
  --new-bundle D:/private/prior-auth/recovery/restored-bundle
```

The target must have no PA schemas/cases. Bootstrap creates the original restricted
roles/grants, verifies schema inventory and constraints, then copies in foreign-key
order and compares every row. Restored sessions are revoked; sign in anew with the
existing account password. Do not renew expired model scopes or reset unknown attempts.
A payer receipt remains received/unknown/reserved as captured. The restore path never
calls a model or payer. External payer state itself is not backed up here.

A failure leaves visible private target artifacts for inspection rather than silently
deleting them. Never launch a partial target or repeat restore into it. SQL and SQLite
publication are not one distributed transaction; the CLI reports success only after
both return successfully. Persist the fresh trial config in `.agent-local` and retain
the original snapshot/config while checking the restored application.

Tests must exercise a complete case and a death-after-reservation case, exact citation
readback, new login/old-session refusal, no model redispatch, retained unknown payer
receipt and unchanged source. This is local same-build recovery. It supplies no
measured host-loss RPO/RTO or promise of production readiness today.

## Live Gemini boundary

The active route remains Gemini3.5Flash-Lite. The revised candidate and SQL reservation
layer are implemented, but the exact same-ledger live grant, validator/transport
composition and selected-host fake-SDK readiness must precede new dispatch. The
prepared citation-repair proposal is not a standing runtime allowance. Its old
615/784history and169bound/unspent slots remain untouched. Do not request an OpenAI
key or run the deferred comparison in this phase.
