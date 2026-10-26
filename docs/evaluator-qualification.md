# Evaluator qualification and reference applicability

2026-10-26, `codex/evaluator-qualification` against merged baseb909aa7. This implements the
next offline portion of the [execution plan](automated-review-execution-plan.md), advancing
#33/#45/#60 preparation. It measures evaluator behavior; it does not supply a human review,
an accepted replacement evidence policy or permission to deploy a model judge.

## Trace the report

[`QualificationDataset`](../harness/src/agent_harness/evaluator_qualification.py) defines
one agent/field, frozen reference labels, input/reference hashes, source/template keys,
development/calibration/holdout splits, exposure and applicability declarations. The expected
label means the answer under evaluation should be accepted or rejected, not that a patient,
contract or complaint has a general positive/negative outcome. Failed state invariants and
critical-reject cases cannot have accept references.

`QualificationProtocol` pins that dataset and the evaluator configuration before execution.
It supplies repetitions, required slices, group/class coverage floors, scheduled accuracy,
decision coverage, false-accept/false-reject limits and group-error uncertainty. Limits have
no permissive production defaults. References and sample-size rationale are required inputs.
These declarations and hashes do not authenticate a publisher, reviewer or risk owner.

`QualificationStudy` binds the protocol to observations with exact case/trial/input/evaluator
identities and capture times. A failed parse/provider operation carries a failure code and
no decision; abstention is a separate valid decision. Duplicate/extra rows, mismatched pins,
changed input/evaluator identities and time-order violations refuse the report.

`qualification_report` merges connected source/template keys and identical input hashes across
the entire population before checking split separation. An exact copied input cannot evade
the check merely by receiving a new case ID/group key. Semantically related examples still
need correctly assigned provenance keys. Conflicting labels for identical input hashes refuse.

The reporter then walks every scheduled case/trial, including absent rows. Calibration and
holdout results are separate. Missing/failed calibration, a missing reference class or a
critical calibration failure blocks criteria. Holdout and every required slice must meet
the explicit limits; a good overall score cannot hide a failed slice.

Each scope reports:

- true accept, false accept, true reject and false reject;
- scheduled acceptable/unacceptable denominators and unresolved counts for each class;
- missing, failed and abstained observations;
- accuracy over the whole schedule and conditional accuracy over actual accept/reject decisions;
- decision coverage globally and for each reference class;
- false-accept/false-reject rates over scheduled class examples and over decided class examples;
- connected source groups, failed groups and separate class/group uncertainty bounds.

An abstention cannot turn a missing decision into a correct rejection. A judge can have100%
conditional accuracy yet fail because it avoids difficult cases. Every group with any wrong,
missing, failed or abstained repetition contributes to group error. Repetitions do not create
independent sources. The shared `binomial_bounds` helper supplies exact two-sided95% boundary
limits and its existing Wilson-envelope interior approximation; these are conditional on
independent, comparable groups, not a proof of representative sampling or model independence.

Known invariant failures accepted by a judge and critical cases not explicitly rejected
block criteria independently of configurable average error limits. Provisional AI reference
labels or missing applicability for calibration/holdout do not qualify the reference basis.
Unknown holdout exposure blocks; public references are disclosed and never called unseen
model-training data. Public labels can test a component without proving generalization.

The result's `criteria_met` only means that the supplied observations meet the supplied
diagnostic protocol. `release_allowed`, `human_review_supplied` and
`unseen_model_data_claimed` remain false. The existing `Review` contracts and domain release
profiles are unchanged. There is no automatic activation, Langfuse mutation or provider call.

## Safe offline entry point

[`evaluator_qualification_cli`](../harness/src/agent_harness/evaluator_qualification_cli.py)
reuses the planning reader's duplicate-key refusal,1MB input limit and canonical pin checks.
Module execution installs the existing outbound-network denial hook. Supply independently
recorded canonical pins; never manufacture approval by calculating a new pin from a substitute.

```powershell
python -m agent_harness.evaluator_qualification_cli `
  --dataset <private-dataset.json> --dataset-sha256 <dataset-pin> `
  --protocol <private-protocol.json> --protocol-sha256 <protocol-pin> `
  --study <private-study.json> --study-sha256 <study-pin> `
  --output <new-private-report.json>
```

