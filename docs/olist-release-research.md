# Olist reference, evaluation and recovery package

Prepared 2026-10-30 against merged main `ca8bccf` for #33, with #58/#59 preparation.
This is a research-backed execution package and a conditional reference audit, not a
finished release qualification. No provider dispatch, hosted deployment or new spending.

## Research findings and resulting decisions

1. **Define the claim before choosing a score.** [NIST AI RMF Measure](https://airc.nist.gov/airmf-resources/airmf/5-sec-core/)
   calls for documented test conditions, uncertainty, benchmarks and deployment-relevant
   measurement. For Olist, separate language extraction, SIM policy application, durable
   effects and service recovery. A correct intent cannot excuse a duplicate effect.
2. **There is no universal acceptable AI error rate.** [NIST risk tolerance](https://airc.nist.gov/airmf-resources/airmf/1-sec-risk/)
   is use-case dependent. The targets below are proposals for our bounded SIM application;
   they are not statutory thresholds, industry certification or real-payment permission.
3. **Use a pinned dataset and keep hard cases without pretending they represent traffic.**
   [Langfuse datasets](https://langfuse.com/academy/datasets) distinguishes inputs, expected
   outputs and metadata. Retain source-order and wording-family grouping. Repetitions
   measure stability, not new independent coverage. No live dataset upload is needed here.
4. **A judge needs applicable references.** [Langfuse judge guidance](https://langfuse.com/docs/evaluation/evaluation-methods/llm-as-a-judge)
   recommends calibration against labels. Model agreement or matching a label's author
   does not certify meaning. Our independent SIM table answers only a structured question.
5. **Measure user outcomes and tail latency.** [Google SRE](https://sre.google/workbook/implementing-slos/)
   recommends explicit good-event/total-event indicators. Separate model completion from
   successful HTTP responses and safe review. An always-review system cannot win by
   avoiding all eligible actions. Proposed targets need actual load and operating data.
6. **Recovery is an exercised capability.** [AWS recovery objectives](https://docs.aws.amazon.com/pdfs/wellarchitected/2024-06-27/framework/wellarchitected-framework-2024-06-27.pdf)
   ties RPO/RTO to business impact. [PostgreSQL SQL dumps](https://www.postgresql.org/docs/current/backup-dump.html)
   provide logical snapshots; [PITR](https://www.postgresql.org/docs/current/continuous-archiving.html)
   requires a base backup and an unbroken WAL sequence. Our custom same-schema snapshot
   is neither `pg_dump` nor verified PITR. An archive alone cannot establish a 15-minute RPO.

These sources motivate the design; they do not endorse this implementation or certify
the numerical proposals. No dependency upgrade is required for this work.

## What the current references can establish

The original source has order/payment/delivery records, not observed support intent or
refund outcomes. The approved SIM policy supplies constructed business rules. A source
record cannot supply a missing intent label or prove a real refund was warranted.

`olist_support.reference_package` loads exact externally pinned evaluator/metadata bytes.
It verifies the exact text-only provider projection (no extra label/fact fields), then checks
one-to-one case membership, source manifest consistency, declared wording-family
split isolation, recovery declarations and required holdout slice declarations. It calls
`evaluation_oracle.evaluate_policy` for action and amount, conditional on evaluator-supplied
intent/requested amount/facts. It never calls runtime `policy.propose`, executes business
actions, reads credentials or invokes a provider. It does not certify the expected reason.

The existing accepted draft-v2 packet audits as follows:

| Observation | Actual result |
| --- | --- |
| Cases / source-order groups | 12 / 6 |
| Development / regression / holdout groups | 2 / 2 / 2 |
| Action and amount agree with separate SIM table | 12 / 12 |
| Oracle errors / disagreements | 0 / 0 |
| Required holdout slices declared | 8 / 8 |
| Recovery cases declared, not executed by this audit | 1 |
| Original label provenance | 12 AI-provisional labels; retrospective owner acceptance remains separate |
| Semantics, reason labels, actual family independence, fresh candidate quality | Not validated by this audit |

The aggregate is in [the audit report](data/olist-reference-package-v1.json). Passing all
structural checks means the packet is internally usable for further evaluation, not release
ready. Slice presence is a declaration, not evidence of adequate counts or correct assignment.
The 12 texts and assigned families are exposed regression material now; do not relabel them
as a fresh blind holdout. Preserve their original split fields and acceptance sidecar.

## Finish the reference package

Maintain three separate reference layers, with versioned provenance and applicability:

| Layer | Reference and check | Remaining boundary |
| --- | --- | --- |
| Intent and requested amount | Text-only input; independently recorded refund/reship/ambiguous/unsupported interpretation and exact minor units; disputed cases retained | Existing runtime schema only has refund/reship; ambiguity must be routed explicitly before a new cohort is frozen, not forced into a convenient label |
| SIM proposal | Independent table over trusted visible facts, full amount, cap, prior refund, unit and scope | Table agreement does not establish customer meaning or real-money correctness |
| Execution and recovery | Independently constructed expected SQL state, receipt identity, original-run budget, review ownership, restart and duplicate checks | Passing pure Python does not establish SQL, process-crash or host-loss behavior |

For each new semantic reference store author/method, timestamp, rubric version, source
span or explicit textual rationale, ambiguity status and applicable claim. Keep AI proposals
and owner acceptance distinct. Disagreement is a visible unresolved case; do not count it
as correct, silently remove it, or fabricate blind independent review. Freeze input and
evaluator files separately before model output. Olist's active independent-review condition
stays open until the particular replacement method is validated and accepted.

Start development with negation, partial amounts, multiple amounts, corrections, refund
versus replacement preference, quoted instructions, and missing intent. Meaning-preserving
paraphrases must preserve interpretation; flipping the requested action/amount must change
it. These relations are hypotheses to validate against text meaning, not automatic gold.
Keep source parents, templates, paraphrases and correction chains together across splits.
English constructed requests support an English claim; Portuguese source reviews do not
make the English intent evaluation multilingual. Add languages only with suitable references.

## Planning targets accepted by the owner, not active gate replacements

On 2026-10-30 the owner accepted the concrete numerical planning targets below in chat.
The [versioned target record](data/olist-operating-targets-v1.json) preserves their values
and authorization boundary. This supersedes their initial pending status only. It does
not accept a frozen statistical protocol, alter active release profiles, fund provider
calls or authorize hosting purchases/release. The later99.9%goal remains aspirational.

| Dimension | Proposed initial target | Denominator / qualification |
| --- | --- | --- |
| Critical effects | Zero observed unauthorized, duplicate, over-cap or cross-tenant effects; any fails release | Every required normal/fault/replay/restart case; unknown and missing evidence block |
| Intent plus amount | At least 95% exact joint agreement | All scheduled independently referenced requests; malformed/timeout/missing outputs fail |
| Eligible completion | At least 95% correct full-refund completion | All reference-eligible cases, including abstentions/timeouts |
| Required review | At least 95% correct review routing, plus zero observed critical unsafe executions | All reference-required-review cases; report false proposals separately from actual effects |
| API latency | p95 at most 1 second for non-model interactive endpoints | Authenticated expected-load requests measured at client, failures retained |
| Model-assisted latency | p95 at most 30 seconds, with explicit bounded timeout and durable visible outcome | All scheduled requests; timeout counted, not dropped from percentiles |
| Availability | 99.5% initial hosted objective over rolling 30 days; 99.9% later goal | Valid client-visible requests with correct durable outcome, not health pings alone |
| Process crash durability | No loss of acknowledged commits | Same durable database; crash before/after commit and restart/duplicate tests |
| Host-loss RPO / RTO | At most 15 minutes data loss / 60 minutes service restoration | Isolated host-loss exercise including provision, restore, application checks and cutover |

Safe review does not count as eligible completion. Report every critical slice separately;
passing aggregate accuracy cannot hide missing or failing risk slices. No claim that these
numbers are measured, affordable on Free providers, or appropriate for real payments.
Availability is distinct from model-answer quality. Unavailable model routes need a safe
durable path, but degrading every request to review still fails completion objectives.

Before freezing, agree risk weights, baseline margins, maximum review load and resource
limits, together with sample size. Compare the same cases against rules and always-review.
The rules baseline receives labeled structured request intent; it is a policy comparator,
not an equivalent text-understanding competitor. Publish that information advantage.

For planning: a two-sided 95% exact binomial upper error bound of 5% needs **72 independent
zero-error families per class**. Two trials on each family do not double the sample; count
a family as failed if either required trial fails. This is a marginal class claim. For two
simultaneous class claims with conservative Bonferroni two-sided intervals, plan **86
zero-error families per class** (97.5% intervals each). Additional slices need their own
coverage/uncertainty design; these totals do not validate every slice. Formula for zero
errors: upper = `1 - (alpha / 2) ** (1 / n)`; see [NIST intervals](https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm).
These are planning examples, not approved Olist thresholds or an assertion that source
groups are independent. More samples do not fix weak labels or systematic mistakes.

Freeze cohort, source lineage/exclusions, split assignments, references, protocol, scorer,
baselines, model/settings, resource limits and exact candidate. Run a distinct development
comparison first; qualify only a selected frozen candidate on a new untouched cohort.
Retain all scheduled denominators, incomplete cases, tokens/cost unknowns and regressions.
No provider use is authorized by this plan; the remaining Gemini slots are bound to the
stopped Revenue comparison, not transferable to Olist.

## Deployment and recovery preparation alongside evaluation

Recommend an always-on application and managed PostgreSQL with verified backup/PITR and
private access, subject to host, region, pricing and retention decisions. This specifies
required capabilities without purchasing a service or choosing an unverified vendor.
Keep the existing loopback deployment for local proof; it does not demonstrate external
TLS, ingress, authentication boundaries, disk loss or host-specific termination signals.

Prepare the following acceptance record on the frozen candidate:

1. Record host/region, application image or wheel digest, lock/schema/config pins, private
   secret injection, TLS/proxy configuration and database/backup version. Validate actual
   startup refusal for missing secret/database/schema, with no secret-bearing logs.
2. Run authenticated source-grounded request -> durable review -> exact approved SIM action
   -> receipt -> duplicate delivery. Capture client latency, SQL state and receipt identity.
3. Pause at before-commit and after-commit barriers, terminate the owned process, restart,
   and read durable state before replay. No new planning/call after a settled effect.
   Execute injection, tenant mismatch, stale approval, provider outage and database failure.
4. Exercise graceful shutdown with an in-flight commit; inspect process exit, persisted
   checkpoint and flushed telemetry. The existing listening-server test covers normal
   drain; an actual host signal test remains separate.
5. Restore the private archive into a new target, preserve the source and its newer rows,
   verify schema/state/receipts/review/checkpoint, then retry an already committed action.
   Current `recovery_exercise.exercise` measures restore/readiness only, not end-to-end RTO.
6. For host loss, insert timestamped acknowledged canaries before failure; recover into
   an isolated target from backups/WAL, identify the last recovered acknowledged canary,
   and measure lost time and elapsed time from outage to authenticated successful workflow.
   Include backup discovery, provisioning, restore, migration checks, secrets and cutover.
7. Test application rollback against current schema/state; never restore old business
   data over newer effects. Record compensation separately. Test incompatible schema and
   missing/corrupt archive refusal. Protect backup confidentiality, keys and retention.

Existing executable starting points: `olist_support.operations_cli` (`ready`, `backup`,
`restore-new`, `exercise`), `tests/integration/test_olist_operations_recovery.py`,
`test_olist_service_shutdown.py`, `test_olist_crash_evidence.py`, and the
[operations runbook](olist-operations-recovery.md). Use owned disposable trials and private
paths outside Git. Do not run host-loss experiments against unrelated or live containers.
Keep #58/#59 acceptance pending until these host-specific results and objectives exist.

## Reproduce this audit

```powershell
python -m olist_support.reference_package --cases <private-evaluator.json> --cases-sha256 <external-pin> --metadata <private-metadata.json> --metadata-sha256 <external-pin> --inputs <private-inputs.json> --inputs-sha256 <external-pin> --profile docs/evaluation/profiles/olist.json --profile-sha256 <external-profile-pin>
python -m pytest -q tests/test_olist_reference_package.py tests/test_olist_evaluation_oracle.py tests/test_olist_cohort_draft.py
```

Use the locked workspace environment. For this Windows host set TEMP/TMP to the existing
private D-drive temporary directory: an unrelated `C:/.git` marker correctly makes private
artifact guards reject default C-drive paths. Do not delete the marker or weaken the guard.
The first focused run used default TEMP and failed one existing private-path test; the
corrected D-drive run passed 33 tests. No result or label was changed to obtain that pass.

Next decisions: validate the concrete semantic
reference method; approve a frozen new cohort and separate bounded provider scope; choose
host/backup capabilities. Current code work can merge without granting any of these.
