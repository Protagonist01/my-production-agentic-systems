# Correlated telemetry — H8

H8 adds optional evaluation tracing to one backend: Langfuse over OTLP/HTTP. Each evaluation owns its trace and exporter. The existing H1 `trace-check` still makes two live model requests; H8 `telemetry-check` uses only invented offline data and sends seven redacted observations to the configured local Langfuse project.

## Compose and run

Normal `python dev.py check` remains offline. Install the workspace with `python dev.py setup`. Applications installing only the harness can select `production-agent-harness[telemetry]`; base-only callers can use `TraceSession` with their own exporter without installing OpenTelemetry or Langfuse. The extra pins OpenTelemetry SDK/encoding 1.45.1, already present in the development lock. No new service or automatic instrumentation is installed.

Create a fresh `TraceSession(LangfuseExporter(origin, public_key, secret_key), private_key)` inside `TrialFactory.build` and return it as `TrialComponents(..., trace=session)`. For an inline evaluation, pass `trace=session` to `evaluation.run_case` or `BoundEvaluation.run_case`. Use a dedicated random key with at least 32 bytes, stored outside Git. Keep it stable only within the approved correlation scope. Rotating it changes references. Knowing the key allows dictionary comparisons, so treat references as pseudonyms rather than anonymous data.

Adapters explicitly wrap operations with `session.invoke("node", operation_name, callable)`, `"tool"` or `"policy"`. The callable receives no evaluator-only object from telemetry. A model request under a node, followed by policy and tool calls, appears as sibling observations beneath that node; the scorer is a sibling of the agent beneath the run. Hook names are keyed references. String and contract results receive keyed result references; arbitrary Python objects are not serialized. Join adapter-owned threads before returning. Copy context into threads when deeper nesting matters; otherwise a new thread attaches to the current trace root. Separate evaluations require separate sessions.

For the actual local export/read-back check, configure `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` and `LANGFUSE_BASE_URL` in ignored `.env.local`, then run:

```powershell
python dev.py telemetry-check
```

This command requires Node/npx and the existing local server. It identifies Git HEAD and dirty status, hashes the actual lock, exports invented canaries, reads observations through `langfuse-cli@1.2.4`, verifies seven types/parents, model usage, code/candidate/data/policy/lock references, source evidence and the tool result reference, and checks that configured keys and canaries are absent. It prints safe health and a local trace URL. Failure exits nonzero with a fixed check name and exception class. It never prints the CLI response, server error body or full private CaseReport. Source exports may supply `--code-revision <actual-identifier>`; that explicit value remains the caller's responsibility.

## Privacy boundary

Only generated trace/span IDs, fixed observation names/types, bounded counts, mode/source-kind/outcome enums, keyed references and known token counts enter the trace. Raw run/tenant/agent/case/trial/business-event identities, model/provider names, endpoints, revisions, prompts, parameters, schemas, provider IDs, tool arguments/results, source text, private expectations, failure messages and exception stacks do not. Model names become `model-<keyed-reference>`; cost/pricing is not inferred. Unknown token counts are omitted, while observed zero remains zero.

Versions and up to the first 64 public source references are represented by domain-separated HMAC-SHA256. `source_count` records the full count so truncation is apparent. These references support matching against separately retained private evidence; they do not prove that a source was fetched or that an answer was grounded. The current probe's source observation is invented.

The safe telemetry report is `TraceHealth`, available as `CaseReport.telemetry` and `TrialRow.telemetry`. Existing CaseReports, schedules, model recordings and journals still retain private identities and runtime payloads. Adding telemetry does not make those artifacts suitable for publication. Canary tests explicitly demonstrate this distinction. Custom exporter implementations and code that bypasses private projection methods are trusted application code; this is not a sandbox against malicious Python plugins.

## Export, flush and cleanup

The session admits at most 256 spans by default, configurable from 2 to 4096. Admission happens at span start, so a full buffer keeps already admitted parents; excess child operations still execute and increment `dropped`. Each trace sends one synchronous batch after the root ends. Export, flush and shutdown run once; each ordinary exception becomes a finite failure state. An agent or scorer exception still propagates after telemetry cleanup. In a spawned worker, an execution error retains safe telemetry health separately from its missing evaluation report. Frame and journal validation reject disagreement between row and case health.

`healthy` requires export acceptance, successful flush/cleanup and zero dropped spans. `accepted` means the configured endpoint acknowledged the batch. It does not mean observations were stored or queried successfully. The probe performs that separate read-back. Health failure never turns a completed result into a model failure or changes the autonomy denominator; a release policy may separately require healthy telemetry. H9/H10 quality and release gates are subsequent work.

The transport requires an explicit HTTPS origin or HTTP loopback origin, rejects embedded credentials/path/query/fragment, disables ambient proxies and refuses redirects. It makes one request with a socket timeout from greater than zero through thirty seconds; default five. It checks HTTP status, bounded reply size, standard OTLP partial acceptance and the observed Langfuse 4.50 queued-job acknowledgement. Backend error text never enters diagnostics. No automatic retry hides an export failure. A socket timeout is not a total wall-clock deadline for a slow peer; the H6 supervisor remains the overall trial deadline. A killed/crashed worker may lose its buffered spans and cannot certify flush/cleanup. Missing health means unknown, not healthy. Cross-process propagation, durable trace queues, asynchronous streaming, live quality experiments and server hardening are outside H8.

## Backend choice and evidence

The local server reported 4.50.0. The installed Langfuse SDK is 5.0.1; current SDK documentation requires server 4.59.0 for its full-platform path. H8 therefore uses the documented standard OTLP boundary and fixed resources rather than automatic SDK/provider capture. The server is left untouched. The actual endpoint returned HTTP 200 with JSON job acknowledgement; the adapter recognizes that response, and the probe separately checks persisted observations.

Primary references read during implementation: [Langfuse OpenTelemetry and attribute mappings](https://langfuse.com/docs/opentelemetry/get-started), [SDK overview](https://langfuse.com/docs/observability/sdk/overview), [masking](https://langfuse.com/docs/observability/features/masking), [trace best practices](https://langfuse.com/docs/observability/best-practices), and [OTLP responses](https://opentelemetry.io/docs/specs/otlp/). The best-practices audit checks meaningful structure, specific types, pseudonymous model identity, known token usage, privacy and explicit flush/cleanup. Raw input/output context and automatic model pricing are deliberately absent under this harness's privacy boundary.

Focused tests cover hierarchy and threaded parents, canaries in free-text fields and exceptions, capacity, lifecycle failures, real HTTP rejection/redirect behavior, worker error/success health, journal recovery and independent CLI response validation. Final local, installed-package, real trace and hosted results are recorded on issue #22 and the PR; a preliminary pass does not establish final-head acceptance.

H8 also proposes an explicit [invented replay fixture/pin update](replay.md#h8-proposed-dependency-lock-fixture-update) for its changed lock metadata. The original resource is retained, and strict lock equality stays enforced. Review that artifact and pin in PR #78.
