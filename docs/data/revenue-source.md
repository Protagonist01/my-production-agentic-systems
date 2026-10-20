# Original-contract source preparation

R1 #39 preparation, 2026-10-20. This imports original CUAD text and publisher-authored extractive references. It does not run an extractor, generate billing truth, or call a provider. See the [source pin](revenue-source-pin-v1.json), [aggregate preparation report](revenue-source-cuad-v1.json) and [code walkthrough](../code-study-revenue-source.md).

## Provenance and use

The Atticus Project's [CUAD landing page](https://www.atticusprojectai.org/cuad/) describes 510 commercial contracts annotated under experienced-lawyer supervision for 41 clause categories. Its [legal page](https://www.atticusprojectai.org/legal/) identifies CUAD as CC BY 4.0; retain attribution, link the license, and identify transformations when using a derived corpus. The [CC BY 4.0 license](https://creativecommons.org/licenses/by/4.0/) supplies its actual conditions. The publisher's [disclaimer](https://www.atticusprojectai.org/disclaimer/) gives no accuracy or currency warranty and does not supply legal advice.

Attribution: The Atticus Project; Dan Hendrycks, Collin Burns, Anya Chen and Spencer Ball, *CUAD: An Expert-Annotated NLP Dataset for Legal Contract Review*, NeurIPS 2021. The [official repository](https://github.com/The-Atticus-Project/cuad/tree/67faa0e6023b04fcaae6cc09497ab00e5d63a2a2) is pinned to `67faa0e6023b04fcaae6cc09497ab00e5d63a2a2`. The downloaded `data.zip` contains the complete `CUADv1.json` and the publisher's train/test files. Only the complete member is imported; PDFs and additional EDGAR agreements are not needed for this extraction-preparation scope. The preserved text is the published text context, not a newly verified PDF rendering or page-level citation corpus.

The archive byte pin is `f8161d18bea4e9c05e78fa6dda61c19c846fb8087ea969c172753bc2f45b999a` (18,309,308 bytes). The complete member pin is `ed0b77d85bdf4014d7495800e8e4a70565b48ee6f8a2e5dca9cf8655dbf10eae` (40,128,638 bytes). These establish byte identity against trusted metadata. A hash does not authenticate who wrote a label, grant permission, or validate the legal interpretation. The source selection, license attribution and reviewed pin are trusted application inputs.

## Storage and reproducible commands

Keep downloaded archives, both SQLite files and full private manifests outside every Git checkout. No contract title, original question identifier, source text or answer span is committed. Tracked reports contain source-level hashes, category names, counts and limitations only. Use a new output directory for each preparation; an existing directory is never overwritten. A failed build has no final manifest and must be inspected before the owner removes or replaces it.

From the repository root in PowerShell:

```powershell
$sourceCache = 'D:/document/.cache/production-agents/revenue/cuad-v1'
$prepared = 'D:/document/.cache/production-agents/revenue/cuad-original-r1-v1'
```

Download the [pinned official archive](https://raw.githubusercontent.com/The-Atticus-Project/cuad/67faa0e6023b04fcaae6cc09497ab00e5d63a2a2/data.zip) into `$sourceCache/data.zip` using a normal download client. Preparation is entirely offline and rejects differing bytes. Use the reviewed source-manifest byte pin; do not calculate a new pin from an unreviewed substitute and treat that as approval.

```powershell
uv run --locked --all-packages --link-mode copy python -m revenue_integrity.source_cli prepare `
  --archive "$sourceCache/data.zip" `
  --source-manifest docs/data/revenue-source-pin-v1.json `
  --source-manifest-sha256 0ea4844e5b8885b14992ffedb2af74d3bd110586c42acb027c2d77eaaced02df `
  --output $prepared
```

Preparation validates the pinned archive and member from the same in-memory bytes, never extracts archive paths, rejects duplicate or unsafe members, and checks every source question and span before creating stores. Original contexts are stored once in `inputs.sqlite.contracts`; `questions` stores opaque case keys, opaque contract keys and the published questions. Joining these produces `ExtractionInput(case_id, context, question)` only. Do not pass a database path to the candidate.

`evaluator.sqlite` holds published answer spans, answerability, category, inferred family, split, original title and original question ID. A trusted evaluator selects cases and passes individual input projections to the extractor. Targets and metadata stay in the evaluator process. This is an application boundary; OS credentials and process isolation remain the caller's responsibility. Original context can itself mention a contract's title or commercial terms because that text is the extraction task.

Retain and independently review the generated `manifest.json` pin before verification. The verification command needs that reviewed value:

```powershell
uv run --locked --all-packages --link-mode copy python -m revenue_integrity.source_cli verify `
  --archive "$sourceCache/data.zip" `
  --output $prepared `
  --manifest-sha256 <reviewed-prepared-manifest-sha256>
```

The verifier reopens both stores read-only, checks their byte hashes and SQLite integrity, checks the agent table/column allowlist and population, recomputes source references and inferred groups, and compares every input, span, source mapping and aggregate count against the original pinned member. A changed target cannot be legitimized simply by updating the database hash in a manifest. Source/member and prepared-manifest pins are separate decisions.

The completed local source drill used prepared-manifest pin `b852424ab854c30bd730ccc90a799907e02d3875a3066d203aed36f842f78540` and returned `verified: true` for 510 contracts, 20,910 questions, 13,823 spans and 457 inferred families. Database hashes identify this prepared snapshot; another SQLite build may require its own reviewed prepared manifest even with identical logical records.

## Family policy and limits

`cuad-issuer-template-v1` was fixed before any candidate evaluation:

1. Parse issuer prefixes using the observed underscore filename boundary or `issuer - contract` title boundary. Normalize Unicode/case and remove issuer punctuation. One title has neither boundary; its issuer is explicitly unknown, rather than guessed.
2. Union documents with an equal recognized issuer or an exactly equal Unicode/case/whitespace-normalized context.
3. Normalize context numbers to `#`, retain ASCII word tokens and numeric markers, and build the set of every five-token shingle. Union a pair when each has at least 100 distinct shingles and intersection/union is at least 65%. This is set Jaccard similarity, not edit distance or embedding similarity. The size-ratio prune cannot exclude a pair that could meet the threshold.
4. Take the transitive closure. A family key hashes the policy plus sorted original titles. Assign the whole family to holdout when the first 32 hash bits modulo five equal zero; otherwise assign development. Answers never choose the split. Regrouping or changing this policy requires a new version and a new reviewed manifest.

The complete source gives **457 inferred families**, 35 with multiple contracts, largest family five. Relations comprise 51 issuer edges, one exact-context edge and five template edges; edges overlap and do not sum directly to the number of merged documents. The split contains **417 development contracts / 93 held-out contracts**. The publisher's contract-level split is preserved in the archive but is replaced for this local family experiment, so results would not be directly comparable to the published benchmark.

No detected family crosses these boundaries. This does **not** prove all legal or semantic template families were found. Issuer names can change; subsidiaries, substantial rewrites, short templates, non-ASCII matching, or less than 65% overlap can hide relations. An issuer can also have unrelated agreements, so grouping may be overly conservative. The unknown issuer needs review before any stronger independence claim. A fresh model may already have seen public CUAD during pretraining; this local split cannot establish training-data novelty.

## What the labels cover

The complete member contains **20,910 questions and 13,823 published answer spans** over 510 contexts. Every answer's Python character offset and literal text matches its original context, with zero repairs. The original `is_impossible` flag is retained and must agree with the presence or absence of spans. An unanswerable clause question means no annotated answer for that question; it does not prove a billing obligation is absent.

Source spans include legal dates, renewal terms, price restrictions and revenue/profit-sharing clauses. They are useful for source-text extraction and citation checks. They do not supply independently normalized subscription quantities, per-seat prices, currency schedules, annual uplifts, account-linked invoices or amendment precedence suitable for billing reconciliation. No invented value fills such a gap. Normalized numeric billing gold, new domain review, extractor scoring and the R2 generated billing world remain pending and must be reported separately from original-contract extraction.

The [aggregate report](revenue-source-cuad-v1.json) records each category's question, answerable-question and answer-span counts. Presence of a category is not proof that it covers a needed billing field or that the source label is error-free. The publisher-authored references are independent of candidate output; no new human billing review is claimed.

Focused offline tests use invented contexts and cover source pins, literal offsets including Unicode, invalid labels, malformed archive members, exclusive output, transitive grouping, unknown issuers, target isolation, manifest/store tampering and recomputed coverage. No live Langfuse dataset or provider was written. The [Langfuse dataset guidance](https://langfuse.com/academy/datasets) informs the input/reference/metadata separation only.
