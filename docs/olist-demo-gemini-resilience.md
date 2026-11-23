# Gemini-only Olist demo candidate

The prior live study stopped after eight HTTP server failures. Of 57 observed domain
requests, 46 matched the authored intent/amount references. Only 59 of 146 scheduled
attempts ran, including two canaries. See the [sealed result](olist-demo-gemini-result-2026-11-23.md).
Neither successful-response accuracy nor unused allowance closes that failed study.

The owner confirmed that only Gemini is available. Groq preparation is parked. This
candidate keeps Gemini 3.5 Flash-Lite, strict semantic parsing, the 48 authored demo
cases and three trials, and the 95% scheduled agreement target. It changes two things:

- The prompt gives unresolved choices and untrusted quoted commands priority, then
  requires coherent non-refund fields. Exact quotes prove source bytes, not intent.
- The existing `BoundedGateway` may make one transient retry within the same 30-second
  logical request, using a one-second backoff. Valid wrong answers and invalid responses
  receive no quality-driven retry. There is no provider/model switch or paid fallback.

Because both prompt and operating policy change, this is a combined candidate comparison,
not a controlled estimate of which individual change caused an improvement. The cases
are exposed, authored demo references, not independent gold or a population confidence bound.

## Build and inspect

Follow `olist_demo_semantic_v2.request` to the prompt/schema binding. The optional request
factory in `DemoPlanner` preserves the original default. `TaskObservation` permits two
calls for this declared unit; the original `Observation` still permits at most one.

`olist_demo_resilience_study.Scope` freezes source, environment, project association,
request order, references, policy and a maximum seven-day window. Preparation reads the
single existing ledger without loading credentials or granting calls. A new exact owner
grant and current Free confirmation are required before provider initialization.

The study contains two canary tasks, then 144 domain tasks. Each task has at most two
raw attempts: a maximum of 292 new reservations. All older unused allocations remain
retained. Unknown tokens consume the full reviewed per-attempt reservation; this is
conservative accounting, not a claim that those tokens were generated. Unknown billing
cost stays unknown even on a confirmed Free account.

For each task, `start_task` commits its exact context and deadline. `RecordedTransport`
commits each raw reservation before I/O and settlement afterward. The existing bounded
gateway owns the retry loop. A second process cannot lease the same task. A crash with
an unfinished task blocks resending; it cannot obtain a fresh deadline. Raw attempts,
task results, scope and stops have SQLite update/delete rejection triggers.

`finish_task` binds the gateway policy, context, raw aggregate usage and final response.
A late success loses credit. SQL work, parent cleanup and source validation have their
own overhead: the 30-second decision budget does not certify a hosted API response time.
The persistent circuit stops after three consecutive or eight total failed domain tasks.
Quota/permission failures and unexpected accounting/unknown-usage failures also stop.
Both canaries must pass before any domain task. Prior stops and observations are immutable.

## Reading the result

Use the readback to report raw provider failure rate, total attempts, unknown usage and
process phases alongside final task agreement and latency. A recovered first failure
remains a raw failure even if the final task succeeds. The scheduled denominator remains
144; missing tasks, invalid output and final failures receive no correctness credit.
Do not mix the first candidate's single-attempt score with this retry-enabled score
without stating their different operating policies. Keep the fixed zero-call baselines.

Offline scripted outputs and network-denied SDK canaries verify wiring and accounting,
not model understanding. This proposal activates no public runtime, host or release.
Passing demo language evaluation would still leave actual account setup, persistent
runtime admission, hosted SIM workflow verification and measured backup/restore to finish.
