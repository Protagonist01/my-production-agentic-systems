"""Actual private snapshot/restore of pending review, committed receipt and checkpoints."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from agent_harness.postgres import Trial, drop_trial
from agent_harness.release_contracts import pin
from fastapi.testclient import TestClient
from olist_support.backup import capture, read, restore, save
from olist_support.business import setup
from olist_support.console_api import create_app
from olist_support.console_auth import AuthStore, setup_console
from olist_support.console_cases import CaseStore
from olist_support.recovery_exercise import RecoveryObjective, RecoveryReport, exercise
from olist_support.service_health import readiness
from olist_support.workflow_postgres import setup_checkpoints
from test_olist_business import app as app
from test_olist_console import console as console
from test_olist_console import create_case, decide, observed


def bootstrap(server, trial):
    for setup_fn in (setup, setup_checkpoints, setup_console):
        with server.connect(trial.name) as admin:
            setup_fn(admin, trial.name)


def test_private_snapshot_restores_review_ledger_checkpoint_and_duplicate_without_touching_source(
    console, tmp_path
):
    server, source, _ = console
    store, pending, operator, reviewer = create_case(console)
    store, committed, operator2, reviewer2 = create_case(console)
    approved = decide(store, committed, reviewer2)
    result = store.resume(
        reviewer2, committed.case_id, approved.action_digest, run_limit_minor=10000
    )
    archive = capture(
        server, source, code_revision="invented-frozen-code", environment_lock="a" * 64
    )
    path = tmp_path / "private-snapshot.json"
    digest = save(path, archive)
    assert read(path, digest) == archive
    with pytest.raises(FileExistsError):
        save(path, archive)
    # A later source effect must survive restore into the separate target.
    approved_pending = decide(store, pending, reviewer)
    later = store.resume(
        reviewer, pending.case_id, approved_pending.action_digest, run_limit_minor=10000
    )
    source_after = observed(console, pending)
    target = restore(
        server,
        source.workspace_key,
        "olist-restored-operations",
        archive,
        archive_sha256=digest,
        bootstrap=bootstrap,
    )
    try:
        rebuilt = CaseStore(lambda: server.connect_trial(target))
        assert rebuilt.detail(reviewer, pending.case_id)[0].status == "review_required"
        assert (
            rebuilt.detail(reviewer2, committed.case_id)[0]
            == store.detail(reviewer2, committed.case_id)[0]
        )
        assert (
            rebuilt.resume(
                reviewer2, committed.case_id, approved.action_digest, run_limit_minor=10000
            )
            == result
        )
        assert observed(console, pending) == source_after and later is not None
        assert readiness(lambda: server.connect_trial(target))["ready"]
        # A measured operator exercise uses another new target and preserves both source
        # effects. The numeric objective is an invented test constraint, not a production SLA.
        exercised, report = exercise(
            server,
            source,
            "olist-measured-recovery",
            code_revision="invented-frozen-code",
            environment_lock="a" * 64,
            archive_path=tmp_path / "exercise-archive.json",
            report_path=tmp_path / "exercise-report.json",
            objective=RecoveryObjective(max_restore_seconds=60.0),
            bootstrap=bootstrap,
        )
        try:
            assert report.passed and report.rows > 0 and report.restore_verify_ns > 0
            assert report.source_unchanged and report.restored_ready
            assert not report.production_rpo_rto_verified and not report.release_allowed
            assert (
                RecoveryReport.model_validate_json((tmp_path / "exercise-report.json").read_bytes())
                == report
            )
            assert observed(console, pending) == source_after
            assert (
                CaseStore(lambda: server.connect_trial(exercised))
                .detail(reviewer, pending.case_id)[0]
                .status
                == "committed"
            )
        finally:
            drop_trial(server, exercised)
        app = create_app(
            rebuilt,
            AuthStore(lambda: server.connect_trial(target)),
            origin="http://127.0.0.1:8765",
            trial_id=target.name,
            code_revision="invented",
            environment_lock="a" * 64,
            run_limit_minor=10000,
        )
        client = TestClient(app, base_url="http://127.0.0.1:8765")
        assert client.get("/health/live").json()["live"]
        assert client.get("/health/ready").status_code == 200
        with pytest.raises(ValueError, match="already exists"):
            restore(
                server,
                source.workspace_key,
                target.trial_id,
                archive,
                archive_sha256=digest,
                bootstrap=bootstrap,
            )
        assert rebuilt.detail(reviewer, pending.case_id)[0].status == "review_required"
    finally:
        drop_trial(server, target)
    assert observed(console, pending) == source_after
    with pytest.raises(ValueError, match="exact archive pin"):
        restore(
            server,
            source.workspace_key,
            "bad-pin",
            archive,
            archive_sha256="b" * 64,
            bootstrap=bootstrap,
        )
    changed = archive.model_copy(update={"schema_sha256": "c" * 64})
    with pytest.raises(ValueError, match="version differs"):
        restore(
            server,
            source.workspace_key,
            "bad-schema",
            changed,
            archive_sha256=pin(changed),
            bootstrap=bootstrap,
        )
    missing = Trial(source.workspace_key, "bad-schema", "unused")
    with server.connect() as admin:
        assert (
            admin.execute("SELECT 1 FROM pg_database WHERE datname=%s", (missing.name,)).fetchone()
            is None
        )
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="external pin"):
        read(path, digest)


def test_readiness_uses_runtime_permissions_and_detects_actual_schema_mismatch(console):
    server, trial, _ = console

    def connect():
        return server.connect_trial(trial)

    assert readiness(connect)["ready"]
    with server.connect(trial.name) as admin:
        old = admin.execute("SELECT sha256 FROM olist_app.schema_pin WHERE version=1").fetchone()[0]
        admin.execute("UPDATE olist_app.schema_pin SET sha256=%s WHERE version=1", ("0" * 64,))
    try:
        result = readiness(connect)
        assert not result["ready"] and result["reason"] == "schema_version_mismatch"
    finally:
        with server.connect(trial.name) as admin:
            admin.execute("UPDATE olist_app.schema_pin SET sha256=%s WHERE version=1", (old,))


def test_operator_cli_freezes_backup_and_persists_only_new_owned_restore_identity(
    tmp_path, monkeypatch, capsys
):
    from agent_harness.local_services import Workspace
    from olist_support.operations_cli import bootstrap, main

    root = tmp_path / "operator-checkout"
    root.mkdir()
    shutil.copyfile(Path(__file__).resolve().parents[2] / "compose.yaml", root / "compose.yaml")
    (root / "uv.lock").write_text("# invented operator fixture lock\n", encoding="utf-8")
    (root / ".gitignore").write_text(".agent-local/\n", encoding="utf-8")
    for args in (
        ("init",),
        ("add", "compose.yaml", "uv.lock", ".gitignore"),
        (
            "-c",
            "user.name=Invented Test",
            "-c",
            "user.email=invented@example.invalid",
            "commit",
            "-m",
            "Invented operator checkout",
        ),
    ):
        subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)
    workspace = Workspace(root)
    workspace.up()
    source = workspace.create("operator-source")
    target = measured = None
    try:
        server = workspace.server()
        bootstrap(server, source)
        archive = tmp_path / "private-operator-archive.json"
        monkeypatch.setattr(
            "sys.argv",
            [
                "ops",
                "--root",
                str(root),
                "backup",
                "--trial",
                source.trial_id,
                "--output",
                str(archive),
            ],
        )
        assert main() == 0
        backup_result = json.loads(capsys.readouterr().out)
        assert backup_result["elapsed_seconds"] > 0 and backup_result["provider_calls"] == 0
        monkeypatch.setattr(
            "sys.argv",
            [
                "ops",
                "--root",
                str(root),
                "restore-new",
                "--archive",
                str(archive),
                "--archive-sha256",
                backup_result["archive_sha256"],
                "--new-trial",
                "operator-restored",
            ],
        )
        assert main() == 0
        restored = json.loads(capsys.readouterr().out)
        assert restored["restored"] and not restored["source_overwritten"]
        target = workspace.load_trial("operator-restored")
        assert main() == 2
        capsys.readouterr()
        monkeypatch.setattr(
            "sys.argv", ["ops", "--root", str(root), "ready", "--trial", target.trial_id]
        )
        assert main() == 0 and json.loads(capsys.readouterr().out)["ready"]
        monkeypatch.setattr(
            "sys.argv",
            [
                "ops",
                "--root",
                str(root),
                "exercise",
                "--trial",
                source.trial_id,
                "--new-trial",
                "operator-measured",
                "--archive",
                str(tmp_path / "measured.json"),
                "--report",
                str(tmp_path / "measured-report.json"),
                "--max-restore-seconds",
                "0.000000001",
            ],
        )
        # An intentionally impossible objective fails explicitly, while preserving the
        # actual new target/report for inspection. It must not fabricate a passed SLA.
        assert main() == 2
        result = json.loads(capsys.readouterr().out)
        assert not result["exercise_passed"] and not result["production_rpo_rto_verified"]
        measured = workspace.load_trial("operator-measured")
        report = RecoveryReport.model_validate_json(
            (tmp_path / "measured-report.json").read_bytes()
        )
        assert result["report_sha256"] == pin(report)
        assert report.snapshot_verified and report.source_unchanged and report.restored_ready
        assert not report.within_restore_objective and not report.passed
        assert main() == 2
        capsys.readouterr()
    finally:
        server = workspace.server()
        if target:
            drop_trial(server, target)
        if measured:
            drop_trial(server, measured)
        drop_trial(server, source)
        workspace.down(destroy=True)
