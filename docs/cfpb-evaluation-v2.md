# CFPB: useful, measurable triage

This opt-in implementation answers the owner's six evaluation requests. It adds a new
workflow and evaluation tooling; it does not rewrite v1 records, reopen the stopped model
study, qualify new labels or approve a release. The result of triage is a category, routing
decision and accepted reviewer disposition. It is **not resolution of the underlying
consumer complaint**.

## Implementation order and coverage

| Request | Implemented path | Check / interpretation |
|---|---|---|
| 1. Unrelated requests | `scope_routing.py`: five explicit scope values, closed v2 schema, exact quotes, mixed-input instruction, scoped desk UI | `test_cfpb_evaluation_v2.py`: out-of-scope, insufficient, unsupported operations, taxonomy gaps, schema violations. Old null classifications remain unknown. |
| 2. Adversarial situations | `evaluation_corpus.py`: 16 exposed authored examples with grouped variants and specific attack goals; no business tools; `evaluation_store.py` independently checks publication and permissions | Unit tests exercise injected model output. Real PostgreSQL/HTTP tests attempt unauthorized reads, forged account actions and CSRF bypass and inspect actual unchanged state. Attack success and legitimate task success are separate. |
| 3. Time and value | Separate manual/assisted assignments, append-only start/pause/correction/acceptance receipts, blinded manual responses, `economics.py` | Active review/correction/oversight, queue/elapsed time, recurring cost and cost per correct accepted triage. Incomplete work, unknown correctness/cost and estimates cannot produce an observed savings claim. |
| 4. Subprocess timing | `measurement.py`, scope parser/evidence/routing spans, SQL read/write/commit spans, worker claim/publication, browser-visible acknowledgement, server queue timestamps | Fixed names only; monotonic process intervals and server wall timestamps have separate meanings. Report stage coverage, p50/p95 and missing stages. Do not sum nested inclusive spans. |
| 5. Broader metrics | `evaluation_v2.py`: explicit schedule, per-class precision/recall/F1, per-slice results, review burden, scope errors, evidence missingness, failures, batch window, latency, cost and safety flags | Expand all case Ã— comparator Ã— trial slots before scoring. A missing result is not a success. Representative and stress cohorts never share a pooled headline. Any observed critical effect blocks the critical gate; unknown safety remains unknown. |
| 6. Balanced routing | `routing_experiments.py`, `classical.py`, versioned `ScopePolicy`, `evaluation_cli.py` | Rules, always-review, TF-IDF/logistic regression and cheap-only/strong-only/cheap-first model paths. Separate training/calibration/holdout; family error bounds, risk/coverage/review curves, confidence reliability bins, explicit operating constraints, descriptive drift and shadow stop rules. No forced automation percentage. |

Build the foundations first (receipts, clocks, missingness), introduce scope-aware candidate
routing second, then compare alternatives and fit a calibration candidate. Retain the
existing fail-closed thresholds (1.01) until an applicable, supported operating point is
accepted. A candidate's self-confidence is a feature, not a probability of correctness.

## Run the private evaluation tooling

Install the locked workspace with `python dev.py setup`. The optional CFPB `evaluation`
extra pins scikit-learn 1.9.1; it is included in the development environment. Existing
historical studies retain their original code and dependency locks.

All example paths below denote an operator-created **private directory outside Git**.
The CLI never loads a provider key, downloads a dataset, retries an attempt or dispatches
a model. Output files are exclusive-create, so old evidence is not overwritten.

```powershell
python -m cfpb_triage.evaluation_cli draft --output D:/private/cfpb/draft.json
python -m cfpb_triage.evaluation_cli baselines --training D:/private/cfpb/train.json --cases D:/private/cfpb/calibration.json --output D:/private/cfpb/baselines.json
python -m cfpb_triage.evaluation_cli score --cases D:/private/cfpb/cases.json --rows D:/private/cfpb/observations.json --trials 2 --output D:/private/cfpb/score.json
python -m cfpb_triage.evaluation_cli calibrate --cases D:/private/cfpb/calibration.json --rows D:/private/cfpb/observations.json --limits D:/private/cfpb/limits.json --trials 2 --output D:/private/cfpb/curve.json
python -m cfpb_triage.evaluation_cli economics --rows D:/private/cfpb/work.json --scheduled-per-arm 12 --output D:/private/cfpb/economics.json
```

`Reference` and `Observation` define the private input formats. Never pass reference labels
to the candidate model. Keep evidence-relevance judgments separate from exact-quote checks:
a quote can exist in a complaint without supporting its assigned category. The automatic
decision adapter records exactness, but leaves relevance and state/security outcomes unknown
until an independent observation supplies them. Known costs must carry their currency.
Batch throughput needs the complete scheduled timestamp set; a partial observed window is
not full-batch performance.

