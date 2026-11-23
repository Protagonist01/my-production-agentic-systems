# Olist demo: final Gemini candidate result, 23 November 2026

**Result: the candidate did not meet the demo acceptance target.** The approved failure
circuit ended the run after the eighth HTTP server error. The cohort was not completed,
and no hosted release or independent language qualification follows from this result.

## What was measured

The candidate interpreted text only: two canaries followed by 48 authored fictional
customer messages, scheduled for three trials each. Messages cover refund, status,
reship, clarification, unrelated requests and adversarial pressure. References and
fixture facts were not sent to the model. All cases are exposed demo contracts in six
dependent groups, rather than independent natural-language gold or representative traffic.

| Measurement | Observed result |
|---|---|
| Canaries | 2/2 passed |
| Domain observations | 57/144 attempted; 87 unattempted |
| Correct joint outcomes | 46 |
| Provider HTTP server failures | 8 |
| Invalid semantic output | 1 |
| Incorrect intent classifications | 2 |
| Parsed outputs | 48; 46 matched their declared references |
| Proposed acceptance target | Complete cohort and at least 137/144 joint matches; not met |
| Observed domain attempt p95 | 18.30 seconds, including admission/process/SDK overhead |

The result categories sum to all 57 attempted domain observations. Eight unrecoverable
failed slots alone cap the possible full-suite result at 136/144, below the fixed target.
No failed occurrence was retried, relabeled or replaced. The original stop remained
intact; the later owner-approved next-slot continuation used only unattempted requests.

Conditional agreement of 46/48 parsed outputs is 95.8%, but it excludes invalid output,
provider failures and missing calls. It is not an acceptance pass. All three trials were
not observed for any case, so full-trial consistency cannot yet be assessed.

The first trial did reach all 48 distinct cases. Its joint result was 41/48, including
four HTTP failures and three non-HTTP errors. The fixed conservative-rules baseline
matched 35/48 and always-review matched 8/48 on the same inputs. This is a finite,
exposed development comparison, not a population estimate or a passing three-trial result.

## Concrete failure modes

- Ambiguous choice: a customer had not decided between refund amounts. The model returned
  refund with an unclear amount; the reference required clarification. The workflow
  projection would route that unresolved refund to review, separately from raw accuracy.
- Source attribution: a quoted command in an explicitly untrusted note was classified as
  a new refund. Finding a matching amount quote did not prove the customer requested it.
- Schema coherence: execution-override pressure produced review intent with explicit
  refund-money fields. The strict semantic validator rejected that inconsistent output.
- Provider availability: eight calls reached the inspected HTTP server-error branch.
  Workers exited normally without parent timeouts. Exact numeric HTTP statuses were not
  retained, so a particular 503, cause or platform-wide incident cannot be asserted.

## Timing, accounting and controls

Across all 59 settled attempts, local process startup p95 was 9.51 seconds and worker
generation p95 was 9.28 seconds. Worker generation includes SDK initialization and
network time; it is not isolated model inference. These phase percentiles do not add
to the total percentile. Source checks and deliberate cooldowns sit outside the reported
per-attempt timer. No hosted API latency or cloud availability was measured.

Fifty-one responses reported 17,460 input and 2,241 output tokens in total, including
canaries. Eight calls retained unknown token usage. Actual cost remained unknown for
all responses. Free-account confirmation is not a provider billing receipt. Unknown
usage was conservatively reserved in the approved study budget and never treated as zero.

The evaluator and an independent arithmetic readback agreed on all outcome counts.
The original ledger prefix, failures and stop remained unchanged. Separate software
checks passed 2,207 offline tests and 340 database checks, with two database checks
skipped. The latter includes scripted-model SIM workflow checks; it does not turn this
language study into an end-to-end hosted recovery result. No real refunds or shipments
were performed by this text-only study.

## Next candidate and limits

Keep the same authored references, strict parser, customer action authority, complete
scheduled denominator and acceptance target. Prepare a separate candidate that gives
clear priority to unresolved choices, untrusted source attribution and non-refund schema
coherence. The owner selected Gemini only. The separate proposal reuses the existing
bounded gateway for at most two transient attempts within each 30-second logical request.
It records both raw attempts and the final user-visible outcome. It does not retry valid
wrong answers or invalid semantic output. This changes the prompt and operating policy
together, so it cannot isolate a causal improvement to either one.
Do not reuse old failed slots as successes or send new requests without exact approval.

A passing future demo score would still not prove independent natural-language truth,
population confidence or safe real-money operation. Card-free hosting accounts, durable
public runtime admission, encrypted off-host backup and measured hosted recovery remain
separate work.
