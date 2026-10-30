# Explicit Olist routing candidate

Prepared against main `b19e8cb`, 2026-10-30. Refs #33. Software mechanism work only;
no provider dispatch, semantic qualification, deployment or release acceptance.

## Correct the diagnosis first

The prior research mistakenly treated the SIM `SupportRequest` two-intent type as the
workflow classifier. Actual `workflow.IntentPlan` already permits refund/status/reship/review.
The status branch reports the scoped recorded order status. It does not read a refund-status
backend and cannot establish whether a prior refund settled. This is a coverage distinction,
not a reproduced language-model failure or evidence that the old classifier forced refunds.

The owner accepted a corrected ABCD development projection after this finding:3refund,
2status,4clarify,3unsupported. Save it as a new private `workflow-projection-v2.json` referencing
the original mapping and input hashes. Original publisher labels,12proposals and both earlier
acceptance records remain unchanged. Owner acceptance is development review, not blind gold.

## Opt in without rewriting old comparisons

`GatewayPlanner` remains the default in old CLI/H10 compositions. Its original system text
and `IntentPlan` output schema stay byte-equivalent. `RoutingGatewayPlanner` explicitly uses
`RoutingPlan` and a new prompt/schema. Its required `routing_version` is
`olist-intent-routing-v2`; it permits the four old routes plus `clarify` and `unsupported`.
This is a new candidate, not a measured quality improvement or an automatic promotion.

```python
from olist_support.workflow import RoutingGatewayPlanner, SupportWorkflow

# Supply an already authorized bounded gateway and pinned model route.
planner = RoutingGatewayPlanner(gateway, route)
workflow = SupportWorkflow(store, planner)
```

The shared gateway still owns admission, one-attempt controls, receipts, deadlines and
provider accounting. The planner creates no transport/credential or additional calls.
It still exports text only, removes tools and bounds output by min(run-token-budget,512).
The new parser rejects duplicate JSON keys, extra authority fields, missing/wrong routing
version, non-integer money, and money on any non-refund route. Failure keeps its explicit
failure code and falls back to the existing safe review plan, not to a second model call.

The graph reads the scoped order and verifies snapshot identity before routing. A `clarify`
plan returns `review_required/request_needs_clarification` with a fixed clarification message.
An `unsupported` plan returns `review_required/unsupported_request`; neither constructs a
refund proposal or enters commit. Generic review/transport failure remain distinct. Status
continues to report recorded source status; reship still requires inventory/shipping review.
Refund still passes the unchanged independent policy/store cap and authorization checks.

`IntentDecision` accepts the legacy or v2 plan and roundtrips the version marker through
durable checkpoints. Redelivery of the same business event returns its saved result without
replanning; switching planner versions does not authorize reinterpreting a completed event.
Future candidate studies need new pinned schedules/event identities and explicit composition.
The old H10 evaluator's PolicyCases remain refund/reship-specific; this candidate is not
silently wired into those old studies or their field denominators. A versioned wider study
adapter still needs reference membership, state observations and H10 binding before capture.

Rollback boundary: a v1-only binary cannot parse a saved v2 plan with its required version
marker. Preserving legacy requests is not bidirectional checkpoint compatibility. Before
enabling v2 in a deployment, verify rollback using a build that can read both contracts, or
keep v2 events on a separately pinned compatible worker and drain them before reverting.
Do not strip the marker, reinterpret completed events or restore older data over new state.
An old-parser refusal test makes this limit explicit; no cross-version migration is claimed.

## Strengthen numeric and reship references without manufacturing truth

`routing_reference.RoutingReference` stores authored development text, expected v2 route,
provenance and an optional exact amount span. For numeric refunds the span must be a whole
two-decimal SIM token, within text bounds, and equal integer minor units without floating
point. It rejects wrong-currency tokens, truncated/embedded/negative numbers, off-by-one
amount labels and missing spans. Amount0 and100.01SIM may be valid extraction references
while remaining ineligible for automatic full refund. Interpretation and action policy
have different validity rules.

Invented witnesses cover three explicit replacement phrasings and six amount values:
0.00,0.01,1.00,99.99,100.00,100.01SIM. They are authored mechanism/development references,
not an independently annotated real-language evaluation or new independent source families.
Exact transcription can be checked by code; selecting a semantically relevant amount span
still needs applicable reference evidence. `semantic_gold_validated` and `release_allowed`
are fixed false. The ABCD draft still supplies no explicit reship or numeric-amount gold.

## Verification and next evidence

Focused tests run the real graph on invented outputs, preserve legacy prompt/schema, test
both supported and new routes, roundtrip v2 decisions and forbid planning on duplicate
delivery. SQL tests close/reopen the real saver and independently compare complete order,
refund-ledger and run-budget state before/after new non-action routes. Checkpoint/session
metadata may change; business effects must not. Hosted final evidence is recorded on the PR.

The initial new test expected512outputtokens despite an invented run budget of100. The
planner correctly reserved min(100,512); correct that test to assert the bound, not enlarge
the budget. No provider call or retry occurred. Existing captures/references remain intact.

Next: review wider reference applicability, create a separately versioned routing/state
evaluation population including unsupported/status/clarification and known reship/amount
witnesses, freeze candidate/protocol/baselines/resource limits, then authorize the bounded
model comparison. Model behavior is unmeasured until those actual outputs exist.