The draft is deliberately exposed constructed training material, not a representative CFPB
sample or fresh qualification cohort. Related mixed/injected/case variants share a family.
Train only on training groups. `validate_groups` rejects duplicate case IDs, exact text,
family or parent links crossing partitions. It cannot discover every paraphrase: source and
template grouping must be reviewed before freezing a cohort. Preserve the original failed
pilot and holdout. A new model comparison requires a new approved study and provider scope.

## Use the protected work desk

The additive `cfpb_eval` schema is SHA-pinned separately from immutable v1 `cfpb_app` DDL.
Provisioned login/CSRF/tenant/case scopes are reused. Participation additionally requires an
explicit trusted participant grant and assignment to that actor. Legacy reviewers do not
automatically acquire study-work authority. Manual cases are stored separately, have no
model job and cannot be fetched through the legacy case API.

Using an existing owned `Workspace` trial:

```powershell
python -m cfpb_triage.desk_cli --root D:/private/workspace --trial STUDY evaluation-bootstrap
python -m cfpb_triage.desk_cli --root D:/private/workspace --trial STUDY account --principal D:/private/cfpb/principal.json
python -m cfpb_triage.desk_cli --root D:/private/workspace --trial STUDY evaluation-participant --tenant demo --actor reviewer-a
python -m cfpb_triage.desk_cli --root D:/private/workspace --trial STUDY evaluation-enroll --tenant demo --actor reviewer-a --family group-a --arm manual --measurement-basis human_attested --review-ref masked-reviewed-a --complaint D:/private/cfpb/input.json --taxonomy D:/private/cfpb/taxonomy.json --policy D:/private/cfpb/policy-v2.json
python -m cfpb_triage.desk_cli --root D:/private/workspace --trial STUDY serve --evaluation-v2 --port 8883
```

Open `http://127.0.0.1:8883/evaluation`. Sign in, choose the assignment, select the work type
and start. Pause for interruptions. At correction/acceptance, attest only active seconds
inside the server-recorded open interval. Supply an exact supporting quote and explicit
final scope/category. Correction pauses work; start another interval before acceptance.
Command IDs bind the exact payload and actor; a stale version must refresh. Acceptance
ends the case. Time is a participant attestation, not proof of presence or reviewer expertise.

The trusted importer must use reviewed-masked data and preserve its private source/masking
receipt referenced by `review_ref`; a nonempty reference is not proof that review occurred.
Use matched family mixes and counterbalance participants across **different** families.
The database refuses the same actor seeing one family twice, and the economics checker
refuses cross-arm exposure and unmatched family multiplicities. A proper prospective
study must also balance difficulty, assignment order and participant experience. The
software does not turn convenient assignments into a randomized causal experiment.

`evaluation-worker` performs one safe, no-provider worker step. Its default result is
unavailable/review-required. Future approved workers may inject `route_v2` through the
existing bounded gateway and stopped shared-ledger controls; there is no new live CLI.
An expired claim is not automatically redispatched, since it may already have consumed a
request. Lease IDs, expiry, case revision, policy/taxonomy/input pins and final acceptance
fence publication. Human correction supersedes candidate publication. A review-only
failure receipt preserves operational failure rather than manufacturing a classification.

## Read the clocks and economics correctly

Within-process spans cover model requests, parsing, quote checks, routing, SQL statements,
commit, worker claim and publication. Authenticated case API calls store a separate timing
receipt after constructing their response. It includes receipt-to-response construction;
its own telemetry write/export overhead is outside that duration. Client-visible work
receipts acknowledge a rendered response using server time, not precise browser paint or
network timing. Queue age is server wall time since enrollment, separately labeled. Clock
skew across separate hosts needs a deployment-level time policy. Worker-process startup,
provider-internal queueing, DNS/TLS phases and external export/readback remain unmeasured
unless supplied by the run host; their absent stage coverage stays explicit. Existing
Langfuse tracing is not silently replaced or claimed to contain these new private receipts.

Measure three clocks: machine execution; nonoverlapping human active work; and elapsed time
to correct accepted triage. Record wrong work and its correction, including escalations and
oversight. Cost per correct acceptance includes the cost of unsuccessful work. Keep one-time
study expenses separate from recurring costs. Missing billing/currency data does not become
zero because a provider is described as Free. Invented/estimated effort can support scenarios
but never the `observed_*_saving` fields. Even complete human attestations establish an
observed comparison, not causal savings or resolution time for a consumer complaint.

## References and operating-point choice

