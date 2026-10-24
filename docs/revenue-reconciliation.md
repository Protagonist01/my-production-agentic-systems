# Offline Revenue extraction and reconciliation

R4 implements an original-clause extraction boundary and separate constructed SIM billing arithmetic. It does not create invoices, change subscriptions, initiate payment, recover money or establish legal interpretation quality. R2 supplies fictional billing worlds with provisional AI-authored literal expectations; those expectations are never an extractor input.

The user approved the constructed policy `revenue-monthly-whole-seat-sim-v1`: monthly whole seats, prices and amounts in integer SIM hundredths, no proration or tax, explicit dated ramps/credits/amendments, and annual uplift only when expressly supplied. Missing or conflicting facts require review. CUAD spans do not supply missing commercial facts.

## Original text extraction

`ExtractionInput` contains the original context, question and opaque case ID. `GatewayExtractor` accepts a caller-composed harness `ModelGateway`, a trusted route, a matching `RunContext` and that public input. It replaces route messages with a fixed instruction and JSON context/question, declares a strict answer schema, removes tools and bounds output to at most 2,048 tokens. It never constructs transport, discovers credentials or retries a provider. The caller must supply the existing bounded gateway for deadline/cost reservation enforcement.

Input context is limited to 200,000 Python characters and the question to 8,192. The response is limited to 65,536 characters, sixteen spans and a 2,000-character rationale. Case identity comes from the server input. Before interpreting content, the adapter revalidates the response contract and requires the requested provider/model plus any explicitly pinned model revision. Wrong-route responses return uncertainty even when their quote is valid. Invalid shape, contradictory answerability, mismatched spans, tool calls or typed provider failure produce an uncertain result requiring review. Oversized inputs return uncertainty before dispatch; a mismatched run case raises a bounded caller error.

The citation verifier checks exact Unicode character offsets into the unchanged context, rejects duplicate/overlapping spans and records the source SHA256. Its output explicitly says `meaning_status: not-validated`: a quotation can be exact and still fail to answer the question or support an amount. `unsupported` and `uncertain` contain no spans. Neither candidate nor verifier reads the published target store.

The supplied command-line original baseline always abstains with `unsupported`; it makes zero provider calls. Scripted gateway tests establish interface behavior only. No original CUAD extraction quality, normalized billing quality or fresh-provider result is measured here.

## Constructed billing arithmetic

The billing input declares a complete first-of-month to next-first-of-month half-open period. Subscription end is exclusive. Before subscription start or on/after end the gross charge is zero, provided the remaining facts are well formed. A partial subscription month or a dated midmonth amendment/credit requires review; there is no day-count convention or silent proration.

The engine validates original terms, sorts explicit amendments by date/sequence, rejects duplicate or date-conflicting sequences and rejects contradictory same-date field values. Different same-date fields can be combined. A dated seat amendment changes the whole-seat quantity. An explicit price amendment resets the current price; subsequent expressly scheduled uplift anniversaries compound from that price. Future amendments do not change the current month, although malformed/conflicting declared amendments are conservatively rejected even when future-dated.

The uplift anchor is the **first applicable uplift date**, followed by the same calendar month annually. It must be a first-of-month date after subscription start. Uplift without an anchor, or an anchor without an explicit basis-point rate, requires review. For example, 10,000 minor units at 1,000 bps becomes 11,000 on the first anchor and 12,100 on the second. The engine divides only when the numerator is exactly divisible by 10,000; it never invents rounding. A price amendment on an applicable anniversary requires review because event precedence is unknown.

Credits apply to exactly their declared calendar month. Credits larger than that month's gross charge require review instead of creating a negative invoice. The final amount must fit a signed 64-bit nonnegative integer. The unsupported December 9999 boundary is rejected before computing a nonexistent next year.

`delta_minor = should_be_minor - issued_minor`: positive means underbilled, negative means overbilled and zero means correct. A review result carries no expected amount or delta. All outputs use SIM; they are not claimed financial loss or recovered revenue.

## Keep the two arithmetic paths separate

The provided-terms path runs `reconcile(BillingInput)` against explicitly supplied normalized facts. In an evaluation, its expected answer must come from independently authored literal targets; the production reconciler must never generate those targets.

The extracted-terms mechanism uses **only invented documents** in `synthetic-billing-grammar-v1`: exactly one `field=JSON-value` line for every `SubscriptionTerms` field except the wire schema version. Dates are ISO strings, absent values are explicit JSON `null`, conflicts are an explicit array, and unknown/duplicate/missing fields fail. `synthetic_document` is an invented-input renderer, not a CUAD converter. `parse_synthetic` attaches exact line citations and a source digest. `reconcile_extracted` reparses the original document, compares the complete supplied parse/citations and substitutes those terms into the billing input before arithmetic. A forged parse or another case's document is rejected.

