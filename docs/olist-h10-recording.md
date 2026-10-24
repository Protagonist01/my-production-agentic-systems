# Olist H10 recording adapter

This adapter connects the real Olist SIM workflow to the shared H10 recorder. It prepares
fresh restricted databases, records new model dispatches, checks the actual SQL state and
preserves private observations for offline recomputation. This is infrastructure for #33;
it does not complete the Olist release study or authorize a provider run.

## Input and evaluator boundaries

`h10_manifest.manifest_for` encodes existing PolicyCases without changing their labels.
AgentInput contains only the unchanged request text. Source facts, expected intent/action/
amount/reason, reviewer provenance and source pins remain evaluator-only. The original
source group is retained. H10 supports two splits: original regression cases map to
development and retain their original split in private metadata; holdout stays holdout.
Different source kinds require separate manifests because one source reference cannot
ambiguously claim two kinds. Freeze and review the resulting manifest byte pin separately.

The parent `OlistEnvironment` creates/enrolls each disposable database and records its
before-state. Workers receive `TrialDatabaseAccess`, a scoped caller grant and the controlled
fixture configuration. They receive no administrator password or expected action. H10
reaps workers before parent-owned cleanup. Failed cleanup remains an error with retained
state; an agent cannot claim successful cleanup.

## Recording and read-back

Use `h10_recording.record_olist` with an already loaded/pinned manifest, complete three-trial
schedule, explicit OlistFreshFactory, isolated environment, new output path, candidate pin
and source root. The candidate inventory must match all executing harness/Olist Python and
SQL bytes and the lock. `h10_config.fingerprints` supplies prompt/route/tool/policy/scorer/
environment fingerprints to freeze before execution. This computes pins, not approval.

The factory requires an explicit transport and admission policy. Mock captures retain mock
origin and cannot qualify release. Provider composition requires the existing Gemini
transport and the separately pinned original Olist database; original-view provenance and
declared edits are rechecked before execution. No key file is loaded automatically.
Authorization of a new provider budget is a separate prerequisite, not a consequence of
calling a constructor or accepting labels.

Each trial runs the workflow, then redelivers its durable business event with a planner that
refuses another model dispatch. Selected recovery cases inject a controlled exception after
commit and reopen the store/checkpointer before resuming. This is explicitly not an OS kill
or complete H7 fault-plan study. Missing requested interruption or changed duplicate state
cannot earn completion credit.

H10 owns receipt writing before model responses reach the agent, journal sealing, usage
reconciliation and source checks. The Olist scorer independently reads final SQL, compares
the eight domain fields and saves its canonical private observation. Each field score binds
the observation digest; the H10 batch pin binds those references. Keep the entire output
private: it contains source facts, evaluator labels, workflow messages and model receipts.

The domain reader verifies the H10 evidence, exact observation inventory/digests and the
executing scorer, then recomputes shared results and domain scores offline. Missing/changed/
extra observations or divergent scores fail. Unknown provider cost remains unknown and
blocks H10 evidence verification. No retry is used to replace an unresolved trial.

Use `h10_evidence.read_olist_evidence` with the independently pinned evidence/candidate
digests and original loaded manifest. Observations are stored at
`observations/<context-pin>.json`; the shared journal and dispatch receipts retain their
normal H10 paths. Use the frozen candidate's installed package bytes for recomputation.
Duplicate delivery retains both its before-state and redelivered result, so a passing
boolean alone is insufficient. Recovery is explicitly N/A on ordinary trials; its binary
projection is not a claim that an interruption occurred in those trials.

This is trusted Python evaluation code, not an OS sandbox or authenticated SQL attestation.
H10's evaluator process has private labels; its closed AgentInput projection prevents
accidental forwarding but cannot contain malicious Python introspection. The adapter does
not yet produce a complete methodology study. New shared trial rows retain
[parent-measured trial timing](trial-timing.md), including setup and cleanup. Historical
rows without that measurement retain unknown latency.
If a worker dies before scoring, its missing report/observation remains unverified and
cannot pass this reader; this adapter does not recover a complete forensic state archive
from every OS crash.

## Verification and remaining release work

The executable recipe is `tests/integration/test_olist_h10.py`, using invented cases and an
in-process mock transport inside actual spawned H10 workers with real restricted Postgres.
It covers refund, required review, controlled recovery, failed attempt and unknown cost.
Unit tests mutate public/private label binding, route/source pins, actual SQL state, shared
result claims and required recovery. These are mechanism checks, not model-quality results.

```powershell
uv run --locked --all-packages python -m pytest tests/test_olist_h10.py tests/test_olist_fields.py -q
uv run --locked --all-packages python -m pytest tests/integration/test_olist_h10.py -o "addopts=--strict-config --strict-markers" -q
python dev.py check
```

The twelve stronger draft labels remain accepted AI-assisted propositions. Representative
coverage, independent review, approved baselines/thresholds, complete latency/call/token/cost
accounting, final-candidate fresh evidence and the bound methodology audit remain required.
Historical recordings/holdouts remain unchanged. No deployment, real payment or shipping
effect is authorized. [Shared standards](evaluation-standards.md) apply to all five agents;
[stronger draft](olist-strong-draft.md) records the current cohort limitations.
