# H2 provider gateway

H2 implements `ProviderGateway.generate(context, request)` with a pinned Gemini Developer API transport. It accepts text, local JSON Schema 2020-12 constraints and function proposals/results. It executes no tool. Domain/framework adapters, durable recording/replay (H3), shared deadline/retry/budget enforcement (H4), full outcome accounting (H6) and production tracing/redaction (H8) remain subsequent work.

## Request identity and model wire version 2

Model request/message/response and tool-call schemas are now **2**. Runtime, usage, evaluation and new exchange/part objects retain their own version **1**. Request serializer version is **2**. Old model wire records explicitly fail validation; no persisted recording format existed before H2. Do not relabel old records as version 2 or reuse their hashes; H3 must provide any reviewed migration it needs.

`ModelRequest.fingerprint()` hashes canonical UTF-8 JSON: provider, endpoint, requested model/revision, complete ordered messages, supplied generation parameters, tool declarations/choice, output schema and serializer/schema versions. Object-key order is canonicalized; whitespace, message/part/tool order, arguments and opaque signatures remain significant. This is content identity, not response identity or a replay store.

`ModelPart` preserves the exact order of assistant text/function parts plus optional encrypted thought signatures as canonical base64. `ModelMessage.content/tool_calls` must equal the public projection of those parts; thought text is excluded from public content. Tool calls carry both a local correlation ID and the provider ID when present. Missing provider IDs get unique local IDs; those invented IDs are not sent back as provider IDs. Retain the returned assistant message unchanged when appending tool results. Gemini function history without original parts fails before dispatch.

The transport converts only leading system messages to ordered system-instruction parts. It rejects developer messages and late system messages rather than changing their meaning. Function results require matching pending IDs/names and a JSON object body; all pending results must arrive before another turn. Parallel result messages are grouped as one ordered function-response turn.

## One dispatch and detached evidence

The gateway validates/detaches context and request through JSON. It allocates an occurrence under a lock within `(run, tenant, agent, case, trial)`, then gives the transport a separate request copy. It validates the returned model contract and checks provider/requested-model plus any explicitly requested revision. A provider alias and returned model version are separate facts; no immutable-weight claim follows from matching the alias.

Each `ModelExchange` retains context, occurrence, request and response. Its identity includes the scoped occurrence and request fingerprint. Two identical requests in a trial produce separate records and can have different answers; a new trial restarts occurrence at one. Snapshot readers get detached copies. Concurrent completion order can differ from allocation order: use the occurrence, not the list index.

Records are private in-memory JSON, contain model-visible content and are not automatically logged/exported. They are neither durable nor globally unique across gateway instances/restarts. Unexpected programming exceptions propagate and may leave an allocated occurrence without an exchange; complete attempt/outcome accounting is H6. Caller-provided identities are provenance, not authentication or tenant authorization.

The live gateway refuses `offline_fake` and `strict_replay` without dispatch. Fresh/monitoring calls have no cache, retry, model fallback or automatic tool execution. This is not H10's fresh evaluation/release recorder. Budget/deadline fields are declarations here; H4 must reserve and enforce shared limits before real workloads.

## Gemini boundary and usage

Install the optional runtime extra `production-agent-harness[gemini]` for the adapter. It pins google-genai 2.30.1 and jsonschema 4.26.0. The root development group selects that extra and pins types-jsonschema; `python dev.py setup` installs it through the shared lock. A base harness wheel does not require Google/framework packages.

The route is explicitly Gemini Developer API, `https://generativelanguage.googleapis.com`, `v1beta`, `gemini-3.5-flash-lite`. Enterprise/Vertex routing, environment proxies and redirects are disabled. Each call owns/closes its client, uses a 30-second request timeout and one SDK attempt. Automatic continuation is **false**; automatic function execution is disabled. Pinned serializer-v2 defaults are one candidate, LOW thinking and 512 maximum output tokens. Changing these implicit translation defaults requires a serializer version review.

Supported explicit parameters are temperature (0–2), top_p (0–1), positive top_k, max_output_tokens (1–512), stop_sequences, integer seed and LOW thinking. Unknown/coerced parameters fail before dispatch. The caller must put intended sampling settings in the request; `RunContext.seed` is not silently substituted into model parameters. This fixed small transport slice can be extended through a reviewed versioned change.

Successful HTTP bodies are checked before SDK parsing so duplicate keys, non-finite values and coerced/negative token counts cannot become valid accounting. Output must have exactly one model candidate ending STOP; blocked, truncated, unsupported multimodal/streaming or ambiguous output becomes a typed failure. JSON text and proposed arguments are validated against supplied schemas, without coercion. References must remain local; an empty referencing registry performs no HTTP/file lookup. Format keywords remain annotations, not additional format checks. Google's supported schema dialect can still reject a locally valid schema; HTTP errors remain failures.

Known prompt tokens include cached tokens; cached counts are retained separately. Output accounting is candidate plus thinking tokens only when both are known. Missing thinking tokens make aggregate output unknown; raw provider fields survive separately. Cost/currency stay unknown, including on a user-confirmed Free project. HTTP/timeout/transport failures count one attempted SDK request and unknown usage; preflight/mode failures count zero. Known usage survives invalid content. Retryable is a classification for H4, not permission to retry automatically.

## Verification and optional live probe

```powershell
python dev.py setup
python dev.py check
python dev.py gateway-live
```

Ordinary checks use actual SDK parsing/serialization over mock HTTP, with socket connections denied. They need no keys, live provider or Langfuse. `gateway-live` is explicitly separate and excluded from CI. It requires the existing ignored `.env.local` Gemini key and `GEMINI_FREE_TIER_CONFIRMED=true`; the flag is a user attestation, not SDK billing verification. Never paste keys into chat or put them in command arguments/Git.

The live probe makes at most two invented requests: a forced `lookup_order` proposal for `invented-order-001`, then its unchanged signed assistant history plus an invented tool result `{"answer":42}`, requiring JSON `case_id="invented-h2", answer=42`. It prints only aggregate identities/usage and the invented answer, not raw signatures/keys. It records the actual code revision (with a dirty marker when applicable) and lock hash. No real source records, business actions, model-quality experiment or Langfuse export are part of this command. H1's separately verified local trace remains compatibility evidence for its original path.

Primary references inspected: [pinned Google SDK](https://googleapis.github.io/python-genai/), [structured output](https://ai.google.dev/gemini-api/docs/structured-output), [thinking/signature distinctions](https://ai.google.dev/gemini-api/docs/thinking), [schema referencing](https://python-jsonschema.readthedocs.io/en/stable/referencing/), [jsonschema 4.26.0](https://pypi.org/project/jsonschema/4.26.0/). See the Build Book Entry 14 and the current study guide for construction and source-level walkthroughs.
