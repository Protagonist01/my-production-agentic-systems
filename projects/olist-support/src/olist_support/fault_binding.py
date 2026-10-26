"""Bind supplementary operator SIM crash drills to a frozen receipted candidate.

This supplies neither provider-quality evidence nor an unobserved full fault matrix.
Required trial scopes come from the separately frozen protocol, never this bundle.
"""

from pathlib import Path
from typing import Literal

from agent_harness.cases import LoadedManifest
from agent_harness.contracts import Contract
from agent_harness.release_contracts import Sha256, pin, sha256
from agent_harness.release_evidence import VerifiedEvidence

from olist_support.crash_evidence import read_crash
from olist_support.h10_config import verify_runtime
from olist_support.h10_manifest import private_case


class FaultEntry(Contract):
    context_sha256: Sha256
    stage: Literal["before_commit", "after_commit"]
    evidence_sha256: Sha256


class FaultBundle(Contract):
    version: Literal["olist-bound-crash-companion-v1"] = "olist-bound-crash-companion-v1"
    candidate_sha256: Sha256
    candidate_evidence_sha256: Sha256
    dataset_sha256: Sha256
    entries: tuple[FaultEntry, ...]


def read_fault_bundle(
    root: Path,
    loaded: LoadedManifest,
    candidate: VerifiedEvidence,
    *,
    bundle_sha256: str,
    required_contexts: tuple[str, ...],
) -> dict[str, object]:
    path = root / "bundle.json"
    if root.is_symlink() or path.is_symlink():
        raise ValueError("fault companion symlinks rejected")
    raw = path.read_bytes()
    bundle = FaultBundle.model_validate_json(raw)
    if sha256(raw) != bundle_sha256 or raw != bundle.canonical_json().encode():
        raise ValueError("fault bundle differs from external pin/canonical bytes")
    verify_runtime(candidate.manifest.candidate)
    if (
        bundle.candidate_sha256 != pin(candidate.manifest.candidate)
        or bundle.candidate_evidence_sha256 != pin(candidate.manifest)
        or bundle.dataset_sha256 != loaded.pin.sha256
        or candidate.batch.schedule.manifest != loaded.pin
        or not required_contexts
        or len(set(required_contexts)) != len(required_contexts)
    ):
        raise ValueError("fault companion candidate/population/protocol scope differs")
    contexts = {pin(t.context): t.context for t in candidate.batch.schedule.tasks}
    if set(required_contexts) - contexts.keys():
        raise ValueError("required fault scope is outside fresh schedule")
    expected = {
        (scope, stage) for scope in required_contexts for stage in ("before_commit", "after_commit")
    }
    actual = {(e.context_sha256, e.stage) for e in bundle.entries}
    if actual != expected or len(actual) != len(bundle.entries):
        raise ValueError("missing, duplicate or unexpected fault boundaries")
    files = {"bundle.json"}
    reports = []
    for entry in bundle.entries:
        context = contexts[entry.context_sha256]
        label, _ = private_case(loaded.entry(context.case_id).case)
        if label.expected.action != "propose_full_refund":
            raise ValueError("operator refund drill cannot stand in for a review case")
        drill_context = context.model_copy(
            update={"mode": "offline_fake", "run_id": context.run_id + "-" + entry.stage}
        )
        relative = Path(entry.context_sha256) / entry.stage
        directory = root / relative
        if directory.parent.is_symlink():
            raise ValueError("fault scope symlink rejected")
        report = read_crash(
            directory, evidence_sha256=entry.evidence_sha256, label=label, context=drill_context
        )
        if report["version"] != (
            "olist-operator-process-crash-v2"
            if entry.stage == "before_commit"
            else "olist-operator-process-crash-v1"
        ):
            raise ValueError("fault stage differs from bound artifact")
        files.add((relative / "crash.json").as_posix())
        reports.append(report)
    if {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()} != files:
        raise ValueError("unexpected fault companion files")
    return dict(
        bundle_sha256=bundle_sha256,
        candidate_evidence_sha256=pin(candidate.manifest),
        covered_contexts=len(required_contexts),
        boundary_observations=len(reports),
        passed=all(r["passed"] is True for r in reports),
        provider_calls=0,
        mechanism_only=True,
        full_fault_matrix_complete=False,
        release_allowed=False,
    )
