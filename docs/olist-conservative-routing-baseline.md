# A stronger conservative development routing baseline

This follows [the unchanged baseline experiment](olist-diagnostic-baseline-results.md).
The new root module `olist_routing_baseline.py` has its own version,
`olist-conservative-rules-v1`. It changes neither captured old algorithms/results nor the
default application composition. It is a comparator for development, not refund authority.

## Behavior and execution

`interpret(text)` returns a typed RoutingPlan and a fixed reason code. ConservativePlanner
implements the existing planner interface, preserving run identity and zero model usage.
It accepts no reference labels, database connection, gateway, order facts or consent.
The rules are visible, deliberately narrow and openly developed after seeing this pack.

Rules run in this order:

1. Explicit private/cross-account requests become unsupported.
2. Quoted material and instruction/execution pressure abstain to review.
3. Recognize only a whole do-not-refund clause; unknown negation scope becomes clarify.
4. Unrelated/mixed requests, existing-refund status and conflicting route features are
   distinguished before selecting order status, replacement or refund.
5. A refund amount must be an adjacent exact decimal SIM expression after a refund/return/
   reimburse verb. A separately recognized paid/payment phrase cannot supply that amount.
   Multiple, malformed, unexplained or oversized amounts become clarify. No numeric amount
   is emitted when the declared refund grammar has no numerical expression.

For example, `I paid 123.45 SIM; refund 6.78 SIM` extracts678minor units. A requested101.00
SIM remains10100; this parser does not silently cap it or decide eligibility. Policy, actor
scope, reviewer/customer confirmation and commit guards remain separate application steps.
An interpreted refund or a review route does not create a command, approval or payment.

## Measured development results

The separate capture uses the same24authored cases and3repetitions as the earlier pack,
with a new single-variant plan. Original source-plan and new-plan hashes are retained.

| Comparator | Exact route/amount matches | Distinct authored cases correct in all3trials |
|---|---:|---:|
| Unchanged template rules, earlier capture |0/72|0/24|
| Unchanged always-review, earlier capture |0/72|0/24|
| New conservative rules v1 |54/72(75%)|18/24|

Six cases differ from the declared reference in every repetition: override, quote, cap,
consent, repeat and noise. All six returnreviewbecause of quotation or instruction/execution
pressure. Those are interpretation mismatches in this benchmark even when abstention is
an understandable operational precaution. Do not relabel them after observing this score.

Per-intent recall is refund50%, status60%, unsupported87.5%, clarify100%and reship100%on
this small exposed pack. Precision among emitted non-review routes is100%here; that is not
a population precision estimate. Review has no correct reference support in this pack.
The new score is below the proposed95%planning target and is not qualification evidence.

Seventy-two repeated decisions are only24different authored texts, with dependent declared
groups. The comparator was developed with this pack visible. The difference from the old
template comparator is useful development feedback, not an unbiased improvement estimate,
confidence bound or evidence of model superiority. No candidate model calls were made.

## Capture and verification

```powershell
uv run --locked --all-packages --link-mode copy python docs/evaluation/olist_conservative_experiment.py --packet <prepared-private-directory> --output <new-private-directory>
uv run --locked --all-packages --link-mode copy python docs/evaluation/olist_conservative_experiment.py --packet <prepared-private-directory> --output <saved-run> --verify-manifest <separately-held-hash>
```

The runner creates a fresh output exclusively, pins selected source/packet bytes, and denies
socket/DNS calls while executing the unchanged frozen version of this new baseline. It
preserves partial records on failure and writes the complete manifest last. Raw contexts,
requests and decisions remain private. No SQL or provider gateway exists in this composition.
The shared schema's minimum1/1call/token budget fields are not provider authorization;
actual usage is zero. The network guard is Python-level, not an OS egress sandbox.

Separate readback execution validates the external manifest pin, packet/source/artifact
hashes, distinct plan identities, requests, context/run identity, raw decisions and the full
72slot inventory. It then recomputes report metrics. Normal Python assertions are required;
the command refuses `-O`. These are local research tools, not hostile-upload endpoints or
proof of a trusted host's honesty. Pins cover selected files, not all transitive runtime bytes.

Raw capture manifest SHA-256:
`2186581d93bca20568bd7baef318a9cc04f32f65b68e93689726439329fb7563`.
The [aggregate](data/olist-conservative-routing-v1.json) exposes counts, fixed reason codes,
case identifiers and source hashes. Full raw records remain outside Git.

## Limits and the next evidence

This is a lexical English comparator, not a qualified natural-language interpreter. It
does not resolve arbitrary quotation, sarcasm, hypothetical requests, indirect speech,
negation scope, multilingual text, money roles or consent meaning. A keyword can appear
in a mention rather than an action request. Unseen synonyms and common phrasings may
abstain or misroute. The tests and development score cannot establish independent truth.
Explicitly retain [the natural-language reference limitations](olist-expanded-evaluation.md).

All raw operational outcome fields remain unknown: actual review, proposals, disclosure,
unsafe effect, completion, clarification follow-up and recovery were not observed. Composite
completion metrics may fail a semantic prerequisite when a route is wrong; that is not a
measured business-state outcome. No end-to-end latency, machine cost or performance claim.

Before qualification, specify and freeze the intended abstention policy independently,
retain mismatches and test a fixed selected comparator on genuinely unexposed, applicable
language references. Meaning evidence and amount-role ambiguity still need applicable
external annotations or a separately qualified evaluator under the accepted evidence-method
design. Model agreement alone cannot supply that evidence. The original stopped/expired
allowance remains untouched; a new candidate run needs its exact freeze and allocation.
No release gate is closed by this implementation or development result.
