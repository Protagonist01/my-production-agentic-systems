# Prior Auth document pipeline and demo

Implementation dated2026-11-12; branch `codex/prior-auth-document-pipeline`, based on
main2cf9d69. This opt-in layer preserves the frozen seven-criterion assessment package,
its prompts, historical reviewer schema and all release requirements. It implements
the intake, adapters, timing, policy selection, development scorecard and local payer
mechanisms requested by the owner. It does not complete release issue#51.

## What each recommendation now has

| Requested improvement | Executable path | Evidence and remaining work |
|---|---|---|
| 1.Unrelated requests/documents | `prior_auth_intake.decide`, `prior_auth_pipeline.prepare` | Distinct unrelated request/document, wrong subject, uncertain binding/relevance, redaction review, unreadable and policy mismatch states. Trusted importer assertions are required. No claim that a new semantic relevance model has been qualified. |
| 2.Adversarial situations | Bounded parsers, exact pins, unchanged citation checker, scoped atomic handoff | DTD/entity and active narrative refusal, no URL dereferencing, malformed file quarantine, prompt-injection and wrong-tenant tests. Native parsers still require OS/container isolation before hostile public uploads. |
| 3.Provider/document variation | Text, C-CDA narrative, selected FHIR narrative, text PDF, image-only OCR | Source SHA, normalized text SHA, Unicode offsets, section/resource locators and page/word boxes. Formats are explicit, not inferred from extensions. PDF/OCR require extraction review. Header identity extraction is not trusted patient matching. |
| 4.Subprocess timing | `Profiler`, `TimedGateway`, `ProfiledAssessor`, `ProfiledReviewStore`, native command spans | Extraction, PDF metadata/text/raster, OCR, gateway, assessment, citation check, SQL transaction, claim/expiry/publication and total spans when those wrappers are used. Inclusive times are not added into wall time. Queue/lock/human/document waits and child CPU/RSS remain unmeasured. |
| 5.Evaluation metrics | `prior_auth_scorecards.score`, `prior_auth_diagnostics.py` | Planned-slot denominators, refusal/route/criterion agreement, claimed-met precision, review routing, both recommendation-risk denominators, provenance/slices, unknown cost/token/call/latency counts, source/parent/template split checks. Missing references never become clinical gold. |
| Demo submission/response | `SyntheticPayer`, `prior_auth_demo.py` | Durable replay receipts, exact case/version/note/policy binding, role checks, invented approved/denied/additional-information scenarios and fixed message previews. Local emulator only; no insurer endpoint, EHR, PAS conformance claim or clinical adjudication. |

## Intended clinical and payer scope

The production-shaped evidence workflow still supports only the existing **adult
initial-CPAP CMS national-policy slice**. Different provider document layouts can
contribute evidence to that same slice. Multiple actual insurer policies/services are
not silently treated as equivalent. The registry matches payer, plan, service and
service date to exactly one pinned policy. Zero matches means unsupported; overlapping
matches mean ambiguous. Effective-until is exclusive. The registry's review/use strings
are declarations, not authenticated clinical qualification.

Demo provider IDs `demo-clinic` and `demo-sleep-lab` represent referral relationships;
they need not be equal. A trusted importer must verify that each document belongs to
the bound subject and case. A document's embedded patient name or instruction cannot
grant that authority. New real payer/service policies need their own sourced criteria,
mapping/reference review, effective dates and evaluation before use.

## Import and durable handoff