[CLINC150](https://github.com/clinc/oos-eval) provides intent and out-of-scope examples.
[BANKING77](https://github.com/PolyAI-LDN/task-specific-datasets/tree/master/banking_data)
provides banking intent examples. `public_intent_references` accepts pinned local original
CLINC split JSON or BANKING CSV with explicit reviewed applicability mappings and an
approval receipt. It retains publisher split metadata and imports into exposed development
only. It refuses to turn these intent labels into CFPB product/risk/ambiguity truth. Source
licensing and mapping review are required before actual use; no corpus was downloaded for
the implementation tests. CFPB consumer-selected categories similarly do not independently
establish urgency, harm or business outcomes.

[CheckList](https://aclanthology.org/2020.acl-main.442/) motivates behavioral minimum-function,
invariance and directional cases. [AgentDojo](https://github.com/ethz-spylab/agentdojo) motivates
separating task utility from actual attacker-goal success. The authored pack is inspired by
those methods; it is not a run of either benchmark. Database/HTTP attack tests are actual
state/permission witnesses, while simulated model outputs are deliberately labeled as such.

The conventional baseline follows [scikit-learn's TF-IDF](https://scikit-learn.org/stable/modules/feature_extraction.html#text-feature-extraction)
and [logistic regression](https://scikit-learn.org/stable/modules/linear_model.html#logistic-regression)
implementations with fixed parameters. Fit vocabulary/IDF/coefficients only on training
groups, fail non-convergence, evaluate a separate calibration set and never load an untrusted
pickle. It is an intent/category comparator, not a qualified urgency/evidence judge. Rules
are another deliberately limited comparator; abstention and review costs must remain visible.

Compare all six variants on the same scheduled groups, including missing/failing trials.
For each candidate, inspect per-class/slice support, false routine/false elevated behavior,
scope errors, unnecessary reviews, selective error, latency and complete cost/effort records.
The calibration grid reports group-level conditional uncertainty and may return no feasible
point. Repeated trials do not create independent families. Limits are explicit inputs, not
production defaults. Choosing a point on calibration data requires a fresh untouched holdout
and approved reference method before qualification. Small or nonrepresentative samples do
not establish a production error bound.

Freeze the chosen policy, input/schema/prompt/taxonomy/model/environment/reference pins and
rollback version. First shadow with no automatic external actions; compare delayed accepted
triage outcomes and review backlog. `shadow_stop` takes explicit approved safety/missingness/
backlog/latency limits. A critical effect, unknown/over-limit latency or breached budget stops
the candidate and restores review-only routing; drift is descriptive evidence for investigation,
never automatic retuning on holdout or production outcomes. Hosting, workload-specific limits,
fresh provider studies and production release still require their existing evidence/approval.

## Calibration, export and replay details

For cascade calibration, use `evaluation_cli calibrate-cascade` with private calibration cases,
BOTH cheap-only/strong-only stage observations, explicit limits, scheduled trials and an
explicit `--scope-threshold`. The frozen scope gate is separate from category confidence.
The tool replays each cheap/strong threshold pair and reports selected-stage request counts
and known cost with currency; it does not manufacture measured end-to-end latency. Final-only
cheap-first rows cannot fit the cascade. Single-stage calibration combines scope/category
gates. Critical effects block every threshold, even if that row would be reviewed. Repeated
trials do not create independent families; the shared interval method uses exact zero/all
boundaries and Wilson interior estimates, conditional on comparable independent families.
Selection on a grid still needs fresh confirmation.

Export participant-scoped records with `desk_cli ... evaluation-work-export --principal
PRIVATE.json --currency USD --output PRIVATE-work.json`; export timing summaries with
`evaluation-timing-export --principal PRIVATE.json --output PRIVATE-timings.json`. Work export
retains unknown correctness/cost until separate reference/billing evidence is supplied.
`review_only(policy)` constructs new1.01gates and a different policy hash for rollback;
it does not modify historical policy or deploy anything. Monetary summaries are diagnostic
numeric reports, not billing-ledger writes or additional model allowance.

The trusted importer must explicitly choose measurement basis for CLI enrollment. The Python
API defaults to `invented`; automated exercises must never export as human-attested labor.
The basis is stored with the assignment, not inferred from a logged-in reviewer role.

## Verification receipts

Initial focused checks passed26tests; expanded legacy/API checks passed33; the broader
scope/calibration/economics/SQL/replay group passed118. These are checkpoints, not the final
head's full-suite result. The first concurrent broad run had1742passes/2source-inventory
failures because files changed during execution; those refusals are retained and final
stable-head CI is required. Browser checks used invented accounts/data and an invented
measurement basis, not human productivity evidence. See the PR for final checks and
post-merge verification. No provider requests, public source exports or production actions
were made. The underlying release issue remains open for its actual evidence requirements.
