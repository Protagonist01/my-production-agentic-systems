# Prior Auth document waits and reviewer desk

P4 #49 and P5 #50 are one user-authorized dependent batch on
`codex/p4-p5-prior-auth-review`, based on verified main `6c2b7d9` (merged #92).
The [P1–P3 source and evaluation limits](prior-auth-evidence.md) still apply. This is a
local illustrative evidence-review system. It has no authorization, denial, treatment,
email or external document-provider tool. P6 clinical/domain release is not completed.

## State and recovery

Postgres schema `prior_auth_app` owns case versions, pinned redacted notes/policies, candidate
and checked findings, document receipts, review events, waits and assessment jobs. Bootstrap
pins immutable schema bytes. Runtime cannot delete review history or change account grants.
Accounts, tenant identity and exact case allow-lists are provisioned by a trusted administrator.
The browser never chooses authority.

Initial enrollment atomically queues a full seven-criterion assessment. A reviewer may then
route for qualified review/information or request named documents with an explicit aware
deadline (future, at most 90 days). There is no default clinical deadline. A bounded worker
step reconciles up to 100 expired waits and claims at most one assessment job. A scheduler
must invoke steps for unattended operation; browser reads do not run model calls or timers.

Supplemental delivery requires a current, unexpired wait and an expected case version. The
trusted import appends reviewed redacted text without moving earlier character offsets.
It invalidates requested criteria plus criteria whose recall terms occur in the supplement;
an empty selection conservatively invalidates all. Remaining exact claims may be reused
against the unchanged prefix; the full P3 checker still checks visible contradictions/rates.
This selection shares the narrow grammar's limits, not general medical change detection.
Policy replacement invalidates every finding and supersedes outstanding work/waits.

Document/review commands have stable IDs and canonical payload digests including actor identity.
Repeating the same ID/payload returns its recorded version, even after later progress. Reusing
an ID for different content fails. The database locks the case before mutating state and records
its event/receipt/job in one transaction. A timeout creates one qualified-review event. A late
document needs a reviewer-created renewed wait; it cannot silently revive an expired request.

A worker lease lasts five minutes. Model work runs outside the database transaction with a
four-minute gateway deadline, one attempt per selected criterion and at most seven calls.
Lease ownership and exact case version must still match at publication. An expired/replaced
worker cannot publish even if its model call succeeded. A hard crash can repeat provider calls
after recovery; canonical publication/events are deduplicated, provider execution is not
exactly once. After three claimed assessment attempts, another step publishes qualified review
without calling the provider. Invalid/missing provider output also routes to qualified review.

LangGraph composes reconcile → assess → publish. SQL remains the durable state; no graph memory
is trusted as a persistent checkpoint. Automatic LangSmith tracing is explicitly disabled around
the graph. Domain events contain fixed reasons, states, criterion IDs and times, not note text,
model rationales or credentials. The same shared bounded Gemini gateway is used for explicit
live worker calls; no paid fallback is available.

## Local operation

Use `python dev.py setup`, Docker, an external private source directory and an isolated trial.
The base Prior Auth package still supports source preparation without web/model dependencies.
For the desk install `production-agent-prior-auth[web]`; live work also needs the harness Gemini
extra and the approved ignored `.env.local` values. All extras pin the existing dependency versions.

```powershell
python -m prior_auth.review_cli --root . --trial prior-auth-review bootstrap
python -m prior_auth.review_cli --root . --trial prior-auth-review account --principal D:/private/reviewer.json
python -m prior_auth.review_cli --root . --trial prior-auth-review enroll --note D:/private/redacted-note.json --policy D:/private/policy.json --review-ref reviewed-map-v1
python -m prior_auth.review_cli --root . --trial prior-auth-review worker --live-gemini
python -m prior_auth.review_cli --root . --trial prior-auth-review serve --port 8881
```

Account provisioning prompts privately for a 15–128 character password. A principal has
`username`, `tenant_id`, `actor_id`, `role` (`reviewer` or `viewer`) and exact `case_ids`.
No wildcard grant exists. A viewer reads assigned evidence but cannot request documents or
record a review route. There is no public registration endpoint. Serve binds to loopback only,
uses opaque expiring sessions, hashed tokens/CSRF, sign-in admission limits, exact Host/Origin
checks, no-store headers and a self-only content policy. Production hosting/TLS is separate work.

In the desk, select a case; inspect seven findings and exact cited note spans. Expand policy
provenance/source quotes and the reviewed note. The request form requires selected criteria and
an explicit local date/time; the browser sends an aware timestamp. Record qualified review or
request information with a fixed reason. Current version checks reject stale actions. Refresh
after a worker step. The history distinguishes document requests, arrivals, expirations,
policy changes and completed assessments. Evidence complete for review is never clinical approval.

Import an arriving supplement through the trusted CLI after reviewing every identifier span:

```powershell
python -m prior_auth.review_cli --root . --trial prior-auth-review document --username reviewer --case case-1 --version 2 --delivery-id received-document-1 --raw D:/private/supplement.txt --redactions D:/private/redactions.json --review-ref reviewed-map-v2
python -m prior_auth.review_cli --root . --trial prior-auth-review worker --live-gemini
python -m prior_auth.review_cli --root . --trial prior-auth-review policy --username reviewer --case case-1 --version 3 --input D:/private/reviewed-policy.json
```

`redactions.json` contains closed `Redaction` objects: kind and an exact source span with
half-open Python Unicode start/end and original quote. The CLI masks those characters before
storing or modeling text. It does not automatically detect PHI. An empty mapping is a deliberate
review assertion, appropriate only when the illustrative input has no identifiers. Raw files,
redaction maps, source records and evaluator labels must stay outside Git. Initial enrollment
likewise requires already reviewed redacted `NoteInput` plus an explicit review reference.
Browser HTTP has no raw upload, document-attestation or policy replacement endpoint.

Omitting `--live-gemini` routes a claimed job to qualified review with failed assessment; this
is not a fake successful extraction. A plain worker step also processes wait timeouts. For a
controlled shutdown, stop the task's server and drop only its named disposable trial using the
shared workspace CLI. Do not reuse evaluation release output directories as mutable case stores.

## Verification so far

The focused source/API set passed 29 tests; seven actual Postgres tests passed in
124.95 seconds. These cover concurrent duplicate arrival, only affected-criterion reassessment,
wait expiration/renewal, in-flight policy invalidation, hard-process-exit lease recovery,
bounded attempts, tenant/role/session scope and canary exclusion from model input/events.
The Node regression executes the shipped browser code with delayed responses and verifies
private-state clearing on logout/expiry and a late denied response after a new sign-in.
Full locked regression passed 886 tests in 489.06 seconds, strict types over 122 source files,
lint/format and import checks. All six package builds and the dependency audit passed.
The first invented workflow probe recorded one gateway attempt and stored qualified review
with failed assessment and no supported findings. A later probe exposed missing Windows main
guards in the temporary scripts: child setup repeated before provider dispatch could be
established. These are preserved probe-startup failures, not provider/model-quality results.
The production CLI already has the correct guard. A corrected standalone education-only
check completed one actual Gemini request with no failure, exact accepted evidence and no
identifier canary in its captured exchange. It is not a full workflow or held-out quality run. Local browser continuation is pending restoration of Docker after
a host disk-space interruption; no full browser pass is claimed. Installed wheel and final
hosted results are added after actual execution. The rebuilt current web wheel matches all
21 source/resource files and imports/replays under network denial. An explicitly labeled
in-memory UI fixture
passed actual Edge document-request/routing/viewer checks and desktop/mobile visual inspection.
At 390px the document stays 390px wide; the 620px evidence table scrolls in a 314px container.
These UI-only checks do not replace the pending real local SQL/browser flow.
The [aggregate evidence](data/prior-auth-review-evidence-v1.json) keeps each evidence kind separate.
Initial hosted run39943225425 passed ten jobs, including886tests per quality cell and94Postgres
tests. Corrected implementation0d8c1ad then passed hosted39945068035 alltenjobs: actual logs
886tests per qualitycell and94Postgres, with identical tested/reviewed Git trees.
Later documentation-only checks remain visible on the draft PR.
The implementation remains in [draft PR #93](https://github.com/Protagonist01/my-production-agentic-systems/pull/93)
until local database-backed continuation is completed or explicitly resolved.

The lock metadata changed to `e261f8bcee3a14ab2061b79ea3a43a2ff3793e96607c97c286561b63730e9c4d`.
Explicit invented replay v10, captured at clean `4ee75bc`, has digest
`c3a6804a93739740a196a44aaed66af31a564faa6c1b9b61600b82386b985f08`.
All six request/response pairs equal v9, including two typed timeouts. V1–v9 remain immutable
and reject this lock. This fixture contains no source notes or provider-quality evidence.

See [the construction journal](../BUILD_BOOK.md#entry-36--durable-prior-auth-document-review)
and the [reviewer workflow walkthrough](code-study-prior-auth-review.md).
