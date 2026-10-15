# Versioned cases and independent scorer registration

H5 #19 adds local evaluator infrastructure on `codex/h5-versioned-cases`, based on reviewed main e9ebd07 (H4 #74). [PR #75](https://github.com/Protagonist01/my-production-agentic-systems/pull/75) contains H5 for review; it remains unmerged. It loads a fixed, private population and binds explicitly registered scorer versions before any case runs. Domain database scorers, batch/trial reset and complete outcome accounting remain H6/domain work.

## Author and review a manifest

Use `agent_harness.cases.CaseManifest`. `case_ids` declares exact membership; `entries` contains each complete F2 `EvalCase` plus `group_id`, `split` (`development` or `holdout`) and `scorer_id`. Existing case fields preserve policy/scorer versions, source category/version, snapshot reference, risk/slices, fault definitions, expected labels, eligibility and hidden state. Snapshot descriptors declare reference, source category and source version. Every descriptor must be used; every case must match one.

Duplicate IDs, absent/unlisted IDs, absent required fields, extra fields, duplicate JSON keys and incompatible provenance fail. A group can have multiple paraphrases in one split but cannot cross development/holdout, even under different snapshot references. Assign groups from reviewed underlying order/complaint/template families before candidate outputs are examined. Consistent group strings do not prove the grouping is correct. This format does not implement temporal splitting or inspect raw source bytes.

Publish a new manifest version when changing membership, splits, labels, policy, scorer selection or provenance. Obtain `ManifestPin(manifest_id, version, sha256)` from independently reviewed configuration. Its SHA-256 covers the **exact file bytes**, including whitespace and line endings. Do not calculate a trusted pin from the incoming file during an evaluation. The loader reads once, checks that byte buffer, rejects duplicate keys, validates the complete population, and checks ID/version. Missing files or malformed JSON fail. A hash identifies reviewed content; it does not authenticate the author or establish ground truth.

[Invented fixture](../tests/fixtures/cases/invented-v1.json) uses manifest `invented-cases` / `v1`, snapshot `invented-text-v1`, source `synthetic` / `invented-v1`, policy `fake-text-policy-v1`, scorer `invented-state` / `invented-state-v1`. Its separately pinned digest is in [the acceptance tests](../tests/test_case_manifests.py). Test labels are invented contract checks and have no domain quality meaning.

## Compose trusted scorers

An application imports its own scorer and passes the instance to `ScorerRegistry.register(spec, implementation)`. The harness never imports a vertical, discovers entrypoints or executes module names from case data. A plugin implements the existing `Scorer.score(case, result) -> tuple[ScoreResult, ...]`. Its `ScorerSpec` declares ID/version and explicit compatible `(snapshot_ref, policy_version)` pairs. One pair does not authorize the cross product of other snapshot/policy pairs. Duplicate registration fails; different versions can coexist.

The application supplies read-only evidence readers to its scorer separately from the agent. For example, an invented state scorer can read `actual_states[case.case_id]`, compare it with `case.expected.expected_state_changes`, and emit a versioned score with a state evidence reference. It must not use a result's `outcome="completed"` or its claimed ledger references as proof that a write occurred. Real scorers must scope and resolve trusted store evidence, including tenant/trial identity, in the later domain integration.

Typical composition, after the application has provided a reviewed pin, context, agent, gateway and independent domain scorer:

```python
from pathlib import Path
from agent_harness.cases import load_manifest
from agent_harness.scorers import ScorerCompatibility, ScorerRegistry, ScorerSpec

loaded = load_manifest(Path("private/cases-v1.json"), reviewed_pin)
registry = ScorerRegistry()
registry.register(
    ScorerSpec(
        scorer_id="order-state", version="order-state-v1",
        compatible=(ScorerCompatibility(
            snapshot_ref="orders-v1", policy_version="refund-policy-v1",
        ),),
    ),
    independent_order_scorer,
)
bound = registry.bind(loaded)  # Validate ALL case bindings before any dispatch.
report = bound.run_case(context, "order-case-1", agent, gateway)
```

This is an application composition fragment, not a working Olist scorer or a new CLI command. Missing registration/version or incompatible snapshot/policy fails at `bind`, including on a case later in the population. Bind captures the registrations; adding a new registry version afterward does not switch the selected version. Registry setup is single-threaded; plugin objects and their state readers remain trusted and may need their own concurrency controls.

## Execute and retain evidence

`BoundEvaluation.run_case` selects an exact manifest case, rechecks scorer compatibility and delegates to F2 `run_case`. Context case/snapshot/policy mismatches fail before agent dispatch. The agent receives only a copied `AgentInput` and public `RunContext`. Group, split, scorer selection, expected labels, eligibility and hidden outcomes stay on the evaluator side. These fields remain private by structure, not by process isolation; reviewed public text/references must also be free of embedded answers.

The scorer receives detached private case/result copies. Empty/duplicate metrics or a returned scorer version differing from registration fails. Scorer exceptions propagate. A typed scorer failure remains a score row with no numeric/category value; it cannot become a pass. H6 must account for these failures across every scheduled trial. A `ScoreResult.eligible` field belongs to that metric's declared denominator; H5 does not force every metric to use autonomous eligibility.

`ManifestCaseReport` wraps the existing `CaseReport` with the reviewed manifest pin, group/split and scorer ID. The nested report retains scorer/policy/source versions, public candidate provenance, result and scores. It does not add private expected/hidden fields. Trusted plugins can emit sensitive evidence strings, so their output still needs review before export. This wrapper changes no model wire, replay fixture, operational database or existing F2 report schema.

`LoadedManifest` stores canonical private JSON and returns fresh validated copies. This costs whole-population parsing on access, appropriate for this first small local population API; large populations need an indexed immutable representation. Private Python attributes and scorer instances are not security sandboxes. Manifest files are trusted reviewed configuration with no hostile-file size/resource isolation.

## Verify the boundary

```powershell
uv run --locked --all-packages python -m pytest tests/test_case_manifests.py -q
python dev.py check
python dev.py build
```

The acceptance tests deny network for the checked-in fixture and exercise missing/duplicate membership, source mismatch, split leakage, byte pins, duplicate keys, one-read loading, copied nested values, all-case registration preflight, result/context identity and invalid scorer output. Identical completed claims/forged state references receive 1 or 0 according to independently supplied invented stored state; absent state scores 0. Mutating private answers/eligibility changes only scorer-visible data. No live provider, database, Langfuse dataset mutation or judged experiment is required.

Design references: [Langfuse datasets](https://langfuse.com/academy/datasets) and [evaluator guidance](https://langfuse.com/academy/evaluate/writing-evaluators), read 2026-10-15. The project’s [declared metrics and release gates](project-management.md#headline-metrics-and-release-gates) remain the product evaluation plan. H5 adds no new quality floor or experiment claim.