This deterministic grammar is deliberately narrow. Passing it proves parser/arithmetic wiring; it does not measure a general contract model. The original extractor's `VerifiedExtraction` cannot be passed as `ParsedTerms`, and no path turns a verified legal quotation into a SIM price.

## Private local commands

Run from a prepared checkout after the normal locked workspace setup. All input and result paths must resolve outside any Git checkout. Parent output directories must exist; results are created exclusively and never overwrite another run. Inputs are bounded to two million bytes. Successful stdout contains only `written` and command mode; full results stay in the private output file. Invalid input, database access or output errors produce a generic message without printing the source or Pydantic payload. Treat the private files as sensitive local artifacts.

```powershell
uv run --locked --all-packages python -m revenue_integrity.reconcile_cli reconcile --input D:/private/billing-input.json --output D:/private/provided-result.json
uv run --locked --all-packages python -m revenue_integrity.reconcile_cli reconcile --input D:/private/billing-input.json --synthetic-document D:/private/invented-document.json --output D:/private/extracted-result.json
uv run --locked --all-packages python -m revenue_integrity.reconcile_cli extract-original --input D:/private/original-input.json --output D:/private/abstention-result.json
uv run --locked --all-packages python -m revenue_integrity.reconcile_cli reconcile-world --database D:/private/worlds/inputs.sqlite --case-id invented-case --grant D:/private/grant.json --output D:/private/scoped-result.json
```

`reconcile-world` checks both `reconcile` and `read` capabilities before reading the database and requires an exact allowed world plus the stored tenant identity. Its optional `--synthetic-document` selects the separate extracted-terms path. A trusted administrator creates the grant file; accepting a local grant file is not user authentication. Do not expose this CLI as an HTTP service or treat filesystem-separated stores as an OS sandbox. The plain `reconcile --input` command is trusted offline arithmetic with no authorization claim.

## Verified scope and remaining acceptance

The final focused R4 command `uv run --locked --all-packages python -m pytest -q tests/test_revenue_reconcile.py tests/test_revenue_extraction.py` passed **41 tests in 0.84 seconds** on Python 3.13.4 with external `TEMP`/`TMP`, at source commit `45ebabb85a8cdbb3142ff32421767d7cff7221c3`. Three new Python modules passed strict mypy with explicit workspace source `MYPYPATH`, and all five owned Python files passed Ruff check/format. A first narrow mypy invocation without the source path failed on untyped installed imports; correcting that invocation passed without changing source. Root combined checks remain separate final integration evidence. Tests cover independent arithmetic expectations, review boundaries, one-year/two-year uplift, dated changes, exact citations, malformed/forged gateway responses, wrong provider/model/revision and invalid unchecked usage, typed failure, scoped capability denial, separate extracted terms, CLI errors and a private-data canary. Another worker compared all 29 R2 literal fixture amounts/dispositions to the reconciler with no mismatches; this is provisional fixture agreement, not a business-quality benchmark.

Fresh original-contract provider evaluation, reviewed normalized commercial labels, real account linkage, invoice approval/write workflows and production authentication/deployment remain pending. The [source study](code-study-revenue-engine.md) traces the implemented functions and representative errors; the [original-source study](code-study-revenue-source.md) explains the separate CUAD preparation boundary.


The integrated private [mechanism capture](data/revenue-reconciliation-mechanism-v1.json) ran the pinned 29-case cohort through both provided-terms and invented grammar paths: 29/29 amount/disposition matches in each, two scoped CLI output paths verified, and private world-store bytes unchanged. Twelve original CUAD development inputs exercised the concrete extractor with a scripted abstention gateway: twelve unsupported responses, zero provider calls. This verifies plumbing and isolation, with original extraction accuracy unmeasured. Full source hashes and the clean executing revision are retained in the aggregate; complete per-case results stay outside Git.


## Stronger evaluation requirements — 2026-10-24

[Shared standards](evaluation-standards.md) and the [five-agent readiness inventory](evaluation/readiness.json) apply to the next release study. R7 must separate original extraction/span/meaning quality from constructed billing reconciliation and approved effects. Qualified labels and family-held-out extraction remain required. Existing sealed pilots are unchanged. Missing reviews, approved pre-output thresholds, grouped unseen inputs, complete field scores/accounting or H10 evidence block release. No additional provider run or release approval is inferred.
