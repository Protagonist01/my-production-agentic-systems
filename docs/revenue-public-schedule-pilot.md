# Revenue public-schedule development pilot

Issue #45. Eight exposed cases drawn from four public pricing schedules pair published rate or eligibility facts with invented buyer, order and invoice details. Four should produce an invoice comparison, three should ask for specific missing facts, and one should send conflicting evidence to review. Each schedule and its variants stay in the same development family.

The [input file](data/revenue-public-schedule-pilot-inputs-v1.json) gives the candidate the schedule facts, order facts and question. The [reference file](data/revenue-public-schedule-pilot-references-v1.json) gives the scorer the family, expected route, missing fields, usable price, expected total and signed discrepancy. The reviewed [source manifest](data/revenue-public-schedule-pilot-source-pins-v1.json) binds four retained original PDFs to exact byte lengths, SHA-256 digests, physical PDF pages and case IDs. It also binds both dataset files after normalizing Windows line endings to LF.

The November 27 review replaced the three draft Zimpatica cases. The old price PDF returned HTTP 404 and the official replacement terms PDF omitted the rate. The MCM schedule supplies a directly checkable per-user monthly rate in its official price table. The review also made the award timing and eligibility assumptions explicit in cases 07 and 08.

## Check the references

Amounts are illustrative USD. A positive delta means underbilling. A negative delta means overbilling.

