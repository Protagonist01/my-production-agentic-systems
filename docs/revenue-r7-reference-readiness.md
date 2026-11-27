# Revenue Integrity reference readiness

[Issue #45](https://github.com/Protagonist01/my-production-agentic-systems/issues/45) asks whether the agent can find the terms that govern an unfamiliar invoice, interpret them correctly, and defer when the evidence is incomplete. The November browser walkthrough verified an approved SIM correction. The separate Gemini scope comparison measured routing and surfaced two admissions with a missing unit price. Neither run measured billing interpretation across unfamiliar agreements.

## Evidence we can use

| Source | Test it supports | Evidence still needed for billing |
|---|---|---|
| [CUAD](https://www.atticusprojectai.org/cuad/) and the [pinned local inventory](data/revenue-source-cuad-v1.json) | Find spans for the publisher’s original clause categories in commercial agreements. Price Restrictions, Minimum Commitment and Revenue/Profit Sharing can help locate candidate documents. | Independently establish the governing unit price, seat basis, applicable dates, credits, precedence and invoice amount for each selected packet. |
| [ContractNLI](https://stanfordnlp.github.io/contract-nli/) | Check entailment, contradiction, absent terms and evidence on the publisher’s 17 NDA hypotheses. | Use billing-specific references to establish what an agreement and its amendments require for a particular month. |
| [Constructed billing worlds](revenue-billing-worlds.md) | Check arithmetic, review rules and discrepancy direction against explicit terms. The existing cohort has 29 cases in nine groups. | Evaluate extraction and interpretation on independently labeled source language. |
| [Revenue walkthrough and routing result](revenue-walkthrough.md) | Test the approved correction path and measure scope decisions on an authored fixture family. | Check whether cited passages support the extracted meaning and whether ambiguous terms reach review across unseen families. |

## Draft examples for development

All amounts below are fictional SIM and exclude tax and proration. Deltas are expected minus issued. The references illustrate the rubric. They can be used to check scorer behavior because every case and answer is exposed here.

| Case | Operative text and invoice | Expected interpretation and result |
|---|---|---|
| Renewal uplift | “Four seats at 25.00 each. Increase the monthly unit price by 10% beginning 1 July.” July invoice is 100.00. | Both sentences govern July. Expected 110.00, underbilled by 10.00. |
| Future amendment | “Ten seats at 12.00 per seat.” Amendment replaces 12.00 with 15.00 starting 1 September. August invoice is 120.00. | The base rate still controls August. Expected 120.00, no discrepancy. |
| Credit omitted | “Six seats at 20.00 each. Apply a one-time August credit of 15.00.” August invoice is 120.00. | Apply the credit once. Expected 105.00, overbilled by 15.00. |
| Missing operative price | “Eight seats. Price is stated in Schedule B.” The packet omits Schedule B. Invoice is 80.00. | Request Schedule B. Expected amount and delta are unknown. The invoice is observed state and cannot supply the missing agreement term. |
| Conflicting amendments | Two signed amendments each state they replace the July unit price, one with 13.00 and the other with 15.00. The packet gives no precedence. | Route to review with both passages. Expected amount and delta are unknown. |
| Quote supports a different field | “Unit price 18.00 per seat. Eight seats. Onboarding fee of 36.00 billed at signing.” Later monthly invoice is 288.00. | The onboarding quote exists but cannot support a recurring seat price of 36.00. Expected 144.00, overbilled by 144.00. |

## Prepare the qualification set

1. Inventory access-cleared agreement packets with all pages and amendments. Establish who will supply billing references. A publisher label is sufficient for a matching publisher task. Billing references require applicable independent evidence, such as a qualified annotation with cited terms, or an authoritative pricing schedule and separately validated billing calculation for the supported packet. Route unresolved references to adjudication before freezing. Keep the candidate input, expected outputs and provenance in distinct records. [Langfuse dataset design](https://langfuse.com/docs/evaluation/experiments/datasets)
2. Group by agreement, amendment lineage, source family and template before splitting. Exclude previously exposed families from the fresh cohort. Keep paired invoices, paraphrases and same-family variants together. Retain doc and clause pins, applicable facts, ambiguity reason and the authority behind each reference.
3. Cover clear amounts, missing facts, competing terms, future and superseded amendments, credits and family shift. Give every discrepancy slice benign matched controls. Verify that the reference includes the decisive clause and exceptions as well as the value. Record exclusions and why.
4. Freeze the input projection, references, rules and review baselines, candidate versions, scorer, thresholds and scheduled trials before dispatch. Report exact supported field/amount agreement, benign false alarms, discrepancy precision and case- and amount-weighted recall, wrong admissions on missing/conflicting facts, correct review routing and verified unsafe effects. Include failures and absent outputs in scheduled denominators. Record latency, usage and actual cost where observed.

For the review proposal, reuse the earlier **5% maximum family error at 95% confidence** as a starting point for both resolvable and review-required classes. With a one-sided exact interval and zero observed errors, 59 independent families suffice per class for an individual 95% bound. For a simultaneous 95% statement across these two classes, use Bonferroni-adjusted 97.5% per-class bounds and at least 72 error-free independent families in each class. These are lower bounds on sample size at zero errors. Repeated calls and related invoices contribute stability evidence and do not add families. Prespecify the family failure rule, treatment of missing runs, and scope of the confidence statement. Zero observed critical effects remains a proposed hard gate. The qualified reference inventory and approval of limits are pending.

The existing [evaluation scorer](revenue-evaluation-v2.md) already records missing slots, unsupported claims, false admissions, discrepancy flags and incomplete effect evidence. The first new input needed for qualification is an inventory of independently supportable billing packet references. The exposed development rows, prior model captures and source category inventories do not establish how many eligible unexposed billing families exist. This packet records no new provider results.

## Observed inventory

A read-only census verified the prepared manifest against the independently recorded pin in the [source guide](data/revenue-source.md), checked both SQLite file hashes and ran SQLite's quick check on the evaluator store. Joining the published targets to their source hashes yielded 20,910 questions in 457 inferred families.

The census excluded families listed in four historical exposure inventories (492 records) and three previously prepared cohorts (148, 12 and 12 cases). An exact context hash match also excluded the entire family. The union excluded 276 families. A remaining family is one that did not match those inventories. Broader training or evaluation exposure is unknown. The census verified the four inventory digests and the two prospective cohort file digests against their historical preparation records. The older pilot contributed exclusions using its saved case records and shared source-manifest binding.

| Published category with an answer span | All source families | Remaining across both project splits | Remaining in the project holdout |
|---|---:|---:|---:|
| Minimum Commitment | 160 | 76 | 25 |
| Price Restrictions | 15 | 8 | 1 |
| Revenue/Profit Sharing | 157 | 68 | 30 |
| Any of the three, deduplicated | 246 | 110 | 44 |

To reproduce the counts, join `targets` and `sources` using `case_id` in the pinned evaluator store. For each of the three categories, retain targets with at least one published answer span and count distinct `family_id` by the stored project split. Build the exclusion set from the four `exposure-*.json` inventories and the saved case references in the confidence study, prospective semantic cohort and semantic pilot. Match both family IDs and source context hashes before counting. Only the aggregate counts are included here.

The audited stores contain **zero independently established billing references** in either class. The 44 families are leads for document review. Their clause annotations do not establish whether a packet contains a complete price schedule, whether its terms govern a given invoice, or what amount is due. Even all 110 candidate families across both splits would fall short of the proposed 144-family total if each family could be counted only once.

## Public schedule feasibility checks

Two public GSA documents illustrate a path to evidence for explicit terms. The published schedule can establish an item, rate and billing unit. GSA ordering guidance also identifies order-level price reductions and quotes as evidence, so a posted rate alone cannot establish what a real customer owed. [GSA ordering guide](https://www.gsa.gov/system/files/MAS_Ordering_Quick_Reference_Guide_FINAL_508.pdf)

| Public source | Development check | Evidence limit |
|---|---|---|
| [Schedule 47QTCA25D004P, printed p. 3](https://www.gsaadvantage.gov/ref_text/47QTCA25D004P/1078W9.3VXLQX_47QTCA25D004P_ZIMPATICA.PDF#page=3) | The ZIM-COMP-NAV row supplies a rate of USD 95.72 per user-month. At that stated rate, an illustrative four-user order for one month totals USD 382.88. An illustrative invoice of USD 400.00 differs by USD 17.12. | The seat count and invoice are constructed. The public schedule supports rate extraction and explicitly conditional arithmetic. |
| [Schedule 47QTCA19D009G, printed p. 14](https://www.gsaadvantage.gov/ref_text/47QTCA19D009G/47QTCA19D009G_47QTCA19D009G_TandC.pdf#page=14) | The Copilot Agent offer lists a non-G5 monthly rate, restricts eligible customers and has an award deadline. An illustrative packet that omits eligibility and award date requires those facts before applying the advertised offer. | This tests whether the agent can withhold a conclusion when explicit conditions are unevidenced. It establishes no real order, invoice, or actual customer eligibility. |

The [public-schedule development pilot](revenue-public-schedule-pilot.md) tests eight cases from four software schedules. It states the synthetic order assumptions, keeps source variants grouped and checks the amounts with independent integer arithmetic. Cases with missing conditions or unresolved rate precedence defer without an amount.

For release evidence, the existing profile still requires qualified label review. A source-backed reference method could reduce the amount of review by making the explicit terms reproducible. Any change to what satisfies that profile needs an explicit method decision. Representative commercial packets with actual order terms and independent references remain the gap for the broader interpretation claim.
