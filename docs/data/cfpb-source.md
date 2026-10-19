# CFPB archived source preparation

C1 #34, 2026-10-18 (Africa/Lagos), unmerged `codex/c1-cfpb-import`. The user selected the complete September 2023–March 2024 archive cohort, with March held out. Preparation and verification are implemented; classification, reviewed risk labels and application workflows remain later tasks.

## Source and taxonomy

CFPB [ceased narrative publication in August 2026](https://www.consumerfinance.gov/about-us/newsroom/the-cfpb-to-cease-discretionary-publication-of-complaint-narratives-and-visualizations/). Its [official FOIA archive](https://www.consumerfinance.gov/foia-requests/foia-electronic-reading-room/cfpb-consumer-complaint-database-narratives-archive/) now supplies previously published narratives; [API release 24](https://cfpb.github.io/api/ccdb/release-notes.html) confirms their removal from the live database. The importer deliberately downloads a fixed archive rather than request a live narrative export.

The [fixed ZIP](https://files.consumerfinance.gov/f/documents/CCDB_Export_5_September_2023_through_March_2024.zip) is 100,880,669 bytes and contains one CSV, 618,266,146 uncompressed bytes. SHA-256 archive and taxonomy pins are in [cfpb-source-pin.json](cfpb-source-pin.json). Exact-byte retrieval completed 2026-10-18 UTC. The source is original published data, not a generated evaluation set.

The [August 2023 taxonomy PDF](https://files.consumerfinance.gov/f/documents/cfpb_consumer_complaint_form_product_issue_options_August_2023_FINAL.pdf) took effect August 24, 2023, before this cohort. It splits credit card/prepaid card, adds debt/credit management and changes several issue/sub-issue names. This preparation preserves source selections exactly. It does not collapse old/new labels, treat a label as independently verified, or claim the PDF is an automatically parsed validation schema. The version `cfpb-form-effective-2023-08-24` and exact PDF bytes accompany each manifest. A later taxonomy requires a newly versioned import, label review and compatible evaluation baseline.

CFPB describes the data as [freely available for use, analysis and building](https://www.consumerfinance.gov/data-research/consumer-complaints/). Keep publisher attribution and these source/use notes with derivatives. No additional dataset license identifier was established here. Raw records remain external and private by project handling policy; source publication does not establish anonymity or authorize automatic provider export.

## Reproduce without publishing records

From the repository root after `python dev.py setup`, choose **source and output directories outside every Git checkout**. The examples use placeholders; do not copy raw rows into the checkout even when ignored.

```powershell
uv run --locked --all-packages python -m cfpb_triage.source_cli acquire --source <external-source-directory> --source-pin docs/data/cfpb-source-pin.json
uv run --locked --all-packages python -m cfpb_triage.source_cli prepare --source <external-source-directory> --source-pin docs/data/cfpb-source-pin.json --output <new-external-prepared-directory> --code-revision <reviewed-importer-commit>
uv run --locked --all-packages python -m cfpb_triage.source_cli verify --output <external-prepared-directory> --manifest-sha256 <independently-recorded-manifest-digest>
uv run --locked --all-packages python -m cfpb_triage.source_cli verify-source --source <external-source-directory> --source-pin docs/data/cfpb-source-pin.json
```

Only `acquire` performs network requests. It uses fixed official HTTPS URLs, restricts redirects to the official file host, caps download bytes, checks externally supplied hashes before publication and never replaces an existing source. An existing correctly pinned source is verified offline. `prepare` validates source pins before and after ingestion, exact ZIP inventory, CSV headers/widths, ISO dates and unique numeric complaint IDs. The archive uses the 16-column schema, including narrative but excluding obsolete consent/disputed columns. Errors print a fixed message, never a source row or parsed value.

The preparer writes a new directory exclusively. Failure can retain private partial files; inspect them locally and select a new directory on retry. It does not resume or silently overwrite. Source records are streamed through a temporary SQLite database; the completed output contains only `agent.sqlite`, `evaluator.sqlite` and `manifest.json`. Completed raw staging records are removed. File modes are private on POSIX; Windows inherits filesystem ACLs. Protect the external directory accordingly.

On this development host a `C:\.git` marker covers the usual C: cache/temp locations. Verification uses external `D:\document\.cache\production-agents` storage and sets only its local test shell's `TEMP`/`TMP` there. The storage guard has no exception for the host's root repository. CI uses its ordinary external temporary directory.

## Isolation and temporal rules

| Store / type | Fields | Access boundary |
|---|---|---|
| `agent.sqlite` / `ComplaintInput` | SHA-256 case ID and original published narrative | Agent composition reads only this store/type; closed schema rejects target fields. |
| `evaluator.sqlite` / `ConsumerTarget` | Case ID, product/sub-product, issue/sub-issue, received date, split and group digest | Evaluator-only composition; never passed to the classifier. |
| Aggregate manifest | Source/taxonomy/code pins, field missingness, counts, windows, file hashes and limitations | Shareable provenance; no source IDs, narrative quotes or example records. |

The input excludes all category targets, company, company response, location, submission channel, tags and dates. The narrative may naturally contain a product or issue name; removing those words would alter the task. Hashing public complaint IDs supplies stable opaque keys, **not anonymity**. The reader is a trusted local library, not a tenant authorization service or hostile-code sandbox. Future classifier composition must receive only agent-store access; a Python process given the evaluator path can read it.

Development dates are September 1–December 31, 2023; regression January 1–February 29, 2024; holdout March 1–31, 2024. Dates outside these inclusive windows are counted and excluded. Regression is a separate development-time partition; no H5 case manifest or scorer mapping is created by C1.

For grouping only, normalize narrative Unicode with NFKC, case-fold and collapse whitespace, then hash the normalized text. Preserve the original published narrative in agent input. Every group crossing windows is wholly quarantined; later records are never moved into development. Within-window repeats stay grouped. This prevents exact normalized text overlap among prepared partitions. It cannot establish consumer-level independence, detect paraphrases or identify near duplicates; source consumer identities are unavailable. Group IDs remain scorer-only.

Missing/whitespace narratives and missing product/issue targets are excluded and counted. Optional empty sub-product/sub-issue selections are retained. Missing source-field counts use all archive rows. Missing-text counts use cohort rows; the missing-required-target exclusion counter is conditional on a narrative being present. A row already excluded for missing text is not counted again in that target-exclusion counter. Mask statistics count case-insensitive whole-word runs of two or more `X` characters, including `XXXX` and `XX`. These are pattern counts, not proof that every identifier was scrubbed. No additional masking or translation changes the text.

## Observed complete-cohort evidence

| Measure | Actual count / denominator |
|---|---:|
| Archive/cohort records | 945,532 / 945,532 |
| Missing/whitespace narrative | 626,728 / 945,532 |
| Available narrative before grouping | 318,804 / 945,532 |
| Missing required targets among narrated records | 0 / 318,804 |
| Narratives with an X-pattern mask | 229,967 / 318,804 |
| X-pattern tokens | 5,757,323 |
| Groups spanning time partitions | 1,651 |
| Narrated records quarantined in those groups | 58,066 / 318,804 |
| Prepared records / exact normalized groups | 260,738 / 206,109 |
| Development / regression / March holdout | 139,732 / 71,859 / 49,147 |

All received dates are within September 1, 2023–March 31, 2024; no source record falls outside the selected windows. One source row has an empty issue field, but it is already excluded for missing narrative; the narrated-target exclusion counter remains zero. The completed agent store is 399,843,328 bytes; evaluator store 103,874,560 bytes. Source tables and narratives remain external. The aggregate manifest records exact file digests and eleven observed product names plus product/issue frequencies, without publishing source rows.

## Evidence and limits

The [aggregate prepared manifest](cfpb-2023-09_2024-03-manifest.json) records actual complete-source evidence and observed taxonomy frequencies after verification. Its prepared file digests describe private local stores; the stores themselves are not committed. Treat the manifest digest supplied to `verify` as independent reviewed configuration, not a value selected from the artifact being checked.

The source archive contains published complaint records, including records without narratives. Its usable narrative subset is additionally selected by consent and scrubbing eligibility. These missingness and classification distributions cannot describe all received complaints or all consumers. CFPB [warns that complaints are not a statistical sample](https://www.consumerfinance.gov/data-research/consumer-complaints/); its [scrubbing standard](https://files.consumerfinance.gov/f/documents/cfpb_narrative-scrubbing-standard_2023-05.pdf) also describes withheld narratives, including language/adequate-scrubbing limits. No independent language label exists in this import. Consumer product/issue selections are reference targets; they do not verify alleged events, legal violations, risk severity or harm reduction. C2 must establish independent risk/ambiguity labeling evidence before such claims.

Offline tests use invented text only. They check physical/typed label isolation, date cutoffs/leap day, cross-window group quarantine, missingness/masks, malformed sources, pins, output tamper, no overwrite and bounded download behavior. Full-source ingestion is separate data evidence, not a model-quality experiment. No provider call, classification baseline, calibrated router, reviewed risk target or live application is produced. Prepared SQLite byte hashes identify these local artifacts; cross-platform SQLite builds are not promised to produce identical file bytes. Consume the input/target iterators completely or explicitly close them so read-only transactions are released.

[Code walkthrough](../code-study-cfpb.md) · [CFPB plan](../cfpb-triage.md)


Final local acceptance,2026-10-19: lockedcheck599passed322.20s with53typedsourcefiles; focused29passed5.16s; allsixpackagesbuilt. The installed base-only current verifier matched5package-modulebytes and independentlypinnedmanifest, then verified260,738preparedrows/206,109groups and exactsplitcounts under networkdenial with optionalSDKs absent. This is source/isolation verification; no classification or risk-label quality is established. Exact hosted and combined O2+C1 results are maintained on#34 before handoff.
