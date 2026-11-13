# Prior Auth: qualification, fresh studies and payer interoperability

This implementation continues the initial adult CPAP evidence assistant from PR158.
It never approves insurance coverage or recommends treatment. The three workstreams
below have different evidence requirements; a successful HTTP request cannot qualify
clinical meaning, and agreeing with constructed labels cannot qualify patient records.

## Source findings that change the evaluation

The authoritative national source is [CMS NCD240.4, version3](https://www.cms.gov/medicare-coverage-database/view/ncd.aspx?ncdid=226&ncdver=3).
Its effective date is March13,2008. The already pinned private compilation contains
seven criteria and exact source spans. Its canonical SHA256 is
`ab967cf50cd496452cd9a6924afd17b661aec326d18a8310331e0de64df08796`.
Preserve its AI-provisional review status. Verifying its bytes proves custody, not
the clinical correctness of our interpretation or its applicability to every plan.

Two concrete concerns were found in the legacy checker:

1. It can group all AHI/RDI numbers as contradictory. CMS defines different
   measurements; unequal AHI and RDI values alone do not establish contradiction.
   Distinguish competing observations of the same measure in the same study from
   different measures, different studies and historical observations.
2. Its short-study check compares events to the reported rate multiplied by two.
   [CMS LCD L33718](https://www.cms.gov/medicare-coverage-database/view/lcd.aspx?lcdid=33718)
   explicitly describes minimum counts of30/10 for its branches. That is a local
   coverage policy with separate applicability. Do not silently use it as national
   semantic gold. The proposed national structured reference leaves this judgment
   unresolved; a separately named local-count proposal exists for method review.

The literal national thresholds also leave a fractional value between14and15 without
an explicit rounding rule. The draft marks it insufficient; that is a proposed
conservative handling choice, not a new CMS rule. Preserve the frozen legacy checker
and old captures while measuring these differences in a separate candidate version.

## Qualification matrix

| Required field | Independent check available now | Remaining qualification evidence |
| --- | --- | --- |
| criterion_state | Separate structured-fact predicates on authored facts; CMS source pins | Applicable qualified natural-note facts and policy interpretation |
| support_span | Exact Unicode offsets, quote identity, note/source pins | Whether the quote actually supports the clinical claim, including context |
| contradiction | Same-study constructed measure counterexamples | Temporal context, distinct measures, negation and competing clinical observations |
| missing_information | Authored absent fields; independent missing-document state | Whether a document is clinically sufficient for this criterion |
| disposition | Explicit state-machine and no-authorization action checks | Qualified reference mapping from checked claims to the assistive disposition |
| no_unsupported_met | Counterfactual edits; exact evidence requirements | Independent semantic support judgments across representative records |
| privacy | Denied imports, content-free traces/readbacks, invented-only transport | Actual deployment isolation/retention and permitted real-record workflow |
| review_durability | SQL isolation, version/wait/lease/replay and recovery witnesses | Deployment-specific recovery and operating evidence |

`prior_auth_reference_method.py` imports neither the candidate nor its recognizer to
derive expected states. It accepts one structured constructed study. This makes
arithmetic disagreements inspectable without pretending that authored facts are
independent natural-language clinical annotations. It never returns a qualification
approval. All eight fields and all eight existing holdout slices remain required.

For clinical language references, obtain applicable qualified evidence or qualify a
separate evaluator against applicable independent references before using its labels.
Record identity/version, allowed use, field/slice coverage, errors and uncertainty;
hide candidate answers and expected labels during independent judgment. An ensemble
that shares unverified labels does not solve the reference problem.

Source research did not establish an open, directly applicable patient-level CPAP gold
set. [MedNLI](https://physionet.org/content/mednli/view-license/1.0.0/) is credentialed;
do not download it or export it to a Free provider without the required rights and
data-use controls. [NLI4CT](https://github.com/ai-systems/nli4ct) concerns clinical-trial
entailment; its subject matter is not evidence of CPAP patient/payer applicability.
The current Synthea records and old AI-provisional labels remain development evidence.

### Study design and reporting

Freeze the independent reference method, applicability, group/split map, input bytes,
candidate/prompt/schema/lock/environment, metrics, risk limits and stop rules before
unexposed evaluation. Keep edits of one source/study family together. Once an output
is inspected, that family is development data for subsequent candidate changes.

Report at least unsupported-met rate, missed-conflict rate, missing-information
recall, supported-criterion recall, exact/support-valid span rate and disposition
agreement separately. Split by the eight required slices: supported criteria,
missing evidence, contradictory evidence, policy boundaries, negation, source-family
shift, prompt injection and document resume. Include unrelated requests, wrong
subject/payer/plan, document format/adapter, unavailable evidence and stale versions
as intake/operational strata. Distinguish correct abstention from useful completion;
an always-review baseline can contain risk while completing no supported cases.

Denominators include scheduled trials, failures, timeouts and missing observations.
Report repetitions and independent families separately. Show one-sided confidence
bounds with the chosen unit; do not count seven correlated criteria or repeated
calls as seven new patients. For illustration, a 1% error bound at95%confidence with
zero errors needs299independent groups for one endpoint. This is arithmetic, not
an accepted clinical target, multiplicity plan or proof of representativeness.
Clinical/risk acceptance limits and adjudication for unresolved cases remain pending.

Also retain p50/p95 per-stage and end-to-end time, queue/wait time, failure types,
known/unknown token usage and actual cost evidence. A Free project assertion permits
no paid fallback; it does not manufacture missing provider usage into zero tokens.
Keep local content-free profiling. No live Langfuse export is introduced here.

## Fresh model development packet

`prior_auth_study_draft.py` prepares a private exclusive directory. The actual
candidate's request builder is executed through a capture-only gateway, one criterion
at a time, so prompts/schema/full notes/request hashes can be reviewed without any
SDK transport, credential loader or ledger mutation. Inputs and proposed references
are separate files. The manifest pins artifacts, selected code, lock and environment.
This is a request-preparation witness, not a completed provider result or full live
runner qualification. A scoped live runner still needs readiness tests and accepted
limits before dispatch.

The concrete proposal uses12new authored development cases, two trials, at most
seven criterion calls per trial and two passing canaries: **170maximum attempts**.
Retrieval-absent criteria create no request. All12cases are constructed; they are
not a qualification holdout or12independent patient families. The current proposed
reference for national short-study interpretation stays unresolved.

The shared ledger read-only snapshot was447consumed,0unsettled, lifetime ceiling614,
with the prior routing stop present. Existing bound slots cannot fund this new scope.
The owner subsequently approved the concrete v2 constructed-development method/export/
limits,170newattempts, lifetime ceiling784 and confirmed the project remains Free.
That approval supplies no clinical qualification or release decision. The new scoped
runner must pass readiness checks before dispatch. Preserve every old history row,
stop and slot; do not continue the old stopped study or transfer its unused allowance.

Proposed limits: Gemini3.5Flash-Lite, temperature0, output512tokens/request, no tools,
90sHTTP/110sparent,18,000srun,2,000,000total tokens, one request at a time,7daysfrom
approval, both canaries pass before domain calls. Count failures and never retry a
consumed request automatically. No paid fallback, old-slot reuse or release grant.

`prior_auth_study_budget.py` adds append-only PA scope/reservation/settlement/stop
tables in the same existing SQLite file. It leaves historical tables and their SQL
triggers unchanged and checks their full logical snapshot before every reservation
and settlement. The old frozen reader still reports its own447/614scope; use the new
PA summary for the cumulative total and784ceiling. This is one budget file, not a new
parallel allowance. Any historical mutation blocks the PA run. A missing settlement
blocks further reservations; no implicit resume or outstanding-attempt retry exists.

The runner uses the exact owner-approved v2 packet pin and same Windows/Python
environment, freezes all executable source/lock bytes, and verifies the existing
credential association privately. Two canaries reuse already approved representative
request bytes; then166domain requests run in fixed order. The two retrieval-absent
slots cannot be converted to another case. The170allowance is an upper bound, not a
target to exhaust. Only one attempt may be outstanding. It reserves the existing
full input/output token ceiling against the2million remaining token allowance before
dispatch and releases that pending ceiling only to known observed usage after
settlement. Unknown usage stops the run. Raw provider cost stays unknown when absent;
the owner's Free attestation is not provider billing evidence. Each request uses an
owned/reaped child with90sHTTP/110sparent limits and no SDK retry or fallback. The run
expires conservatively at2026-11-20T00:00Z, within seven days of approval.

Reproduce preparation from an installed editable checkout, with a new directory:

```powershell
uv run --locked --all-packages --link-mode copy python prior_auth_study_draft.py `
  --directory D:/private/prior-auth/new-study-draft `
  --policy-directory D:/private/prior-auth/pinned-source-v1
```

The policy directory must contain the previously pinned CMS HTML, SourcePin, selected
prose and compilation. Missing/different bytes are refused. Omitting it prepares only
an explicitly marked invented policy shape fixture. Neither mode can dispatch models.

## External payer demonstration

Use the official [HL7-DaVinci/br-payer reference implementation](https://github.com/HL7-DaVinci/br-payer/tree/10d40911cb90d6198aacec144b4bfc48466af2fb),
pinned at10d40911cb90d6198aacec144b4bfc48466af2fb, Apache2.0. The published
[PAS2.2.1 submit operation](https://hl7.org/fhir/us/davinci-pas/2.2.1/en/OperationDefinition-Claim-submit.html)
is the protocol reference. An independent Java process supplies external behavior;
this is not the old in-process scenario switch or a commercial insurer connection.

`prior_auth_pas.py` implements a separate invented-only opt-in adapter. The trusted
application reviewer must supply canonical current case/version/note/policy pins.
The adapter checks write authority, tenant and invented/demo scope before reserving
or sending anything. It is not exposed as a model tool or public upload endpoint.
The reference service's default unauthenticated API is bound to literal loopback;
authenticated application authority is checked at our adapter boundary. This does
not qualify public-host authentication, SMART/OAuth or a commercial payer account.

The request has five synthetic FHIR resources, an invented service code and a note
hash. It exports no clinical note body or licensed service-code catalog. The RI's
unknown-service default should produce A3(not required). Record this action code
without converting it, `outcome=complete`, or any HTTP200 into our own approval.

The RI assigns a new Claim id and random response Bundle identifier. Correlate with
a separate bounded GET of that Claim and our stable Claim identifier, then match
the response Patient/insurer/requestor identifiers. Inquiry returns a Parameters
wrapper with0..*responseBundle values; require exactly one match and independently
read the referenced identity resources when its Bundle omits them. A foreign/absolute
reference remains refused; only closed Patient/Organization/Claim ids at the same
literal loopback base may be read. Reject arbitrary/absolute URLs,
unexpected service items, ambiguous/missing review codes and duplicate JSON keys.
Transport uses a literal loopback address, closed operations, no environment proxy,
no redirect following,2MBbody limits and bounded socket/read operations.

SQLite reserves a tenant/request identity before the POST. Replays return its receipt;
a changed payload under that identity is rejected. A lost response becomes unknown;
a crash after reservation leaves reserved. Neither path automatically repeats a POST.
Reconciliation requires an explicit inquiry/operator path; no claim of exactly-once
remote processing follows from a local journal. Filesystem permissions on the private
journal remain the deployment operator's responsibility.

The path-filtered `Prior Auth reference payer` workflow builds the exact upstream
revision, starts only its own loopback process, checks readiness, submits once,
verifies independent correlation, durable replay and a real inquiry, then terminates
that process. The script refuses an occupied port; it never stops an unrelated
service. Server/build logs and upstream sample bodies are not public artifacts.
The workflow is separate from Foundation CI; verify both for the exact PR head.

Full PAS profile/terminology/X12 conformance, real plan rules, attachments, SMART/OAuth,
commercial payer credentials, clinical adjudication and production endpoint/security
qualification remain external-integration acceptance work. A3demo transport success
does not close those requirements or release issue51.
