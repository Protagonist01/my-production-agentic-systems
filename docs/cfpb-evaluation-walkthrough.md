# CFPB evaluation: architecture to code

Inspected branch: `codex/cfpb-evaluation-v2`, based on main163888e (#144), 2026-11-10.
Scope is the new CFPB workflow/tools and their shared package/auth boundaries. Other
agents, historical provider studies and production hosting are not re-audited here.
See [the operator/method chapter](cfpb-evaluation-v2.md) and Build Book Entry93.

## Follow a candidate

`scope_routing.route_v2` verifies case, narrative, taxonomy, policy and comparator mode
before dispatch. Narrative is only the untrusted user envelope. `_attempt` uses the bounded
gateway with no business tools or retry loop, parses `ScopeOutput` and locates unique
exact quotes through `ExtractedPrediction.locate`. Scope means one of financial complaint,
unrelated, insufficient, unsupported operation/advice or taxonomy gap. It is not account
authority. A non-complaint cannot masquerade as a routine financial complaint with null
category fields. A mixed complaint and injected instruction can retain its legitimate task.

For an invented routine complaint, cheap=.7 then strong=.9 at both gates=.8 uses two calls.
An elevated/ambiguous cheap result uses one and cannot be downgraded. Operational failure
does not trigger another model; scope disagreement waits. Default thresholds1.01 admit no
automatic classification/unrelated response. Exactness is independently checked; semantic
relevance still needs applicable reference evidence. Tests use invented gateways, not models.

## Follow a human work receipt

`evaluation_store.setup_evaluation` SHA-pins additive `cfpb_eval` DDL without changing v1.
Trusted import binds participant, family, arm and the private masking-review reference.
A manual assignment creates no model job. `evaluation_snapshot` hides candidates on the
server, and legacy APIs cannot read these separate cases. Explicit participant provisioning
is additional authority; an old reviewer account alone is insufficient.

`work` locks the case, checks participant/case/actor scope, binds an exact idempotent command
receipt, fences its revision and bounds active seconds inside an open server interval.
Review/correction/oversight are separate kinds. Correction pauses; acceptance finalizes
triage, not resolution of a consumer complaint. Visibility acknowledgement preserves the
revision so displaying a case cannot accidentally invalidate its in-flight candidate.
With an invented 30-second interval and20active seconds, a correction records20, not30.
A later10-second interval with5active seconds yields25total, with5seconds of additional
active work. Replaying an identical receipt adds nothing; changing its payload conflicts.

`claim_evaluation` locks the case before its job, matching publication's lock order.
`finish_evaluation` checks lease identity/expiry, case revision, final human work, content
pins and independently reconstructed quotes/prediction. A forged automatic answer must
still meet routing and comparator-mode rules. `evaluation_worker.step_evaluation` refuses
to redispatch expired claims: an earlier request may already have been consumed. Its CLI
default publishes unavailable/review without loading keys. Runtime SQL cannot delete events
or provision participants. The application still trusts runtime code/DB credentials; this
is not database row-level isolation against a compromised service process.

## Follow the measurements

`measurement.Profiler` uses fixed stage names, monotonic intervals and no payload/SQL/error
attributes. API/worker receipts retain SQL statement/commit timing. `export_timings` selects
post-commit receipts, avoiding double-adding pre-commit copies. Nested spans are inclusive.
Queue age and a rendered-response acknowledgement use separate server timestamps. Provider
internals and absent stage coverage remain unmeasured. No new remote Langfuse export/readback
is claimed by this private instrumentation.

`evaluation_v2.scorecard` expands every scheduled case/comparator/trial before scoring.
Missing rows reduce completion and retain unknown cost/safety. Per-class/slice performance,
scope errors, exact/relevant evidence and attack-goal success remain separate. A correct
classification can coincide with disclosure: count task success AND block the critical gate.
Content hashes bind references/observations, not their applicability. Behavioral parent-group
checks require every related observation, so omitting the hard variant cannot improve a pass.

`classical.TfidfBaseline` fits vocabulary/IDF/logistic coefficients only on training groups,
fails non-convergence and rejects family/parent/exact-text overlap at prediction. It loads
no pickle. An intent probability is not a qualified urgency, ambiguity or evidence judgment.
`routing_experiments.calibrate` requires explicit scheduled calibration trials and limits;
an entirely absent trial remains missing. `calibrate_cascade` needs cheap-only AND strong-only
observations, replays stop/escalation rules for each threshold pair and sums selected known
stage costs. A final routed answer alone cannot reveal which cheaper settings would escalate.
Critical effects block every point even if the affected answer would go to review. Repeated
trials count as one family for uncertainty. Selection still needs fresh untouched validation.

`economics.economic_report` requires matched family multiplicities, distinct cross-arm
exposure, complete correct acceptance and human-attested effort before returning observed
savings. Unknown cost/currency or invented effort cannot fill those fields. Wrong work and
rework remain in cost per correct acceptance; study expense is separate. Attestations are
not presence proof or randomized causal evidence. `export_work` deliberately leaves
correctness/cost unknown until separate reference/billing evidence is supplied.

## Evidence, limits and interview exercises

`tests/test_cfpb_evaluation_v2.py` covers false savings, missing-trial promotion, group
leakage, actual sklearn fitting, scope/schema/quote failures and unsafe calibration.
`tests/integration/test_cfpb_evaluation_state.py` uses PostgreSQL/HTTP to check reconstruction,
idempotence, leases, protected study grants, manual blinding and actual denied attacks.
Constructed witnesses do not establish real model quality, causal value or production safety.

Why is always-review insufficient? It can avoid automatic errors while imposing effort and
delay on every case. Explain scheduled support, coverage/selective error, missed required
review, unnecessary review, corrections and complete cost together. Why not use only final
cascade answers for calibration? Escalation and its cost change with the first-stage threshold.
Why not sum subprocess times? Inclusive/concurrent spans overlap. Why not call accepted
triage correct? Acceptance and independent reference agreement are different observations.
What would justify more automation? Applicable references, a supported calibration point,
fresh frozen validation and shadow outcomes within explicitly approved operating limits.
