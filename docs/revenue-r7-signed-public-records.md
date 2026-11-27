# Signed public billing references for Revenue #45

Three executed public records are pinned for Revenue #45. They cover annual pricing, a superseding monthly order form, and tiered monthly pricing. A fourth signed source remains provisional pending retrieval of its original PDF. Invoice figures and account or user counts supplied by the test scenarios are fictional. This is a development reference set.

## Retained source

**Denton contract 6928.** The executed contract incorporates Exhibit D and gives precedence to the written agreement and then the listed contract documents. Exhibit A directs pricing to Exhibit D and states a separate contract-wide ceiling of USD 95,524.73. Exhibit D gives Legistar fees by year and shows a prorated fee for the streaming line. The pricing tables were checked against the published text and the downloaded copy's rendered PDF pages. [Executed Denton contract](https://lfpubweb.cityofdenton.com/MaterialsManagement/0/edoc/12856/6928%20EXECUTED%20CONTRACT%20-%20Granicus.pdf)

| Source locator | What it establishes |
|---|---|
| Physical PDF pages 2–3 | Incorporated pricing exhibit and executed signature blocks |
| Physical PDF page 4, Exhibit A §1 | USD 95,524.73 overall ceiling and pricing by Exhibit D |
| Physical PDF page 13, Exhibit D | First-period product fees, service dates and proration |
| Physical PDF page 14, Exhibit D | Separate annual line amounts for the two remaining periods |

Retained as `denton.pdf` in the private Revenue cache under `signed-public-records-v1`. Size 1,506,360 bytes. SHA-256 `35d4001277bc970e638045f5b9a6a8cf223beb02ef7282bc0daa55df92d956f7`.

## First reference draft

Amounts apply to the specified line only. The simulation supplies the invoice amount and excludes tax and later adjustments. Signed delta is expected minus issued. Review cases have no expected amount or delta under the current app's whole-month policy.

| Case | Source and invoice scenario | Expected reference |
|---|---|---|
| D01 | Denton Exhibit D, Legistar for October 2019 through September 2020. Fictional annual invoice USD 16,178.39. | Extract USD 16,178.39 for this line and period. Arithmetic control gives delta USD 0.00. |
| D02 | Same line for October 2020 through September 2021. Fictional annual invoice repeats the earlier USD 16,178.39. | Extract USD 16,987.31 for the later period. Arithmetic control gives delta +USD 808.92. |
| D03 | Same line billed as a single month, with no monthly pricing rule in the reviewed packet. | Route to review under the current policy. The annual table does not authorize dividing the price into a monthly charge. |
| D04 | Denton Exhibit D, Granicus Streaming October–November 2018. Compare the stated prorated fee with a fictional line billed at the full USD 13,113.24 annual fee. | Extract the expressly stated USD 2,185.54 prorated amount. Arithmetic control gives delta −USD 10,927.70. The current application routes proration to review. |
| C01 | Collin County Schedule 1, full month in October 2024 with the signed schedule and stated 112 licenses. Fictional licensing invoice USD 10,416.00. | The schedule states a monthly fee of USD 10,416.00. The 112 × USD 93.00 cross-check also gives USD 10,416.00. |
| C02 | Same county schedule and full month. Fictional licensing invoice USD 10,500.00. | Expected USD 10,416.00, delta −USD 84.00 under the stated fixture assumptions. |
| C03 | County agreement, same period, but the test packet withholds Schedule 1. | Request Schedule 1. The current invoice supplies no reference amount. This omission is a constructed test case. |