1.A trusted local operator creates `ImportRequest`: exact source and normalized-text
pins; case/payer/service bindings; reviewed relevance, binding and redaction references;
and, for PDF/OCR, an extraction review reference. The current request contract permits
only invented provenance. It is not a public upload API or permission to process PHI.
2.`prepare` verifies bytes, extracts supported narrative, checks applicability and
applies reviewed redaction spans to normalized text. Redaction preserves character
length, so source locations remain usable. A reference string does not prove that
every identifier was found. The operator must review the exact text.
3.`IntakeStore.accept` checks reviewer/case scope and revalidates the prepared contract.
An advisory transaction lock serializes initial enrollment and duplicate delivery.
The receipt fingerprint covers the **entire prepared payload**, not only a caller's
request-hash declaration.
4.An initial accepted note enrolls the existing case/job. A supplement must match the
stored case binding, current policy pin, version and unexpired document wait. The
existing delivery logic invalidates affected criteria and queues reevaluation.
5.The receipt, accepted document/location metadata and legacy case/job mutation share
one Postgres transaction. A joined store overrides only transaction ownership; it
never commits inside that transaction. An insert/permission failure rolls everything
back. This avoids a separately committed outbox and its crash-reconciliation problem.
6.Rejected documents store only hashes and a fixed intake decision. They do not create
or modify the legacy case, text, version, claims or jobs. Duplicate receipts replay;
reusing a document ID with a different payload is a conflict, requiring a new identity.

Install the old reviewer schema using its existing administrator command first. Then
call `prior_auth_store.setup(admin_connection, runtime_role)` explicitly. This adds
`prior_auth_intake` with a pinned schema, least-privilege grants and no public access.
Runtime access is SELECT/INSERT only on its three tables. Whole-database backup must
include this schema. Rollback disables the opt-in importer; do not drop receipts or
rewrite the frozen schema to roll code back.

Accepted document records retain only reviewed/redacted normalized text, regions,
case version, offset into that version's combined note, note SHA and binding SHA.
PDF boxes use PDF points; OCR boxes use pixels of the bounded rendered image. A quote
is mapped through `Document.locate(start,end)` in normalized-text coordinates, then
the stored note offset. Layout extraction and exact citation matching do not establish
medical entailment or policy meaning.

## Document capabilities and limits

| Adapter | Included | Explicit limitations |
|---|---|---|
| UTF-8 text | Exact normalized text and one region | Binary/NUL and invalid UTF-8 refused. |
| C-CDA | HL7 ClinicalDocument section/text narratives | Structured clinical entries and header identity are not interpreted; absent narrative is refused. |
| FHIR JSON | Composition sections, supported resource narratives, DiagnosticReport conclusion | No remote reference/attachment lookup; not a FHIR validator or patient-resource matching implementation. Unsupported/no narrative is refused. |
| Text PDF | Poppler bbox-layout words and page regions | Missing/corrupt/encrypted/no-text files refuse; review needed for reading order, missing tables and wording. |
| Image-only PDF | Bounded Poppler raster and Tesseract TSV words/boxes | English single-block OCR configuration; handwriting, rotation, columns, degraded scans and units need review. Never treat OCR confidence as clinical correctness. |

Configure trusted absolute paths to `pdfinfo`, `pdftotext`, `pdftoppm` and `tesseract`
through `NativeTools`. Attachment content selects neither executable nor arguments.
Defaults:10MB source,20pages,100k normalized characters,20k regions,30seconds per native
command and120seconds across a document's native commands. Output and raster sizes
are monitored; subprocesses are killed and reaped on timeout. Limits are fail-closed
operational bounds, not a sandbox or proof against native-parser vulnerabilities.
No native output/stderr or clinical text is written to timing reports.

