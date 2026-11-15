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

- [x] Every criterion displays its policy paragraph and exact synthetic document
  citations, with the source identity/location available for inspection.
- [ ] Every required subcondition is supported. Missing, conflicting or ambiguous
  evidence produces an explicit missing-information/review result.
- [ ] Fix the measured citation omissions, including positive test/type and prior
  order/supervision. Preserve the prior model outputs and original baseline results.
- [x] Keep unresolved national/local short-study and fractional-threshold questions
  visible. A demo must not invent a clinical interpretation to make a case pass.

### 2. Connect the model to the operational workflow safely

- [ ] Explicit model-enabled composition works with authenticated, synthetic-only
  imports and the existing document wait/resume workflow.
- [x] Durable per-criterion provider admission and settlement survive worker crashes;
  a lease retry cannot silently resend an unknown or already consumed model attempt.
- [ ] Budget, route, expiry, timeout, no-fallback, tenant and stale-version controls
  are exercised with SQL and mocked SDK responses before any new live run.
- [ ] Complete an expressly scoped live demo smoke test after its exact model grant.
  Existing study slots are not a standing runtime allowance.

### 3. Make the payer exchange visible end to end

- [x] An authenticated operator explicitly submits a synthetic packet to the separate
  reference payer; the model cannot authorize submission itself.
- [x] Display the actual submission receipt/status and inquiry result. Label the
  system as an HL7 reference payer and all patient content as synthetic.
- [x] Demonstrate duplicate submission containment and recovery of unknown outcomes
  without blind POST retries.
- [x] Never present processing-complete or A3/not-required as a clinical approval.
  Additional controlled response scenarios must be labeled simulated if supplied
  by an authored emulator rather than the reference service.

### 4. Package, test and demonstrate

- [x] Supply a reproducible local launch/config guide with private credentials and
  a clear setup/readiness failure message. A hosted destination is still undecided.
- [ ] A frozen synthetic test pack covers complete, missing, conflicting, unrelated,
  wrong-subject, adverse-instruction and document-resume scenarios across supported
  layouts. Keep declared facts, expected outputs and model inputs separate.
- [ ] Test candidate evidence, exact citations, arithmetic, unauthorized effects,
  privacy, replay, concurrency and failures. Missing measurements remain unknown.
- [x] Demonstrate one complete workflow: import → evidence review → missing-document
  request → supplement → reassessment → explicit reference-payer submission → inquiry.
- [x] Publish measured results, known limitations and a short demonstration recording
  or walkthrough. Report synthetic-case agreement, not clinical accuracy.

Checked items above are verified engineering mechanisms: PR160/PR161 and the
subsequent closeout actual-service test. The gateway is scripted in that workflow;
those checks do not establish live-provider readiness or clinical correctness.
The complete path is an automated authenticated SQL/API witness plus a written
[walkthrough](prior-auth-demo-walkthrough.md), not an observed local browser recording.

The demo is not yet fully ready as a live-model demonstration. Citation improvement
on fresh provider output, exact live composition/readiness and its bounded smoke test
remain. Host-loss backup/restore and native parser isolation are also unverified;
public native uploads remain disabled. A chosen remote deployment host is undecided.

The private no-provider proposal at
`D:/document/.cache/production-agents/prior-auth/citation-repair-proposal-2026-11-15-v1`
uses the12already exposed invented development notes, separate constructed references,
2canaries and166domain requests. It proposes168newattempts and same-file ceiling952,
preserving615consumed and169old unspent/bound slots. It is prepared, not authorized
or dispatchable: exact final-source/environment, grant implementation and selected-
host readiness remain prerequisites. No new provider call or release follows.

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
