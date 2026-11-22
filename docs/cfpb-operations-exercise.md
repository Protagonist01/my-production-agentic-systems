# CFPB complaint operations exercise

This exercise pairs publicly available CFPB intake metadata with archived text and a
scripted reviewer. It uses the existing protected evaluation desk and an isolated
PostgreSQL trial. Its results measure the handling of the exercise workload. A
company pilot still requires an approved live intake and an operator accountable for
real case decisions.

| Input | Role in the exercise |
|---|---|
| Public CFPB API | Recurring bounded samples, durable intake receipts and duplicate detection. A metadata-only row reaches the desk with a clearly marked placeholder and stays pending. |
| Prepared CFPB archive | Privately replay development text with one case per declared group. Publisher categories stay outside the desk. Archived cases await independent review. |
| Authored fixtures | Exercise normal classification, out-of-scope triage, missing detail, a missed escalation corrected by the reviewer, provider failure and unresolved work. |

The CFPB announced the end of narrative publication in the public database in August
2026. Published records can arrive after the company has responded. Use the
[public API](https://cfpb.github.io/api/ccdb/api.html) for metadata and the existing
[pinned archive](data/cfpb-source.md) for replay text. See the
[CFPB announcement](https://www.consumerfinance.gov/about-us/newsroom/the-cfpb-to-cease-discretionary-publication-of-complaint-narratives-and-visualizations/).
The poller persists only a hashed public case ID, receipt date and aggregate poll
receipt. A hash provides a repeatable key. Treat the journal as private.

## Run intake and replay

Use the repository's locked workspace and choose private paths outside Git. The default
poll samples 25 results in a rolling 30-day receipt window. Both explicit date bounds
are inclusive in observed service responses. The command refuses malformed and partial
search responses and reports whether the returned sample covered the window. Schedule it
through the selected host's scheduler for repeat operation, with that host's logging and
failure handling. Repeated runs preserve the same journal. The date window is a sampling
boundary, and publication delays can cause earlier records to appear on later polls.

```powershell
uv run --locked --all-packages python cfpb_public_feed.py --journal D:/private/cfpb/intake.sqlite
uv run --locked --all-packages python cfpb_public_feed.py --journal D:/private/cfpb/intake.sqlite
```

Start an isolated local Postgres workspace using the project's documented
[database setup](local-postgres.md). Use this checkout for `--workspace` if it owns that
running service. The exercise creates a new trial on that server and removes the owned
trial when it finishes. Optional archive input requires the original prepared directory
and its externally retained byte hash. Omit both archive flags for invented-only replay.
Omit the journal flag to leave out live metadata. The result path must be new.

```powershell
uv run --locked --all-packages python cfpb_operations_exercise.py --workspace . --journal D:/private/cfpb/intake.sqlite --public-count 3 --archive D:/private/cfpb/prepared --archive-sha256 EXTERNAL_MANIFEST_HASH --archive-count 3 --report D:/private/cfpb/exercise.json
```

The preparation tool verifies the stored manifest and both database inventories before
selection, then rechecks their bytes after the selected text is read. It selects
development rows across distinct source groups. It imports no labels into the desk.
The two arms enroll the same workload under separate scripted accounts. The worker
publishes only fixture decisions through the normal lease and publication fences.
Reviewers sign in through the actual API, then accept a disposition or spend time
correcting the deliberately wrong routine routing. An intentionally unavailable
worker response goes to review. Retrying the final command returns the same receipt.
The trial uses actual database transactions and in-process HTTP requests.

## Read the report

The queue includes unresolved arrivals in both denominators. A review-only disposition is
a triage result. Consumer resolution, complaint truth, escalation recall on archived text
and labor savings require separate evidence. The synthetic clock measures assumed handling
and queue time. The machine wall time measures this one local run. Cost and observed human
savings are null. Zero provider calls are recorded. No live routing policy is fit by this
exercise. The PostgreSQL integration test runs the same path with invented data so hosted
CI can verify the mechanics without accessing private archives.

The next operational measurement is a run on the chosen evaluation host with sustained
arrivals, restart and an independent fresh-queue alarm. Real company deployment still
requires an authorized case feed, accountable operators, measured human effort and the
release evidence in the [CFPB release issue](https://github.com/Protagonist01/my-production-agentic-systems/issues/38).
