# H1 integration checks

The [first integration ADR](adr/0001-first-integration.md) selects Gemini Developer API / gemini-3.5-flash-lite, LangGraph, Pydantic AI and the existing local Langfuse. These commands use invented data and are development probes. They are not the production gateway, recordings/replay or a domain evaluation.

```powershell
python dev.py setup
python dev.py integration-check
python dev.py check
```

integration-check runs the actual pinned Google SDK against a mock HTTP transport, validates JSON/function proposals and exercises framework extension seams. Ordinary check includes its network-blocked/negative cases. Neither needs provider or Langfuse credentials. SDK package pins live in the dev group and uv.lock; Node is unnecessary for these offline commands.

For the live check, use a Google AI Studio project on the Free tier with billing disabled. Copy the Gemini placeholders from .env.example to ignored **.env.local** in this checkout. Set GEMINI_API_KEY and GEMINI_FREE_TIER_CONFIRMED=true after checking the project's tier. The probe cannot detect billing configuration from a model response; the flag is a user attestation, not a budget reservation. No code accepts pasted keys as command-line arguments or logs their values.

```powershell
python dev.py integration-live
```

This makes at most two SDK requests, with one attempt each and no automatic tool execution: JSON arithmetic, then one lookup proposal. HTTP 503/429/auth errors fail with a safe status, without switching models or making a paid route. Missing key/confirmation fails before constructing a live client. A later invocation is a new live smoke attempt; it does not replay old output. Each request has a 30-second HTTP timeout and at most 512 output tokens; H4's global deadline/budget behavior is still future work. Free capacity is not guaranteed.

For tracing, sign into the existing local Langfuse, create a dedicated my-production-agentic-systems project and put its LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY and LANGFUSE_BASE_URL in the same ignored file. Use http://localhost:3000 or the actual loopback port. The traced probe refuses cloud/non-loopback hosts, URL userinfo/query strings and missing fields before dispatch. It neither starts/upgrades Langfuse nor reads unrelated projects. Preserve existing server state and credentials.

```powershell
python dev.py trace-check
```

Requires Node 20+/npx. It authenticates the project, makes two fresh invented Gemini calls under one root/two generation observations, flushes and closes an isolated tracer, and calls **langfuse-cli@1.2.4 api observations list** for that exact trace/time range. This uses v4 observations rather than the deprecated traces-get route. Checks require API status 200, the root and both generations, matching parent/trace/model, known nonnegative token counts and input/output. It also refuses read-back containing either configured secret. A missing/late/export-failed collection returns nonzero; SDK flush alone is insufficient. CLI/package downloads and live services require network.

Only explicit invented input/output and selected metadata are exported. Manual H1 spans make the probe boundary visible without globally patching framework calls. H8 still needs production instrumentation, identifier canaries, redaction, full run/case/trial correlation, error-path export and health diagnostics. Langfuse's estimated model price is separate from actual free-tier billing; the provider report keeps monetary cost unknown. No latency benchmark follows from this small trace.

Keep .env.local, raw CLI output, traces and generated packages out of Git. Saved aggregate evidence may record request/model/code/lock identities, timestamps, tool versions and known limitations, never keys or real source records.
