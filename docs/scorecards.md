# Private scorecards and paired comparisons — H9

H9 #23 builds reports over H6/H7 evidence. It does not invoke an agent, scorer, model or exporter. H8 is merged/verified on main 21a5720; H9 is merged/verified on main fd87750. H10 #24 adds [fresh evidence verification and release gates](release-evidence.md) separately from these report-only APIs.

## Read a reviewed journal

Supply a private case manifest, its separately reviewed ManifestPin JSON, a journal directory and a versioned ReportPolicy JSON. Required cases come from that external policy, never candidate outcomes. An empty required list is explicit and means no required-case regression rule was requested. Unknown or duplicate policy case IDs fail. The optional repeated_case_ids list declares a subset before reporting.

```json
{"schema_version":1,"version":"reviewed-report-v1","required_case_ids":["case-a"],"repeated_case_ids":["case-a"]}
```

After `python dev.py setup`, run this as one command (quote paths with spaces):

```powershell
python dev.py scorecard --manifest "private/cases.json" --manifest-pin "private/reviewed-pin.json" --journal "private/candidate-journal" --report-policy "private/report-policy.json" --output "artifacts/new-private-report"
```

For fault cases, also pass `--fault-plan private/reviewed-plan.json`. The plan must match the schedule; a journal cannot authorize its own treatment. The output parent must exist and the output directory must be new. The command writes scorecard.json and scorecard.md exclusively, flushes files and refuses overwrite. A filesystem failure returns nonzero and may retain partial files; inspect them and choose a new directory for retry. POSIX output modes are 0700/0600; on Windows also protect the parent directory with appropriate local ACLs. No data is uploaded. Module execution denies outbound network; inline library use does not install a permanent process-wide hook.

The dev wrapper records the actual reporter Git revision with a dirty marker. Direct module users must supply `--code-revision`. That identifies report software, separately from the experiment's candidate/code/environment versions. Neither a caller-supplied revision nor JSON hashes authenticate a trusted author.

## Counts and missing evidence

Every reviewed manifest case and every declared trial remains in the report. Missing rows become explicit missing facts. Worker errors, scorer errors, incomplete hooks and cleanup errors retain the denominator and cannot earn completion. Malformed/duplicate/unexpected journal rows and incompatible provenance fail instead of producing a plausible report. Source kind/version, split, group, scorer and policy metadata are checked against the loaded pinned case.

| Measure | Numerator | Denominator |
|---|---|---|
| Autonomous completion | Independently verified autonomous completions | Every scheduled eligible case/trial |
| Confirmed success | Verified autonomous/other completion or appropriate review | Every scheduled case/trial |
| Observed review | A retained result reports review_required, even if another check failed | Every scheduled case/trial |
| Appropriate review | Independently correct required review | Every scheduled required-review case/trial |
| Unnecessary review | Verified review on a case not requiring it | Every scheduled case/trial not requiring review |
| Observed violations | Binary unsafe outcomes from safety/invariant checks or required-review bypass | Every scheduled case/trial; unknown evidence remains explicit |
| Complete evidence | All required independent assessment and hook evidence is present | Every scheduled case/trial |

Each Ratio retains numerator, denominator, unknown count, observed value and possible upper value. Zero denominators produce null values. Known unsafe outcomes remain unsafe even alongside another error. One unsafe trial counts once regardless of how many atomic violations it contains: these are not per-action opportunity counts. Report category counts distinguish completion, appropriate/unnecessary review, safe unresolved, incorrect, unsafe, unverified and missing. Escalating everything earns zero autonomy credit.

Fault summaries use the declared fault-case population, including missing outcomes. Split, source kind/version, risk, tag and fault-kind slices use manifest membership rather than successful rows. Tags and fault kinds overlap; do not add those slice denominators. An overall summary describes one reviewed manifest and is not an industry-blended quality benchmark. Source-kind labels in invented unit fixtures exercise serialization/slicing; they are not evidence that those inputs are authentic observations.

## Unknown usage is not zero

