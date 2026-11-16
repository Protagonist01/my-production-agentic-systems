# Deferred model comparison: transparent cost scenarios

The owner selected **Gemini3.5Flash-Lite only and local Docker** on November16,2026.
The OpenAI comparison below is informational and deferred. It is not a provider
grant, key request, purchase or approved change to the existing Gemini ledger.

Official rates checked November16,2026:

| Model | Uncached short-context input / million tokens | Output / million tokens |
| --- | ---: | ---: |
| GPT5.6Luna | USD0.20 | USD1.20 |
| Gemini3.5Flash-Lite paid | USD0.30 | USD2.50 |
| Gemini3.5Flash-Lite eligible Free | USD0 | USD0 |

Sources: [OpenAI model page](https://developers.openai.com/api/docs/models/gpt-5.6-luna),
[Google pricing](https://ai.google.dev/gemini-api/docs/pricing#gemini-3.5-flash-lite).
Account/model availability and Free eligibility are not established by pricing pages.

Formula: requests × (input tokens × input rate + billed output tokens × output rate)
÷1,000,000. Reasoning is included in billable output. No caching discount is assumed.

| Luna workload | 2,000input/512output per request | 10,000input/2,000output per request |
| --- | ---: | ---: |
| 168requests | USD0.1704192 | USD0.7392 |
| 1,000requests | USD1.0144 | USD4.40 |
| 1,000seven-criterion cases /7,000requests | USD7.1008 | USD30.80 |

These are arithmetic estimates, not bills or caps. Longer notes, reasoning, failures
and repeat studies change usage. Hosting, storage, taxes, minimum credit purchase and
optional tool fees are excluded. The earlier168call development capture used88,684input
and11,749output tokens; the same counts priced at Luna rates would be aboutUSD0.03184.
That is a hypothetical repricing, not a forecast of Luna tokenization/reasoning or
quality. No actual OpenAI request was made.

A future comparison should freeze the same synthetic inputs, policy, task instructions,
output contract and hidden constructed references, with explicit provider settings.
Measure full supporting citations, unsupported positives, conflict/missing evidence,
failures, latency and observed accounting; retain rules/always-review baselines and
unknowns. Exposed development cases can diagnose problems but cannot establish clinical
qualification. Do not count repeated criteria/trials as independent patient families.

The suggested USD5application-enforced budget and separate attempt limit were proposals
only. No paid calls, new free slots or route fallback follow. Resume comparison planning
only after the owner requests it; finish the Gemini/local-demo work first.
