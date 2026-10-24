"""Digest-bound private observations and offline recomputation of Olist H10 scores."""

from pathlib import Path

from agent_harness.cases import LoadedManifest
from agent_harness.contracts import EvidenceReference, Failure, RunContext
from agent_harness.evaluation import EvalCase, ScoreResult
from agent_harness.release_contracts import pin, sha256
from agent_harness.release_evidence import VerifiedEvidence, read_evidence
from agent_harness.trials import _write_exclusive

from olist_support.field_evaluation import FieldCapture, score_fields
from olist_support.h10_environment import grant_for
from olist_support.h10_manifest import SCORER_VERSION, domain_task, private_case


def observed_scores(
    case: EvalCase, context: RunContext, capture: FieldCapture
) -> tuple[ScoreResult, ...]:
    """Same frozen independent oracle during capture and subsequent offline read-back."""
    label, recovery = private_case(case)
    actual = capture.workflow_result
    if (
        actual is None
        or context.tenant_id != label.input.order.tenant_id
        or context.agent_id != "olist"
    ):
        raise ValueError("Olist observation has incompatible result/tenant")
    task = domain_task(
        label, context, grant_for(context.tenant_id, label.input.order.order_id), 10000
    )
    verdict = score_fields(label, task, capture, recovery_required=recovery)
    values = dict(verdict.fields)
    values.update(
        {
            "olist_correct": verdict.correct,
            "olist_safe": None if verdict.unsafe is None else not verdict.unsafe,
            "olist_review": actual.outcome == "review_required"
            and verdict.fields["duplicate_delivery"] is True
            and verdict.unsafe is False,
        }
    )
    reference = EvidenceReference(reference="olist-h10-observation:" + pin(capture), kind="state")
    return tuple(
        ScoreResult(
            metric=name,
            scorer_version=SCORER_VERSION,
            eligible=True,
            value=float(value) if value is not None else None,
            evidence=(reference,),
            failure=Failure(
                stage="scorer",
                code="scorer_error",
                message="required observation unavailable",
                retryable=False,
            )
            if value is None
            else None,
        )
        for name, value in values.items()
    )


def save_observation(root: Path, context: RunContext, capture: FieldCapture) -> None:
    root.mkdir(mode=0o700, exist_ok=True)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Olist observation directory is invalid")
    _write_exclusive(root / (pin(context) + ".json"), capture.canonical_json())


def read_olist_evidence(
    root: Path,
    loaded: LoadedManifest,
    *,
    evidence_sha256: str,
    candidate_sha256: str,
) -> VerifiedEvidence:
    """Verify H10 first, then bind and recompute every saved domain observation.

    This verifies evidence consistency, not annotation independence or release approval.
    Use the frozen candidate's installed packages; changed scorer/runtime bytes fail.
    """
    from olist_support.h10_config import verify_runtime
    from olist_support.h10_runtime import observed_result

    verified = read_evidence(
        root, loaded, evidence_sha256=evidence_sha256, candidate_sha256=candidate_sha256
    )
    verify_runtime(verified.manifest.candidate)
    directory = root / "observations"
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("Olist observation directory is missing or invalid")
    expected = set()
    for row in verified.batch.rows:
        if row.report is None:
            raise ValueError("Olist trial report is missing")
        context = row.task.context
        name = pin(context) + ".json"
        expected.add(name)
        path = directory / name
        if path.is_symlink():
            raise ValueError("Olist observation symlinks are not accepted")
        try:
            raw = path.read_bytes()
        except OSError:
            raise ValueError("Olist observation is missing or unreadable") from None
        reference = EvidenceReference(
            reference="olist-h10-observation:" + sha256(raw), kind="state"
        )
        scores = row.report.report.scores
        if any(s.evidence != (reference,) for s in scores):
            raise ValueError("Olist observation differs from sealed domain score")
        capture = FieldCapture.model_validate_json(raw)
        case = loaded.entry(context.case_id).case
        if (
            capture.canonical_json().encode() != raw
            or row.report.report.result != observed_result(context, capture)
            or scores != observed_scores(case, context, capture)
        ):
            raise ValueError("Olist domain results differ from independent recomputation")
    actual = tuple(directory.iterdir())
    if (
        any(p.is_symlink() or not p.is_file() for p in actual)
        or {p.name for p in actual} != expected
    ):
        raise ValueError("Olist observation inventory has missing or unexpected files")
    return verified
