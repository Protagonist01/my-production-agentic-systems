# Supply boundary evaluation, timing and scorecards

This implements the owner's four Supply recommendations in dependency order. The current
workbench accepts structured incident commands. It has no customer-chat route or language
model. This package strengthens that service and prepares explicit development contracts
for language intake; it does not claim a language classifier has been evaluated.

## 1. Unrelated requests and scope

`supply_diagnostics.py` defines a bounded proposed-intake contract. It separates supported,
unrelated, ambiguous, mixed, unauthorized and adversarial requests. An injected future
classifier must produce a decision; the scope admission function checks that decision
against the authenticated principal, explicit incident and role. It neither infers meaning
nor executes a command. An admitted `apply` request still needs the existing exact proposal,
fingerprint, current facts, budget, reviewer and transaction checks.

The authored development inventory has twelve cases, six groups and three repetitions
(36 scheduled slots). No classifier observations are invented. An empty report has 36
missing slots. Both false rejection of legitimate requests and acceptance of unrelated
requests count. Mixed requests preserve an explicit mixed disposition rather than silently
executing every instruction. These are authored development references, not qualified
natural-language labels. A future intake UI/model and a qualified language cohort remain
separate work.

The real API tests send unrelated text, forged tenant/approval/price fields, malformed
identifiers, unknown scopes and unknown routes. Rejection is checked before service effects;
SQL integration also snapshots budgets, shipments, proposals, ledger, confirmations and
notices before/after the hostile requests. The SQL test also logs in through the actual profiled authentication store;
existing authentication/CSRF/session regressions remain in the suite.

## 2. Adversarial evaluation

Report three independent questions: did the candidate propose something prohibited, did a
guardrail block it, and did an unauthorized effect or disclosure occur? A blocked bad proposal
remains a candidate failure. Missing effect/disclosure observations remain unresolved.
Repetitions and declared family groups stay in the denominator; always rejecting supported
work cannot pass. There is no real prompt-injection/model run in this change.

| Attack or failure | Executable regression evidence |
|---|---|
| Extra text, forged price/tenant/approval; unknown incident | `test_supply_intake_diagnostics.py`; SQL table snapshot in `test_supply_evaluation_v2.py` |
| Unknown action, foreign shipment, acting on missing facts | `test_adversarial_planner_cannot_authorize_effects`; no ledger/proposal/portfolio changes |
| Self-review, wrong role, forged payload, revoked scope | Existing `test_supply_operations.py` and `test_supply_console.py` |
| Replayed approval, stale budget/shipment, expired approval | Existing exact-payload/version/expiry integration tests |
| Concurrent duplicate writes and overspending | Existing parallel receipt and budget-lock integration tests |
| Forged wakeup or replay treated as approval | Real SDK mocked event tests, including the opt-in adapter |
| Before-commit rollback, post-commit death and restart | Existing actual process/SQL recovery tests; mechanisms reported separately by OS |
| False delivery claims and notice reconstruction | Existing canonical notice and console-state integration tests |
| Private content in instrumentation | SQL/worker/HTTP canaries assert content, credentials, raw IDs and exception text absent |