Output creation is exclusive. A blocked protocol writes an inspectable failed report and
exits1; invalid input or existing output refuses without overwriting. Exit0is not deployment
authorization. Source text and raw identifiers are absent from aggregate metrics; keep all
raw datasets/observations private and review aggregate contents before publication.

## Actual CUAD reference applicability audit

The existing raw archive and both derived stores were reverified read-only against prepared
manifest pin `b852424ab854c30bd730ccc90a799907e02d3875a3066d203aed36f842f78540`.
Original source/store checks and every publisher target passed. No original records, labels,
splits or pins changed. No source text or original identifiers entered the chat or a provider.

The [aggregate audit](data/reference-applicability-v1.json) records20,910questions:
6,702answerable,14,208no-answer,13,823published spans and457inferred document families.
[`reference_coverage`](../projects/revenue-integrity/src/revenue_integrity/reference_applicability.py)
revalidates target contracts, refuses duplicate cases and cross-split families, and reports
all/development/holdout answerability and family counts by category. Its pure aggregation
function does not verify source files: the separate source-to-store verification does that.

All41categories have at least one answerable holdout reference, but coverage is uneven:
Price Restrictions and Source Code Escrow each have only one answerable holdout family;
Most Favored Nation and Non-Disparagement each have five. Document Name and Parties have
no no-answer holdout examples. These cannot establish well-covered class-specific error
limits simply because total corpus size is large. No-answer span recall stays inapplicable;
it is not reported as perfect recall. Family grouping is inferred, not independently proven.

These publisher labels can support reference-relative span extraction/answerability in
their original task. They do not establish normalized subscription terms, SIM invoice
deltas, general contract meaning, authorization/state recovery or clinical validity. The
[official CUAD description](https://www.atticusprojectai.org/cuad/) identifies lawyer-supervised
clause annotations; our applicability decision must retain that limited annotation purpose.

## Candidate external references, not acquired cohorts

| Source | Possible use | Why it is not blanket replacement evidence |
| --- | --- | --- |
| [ContractNLI](https://stanfordnlp.github.io/contract-nli/) | Contract entailment, contradiction, not-mentioned and evidence-span tests | Publisher describes607NDAs and17fixed hypotheses under CC BY4.0. NDA interpretation does not automatically cover subscription billing terms. No download, new split or model export occurred. |
| [MedNLI](https://physionet.org/content/mednli/1.0.0/) | Clinical inference diagnostics with doctor-authored labels | Credentialing, training and DUA apply; metadata inspection grants no access/export rights. Clinical inference is not CMS coverage-policy validation. No restricted records were accessed. |
| [CFPB database](https://www.consumerfinance.gov/data-research/consumer-complaints/) | Disclosed consumer-taxonomy and narrative references | Official documentation describes consumer-selected categories and nonrepresentative coverage. It does not establish our elevated-risk/ambiguity labels. |

Next: source-specific applicability review and an exactly scoped reference cohort for each
semantic field, followed by a frozen evaluator study within actual provider permissions.
The Gemini180allowance is not silently repurposed to new roles; Groq remains invented-smoke
only. This batch uses zero provider attempts and does not activate a model judge.

## Tests and remaining work

Focused tests exercise all-abstain/always-accept/always-reject behavior, class-specific
abstention hidden by an acceptable overall score, exact confusion counts, tiny-group
uncertainty despite perfect repetitions, transitive/identical-input leakage, unqualified
references, missing classes/slices/calibration, invariant overrides, identity/time tampering,
duplicate-key input and exclusive output. Invented permissive protocol fixtures prove branch
behavior only; they are not production thresholds or qualified domain examples.

No model reviewer has been calibrated against a real semantic cohort yet. Source/label
applicability, risk limits, representative coverage, capture/accounting and an explicitly
accepted replacement evidence policy still matter. [Build Book Entry60](../BUILD_BOOK.md#entry-60--test-the-evaluator-without-hiding-abstentions-or-weak-references)
records construction; final hosted and postmerge results belong on the delivery PR.