| Cases | Facts to check in the published source | Expected outcomes under the stated order assumptions |
|---|---|---|
| 01–03 | The 4071-MO-CS-S row lists USD 247.29 per user-month inclusive of IFF. [GSA schedule 47QTCA22D00CS, p. 7](https://www.gsaadvantage.gov/ref_text/47QTCA22D00CS/47QTCA22D00CS_Terms_and_Conditions_MCM_04_2026.pdf#page=7) | Four users cost USD 989.16. Case 01 is overbilled by USD 10.84. Case 02 matches. Case 03 needs the user count even though its invoice equals the four-user total. |
| 04–05 | The GAPPS-ENT-1USER-12MO row shows a USD 25.00 list rate, a 6% discount and a USD 23.50 GSA rate per user-month. [GSA schedule GS-35F-135BA, GSuite pricing](https://www.gsaadvantage.gov/ref_text/GS35F135BA/10ADVA.3W0QPY_GS-35F-135BA_GS35F135BAEFFECTUAL.PDF) | The fictional order adopts the final rate. Five users cost USD 117.50. Case 04 matches. Case 05 is underbilled by USD 5.00. |
| 06 | The Zodiac SaaS description uses monthly wording while the unit-of-issue column says annual. [GSA schedule 47QTCA21D00DJ, products awarded prices](https://www.gsaadvantage.gov/ref_text/47QTCA21D00DJ/47QTCA21D00DJ_47QTCA21D00DJ_TandC.pdf) | Route to review with both pieces of evidence. The packet leaves the applicable billing unit unresolved. |
| 07–08 | The Copilot Agent offer gives an MRP of USD 8.64 per user-month, restricts eligibility and gives a September 30, 2026 award deadline. [GSA schedule 47QTCA19D009G, Copilot Agent offer](https://www.gsaadvantage.gov/ref_text/47QTCA19D009G/47QTCA19D009G_47QTCA19D009G_TandC.pdf) | Case 07 needs customer and user eligibility and the adopted order price. Case 08 needs the signed award date. Both totals stay unknown, even though the invoice matches five times the advertised rate. |

A reviewer can check each row against its linked source and the corresponding order assumptions. Cases 06–08 deliberately ask the workflow to withhold a total. They contain no judgment about what a real customer owes.

## Offline baseline results

Run from the checkout after the locked setup:

```powershell
uv run --locked --all-packages python revenue_schedule_pilot.py --source-dir <retained-pdf-directory>
```

The runner verifies the integer arithmetic on all four calculable cases, checks full reference coverage and runs the existing Revenue scorecard. Both comparators completed eight of eight slots. Each returned generic review on all eight and matched the expected action on **1/8**. Neither attempted the four calculable cases. Both deferred on the four unresolved cases, but matched the specific clarification or review route on only one. The rules baseline expects normalized key/value lines. These schedule paraphrases exercise its behavior outside that grammar.

The runner records the input, reference, manifest and plan digests. This capture used zero provider calls. The [reference inventory](revenue-r7-reference-readiness.md) explains the remaining qualification evidence for unfamiliar agreements.

## Proposed two-model run

| Provider | Proposed model | Maximum new attempts |
|---|---|---:|
| Gemini Developer API Free | [Gemini 3.5 Flash-Lite](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite) | 1 invented canary + 8 case calls |
| OpenRouter Free | [Gemma 4 26B A4B Free](https://openrouter.ai/google/gemma-4-26b-a4b-it:free) | 1 invented canary + 8 case calls |

Use the existing credential configuration. Run one paired trial per case. Send the same text projection and semantic response schema to both models. Each request contains the public schedule paraphrase, invented invoice/order facts and the question. The expected answers and original PDFs stay local. Each result must provide a route, named missing facts when applicable, the amount and signed discrepancy in integer cents when justified, and evidence quoted from the input. Score exact action, missing-field agreement, justified amounts and unsupported claims. Include failed and unrun slots in the report. A passing canary is required per provider. Count failures against each cap. Use an explicit zero-price OpenRouter endpoint with the required schema support and with fallbacks disabled. Stop on availability, settlement or pricing failures.

The owner approved nine new attempts per provider and reconfirmed Gemini Free. The runner verified all four PDF hashes against the pinned manifest and matched the existing credential associations. The Gemini append raised the shared ceiling from 1,284 to 1,293. The OpenRouter grant was recorded separately from the older invented-only canary.

## Observed comparison

| Measure | Gemini 3.5 Flash-Lite | OpenRouter Gemma 4 26B Free |
|---|---:|---:|
| Attempts including the canary | 9 of 9 | 1 of 9 |
| Canary | Passed | HTTP 404 |
| Domain outputs received | 8 of 8 | 0 of 8 |
| Correct route among received outputs | 8 of 8 | Unmeasured |
| Exact missing-field set | 7 of 8 | Unmeasured |
| Exact total and signed discrepancy, including required nulls | 7 of 8 | Unmeasured |
| All automated checks passed | 6 of 8 | Unmeasured |

Gemini calculated all four resolvable invoices correctly. In case 06 it routed the conflicting units to review, quoted both, and withheld the total. It also emitted a missing-condition code where the reference expected an empty list for a conflict. In case 07 it correctly asked for eligibility and the adopted order rate, then returned USD 43.20 and a zero discrepancy despite those missing facts. All eight outputs quoted literal text, which by itself gives no assurance that the evidence supports the conclusion.

The current schema allows a clarification response to carry a numeric total. A deterministic check should reject amounts on `request_information` and `review`, then verify any analyzed amount against the applicable unit, rate and quantity. The case 07 answer is a regression example for that check.

OpenRouter's public catalog showed a zero-price endpoint with structured output before dispatch. The pinned route returned 404 on the invented canary. The runner retained the HTTP status and did not capture the error body, so the exact cause is unknown. No domain cases were sent to OpenRouter and no quality ranking is possible.

One separately approved diagnostic canary used the same model, Google AI Studio endpoint, strict response schema and zero-price limits. The existing key passed the read-only Free-tier check. The catalog still listed the endpoint. Dispatch returned HTTP 404 again, and the sanitized response identified **no endpoints**. This narrows the failure to endpoint availability under the requested constraints. The response did not establish which constraint or upstream condition caused the mismatch. The attempt was settled in the OpenRouter ledger, and no billing cases were sent.

### Nemotron follow-up

The pinned NVIDIA route served Nemotron 3.5 Super VL Free for both calls and reported zero cost. The invented canary passed all four automated checks. It used 736 reasoning tokens and produced valid JSON within the 1,536-token completion limit. Case 01 returned HTTP 200 with a `length` finish reason. It used all 1,536 completion tokens for reasoning and returned no visible answer. The frozen runner stopped there, with one incomplete and seven unrun domain slots. Both attempts matched their settled OpenRouter ledger records. The result measures endpoint and output-budget behavior. A comparison with Gemini still requires completed domain answers. For a future run, test a bounded reasoning budget on an invented invoice resembling case 01 before sending the schedule cases.

The approved follow-up canary switched reasoning off because the model advertises optional reasoning and direct token-budget support was unverified. It kept the same NVIDIA route, strict schema and 1,536-token completion limit. On an invented invoice with a prior-period setup fee, Nemotron calculated USD 583.87 and a signed discrepancy of −USD 16.13. All four checks passed. The response completed in 1.22 seconds with 88 completion tokens, zero reported reasoning tokens and USD 0 reported cost. The one attempt was settled and read back from the OpenRouter ledger.

### Completed paired replay

The owner then approved eight new Free attempts. Reasoning-disabled Nemotron completed all eight original cases on the pinned NVIDIA route. The report matched all eight settled ledger entries. OpenRouter reported zero cost and no reasoning tokens on each response.

| Check on eight cases | Saved Gemini | Nemotron with reasoning disabled |
|---|---:|---:|
| Correct route | 8 | 6 |
| Exact missing fields | 7 | 5 |
| Correct amounts or required nulls | 7 | 7 |
| Literal evidence | 8 | 7 |
| All four | 6 | 4 |

Gemini calculated all four answerable cases. Nemotron calculated three and deferred a clear underbilling case. Nemotron withheld the total in all four unresolved cases. It requested information where the fixed reference calls for review of conflicting units and supplied an extra missing field in another case. It also paraphrased evidence where the schema requested exact input substrings. The single-run development results favor Gemini on overall agreement and expose a concrete unsafe-amount failure even on a correct route.

The post-response guard in `revenue_schedule_guard.py` rejects totals on clarification and review. For analysis, it requires separately verified monthly unit price, quantity and issued total, then checks the reported figures with integer arithmetic. Replaying the stored outputs blocked Gemini case 07, accepted all four of Gemini's valid calculations and accepted all three of Nemotron's valid calculations. The guard does not establish the governing terms or adjudicate evidence. It is exercised in the pilot and its tests, and the existing browser demo continues to use the deterministic SIM engine.

### Production decision

These four exposed source families can identify regressions. Production qualification needs a fresh, representative set of unfamiliar agreement packets with independently supported governing terms, missing-fact judgments and expected totals for the supported billing policy. Run the final guarded candidate on that set, confirm reference coverage and qualify the proposed error bounds before enabling customer-facing decisions. The browser demo's current loopback authentication and SIM ledger also require a production deployment target with remote identity, tenant isolation and verified backup, restore and rollback. See [Revenue #45](https://github.com/Protagonist01/my-production-agentic-systems/issues/45), [deployment #58](https://github.com/Protagonist01/my-production-agentic-systems/issues/58) and [recovery #59](https://github.com/Protagonist01/my-production-agentic-systems/issues/59).

The private execution receipts matched every settled ledger row. Gemini used 2,941 reported tokens across nine replies. Its eight domain calls had a nearest-rank p95 of 1.12 seconds. Actual billing cost was not observed. The shared Gemini ledger ended at 714 of 1,293 attempts, with zero unsettled reservations. OpenRouter retains one settled attempt under this new scope and one under the older scope. The first setup run hit a read-only file flag before any reservation. The execution used a fresh receipt directory and restored the original flag.