The future language inventory also includes direct instruction override and malicious alert
text. Those remain unmeasured until an actual language path exists. Keep direct/indirect
injection distinct from structured tool forgery ([OWASP definition](https://genai.owasp.org/llmrisk/llm01-prompt-injection/)).

## 3. Timing the actual runtime

`supply_profiling.py` records bounded, fixed-name local spans: monotonic wall intervals,
inclusive process CPU, process ID, trace/parent IDs, HTTP status and outcome class. Raw
requests, SQL, parameters, grants, credentials, messages, rows and exceptions are never
stored. Optional incident references use a per-recorder random HMAC key; they cannot be
joined across recorder restarts. Caller-generated trace context is propagated to trusted
spawned workers. Worker return values belong to the caller and never enter the profile.

`supply_profiled_runtime.py` composes the unchanged domain service with these opt-in adapters:

| Measured stage | Meaning and limit |
|---|---|
| Request / response send, login / authenticate | Actual ASGI and auth calls; paths, bodies and headers absent |
| Assessment / planning / board | Canonical workflow and allocator, not an LLM invocation |
| Shipment / alert read, notice append/list/read | Actual store calls; notice-build span includes append, while body construction remains inside board |
| Connection / execute / fetch / transaction / finalization | Actual Psycopg calls, including errors and rollback |
| SQL lock statement | `FOR UPDATE` statement wall time, including roundtrip/execution; not isolated PostgreSQL lock-wait attribution |
| Review / apply / confirmation | Existing role-scoped exact commands, no bypass |
| Event / step / send / approval and confirmation wait | Real SDK delegation; replay/resumption duration is not independently measured elapsed business wait |
| Worker launch / ready / result wait / receive / cleanup | Actual spawned process; child execution reported separately with trace linkage |

Unknown stages appear in `unobserved_stages`. Queue residence, provider transport, remote
freight execution, kernel fsync/WAL and scheduler downtime are not measured by these adapters.
The deterministic service has no provider subprocess to time. CPU is process-wide, so it
cannot attribute concurrent threads individually. Nested/parallel wall times must not be
added as sequential latency. Capacity drops, active spans and clock anomalies prevent a
complete coverage claim. Required-stage coverage is checked for every recorded root, not
merely once anywhere in a report. Specify requirements for the actual operation; a denied
request should not be expected to reach planning.

This follows the distinction between spans, trace context and process boundaries in
[OpenTelemetry](https://opentelemetry.io/docs/concepts/signals/traces/) and the operational
guidance in [Langfuse](https://langfuse.com/docs/observability/best-practices). This adapter is
local; it does not export to Langfuse and does not enable native graph tracing.

To serve an **already provisioned** local trial using the locked project environment:

```powershell
uv run --locked --all-packages python supply_profiled_runtime.py `
  --root "<checkout>" --trial "<existing-trial>" --port 8877 `
  --output "D:/document/.cache/production-agents/supply/<new-profile>.json"
```

The output parent must already exist outside every Git checkout. Existing output is refused.
Normal shutdown writes one exclusive JSON snapshot and fsyncs the file; failures are visible.
An abrupt crash may lose the in-memory trace. This is not a crash-durable exporter. Serving
does not bootstrap/reset data, create accounts, schedule Inngest functions or call providers.
Use `profiled_functions(client, handlers, recorder)` explicitly when composing an event host;
it preserves native retry settings. Worker execution is for trusted local callables only,
not an untrusted-code sandbox or a customer-accessible shell tool.

## 4. Expanded metrics

`supply_scorecard.py` consumes the frozen native simulation plan/worlds/action observations
plus separate independent operational readbacks. It retains the native split/family/outcome
model and sensitivity report; pins the new reference plan and operational inventory; and
adds:

| Metric | Definition / denominator |
|---|---|
| Safe action-map completion | Complete, policy-valid map / all scheduled trials; does not establish durable execution |
| Safe operational completion | Verified state, completed work and explicitly zero unauthorized effects / all scheduled trials |
| Unnecessary / missed interventions | Action versus declared shipment-level reference; public-policy and evaluator-hindsight bases reported separately |
| Tail cost | Observed SIM total cost p50/p95/max and mean at/above empirical p95, for every delay-cost sensitivity |
| Paired baseline wins/ties/losses | Same observed world/trial, candidate against do-nothing, rules and estimate solver; wins only among safe complete pairs |
| Approval burden | Requests, wait duration and expired counts, including missing observation count |
| Plan churn | Replans and subset with unchanged facts; churn cannot exceed total replans |
| Notice accuracy | Independently checked correct notices / checked notices, with named checker; zero checked gives unknown accuracy |
| Recovery | Duration paired with state verification; elapsed time alone is not successful recovery |
| Latency / throughput | Observed wall-time distribution; safe completions / independently measured window, never sum of overlapping trial durations |
| Telemetry completeness | Caller-supplied timing coverage alongside absent stages, dropped/active spans and anomalies |

Unsafe maps retain native fallback cost but are never presented as safe savings. Failed and
missing trials stay scheduled. No intervention reference means unknown quality, not implicit
correctness. Operational schema acceptance is not proof that the observations were actually
collected: preserve checker identity and private readback artifacts. Raw provider costs and
provider attempts are unknown without separate evidence; generating this report makes no
provider calls. No confidence or qualification result is inferred from these development
metrics. All release gates remain unchanged and `release_allowed` stays false.

## Verification

Run the normal quality suite, plus actual SQL checks:

```powershell
python dev.py check
python dev.py db-check
```

Focused files: `tests/test_supply_intake_diagnostics.py`, `tests/test_supply_profiling.py`,
`tests/test_supply_scorecard.py`, `tests/integration/test_supply_evaluation_v2.py`.
Tests use invented fixtures and real local processes; SDK event tests use the actual SDK's
mock transport. They do not consume provider allowance or create production release evidence.
