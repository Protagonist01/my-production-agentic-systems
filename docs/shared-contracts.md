# Shared contracts — F2

Runtime/evaluation schemas remain version 1. H2 uses model request/message/response/tool-call schema version 2 and request serializer 2; old version-1 model records fail validation and require an explicit migration. F2 is merged; H1 compatibility is verified. The fake example still exercises wiring only; [H2 gateway](gateway.md) adds bounded real transport and per-occurrence evidence.

## Public runtime and model objects

Import from `agent_harness.contracts`.

| Object | Meaning |
|---|---|
| `RunContext` | Tenant/agent, case/trial/run and stable business-event identities; mode, aware fixed clock/deadline, seed, budget and code/candidate/data/policy/environment versions |
| `AgentInput` | Request and reviewed public observations (`reference`, `text`); no metadata, expected answers or hidden-state fields |
| `AgentResult` | Decision, claimed outcome, output, state-change/review/evidence/trace references, usage and typed failure |
| `ModelRequest` | Provider/endpoint/model/revision; ordered role/text/tool-call/tool-result messages, all supplied JSON generation parameters, tool schemas/choice, output schema and serializer version |
| `ModelResponse` | Provider/model/revision/request ID, assistant output or typed model failure, finish reason and usage |
| `Usage` | Call count, token counts and decimal cost/currency; unknown observations remain null |
| `Failure` | Stage, code, message, retryability and evidence; callers decide whether retries are permitted |

Pydantic 2.14.1 is pinned exactly. Contracts use strict validation, forbidden extra fields and schema version 1. Use `model_dump_json()` and `Type.model_validate_json(...)` for transport. Unknown versions fail. Decimal money serializes as text; timestamps require a timezone. Assignment is frozen, but nested JSON dictionaries remain mutable: copy/revalidate at dispatch boundaries. This is not a security sandbox. Do not use `model_construct` or unvalidated `model_copy` at a transport boundary.

`review_required` requires a review reference; `failed` requires a typed failure. Other outcomes cannot carry those fields. References are claims, not verified durable records: domain scorers must inspect actual state, review and ledger stores.

`ModelRequest.canonical_json()` preserves message/tool order and prompt whitespace while sorting object keys. `fingerprint()` hashes this complete representation. It is request identity; [H3 replay](replay.md) additionally retains full scoped trial/call occurrence and provenance. Schemas are preserved JSON objects; provider dialect validation remains H1/H2. Multimodal content and streaming need a reviewed contract extension before use.

## Evaluator-only objects and dispatch

Import from `agent_harness.evaluation`. `EvalCase` keeps public `input` separate from `ExpectedResult`, hidden state, risk/slices, source/snapshot/policy/scorer versions and faults. Expectations hold outcome/text, autonomous eligibility, required review, allowed decisions and expected state changes. `FaultScenario` declares target, timing, predeclared recoverability, expected safe behavior and invariants. Evaluator fields are never forwarded to the agent by this runner.

The public `contracts` module defines `Agent.run(context, input, gateway)` and `ModelGateway.generate(context, request)`; `evaluation` defines `Scorer.score(case, result)`. Agents need no evaluator import. `run_case(...)` validates/copies context and case, checks case/snapshot/policy identity, constructs only the closed `AgentInput`, runs the agent, checks result identity, invokes the scorer with a distinct result copy, and returns `CaseReport`. Scorer exceptions propagate; an empty score list fails validation. H5 adds [versioned case manifests and explicit scorer registration](case-manifests.md); H6 owns batch/trial accounting.

`ScoreResult` has a metric name, scorer version, denominator eligibility, one finite numeric value or category, evidence and an optional typed scorer error. Errors cannot carry scores. Values are not restricted to proportions because later metrics include latency/cost; the scorer defines units and meaning. `CaseReport` preserves context, versions, agent result and scores; it does not publish expected labels or hidden state.

Closed public schemas reject evaluator fields both at the root and inside observations. Tests change private answers/hidden state, capture the agent/gateway arguments and verify that only the scorer sees the changes. This prevents structural leakage through this runner. It cannot detect answers embedded in legitimate free text or references. Domain adapters must build and review public as-of views; in-process Python code can access shared memory. Never serialize an entire source row as a public observation without an explicit field review.

## Executable offline example

After setup, use the portable wrapper from PowerShell or CI:

```powershell
python dev.py example
```

The wrapper discovers actual Git HEAD and marks a dirty working tree with `+dirty`. Source exports need an explicit `--code-revision`; see [development commands](development-commands.md). The underlying module still accepts required revision/lockfile arguments directly. It hashes the lockfile, runs one invented case through `FakeAgent` → `FakeGateway` → `FakeScorer` → `CaseReport`, validates the JSON round trip, prints the report and exits nonzero if its text check fails. It uses no credentials, provider, database or telemetry.

The source is synthetic, mode is `offline_fake`, and metric is `fake_case_correct`. Zero tokens/cost describe an in-process text transformation, not model pricing. The gateway rejects fresh/replay/monitoring modes, unsupported routes, tools and output schemas. Fault definitions serialize, but scheduled faults fail explicitly until H7 implements them. Budgets/deadlines remain declarations on this fake path; [H4 controls](controls.md) enforce shared reservations and elapsed limits on the explicitly selected controlled path. H3 supplies immutable reviewed model-call fixtures/replay separately. Durable reviews, state scorers, fresh quality and release gates remain later tasks.

Tests cover an invented model timeout, review/usage/evidence round trips, tool-call/result wire shapes, request identity changes, invalid payloads/identities and scorer failures. These establish contract behavior, not industry accuracy or safety.

Design references: [Pydantic models](https://docs.pydantic.dev/latest/concepts/models/), [serialization](https://docs.pydantic.dev/latest/concepts/serialization/), and [Langfuse input/expected-output separation](https://langfuse.com/docs/evaluation/experiments/datasets). No live Langfuse dataset or SDK integration is created by F2.


## H2 model extensions

ModelPart retains ordered assistant text/calls, thought flags and canonical-base64 opaque signatures. Public content/tool_calls must match the non-thought projection; retained parts are assistant-only. ToolCall separates local call_id from optional provider_call_id. ModelResponse adds raw provider_usage beside aggregate Usage; cost remains unknown and aggregate output is unknown when thinking usage is absent. The shared contract validates shape, while GeminiTransport checks local schemas, pending function history and supported dialect/route. ProviderGateway revalidates Python objects before canonical JSON snapshots, checks response route/revision and retains detached scoped occurrences. Runtime identities do not grant authorization. See [gateway details and migration boundary](gateway.md).
