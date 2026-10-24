"""Bind an additional methodology audit to H10's already verified evidence."""

from agent_harness.cases import LoadedManifest
from agent_harness.evaluation_standards import StandardProfile, StandardProtocol, StandardStudy
from agent_harness.release_contracts import pin
from agent_harness.release_evidence import VerifiedEvidence
from agent_harness.trials import TrialRow, assess


def _correct(row: TrialRow, evidence: VerifiedEvidence) -> bool:
    return assess(row, evidence.batch.schedule.outcome_policy).category in (
        "autonomous_completion",
        "verified_completion",
        "appropriate_review",
    )


def verify_binding(
    profile: StandardProfile,
    protocol: StandardProtocol,
    study: StandardStudy,
    loaded: LoadedManifest,
    baseline: VerifiedEvidence,
    candidate: VerifiedEvidence,
    required_case_ids: tuple[str, ...],
) -> None:
    """A successful audit from another population/candidate cannot qualify this release."""
    profile = StandardProfile.model_validate_json(profile.canonical_json())
    protocol = StandardProtocol.model_validate_json(protocol.canonical_json())
    study = StandardStudy.model_validate_json(study.canonical_json())
    if (
        protocol.dataset_sha256 != loaded.pin.sha256
        or protocol.scorer_sha256 != candidate.manifest.candidate.scorer_sha256
        or protocol.baseline_sha256 != pin(baseline.manifest)
        or study.candidate_spec_sha256 != pin(candidate.manifest.candidate)
        or study.candidate_evidence_sha256 != pin(candidate.manifest)
        or study.started_at != candidate.manifest.started_at
        or study.finished_at != candidate.manifest.finished_at
        or any(t.context.agent_id != profile.agent for t in candidate.batch.schedule.tasks)
    ):
        raise ValueError("methodology study belongs to different release evidence")
    if (
        protocol.baseline_review is not None
        and protocol.baseline_review.reviewed_at < baseline.manifest.finished_at
    ):
        raise ValueError("baseline review precedes its evidence")
    entries = {e.case.case_id: e for e in loaded.manifest.entries}
    if set(entries) != {c.case_id for c in study.cases}:
        raise ValueError("methodology population differs from sealed manifest")
    required = set(profile.required_fields)
    for case in study.cases:
        entry = entries[case.case_id]
        if (
            entry.group_id not in case.independence_keys
            or case.input_text != entry.case.input.request
            or case.source_kind != entry.case.source_kind
            or case.required_review != entry.case.expected.required_review
            or case.eligible_for_autonomy != entry.case.expected.eligible_for_autonomy
            or (case.split == "holdout") != (entry.split == "holdout")
            or (case.case_id in required_case_ids and not case.critical)
        ):
            raise ValueError("methodology case differs from sealed input/group/labels")
    if set(study.trial_ids) != set(candidate.batch.schedule.trial_ids):
        raise ValueError("methodology trial schedule differs from sealed evidence")
    before = {r.task.key: r for r in baseline.batch.rows}
    after = {r.task.key: r for r in candidate.batch.rows}
    if {(r.case_id, r.trial_id) for r in study.rows} != set(after):
        raise ValueError("methodology result inventory differs from sealed evidence")
    for result in study.rows:
        key = result.case_id, result.trial_id
        row = after[key]
        measured = row.timing.elapsed_seconds if row.timing is not None else None
        if result.elapsed_seconds != measured:
            raise ValueError("methodology latency differs from sealed parent measurement")
        receipts = [
            receipt
            for receipt in candidate.receipts
            if (receipt.exchange.context.case_id, receipt.exchange.context.trial_id) == key
        ]
        if result.elapsed_seconds is not None and receipts:
            observed_span = (
                max(r.finished_at for r in receipts) - min(r.started_at for r in receipts)
            ).total_seconds()
            if result.elapsed_seconds < observed_span:
                raise ValueError("declared trial latency is shorter than sealed dispatch span")
        assessment = assess(row, candidate.batch.schedule.outcome_policy)
        actual = row.report.report.result if row.report else None
        outcome = (
            actual.outcome
            if actual and actual.outcome in ("completed", "review_required")
            else "unresolved"
        )
        if (
            result.correct != _correct(row, candidate)
            or result.unsafe != (assessment.category == "unsafe")
            or result.outcome != outcome
            or result.baseline_correct != (key in before and _correct(before[key], baseline))
        ):
            raise ValueError("methodology outcome differs from independent H10 assessment")
        scores = {s.metric: s for s in row.report.report.scores} if row.report else {}
        for field in required:
            score = scores.get(field)
            if score is None or score.failure is not None or score.value not in (0.0, 1.0):
                raise ValueError("required field needs an independent binary H10 scorer")
            if result.fields.get(field) != (score.value == 1.0):
                raise ValueError("methodology field differs from sealed domain score")
        usage = actual.usage if actual else None
        if usage is None or (
            result.input_tokens,
            result.output_tokens,
            result.cost,
            result.cost_currency,
            result.model_calls,
        ) != (
            usage.input_tokens,
            usage.output_tokens,
            usage.cost,
            usage.cost_currency,
            usage.model_calls,
        ):
            raise ValueError("methodology usage differs from sealed domain result")
