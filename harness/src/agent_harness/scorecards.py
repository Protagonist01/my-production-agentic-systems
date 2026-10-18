"""Join every scheduled key to independently assessed, provenance-checked evidence."""

from collections import defaultdict
from typing import Literal

from agent_harness.cases import LoadedManifest
from agent_harness.fault_contracts import FaultPlan, digest
from agent_harness.faults import verify_evidence
from agent_harness.scorecard_contracts import (
    CaseScorecard,
    RepeatedCorrectness,
    ReportPolicy,
    Scorecard,
    SliceScorecard,
    TrialFact,
    ratio,
)
from agent_harness.scorecard_stats import summarize
from agent_harness.trials import BatchReport, TrialAssessment, assess, validate_schedule


def _validate(batch: BatchReport, loaded: LoadedManifest, plan: FaultPlan | None) -> None:
    validate_schedule(batch.schedule, loaded)
    if batch.schedule.fault_plan != plan:
        raise ValueError("report requires the separately reviewed fault plan")
    for row in batch.rows:
        if row.report is None:
            continue
        wrapped = row.report
        entry = loaded.entry(row.task.context.case_id)
        report = wrapped.report
        if (
            wrapped.group_id,
            wrapped.split,
            wrapped.scorer_id,
            report.source_kind,
            report.source_version,
            report.scorer_version,
            report.policy_version,
        ) != (
            entry.group_id,
            entry.split,
            entry.scorer_id,
            entry.case.source_kind,
            entry.case.source_version,
            entry.case.scorer_version,
            entry.case.policy_version,
        ):
            raise ValueError("report provenance differs from reviewed case")
        if report.fault_evidence is not None and not verify_evidence(
            report.fault_evidence, plan, entry.case, row.task.context.seed, require_complete=False
        ):
            raise ValueError("fault evidence differs from reviewed case/plan")


def build_scorecard(
    batch: BatchReport,
    loaded: LoadedManifest,
    policy: ReportPolicy,
    *,
    reporter_revision: str,
    fault_plan: FaultPlan | None = None,
) -> Scorecard:
    batch = BatchReport.model_validate_json(batch.canonical_json())
    policy = ReportPolicy.model_validate_json(policy.canonical_json())
    _validate(batch, loaded, fault_plan)
    manifest = loaded.manifest
    inventory = set(manifest.case_ids)
    if (set(policy.required_case_ids) | set(policy.repeated_case_ids)) - inventory:
        raise ValueError("reporting policy contains unlisted cases")
    rows = {row.task.key: row for row in batch.rows}
    tasks: dict[str, list[TrialFact]] = defaultdict(list)
    for task in batch.schedule.tasks:
        row = rows.get(task.key)
        assessment = assess(row, batch.schedule.outcome_policy) if row is not None else None
        entry = loaded.entry(task.context.case_id)
        if row is not None and entry.case.faults:
            evidence = row.report.report.fault_evidence if row.report is not None else None
            if evidence is None or not evidence.complete:
                assessment = TrialAssessment(
                    category="unsafe"
                    if assessment and assessment.category == "unsafe"
                    else "unverified",
                    evidence_complete=False,
                )
        result = row.report.report.result if row is not None and row.report is not None else None
        tasks[task.context.case_id].append(
            TrialFact(
                case_id=task.context.case_id,
                trial_id=task.context.trial_id,
                seed=task.context.seed,
                assessment=assessment,
                observed_outcome=result.outcome if result else None,
                usage=result.usage if result else None,
                usage_complete=row is not None and result is not None and not row.errors,
                errors=row.errors if row is not None else (),
            )
        )
    kinds = {rule.scenario_id: rule.kind for rule in fault_plan.rules} if fault_plan else {}
    cases = tuple(
        CaseScorecard(
            case_id=entry.case.case_id,
            group_id=entry.group_id,
            split=entry.split,
            source_kind=entry.case.source_kind,
            source_version=entry.case.source_version,
            risk=entry.case.risk,
            tags=tuple(sorted(set(entry.case.slices))),
            snapshot_ref=entry.case.snapshot_ref,
            policy_version=entry.case.policy_version,
            scorer_id=entry.scorer_id,
            scorer_version=entry.case.scorer_version,
            eligible_for_autonomy=entry.case.expected.eligible_for_autonomy,
            required_review=entry.case.expected.required_review,
            required_case=entry.case.case_id in policy.required_case_ids,
            repeated_case=entry.case.case_id in policy.repeated_case_ids,
            fault_kinds=tuple(sorted({kinds[f.scenario_id] for f in entry.case.faults})),
            trials=tuple(sorted(tasks[entry.case.case_id], key=lambda f: f.trial_id)),
        )
        for entry in sorted(manifest.entries, key=lambda e: e.case.case_id)
    )
    repeated = tuple(case for case in cases if case.repeated_case)
    first = batch.schedule.tasks[0].context
    if first.mode == "monitoring":
        raise ValueError("monitoring is not controlled reporting evidence")
    status: Literal[
        "not_declared", "requires_fresh_candidate", "requires_exactly_three_trials", "reported"
    ]
    if not repeated:
        status = "not_declared"
    elif first.mode != "fresh_candidate":
        status = "requires_fresh_candidate"
    elif len(batch.schedule.trial_ids) != 3:
        status = "requires_exactly_three_trials"
    else:
        status = "reported"
    repeated_count = (
        ratio(
            sum(all(f.passed for f in case.trials) for case in repeated),
            len(repeated),
            sum(
                not any(
                    f.category in ("unsafe", "incorrect", "safe_unresolved", "unnecessary_review")
                    for f in case.trials
                )
                and not all(f.complete for f in case.trials)
                for case in repeated
            ),
        )
        if status == "reported"
        else None
    )
    dimensions: dict[str, dict[str, list[CaseScorecard]]] = defaultdict(lambda: defaultdict(list))
    for case in cases:
        for dimension, labels in (
            ("split", (case.split,)),
            ("source_kind", (case.source_kind,)),
            ("source_version", (case.source_version,)),
            ("risk", (case.risk,)),
            ("tag", case.tags),
            ("fault_kind", case.fault_kinds),
        ):
            for label in labels:
                dimensions[dimension][label].append(case)
    slices = tuple(
        SliceScorecard.model_validate(
            {
                "dimension": dimension,
                "label": label,
                "summary": summarize(tuple(group)),
            }
        )
        for dimension, groups in sorted(dimensions.items())
        for label, group in sorted(groups.items())
    )
    return Scorecard(
        reporter_code_revision=reporter_revision,
        experiment_id=batch.schedule.experiment_id,
        batch_sha256=digest(batch),
        manifest=loaded.pin,
        report_policy=policy,
        outcome_policy=batch.schedule.outcome_policy,
        candidate=first.versions.candidate,
        code_revision=first.versions.code_revision,
        environment_lock=first.versions.environment_lock,
        environment_version=batch.schedule.environment_version,
        state_fixture=batch.schedule.state_fixture,
        fault_plan_version=fault_plan.version if fault_plan else None,
        fault_plan_sha256=digest(fault_plan) if fault_plan else None,
        mode=first.mode,
        overall=summarize(cases),
        fault_outcomes=summarize(tuple(case for case in cases if case.fault_kinds)),
        repeated_correctness=RepeatedCorrectness(status=status, all_three_correct=repeated_count),
        slices=slices,
        cases=cases,
    )
