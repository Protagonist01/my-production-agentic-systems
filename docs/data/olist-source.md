# Olist source acquisition and handling

Verified 2026-10-12 for O1 #26. [Source publisher data card](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) · [Pinned aggregate manifest](olist-v7-manifest.json) · [Official acquisition library](https://github.com/Kaggle/kagglehub).

## Exact source

Publisher: Olist. Dataset: Brazilian E-Commerce Public Dataset by Olist. Download handle: `olistbr/brazilian-ecommerce/versions/7`; download library: `kagglehub==1.0.2`. Source metadata lists version 7's creation as 2018-11-29. The legacy metadata endpoint also reports a current version 2 dated 2021-10-01 and duplicate version-2 history entries; this work does not claim v7 is latest. Explicit versioned download succeeded through the publisher's platform; checksum comparison identifies the inspected bytes.

The source has anonymized historical commerce records. Source-supplied category translations are separate from original Portuguese fields; review text is not automatically translated. No source rows, IDs, review quotes or geolocation examples are committed. The manifest contains only filenames, hashes, schema, aggregate counts and timestamp bounds.

## Reproduce acquisition and verify

With uv installed, from the repository root:

```powershell
uv run --script projects/olist-support/scripts/snapshot.py acquire --manifest docs/data/olist-v7-manifest.json
```

The script pins the library separately from application dependencies. It downloads the explicit source version to Kagglehub's cache outside the repository, then verifies all nine files against the checked-in manifest. If access requires authentication or a consent step on another machine, complete the normal Kaggle access flow; do not put tokens in chat or Git. No login was needed for the verified acquisition here.

For an existing externally stored snapshot, local verification needs only Python 3.12+ and performs no network calls:

```powershell
python projects/olist-support/scripts/snapshot.py verify --source "C:\Users\wolas\.cache\kagglehub\datasets\olistbr\brazilian-ecommerce\versions\7" --manifest docs/data/olist-v7-manifest.json
```

Replace the example source path with the path printed on your machine. `KAGGLEHUB_CACHE` can point to a preferred external cache as documented by Kagglehub. `profile --source <external-directory> --manifest <new-manifest-path>` creates a new report without overwriting an existing one. Compare/report any difference; do not silently replace the baseline to make verification pass.

The checker rejects missing or unexpected CSVs, header changes, malformed record widths, invalid purchase timestamps, changed hashes/counts/missingness and a manifest for another dataset version. It preserves bytes and source spelling, including `product_name_lenght`/`product_description_lenght`. This checks source integrity; it does not yet check joins, business rules or historical visibility.

## Observed contents

| File | Parsed records |
|---|---:|
| Customers | 99,441 |
| Geolocation | 1,000,163 |
| Order items | 112,650 |
| Payments | 103,886 |
| Reviews | 100,000 |
| Orders | 99,441 |
| Products | 32,951 |
| Sellers | 3,095 |
| Category translation | 71 |

Total: 1,551,698 table records, not distinct orders. Purchase timestamps span 2016-09-04 21:15:19 through 2018-10-17 17:30:18. Orders contain 160 empty approvals, 1,783 empty carrier handoffs and 2,965 empty customer delivery dates. Every column's missing count is in the manifest. Do not equate missing delivery with a known outcome. Reviews/items/payments may have different grains; O2 must validate cardinality before joining.

## Use conditions and export boundary

The publisher lists [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/). Keep source attribution and license reference with derived data; identify modifications. This project acquires the source for local noncommercial portfolio development. Commercial reuse needs a suitable source or permission. If adapted source data is shared, preserve the license's attribution, noncommercial and ShareAlike conditions. This source license does not automatically establish a license for our independent code.

Keep raw archives/CSVs and any derived source-row tables outside Git. Keep raw reviews, identifiers and precise geolocation out of model-provider calls and telemetry until the scoped data/redaction policy is implemented. Share aggregate schema/count/checksum reports and invented fixtures in the public repository. Any future demo that exports source content needs a separate handling review with attribution and modification labels.

Currency unit and timestamp timezone are **not explicitly declared in the inspected metadata/schema**. They are recorded as null/unverified. Brazil alone does not prove a specific currency unit or timezone. O2 must document units and timestamp treatment before calculations/as-of views; this acquisition script never performs refunds or normalizes time.

## Credential-free test strategy and limits

The offline integrity tests create hand-invented CSVs in temporary directories using the required schemas; they copy no real Olist records. They check detection of altered bytes, wrong versions, missing files, malformed schemas/records and in-repository raw storage. CI integration remains F5. Such synthetic plumbing tests are not model evaluation or evidence of correctness on Olist workflows.

Source data has no support request, refund/reship policy, approval record or ground-truth support action. These remain constructed and separately labeled under O3. Holdouts, business-event keys, scoped/as-of reads and independent action scoring remain O2/O3/O4 and the harness tasks.
