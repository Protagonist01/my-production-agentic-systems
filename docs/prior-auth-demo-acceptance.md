# Prior Auth portfolio demo: accepted scope and finish line

On November 15, 2026 the owner clarified that this project demonstrates the ability
to build an agent and accepted the recommendation: authoritative policy sources,
synthetic case documents, rigorous synthetic-case tests and the existing official
HL7 reference payer. This is the active demo-development target.

## What this approval resolves

- Clinical qualification for real patients is not a prerequisite to completing the
  portfolio demo. Keep the absence of clinical validation explicit and preserve the
  separate original production-release gates as unmet, not passed or deleted.
- Commercial payer credentials are not needed for this demo. Reuse the already
  tested independent HL7 reference service, with its actual responses clearly labeled.
- Synthetic facts and explicitly authored CPAP supplements may supply declared
  expected results for demo tests. They are not independently validated clinical gold.
- Pin the CMS national policy already used by the project; show a policy citation
  and exact case-document evidence for each finding. Do not use a research paper as
  proof that an individual synthetic patient met a requirement.

## Four deliverables to finish

### 1. Complete evidence and citations

- [ ] Every criterion displays its policy paragraph and exact synthetic document
  citations, with the source identity/location available for inspection.
- [ ] Every required subcondition is supported. Missing, conflicting or ambiguous
  evidence produces an explicit missing-information/review result.
- [ ] Fix the measured citation omissions, including positive test/type and prior
  order/supervision. Preserve the prior model outputs and original baseline results.
- [ ] Keep unresolved national/local short-study and fractional-threshold questions
  visible. A demo must not invent a clinical interpretation to make a case pass.

### 2. Connect the model to the operational workflow safely

- [ ] Explicit model-enabled composition works with authenticated, synthetic-only
  imports and the existing document wait/resume workflow.
- [ ] Durable per-criterion provider admission and settlement survive worker crashes;
  a lease retry cannot silently resend an unknown or already consumed model attempt.
- [ ] Budget, route, expiry, timeout, no-fallback, tenant and stale-version controls
  are exercised with SQL and mocked SDK responses before any new live run.
- [ ] Complete an expressly scoped live demo smoke test after its exact model grant.
  Existing study slots are not a standing runtime allowance.

### 3. Make the payer exchange visible end to end

- [ ] An authenticated operator explicitly submits a synthetic packet to the separate
  reference payer; the model cannot authorize submission itself.
- [ ] Display the actual submission receipt/status and inquiry result. Label the
  system as an HL7 reference payer and all patient content as synthetic.
- [ ] Demonstrate duplicate submission containment and recovery of unknown outcomes
  without blind POST retries.
- [ ] Never present processing-complete or A3/not-required as a clinical approval.
  Additional controlled response scenarios must be labeled simulated if supplied
  by an authored emulator rather than the reference service.

### 4. Package, test and demonstrate

- [ ] Supply a reproducible local launch/config guide with private credentials and
  a clear setup/readiness failure message. A hosted destination is still undecided.
- [ ] A frozen synthetic test pack covers complete, missing, conflicting, unrelated,
  wrong-subject, adverse-instruction and document-resume scenarios across supported
  layouts. Keep declared facts, expected outputs and model inputs separate.
- [ ] Test candidate evidence, exact citations, arithmetic, unauthorized effects,
  privacy, replay, concurrency and failures. Missing measurements remain unknown.
- [ ] Demonstrate one complete workflow: import → evidence review → missing-document
  request → supplement → reassessment → explicit reference-payer submission → inquiry.
- [ ] Publish measured results, known limitations and a short demonstration recording
  or walkthrough. Report synthetic-case agreement, not clinical accuracy.

The demo is ready only when these checks have actual evidence. This document does
not mark any new runtime feature implemented or declare the demo ready today.

## What remains separate

Real-patient validation, clinical reference qualification, commercial insurer
onboarding and production deployment acceptance remain future gates. Keep all
existing production field/slice requirements intact. Use a distinct demo milestone
instead of closing those gates as though synthetic tests satisfied them.

No new provider attempt limit, source export, hosting purchase, remote deployment
activation or real-patient use is authorized by accepting this demo recommendation.
The prior study ended at 615/784 cumulative attempts; its unused slots cannot move
to a new prompt, candidate or runtime use. Prepare a concrete bounded proposal for
any new calls when the revised demo composition is ready.

References: [engineering checklist](prior-auth-closure-checklist.md),
[original study and limitations](prior-auth-development-study-v1.md),
[code walkthrough](code-study-prior-auth-release.md).
