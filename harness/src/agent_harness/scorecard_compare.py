"""Explicit matched-baseline comparisons; no approval, threshold or release decision."""

from agent_harness.cases import LoadedManifest
from agent_harness.fault_contracts import FaultPlan, digest
from agent_harness.scorecard_contracts import CaseChange, Comparison, ReportPolicy
from agent_harness.scorecards import build_scorecard
from agent_harness.trials import BatchReport


def compare_batches(
    baseline: BatchReport,
    candidate: BatchReport,
    loaded: LoadedManifest,
    policy: ReportPolicy,
    *,
    reporter_revision: str,
    baseline_sha256: str,
    fault_plan: FaultPlan | None = None,
) -> Comparison:
    baseline = BatchReport.model_validate_json(baseline.canonical_json())
    candidate = BatchReport.model_validate_json(candidate.canonical_json())
    if digest(baseline) != baseline_sha256:
        raise ValueError("baseline differs from separately supplied digest")
    left = build_scorecard(
        baseline, loaded, policy, reporter_revision=reporter_revision, fault_plan=fault_plan
    )
    right = build_scorecard(
        candidate, loaded, policy, reporter_revision=reporter_revision, fault_plan=fault_plan
    )
    a, b = baseline.schedule, candidate.schedule
    if (a.manifest, a.environment_version, a.state_fixture, a.outcome_policy, a.fault_plan) != (
        b.manifest,
        b.environment_version,
        b.state_fixture,
        b.outcome_policy,
        b.fault_plan,
    ) or left.mode != right.mode:
        raise ValueError("baseline/candidate population, evaluator, mode or treatment differs")
    before = {task.key: task.context for task in a.tasks}
    after = {task.key: task.context for task in b.tasks}
    if before.keys() != after.keys():
        raise ValueError("baseline/candidate scheduled keys differ")
    for key, ctx in before.items():
        other = after[key]
        if (
            ctx.seed,
            ctx.clock,
            ctx.deadline,
            ctx.budget,
            ctx.tenant_id,
            ctx.agent_id,
            ctx.business_event_id,
        ) != (
            other.seed,
            other.clock,
            other.deadline,
            other.budget,
            other.tenant_id,
            other.agent_id,
            other.business_event_id,
        ):
            raise ValueError("baseline/candidate trial conditions differ")
    changes = []
    for old, new in zip(left.cases, right.cases, strict=True):
        old_facts = {fact.trial_id: fact for fact in old.trials}
        new_facts = {fact.trial_id: fact for fact in new.trials}
        changes.append(
            CaseChange(
                case_id=old.case_id,
                required=old.required_case,
                trials=len(old_facts),
                baseline_passes=sum(f.passed for f in old_facts.values()),
                candidate_passes=sum(f.passed for f in new_facts.values()),
                regressed_trial_ids=tuple(
                    k for k, f in old_facts.items() if f.passed and not new_facts[k].passed
                ),
                improved_trial_ids=tuple(
                    k for k, f in new_facts.items() if f.passed and not old_facts[k].passed
                ),
                new_unsafe_trial_ids=tuple(
                    k
                    for k, f in new_facts.items()
                    if f.category == "unsafe" and old_facts[k].category != "unsafe"
                ),
                new_unverified_trial_ids=tuple(
                    k for k, f in old_facts.items() if f.complete and not new_facts[k].complete
                ),
            )
        )
    x, y = left.overall.autonomous_completion.value, right.overall.autonomous_completion.value
    return Comparison(
        reporter_code_revision=reporter_revision,
        baseline_candidate=left.candidate,
        baseline_code_revision=left.code_revision,
        baseline_environment_lock=left.environment_lock,
        candidate_version=right.candidate,
        candidate_code_revision=right.code_revision,
        candidate_environment_lock=right.environment_lock,
        baseline_sha256=baseline_sha256,
        candidate_sha256=digest(candidate),
        manifest=loaded.pin,
        report_policy=policy,
        mode=left.mode,
        completion_delta=y - x if x is not None and y is not None else None,
        newly_failing_required_cases=tuple(
            c.case_id for c in changes if c.required and c.regressed_trial_ids
        ),
        cases=tuple(changes),
    )
