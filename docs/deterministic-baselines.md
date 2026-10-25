# Executed deterministic comparators

Inspected base: #105 merge `1f7c3efa766c9002d795095d97f84b7312c0797f`.
This extension on `codex/deterministic-release-baselines` prepares #33/#38/#45.
It fixes a comparison gap: H10 fresh evidence requires a dispatch receipt per trial,
whereas a deterministic rules/review/abstain algorithm should make no model call.

## Evidence types and trust boundary

[`baseline_recording.py`](../harness/src/agent_harness/baseline_recording.py) defines a
separate `BaselineManifest` with origin=deterministic, algorithm, candidate/source pins,
execution identity, capture interval and sealed batch hash. It is not an EvidenceManifest.
`record_baseline` verifies the domain factory and current source bytes before creating an
exclusive output directory, then runs three sequential isolated H6 trials. Every context
must be explicitly offline and bound to the baseline's candidate/code/lock/currency.
Parent timing includes setup, execution and cleanup just as it does for fresh candidates.
Existing positive context budget limits remain unused; zero model usage is observed in the
closed composition rather than represented by an invalid zero-valued Budget.

`GuardFactory` replaces the factory's gateway with `DenyModels`. Its mutable attempted flag
survives a delegate catching the denial exception. `GuardAgent` rejects such an attempt and
requires exact zero calls, input/output tokens and cost in the returned typed result.
This checks the gateway contract, not all OS networking. Trusted factories/algorithms must
not create separate transports or other side effects. The domain algorithms below neither
load credentials nor receive evaluator labels as input.

`read_baseline` requires external manifest and candidate pins, canonical manifest bytes,
matching sealed journal, complete observed reports, no execution/cleanup errors, parent
timing and zero usage. Provider receipts and unexpected root artifacts are rejected. A
failed recording remains saved and unverified; an exception does not turn it into a pass.
Use the domain reader next: generic read-back alone does not recompute domain field scores
or verify currently installed domain resources. Private manifests/journals/observations can
contain source inputs and must stay outside Git and public reports. Pins bind integrity;
they do not authenticate a human reviewer or attest independent execution against a malicious
trusted factory. Readers require the matching frozen source environment.

## Domain algorithms and execution paths

| Domain | Algorithm | Actual execution | Remaining limits |
| --- | --- | --- | --- |
| Olist | Existing template-aware RulesPlanner or always-review | Real scoped workflow, policy, SQL, independent fields, duplicate delivery and optional controlled recovery | Rules are grammar-aware; always-review earns no eligible completion. No unseen-language claim |
| CFPB | Always-review | Narrative-only typed input to a Decision with no prediction/attempts; separate field recomputation | No product/issue/risk inference. Missing privacy and durable state stay scorer errors |
| Revenue | Existing original-span abstention | Context/question to declared unsupported claim, source-hash/literal validation and separate reference-relative scores | No supported spans, legal meaning, numeric billing or business-state credit |

[`OlistBaselineFactory`](../projects/olist-support/src/olist_support/baseline_recording.py)
binds the selected algorithm into the behavior fingerprint. Its BaselineAgent overrides only
the planner constructor; OlistAgent's workflow, observation capture, independent SQL scorer,
recovery and redelivery paths are shared. DeterministicPlanner adds explicit zero usage to
the observed decision. `read_olist_baseline` validates the full installed source inventory,
algorithm and frozen behavior, then recomputes every private observation with the same oracle.
Controlled after-commit exception/reopen remains distinct from the separately recorded hard
process-death drills introduced in #104/#105.

For CFPB/Revenue,
[`DomainBaselineFactory`](../harness/src/agent_harness/domain_recording.py) binds each adapter's
fixed algorithm hash, full source inventory, configuration and scorer. BaselineDomainAgent
receives only the public input, saves its actual typed observation and returns the adapter's
normal result projection. The existing DomainScorer and domain observation reader recompute
all fields; absent evidence remains an error. `record_domain_baseline`/`read_domain_baseline`
wrap the shared recorder/reader with those checks. This does not train or fit a classifier.

## Comparison without promotion

`assemble_study` and `verify_binding` accept either an already verified H10 baseline or an
already verified deterministic baseline, only in the baseline position. Both still require
the same sealed population, original split/group identity, scorer/policy/environment/lock,
case/trial inventory and observed results. `assemble_olist_study` selects the deterministic
domain reader when explicitly given `baseline_route`; the candidate always goes through the
fresh Olist evidence reader. The route is a pinned configuration input, never a dispatch in
the deterministic path. A deterministic baseline passed as candidate is explicitly rejected.

This removes the need to fabricate receipts for deterministic comparison. It does not
approve the comparator, thresholds, cohort or release. Reviews remain separate inputs.
The existing H10 release entry points explicitly require their reviewed dispatch-evidence
format and reject the new deterministic format. Extending release promotion would require
an explicit approval/gate design, not silently widening this analysis API. Partial CFPB/
Revenue fields still prevent a complete profile study. Unknown provider cost is never
replaced with zero because the baseline's cost is known to be zero.

The [comparison guidance](https://langfuse.com/docs/evaluation/experiments/compare-experiments)
requires comparable datasets/evaluators and explicit baseline approval. Repeated deterministic
trials verify isolation and lifecycle behavior; they are not three independent samples or
stochastic quality estimates. Same-population pairing does not establish causality when
other conditions change. Historical captures, labels, holdouts and proposed thresholds stay
unchanged; no new provider calls are part of this extension.

## Reproduce and explain

```powershell
uv run --locked --all-packages python -m pytest tests/test_deterministic_baselines.py tests/test_evaluation_study.py -q
uv run --locked --all-packages python -m pytest tests/integration/test_olist_baselines.py -q -o "addopts=--strict-config --strict-markers"
```

The invented SQL drill runs the actual baseline through three owned databases, checks exact
field scores and database removal, and pairs it with a separately receipted mock candidate.
That is a composition test, not an independent quality experiment. Final exact-tree hosted
acceptance is recorded on the review PR. Explain why making a fake provider call would spoil
the baseline's cost comparison, why a swallowed denial still fails, and why passing this
comparison API cannot qualify a deterministic artifact as fresh candidate evidence.
