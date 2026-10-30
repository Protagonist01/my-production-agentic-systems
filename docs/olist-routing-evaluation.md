# Wider Olist routing and state evaluation

Prepared 2026-10-30 against main `69b6a3f`, for #33. This is a development adapter and
protocol draft. No live model call, new allowance, hosting purchase or release approval.

## What is implemented

The old H10 adapter stays unchanged in scope: its labels describe refund/reship policy
cases. The new `routing_evaluation.RoutingCase` keeps the accepted interpretation reference,
source provenance, group/family/split, trusted SIM fixture and literal expected workflow
outcome/reason separate. It represents refund, recorded-order status, reship, review,
clarification and unsupported requests without inventing a refund/reship label for them.

`RoutingPopulation` refuses duplicate IDs and source-group, declared-language-family or
fixture-order leakage across splits. `RoutingCase` checks scope and outcome consistency.
For refund/reship it checks the declared effect against the separate structured SIM policy
table. That is conditional policy validation, not certification of customer meaning.

`routing_h10.manifest_for` projects customer text into a closed `AgentInput`; reference
labels, expected amounts and trusted source facts stay evaluator-side. The private label
reader reconstructs and compares the full `EvalCase`, including expected disposition and
source/policy/scorer versions. A changed public input or hidden expectation refuses.

The owned SQL environment enrolls the frozen fixture and reads initial state with its
administrative observer. Workers receive restricted `OlistAccess`, not the administrator
credential. `RoutingAgent` reuses the real workflow, checkpoint saver, duplicate delivery
collector and controlled after-commit recovery path. Only the explicitly selected planner
changes. `RoutingScorer` independently reads final SQL state after the agent returns.

The existing independent state-delta constructor is factored into `release.expected_state`.
The old `_expected_state(PolicyCase, ...)` remains a wrapper with the same behavior. The
wider scorer supplies order, confirmation, expected effect and task directly. It never
fabricates a legacy intent or calls runtime `policy.propose` to generate an expected result.
Its permitted delta includes the exact receipt, operation payload, original-run budget,
order version and every unaffected row. A no-effect outcome must preserve business state.

## Metrics and denominators

These use the already accepted Olist evaluation fields; no new release threshold is activated.

| Field | Evidence | Missing or wrong evidence |
| --- | --- | --- |
| Intent / requested amount | Actual saved planner decision versus accepted development reference | Unknown stays unknown; wrong interpretation stays incorrect |
| Action / review reason | Actual workflow outcome and reason versus literal reference | Safe generic review does not become a successful refund or an exact clarification label |
| Truthful confirmation | Fixed recorded-status/review messages; a refund message must match the exact expected committed receipt | A foreign receipt or unsupported commitment claim cannot pass |
| Exact state | Independently expected complete order/ledger/run-budget snapshot | Missing state is unknown; extra, wrong or foreign effects fail |
| Duplicate delivery | Equal first/redelivered results and state snapshots, with no second planner invocation | A flag alone or a missing pre-redelivery snapshot is insufficient |
| Recovery | Actual committed/resumed snapshots, only for explicitly required refund recovery cases | Missing required evidence stays unknown; non-applicable cases are excluded from its denominator |

`correct` requires all applicable fields, no model/capture failure and a completed observation.
`routing_safe` combines observed state safety and truthful confirmation. A timeout routed to
review is not a successful model decision. The summary preserves every scheduled variant ×
case × trial, including missing variants, unknown fields and unresolved attempts. It refuses
duplicate/foreign rows, missing required recovery disguised as correct, and wrong pins.

Parent-owned H10 timing includes setup, worker execution and cleanup. Its observed p95 is a
trial-resource measurement; it does **not** assess the accepted client-facing API/model
latency SLO. Missing timing counts are explicit and operational latency assessment stays false.
Underlying H10 journals retain usage, receipts and unknown monetary costs; this field summary
does not manufacture billing evidence or infer zero cost from a Free label.

## Four explicit comparators

| Variant | Behavior | Interpretation of results |
| --- | --- | --- |
| `candidate` | Opt-in v2 prompt and versioned schema | Development reference agreement; no model-quality result until actual evaluation |
| `legacy` | Original v1 prompt/schema on the same text and fixture | Cannot express the two new fine labels, but safe coarse review can still be observed |
| `rules` | Existing declared template-aware rules, without labels/source facts | Reports its limited template coverage honestly |
| `always-review` | Deterministic review, without model access | Useful safety/review-load comparator; never eligible refund completion |

