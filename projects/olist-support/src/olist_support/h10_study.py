"""Olist-specific read-back before shared methodology projection; no provider calls."""

from pathlib import Path

from agent_harness.baseline_recording import VerifiedBaseline
from agent_harness.cases import LoadedManifest
from agent_harness.contracts import ModelRequest
from agent_harness.evaluation_standards import (
    StandardCase,
    StandardProfile,
    StandardProtocol,
    StandardStudy,
)
from agent_harness.evaluation_study import assemble_study
from agent_harness.release_evidence import VerifiedEvidence

from olist_support.field_evaluation import FIELDS
from olist_support.h10_evidence import read_olist_evidence
from olist_support.h10_manifest import private_case


def assemble_olist_study(
    profile: StandardProfile,
    protocol: StandardProtocol,
    cases: tuple[StandardCase, ...],
    loaded: LoadedManifest,
    *,
    baseline_root: Path,
    baseline_evidence_sha256: str,
    baseline_candidate_sha256: str,
    candidate_root: Path,
    candidate_evidence_sha256: str,
    candidate_sha256: str,
    required_case_ids: tuple[str, ...],
    baseline_route: ModelRequest | None = None,
) -> StandardStudy:
    if profile.agent != "olist" or set(profile.required_fields) != set(FIELDS):
        raise ValueError("Olist study requires its complete field profile")
    labels = {e.case.case_id: private_case(e.case)[0] for e in loaded.manifest.entries}
    if len(cases) != len(labels) or {c.case_id for c in cases} != set(labels):
        raise ValueError("Olist methodology population differs from private labels")
    for case in cases:
        if case.split != labels[case.case_id].split:
            raise ValueError("Olist original regression/development split must be retained")
    baseline: VerifiedEvidence | VerifiedBaseline
    if baseline_route is None:
        baseline = read_olist_evidence(
            baseline_root,
            loaded,
            evidence_sha256=baseline_evidence_sha256,
            candidate_sha256=baseline_candidate_sha256,
        )
    else:
        from olist_support.baseline_recording import read_olist_baseline

        baseline = read_olist_baseline(
            baseline_root,
            loaded,
            route=baseline_route,
            evidence_sha256=baseline_evidence_sha256,
            candidate_sha256=baseline_candidate_sha256,
        )
    candidate = read_olist_evidence(
        candidate_root,
        loaded,
        evidence_sha256=candidate_evidence_sha256,
        candidate_sha256=candidate_sha256,
    )
    return assemble_study(
        profile, protocol, cases, loaded, baseline, candidate, required_case_ids=required_case_ids
    )