The required hosted native canary generates invented PDFs, verifies text extraction,
renders an image-only PDF with no text layer, exercises actual OCR and source regions,
and refuses21pages. Windows without the native binaries cannot claim that proof.
The [Tesseract command documentation](https://tesseract-ocr.github.io/tessdoc/Command-Line-Usage.html)
describes the TSV/segmentation interface used here. Production needs a pinned native
worker image, restricted filesystem/network/resources and a representative layout/OCR
study; the hosted canary verifies mechanisms on the installed CI tools only.

## Run the demo and diagnostics

From the repository root after locked setup:

```powershell
uv run --locked --all-packages --link-mode copy python prior_auth_demo.py --output artifacts/pa-demo
uv run --locked --all-packages --link-mode copy python prior_auth_diagnostics.py --output artifacts/pa-diagnostics
uv run --locked --all-packages --link-mode copy python -m pytest -q tests/test_prior_auth_pipeline.py tests/test_prior_auth_sandbox.py
```

The demo emits zero-provider-call output and a durable local SQLite payer receipt.
It does not exercise the Postgres handoff; the required SQL suite does that separately.
For another simulated outcome, instantiate `SyntheticPayer` with an explicit trusted
scenario. Its response survives restart/replay even if the later scenario changes.
Stale versions/pins and different payloads under the same request ID are refused.

The diagnostic runner executes26invented cases in13paired families and two baselines,
writing52actual observations and input/request pins. These are development mechanism
fixtures. The two variants of each family are related, not independent samples. All
cases stay in development; no holdout is exposed. The model comparator is **not run**.
Route expectations are authored proposals; all criterion reference slots remain unknown.
Broken-PDF and static recovery slices do not prove OCR accuracy or process recovery;
the native and real SQL suites provide separate mechanism witnesses for those paths.
No result here qualifies #51 or supplies a clinical sample-size/confidence claim.

The executed2026-11-12 development capture observed52baseline outputs. Both comparators
matched26/26authored intake outcomes. Among14admitted cases, rules matched12/14proposed
routes and always-review matched2/14. The rules baseline sent both contradictory-AHI
fixtures to request-information rather than the proposed qualified-review route; keep
that disagreement visible. Neither comparator emitted an evidence-complete recommendation.
All98criterion reference slots are unknown, so criterion agreement is0/0with a null
rate. These results measure this authored matrix only; they are not provider/clinical
accuracy, proof of independence or a passing release study.

Scorecards include zero-coverage slices, missing/failed outputs, missing references and
unknown accounting. The all-complete recommendation denominator additionally reports
a known-error lower bound with unreferenced recommendations listed separately. This
cannot be presented as a validated error rate when recommendation references are absent.
Unknown criterion labels have no agreement/precision denominator. Exact quote integrity
and clinical support remain different measures. Human workload, turnaround time,
appeals, overturn rates, first-pass insurer acceptance and real-world outcomes require
later independently collected workflow/payer evidence.

## Timing and operational use

Create a new profiler per bounded job, pass it into `prepare`, use `TimedGateway` or
`ProfiledAssessor` for an explicitly authorized injected gateway, and use
`ProfiledReviewStore` with the unchanged `ReviewWorkflow`. Claim/expiry/publication and
whole SQL transactions are measured, including failure paths. Publication includes the
legacy checker and transaction. Separate SQL statement, lock and queue timings are not
inferred from it. Retrieval timing in `ProfiledAssessor` is an identical deterministic
preflight; extraction repeats retrieval internally. Do not subtract it to invent a
clean model-only or retrieval-only latency decomposition.

Gateway attempts count before dispatch; response usage is retained as numeric metadata.
Exceptions leave an unknown-usage slot. Known token/cost subtotals are labeled as such;
they do not fill missing usage with zero. Nothing automatically exports notes, prompts,
model rationales, credentials or telemetry. Langfuse wiring would require a separate
reviewed payload-free integration; the existing shared call ledger/stop is unchanged.

## Optional external demo target

For a later EHR/payer interoperability demonstration, use the official
[HL7 Da Vinci prior-auth reference implementation](https://github.com/HL7-DaVinci/prior-auth)
and [SMART testing tools](https://docs.smarthealthit.org/) with invented/synthetic data.
Those are external reference systems, not commercial insurers. This change does not
install/connect them, disable their authentication or claim DTR/CRD/PAS conformance.
Before that step: pin a compatible FHIR/IG/server version, map the local evidence and
requested service into validated resources, configure authenticated endpoints, test
additional-information/denial/approval/cancellation/timeout/duplicate correlation, and
retain actual request/response provenance without implying clinical validation.

Production still needs an applicable/qualified policy and language-reference package,
fresh frozen evaluation, real sandbox integration evidence, protected upload isolation,
privacy/security review and tested deployment/recovery. These are concrete remaining
requirements, not evidence supplied by this implementation merge.
