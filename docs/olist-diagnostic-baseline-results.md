# Routing baseline results on the authored Olist development pack

Continue from merged1a14f19 (#145). This is a separate zero-provider routing experiment,
using the24exposed authored texts prepared earlier. Three repetitions are repeated
executions, not72independent language examples. The18declared groups are not independently
sampled customer populations. No language qualification, service completion or release follows.

## Observed result

| Variant | Scheduled | Observed | Missing | Output routes | Exact intent/amount matches |
|---|---:|---:|---:|---|---:|
| Existing template rules |72|72|0|72review|0/72|
| Existing always-review |72|72|0|72review|0/72|
| Candidate model |72|0|72|Unknown|Unknown|

Both unchanged baselines abstain on this wording. RulesPlanner recognizes specific
`Primary request:` templates, whereas this pack uses ordinary authored questions and
commands. Falling back to review can be an appropriate operational precaution; it does
not correctly identify the more specific declared six-route language target. The pack
contains no expected `review` intent, although several cases require downstream review.
Required-review behavior is distinct from matching a semantic route such as `clarify`.

The zero score therefore establishes a narrow weakness in these baselines for this pack.
It does not establish candidate superiority, customer completion, operational review burden,
or production error rates. Always-review remains a useful operational safety floor, but
these two identical routing outputs are a weak benchmark for demonstrating model quality.
Keep their results and add a separately specified stronger routing baseline in future
development; do not retune this captured run or its expected answers after observing results.

No SQL, business guard, customer confirmation or reviewer interaction was run. Proposed
commands, unsafe effects, disclosure, actual review, completion, clarification follow-up and
recovery remain unknown across these rows. Zero provider usage is observed for each decision;
machine/runtime cost is not measured. Planner-only elapsed time is captured separately and
not passed off as end-to-end latency or complete stage coverage.

## Evidence and reproduction

The unchanged `DeterministicPlanner` receives only WorkflowRequest and neutral RunContext,
not the reference answers. Its legacy IntentPlan is projected field-for-field into the
explicit v2diagnostic schema; `review` is not reinterpreted as `unsupported` or `clarify`.
The runner pins selected source files and the lock before execution and checks them again
afterward. It constructs no gateway. Socket connection and DNS APIs are denied during the
planner loop; zero such attempts occurred. This is an execution guard, not an OS egress
sandbox or a proof that arbitrary malicious source code could not bypass Python hooks.

Run the checked-in reproduction script from the locked checkout, using new private output:

```powershell
uv run --locked --all-packages --link-mode copy python docs/evaluation/run_olist_diagnostic_baselines.py --packet <prepared-private-directory> --output <new-private-directory>
uv run --locked --all-packages --link-mode copy python docs/evaluation/read_olist_diagnostic_baselines.py --packet <prepared-private-directory> --run <saved-run> --manifest-sha256 <separately-held-manifest-hash>
```

Use normal Python without `-O`: these research scripts use assertions for refusal checks.
They are local reproduction tools, not hostile-upload validation endpoints. Inputs and all
results remain in the private output; publish only counts and hashes. The complete manifest
is written last. An existing output refuses; a partial run cannot claim completion.

Separate readback validates artifact/packet/source hashes, context/request/decision/output
bindings, zero model usage and the full144slot baseline inventory, then recomputes all
diagnostic metrics. It verifies the reported capture against an externally held manifest
pin. This does not authenticate independent real-world language judgments, a trusted host's
honesty or every transitive imported source byte. Selected source pins and uv.lock are the
recorded boundary; this is not a fully qualified frozen host/provider protocol.

The v1run failed before decisions because shared Budget contracts require positive call/
token limits. Its partial files remain preserved. The separate v2run uses the schema-minimum
1/1context values, no provider gateway and zero actual usage. Those fields grant no provider
permission. The first readback attempted Python-object validation of persisted JSON dates/
decimals and failed; correcting the reader to use strict JSON loaders reproduced the
unchanged captured rows. Sandbox access to new private files required read-only elevation.

Raw capture manifest SHA-256:
`2444dee6b50ab7e6f69ecff43411a72ebc8a5bdeb4c3b9b79bc8f83ba5d5ac83`.
The [public aggregate](data/olist-diagnostic-baseline-routing-v2.json) records counts, source
and report pins without raw run identifiers or private request/response records.

## What remains

The references remain exposed AI-authored development proposals. Preserve the limitations
in [expanded evaluation](olist-expanded-evaluation.md) and the source-applicability findings.
Independent reference evidence and a separately qualified language evaluator remain needed
before qualification. Seventy-two model slots are still missing. The expired/stopped provider
study is not resumed, and old bound slots are not reused. A new bounded model run requires
its own exact model/request/environment freeze, readiness and allocation approval.

This routing-only experiment does not replace the earlier108whole-service development
baseline captures. Their fixtures, policy/actor scripts, outcomes and historical failures
remain separate. No qualification or production release gate is closed by these results.

Five negative readback probes on separate copies were refused: missing row, changed
prediction, invented effect, forged report and wrong external manifest pin. Both reproduction
scripts are included in the normal developer lint/format source list. Existing root runtime
and frozen package source inventories remain unchanged by this evidence publication.
