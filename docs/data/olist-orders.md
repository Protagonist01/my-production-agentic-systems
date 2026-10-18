# Olist order grain and historical visibility — O2

O2 #27 follows verified O1 and shared contracts. This branch implements a local private SQLite importer and read-only order projections. It does not implement refunds, a support policy, runtime authentication or a model workflow. C1 #34 proceeds independently in the user-selected parallel batch. See [source acquisition](olist-source.md), [source study](../code-study-olist-orders.md) and [Build Book Entry 24](../../BUILD_BOOK.md#entry-24--parallel-source-preparation-and-honest-historical-order-views).

## Create and pin a private derived store

Install the locked workspace with `python dev.py setup`. The source directory must contain the exact nine O1 CSV files outside this checkout. The derived database also stays outside this checkout; use a restricted private parent directory. Obtain the manifest byte digest from the reviewed O1 checkout, not an unreviewed replacement manifest. For example:

```powershell
$sourcePin = (Get-FileHash docs/data/olist-v7-manifest.json -Algorithm SHA256).Hash.ToLower()
uv run --locked --all-packages --link-mode copy python -m olist_support.source_cli `
  --source "C:\Users\wolas\.cache\kagglehub\datasets\olistbr\brazilian-ecommerce\versions\7" `
  --source-manifest docs/data/olist-v7-manifest.json `
  --source-manifest-sha256 $sourcePin `
  --output "D:\document\.cache\production-agents\olist\new-orders.sqlite" `
  --repository-root . `
  --observed-at "2026-10-18 00:00:00" `
  --aggregate-report artifacts/new-olist-aggregate.json
```

Replace machine-specific paths and choose new output/report names. `--observed-at` is an **explicit conservative availability boundary expressed in the scenario's source-local clock**. The example's date is a declared scenario boundary after all actual source events; it is not a UTC conversion, a recovered historical ingestion timestamp or proof of when a customer-service system knew a value. The importer rejects a timezone-aware clock and an observation boundary before any recorded actual event. Future shipping/estimated-delivery dates are plans, so they do not establish when a snapshot was observed.

The CLI verifies the separately supplied manifest digest, Olist v7 identity, complete CSV inventory and each raw byte hash. It verifies exact column order/width, record counts and missingness while loading the eight needed tables. Geolocation is hash-checked but is not imported or exposed. It checks key uniqueness, child references, timestamps and nonnegative two-decimal amounts. It rechecks source hashes after import and creates metadata plus aggregates in one transaction and explicitly closes the connection before returning the final file digest. Existing output is refused; a failed import can leave a private partial file, which is never resumed. The CLI prints only aggregate counts and hashes and optionally writes an aggregate-only report. It never prints source rows, IDs or review text.

## Grains and arithmetic

| Table | Declared key | Handling |
|---|---|---|
| orders / customers / products / sellers | Their source ID | Unique, nonempty; orphan item/order/customer references fail |
| items | order_id + order_item_id | Every line retained; price and freight aggregated independently |
| payments | order_id + payment_sequential | Every payment retained; installments are not multiplied into payment_value |
| reviews | order_id + review_id | Review ID is not globally unique; distinct order reviews remain separate |
| translations | Portuguese product category | Source English category labels remain separate from original category |
| orders_360 | order_id | Exactly one row per source order; independent one-row-per-order child aggregates joined afterward |

An invented witness has two items, two payments and two reviews. A direct join yields eight rows and a fourfold item total. The implementation first reduces each child to one order row and reconciles global child counts/totals against source tables before accepting the store. It does not silently deduplicate or multiply payments by installments. A missing child population is zero rows with an unknown monetary total, not proof of a zero-valued transaction. A missing amount retains a known subtotal plus missing count and a null complete total.

Amounts are parsed through exact Decimal values and stored as integer hundredths of the **undeclared source unit**. Scale two is a numeric representation, not a claim that the unit is BRL or a particular legal currency. The pinned source manifest keeps currency unit and timestamp timezone unverified. No conversion, foreign exchange, refund valuation or timezone normalization is performed. Invalid/nonfinite/negative/overprecise/out-of-range amounts fail rather than being rounded.

## Read a scoped as-of view

Use `OrderStore(database, expected_sha256=<separately retained database digest>)`. It rejects journal/WAL/SHM sidecars, verifies the file digest, opens SQLite read-only, begins a retained read transaction and rechecks the digest after acquiring the read snapshot. Concurrent writer commits remain blocked until close. Call `store.view(scope, tenant_id=..., order_id=..., as_of=<naive datetime>)` and close the store afterward. `OrderScope` grants an explicit immutable set of source order IDs to one tenant. A mismatched tenant or ungranted order fails before lookup; an order before its purchase time is unavailable. The trusted caller must obtain that grant from its authorization layer. Constructing a Python OrderScope does not authenticate a person or establish that the dataset supplies tenant ownership; the real application mapping belongs to O4/O7.

| Fact | Before declared snapshot observation | At/after observation |
|---|---|---|
| Purchase/approval/carrier/customer-delivery event | Only source event timestamps at or before as_of | Same cutoff, with future events hidden |
| Final order_status | Hidden; final status must not be backdated | Original final source status |
| Items/payments/counts/totals | Null: availability timestamp absent | All snapshot rows and reconciled exact totals |
| Customer city/state, category/translation | Hidden | Source values, retaining missingness |
| Estimated delivery | Hidden: its first availability is unknown | Original plan value, explicitly named estimated |
| Review score/title/message | Hidden: final row has no revision history | Retained only when answer timestamp is present and no later than as_of |

The review creation date is not proof a score/comment existed. Even an answer timestamp does not establish that the final text was unchanged afterward, so final text/score is never backdated before observation. Portuguese review text is retained verbatim in private storage; no translation is invented. The source's English product-category mapping is labelled as source supplied and is not a translation of reviews. Customer unique IDs, zip codes, raw review creation dates and geolocation are not included in OrderView.

The event path is a deliberately limited **effective-time projection of recorded source events**, not a reconstructed historical ingestion log. Nonmonotonic or missing event dates remain source-quality limitations; the importer does not invent intermediate status changes, cancellation dates or delivery outcomes. For future O3 scenarios that need earlier item/payment/text availability, add a separately reviewed, explicitly hybrid availability policy and new provenance/version/tests. Do not quietly infer it from purchase time.

## Verification and limits

Run `uv run --locked --all-packages --link-mode copy pytest -q tests/test_olist_orders.py tests/test_olist_snapshot.py`, then `python dev.py check` and `python dev.py build`. Tests use hand-invented CSVs and cover join multiplication, duplicate/orphan rejection, shared review IDs across orders, source/database pins, missing money, future-event/text canaries, scope failures, unknown timezone and no-overwrite output. Strict mypy includes all installable vertical source packages; standalone acquisition scripts retain their existing separate dependency boundary.

Actual-source and final package/CI results are recorded on #27 and the aggregate report after execution. Source rows/private derived databases stay outside Git and model-provider/telemetry calls. Keep the original [O1 use conditions](olist-source.md#use-conditions-and-export-boundary) with derived data. POSIX files use mode0600; Windows inherits parent ACLs. The path guard protects this specified repository boundary, following O1; it does not discover or administrate every unrelated Git repository on the host. Pins and the authorization grant remain trusted caller inputs. No model quality, business action or production deployment is claimed.
