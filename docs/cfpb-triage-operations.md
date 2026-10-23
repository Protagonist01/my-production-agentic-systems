# CFPB typed triage and private review desk

C3 #36 and dependent C4 #37 are implemented on `codex/c3-c4-cfpb-triage`, based on verified #84 main `95397c46e796768eb788d5eb5c82ba8b0442e02c`. They remain unmerged until user review and exact-main acceptance. [Source walkthrough](code-study-cfpb-triage.md), [aggregate experiment evidence](data/cfpb-triage-evidence-v1.json), [original source limitations](data/cfpb-source.md) and [prior provisional baselines](cfpb-risk-baselines.md) are separate records.

## What the classifier does

Pydantic AI 2.56.0 validates product, issue, priority, ambiguity, confidence and up to three exact quotes. A custom model calls the shared bounded gateway; it does not open another provider client. Trusted code requires each quote to occur exactly once, computes Unicode offsets and checks the exact taxonomy pair. This verifies textual support, not the truth of the allegation or correctness of the category. Consumer product/issue targets and provisional risk labels never enter the candidate input.

Cheap-first uses `gemini-3.5-flash-lite`, then `gemini-3.8-flash` only for otherwise clear routine predictions below threshold. Elevated/uncertain priority, ambiguity, invalid output and operational/budget failure require review. A failed attempt never triggers a second provider route. Always-strong is an independent comparison. The stronger route requires explicit shared-adapter/admission opt-in; existing callers retain their original model allowlist. Each run allows two calls, one attempt per call, full token-ceiling reservation and a 90-second outer deadline. No paid fallback exists. Free-project confirmation is an operator assertion, not independent billing verification.

`fit` accepts development cases only. It maximizes admitted development cases under the declared composite-error ceiling, breaking ties toward higher thresholds. The recorded 50% target review fraction is a reporting objective, not a constraint that can override error checks. The taxonomy is a development-observed subset: 11 products/131 pairs, bound to the official source/form manifest. Unobserved pairs require review. Confidence is a model feature, not a calibrated probability.

## Actual provisional pilot

The user approved 24 new cases: 12 development, 6 regression and 6 holdout, with half risk-keyword and half nonkeyword hash selection in each split, full narrative lengths 250–8000 characters and prior-pilot exact groups excluded. The private selection policy records the frame, seed and regex. This is a restricted stress pilot, not a representative sample. Exact-text grouping does not establish consumer or near-duplicate independence. Manual masking review found no additional personal identifiers; that is not a privacy certification. All 24 labels were sealed before candidate output: 9 routine/5 elevated/10 uncertain and 15 clear/9 ambiguous, under `cfpb-narrative-risk-v2-pilot`. They are AI-provisional, with no independent human validation.

Candidate v1 returned wrong evidence offsets and all cases required review. Preserve its 24-attempt development record. Candidate v2 changed only the evidence interface during development: exact quotes replace model-supplied offsets. Its fresh 24-attempt development record again yielded thresholds 1.01/1.01, admitting nothing. Freeze that policy before fresh regression/holdout; no tuning followed held-out output. Development metrics are counterfactual routing over independently collected cheap/strong attempts, not fresh executions of both pipelines.

Fresh held-out comparison completed every scheduled case in both modes. Both modes required review for all 6 regression and all 6 holdout cases: coverage 0%, review load 100%, selective error unknown because nothing was admitted. Regression's two provisionally elevated cases both reached review; holdout contains zero elevated cases, so its elevated recall is unknown. Strong-route rate limits and other provider failures remain in denominators. These results establish neither useful automation nor a model-quality, consumer-harm or savings claim. The 50% review objective was missed. The aggregate artifact distinguishes gateway exchanges, reported model calls, validation failures and unknown usage; zero observed tokens with missing usage is not zero consumption.

## Run the protected desk locally

Install the locked workspace with `python dev.py setup`; deployed package users need the `web` extra. Keep source narratives, labels, credentials, accounts and database service state outside Git. The existing shared `Workspace` service commands create a disposable Postgres trial. Copy the repository's `compose.yaml` into the chosen external service root, initialize its config, start it and create a named trial with the shared local-services CLI. No database schema is installed by an HTTP request.

Use the domain CLI as a trusted local operator:

```powershell
python -m cfpb_triage.desk_cli --root D:/private/cfpb-services --trial cfpb-demo bootstrap
python -m cfpb_triage.desk_cli --root D:/private/cfpb-services --trial cfpb-demo account --principal D:/private/reviewer.json
python -m cfpb_triage.desk_cli --root D:/private/cfpb-services --trial cfpb-demo enroll --tenant demo --complaint D:/private/complaint.json --taxonomy D:/private/taxonomy.json --policy D:/private/policy.json --review-ref reviewed-mask-v1 --provenance invented
python -m cfpb_triage.desk_cli --root D:/private/cfpb-services --trial cfpb-demo worker
python -m cfpb_triage.desk_cli --root D:/private/cfpb-services --trial cfpb-demo serve --port 8883
```

`Principal` contains username, tenant_id, actor_id, role (`viewer` or `reviewer`) and exact case_ids. Password provisioning prompts without echo. `ComplaintInput` contains only a SHA-256 case_id and narrative. The policy pins taxonomy and development-fit evidence. Input JSON paths must be outside every Git checkout; imports are bounded and require a masking review reference and original/edited/invented provenance. Do not label real source material invented. Trusted operators must actually perform the stated masking review; the string alone cannot prove it.

