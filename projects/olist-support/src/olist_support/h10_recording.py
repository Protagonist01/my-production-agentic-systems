"""Explicit new H10 execution; no historical-row import, credential loading or release grant."""

import json
import subprocess
from dataclasses import replace
from pathlib import Path

from agent_harness.cases import LoadedManifest
from agent_harness.fresh_recording import record_candidate
from agent_harness.release_contracts import EvidenceManifest
from agent_harness.trials import TrialSchedule, validate_schedule

from olist_support.h10_environment import ENVIRONMENT_VERSION, FIXTURE, OlistEnvironment
from olist_support.h10_manifest import SCORER_ID, OlistMetadata, private_case
from olist_support.h10_runtime import OlistFreshFactory
from olist_support.policy_cases import PolicyCases, external


def record_olist(
    schedule: TrialSchedule,
    loaded: LoadedManifest,
    factory: OlistFreshFactory,
    environment: OlistEnvironment,
    output: Path,
    *,
    candidate_sha256: str,
    source_root: Path,
    source_database: Path | None = None,
) -> EvidenceManifest:
    """Caller supplies a reviewed pin/budget and separately authorizes any provider calls.

    Mock runs retain mock origin and cannot qualify release. Unknown provider usage
    stays unknown; H10 read_evidence rejects incomplete accounting without a retry.
    """
    validate_schedule(schedule, loaded)
    if environment.loaded.pin != loaded.pin or (environment.version, environment.fixture) != (
        ENVIRONMENT_VERSION,
        FIXTURE,
    ):
        raise ValueError("Olist environment belongs to another reviewed population")
    for entry in loaded.manifest.entries:
        label, _ = private_case(entry.case)
        if (
            entry.scorer_id != SCORER_ID
            or entry.group_id != label.group_id
            or (entry.split == "holdout") != (label.split == "holdout")
        ):
            raise ValueError("Olist entry differs from reviewed group/split/scorer")
    factory.validate()
    if factory.origin == "provider":
        from olist_support.fresh_cli import verify_original_source

        if source_database is None:
            raise ValueError("provider capture requires its separately pinned original database")
        external(output)
        revision = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=source_root, text=True
        ).strip()
        dirty = subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=source_root, text=True
        ).strip()
        if dirty or revision != factory.candidate.code_revision:
            raise ValueError("provider capture requires the clean pinned source revision")
        metadata = tuple(
            OlistMetadata.model_validate_json(json.dumps(e.case.hidden_state))
            for e in loaded.manifest.entries
        )
        if len({m.source_database_sha256 for m in metadata}) != 1:
            raise ValueError("provider population contains different source databases")
        cases = PolicyCases(
            source_database_sha256=metadata[0].source_database_sha256,
            source_manifest_sha256=loaded.manifest.entries[0].case.snapshot_ref,
            entries=tuple(m.olist_case for m in metadata),
        )
        verify_original_source(source_database, cases)
    return record_candidate(
        schedule,
        loaded,
        replace(factory, observation_root=output / "observations"),
        environment,
        output,
        candidate=factory.candidate,
        candidate_sha256=candidate_sha256,
        source_root=source_root,
    )
