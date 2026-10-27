# Unique whitespace alignment with exact original evidence

2026-10-27, `codex/citation-alignment` against merged base3d72610. This is a separate offline
parser improvement following the unsuccessful [semantic pilot](semantic-answerability-pilot.md).
Legacy `parse_judgment`, its provider prompt, original captures, labels, report and failures
are unchanged. No provider calls or permission to spend remaining attempts are part of this work.

## Trace the algorithm

[`align_quote`](../harness/src/agent_harness/citation_alignment.py) accepts source text and a
quotation. It first enforces200,000source/10,000quote code-point bounds. `_mapped` replaces
each run of Python Unicode `str.isspace()` characters with one ASCII space, strips edge
whitespace, and retains original start/end positions for every normalized character.
All other characters remain exactly unchanged: no case folding, NFKC, punctuation repair,
OCR correction, tokenization or fuzzy matching. Versioned normalization names that behavior.

Find the normalized quotation in the normalized source. Zero matches refuse. A second match,
including an overlapping one or another exact occurrence, refuses as ambiguous. An exact
match at one position does not override another whitespace-equivalent occurrence. This is
stricter than the old parser for repeated/overlapping quotations; v2is explicitly opt-in.
The first/last matched normalized characters map to one continuous original source span.
Return the original substring, Unicode code-point offsets and SHA256of exact UTF-8source,
plus the original quotation's hash and exact/whitespace-only method. `EvidenceSpan.verify`
checks the reconstructed substring against the original source. `verify_alignment` reruns
the deterministic mapping and refuses modified source, quote, offsets, hashes or method.

For invented source `Payment\t is\r\ndue.` and quote `Payment is due.`, the result contains
the exact original tabs/CRLF, not a cleaned replacement. A changed negation, decimal separator,
Unicode compatibility character or zero-width character refuses. Whitespace within a word
cannot be inserted/deleted unless the source already has equivalent whitespace there.
There is no token-boundary or semantic claim; even a literal substring can be misleading.

## Separate Revenue parser v2

[`parse_aligned_judgment`](../projects/revenue-integrity/src/revenue_integrity/semantic_alignment.py)
accepts only `ExtractionInput` and a recorded `ModelResponse`; it reads no publisher labels.
It revalidates contracts, route, output shape, duplicate JSON keys and existing decision/quote
consistency. Align every quote uniquely and reject duplicated/overlapping mapped source
spans. Preserve model decision/raw quotes separately from original source evidence. Reject
and abstain return no quotations, as in v1. Failed provider responses or tool calls refuse.

The returned record binds original input/response pins, quotes and exact source spans.
`semantic_support` remains `not_assessed` and `release_allowed`false. A DTO/hash is not an
authenticated approval or sufficient evidence of meaning. Bare caller-authored records still
require reconstruction against trusted source/response bytes. This parser is not wired into
the old live capture, H10 release path or business tools and does not activate a model judge.

## Offline diagnostic protocol

Freeze new code before applying v2to the24saved responses. Hash-check the original plan,
schedule, dataset, protocol, study and report against PR115's safe aggregate. Recompute v1
decisions under unchanged legacy code and compare them to saved observations. Then run v2
as a separate diagnostic with network denied, preserving original response/source bytes.
Keep original and derived records in different exclusive directories.

Report mappings, refusals and differences without replacing original rows or computing a
fresh model-quality score. These are exposed cases that motivated the implementation;
reprocessing them cannot qualify the new parser or model on an independent holdout. No new
provider dispatch, token consumption, ledger update or price calculation occurs. Semantic
reference disagreements and small-sample uncertainty remain regardless of quotation handling.

## Verification and limits

Tests use invented text and cover CRLF/tabs/NBSP/Unicode whitespace, exact mapping and hashes,
edge whitespace, repeated/overlapping ambiguity, negation/digit/punctuation/case/Unicode
changes, size bounds, source/quote/offset/hash tampering, parser route/schema/citation
consistency and preserved v1failure. Oversized pytest parameters need explicit short test
IDs on Windows, otherwise the test runner's current-test environment value exceeds platform
limits before the code runs. No actual source material belongs in test parameters.

```powershell
python -m pytest -q tests/test_citation_alignment.py tests/test_semantic_alignment.py `
  tests/test_revenue_semantic_pilot.py tests/test_evaluator_qualification.py
```

Linear-size source/quote normalization precedes string search; explicit bounds limit in-memory
mapping. No adversarial resource-isolation or production performance guarantee is claimed.
Unicode whitespace normalization changes formatting only, but layout can matter to meaning;
semantic support must be established separately. Unique short substrings are allowed as
literal evidence without claiming they answer a question. A future release needs applicable
reference evidence, prospective frozen fresh studies and an accepted method policy. Existing
human/qualified review and other domain gates are not bypassed by this improvement.

[Build Book Entry63](../BUILD_BOOK.md#entry-63--map-whitespace-changes-back-to-exact-source-spans)
records construction and actual checks. Hosted acceptance is recorded on the PR after it
finishes, not inferred from focused tests. Shared Gemini stays24/180consumed,156remaining;
separate Groq9/12invented-only unchanged.

## Actual frozen offline diagnostic

Freeze executable `869f1c1d9b59bb788907ccc812b8e94a82ce7329` before readback. A network-denied
process verifies original plan/dataset/protocol/study/report pins and every old executing
source file against the sealed capture inventory. It first reproduces every saved v1decision,
then applies the separate v2parser to exactly the same24recorded responses. Original files
are hashed before/after; the authoritative shared ledger is read-only and compared unchanged.
New private plan, source inventory and derived rows use an exclusive directory.

The [safe aggregate](data/citation-alignment-diagnostic-v1.json) reports22legacy-valid and
24v2-valid responses. Both old invalid rows map uniquely; their three submitted quotations
produce whitespace-only mappings. Seven other quotations map exactly. No response gets a
different model decision and no additional conservative refusal occurs on this exposed
population. Every returned span is independently reconstructed against the exact original
source and raw quotation. Repeated/ambiguous/overlapping cases are covered by invented tests,
not newly observed live examples.

These are parser-diagnostic counts, not a new model-quality score. The original pilot stays
calibration6/8,validation13/16including2invalid outputs,qualificationfalse. No labels, original
failures, quotes or reports are overwritten. The Minimum Commitment/Expiration Date
reference disagreements and uncertainty remain unadjudicated. Shared Gemini consumption
stays24/180,156remaining,0unsettled; no provider call, token usage or cost is generated here.
Because the old outputs motivated development, this diagnostic is explicitly exposed and
cannot serve as prospective validation. There is no release or human-review substitution.

A [separate prospective cohort](prospective-semantic-cohort.md) now prepares future requests
with inspected prior families/contexts/inputs excluded. It has no provider results, and its
forecast explicitly distinguishes a diagnostic pilot from an affordable final qualification.
