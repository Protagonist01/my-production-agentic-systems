# Run the Prior Auth portfolio demonstration

The demo shows evidence review and workflow engineering with invented records. It
does not make clinical decisions. The bundled assessor is explicitly scripted;
the earlier live-model study is a separate historical result. A complete-citation
prompt exists, but its changed behavior still needs a newly authorized model run.

## Prepare once

Use Python3.12 or3.13, the locked repository setup, Docker/Postgres and Java17 for
the optional pinned reference payer. Follow the [citation launcher guide](prior-auth-demo-runtime.md)
and [reference-payer setup](prior-auth-payer-desk.md). Keep the exact previously
pinned CMS HTML, source pin, selected prose and policy compilation in a private
directory outside Git. The launcher verifies those bytes; it does not fetch a
new policy silently. The compilation is provisional and is labeled accordingly.

Initialize a new trial with the missing-education scenario. The example paths below
are placeholders for private directories, not a request to create a real patient:

```powershell
uv run --locked --all-packages --link-mode copy python prior_auth_demo_console.py `
  --root . --trial pa-demo-wait initialize `
  --directory D:/private/prior-auth/demo-wait `
  --policy-directory D:/private/prior-auth/pinned-source-v1 `
  --scenario education-wait
```

Enter a new reviewer password when prompted; it is not written into the bundle.
The fixed demo account is `demo-reviewer`. Initialization refuses an existing
trial/directory. A failed initialization can leave partial state: inspect it and
use a deliberately new identity instead of overwriting it.

The private bundle has initial source, policy, import request, scope, manifest,
fixed education supplement and supplement request. The scope covers only those
constructed request bytes, lasts one hour and cannot activate a provider.

## Demonstrate the complete workflow

1. Run the worker using `scope.json` from the private bundle:

   ```powershell
   uv run --locked --all-packages --link-mode copy python prior_auth_demo_console.py `
     --root . --trial pa-demo-wait worker --scope D:/private/prior-auth/demo-wait/scope.json
   ```

   It makes six scripted criterion invocations; education has no retrieved evidence.
   These are not six provider calls. The response explicitly reports zero provider calls.

2. Start the desk with the optional payer configuration from the payer guide,
   substituting trial `pa-demo-wait`, the bundle's `request.json`, and a private
   `payer.sqlite`. Open `http://127.0.0.1:8766`, sign in, select
   `demo-education-wait`, and inspect **Policy and case sources**. Education is
   insufficient. Show a policy paragraph and the mapped synthetic source for the
   other findings. Explain that source location does not establish clinical validity.

3. Use the desk's missing-document form: select only **CPAP education**, choose a
   future deadline within the next hour, and submit the request. The case advances
   from revision1 to2 and waits. No model or payer submission happens on this action.

4. In another terminal import the fixed supplement through the authenticated local
   operator command. Enter the same reviewer password when prompted:

   ```powershell
   uv run --locked --all-packages --link-mode copy python prior_auth_operator.py `
     --root . --trial pa-demo-wait import --username demo-reviewer `
     --request D:/private/prior-auth/demo-wait/supplement-request.json `
     --source D:/private/prior-auth/demo-wait/supplement.txt
   ```

   This is trusted synthetic import, not an unauthenticated browser upload. The
   prepared request is bound to revision2; a different revision is refused.

5. Run the same worker command again. It performs one scripted education invocation
   at revision3 and retains the other six findings. Refresh the case. All seven
   cards should be mapped; education points to `demo-education`. The fake response
   cites the supplement sentence, excluding the document separator.

6. With the owned reference payer running, click **Submit synthetic packet**.
   Show the actual receipt and packet digest. Click **Check payer status** and show
   the independently correlated inquiry. A3 means the reference service reports
   authorization is not required for the invented service. It is not treatment
   approval or evidence of commercial insurer acceptance. The packet exports
   invented FHIR identities and a note digest; it does not export case-note text.

7. Restart the desk with the same trial, binding and journal. The receipt remains.
   Running the worker again finds no pending job. A repeated submit for the same
   packet returns its original receipt without a second remote submission. Logout
   clears private evidence and blocks further actions.

## Restart and recovery boundaries

Stop the web process before copying state, and ensure no operator/worker is active.
Retain the private `.agent-local` configuration, the Postgres volume, private bundle
and payer SQLite journal together. A source bundle alone is not a database backup.
Copying only the journal or only SQL can lose the correspondence between cases and
remote effects. Do not delete a journal or create a new request ID to clear an
uncertain result. Inquiry is separate from resubmission.

A settled criterion response survives worker death and is reused on the same work
identity. An unsettled reservation stays consumed/unknown and routes for review;
it is not automatically resent. An uncertain payer packet blocks replacement by
a later revision. Index-only crashes and old-revision inquiry need private operator
inspection; the browser does not silently reconcile them.

The hosted tests prove these crash/restart mechanisms. **A full host-loss backup
and restore drill is still outstanding.** No PA RPO/RTO or off-host recovery claim
is made. Native document parsing is available only through trusted local tools;
this demo has no public upload endpoint and no native-parser sandbox claim.

## Evidence to show with the demo

- PR160: citation cards, durable model-work reservation/replay, protected desk and
  minimally patched dependency audit. All final PR and merged-main checks passed.
- PR161: operator payer exchange, SQL/API authorization, retained uncertainty,
  duplicate containment and two-packet trace correlation. All final PR checks passed.
- This closeout batch adds a single actual-service test of wait → supplement →
  reassess → submit → inquire. Its final-head hosted result is required before
  calling the complete path verified.
- The earlier development study remains168freshcalls,615/784cumulative. Its
  checked agreement was128/168 on constructed cases, not clinical accuracy. This
  new scripted demo does not improve or replace that measured result.

For a recording, show the seven steps above and close with the limitations on the
screen. A script walkthrough is supplied here; no screen recording is claimed.


See the [observed local and hosted verification](prior-auth-demo-verification.md)
for the completed checks and their distinct evidence boundaries.
