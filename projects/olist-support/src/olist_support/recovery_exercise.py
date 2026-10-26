"""Measured local recovery into a new target, with an explicit operator time objective."""

import os
import time
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Literal

from agent_harness.contracts import Contract
from agent_harness.postgres import Server, Trial, drop_trial
from agent_harness.release_contracts import Sha256, sha256
from pydantic import Field

from olist_support.backup import capture, restore, save
from olist_support.policy_cases import external
from olist_support.service_health import readiness


class RecoveryObjective(Contract):
    max_restore_seconds: Annotated[float, Field(gt=0, le=3600)]
    recovery_point: Literal["snapshot_only_no_wal"] = "snapshot_only_no_wal"


class RecoveryReport(Contract):
    version: Literal["olist-local-recovery-exercise-v1"] = "olist-local-recovery-exercise-v1"
    archive_sha256: Sha256
    schema_sha256: Sha256
    environment_lock: Sha256
    code_revision_sha256: Sha256
    objective: RecoveryObjective
    capture_ns: Annotated[int, Field(ge=0)]
    restore_verify_ns: Annotated[int, Field(ge=0)]
    tables: Annotated[int, Field(gt=0)]
    rows: Annotated[int, Field(ge=0)]
    source_unchanged: bool
    restored_ready: bool
    within_restore_objective: bool
    snapshot_verified: Literal[True] = True
    source_overwritten: Literal[False] = False
    production_rpo_rto_verified: Literal[False] = False
    provider_calls: Literal[0] = 0
    release_allowed: Literal[False] = False

    @property
    def passed(self) -> bool:
        return self.source_unchanged and self.restored_ready and self.within_restore_objective


def exercise(
    server: Server,
    source: Trial,
    new_trial_id: str,
    *,
    code_revision: str,
    environment_lock: str,
    archive_path: Path,
    report_path: Path,
    objective: RecoveryObjective,
    bootstrap: Callable[[Server, Trial], None],
) -> tuple[Trial, RecoveryReport]:
    objective = RecoveryObjective.model_validate_json(objective.canonical_json())
    if archive_path.is_symlink() or report_path.is_symlink():
        raise ValueError("exercise requires new private output paths")
    archive_path, report_path = external(archive_path), external(report_path)
    if archive_path == report_path or archive_path.exists() or report_path.exists():
        raise ValueError("exercise outputs must be different new private paths")
    if not archive_path.parent.is_dir() or not report_path.parent.is_dir():
        raise ValueError("prepare private output parents before exercise")
    started = time.monotonic_ns()
    archive = capture(
        server, source, code_revision=code_revision, environment_lock=environment_lock
    )
    digest = save(archive_path, archive)
    captured = time.monotonic_ns()
    target = restore(
        server,
        source.workspace_key,
        new_trial_id,
        archive,
        archive_sha256=digest,
        bootstrap=bootstrap,
    )
    try:
        ready = readiness(lambda: server.connect_trial(target))["ready"] is True
        restored = time.monotonic_ns()
        # A changing source is explicitly incomplete evidence, never a silent pass.
        after = capture(
            server, source, code_revision=code_revision, environment_lock=environment_lock
        )
        report = RecoveryReport(
            archive_sha256=digest,
            schema_sha256=archive.schema_sha256,
            environment_lock=environment_lock,
            code_revision_sha256=sha256(code_revision.encode()),
            objective=objective,
            capture_ns=captured - started,
            restore_verify_ns=restored - captured,
            tables=len(archive.tables),
            rows=sum(t.rows for t in archive.tables),
            source_unchanged=after.tables == archive.tables
            and after.schema_sha256 == archive.schema_sha256,
            restored_ready=ready,
            within_restore_objective=(restored - captured) / 1e9 <= objective.max_restore_seconds,
        )
        descriptor = os.open(report_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as output:
            output.write(report.canonical_json().encode())
            output.flush()
            os.fsync(output.fileno())
    except BaseException:
        drop_trial(server, target)
        raise
    return target, report
