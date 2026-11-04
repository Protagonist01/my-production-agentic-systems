# Controlled amount, reship and clarification references

On 2026-11-04 the owner accepted the method and first twelve meanings with **“Accept
this constructed development method.”** The separate [acceptance record](data/olist-controlled-field-acceptance-v1.json)
binds the exact private proposal, references and review packet. This accepted development
method supplies neither natural-customer gold, independent family sampling nor replacement
release review. The [draft](data/olist-controlled-field-draft-v1.json) retains its original
proposal fields unchanged. Its method file SHA-256 is
`6bcd0d9541217af327381a5bdf7367c06c2fa277f3e84d0e6624dbb1c6275ccc`.
Receipt time records the reply, not the exact owner-action time. Pins verify bytes and
supplied provenance, not a cryptographically authenticated identity.

## Twelve entirely authored development examples

| # | Input | Intent | Requested minor SIM |
|---|---|---|---:|
| 1 | Please refund exactly 0.00 SIM. | refund | 0 |
| 2 | Please refund exactly 100.00 SIM. | refund | 10000 |
| 3 | Please refund exactly 100.01 SIM. | refund | 10001 |
| 4 | Please refund exactly SIM 99.99. | refund | 9999 |
| 5 | I paid 100.00 SIM. Please refund exactly 25.00 SIM. | refund | 2500 |
| 6 | Please refund my full payment. | refund | null |
| 7 | Please reship this order. Do not refund it. | reship | null |
| 8 | I paid 99.99 SIM. Please reship this order. Do not refund it. | reship | null |
| 9 | I have not chosen between a refund and a reshipment. What are my options? | clarify | null |
| 10 | I need help with this order. I have not chosen an action. | clarify | null |
| 11 | I paid 100.00 SIM. What is this order's shipping status? | status | null |
| 12 | What is the status of my existing refund? | unsupported | null |

All six refund variants share one conservative parent; each other intent has one parent:
five declared dependent groups, all exposed development. These counts establish no
independence, representative distribution, fresh holdout or confidence interval. Native
Bitext/ABCD bytes, labels, exposure indexes, partitions and decisions stay unchanged.

Null has an explicit controlled meaning: case 6 requests a full payment without naming
a number; non-refund routes cannot carry a requested refund amount. Missing native amount
annotations remain unknown. Payment mentions in cases 5/8/11 never become requested
refunds. Zero and above-cap requests stay literal instead of becoming the full payment
or being clipped to the cap.

## Construction and independent consistency check

[`controlled_reference.py`](../projects/olist-support/src/olist_support/controlled_reference.py)
defines ten templates and strict typed slots. `ControlledSpec` requires exact requested/
payment roles and rejects booleans, negative/overflow values and extra slots. `_render`
builds literal pieces using integer divmod and records complete currency-token offsets.
`construct` binds the spec, case, conservative parent, candidate-only input, expected
RoutingPlan and role-specific spans. Revalidation reconstructs every field.

[`controlled_reference_check.py`](../projects/olist-support/src/olist_support/controlled_reference_check.py)
does not import the generator. Full-message expressions independently capture roles and
use Decimal arithmetic. Both `99.99 SIM` and `SIM 99.99` are explicit grammar productions.
Unknown wording, signs, malformed decimals, foreign currency, extra actions, unicode digits
and overflow refuse reference construction. Refusal means no reference under this method,
not a prediction that the customer's intent is unsupported.

Seeded faults demonstrate detection when the generator's expected amount and witness
both select the payment, or when a clarification becomes refund. Both implementations
share an engineering author and can share a semantic mistake. Agreement checks consistency
conditional on the accepted grammar; it is not independent language adjudication, a
customer authority or a general parser. Neither is wired into a production planner,
customer confirmation, service recorder, baseline, prompt or legacy review gate.

Input, expected output and metadata stay separate, following the
[Langfuse dataset model](https://langfuse.com/academy/datasets). No reference metadata enters
AgentInput; no live Langfuse dataset is created or changed.

## Actual conditional policy check

Use an entirely invented canceled/visible order, confirmed undelivered, paid 100.00 SIM,
no prior refund and complete/current facts. Feed the structured refund/reship meanings
into the separate `evaluate_policy` table and existing `policy.propose`; neither extracts
intent from text. All eight agree with hand-declared expectations: cases 2/6 propose
100.00 SIM; cases 1/3/4/5/7/8 require review. Cases 9–12 are outside that table's input
domain and are not fabricated as refund requests. All eight outputs are recorded.

Original view/facts remain identical. No SQL service, receipt, action, customer click or
business mutation runs. Policy agreement authenticates neither original intent nor
completion and authorizes no refund. Existing consent/state/recovery evidence stays separate.

## Reproduction and remaining boundary

From the reviewed checkout:

```powershell
.venv\Scripts\python.exe -m pytest -q tests/test_olist_controlled_reference.py
.venv\Scripts\python.exe D:\document\.cache\production-agents\olist\controlled-field-reference-proposal-2026-11-04-v1\reproduce.py --verify
```

The private packet holds immutable method/references/inputs/review, policy outputs,
reproduction script and file pins. Sibling directory
`controlled-field-development-acceptance-2026-11-04-v1` holds the exact owner reply/pin.
Readback recomputes all twelve references/spans, eight actual policy proposals and the
read-only stopped allowance. Forty new tests cover boundaries, roles, altered text/labels/
identities, illegal authority flags, unknown language, related variants and seeded faults.
These test construction/checking mechanics, not model quality.

For #33, pair this controlled development evidence with accepted native intent references
without inheriting unknown fields or treating populations as interchangeable. A complete
study still needs supported qualification references/sampling, frozen service-aware inputs/
scorer/host, selected-host readiness and concrete provider allocation approval. Do not
coerce this draft into the old suffix-only RoutingReference schema or call it an accepted
service cohort. Release-review requirements and operating targets remain unchanged.
No provider calls, keys, allocation changes or stopped-run continuation occur. The same
ledger stays 447/614, zero unsettled and one original stop as read for this delivery.
