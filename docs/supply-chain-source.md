# Independent shipping and weather source snapshots

S1 prepares original source facts for later controlled supply-chain scenarios. It does not join historical shipments to current weather, infer a causal delay, generate simulated outcomes, train a policy or claim freight savings.

## Provenance and permissions

The source is **DataCo SMART SUPPLY CHAIN FOR BIG DATA ANALYSIS**, Fabian Constante, Fernando Silva and António Pereira, Mendeley Data version 5, published 12 March 2019, DOI [10.17632/8gx2fvg2k6.5](https://data.mendeley.com/datasets/8gx2fvg2k6/5). The publisher describes company supply-chain data, provides the structured CSV and its field-description CSV, and declares **CC BY 4.0**. Preserve attribution, version, source link and notice that this project transforms the records; the publisher's operational provenance is not independently established by this importer. No general permission claim is made about unrelated site content. The clickstream file is unnecessary and was not downloaded.

The [official NWS API documentation](https://www.weather.gov/documentation/services-web-api) supplies independent current U.S. alerts in GeoJSON. It requires an identifying User-Agent, supports `/alerts/active`, and describes a seven-day alert API rather than a historical archive. The [NWS use notice](https://www.weather.gov/disclaimer) permits lawful use of public-domain NWS information subject to attribution/no endorsement and no altered content presented as official. Third-party material can have separate terms. This project preserves raw JSON privately, exposes an explicitly transformed fact projection, and supplies no emergency notification or delivery guarantee.

Raw source CSV/JSON, source identifiers and operational rows remain outside Git. The published manifest contains only aggregate counts, hashes, dates and source limitations. This workflow makes ordinary public source requests, never an LLM/provider request.

## What is visible

The 53-column DataCo CSV contains customer names, emails, passwords, street/location fields, order identifiers, shipment outcomes and commercial figures. The public projection discards customer PII, raw identifiers, prices/profits and outcome fields. It retains an opaque SHA256 item key, recorded naive order time, destination country/region, category, quantity, shipping mode and scheduled duration. Separate evaluator-only records retain original order/item IDs, recorded shipping time, actual shipping duration, delivery status, late flag and order status. These are published retrospective references, not independently reviewed causal or simulation labels.

The CSV uses a lossless Latin-1 byte-to-character decode; semantic text encoding is not independently verified. Exact headers and order are checked. Dates follow the source's month/day/year minute format. The original timezone and historic per-field availability are **unverified**. A naive timestamp is never converted to UTC or interpreted as a known scenario observation. A DataCo fact is available only at or after the explicitly captured snapshot observation time; historical order dates do not authorize a historical online view. Any future S2 retiming must be a declared constructed scenario with separate lineage and hidden outcomes.

NWS alert facts retain independent source keys, capture/sent/effective/onset/expires/ends times, event, area, status and severity/urgency/certainty. Aware offsets are required. Collection update cannot follow capture, alert sent cannot follow capture, and expiry must follow sent/effective. Duplicate alerts or an unconsumed next-page link fail preparation. A future onset can be visible as a forecast statement; visibility never asserts that the event has occurred.

## Scenario clock and freshness

`read_shipments(output, manifest_sha256, clock)` yields no shipment before its real snapshot observation. `read_alerts(output, manifest_sha256, clock, max_snapshot_age)` requires an explicit positive freshness allowance of at most seven days. It returns no alerts before capture or when collection-update age exceeds that allowance. It also requires Actual Alert/Update messages, sent/effective at or before the scenario clock, and expires/ends after that clock. Test, exercise, cancellation, future-issued, expired and ended messages are excluded. HTTP Date/Cache-Control/Expires are retained in the source pin; HTTP cache lifetime is separate from the caller's scenario freshness rule.

An explicit acquisition command creates one new private snapshot and a receipt, without retrying or overwriting:

```powershell
uv run --locked --all-packages --link-mode copy python -m supply_chain.source_cli capture-weather `
  --output D:/private/nws-new `
  --user-agent "production-agentic-systems (https://github.com/Protagonist01/my-production-agentic-systems)"
```

Review the returned original hash and private receipt before creating a new source pin. Normal preparation, verification and public readers make no network requests.

The captured modern U.S. weather population and historical multinational DataCo population have separate spatial and temporal coverage. There is no shipment-to-weather mapping, country substitution, causal join or unseen alert history. Empty/old alerts mean unavailable evidence, never proof of safe weather.

## Reproduce preparation and verification

Acquire the two exact files from the versioned Mendeley page/file API and one NWS `/alerts/active` response. Record the download/capture receipt privately, compare each DataCo file with its publisher-provided SHA256/size, then review and retain the explicit `SourcePin` byte digest. The source pin binds each raw file and capture clocks; it is not automatically changed to accommodate new input.

Use new external paths from the repository root after locked setup:

```powershell
python -m supply_chain.source_cli prepare `
  --dataco D:/private/DataCoSupplyChainDataset.csv `
  --description D:/private/DescriptionDataCoSupplyChain.csv `
  --nws D:/private/alerts.json --source-pin D:/private/source-pin.json `
  --source-pin-sha256 <independently-reviewed-pin> --output D:/private/prepared-new
python -m supply_chain.source_cli verify `
  --dataco D:/private/DataCoSupplyChainDataset.csv `
  --description D:/private/DescriptionDataCoSupplyChain.csv `
  --nws D:/private/alerts.json --output D:/private/prepared-new `
  --manifest-sha256 <independently-retained-manifest-digest>
```

Prefix module commands with `uv run --locked --all-packages --link-mode copy` when not using the workspace interpreter. Output must be outside every Git checkout and is created exclusively. The preparer streams CSV lines, hashes exactly the bytes consumed, validates the complete publisher pin before creating a final manifest and streams separate public/evaluator inserts. Failed partial output has no passing manifest and must not be reused. The verifier replays the pinned originals, compares every derived row, checks exact SQLite tables/indexes/schema and recomputes all aggregates. Repinning a changed target, view or aggregate cannot redefine the raw source truth.

Local public readers require the independently retained manifest pin and check public-store bytes/schema before yielding typed projections. They never open the evaluator store. Filesystem separation is not an OS security sandbox or HTTP authorization system; the file owner must protect snapshots against concurrent replacement. Raw inputs are trusted private administrative artifacts, not a remote upload endpoint. Generic CLI errors omit source payloads.

## Evidence boundary

The completed [source aggregate](data/supply-chain-source-v1.json) records 180,519 shipment lines across 65,752 orders and 306 independently captured NWS features. Preparation took 305.66 seconds; full original-to-store verification and clock checks passed in 205.42 seconds. Recorded DataCo order timestamps span 2015-01-01 through 2018-01-31 with timezone unverified. The field-description file contains 52 descriptions: Order Zipcode has no exact description and the shipping-date label differs in case; neither discrepancy establishes historical availability. At the NWS capture clock, 245 alerts pass the explicit thirty-minute example allowance and status/validity checks. A stale clock returned no alerts and a pre-observation shipment clock returned no rows.

The private prepared manifest pin is `ff7e5ca38542de94d12a6140367abd469ca58b3c4a95b35ae8bc36b6667bab35`; the raw-source pin is `d5519c64e3d413fdd33af4700d0a4f7ec2d843757e829c83d67dfbccc775d33a`. The [code study](code-study-supply-source.md) traces row-by-row original-source reconstruction. Invented tests cover schema changes, duplicates, malformed timestamps, future/expired alerts, explicit freshness, source/evaluator isolation, mutation/repinning, output exclusivity and source-pin integrity. Full integration and hosted matrix checks belong to the parent delivery. No live model quality, independent shipment outcome adjudication, intervention accuracy or release acceptance follows from source verification.
