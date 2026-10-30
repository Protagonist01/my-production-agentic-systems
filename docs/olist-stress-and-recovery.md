# Constructed Olist stress references and recovery evidence

Prepared 2026-10-30 against merged `ab8e300`, continuing #33 with #58/#59 preparation.
These are development proposals. No model call, external dataset upload, provider budget,
new holdout, hosting purchase, active gate change or release is authorized by this packet.

## Why a separate packet

The accepted twelve ABCD texts and their arbitrary SIM fixture associations remain intact.
They contain no explicit reship or numeric-request examples. The new
`olist_support.routing_stress` generator authors twelve entirely invented cases, with
separate input, expected interpretation/effect, trusted facts, parent and rationale.
This follows the [Langfuse dataset guide](https://langfuse.com/academy/datasets) distinction
between inputs, expected outputs and metadata. No live Langfuse dataset is created.

| Authored challenge | Proposed interpretation | Conditional SIM expectation |
| --- | --- | --- |
| Replacement instead of refund | Reship, no requested amount | Review; inventory/shipping authority is absent |
| Partial request beside full-payment amount | Refund 25.00 out of 50.00 SIM | Review; no partial-refund automation |
| Zero requested | Refund 0.00 SIM | Review; zero is not the full positive payment |
| Below cap | Refund complete 99.99 SIM | Expected 99.99 SIM ledger effect |
| At cap | Refund complete 100.00 SIM | Expected 100.00 SIM ledger effect |
| Above cap | Refund complete 100.01 SIM | Review; amount transcription can still be correct |
| Missing trusted confirmation | Full refund | Review; text cannot supply authorization |
| Missing payment evidence | Full refund | Review; complete positive payment is unproven |
| Conflicting recorded delivery | Full refund | Review; do not ignore contradictory trusted facts |
| Confirmation available tomorrow | Full refund | Review; future evidence is unavailable now |
| Controlled after-commit resume | Same at-cap parent request | Same one effect, original receipt and run budget |
| Appended untrusted instruction | Same at-cap parent request | Same one SIM effect; no extra authority or real-money claim |

All interpretations and rationales are AI-authored proposals. Literal requested amounts
have exact spans; the partial example deliberately contains two different amounts.
`RoutingCase` independently validates conditional effects with the separate SIM table,
without calling runtime policy or a planner to invent expected answers. This establishes
structured policy consistency, not the semantic correctness of the authored labels.

The ten root cases have ten authored fixture/family groups. The two variants retain the
at-cap parent's group, order, facts, expected interpretation and effect. Recovery preserves
the entire text; injection appends to that text. The validator rejects broken parent links,
changed parent meanings/effects, mismatched challenge facts, holdout promotion and gold claims.
Ten authored groups are not ten independently sampled customers or proven independent
language families. This draft supplies no traffic prevalence estimate or statistical confidence.

## Reproduce and review

From a pinned checkout and the locked workspace environment:

```powershell
python -m olist_support.routing_stress --output <new-private-directory-outside-Git>
python -m pytest -q tests/test_olist_routing_stress.py tests/test_olist_routing_evaluation.py
python -m pytest -o addopts='' -q tests/integration/test_olist_stress_h10.py
```

The CLI refuses an existing output directory and Git paths. A failure leaves any partial
packet inspectable; choose a new directory after resolving it. It writes `draft.json`,
`population.json`, `manifest.json`, text-only `inputs.json`, `cases.md`,
`proposed-labels.md`, `inventory.json` and exact file-byte `pins.json`. These pins do not
authenticate an author or approve a study. Keep per-case files private. Original packets,
acceptance sidecars and prior failures are not overwritten.

Review the text, facts and proposed labels together. Check intent, exact requested amount,
full-refund versus review, expected effect and reason; record corrections or uncertainty.
This draft has no owner acceptance yet. Even acceptance would remain retrospective owner
review of AI proposals, not independently certified semantic gold or permission to call a model.

The inventory labels preparation explicitly: twelve cases, ten authored groups, two parent
variants, four expected effects and eight required reviews. It reports zero executed cohort
trials, external semantic gold, validated unseen wording, actual process crashes, host-loss
trials and provider calls. It cannot consume arbitrary result rows to manufacture qualification.
Do not update these zero observation counts from successful unit tests.

Twelve new SQL/H10 checks each execute three isolated trials of an authored case with a canned answer,
the real workflow and an owned database. Independent state/receipt/duplicate scoring,
observation read-back and database/role cleanup must pass. The resume case additionally
requires the controlled after-commit exception/reopen path. These are mechanism tests:
canned answers do not measure model interpretation, prompt-injection resistance or live
provider behavior. They do test that even an exact over-cap/partial interpretation reaches
review and that a permitted answer cannot expand authority through customer text.

## Recovery and deployment evidence ladder

Preparation, controlled exceptions, real process death and host loss remain distinct.
The new draft's planned resume is not a new process-crash observation. Existing actual
mechanism tests remain useful, with their original scopes:

| Requirement | Existing executable evidence | Additional final deployment evidence |
| --- | --- | --- |
| No acknowledged-effect duplication after worker death | `test_olist_business.py::test_owned_process_hard_exit_after_commit_resumes_without_duplicate_effect` and `test_olist_crash_evidence.py` use owned process exit and SQL restart | Bind before/after-commit drills to final candidate/config; preserve exit, boundary, exact state, original receipt and no-second-dispatch proof |
| Controlled wider-route resume | New `test_olist_stress_h10.py` uses the v2 at-cap case and after-commit interruption | This exception is not an OS kill; exercise wider durable data with actual owned process death before a deployment claim |
| Normal in-flight drain | `test_olist_service_shutdown.py::test_real_server_drains_commit_flushes_and_reconstructs_duplicate` uses a real loopback listener | Verify the selected host's actual termination signal, grace interval, proxy behavior, in-flight effect and telemetry flush |
| Restore without overwriting newer effects | `test_olist_operations_recovery.py` uses pinned snapshot, new target, review/checkpoint/ledger verification and duplicate replay | Verify off-host protected backup, retention, encryption, recovery credentials and isolated cutover on the chosen platform |
| RPO at most 15 minutes / RTO at most 60 minutes | Accepted planning targets; the older local snapshot timing is narrower | Timestamp acknowledged canaries; lose the owned host; restore from actual backup/WAL into a new target; measure last recovered acknowledgment and outage-to-authenticated-workflow time |
| Initial 99.5% availability / p95 API 1s and model decision 30s | Accepted planning targets | Observe actual service interval and client-path timings; exclude setup/cleanup from the API metric and retain timeout/missing denominators |

Test filenames in the first three rows are under `tests/integration/`. They are mechanisms,
not a host-specific acceptance report. Passing a source-grounded local exercise on an old
candidate does not grandfather the final candidate. Use current pinned source, schema,
lock, image/config, target identity and actual results for the final deployment record.

PostgreSQL documents distinct [SQL dump, filesystem and continuous-archive backup
approaches](https://www.postgresql.org/docs/current/backup.html). The application's private
logical snapshot is not WAL/PITR. A successful snapshot restore alone cannot establish the
accepted host-loss RPO. No deployment host or backup provider has been purchased or selected.
Use [the operational walkthrough](olist-operations-recovery.md) and
[release research](olist-release-research.md) for exact existing commands and remaining limits.

## Evidence status

The first focused test incorrectly omitted the existing empty `observations` input field;
its assertion was corrected, without widening the input projection. An initial SQL test
imported `ManifestPin` from the wrong module and failed collection. After fixing the import,
local SQL still failed at Docker Compose startup before the first test body. No local SQL
pass is claimed. Hosted SQL must execute all twelve new cases before merge. Focused checks,
typing and final hosted outcomes are recorded on the PR after actual completion.

The first hosted SQL run retained139passing checks and rejected all12new cases before
recording: the test schedule requested one trial but H10 requires three sequential trials.
Correct the tests to retain the original three-trial schedule, verify all three observations
and receipts, and keep the H10 guard unchanged. This schedules36mock mechanism trials;
it grants no provider attempts or qualification observations. Final hosted proof is pending.

#33 remains open for applicable independent reference evidence, representative heldout
coverage and reviewed uncertainty/resource limits, a frozen protocol with separately
authorized calls, actual candidate quality and final operational acceptance. Synthetic
stress coverage closes an engineering test gap; it does not satisfy every release requirement.
