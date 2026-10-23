# Prior Auth: durable documents and protected review

Inspected branch `codex/p4-p5-prior-auth-review`, implementation `4ee75bc`, October 23, 2026.
Later fixes/evidence are recorded in the PR and [operations](prior-auth-review.md). This is an
unmerged P4/P5 slice; source/criterion logic is covered in [P1–P3](code-study-prior-auth.md).
Clinical validation, production hosting, P6 and O8 release acceptance remain excluded.

## Follow a document arrival

`review_cli.main` composes an isolated workspace/trial. Trusted bootstrap runs `setup_review`,
which hashes packaged `review.sql`, locks migration setup, refuses changed applied schema
and grants only domain-specific runtime privileges. Account provisioning stores a closed
`Principal` and salted PBKDF2 hash. The role and exact case allow-list come from this account,
never the HTTP command or model. `Principal.require` delegates the exact resource check to
the shared harness; no cross-domain imports are used.

`ReviewStore.enroll` writes pinned redacted note/policy, version 1 and a pending full assessment
in one transaction. `ReviewWorkflow.step` first expires due waits, then claims one SQL job.
`claim` uses skip-locked selection and a random five-minute lease. It does not lock a case
after locking its job: that reverse order would conflict with case-first policy/document writes.
MVCC reads the matching version, or marks the job obsolete. Claiming work commits before
model execution, so a slow provider does not retain a case lock.

`live_assessor` builds shared admission/transport controls, a fresh run ID and bounded context.
`extract(..., criteria_subset=keys)` uses the unchanged structured criterion prompt for only
the selected IDs. Expected labels are absent. The worker verifies returned note/policy/case
pins and exact requested IDs, combines stored unaffected claims and calls `assess` again.
`finish` locks the case then job, requires current version, unexpired matching lease and
leased status, and atomically publishes result/status plus one assessment event. A stale
result returns false; it cannot replace a newer policy or document decision.

Now suppose the reviewer requests education evidence. `request` checks the current version,
future deadline and role, stores a stable command digest and increments the case version.
`deliver` is called only by the trusted CLI after explicit redaction. The raw text never enters
the database. The redacted supplement is appended after a separator, so earlier offsets remain
valid. Requested IDs plus recall terms found in the supplement determine the invalidated set.
The old result is cleared immediately. Retained candidate claims exclude invalidated IDs;
a new job is queued at the new version and older jobs become obsolete in the same transaction.
The full support checker still scans current visible text for its represented contradictions.

Repeated delivery finds its receipt before comparing current version. Equal canonical payload
returns the original resulting version; changed payload under the same identity fails. This
ordering permits safe retry after an ambiguous response. The receipt includes actor identity,
so another reviewer cannot take over an earlier command ID. Timeout and policy replacement
have separate fixed events. A late document needs an explicitly renewed wait.

## Follow a browser action

`review_api.create_app` rejects non-loopback configuration and exact Host/Origin mismatches.
The session cookie is HttpOnly/SameSite Strict; mutations additionally require the session's
CSRF header. Errors return fixed text without validation bodies. Document-request JSON is
revalidated in strict JSON mode after authentication, preserving closed tuple/datetime semantics.
The endpoint passes a server-authenticated principal to the store; a supplied tenant/role field
is rejected. Reads serve only assigned tenant/case state. The only mutations are request documents,
review routing and session lifecycle. Raw delivery/policy changes are absent from HTTP.

`web/console.js` constructs source/evidence content with textContent. No note is HTML. Session
epochs and selection counters prevent old responses repainting a new case or logged-out view.
`signOut` clears private DOM immediately; its request is serialized only with authentication,
not a potentially stalled case read. A denied session clears the visible private state.
`tests/prior_auth_session_test.cjs` exercises the actual asset under controlled late responses,
including logout during a stalled initial load and session expiry.

## Evidence, limitations and interview exercises

- **Verified mechanism evidence:** 29 focused tests and seven isolated Postgres tests passed.
  The SQL suite includes a child process terminating after claim and a later lease recovery,
  concurrent document retries and a policy update before stale publication. Full/hosted counts
  belong in the PR after they actually finish.
- **Observed provider failure:** the first invented fresh workflow probe timed out on its first
  request. It produced qualified review with no supported findings. This is preserved as failed
  model output, not counted as correct reasoning or folded into P3's prior holdout result.
- **Design limitation:** leases deduplicate canonical publication, not provider dispatch. Crashed
  workers can repeat calls. After three attempts, processing routes to qualified review without
  another dispatch. Delayed scheduling can delay timeout events, so a deployment needs an owned
  worker/scheduler and monitoring.
- **Design limitation:** selective invalidation uses declared requested IDs and narrow recall
  terms. It is not general medical semantic dependency tracking. Adding new policy logic requires
  reviewing that invalidation dependency map as well as the support checks.
- **Privacy trust boundary:** initial redacted input and explicit redaction mappings are reviewed
  by the trusted operator. There is no general PHI detector, real-patient ingress or claim that
  a complete source record is automatically sanitized. Events use fixed projections and the graph
  disables automatic external tracing; this is not an exhaustive privacy/security audit.
- **Not assessed:** clinical utility, qualified adjudication, production hosting/TLS, real-world
  authorization and payer-local coding rules. P6 remains a separate release issue.

Explain why a SQL lease must be checked again after a successful model call. Trace how policy
replacement changes the case version and obsoletes the old job. Then compare an expired worker
and duplicate document delivery: one refuses publication while the other returns a receipt.
For a scale change, discuss tenant scheduling fairness, bounded queues, lease renewal and
independently reviewed medical dependency rules without weakening current version checks.
