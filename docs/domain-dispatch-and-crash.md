# Partial domain dispatch and process-death evidence

This is preparation for #33, #38 and #45. Every reader keeps release approval false.
No provider budget, new source cohort or reviewed baseline is created by these adapters.

## CFPB and Revenue recording

[`domain_recording.py`](../harness/src/agent_harness/domain_recording.py) supplies the shared
mock-only composition. `record_domain` verifies the complete harness/domain Python and SQL
inventory, environment lock, configuration, scorer and synthetic response recipe before
creating output. It then uses the existing H10 worker and receipt gateway. Each dispatch
has a new nonce; transport responses and zero token/cost amounts are explicitly invented.
Unknown usage still blocks read-back. No credentials or provider transport are loaded.

[`CfpbAdapter`](../projects/cfpb-triage/src/cfpb_triage/h10_recording.py) invokes the actual
typed classifier with narrative-only input. Private product, issue, risk and ambiguity
references remain in the evaluator manifest. Regression membership is preserved in slices
even though the shared manifest groups it with development. The independent existing
evaluation checks prediction validity and required routing, rather than trusting the
classifier's claim that its decision is correct.

[`RevenueAdapter`](../projects/revenue-integrity/src/revenue_integrity/h10_recording.py)
invokes the actual gateway extractor with context and question. Source hash and literal
Unicode spans are checked against the separate reference. Undefined precision or recall
does not become 1.0. This tests literal extraction; it establishes no legal interpretation,
numeric-term support or billing correction quality.

`DomainScorer` saves a private canonical observation in `observations/<context-pin>.json`.
Its digest is part of sealed score evidence. `read_domain` verifies H10 pins and receipts,
requires the currently installed source inventory, checks exact sidecar membership, and
recomputes both the full result and field scores. Changed, missing, extra and symlinked
observations fail. A reader and trusted recorder are still required; a digest is integrity
binding, not independent attestation. Sidecars can contain narrative/context and must stay
outside Git/publication. Installed read-back requires the matching frozen source environment.

CFPB privacy and durable reviewer state, and Revenue supported terms, reconciliation,
authorization and business recovery are unobserved. They emit scorer errors, leaving the
batch incomplete. Preview references are not durable reviews. Safety is unmeasured. These
partial stateless mock captures cannot qualify either complete release profile.

## Olist operator-selected crash drill

[`crash_evidence.py`](../projects/olist-support/src/olist_support/crash_evidence.py) accepts
only an offline Olist context and the controlled SIM grant. The shared context schema requires a positive budget; this drill never consumes it or receives a model gateway.
`collect_crash` checks fresh before-state, spawns one owned process and hard-exits it with
code 23 at the workflow's after-commit boundary. The parent observes the boundary and exit,
reads SQL independently, then restarts with a new store/checkpointer and `NoSecondDispatch`.
It reads SQL after restart and again after duplicate delivery. No model chooses this refund.

The caller owns the disposable database. Release it after return or an ordinary failure;
on `WorkerCleanupError`, preserve state because a live worker may remain. Startup, timeout,
unobserved boundary and restart errors remain failures. No unrelated process is terminated.
`read_crash` checks an externally retained byte pin and canonical single-file inventory,
then uses the independent label/state oracle after database deletion. It checks exact
committed/restarted/duplicate state, original operation receipt and duplicate result identity.
The current installed oracle is trusted; this artifact is not a complete H10 source-pinned
quality study. One after-commit process death does not establish the complete fault matrix.

## Reproduce mechanism checks

```powershell
uv run --locked --all-packages python -m pytest tests/test_domain_recording.py -q
uv run --locked --all-packages python -m pytest tests/integration/test_olist_crash_evidence.py -q -o "addopts=--strict-config --strict-markers"
python dev.py check
```

Use only invented inputs for these tests. Final measured local and hosted results belong
on the review PR; neither passing infrastructure tests nor merging code approves release.

Main CI after #103 exposed a faulty timing-tamper test: it altered and re-sealed the batch,
then depended on a real receipt span being positive. The correction retains the original
batch seal when changing timing. Production duration checks and limits are unchanged.

Study exercise: trace public input into the gateway and private reference into the scorer.
Explain why a verified mock receipt cannot prove model quality, and why a surviving receipt
after process death proves less than a complete recovery matrix.

The [durable-state extension](durable-state-evidence.md) adds separately saved CFPB queue and Revenue SIM ledger observations and a versioned Olist before-commit hard-exit scenario. Partial H10 adapters retain their unobserved-field errors; these artifacts cannot substitute for a complete bound release study.
