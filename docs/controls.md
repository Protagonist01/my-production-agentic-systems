# H4 shared execution controls

H4 adds `BoundedGateway` around individual attempts. The live path is caller → BoundedGateway → shared reservation → ProviderGateway → IsolatedTransport → GeminiWorker → GeminiTransport. The optional `gateway-live` command uses this path, with at most two admitted calls and one attempt per call. H1 compatibility probes retain their original path. No H4 live provider request has been made; H4 acceptance uses invented data and actual SDK mock HTTP.

## Integrating a caller

Create one `SharedControls` in the parent process and pass it to every BoundedGateway that shares capacity. A run is `(tenant_id, run_id)` across its agents/cases/trials. Keep its budget and deadline identical; changing either is rejected. A new controller, process or run ID has new capacity. This is not a durable/distributed account quota or tenant authorization.

```python
from agent_harness.admission import GeminiFreeAdmission
from agent_harness.controls import BoundedGateway, ExecutionPolicy, SharedControls
from agent_harness.gateway import ProviderGateway
from agent_harness.isolated_transport import GeminiWorker, IsolatedTransport

# Read a locally configured key and the existing explicit Free-project attestation.
controls = SharedControls()
attempts = ProviderGateway(IsolatedTransport(GeminiWorker(api_key, confirmed)))
gateway = BoundedGateway(
    attempts, controls, GeminiFreeAdmission(free_tier_confirmed=confirmed),
    policy=ExecutionPolicy(max_attempts=3),
)
# context is a validated fresh_candidate/monitoring RunContext with current deadline.
response = gateway.generate(context, request)
snapshot = controls.snapshot(context.tenant_id, context.run_id)
```

Put executable process-launching code under `if __name__ == '__main__':` in scripts. Workers must be trusted, importable and spawn-picklable. Do not pass a thread executor as a substitute for the owned process. ProviderGateway alone is still a one-attempt low-level API; passing timeout_seconds directly to GeminiTransport configures HTTP, not a complete elapsed deadline.

## Capacity and observed usage

Each attempt atomically reserves one call, a reviewed total token upper bound and a monetary upper bound in the budget currency. Retries require another reservation. No admitted capacity is refunded, including preflight failures and unknown timeout usage. This deliberately sacrifices utilization. It prevents concurrent callers from each spending the last available unit; it cannot retroactively undo a provider that violates its declared ceiling.

`BudgetSnapshot` exposes reserved totals separately from `observed_usage`. Returned response usage sums all attempts; any unknown token/cost component remains unknown. `ControlledCall` retains policy, quotes, attempt usage and terminal response; ProviderGateway retains individual ModelExchange records. Response provider_usage describes the terminal attempt, not an invented aggregate. On a known token/cost/call ceiling breach, or unexpected attempt exception, the run freezes and returns budget_exhausted with observed usage retained. H6 still owns full trial/exception accounting.

Money is Decimal; addition temporarily expands precision so a tiny extra reservation cannot round away. Currency mismatch blocks admission. Quotes are trusted reviewed configuration, not provider measurements. Unknown usage cannot establish that the quote was respected.

The current Gemini admission supports exactly the existing Developer API route/model and requires the user-confirmed billing-disabled Free project. It reserves **1,114,112 tokens per attempt**: the published 1,048,576 input plus 65,536 output ceiling. This exceeds the adapter's 512 visible output setting deliberately; no unverified token estimator is used. Reserve zero monetary capacity only under that Free-project attestation; observed cost remains unknown. This is an operating assumption, not SDK verification of billing. A three-attempt run needs at least 3,342,336 reserved tokens. The two-call probe declares 2,228,224 tokens and zero dollars. No paid fallback is configured.

The model ceiling and Free text pricing were inspected on 2026-10-15: [Google model card](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite), [pricing](https://ai.google.dev/gemini-api/docs/pricing). Re-review quotes when changing route/model/pricing. Smaller reservations require reviewed counting and output-limit evidence.

## Deadline, retry and circuit behavior

The first admission maps the UTC deadline to a monotonic end time. Later wall-clock reversal cannot extend it. Every attempt gets the smaller of remaining run time and attempt timeout. The parent uses an owned spawned process, a fixed 1 MiB response frame and an 8 MiB request limit. It discards late results, terminates/joins on timeout and, if necessary, kills/joins. Each cleanup join allows 0.25 seconds; OS startup/scheduling/termination can add overhead. This is bounded application waiting with cleanup, not a hard real-time guarantee. Terminating a local worker cannot cancel work already accepted remotely; retain its reservation. A worker is not a sandbox for malicious Python or its arbitrary subprocesses.

Default policy: three attempts (allowed 1–5), 30-second per-attempt timeout (maximum 60), exponential backoff starting at 0.25 seconds capped at two seconds. Retry only a retryable timeout, rate_limited or unavailable result. Permanent errors do not retry. Backoff cannot extend past remaining run time. Budget/deadline stops are typed failures with aggregate observed usage, leaving the domain caller to choose stop/review. This layer performs no domain action or tool execution.

Circuits share state across runs using the same controller, keyed by tenant/provider/endpoint/model/revision. Default: open after three transient failures, five-second cooldown, one half-open probe, close on success/nontransient reachability. A policy change on an existing route is rejected. Epochs stop stale in-flight completions from closing a newer open circuit. This is neither a provider-wide rate limiter nor a persistent breaker. State lives until its controller is discarded; no eviction policy is supplied yet.

## Strict replay and verification

Use `ReplayAttempts(strict_replay_gateway)` as the bounded attempt interface in strict_replay mode. It accepts only H3's network-free gateway. The current retry controller still executes and consumes each recorded attempt. Always call `strict_replay_gateway.assert_complete()`: changed retry counts leave missing/trailing calls and fail. A ReplayMismatch propagates as infrastructure failure, freezes the reservation and cannot become a scored model outcome. Offline fake mode is refused by this controlled path; its existing example remains separate. Replay time is not provider latency.

```powershell
python dev.py check
python dev.py eval-replay
python dev.py build
# Optional, explicit, credentialed and excluded from CI:
python dev.py gateway-live
```

`tests/test_controls.py` covers all reservation dimensions, twelve concurrent agents sharing two available attempts, failed/unknown usage, immutable run limits, exact Decimal accounting, monotonic deadline/backoff, open/half-open/stale circuits, owned worker interruption/crash/oversize handling, actual SDK 429/503/read-timeout mocks in spawned workers, strict replay and mode denial. Network is denied in parent tests and the SDK mock worker installs the existing Python audit hook. This is test isolation, not OS network sandboxing. Hosted cross-platform evidence belongs to the final PR head. No model quality, domain-state safety or production authorization claim follows from these checks.

See [code anatomy](code-study-controls.md), [gateway](gateway.md), [replay](replay.md) and [Python process documentation](https://docs.python.org/3.13/library/multiprocessing.html).