Both model variants currently have **mock-only factories**. Live routes, provider origin
overrides and provider-control pins are refused. They create genuine H10 mock exchange
receipts, labeled mock. Deterministic comparators use the shared baseline recorder and
`DenyModels`: zero actual model calls, zero usage and no provider receipts. No result is
converted between these evidence origins.

Each variant has a distinct candidate pin. Fingerprints bind variant, prompt/schema, rules,
state/scorer implementation, environment and complete executable source inventory. Wrapper
entrypoints check source groups/splits, loaded population and environment identity before
recording. Domain readers first verify shared H10/baseline evidence, then reparse canonical
private observations and recompute every score. Missing, altered, symlinked or extra
observation files refuse. These checks establish consistency of trusted captured evidence;
they do not authenticate publisher labels or attest freshness when called on arbitrary rows.

## Accepted development fixture draft

The owner accepted using the [12-case development draft](data/olist-routing-evaluation-draft-v1.json).
The private packet is `routing-evaluation-draft-2026-10-30-v1` under the existing Olist cache.
It contains the 12 accepted ABCD texts and corrected mappings, paired by index with the old
frozen Olist/SIM draft's order views and fictional confirmations. **These are arbitrary
constructed test associations, not actual customer/order links.** Original files remain intact.

There are three expected conditional SIM refunds, two recorded-status replies and seven
reviews, in six reused order groups and four manually declared subflow families. All are
development cases. No independence, fresh holdout or representative traffic claim is made.
The packet has zero explicit reship, numeric-request, recovery or injection cases. Constructed
unit witnesses for some of those dimensions remain separate; they do not fill external-gold
or release-cohort coverage requirements. Schema-valid references are not semantic gold.

The owner accepted this fixture construction for development only. Its acceptance sidecar
binds exact population and lineage bytes. Original ABCD annotations, earlier proposed labels,
owner acceptances and failed studies are preserved. Source facts and references never enter
the model projection. No data has been uploaded to Langfuse or another provider.

## Protocol draft and preflight

`RoutingProtocol` binds the canonical population pin, the **actual serialized manifest byte
pin**, four distinct candidate pins and three distinct trial IDs. Manifest file bytes may
differ from a model's canonical serialization, so the two pins are deliberately separate.
The protocol is explicitly development-only and cannot be marked frozen for provider use
or qualified for release. For this 12-case draft its complete schedule would be:

- 36 v2 and 36 legacy model-route trials;
- 36 rules and 36 always-review zero-call trials;
- 144 total workflow trials, with repetitions counted separately from source groups.

Those are planning counts, not executed observations or funding. Source/candidate/protocol
pins must be prepared on a clean final commit. Provider authorization and durable budget
integration remain separate; the existing 51 unused Gemini slots are bound elsewhere.
No new provider-capable factory is activated here.

Before any live request, the frozen model payloads should pass actual SDK serialization and
the exact worker/gateway/receipt path under fake HTTP; representative invented canaries must
pass under an explicitly accepted scope. Preserve failures, count all reservations and stop
on the frozen conditions. Do not retry consumed requests, reinterpret old unused slots or
relax criteria after output. This follows the previously documented availability failures.

## Verification and limits

Focused tests cover all six routes, seeded wrong state/reason/amount/receipt, missing final
state and recovery, initial-state/identity forgery, metadata/split changes, live-route/origin
refusal and complete missing denominators. Legacy state/field/H10 unit checks run alongside
the new scorer. SQL tests exercise owned fresh recordings, all six workflow routes, recovery,
zero-call comparators, legacy coarse outcomes, cleanup and altered-observation read-back.

Local Docker Compose refused startup before all nine new SQL test bodies. Do not call that
a local SQL pass or skip the checks. Hosted PostgreSQL must run them before merge. Final
hosted results are recorded on the PR after actual completion.

Remaining for #33: broader applicable references and independent review evidence; a
representative, grouped cohort covering required risk/fault slices; reviewed sample size,
baselines and resource bounds; a frozen provider protocol and separate bounded allowance;
fresh candidate results and deployment/recovery acceptance. The active profiles, gates and
planning targets are unchanged.

Sources used for the design boundary: [Langfuse datasets](https://langfuse.com/docs/evaluation/experiments/datasets)
separates inputs, expected outputs and metadata; [score APIs](https://langfuse.com/docs/evaluation/evaluation-methods/scores-via-sdk)
allow independently computed scores to be attached to experiments. This implementation
uses local deterministic scoring and sealed H10 artifacts, without creating a live evaluator.
