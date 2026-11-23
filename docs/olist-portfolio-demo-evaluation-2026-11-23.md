# Olist demo: live evaluation stopped on an HTTP server failure

PR [#169](https://github.com/Protagonist01/my-production-agentic-systems/pull/169) merged
as `b5379b4`. All ten PR jobs passed. Post-merge checks also passed; the PR-only metadata
job was correctly skipped. The shared offline suite passed 2,190 tests and the database
suite passed 340 checks, with two database checks skipped. These establish software and
SIM guardrail behavior, separately from language quality.

## What actually ran

On 23 November 2026 the exact owner-approved amended study started against the existing
configured Free project. It kept the 48 authored input texts, fixed prompt/schema, three
interleaved trials, two canaries and original 24 November expiry. No paid fallback or
automatic retry was enabled. Scope reference: `c48156c0…c7fb2cd`.

| Observation | Saved result |
|---|---|
| Canary slots | 2/2 passed |
| Domain slots | 8/144 settled; 136 unattempted |
| Parsed domain answers | 7; all seven matched their declared references |
| Domain provider failures | 1 |
| Scheduled joint matches | 7/144; incomplete, not a language-accuracy estimate |
| Other intent buckets | No observations yet; only the first refund cases ran |
| Lifetime consumed / ceiling | 653/990, including all older namespaces |
| Older bound allocation | 201 slots preserved: 169 earlier plus 32 Revenue |
| Unsettled reservations | 0 |
| Additional dispatches after stop | 0 |

The last attempted slot was ordinal 10: `olist-demo-refund-8`, trial 1. The SDK returned
`unavailable`, message `Gemini HTTP request failed`, with `retryable=true`. Inspection of
that exact adapter branch establishes an HTTP status of at least 500, excluding its
separate 504 timeout branch. The exact numeric status and provider body were not retained;
calling this a specific 503 or proving a particular server incident would overstate the
evidence. The worker exited normally, did not time out, and returned in 18.25 seconds.

The frozen stop rule did exactly what it specified: preserve the failed call and unknown
usage, insert a durable stop, and dispatch nothing further. The two million token cap
also cannot safely ignore that unknown row. Current unused capacity is not permission to
clear the stop or resend a consumed request.

## Usage and timing

Nine responses reported token usage: 3,087 input and 398 output tokens across canaries
and domain calls. The failed call reported neither. Actual cost is unknown for all ten
responses. Owner confirmation of Free configuration is not a provider billing receipt.
The failed call counts as consumed even though its token usage is unknown.

| Phase, all 10 settled attempts | p50 seconds | p95 seconds |
|---|---:|---:|
| Admission plus parent transport | 13.06 | 23.69 |
| Process startup | 7.11 | 12.40 |
| Worker generation, including SDK/network | 5.69 | 11.99 |
| Frame encoding | 0.00026 | 0.00048 |
| Process exit | 0.52 | 0.90 |

Each p95 uses the nearest rank over only ten observations. Phase percentiles do not add
up to the total percentile. Worker generation includes SDK initialization and network
time; it is not isolated inference latency. Per-slot source/environment checks happen
outside the reported transport timer. No public API latency or cloud availability was
measured.

The separate fresh-process readback and arithmetic audit agreed on seven joint matches.
All original historical rows and stops matched their pre-study snapshot. The original
full 146-slot network-denied SDK run remains a plumbing witness. Its requests, environment
and SDK/capture/scoring code match this run; current-source CI and fresh SDK canaries
provided additional readiness evidence. A further optional local repeat was interrupted
after the provider stop; its partial rows are retained and are not a completed result.

## Proposed bounded continuation

`olist_demo_continuation.py` prepares a separate, explicitly approved amendment. It never
deletes or edits the original scope, stop, reservation or failed response. The proposal:

- Continue only original ordinals 11 through 146: at most 136 calls. Never resend ordinal
  10 or replace its failure. Keep the model, texts, order, references, request parameters,
  90/110-second deadlines, ceiling 990, retained allocation and original expiry.
- Count the failed call in the original 144-slot domain denominator. Keep the same
  complete-capture and 137/144 agreement target. No reference correction or prompt tuning.
- Permit only the inspected HTTP-server-failure category to continue to the next slot,
  after a 60-second pause. Stop on three consecutive such failures or the eighth overall.
  Quota, permission, transport, worker, timeout, unexpected route/cost and other unknown
  usage still stop. Known-usage invalid domain output remains a scored error as before.
- Conservatively reserve 1,114,112 tokens for each unknown-usage row, rather than treating
  it as zero. Propose a 10,000,000-token accounting ceiling in place of 2,000,000, with
  admission requiring room for the next full route quote. This is a reservation bound,
  not a claim that those tokens were used. No additional provider attempts are allocated.
- Pin the original prefix, including SQL schema/triggers, all first-ten rows and the
  original stop. Verify contiguous settled admission before every next request. A crash
  leaving an outstanding reservation blocks dispatch. A new owner grant and current
  Free confirmation are required before this proposed executor can spend.

Google describes transient HTTP failures and bounded backoff in its
[troubleshooting guidance](https://aistudio.google.com/docs/troubleshooting#retry-strategy).
This proposal deliberately keeps failed study slots failed; it does not enable the SDK's
default automatic retries. Availability and interpretation remain separately reported.

## What this does not establish

This is an incomplete study, so neither the demo language target nor hosted acceptance
passes. Even a completed passing score would describe an exposed authored demonstration
contract, with six dependent groups and unknown amount-role exclusions. It would not
establish independent natural-language truth, representative customer accuracy, a
population confidence bound, or reliable real-money operations. Public runtime admission,
Render/Neon account compatibility, off-host encrypted backup and measured cloud recovery
remain separate work.
