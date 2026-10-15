# ADR 0001 — First provider, framework and tracing integration

Date: 2026-10-15 (Africa/Lagos). Task [H1 #15](https://github.com/Protagonist01/my-production-agentic-systems/issues/15). Status: merged and verified on main 0a859bb (PR #71). Original H1 implementation was based on verified main 6e48011 (F5 PR #70).

## Decision and reasons

Use **Google Gemini Developer API**, model **gemini-3.5-flash-lite**, through the official Google Gen AI Python SDK. The user requires the free tier with billing disabled and confirmed that project configuration. This is an integration candidate, not a measured winner on Olist or the other domains.

Initially tested stable 3.8 Flash: two bounded structured-output attempts returned HTTP 503. A metadata request succeeded, identifying models/gemini-3.8-flash, version 3.0 and generateContent support. Explicitly revised the first candidate to stable 3.5 Flash-Lite, which passed both the JSON and single-function proposal checks. There is no hidden runtime model switch, paid route or automatic fallback.

Use **LangGraph** for the intended Olist workflow and **Pydantic AI** for the intended CFPB classifier. Keep domain workflows separate. LangGraph can call an arbitrary node function without a LangChain model adapter; Pydantic AI exposes a custom Model interface. H1 tests a graph node and a FunctionModel producing validated typed output. These are extension-seam checks; a real framework adapter to the shared ModelGateway remains H2/application work. Frameworks must not introduce independent live/replay/budget paths.

Use the **existing local Langfuse v4.50.0** with a dedicated project for this repository. The user explicitly chose reuse. Docker already runs Langfuse and other services with roughly 7 GB available to its engine. Removed the proposed second six-container stack before starting it. No existing services, volumes, network bindings or server version were changed. Current Langfuse SDK 5.0.1 and CLI 1.2.4 are the tested client candidates.

## Exact dependency pins

| Package | Pin | Responsibility |
|---|---|---|
| google-genai | 2.30.1 | SDK request serialization and typed provider responses |
| langgraph | 1.2.15 | Graph-node compatibility probe; later domain orchestration |
| pydantic-ai-slim[google] | 2.56.0 | Custom model/typed-output seam, selected provider extra |
| langfuse | 5.0.1 | Explicit H1 generation spans and local export |
| langfuse-cli | 1.2.4 | Read actual v4 observations through the public API |

Python remains 3.12–3.13; local verification is Windows/Python 3.13.4, uv 0.11.1. uv.lock resolves 109 packages, including transitive dependencies. SDK/framework probes are pinned **development dependencies**; the harness's ordinary runtime dependencies remain Pydantic/Psycopg. Installing a wheel alone does not install the H1 probe tools. The CLI is invoked through pinned npx and requires Node 20+; offline CI does not invoke it.

## Identity, limits and free-tier boundary

Provider: Google Gemini Developer API; endpoint https://generativelanguage.googleapis.com; API version v1beta; requested identifier gemini-3.5-flash-lite. The first successful responses reported that same model identifier and their response IDs. This is a stable provider alias, not proof of immutable weights. SDK and request configuration are pinned; model weight drift remains outside our control. Record returned versions/IDs and timestamps; later releases require fresh candidate evidence after behavior/model changes.

Official model documentation lists a 1,048,576-token input limit and 65,536-token output limit. The probe requests at most 512 output tokens, LOW thinking, one attempt per SDK request, a 30-second HTTP timeout and disabled automatic function execution. Two calls verify JSON and function proposal separately; the proposed lookup is never executed. This is a small smoke bound, not H4's shared resource queue/reservations or an end-to-end deadline guarantee.

Free-tier input/output tokens are listed free of charge. RPM/TPM/RPD depend on the actual project and current capacity; no universal quota is invented here. The user confirmed Free tier/billing disabled; SDK responses do not independently attest to billing. Report token counts and leave monetary cost unknown. Langfuse's default model-price estimates are not the user's billing statement. No paid upgrade, grounding, caching service, batch job or provider fallback is configured.

Free-tier content can be used to improve Google's products. H1 submits only invented values: case invented-h1, arithmetic 6 × 7 and order invented-order-001. No real Olist rows, complaints, contracts, clinical notes or user identifiers are part of these requests. Production data export/redaction policy belongs to H8 and domain tasks.

## Verification and acceptance boundary

The first untraced Flash-Lite checks returned validated answer 42 and exactly one lookup_order proposal with the required invented order ID. Observed usage: structured 25 input/25 output tokens; tool 86 input/25 output and 39 thinking tokens. These are individual observations, not accuracy or latency benchmarks.

The actual pinned SDK also serializes/parses both responses over a mock HTTP transport. A socket guard blocks probe connections; Windows asyncio's owned wake-up socketpair is constructed before the guard. The graph and Pydantic AI custom model receive validated invented output. Wrong/coerced/extra JSON, unauthorized/multiple/wrong-order calls, missing usage/key/free confirmation and incomplete trace collections fail.

The traced path authenticates only against the configured loopback Langfuse project, creates a root span and two real generation children, flushes/shuts down its isolated tracer, then reads that trace through the pinned CLI. SDK initialization or an empty read-back cannot pass. The first read-back failed because the validator expected a made-up data/data wrapper; CLI 1.2.4 actually returns status/headers/body/data. Inspected the real shape and corrected both parser and fixture. Corrected trace [a8bd44895cdcc0df04779db8ba36d9ca](http://localhost:3000/project/cmv8pr1r00006rd07qo80hr5h/traces/a8bd44895cdcc0df04779db8ba36d9ca) passed read-back: exactly three correlated observations, both real model generations, retained input/output/usage and no configured secret. Its thinking-token fields were unknown, rather than borrowed from an earlier response. Local URLs resolve only while this user's Langfuse is running; hosted CI evidence is maintained in the H1 PR.

## Alternatives and remaining work

Paid OpenAI/Anthropic requests were deferred because the user selected free tier only. Gemini 3.8 Flash remains a possible later candidate; two 503 responses establish observed availability failure, not inferiority. Legacy 2.5 models were deferred because current Google guidance restricts new-project access. Local/cloud alternative trace deployments were deferred after the user chose the existing instance.

Do not add a LangChain model wrapper to Olist merely to call Gemini directly: it would bypass the planned shared gateway. Do not claim Pydantic AI's direct Google adapter has been wired into that gateway. H2 supplies the typed transport and framework adapters; H3 strict recordings/replay; H4 deadlines/retries/budgets; H8 full correlation/redaction/export health; H9/H10 real quality comparisons and release evidence. No business action, durable workflow, production recovery or real-data/model-quality result is implemented by this ADR.

## Primary sources inspected

- [Gemini model and capabilities](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite), [model identities/new-project guidance](https://ai.google.dev/gemini-api/docs/models), [pricing/data use](https://ai.google.dev/gemini-api/docs/pricing), [project-specific rate limits](https://ai.google.dev/gemini-api/docs/rate-limits).
- [Google SDK](https://googleapis.github.io/python-genai/), [structured outputs](https://ai.google.dev/gemini-api/docs/structured-output), [function calls](https://ai.google.dev/gemini-api/docs/function-calling).
- [LangGraph boundaries](https://docs.langchain.com/oss/python/langgraph/overview), [Pydantic AI Google interface](https://pydantic.dev/docs/ai/models/google/), [FunctionModel](https://pydantic.dev/docs/ai/api/models/function/).
- [Langfuse instrumentation](https://langfuse.com/docs/observability/sdk/instrumentation), [isolated tracers](https://langfuse.com/docs/observability/sdk/advanced-features), [trace audit criteria](https://langfuse.com/docs/observability/best-practices), [v4 health/readiness](https://langfuse.com/self-hosting/configuration/health-readiness-endpoints).
- Publisher metadata: [google-genai](https://pypi.org/project/google-genai/2.30.1/), [LangGraph](https://pypi.org/project/langgraph/1.2.15/), [Pydantic AI slim](https://pypi.org/project/pydantic-ai-slim/2.56.0/), [Langfuse](https://pypi.org/project/langfuse/5.0.1/).

## Final source and trace context audit

Source commit ccc036efc843155818d4c591915deb13d46e2069. After the first trace passed, added explicit schemas, allowed function/no-execution settings, LOW/512 generation parameters and root SDK/source/lock identities. One final-context attempt returned HTTP 503 during the second request. The subsequent [trace ce1613328f8a20c48cbd4e2ef2fb35aa](http://localhost:3000/project/cmv8pr1r00006rd07qo80hr5h/traces/ce1613328f8a20c48cbd4e2ef2fb35aa) passed the required CLI read-back; this is the final context audit, not the earlier trace. Both calls reported 25 output tokens; inputs were 25 and 86. Thinking and monetary cost were unknown in this invocation. Final offline checks/CI are recorded in the PR.


## Review evidence

[PR #71](https://github.com/Protagonist01/my-production-agentic-systems/pull/71) is unmerged and H1 is in native Review. [Hosted run 38655659165](https://github.com/Protagonist01/my-production-agentic-systems/actions/runs/38655659165) passed all ten jobs on 2ac2f4a083602619f5babaebf775623aadf93bfa; the final documentation handoff commit is checked separately in the PR. Local source passed 97 offline cases, types/imports/Ruff/lock, six builds and dependency audit. Provider and Langfuse live checks are local evidence; CI uses mocks and contains no provider keys or live requests.


## Post-merge verification

User merged PR #71. Main 0a859bb passed [run 38660002889](https://github.com/Protagonist01/my-production-agentic-systems/actions/runs/38660002889), nine applicable jobs with PR metadata intentionally skipped. Clean merged installation/check passed 97 offline tests, strict types/imports/Ruff, the SDK/framework mock probe, exact-main fake example, six builds and dependency audit. H1 is completed. H2 builds the separate shared transport described in [the gateway runbook](../gateway.md); the H1 trace URLs above retain their original path/source boundary.
