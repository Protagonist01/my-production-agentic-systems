# Prior Auth demo runtime: code walkthrough

This chapter covers the opt-in demo implementation built after the owner's November15
portfolio clarification. It extends the [release-readiness chapter](code-study-prior-auth-release.md)
without changing the frozen candidate/checker or historical provider evidence.

## Exact request and evidence flow

`extract_complete` first rejects noninvented notes and a context that does not name
the new candidate. It invokes the old extractor through `CompleteGateway`, which adds
one prompt supplement to address the observed missing-conjunction citations. This
transformation occurs **before** the final request reaches `DurableGateway`; request
admission and recording therefore see the actual bytes sent to its delegate. It
keeps the original schema, generation settings, exact-quote offset reconstruction
and conservative checker. A passing fake does not establish real model improvement.

`EvidenceReader.cards` authorizes the user through `ReviewStore.snapshot`, requires
the expected current version and invented provenance, and recomputes the published
result from its saved candidate. It rejects a mismatched result. For every exact
case span it tries the imported documents' pinned source maps via `IntakeReader.locate`.
A span outside a document is not mapped to it; a stale source raises rather than
being suppressed. A final canonical version/note/policy check prevents returning
assembled citations as current after a concurrent supplement.

Each card contains the policy's URL, source/text pins and original criterion span,
plus case spans and document locations. `mapped` means every returned case span has
a source location; it does not mean clinical validity or adequate semantic support.
`no_evidence` and `incomplete` remain visible states. Private quotations appear only
inside the existing authenticated case view. The browser uses textContent, a fixed
CMS link and the original session/selection fences; it does not interpret source HTML.

## SQL attempt control

`setup` pins a new `prior_auth_demo` schema; legacy SQL stays unchanged. `provision_scope`
is trusted administration. Runtime cannot INSERT/UPDATE scope rows or UPDATE/DELETE
reservations/settlements. Scope identity and contents are checked at admission.

`DemoWorker.step` claims only a provisioned tenant/case job, creates a bounded context
and invokes the new candidate. `DurableGateway.generate` locks the canonical case,
then its job, then serializes that scope with a transaction advisory lock. This
preserves publication's case-before-job order. A row-level lock on the scope itself
would require UPDATE privilege; the runtime deliberately lacks that authority.

Admission verifies scope, expiry, note/policy/request, current lease and case version.
It derives logical work identity from tenant/case/version/note/policy/criterion/candidate.
An existing reservation with no settlement returns an unavailable result with no
new delegate invocation. A settled matching response is hash-checked and reused.
Changed request bytes under that identity raise a conflict. A different explicitly
provisioned scope is not an automatic retry mechanism.

For new work, admission checks attempts, one-outstanding-request, stop state and token
headroom, then commits a reservation. Only afterward does it invoke the delegate.
Ordinary delegate errors become fixed-message unknown-usage failures and settle as
stopped. Process death leaves the reservation outstanding. A new worker cannot infer
that no network dispatch happened from the missing settlement. This intentionally
trades automatic availability for duplicate containment.

Settled responses are local recovery evidence. Fresh shared-provider admission is
still a separate responsibility: the opt-in live path requires a provider-scope pin
and explicit validator, and the shipped CLI refuses that path. Do not interpret a
provisioned fake scope or injected arbitrary gateway as an owner-approved provider grant.

After extraction, the worker retains only unaffected claims from the unchanged note
prefix and delegates publication to the old store. Publication rechecks version and
lease; a concurrent document/policy change cannot become a stale published result.

## Runnable composition and tests

The console initializer requires a new trial/output directory, verifies the pinned
CMS compilation, provisions a reviewer through an interactive password, imports an
invented note and provisions exact scripted requests. `ScriptedGateway` returns
controlled full-note quotations, labeled as scripted current attempts in the desk.
No key is read and no real model is called. The launch guide distinguishes this
workflow mechanism from an actual quality comparison.

Tests use real SQL for concurrent claims, scope exhaustion, role privileges, process
death before settlement, crash after settlement and document-resume source mapping.
The incomplete-citation unit test checks the actual claim directly, avoiding a vacuous
failure caused only by submitting an incomplete seven-criterion assessment. Browser
tests load both the original asset and demo appendage so logout/late-response fences
cover the composed script.

Material limits: no new provider-quality result, no public upload/native sandbox,
no browser payer-submission flow yet, and no full production/clinical qualification.
Read [the launch and verification guide](prior-auth-demo-runtime.md) for actual evidence
status and the remaining demo deliverables. Build Book Entry108 records construction.
