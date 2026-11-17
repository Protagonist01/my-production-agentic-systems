# Final local portfolio demo

The finish line is a synthetic evidence-review demonstration: inspect policy and
document citations, request a missing record, resume only the affected criterion,
and explicitly exchange an invented packet with the official HL7 reference payer.
Real patients, clinical qualification, commercial payer onboarding and remote hosting
remain separate. The earlier nine-call live result is preserved; this closeout
adds no model calls and does not improve its statistical evidence.

## Reproducible regression pack

`prior_auth_demo_regression.py` defines 19 immutable authored input scenarios and a
separate expected-output map. The cases cover text, selected C-CDA and FHIR narrative
layouts; complete/missing/negative/conflicting evidence; fractional/short-study
boundaries; incomplete adult/test/order citations; unrelated request/document;
wrong/unverified subject; uncertain relevance; unsupported plan; an attachment
instruction without education support; and a redacted fictional name. Neither the
source text nor the proposed candidate receives the expected-output map.

The runner deliberately proposes positive states with exact selected quotations.
That exercises the unchanged checker and intake boundary, including refusal when
an exact quote omits a required subcondition. It is not a language-model experiment,
a natural-document distribution, a clinical reference set or an unseen holdout.
The malicious-instruction case establishes that an unsupported positive proposal
is contained by this checker; it does not establish Gemini's resistance to every
prompt injection. Repeated layouts and related edits are not independent patients.