Reported model calls/tokens/cost survive as known subtotals. Missing reports, row errors or unknown components make their corresponding complete totals null. Keep subtotal and unknown-trial count together; a crashed worker might have spent unreported resources. Costs are subtotaled separately by declared currency. Only fully known cost in one currency becomes a total or cost-per-autonomous-completion value. The latter divides the entire run's known cost, including review work, by autonomous completions; zero completions yield null. No prices, currency conversion or latency are inferred. H6 journals do not retain a measured latency field.

## Safety uncertainty

Safety opportunities here are binary unsafe trials; uncertainty uses the reviewed group as its sampling unit. Within a reported slice, any observed unsafe trial makes its group positive. A group without an observed violation but with missing/unverified evidence remains unknown. Repeated trials and related cases in the same group do not inflate the sample count.

For G groups, P observed positive groups and U unknown groups, possible event counts range from P to P+U. The 95% interval envelope takes the lower binomial endpoint at P and the upper endpoint at P+U. For zero/all events use exact two-sided binomial boundaries; otherwise use Wilson endpoints. In particular, zero events with complete evidence has upper bound `1 - 0.025 ** (1/G)`, computed with expm1 for numerical stability. One complete group with zero events therefore has interval [0, 0.975], not [0, 0]. With all groups unknown it is [0, 1]. No groups yields null bounds.

These are conditional model-based intervals: comparable independent groups are assumed, not established by IDs. Handpicked, dependent, synthetic or replay evidence does not establish a population risk rate. Unknown groups widen the envelope rather than disappearing. No zero-event bootstrap or claim of zero risk is used. Methods follow [NIST's binomial confidence-interval guidance](https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm).

## Repeated-trial correctness and modes

All-three correctness is emitted only for an explicitly declared subset, fresh_candidate mode and exactly three scheduled trials per case. Missing/unverified trials cannot pass. Other modes or trial counts show a reason and null metric. The report always states freshness_verified=false: mode is a declaration, and H10 verifies fresh dispatch receipts separately, without changing this report-only flag. Replay cannot silently become a fresh quality result. Monitoring is not a controlled H6 schedule mode.

## Explicit baseline comparison

Add `--baseline-journal private/baseline-journal --baseline-sha256 <reviewed-canonical-batch-digest>` to the command. Obtain the expected digest separately from a reviewed BatchReport, using `agent_harness.fault_contracts.digest`. This is canonical batch content, not a hash of directory bytes or report JSON. The CLI never chooses the latest journal or computes its own expected baseline pin.

Both batches must use the same reviewed manifest, evaluator/outcome policy, mode, fault treatment, environment/state fixture and scheduled keys. Paired trial seeds, fixed clocks/deadlines, budgets, tenant/agent/business-event identities must match. Code, candidate and dependency versions may differ as candidate changes and are retained explicitly. Missing terminal rows are comparable missing evidence; removing scheduled tasks is an incompatible population.

Comparison output includes every case's pass counts, regressed/improved trial IDs, newly unsafe and newly unverified trials. Any previously passing required trial that now fails or is missing flags its case even when the overall average improves. A fixture demonstrates 1/3 → 2/3 average completion while a required case regresses. A digest-bound baseline argument establishes identity, not baseline approval or a release decision. H10 supplies that reviewed release policy. This boundary follows [Langfuse's experiment-comparison guidance](https://langfuse.com/docs/evaluation/experiments/compare-experiments).

## Trust and scope

Reports omit raw input/output, private expected state, scorer evidence text, credentials and exception bodies. They still contain private identifiers, membership, risk/tags and metadata; they are not the pseudonymous H8 telemetry projection and are not automatically safe to publish. Do not commit real report artifacts. Trusted plugins and local journal files can lie; this is validation/reproducibility, not a malicious-code sandbox or authenticated evidence system. Corruption or concurrent incomplete writes fail closed. Existing Langfuse 4.50.0 and locked SDK versions stay unchanged because no backend integration is added.

[Code study](code-study-scorecards.md) · [H6 journals](isolated-trials.md) · [H7 faults](seeded-faults.md) · [Project workflow](project-management.md)
