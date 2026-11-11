"""Required real SQL plus real Restic encrypted-copy/restore; still one-host mechanism evidence."""

import json
import os
import secrets
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

import pytest
from agent_harness.postgres import drop_trial
from agent_harness.release_contracts import sha256
from olist_support.backup import capture, read, restore
from olist_support.console_cases import CaseStore
from olist_support.operations_cli import bootstrap
from olist_support.service_health import readiness
from test_olist_business import app as app
from test_olist_console import console as console
from test_olist_console import create_case, decide, observed

from olist_backup_catalog import BackupCatalog, Marker, new_file
from olist_remote_recovery import Receipt, Repository, Restic, bundle, recover


def test_actual_encrypted_database_copy_restores_state_and_preserves_newer_source(
    console, tmp_path
):
    configured = os.environ.get("OLIST_RESTIC_CANARY_EXECUTABLE")
    executable = (
        Path(configured)
        if configured
        else Path(__file__).resolve().parents[2] / "artifacts/tools/restic-canary"
    )
    if not executable.is_file():
        pytest.fail(
            "Verified Restic 0.19.1 binary is required for encrypted SQL recovery acceptance"
        )
    server, source, _ = console
    store, pending, operator, reviewer = create_case(console)
    store, committed, operator2, reviewer2 = create_case(console)
    approved = decide(store, committed, reviewer2, console=console)
    original = store.resume(
        reviewer2, committed.case_id, approved.action_digest, run_limit_minor=10000
    )
    catalog = BackupCatalog.initialize(
        tmp_path / "catalog",
        Marker(source_identity_sha256=sha256(source.marker.encode()), max_entries=4),
    )
    selected = catalog.publish(
        lambda: capture(
            server, source, code_revision="invented-sql-canary", environment_lock="a" * 64
        )
    )
    password = tmp_path / "repository-password"
    new_file(password, secrets.token_hex(32).encode())
    location = tmp_path / "repository-location"
    new_file(location, str(tmp_path / "encrypted-repository").encode())
    arguments = [
        str(executable),
        "--no-cache",
        "--repository-file",
        str(location),
        "--password-file",
        str(password),
    ]
    initialized = subprocess.run([*arguments, "--json", "init"], capture_output=True, timeout=60)
    assert initialized.returncode == 0, "isolated local encrypted repository initialization failed"
    configuration = subprocess.run([*arguments, "cat", "config"], capture_output=True, timeout=30)
    assert configuration.returncode == 0
    repository = Repository(
        executable=executable.resolve(),
        executable_sha256=sha256(executable.read_bytes()),
        repository_file=location,
        repository_id=json.loads(configuration.stdout)["id"],
        password_file=password,
        backend="local_canary",
    )
    raw = bundle(catalog, selected)
    started = time.monotonic_ns()
    snapshot = Restic(repository, time.monotonic() + 90).upload(raw, "invented-sql-canary")
    receipt = Receipt(
        job_sha256="b" * 64,
        repository_id=repository.repository_id,
        backend="local_canary",
        snapshot_id=snapshot,
        bundle_sha256=sha256(raw),
        bundle_bytes=len(raw),
        catalog_sha256=catalog.marker_sha256,
        selection=selected,
        completed_at=datetime.now(UTC),
        elapsed_ns=time.monotonic_ns() - started,
    )
    later = decide(store, pending, reviewer, console=console)
    store.resume(reviewer, pending.case_id, later.action_digest, run_limit_minor=10000)
    newer_source = observed(console, pending)
    recovered = tmp_path / "separate-recovery-directory"
    result = recover(repository, receipt, recovered, seconds=60)
    assert result["recovered_bundle_verified"] and not result["actual_host_loss_recovery"]
    archive = read(recovered / selected.entry / "archive.json", result["archive_sha256"])
    target = restore(
        server,
        source.workspace_key,
        "encrypted-recovery-target",
        archive,
        archive_sha256=selected.archive_sha256,
        bootstrap=bootstrap,
    )
    try:
        rebuilt = CaseStore(lambda: server.connect_trial(target))
        assert rebuilt.detail(reviewer, pending.case_id)[0].status == "review_required"
        assert (
            rebuilt.resume(
                reviewer2, committed.case_id, approved.action_digest, run_limit_minor=10000
            )
            == original
        )
        assert readiness(lambda: server.connect_trial(target))["ready"]
        assert observed(console, pending) == newer_source
        check = subprocess.run(
            [*arguments, "--json", "check", "--read-data"], capture_output=True, timeout=60
        )
        assert check.returncode == 0, "actual encrypted repository full-data check failed"
    finally:
        drop_trial(server, target)
