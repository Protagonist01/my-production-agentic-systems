# Prior Auth, Supply and cross-vertical report preparation

Prepared on `codex/prior-auth-supply-release-reports`, based on PR #107 merge `a30ebc4`,
2026-10-26. This advances #51, #57 and #61 preparation under the user's autonomous delivery
instruction. It does not accept their prerequisites or complete any release study. Reviewer
responses remain pending. No provider calls occur in these APIs, and the existing 180-attempt
authorization names Olist, CFPB and Revenue only.

## Prior Auth: preserve both risk denominators

[`AssessmentPlan`](../projects/prior-auth/src/prior_auth/release_evaluation.py) pins the
candidate, source-manifest hash, full private cohort, explicit trial IDs and declared origin.
The plan hash also binds all inputs and provisional references. `AssessmentObservation` holds
one actual result or missing/failed status for a scheduled case/trial. `assessment_report()`
revalidates both, rejects duplicate/unknown identities, uses the existing parent/group/note
split rules and requires one policy hash. Expected labels never enter a candidate invocation.

The scorer expands the entire case × trial matrix before counting results. For example,
one correct information request, one failed incorrect evidence-complete recommendation and
one absent trial produce three scheduled/non-approvable opportunities, one incorrect
recommendation out of one recommendation, and one out of three reference-non-approvable
opportunities. Missing outputs never disappear from the latter denominator. An undefined
ratio is `null`, not zero. These are reference-relative assessment labels, not clinical truth.

Every criterion retains the scheduled denominator. A claimed met criterion needs actual
literal citation spans; malformed/duplicate/incomplete criterion inventories or wrong spans
make the result invalid. Failed/retrieval-failed/assessment-failed outputs remain unresolved,
even if their wording appears correct. A failed incorrect recommendation still counts as a
risk observation. All-trial correctness requires every declared trial to resolve correctly.
The report separates development/holdout and published/edited/invented provenance, counts
independent groups, and marks clinical validation and release authorization false.

The report establishes literal citation integrity and agreement with the frozen provisional
references. It cannot establish clinical criterion meaning, independent expert review,
representative sampling, privacy/injection/state coverage or provider freshness. Origin is
a declaration; provider receipts must still be independently verified by the release path.

## Supply: paired realized SIM costs and sensitivity

[`SimulationPlan`](../projects/supply-chain-disruption/src/supply_chain/release_evaluation.py)
pins the candidate, ordered hidden-world inventory, scenario/trial IDs, explicit sensitivities
and declared origin. `world_pin()` includes public facts, hidden action outcomes, seeds,
family, split, template and outcome-model metadata. Changing realized outcomes requires a
new world pin, rather than silently revising an existing result. Related shipment identities
cannot cross splits. The evaluator requires nonempty unique shipments and three nonnegative
integer action outcomes per shipment.

`simulation_report()` passes detached public shipments only to do-nothing, rules and the
estimate solver. Hidden worlds stay with `realized_cost()`. It applies the same frozen world
and sensitivity to each recorded candidate action map and comparator. Candidate action
observations do not call a model or perform a business mutation.

An absent action map is a missing trial. An empty or partial map is observed but unresolved:
an omitted shipment never counts as an intentional completed wait. Unsafe actions and cap
violations remain counted, and explicit failed trials remain unresolved. The cost for an
unsafe action uses the existing conservative wait realization; the report retains the unsafe
event rather than crediting the infeasible action's hoped-for benefit.
Explicit wait on stale/missing/conflicting facts also remains unresolved: zero spend does
not make unavailable facts sufficient to complete an assessment.

Cost totals compare the same observed trial scope on both sides. Missing candidate trials
therefore produce missing comparisons, not a candidate cost of zero against a fully populated
baseline. `paired_observed` and the full scheduled denominator show the distinction. Failed/
unsafe observations are retained in observed cost comparisons and explicitly separated from
completed outcomes; do not interpret their cost as achieved safe benefit. Split, family,
outcome-model and sensitivity tables remain separate. All-trial completion requires every
declared trial to complete safely. Scenario counts are not production shipment independence.

All amounts use SIM. These are constructed equations, not fitted causal freight outcomes.
`business_state_verified` and `release_allowed` stay false: action maps establish no actual
authorization, ledger persistence, duplicate guard, compensation, recovery or fresh receipts.

## Catalog: publish pins without private inputs

[`report_catalog()`](../harness/src/agent_harness/release_catalog.py) takes a private directory
and `ReportPin` entries containing scope, relative path and independently retained byte hash.
It rejects path escape, symlinks, oversized files, changed bytes, wrong domain versions,
duplicate scopes, claimed release authorization and invalid aggregate counts. It reads each
descriptive report and publishes only a fixed projection: scope, known report version, byte
pin, whitelisted aggregate integer counts and `release_allowed=false`.

No source text, candidate answer, private path, note/case ID or arbitrary nested report field
passes through the catalog. Revenue original and SIM remain separate scopes. Supply's full
sensitivity tables and Olist's mode comparisons remain in their individual pinned reports;
the catalog does not invent a common summary. Missing scopes are listed. `reports_complete`
means all six report scopes are present, never that their studies or release gates passed.
There is no blended cross-industry accuracy or computed financial savings.

For an operator preparing a handoff:

1. Freeze each domain plan and actual observations outside Git; recompute its report using
   the relevant domain API. Preserve missing/failure rows and old versions.
2. Serialize the descriptive report to a new private file and retain its byte SHA-256.
3. Construct `ReportPin(scope="prior-auth", relative_path="assessment.json", sha256=pin)`
   (using the actual byte hash) and call `report_catalog(private_root, references)`.
4. Review the small projected catalog before publishing. Keep detailed reports private or
   separately reviewed for publication. Catalog presence does not replace release artifacts.

The executable entrypoint is `python -m agent_harness.release_catalog --root <private-root>
--inventory <inventory.json> --inventory-sha256 <actual-byte-pin> --output <new-catalog.json>`.
The inventory is a canonical `ReportInventory` object containing the `ReportPin` tuple.
The CLI verifies its external byte pin, writes a new output exclusively, and prints only
the output pin, inventory completeness and false release authorization. Existing outputs
are never overwritten; there is no provider, deployment or automatic publishing command.

## Checks and limits

`tests/test_remaining_release_reports.py` uses invented inputs to verify missing/repeated
denominators, failed incorrect recommendations, invalid citations, complete/partial/unsafe
shipment plans, sensitivity pairing, changed hidden targets, wrong report versions and
private canary suppression. Existing Prior Auth and simulation tests remain applicable.
Hosted quality/database checks verify software behavior; final studies and reviewer judgments
are separate. No existing cohort, holdout, label, threshold or historical provider result is
promoted by these report APIs.
