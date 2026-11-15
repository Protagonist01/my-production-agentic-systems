# Prior Auth demo: complete citations and a durable assessor

This opt-in implementation follows the [accepted portfolio-demo target](prior-auth-demo-acceptance.md).
It adds a separately versioned citation candidate, a SQL-backed assessor, authenticated
source cards and a runnable scripted demo. It preserves the original domain/checker behavior, historical study results and
shared provider ledger. A separate OpenTelemetry security patch updates the
telemetry dependency pins and active invented replay fixture; historical captures
retain their original lock.

## What is implemented

- `prior_auth_complete_citations.py` adds a versioned prompt supplement: cite all
  applicable subconditions, including separate sentences/documents and relevant
  negative/conflicting context. It supplies no new clinical threshold interpretation.
  The final request reaches admission before its fingerprint is checked/reserved.
- `prior_auth_demo_runtime.py` can run the new candidate inside a tenant/case-scoped
  SQL job. Reservation and canonical case/version/lease checks happen in one database
  transaction before delegate invocation. Completed responses are reused after a
  worker crash; unknown reservations cannot be automatically resent.
- `prior_auth_evidence_cards.py` verifies the published result against the current
  pinned note/candidate/policy and supplies the exact policy quote plus source-mapped
  document evidence. Unmapped evidence is marked incomplete, not given an invented
  location. A changed case during assembly requires refresh.
- `prior_auth_demo_web.py` reuses the existing protected reviewer API and desk design.
  The appended presentation script shows both citation types and distinguishes
  scripted current attempts. Existing login, logout, CSRF, tenant and stale-response
  handling remain in force. It adds no unauthenticated evidence endpoint or upload.
- `prior_auth_demo_console.py` creates a new isolated trial, provisions an interactively
  supplied reviewer password, imports one invented complete case against the pinned
  CMS policy compilation, registers an offline-only scope, and serves the demo desk.

The shipped console uses `ScriptedGateway`, which returns controlled invented output.
**It does not call Gemini and is not a model-quality evaluation.** The injected assessor
interface supports a separately authorized model gateway, but there is no credential
loader or live-provider switch in this console. A fresh provider comparison is still
needed to measure whether the changed prompt improves actual model citation selection.

## Run the scripted local demonstration

Prerequisites: the existing locked editable checkout, Docker/Postgres, the previously
pinned CMS source directory and an unused trial name/private output directory. Source
and evaluator files remain outside Git. Use a new trial; the initializer refuses to
replace existing accounts/state. The example paths are illustrative.

```powershell
uv run --locked --all-packages --link-mode copy python prior_auth_demo_console.py `
  --root . --trial pa-demo-citations initialize `
  --directory D:/private/prior-auth/demo-citations `
  --policy-directory D:/private/prior-auth/pinned-source-v1

uv run --locked --all-packages --link-mode copy python prior_auth_demo_console.py `
  --root . --trial pa-demo-citations worker `
  --scope D:/private/prior-auth/demo-citations/scope.json

uv run --locked --all-packages --link-mode copy python prior_auth_demo_console.py `
  --root . --trial pa-demo-citations serve --port 8766
```

Open `http://127.0.0.1:8766`, sign in as `demo-reviewer` with the password entered
during initialization, select the case and expand **Policy and case sources**.
The scope lasts one hour; it cannot be renewed by the runtime role. No password is
written to the source bundle, arguments or report. The private bundle contains the
scope, request, policy, source and a file-hash manifest. Initialization failures can
leave partial state in the new isolated trial; inspect it rather than retrying under
another identity or silently overwriting it.

The required policy directory contains the previously pinned CMS HTML, SourcePin,
selected prose and compiled policy. Its bytes and spans are verified before setup.
The compilation remains AI-provisional. Its byte identity is not clinical qualification.

## Durable work, provider budgets and recovery

The additive schema owns immutable scope documents, reservations and settlements.
Trusted administration provisions exact request fingerprints, case/tenant membership,
candidate revision, time interval, token and attempt limits. The runtime role has
SELECT only on scopes and SELECT/INSERT only on attempts and settlements; it cannot
increase limits or rewrite responses. Schema bootstrap is explicitly pinned.

Work identity includes case version, note/policy pins, criterion and candidate version.
A changed request under the same work identity is refused. A settled matching response
may be reused only while its current lease, case and provisioned scope remain valid.
A crash after reservation leaves an outstanding row: subsequent invocations return
review without another delegate call. One outstanding request blocks other dispatches
in that scope. A failed/unknown-usage response stops further fresh work in that scope.
No automatic provider retry or fallback is introduced.

For a future live delegate, a scope also needs an external provider-scope pin and an
explicit shared-provider authorization validator. This local SQL scope is an additional
fence, not a second lifetime allowance or a substitute for the shared Gemini controls.
The CLI refuses live scopes. Existing job leases can retry; these durable attempt
records are what prevent that retry from silently duplicating provider work.

Attempt admission reserves the existing full input/output ceiling. It proceeds only
when that ceiling fits after known settled usage; unknown usage fails closed. A
response is settled even if the case becomes obsolete while the delegate is running,
but the original store's compare-and-publish fence rejects obsolete publication.
Private responses remain in the database for recovery; they are not emitted in public
timing logs. Include this schema in any future PA backup/restore inventory.

This trusted local worker is not an OS sandbox. Hostile native uploads remain disabled
until the separate parser isolation work is completed.

## Verification and remaining demo work

Local candidate tests exercise complete conjunctions, incomplete citations, versioned
request identity, provenance restrictions and instruction/data separation. Web tests
exercise the inherited authentication boundary and explicit demo labels. The existing
browser race test now also loads the appended presentation code.

The real-SQL suite additionally covers settlement replay after crash, death after
reservation, concurrent workers, scope exhaustion, restricted privileges, only-affected-
criterion reassessment and source mapping across a supplement. Hosted SQL results must
be checked for the actual PR head; local Docker was unavailable during development.

The already tested external reference-payer transport remains unchanged. This batch
does not add a browser submission button or claim a new actual payer exchange. The
remaining demo work is the explicit operator submission/inquiry presentation, native
worker isolation/packaging, the newly scoped live candidate comparison and final
end-to-end demonstration. Clinical/commercial production qualification remains separate.


PR160 initial hosted validation (e0df1db): all four Windows/Linux Python3.12/3.13
quality jobs, Postgres isolation and independent reference payer passed. The first
dependency audit failed CVE-2026-126360; the minimal OpenTelemetry patch then passed
the local locked audit. Focused replay/candidate/web tests:94passed; browser
session regressions passed. These are engineering/synthetic evidence only. Final
head CI must additionally cover the authenticated citation API regression.


The subsequent [operator payer-desk composition](prior-auth-payer-desk.md) adds
optional explicit submission/inquiry using the same protected desk and canonical
state. It is separately verified; the initial citation batch did not include it.
