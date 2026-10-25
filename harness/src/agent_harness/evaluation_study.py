"""Project verified H10 evidence; never author reviews, labels, limits or receipts."""

from agent_harness.baseline_recording import VerifiedBaseline
from agent_harness.cases import LoadedManifest
from agent_harness.evaluation_binding import verify_binding
from agent_harness.evaluation_standards import (
    StandardCase,
    StandardProfile,
    StandardProtocol,
    StandardRow,
    StandardStudy,
)
from agent_harness.release_contracts import pin
from agent_harness.release_evidence import VerifiedEvidence
from agent_harness.trials import assess


def assemble_study(
    profile: StandardProfile,
    protocol: StandardProtocol,
    cases: tuple[StandardCase, ...],
    loaded: LoadedManifest,
    baseline: VerifiedEvidence | VerifiedBaseline,
    candidate: VerifiedEvidence,
    *,
    required_case_ids: tuple[str, ...],
) -> StandardStudy:
    """Caller must use pinned evidence readers first; binding is not qualification.

    Existing H10 binding deliberately requires observed reports and independent
    binary fields. Missing reports/scorer observations cannot be manufactured here.
    """
    if not isinstance(candidate, VerifiedEvidence):
        raise ValueError("candidate requires verified fresh dispatch evidence")
    left, right = baseline.manifest.candidate, candidate.manifest.candidate
    if (
        left.scorer_sha256,
        left.policy_sha256,
        left.environment_sha256,
        left.environment_lock,
        baseline.batch.schedule.environment_version,
        baseline.batch.schedule.state_fixture,
        baseline.batch.schedule.outcome_policy,
        baseline.batch.schedule.fault_plan,
    ) != (
        right.scorer_sha256,
        right.policy_sha256,
        right.environment_sha256,
        right.environment_lock,
        candidate.batch.schedule.environment_version,
        candidate.batch.schedule.state_fixture,
        candidate.batch.schedule.outcome_policy,
        candidate.batch.schedule.fault_plan,
    ):
        raise ValueError("study baseline evaluator/policy/environment is incompatible")
    if (
        baseline.batch.schedule.manifest != loaded.pin
        or candidate.batch.schedule.manifest != loaded.pin
        or baseline.batch.schedule.trial_ids != candidate.batch.schedule.trial_ids
        or baseline.batch.schedule.case_ids != candidate.batch.schedule.case_ids
        or any(t.context.agent_id != profile.agent for t in baseline.batch.schedule.tasks)
        or pin(baseline.batch) != baseline.manifest.batch_sha256
        or pin(candidate.batch) != candidate.manifest.batch_sha256
        or len(set(required_case_ids)) != len(required_case_ids)
        or not set(required_case_ids).issubset(loaded.manifest.case_ids)
    ):
        raise ValueError("study requires compatible sealed populations")
    before = {r.task.key: r for r in baseline.batch.rows}
    rows = []
    for row in candidate.batch.rows:
        assessment = assess(row, candidate.batch.schedule.outcome_policy)
        if row.report is None:
            raise ValueError("study cannot invent a missing H10 report")
        result = row.report.report.result
        scores = {s.metric: s for s in row.report.report.scores}
        fields = {}
        for name in profile.required_fields:
            score = scores.get(name)
            if score is None or score.failure is not None or score.value not in (0.0, 1.0):
                raise ValueError("study requires independently observed binary fields")
            fields[name] = score.value == 1.0
        old = before.get(row.task.key)
        rows.append(
            StandardRow(
                case_id=row.task.context.case_id,
                trial_id=row.task.context.trial_id,
                outcome=result.outcome
                if result.outcome in ("completed", "review_required")
                else "unresolved",
                correct=assessment.category
                in ("autonomous_completion", "verified_completion", "appropriate_review"),
                unsafe=assessment.category == "unsafe",
                fields=fields,
                baseline_correct=old is not None
                and assess(old, baseline.batch.schedule.outcome_policy).category
                in ("autonomous_completion", "verified_completion", "appropriate_review"),
                elapsed_seconds=row.timing.elapsed_seconds if row.timing else None,
                input_tokens=result.usage.input_tokens,
                output_tokens=result.usage.output_tokens,
                model_calls=result.usage.model_calls,
                cost=result.usage.cost,
                cost_currency=result.usage.cost_currency,
            )
        )
    study = StandardStudy(
        version="h10-projected-study-v1",
        protocol_sha256=pin(protocol),
        candidate_spec_sha256=pin(candidate.manifest.candidate),
        candidate_evidence_sha256=pin(candidate.manifest),
        started_at=candidate.manifest.started_at,
        finished_at=candidate.manifest.finished_at,
        cases=cases,
        trial_ids=candidate.batch.schedule.trial_ids,
        rows=tuple(rows),
    )
    verify_binding(profile, protocol, study, loaded, baseline, candidate, required_case_ids)
    return study