Input and reference manifests are separately pinned in the tests. Changing either
requires an explicit version/review decision, not quietly updating a passing score.
This separation follows the [Langfuse dataset guidance](https://langfuse.com/academy/datasets).
No live Langfuse dataset or clinical text export is created by this local pack.

```powershell
uv run --locked --all-packages --link-mode copy python prior_auth_demo_regression.py `
  --output D:/private/prior-auth/demo-regression-v1.json
```

The output must be a new path outside Git. It records all scheduled/observed cases,
actual and declared outcomes, individual failures, manifest pins and zero provider
calls. Missing/failed results cannot become passes. The accompanying unit checks
and actual SQL pack are:

```powershell
uv run --locked --all-packages --link-mode copy python -m pytest `
  tests/test_prior_auth_demo_regression.py tests/test_prior_auth_complete_citations.py
uv run --locked --all-packages --link-mode copy python -m pytest -o addopts= `
  tests/integration/test_prior_auth_demo_pack_state.py `
  tests/integration/test_prior_auth_demo_runtime_state.py `
  tests/integration/test_prior_auth_recovery_state.py `
  tests/integration/test_prior_auth_live_gateway_state.py
```

The SQL pack tests the same 19 inputs against actual scoped intake, worker and
source readback. Rejected cases cannot appear in canonical SQL; accepted cases must
retain the declared checked states and mapped positive citations. Existing companion
witnesses cover durable document resume, obsolete versions, concurrent workers,
crash/settlement replay, malformed or unavailable model output and clean-target
restore. The real-SDK/fake-HTTP witnesses are explicitly distinct from fresh Gemini
output. Native PDF/OCR, containment and deadlines remain the separately executed
[parser checks](prior-auth-demo-hardening.md), not invented extra language-model cases.

## Build and start the local official payer

Obtain the existing approved reference repository in an ignored/private directory,
and detach it at `10d40911cb90d6198aacec144b4bfc48466af2fb`. The build helper verifies
that exact revision and refuses modified or untracked server/library source. The
container file uses the immutable official Maven3.9.12/Java17 image selected from
the upstream build, a bounded Maven heap, the upstream server/library and license.
No frontend, telemetry Java agent, app credentials or source documents are included.
Native Maven dependencies still resolve during build; the completed image ID pins
the actual local output. This is not a byte-reproducible or audited upstream release.

```powershell
uv run --locked --all-packages --link-mode copy python prior_auth_reference_service.py `
  --root . --image-file D:/private/prior-auth/reference-image.txt `
  --build-repository D:/private/reference/br-payer
uv run --locked --all-packages --link-mode copy python prior_auth_reference_service.py `
  --root . --image-file D:/private/prior-auth/reference-image.txt
```

The first command refuses to overwrite an earlier image record. The second starts
or reuses only the checkout-owned container with the exact image/provenance and
loopback binding, no mounts, non-root image user, dropped capabilities and resource
limits. It refuses another service on the port or an altered existing container.
There is no automatic pull, replacement, removal, factory reset or broad Docker
cleanup. Readiness requires an actual FHIR CapabilityStatement from the service.

The reference service listens on its container interface so Docker can forward it,
but the host publication is only `127.0.0.1:8081`. This is a local reference service,
not a hardened commercial payer or authenticated internet service. Its default H2
database is transient. Keep the application submission journal across all restarts;
if the payer loses remote state, an inquiry may fail and that does not permit blind
resubmission. A saved application receipt is not an external-payer database backup.

## Connect the existing completed case

Bring up the existing checkout database using `python dev.py db-up`; keep its private
trial configuration and volume. Stop only the desk process serving the intended
trial before relaunching it with the three explicit payer options. Never kill an
unidentified listener or initialize over a saved case.

```powershell
uv run --locked --all-packages --link-mode copy python prior_auth_demo_console.py `
  --root . --trial <saved-trial> serve --port 8767 `
  --payer-endpoint http://127.0.0.1:8081/fhir `
  --payer-journal D:/private/prior-auth/<saved-case>/payer.sqlite `
  --binding-file D:/private/prior-auth/<saved-case>/bundle/request.json
```

The binding must be the exact request saved by that trial's import. Keep the same
journal path thereafter. This command serves saved results; it starts no model worker
and consumes no provider allowance. Credentials stay private. A separate future
fresh model demo needs a new exact authorization; the nine-call scope is exhausted.

## Five-minute presentation

1. Explain the declared scope: a fictional adult initial-CPAP case, a pinned CMS
   policy compilation, and evidence assistance rather than clinical authorization.
2. Sign in and show the saved policy paragraph and document quotation for each
   finding. Use the retained initial record to explain why education was missing.
3. Show the recorded document request, fixed education supplement and version3
   result. Only education was reassessed; its source is the supplement. The earlier
   live result used nine calls total, including two canaries, and restart sent zero.
   A walkthrough of retained results is not a new live execution.
4. With the reference payer connected, explicitly submit the synthetic packet and
   inspect the actual receipt. Inquire separately and verify packet correlation.
   A3 means authorization is not required in the reference response, not treatment
   approval. A repeated submit must return the same receipt without another POST.
5. Sign out, demonstrate private-access refusal, and show the actual test report,
   preserved failures and limits. Explain unknown-cost handling and recovery rather
   than promising clinical accuracy, commercial integration or production availability.

The existing [nine-call result](prior-auth-live-demo-result.md),
[full workflow walkthrough](prior-auth-demo-walkthrough.md),
[payer controls](prior-auth-payer-desk.md) and
[restore/parser guide](prior-auth-demo-hardening.md) supply the supporting material.
Record a video only from the verified running application; no recording is claimed
by this written package. Local SQL/container and reference-service results must be
verified before marking the final local exchange complete.

## Observed local closeout, November 17

The authored pack passed 19/19 declared software cases. Its 25 unit/launcher checks
and 19 actual SQL cases passed (44 total); strict typing covered 295 source files.
These counts do not expand the completed nine-call model evidence.

The pinned official image built locally. Under severe memory pressure the initial
eight-minute startup check expired; the retained service later completed startup
in about 795 seconds and returned an active FHIR R4 CapabilityStatement. Keep the
timeout and failed earlier builds as part of the operational record. Starting the
saved desk also took longer than the first HTTP probe; that connection refusal
occurred before any submission.

The actual running desk at `http://127.0.0.1:8767` then passed authenticated
saved-case submission, an identical repeated receipt, and separate correlated
inquiry returning A3. The private journal retained one attempt, one packet and one
inquiry. All seven source cards remained met/mapped at version 3; logout restored
private-access refusal. Clinical note text was not exported to the payer. The
private capture is alongside the completed model run in
`D:/document/.cache/production-agents/prior-auth/local-gemini-demo-2026-11-16-v1`.
The provider readback remained 624/793, zero unsettled, nine newly consumed calls
and 169 preserved old bound slots. No new model calls were made for this closeout.

This is a functioning local synthetic protocol demonstration. Broad model quality,
clinical adjudication, commercial payer interoperability and remote deployment
remain unestablished. The reference service is transient and startup performance
on this memory-constrained machine is unsuitable for an availability claim.