All four Denton cases share one agreement family. The three Collin County cases share another. The Denton source can test annual price, date selection and proration extraction directly. Its annual and prorated charges fall outside the current monthly billing engine. The Collin County source has a monthly schedule. Schedule 1 distinguishes a per-user ceiling from a separately stated monthly fee. The fee table, term and visible executed signature page were reviewed from the indexed copy. The county host refused direct retrieval, so the Collin rows are provisional pending an original-byte pin. [Collin County signed agreement](https://eagenda.collincountytx.gov/docs/2024/CC/20240916_3004/56575_Attachment_C_-_Collin_County_SaaS_Subscription_and%20_%20License%20Agreement%20Final%20Signed.pdf)

## Other intake decisions

- City of Orange amendment 6858.6 incorporates an order-specific exhibit and sets precedence. Its download timed out on both attempts. It also uses Granicus order forms, so it shares a vendor/template lineage with Denton for independent-family counting until a grouping review establishes otherwise. [Orange executed amendment](https://citydocs.cityoforange.org/WebLink/edoc/244321144/AGR-6858.6%20-%20GRANICUS%20LLC%20-%20SIXTH%20AMENDMENT%20TO%20MASTER%20SUBSCRIPTION%20AGREEMENT%20-%20NOV%2015%2C%202022.pdf?dbid=0&repo=CityofOrange)
- The [earlier GSA pilot](revenue-public-schedule-pilot.md) supplies public schedule rates paired with constructed orders. This intake relies on executed, customer-specific records to establish the governing price.

This exposed draft is ready for reference review. The release profile still calls for independent label review and fresh agreement families. No model calls were made.

## Executed monthly orders

| Source | Retained PDF | Bytes | SHA-256 | Source locators |
|---|---|---:|---|---|
| Pinellas County and VertexOne, Third Amendment | `pinellas.pdf` | 5,777,560 | `4f74c04590ff7749a77273c6faf4174e05483f464fee6a8aa7e997f216a874b5` | PDF page 1 has signatures from both parties and replaces all prior order forms with Attachment 3. Physical PDF page 2 has recurring SaaS prices and the cost-of-living adjustment provision. |
| Colorado HCPF and AssureCare, base contract | `colorado.pdf` | 3,011,616 | `5e63165bed9789af7474396169f1b6a87bc3337fb748fc506b63bff05d9463e2` | Physical PDF page 3 has both parties' signatures and the controller's effective date of July 30, 2024. Exhibit C, printed pages 7–8 (physical PDF pages 81–82), has the rate table and worked example. |

Both PDFs are in the same private `signed-public-records-v1` cache as Denton. Signature pages were checked visually. [Pinellas County executed amendment](https://pinellas.legistar.com/View.ashx?G=4892F4D9-36FE-48F2-8E4D-022D5221CB08&GUID=BABCF38E-4219-4D8B-879F-F1BD485C9B60&ID=12611956&M=F) · [Colorado executed base contract](https://hcpf.colorado.gov/sites/hcpf/files/AssureCare%20Base%20Contract.pdf)

| Case | Scenario and source | Expected reference |
|---|---|---|
| P01 | Attachment 3 §1, VXenterprise base subscription. Assume a full in-term month and no applicable cost-of-living adjustment. Fictional invoice USD 5,500.00. | Base monthly fee USD 5,563.00. Delta +USD 63.00 under the fixture assumptions. The amendment supersedes the earlier order form. |
| P02 | Same base subscription. Fictional invoice USD 5,700.00 claims an adjustment, and the submitted packet omits the governing adjustment terms and evidence of its effective date. | Identify the USD 5,563.00 base and request the governing adjustment terms and effective-date evidence. Amount and delta remain unresolved. |
| P03 | Attachment 3 §1, VXsmart. Fictional record supplies 10,000 qualifying billable accounts for a full in-term month with no applicable adjustment and a USD 1,200.00 invoice. | Rate USD 0.1125 per billable account. Arithmetic control gives USD 1,125.00 and delta −USD 75.00. The current whole-seat engine should route this account-based, fractional-cent rate to review. |
| A01 | Exhibit C §§3.1.6–3.1.7, SFY25 worked example for 2,700 authorized users. | Published total USD 341,366.50. Table 10 and the printed tier subtotals reproduce it. Table 11's narrative uses USD 115.15 for the 500-user tier, which would raise the total to USD 341,376.50. Flag the mismatch and route to review. An automated correction has no reference amount or delta. |
| A02 | Exhibit C §3.1.6. Compare the stated minimum for December 2024 and January 2025. | Minimum rises from 2,200 to 2,500 on January 1, 2025. Extract both effective rules. Route the graduated tier and minimum calculation to review under the current engine. |
| A03 | Exhibit C §3.1.6. A fictional usage export shows one authorized user against two agencies during the month. | Count the person once for the user metric. A full month of verified usage is needed to compute a charge. |

P01–P03 count as one agreement family and A01–A03 count as one. The six additional cases probe source interpretation, arithmetic, and escalation. The fixed monthly fee, fractional-cent account rate, and graduated tiers are outside the current engine's whole-month, whole-seat calculation.

## Excluded from executed pricing evidence

- The Denver fifth amendment's physical PDF page 3 has blank city signature lines. Its dated price schedule is a source lead pending an executed copy. [Denver legislative copy](https://denver.legistar.com/View.ashx?GUID=83650317-A93B-44DE-B5FE-5F7BF9EF9CDA&ID=11943231&M=F)
- The Santa Barbara SOW's physical PDF page 5 has a vendor signature and a blank county signature block. Its rates are a source lead pending an executed copy. [Santa Barbara legislative copy](https://santabarbara.legistar.com/View.ashx?GUID=42D16337-9F2B-4995-8DFD-3D460070725A&ID=11474987&M=F)

The set contains ten cases tied to three pinned executed agreement families, with three provisional Collin County cases. The signed prices establish source-backed development references for the scenarios described. The remaining release-evidence gap includes supported whole-seat monthly pricing paired with verified quantities and effective dates, plus evaluation on fresh agreement families.

## Observed development comparison

The runner verified the three PDF digests and pinned ten public pricing paraphrases with fictional invoice facts plus an invented canary. Each provider received a fixed prompt and output schema. Expected answers and original PDFs stayed local. The comparison tests interpretation of the supplied paraphrases. Full-document retrieval, governing-document completeness and production ledger effects are separate measures. This comparison allows calculating a signed annual or expressly prorated line even though the production candidate's whole-seat engine would route that line to review.

| Measure | OpenRouter NVIDIA Nemotron 3.5 Super VL Free | Gemini 3.5 Flash-Lite Free |
|---|---:|---:|
| Attempts, including canary | 11 | 1 |
| Domain outputs | 10/10 | 0/10 |
| Correct route | 8/10 | Unmeasured |
| Correct missing fields | 10/10 | Unmeasured |
| Correct amount and delta, including required nulls | 8/10 | Unmeasured |
| Literal citations | 8/10 | Unmeasured |
| All four checks | 7/10 | Unmeasured |

An always-review baseline matched the route on 3/10 and withheld amounts on all five unresolved cases. Nemotron withheld amounts on all five and calculated three of the five resolvable cases. It referred the Denton D02 annual price change and D04 explicitly priced proration to review. Both had a governing price and material invoice difference in the supplied facts. In Colorado A01 it chose review and withheld amounts, but paraphrased the conflicting rates instead of returning verbatim evidence. The literal citation check verifies exact substrings. A separate semantic check is needed to verify that each quote supports the conclusion.

OpenRouter reported zero cost on all 11 attempts. The longest domain call took 2.17 seconds. Gemini returned HTTP 503 on the invented canary, so all ten Gemini domain slots were left unrun. All 12 provider results matched the corresponding ledger settlements. The ten unused Gemini slots remain dedicated to this scope. There is no model ranking from this run.

## Recording status

Thirteen local Python tests passed, including the authenticated walkthrough with real Docker PostgreSQL, and the browser session test passed. The demo uses constructed agreements and a separate SIM ledger. The remote app still needs an Azure target, HTTPS and a hosted identity and session configuration that preserves operator/reviewer separation. This evaluation provides evidence for a demo walkthrough. The issue #45 release evidence remains pending.