The default worker publishes a failure-to-review result without provider calls. To use the previously authorized Gemini configuration, add `--live-gemini --code-root <checkout>`; the ignored `.env.local` supplies `GEMINI_API_KEY` and `GEMINI_FREE_TIER_CONFIRMED=true`. Only use source exports with appropriate rights and privacy authorization. Source revision, dirty status and lock are pinned. The worker takes one durable job per invocation; scheduling is an operator responsibility.

## Persistence and access boundaries

Postgres owns case versions, jobs, fixed events and command receipts. Import atomically enrolls a case and job. Claim uses SKIP LOCKED with a five-minute lease; publication rechecks current case version, live lease and exact narrative/taxonomy/policy pins. Expired workers cannot overwrite a later result. After three claimed assessment attempts, the next claim publishes review without another provider call. A hard child-process exit after claim was recovered in the real Postgres test. Provider dispatch is at-least-once across process loss; business publication is fenced, not a promise of exactly-once model billing.

Reviewers can enqueue a fixed reason against an expected revision. The tool binds identity and case before accepting a command. Identical command retries return the stored receipt before stale-version rejection; rebinding the same command ID to different content fails. Enqueue increments the case revision and obsoletes pending/leased assessment work. It does not dispatch another model or resolve a complaint. The stored prior assessment remains visible with the new queue status. Viewers cannot enqueue; neither role can perform account actions.

HTTP binds loopback, exact Host/Origin, opaque hashed sessions, CSRF tokens, 30-minute expiration, bounded request bodies and a self-only content policy. Disabled accounts stop working on the next request. Assigned-case membership and tenant scope are checked server-side; omitted UI buttons are not the access control. Runtime roles cannot delete event history. Local operators/database owners remain trusted. This is a protected local demo, not an Internet deployment or a complete security audit.

Actual SQL-backed Edge checks verified revision 2 after enqueue, durable history, viewer POST 403, unassigned GET 403, absent viewer controls, private-state clearing on logout and no horizontal overflow at 1440/390 pixels. Screenshots use an explicitly invented consumer-free record. The three browser console 403s were the initial signed-out session and the two intentional denial probes; there were no JavaScript exceptions. Shipped JS also has deterministic stale-response/login/logout regressions.

## Traces and distribution diagnostics

The optional live-worker `--langfuse` flag reads explicit `LANGFUSE_BASE_URL`, `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` from the same ignored configuration. It composes the H8 `TraceSession`/`TracedGateway`/`LangfuseExporter` path, with a new private HMAC key per run and bounded synchronous export. Automatic Pydantic AI prompt capture is disabled. Traces contain run/agent/node/model hierarchy, fixed counters and HMAC input/model/version references; no narrative, quote, case identifier, raw response, credential or hidden target is exported. HMAC model references prevent backend model-name price inference; unknown costs remain unknown. Export health is separate from classifier success. An invented zero-provider probe exported successfully to the existing local backend and independently read back all four observations using pinned Langfuse CLI 1.2.4, verifying hierarchy and absent narrative/credential canaries. This proves the mechanism for that probe, not live pilot trace coverage or production observability. An accepted queue response alone is not durable read-back.

`GET /api/diagnostics` returns only the signed-in account's aggregate profile. Trusted operators can compare the same assigned scope against an external reference profile:

```powershell
python -m cfpb_triage.desk_cli --root D:/private/cfpb-services --trial cfpb-demo diagnostics --principal D:/private/reviewer.json --reference D:/private/reference-profile.json --output D:/private/diagnostic.json
```

The output path is exclusive. A total-variation distance of at least 0.2 flags category, length, marker-language, mask density, model or provider distribution changes. Empty dimensions say insufficient data. Length bins are <500, <2500 and remaining characters; mask density >=10% is dense. English/Spanish token markers are heuristic signals and explicitly allow unknown. Profiles count proposed output products, not consumer reference targets; no accuracy or demographic conclusion follows from these alerts. Tests construct independent category/length/language/masking/model/provider shifts.

## Rollback and remaining gates

Do not point a different schema version at an existing desk database: bootstrap pins the DDL digest and fails on mismatch. Roll back code with its matching trial schema or create a new isolated trial; preserve private audit evidence before dropping a task-owned trial. No automatic migration or public deployment is included. C5 #38 still depends on O8 #33. Human-reviewed labels, representative samples, operational quota reliability, useful review-load tradeoffs and complete release evidence remain pending.


## Review acceptance record

[PR #94](https://github.com/Protagonist01/my-production-agentic-systems/pull/94) contains the unmerged C3/C4 bundle. The final executable snapshot passed the complete locked check: 924 tests in460.78s,136 typed source files,203 formatted Python files, both import contracts, lock and Ruff. All six packages built and the exact dependency audit found no known vulnerabilities. A fresh external web-only installation matched all23 CFPB module/schema/asset bytes, served its protected API/assets, denied signed-out case access and consumed all6 invented replay calls with zero provider calls under strict network denial. Google/Langfuse SDKs and other vertical packages were absent. Windows' in-process API loop requires an internal socket pair, so strict network denial applies to the separate replay phase, after the API check. The non-failing Pydantic event-loop deprecation and local pytest-cache permission warning are retained. Earlier focused16/SQL5/browser/local-backend evidence remains valid; no source/SQL/asset bytes changed during the replay/documentation packaging. Hosted exact-head checks are recorded on the PR and issues before acceptance. Both issues remain open until user merge and exact-main verification.
