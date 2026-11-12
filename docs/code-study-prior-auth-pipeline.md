# Prior Auth document pipeline: code walkthrough

Inspected2026-11-12 on `codex/prior-auth-document-pipeline`, based on main2cf9d69.
This chapter covers the opt-in root adapters and new tests, not a fresh clinical study.
See [implementation/runbook](prior-auth-document-pipeline.md) and Build Book Entry102.

## Follow one invented request

`prior_auth_demo.demo_request` builds a case for `demo-clinic`, a document from
`demo-sleep-lab` and the exact `demo-payer`/`demo-plan` registry entry. These are referral
partners, so provider IDs differ while the subject hash agrees. `demo_policy` is an
explicit invented mechanism fixture under the legacy policy contract, not downloaded
CMS text and not a qualified clinical source.

`prepare` revalidates the request, checks raw-byte SHA, calls `normalize`, compares its
normalized-text pin, calls `decide`, applies the reviewed redaction spans and creates a
legacy `NoteInput` only after admission. A missing PDF extraction review is unreadable
for admission purposes. Parser failure yields no note, rather than empty evidence that
could be confused with an otherwise valid case.

`normalize` preserves an exact text hash and half-open Unicode regions. Text-PDF and
OCR use different coordinate systems, explicitly documented in the runbook. Generic
XML DTD/entity declarations are refused before parser entry. Only Poppler's exact fixed
inert XHTML declaration is removed from trusted tool output; no DTD or URL is loaded.
`NativeTools.run` uses an argument array and bounded temporary output, records fixed
stage labels, kills/reaps failures and never prints parser/body output.

`decide` is deliberately a deterministic gate over trusted source assertions. It does
not claim to infer patient ownership or clinical relevance from prose. Exact payer,
plan, service, date and policy pins prevent a model from selecting a convenient policy.
Uncertain assertions yield review. Supporting another service requires policy work,
not another keyword in this gate.

## Why the transaction override exists

`IntakeStore.accept` takes the case-scoped reviewer principal. Under a transaction and
case advisory lock, it checks replay receipts and stored case identity. `JoinedReviewStore`
overrides only `transaction` to yield that same connection. Thus the old `enroll` or
`deliver` mutation, assessment job, new receipt and source-region row commit together.
Calling an ordinary independent `ReviewStore` here would risk committing a case without
its receipt when the process fails between the two commits.

An accepted supplement still needs the old unexpired wait/version guard. After the
legacy append, the importer derives the document's combined-note offset from the saved
text and verifies its suffix. Rejected evidence writes a fixed receipt only; it never
reaches legacy mutation. The SQL failure test revokes receipt INSERT and proves there
is no orphan case or job after rollback. Duplicate delivery tests use concurrent imports
and reconstruct the store to exercise actual durable replay.

## Assessment, profiling and metrics

`ProfiledAssessor` delegates to the old extractor through an injected `TimedGateway`;
it selects no credentials or budget. `checked` delegates to the existing quote/support
checker. `ProfiledReviewStore` can replace the old store in `ReviewWorkflow` to measure
claim, expiry, aggregate persistence and publication without editing frozen runtime bytes.
Profiler rows contain only stage/time/failure; usage contains numeric accounting. Inclusive
overlap is not elapsed time. Unknown usage, queue delay, lock wait and human work remain
unknown. A fast mock is not provider latency evidence.

`score` validates every result's case/note/policy pins and seven-criterion inventory.
Only scheduled unique trial rows count. Source, parent and template groups cannot cross
project splits. Missing trials remain in route/intake denominators; nullable criterion
references are excluded from agreement and explicitly counted as missing. Both incorrect
evidence-complete risk denominators are reported, including an all-recommendation lower
bound and unknown-reference count. No routine can return qualification=true.

`prior_auth_diagnostics.run` produces actual rules/always-review outputs for26invented
cases; it does not fill the missing model comparator with fixture predictions. These
family pairs are development examples and cannot supply a confidence interval for a
production claim. `SyntheticPayer.submit` separately checks trusted role, invented
identities, current version and note/policy pins, then persists an idempotent scenario
response. A simulated approval never changes the legacy evidence checker into an insurer.

## Tests and engineering questions

Read `tests/test_prior_auth_pipeline.py`, `tests/test_prior_auth_sandbox.py`, the new
SQL tests and the required native canary. Focus on wrong patient/tenant, malformed
documents, DTDs, URL attachments, injection, expired/overlapping policies, redaction
pinning, missing result/accounting slots, concurrent replay and transaction rollback.
The native canary creates a real image-only PDF and refuses to call a text-layer read
an OCR test. Hosted CI requires actual tools; a protocol mock cannot replace that proof.

Explain these tradeoffs in an interview: Why can a readable report be inadmissible?
Why does exact quotation fail to prove medical meaning? Why is an import receipt in a
separate transaction dangerous? Why are source-family repetitions not independent cases?
Why must native parser limits still be paired with OS isolation? Why does a local payer
scenario prove replay and correlation but not interoperability or clinical acceptance?
