# Prior Auth: operator-controlled reference payer

This optional demo composition adds explicit submission and inquiry to the protected
citation desk. It uses the existing `PasClient`; the model has no payer capability.
The target is an owned loopback instance of HL7-DaVinci/br-payer at
`10d40911cb90d6198aacec144b4bfc48466af2fb`. It is not a commercial insurer.

## Local launch

First initialize and run the scripted citation demo using the
[runtime guide](prior-auth-demo-runtime.md). Build the pinned independent service as
shown in `.github/workflows/prior-auth-pas.yml`. Start that owned service with Java17,
bound explicitly to loopback:

```powershell
java -Xmx1536m -Dserver.address=127.0.0.1 -Dserver.port=8081 -jar <pinned-build>/server/target/ROOT.war
```

The private binding file is `request.json` from demo initialization. Its case binding
must match the binding hash saved during import. Supply all three payer options:

```powershell
uv run --locked --all-packages --link-mode copy python prior_auth_demo_console.py `
  --root . --trial pa-demo-citations serve --port 8766 `
  --payer-endpoint http://127.0.0.1:8081/fhir `
  --payer-journal D:/private/prior-auth/demo-citations/payer.sqlite `
  --binding-file D:/private/prior-auth/demo-citations/request.json
```

Use an existing private parent directory outside Git for the journal. Keep this
journal across restarts and include it in backup/restore with the trial database,
binding file and source bundle. Replacing the journal discards duplicate containment.
Without these options the desk does not expose payer controls or make payer calls.
The configuration is trusted local operator input, not a browser-selected destination.

Sign in, select the case, inspect policy/document sources, then click **Submit
synthetic packet**. The click explicitly confirms a reference-payer exchange. Only
an assigned reviewer can submit or inquire. The browser supplies revision and
confirmation only; it cannot send a destination, patient, payer, policy or note body.

## What happens at submission

`PayerDesk.current` locks the canonical Postgres case, checks the requested revision
and trusted binding hash, and requires an invented note. It constructs `Submission`
from server-owned values. A stable identity includes tenant, case, revision, note
and policy pins. The lock stays held during the bounded exchange, preventing a
supplement from changing the packet between validation and dispatch. This can delay
another edit; a larger deployment should consider an atomic SQL outbox.

Before calling the existing reserve-before-POST adapter, an additive SQLite packet
index records the case/revision identity. A repeated click for the same packet
returns the stored receipt. A prior uncertain packet blocks a new revision from
silently creating a replacement submission. The index is not a clinical record.

The packet contains invented FHIR identities/service and a note digest. **The case
note text is not exported.** Independent Claim and patient/payer/provider readback
checks correlation. Processing completion is not clinical approval. A3 means the
reference payer reports authorization is not required for the invented service;
the UI must not call that treatment approval.

## Unknown outcomes and inquiry

Reserved/unknown submission history stays intact. **Check payer status** performs
only `$inquire`, validates independent correlation and stores a separate observation.
It never calls `$submit`. An unavailable inquiry remains explicit and cannot become
an invented denial or approval. No automatic submission retry or background inquiry
is introduced. A crash after the packet index but before a submission receipt is
conservatively unresolved and requires private operator inspection.

Current browser inquiry targets the current revision. An uncertain older revision
after a document change needs private operator reconciliation; the UI blocks a new
submission rather than guessing. This is an explicit demo recovery limitation.

## Evidence

The SQL suite exercises concurrent duplicate containment, state/binding/tenant/viewer
fences, retained uncertainty, inquiry-before-submit refusal and authenticated
origin/CSRF/confirmation enforcement. Browser tests check that a late payer response
after logout cannot reload private case data. The independent reference workflow
also executes the authenticated SQL desk against the real pinned payer process.
Those hosted results must pass on the actual final PR head before claiming the new
composition verified. A fake unit transport is not independent-payer evidence.

This adds no model attempt, clinical qualification, real-patient permission,
commercial-payer credential or hosted deployment activation.


The desk uses the versioned `payer-desk-trace-v1` request identity and adds the PAS
itemTraceNumber extension containing the packet digest to both submit and inquiry.
The pinned reference matcher can otherwise find several requests with the same
patient/coverage/service. The legacy standalone serializer is still the default;
its historical wire bytes are unchanged. The desk keeps the single-match response
check and independent Claim/identity readback. The actual-process regression uses
two explicit packets for the same patient and requires one match for each inquiry.
