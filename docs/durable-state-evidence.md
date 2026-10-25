# Independent durable-state mechanism evidence

Inspected base: merged #104, `437e76277794c88e227a90019d91188a6bbd8b99`.
This extension on `codex/release-durable-state` prepares #33/#38/#45. The functions
below measure already-required state and duplicate invariants; no release limit is relaxed.

## What the evidence establishes

| Existing criterion | Observed evidence | Decision and limit |
| --- | --- | --- |
| Olist commit recovery | Parent-observed child exit and before/restarted/duplicate SQL | Reject wrong rollback/commit delta or receipt; one selected boundary per drill |
| CFPB review durability | Scoped case, job, event and command rows | Reject absent/extra/wrong queue effects; no classifier or privacy credit |
| Revenue exact state | Whole isolated fixture records, proposals and receipts | Reject unrelated changes, wrong expected amount/reviewer or duplicate effects; SIM invoice correction only |

These are guardrails, separate from quality and operational metrics. That separation follows
[Langfuse's evaluation guidance](https://langfuse.com/academy/evaluate/choosing-what-to-evaluate).
They are not silently inserted into the partial H10 adapters. Those adapters still report
unobserved required fields as scorer errors. A future complete study must bind observations
to its scheduled cases, candidate, protocol, fault plan and complete source inventory.

## Private artifact boundary

[`save_state` and `read_state`](../harness/src/agent_harness/state_evidence.py) write one
exclusive canonical `state.json` and require its separately retained byte digest on read.
The reader checks exact inventory, symlinks, byte pin and canonical serialization before
constructing a strict typed contract. Editing the JSON and computing a new hash is not
independent evidence: the caller must retain the original pin outside the artifact.
The helpers do not connect to SQL, dispatch models, approve actions or decide release.
Keep these artifacts outside Git; application state may contain private values. Windows
directory mode is not an ACL guarantee; use the operator's protected private directory.
The trusted collector and installed oracle remain in the trust boundary. These artifacts
are not signed attestations or complete H10 source-pinned studies.

## CFPB: reconstruct the permitted queue delta

[`collect_queue`](../projects/cfpb-triage/src/cfpb_triage/state_evidence.py) opens a read-only,
repeatable-read transaction for one explicit tenant/case. It reads case/version/status,
jobs, events and command receipts. Complaint, taxonomy, policy, provenance, reviewed import
reference and previous classifier result become one immutable content pin; raw narrative
is not exported. Event timestamps are omitted; job lease expiry remains visible.
Sessions and account credentials are never queried. This is an observation collector for
trusted test composition, not an authenticated API. The caller supplies the authorized scope.

`assess_queue(evidence, principal, case, command)` requires enqueue capability, exact tenant/
case/starting version and a new command/event identity. It builds the expected delta directly:
increment version, set review_queued, obsolete pending/leased jobs, add one command with the
canonical command hash and resulting version, and one review event with actor and reason.
All other captured values must stay unchanged. After, reconstructed-store and duplicate
observations must equal that exact state. A worker is intentionally not running concurrently;
this narrow scenario cannot stand in for classifier routing, all races or tenant-wide privacy.

An invented execution starts case version1, enqueues `saved-review`, reconstructs DeskStore,
redelivers the same command and observes version2 with exactly one command/event. Missing
commands/events, changed source/result pin, stale expectation and a viewer principal fail.
The source store's `enqueue` method is never used to compute the expected delta.

## Revenue: preserve all fixture rows and the original receipt

[`collect_operations`](../projects/revenue-integrity/src/revenue_integrity/state_evidence.py)
reads the entire **disposable SIM fixture database** in one read-only, repeatable-read view.
Never give it a shared or production database. Record identity/kind/version SQL columns must
match their typed JSON documents. Proposal columns must match the embedded command and its
digest; ledger identity, ledger ID and compensation reference must match its receipt.
Reading only the application's filtered projection could hide an unintended extra effect,
so this collector deliberately observes all fixture records/proposals/receipts.

`assess_invoice` accepts a separate InvoiceExpectation: exact command, operator grant,
different reviewer ID, committing run and independently supplied expected amount. It requires
a fresh approved proposal and available invoice facts; checks the existing100.00SIM absolute
correction cap; constructs the target's expected amount/version change; and validates the
receipt's before/after, actor, reviewer, run, ledger ID and approval time interval. It never
calls the production `reconcile`, `propose` or `apply` methods to create the expected amount.
The other records and all proposals stay unchanged; exactly the observed, validated receipt
is added to the ledger. Restart and redelivery must preserve that entire state and receipt.

The test independently specifies10000SIM minor units for an invented9000 invoice, performs
the approved operation, reconstructs OperationStore and redelivers it. Altered unrelated
accounts, missing committed state, wrong actor/run, self-review expectation, missing capability
and an indexed version that disagrees with JSON all fail. This scenario does not test original
contract extraction, authorization attacks against a running agent, compensation or process
death. Passing it establishes no real recovered revenue or complete Revenue release.

## Olist: distinguish rollback from commit

[`collect_crash`](../projects/olist-support/src/olist_support/crash_evidence.py) now accepts
`crash_stage="before_commit"` or its existing `after_commit` default. An owned child exits23
at that exact hook. For before-commit, PostgreSQL must roll back the refund, budget and ledger
transaction; the parent's immediate snapshot must equal before-state. Restart resumes the
durable policy checkpoint with `NoSecondDispatch`, commits once and charges the restart run.
The independent label/state oracle therefore uses that restart run identity for the final
expected receipt/budget. Redelivery cannot charge either run again.

Before-commit evidence uses `olist-operator-process-crash-v2` and a required before-boundary
observation. Existing v1 after-commit bytes omit the new optional field and retain their
original pins. Validation rejects mixed boundaries or implicit relabeling. The inherited
`committed` snapshot name means the immediate post-exit observation; for v2 it must show
rollback, not a committed effect. The parent must reap the worker before dropping state;
WorkerCleanupError still requires preserving the database. No model gateway is passed.

## Verification and interview exercise

```powershell
uv run --locked --all-packages python -m pytest tests/test_state_evidence.py tests/test_crash_evidence_versions.py tests/test_domain_recording.py -q
uv run --locked --all-packages python -m pytest tests/integration/test_release_state_evidence.py tests/integration/test_olist_crash_evidence.py -q -o "addopts=--strict-config --strict-markers"
```

The focused tests use invented inputs. Hosted full regression, Postgres and package checks
provide final exact-tree acceptance, recorded on the review PR. Explain why after-commit
recovery preserves the original run receipt but before-commit recovery creates a restart-run
receipt; why an application snapshot alone may miss another changed resource; and why these
guardrails still cannot answer whether the model chooses the correct action on unseen cases.
