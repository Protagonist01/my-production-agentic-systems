# Execution and evidence proposal

Written: 2026-10-09. Delivery direction adopted 2026-10-11; runtime and dataset validation remain unimplemented. [Current delivery plan](project-management.md) and [architecture](README.md) govern execution; tentative examples here are design rationale, not tested APIs.

User context: the base targets general AI / agent engineering; each vertical supports applications in its industry. The user can spend 40 hours per week building together with the assistant. Preserve all five verticals as the destination, while proving a complete first workflow before expanding.

The accepted delivery plan revises the original requirements where explained below. The GitHub repository and connected local Git checkout now exist. No executable agent, test suite or evaluation recordings exist. CFPB and Olist now have detailed task-based plans. No measured runtime result is claimed.

## 1. Parallelize bounded parts, integrate one finished workflow

Recommendation: one monorepo, a main checkout owned by the integrator, and at most three active implementation worktrees. A worktree is a separate branch checkout, not a worker or a separate application deployment. Give each worker a bounded task and acceptance criteria. Git worktrees support multiple branch checkouts attached to one repository. [Git documentation](https://git-scm.com/docs/git-worktree)

### Foundation: finish before creating implementation branches

1. Initialize Git and make a reviewed starting commit containing the plans and an ignore file.
2. Create the Python package scaffold, locked environment, one repeatable check command, and import-boundary checks. Decide the supported Windows command path; the supplied Makefile assumes Bash.
3. Define the shared contracts and fake implementations. Run one fake case through agent -> gateway -> result -> scorer -> report without a model or network.
4. Commit the contract baseline. Branch each implementation worktree from that same commit.

The integrator owns `harness/interfaces.py`, root dependency files, root command definitions, CI configuration, database migrations shared across modules, and the Build Book. Contributors request changes to those files instead of editing competing copies.

### First implementation wave

| Stream / proposed branch | Owned paths | Concrete deliverable | Acceptance evidence |
|---|---|---|---|
| Gateway / `feat/gateway-replay` | `harness/gateway/`, gateway tests, recording format | One provider adapter behind a fake transport, typed responses/errors, timeouts, bounded retries, budget reservation/accounting, strict replay and fresh recording modes | Exact request matches replay; changed requests fail; repeated identical requests retain distinct trial/sequence identity; timeout/retry cannot exceed budget; replay cannot call network |
| Evaluation / `feat/eval-runner` | `harness/evals/`, `harness/faults/`, `harness/reporting/`, evaluation tests | Versioned cases, deterministic scoring, seeded fault scenarios, outcome accounting, case-level baseline comparison, JSON/Markdown report | Missing cases and scorer errors fail the run; partial runs stay incomplete; fake deliberately broken agents fail; escalation-only agent cannot get a completion score |
| Olist / `feat/olist-first-slice` | `projects/olist-support/`, its policies, catalog, mock backend, fixtures and tests | Order lookup -> policy -> limited refund or review -> truthful reply; transaction-aware idempotency; trace events through the shared interface | Valid refund changes mock state once; excessive refund is denied; timeout after commit returns the original result on retry; restart and duplicate event do not create a second refund |

The main checkout integrates these streams, adds the telemetry exporter, and owns the cross-module test. Workers use the fake contracts until upstream implementations are merged. They do not wait on unfinished internals or invent alternate shared schemas.

### Contracts to agree before branching

- `RunContext`: tenant/agent identity, case and trial IDs, business event ID, fixed test clock, seed, mode, deadline and budget.
- `ModelRequest` / `ModelResponse`: complete ordered messages, model/provider identity, generation parameters, tool schemas, output schema, usage and typed errors.
- `AgentResult`: proposed decision, actual outcome, state-change references, review reference, trace reference, resource usage. Scorers independently verify outcome claims against state.
- `EvalCase`: input, snapshot reference, expected allowed decisions and state changes, eligibility for autonomous action, required review, risk and slice labels. Expected values are available only to the scorer.
- `ScoreResult`: metric name, value or category, denominator eligibility and evidence; scoring errors are explicit failures.
- `FaultScenario`: injection target and timing, recoverability label set before execution, expected safe behavior and required invariants.

These are proposed fields, not final Python APIs. Add only fields needed by the first complete slice.

### Worktree operation rules

- One task owner and branch per worktree; one owner of each shared contract.
- Merge small, working increments into the main branch after review. Refresh other branches after each shared-interface change. Integrate continuously, not after three large feature branches finish.
- Give each worktree its own environment, writable cache, test database/schema, temporary directory, ports and Docker Compose project name. Worktrees do not isolate running services. Store immutable sanitized recordings separately from mutable runtime caches.
- All write tests use isolated mock systems. Use synthetic fixtures and fake clocks, and restore initial state per trial.
- The integrator reruns the complete workflow after merging, even if branch-local checks passed.
- Use a single provider call queue/budget for live runs, so concurrent workers do not independently consume the same quota.

### First milestone and later waves

The first milestone is a recorded demonstration and report showing: a valid refund, an over-limit request, a genuinely ambiguous case with review evidence, an injected instruction, a timeout after commit, and crash recovery. Start with about 30-50 deliberately varied development cases, then build the release set separately. These counts are development scope proposals, not evidence of safety.

Defer the second provider, calibrated judge, drift jobs, MCP transport and Inngest until the complete in-process workflow and its failure tests work. Keep their interfaces possible without building their infrastructure upfront.

Next wave: CFPB classification/routing can proceed alongside Revenue integrity's synthetic world, reconciler and gold labels. Extract the access mechanism only when Olist and the second write-heavy vertical expose actual common code. Begin prior-auth policy selection and independent labeling while those agents are being integrated. Build Supply chain and Prior auth against the tested foundation with no more than two verticals being integrated at once. Add workflow orchestration when a vertical actually needs external event waits.

Why: Olist exercises the widest useful set of base features in a compact workflow. CFPB adds a different framework and classification/calibration task. Revenue integrity tests reuse of controlled writes. Preserve five-industry coverage without multiplying unfinished foundations.

### Capacity and estimates

Treat 40 hours/week as the user's build, review and integration budget, not 40 hours per worktree. For the first two weeks, provisionally allocate 24 hours to implementation/pairing, 8 to integration and evaluation, and 8 to data review/documentation. Revise from actual blocked time and review load.

The existing 500-630-hour vertical estimate is roughly 12.5-15.75 weeks at 40 hours/week before shared harness, integration and extra work. It is not a delivery promise. Revenue integrity's ten milestone rows total 176 hours, whereas its headline is 142-172 hours. Reconcile estimates and measure the first milestone before publishing a calendar.

## 2. Boundary between replay and fresh evaluation

Recommendation: separate software verification, candidate-quality experiments and monitoring. Replay answers whether the current code behaves correctly with specified recorded model responses. Fresh evaluation answers how the candidate behaves with newly generated responses. Monitoring observes deployed traffic and feeds newly found cases back into evaluation. This separation follows the offline/online distinction in [Langfuse concepts](https://langfuse.com/docs/evaluation/core-concepts).

| Mode | External model/read behavior | Application/tool behavior | What the result supports |
|---|---|---|---|
| Strict replay | Exact recorded model requests only; snapshot external reads; missing/mismatched recording raises an error; no provider calls | Execute current policy, validation, graph and mock write logic against reset state | Deterministic software checks under these recorded responses |
| Fresh candidate recording | Bypass previous response cache for every trial; call the selected model; save a new immutable run | Execute complete candidate against isolated mocks and pinned source snapshots | Candidate quality, repeated-run reliability, actual provider latency and usage on this dataset |
| Monitoring | Actual deployed requests; report cache-hit and cache-miss cohorts | Actual supported operational workflow | Observed trends in the traffic served; not a controlled baseline comparison |

VCR.py similarly distinguishes replay that errors on new requests from recording that never reuses old responses. This is evidence for strict mode semantics, not a mandate to use VCR.py as the LLM gateway. [Recording modes](https://vcrpy.readthedocs.io/en/latest/usage.html)

### What must be recorded and frozen

1. Match requests using a canonical representation of provider endpoint identity, model identifier/revision where available, ordered messages, tool schemas, response schema, all generation parameters, and gateway serialization version. Do not remove whitespace from prompt content or omit schema changes to force a match. Bind recordings to a trial and call occurrence so identical requests can have different sampled responses.
2. Run manifests record code SHA and relevant behavior fingerprints; prompts, policies, scorer and judge versions; dataset/corpus snapshots; tool implementations/schemas; environment lock; clock and seed; fallback route; faults; outputs, errors and usage. Never put expected labels into agent context.
3. Replay current code, not a cached final answer. Read snapshots are fixed, but mock writes execute and final state is checked. Otherwise an adapter bug can be hidden by a recording of successful tool output.
4. Record or simulate timeout/failure sequences and retry timing. Fix the clock and event schedule for replay. Live p95 measurements come from fresh runs, not simulated/replay timing.
5. Replayable does not mean every distributed production run can be reproduced byte for byte. The guarantee is logical output/state reproducibility under captured dependencies and deterministic scheduling; trace IDs and timing fields may differ. Missing dependencies explicitly limit reproducibility.
6. Retain original request/response provenance for each fixture. Only sanitized, publishable fixtures enter Git; protected/licensed source content stays in approved local storage. Sanitized requests must still match the sanitized test inputs.

### When a fresh experiment is required

- Prompt, model/provider, fallback route, sampling or output/tool schema change: generate new candidate recordings and quality results. An old recording cannot measure a response the new candidate never produced.
- Retrieval, corpus, context formatting, graph/tool selection or any change that alters model-visible messages: fresh evaluation of the affected slice plus the common regression set.
- Policy/write/scorer changes: deterministic tests and compatible replay first. If user-visible decisions or safety behavior change, rerun the affected full pipeline freshly before release. Compare baseline and candidate under the same evaluator; an evaluator change requires a separately reviewed scoring baseline.
- Documentation or behavior-preserving refactor: offline checks and compatible replay can suffice. Request mismatches still fail rather than silently falling back to live mode.

An unchanged prompt on an unpinned provider alias can change at the provider. Schedule a small cache-bypassed sentinel run; expand the run if its results change. Nightly full runs are optional budget decisions, not the sole release gate.

### Proposed command and release contract

`eval-replay`: no network, never writes new recordings, fails on missing fixtures. `eval-record`: fresh candidate run, bypasses response reuse, writes a new artifact. `eval-compare`: compare candidate and reviewed baseline on the same cases/scorer. `eval-release`: completeness, safety invariants, per-case regressions, candidate-quality checks and evidence manifest. These command names are proposed interfaces, not working commands.

Run offline checks on every PR. For behavior changes, release requires fresh affected-slice evidence tied to the candidate's behavior and the common regression set. Quota exhaustion yields an incomplete run and blocks the evidence requirement; it does not count as a pass. A safe local fallback may provide separately labeled evidence for that model, but does not substitute for the intended deployment model's quality results.

Keep the approved baseline independently reviewed. No candidate may automatically overwrite it. A higher average can hide a newly broken critical case; case-level checks and artifact provenance address this risk. [Langfuse CI guidance](https://langfuse.com/docs/evaluation/experiments/experiments-ci-cd)

## 3. Headline metrics that survive skeptical review

Recommendation: a small scorecard per vertical, with separate goal, safety and operational results. Do not average different domains into one platform quality score. Langfuse recommends tying metrics to decisions and separating these three kinds of measures. [Metric selection](https://langfuse.com/academy/evaluate/choosing-what-to-evaluate)

### Shared scorecard

| Priority / status | Metric and exact meaning | Source | Why / decision |
|---|---|---|---|
| P0 / sharpen existing | Critical violation counts: unauthorized action, duplicate financial effect, unapproved spend/write, data disclosure; count cases with each violation and total eligible cases, plus action counts | State/ledger/authorization/log inspection | Any observed critical violation blocks release; no quality average can cancel it |
| P1 / replace broad success | Safe autonomous completion: eligible cases with the correct final state/decision, no human intervention and no safety violation, divided by all pre-labeled automation-eligible cases | Independently labeled eligibility and post-run state | Stops an escalate-everything system looking useful; labels are not chosen by the agent |
| P1 / sharpen escalation | Unnecessary handoff / eligible cases; required-review recall / cases pre-labeled as requiring review; complete evidence bundles / all handoffs | Ground truth, review queue, evidence checks | Exposes both reviewer overload and missed required review. Review minutes stay unmeasured until a human study exists |
| P1 / replace resilience | Autonomous recovery / pre-labeled recoverable fault trials; appropriate safe handoff / review-required fault trials; terminal outcome distribution for all fault trials | Fault manifests, final state and queue | Separates usefulness from safe refusal; unresolved timeouts and missing results stay visible |
| P1 / add | All-three-trials-correct rate: eligible cases completing safely and correctly in every one of three fresh isolated trials / eligible cases tested three times | Cache-bypassed repeated trials | Measures consistency rather than cherry-picking the best response; incomplete trials cannot pass |
| P2 / sharpen cost/latency | Model/tool tokens and notional cost per safely completed task; time to autonomous completion and time to review-ready separately; p95 only for fresh runs | Gateway usage and clocks | Includes resources consumed by failed attempts in the numerator. Also publish timeout/failure counts and review waiting time |

For fault trials, terminal states are: safe autonomous completion, justified review-ready handoff, safe blocked/unresolved, or unsafe. Their counts must sum to all scheduled trials. Report recoverable versus review-required scenarios separately and keep an outage that prevents all completion from earning a recovery pass.

All-trials reliability follows the idea of pass^k: success in every trial, rather than success at least once. The tau-bench paper also checks final database state instead of relying on a conversational claim. [tau-bench paper](https://arxiv.org/abs/2406.12045)

### Vertical headline results

| Vertical | Primary result and companion measures | Skeptical challenge addressed |
|---|---|---|
| CFPB | Product/issue macro-F1; high-risk recall at a declared review fraction; autonomous coverage with error rate among accepted cases; routing resource use versus always-strong model on the same cases | Accuracy can hide minority failures; routing everything to review makes high-risk recall trivial. Exclude target product/issue/risk labels from input views |
| Olist | Correct final order/refund state on automation-eligible cases, unnecessary handoffs, required-review recall, duplicate/over-limit effects, all-three-trials correctness | A fluent reply claiming a refund is not proof it happened; zero refunds is not proof of useful policy compliance |
| Prior auth | Incorrect approval recommendations / all approval recommendations AND / all non-approvable cases; criterion-level evidence correctness; correct information-request/routing coverage | Never denying is structural but not enough; an approval recommendation can still be wrong. It remains a recommendation, not a real authorization outcome |
| Supply chain | Paired realized simulated total cost versus do-nothing, rules and solver policies; completion rate, budget violations and missed interventions; sensitivity and a separate holdout simulator | Beating a weak baseline or optimizing the same simulator used to generate labels is not proof of real shipping savings. Define regret as `(cost_agent - cost_solver) / max(cost_solver, declared_epsilon)` and show absolute differences too |
| Revenue integrity | Finding precision, benign-deviation false alarms, value-weighted AND case-level recall; simulated approved-and-applied correction dollars reconciled to the ledger | One large injected discrepancy can dominate weighted recall. Detected/proposed/applied dollars must remain separate; no claim of real recovered revenue |

Judge scores, citation existence, schema validity and preferred tool order are diagnostic measures. A citation can exist without supporting a claim. Judge calibration needs independent human labels and separate validation examples; scorer tests must deliberately expose false passes and false failures. Verify actions in state, not just statements. [Evaluator guidance](https://langfuse.com/academy/evaluate/writing-evaluators)

### Statistics and gates

- Fix test membership, slice definitions and eligibility labels before examining candidate results. Keep development cases distinct from a final holdout. Split synthetic contract template/paraphrase families, not only random seeds; group CFPB/Olist examples by their underlying complaint/order and use temporal holdouts where relevant.
- Report numerator, denominator, dataset/scorer versions, provider/model, fresh versus replay mode, and uncertainty on every headline. Publish all scheduled case outcomes; errors, missing cases and scorer failures cannot disappear from denominators.
- Keep zero observed critical violations as a release requirement, but describe the evidence as `0/N observed`. With zero events in 100 independent representative trials, the exact one-sided 95% binomial upper bound is `1 - 0.05^(1/100)`, about 2.95%. This is a calculation under a sampling model, not a claim about all attacks or live traffic. [NIST interval guidance](https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm)
- Use exact binomial intervals for rare-event counts. Do not bootstrap an all-zero sample and call the resulting zero-width interval proof of safety. Use paired, group-aware resampling for candidate/baseline quality and cost differences; repeated trials of one case are not independent new cases.
- Block any critical safety failure or newly failing required case. Require a minimum acceptable quality/coverage floor and a paired non-inferiority margin chosen before evaluation from acceptable business impact. If results are too uncertain, collect more evidence or mark release evidence insufficient. Do not pick a margin after seeing results.
- Existing 2-point accuracy, 15% cost and 20% latency limits remain hypotheses until a baseline exists. Judge quality never compensates for a bad state change. Require a tradeoff to be explicitly reviewed if lower cost comes with worse quality.

### Additional implementation risks uncovered

- `hash(entity, field, new_value, run_id)` is insufficient to deduplicate the same business event across newly created runs. Use a stable tenant + business operation/event identity + target + action intent, persisting the key across retry/resume. Keep run ID for tracing. Validate payload equality for repeated keys and allow genuinely new operations with distinct business identities.
- A ledger alone does not make rollback safe. Bind approval to the exact change/record version. Rollback must check for intervening changes and append a compensating entry; it must not overwrite another legitimate writer's update.
- A deterministic reconciler can contain logic bugs. The claim that errors originate in extraction is too strong: verify money/date/amendment logic with independent expected examples and property checks before attributing errors to the model.
- Resolve the absent CFPB/Olist plans, broken README relative links, inconsistent build-order text and effort arithmetic during foundation work.

## 4. Decisions still open

The user has confirmed general engineering plus specialized vertical coverage and 40 hours/week. Still to agree before implementation: the contract schema, first Olist policy scope, acceptable quality/coverage floors, live-evaluation resource limits, and independent labeling availability. These do not prevent reviewing this proposal. No worktrees or deployments have been created.
