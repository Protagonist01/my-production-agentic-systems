"""Encrypted-copy orchestration tests use invented data and explicit fake Restic results."""

import json
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from agent_harness.release_contracts import sha256
from test_olist_backup_catalog import archive

import olist_remote_recovery as module
from olist_backup_catalog import BackupCatalog, Marker


def fixture(tmp_path, *, backend="local_canary", attempts=4):
    executable = tmp_path / "fake-restic"
    executable.write_bytes(b"invented pinned executable")
    location = tmp_path / "repository-location"
    location.write_text(
        "s3:https://" + "a" * 32 + ".r2.cloudflarestorage.com/private-bucket/prefix"
        if backend == "r2"
        else str(tmp_path / "encrypted-repo")
    )
    password = tmp_path / "password"
    password.write_text("invented-repository-password-canary-123456")
    credentials = tmp_path / "credentials.json"
    credentials.write_text(
        json.dumps(
            {
                "AWS_ACCESS_KEY_ID": "invented-key",
                "AWS_SECRET_ACCESS_KEY": "private-key-canary",
                "AWS_DEFAULT_REGION": "auto",
            }
        )
    )
    repo = module.Repository(
        executable=executable,
        executable_sha256=sha256(executable.read_bytes()),
        repository_file=location,
        repository_id="a" * 64,
        password_file=password,
        credentials_file=credentials if backend == "r2" else None,
        backend=backend,
    )
    catalog = BackupCatalog.initialize(
        tmp_path / "catalog", Marker(source_identity_sha256="a" * 64, max_entries=10)
    )
    job = module.Job(
        repository=repo,
        root=Path(module.__file__).resolve().parent,
        trial="invented",
        catalog=catalog.directory,
        catalog_sha256=catalog.marker_sha256,
        journal=tmp_path / "journal",
        interval_seconds=600,
        max_cycle_seconds=240,
        max_snapshot_age_seconds=900,
        max_attempts=attempts,
    )
    job_pin = sha256(job.canonical_json().encode())
    module.initialize_journal(job, job_pin)
    return job, job_pin, catalog


class FakeRestic:
    raw = b""
    fail = False

    def __init__(self, repository, deadline):
        self.repository = repository

    def verify_repository(self):
        if self.fail:
            raise ValueError("private-remote-error-canary")

    def upload(self, raw, tag):
        self.verify_repository()
        type(self).raw = raw
        return "b" * 64

    def run(self, arguments):
        assert arguments == ["dump", "b" * 64, "/" + module.BUNDLE_NAME]
        return type(self).raw


def fake_cycle(tmp_path, monkeypatch, **kwargs):
    job, pin, cat = fixture(tmp_path, **kwargs)
    monkeypatch.setattr(module, "Restic", FakeRestic)
    monkeypatch.setattr(FakeRestic, "fail", False)
    monkeypatch.setattr(
        module, "capture_job", lambda *_: cat.publish(lambda: archive(seconds_old=1))
    )
    receipt, receipt_pin = module.cycle(job, pin, allow_local_canary=True)
    return job, pin, cat, receipt, receipt_pin


def test_verified_copy_recovery_preserves_bytes_without_claiming_host_loss(tmp_path, monkeypatch):
    job, pin, cat, receipt, receipt_pin = fake_cycle(tmp_path, monkeypatch)
    assert receipt_pin == sha256(receipt.canonical_json().encode())
    report = module.health(job, pin)
    assert report["fresh_uploaded_snapshot"] and not report["healthy"]
    assert report["backend"] == "local_canary" and report["completed"] == 1
    output = tmp_path / "recovered"
    result = module.recover(job.repository, receipt, output, seconds=30)
    assert result["recovered_bundle_verified"] and not result["database_restored"]
    assert not result["actual_host_loss_recovery"] and not result["release_allowed"]
    for name in ("archive.json", "complete.json"):
        assert (output / receipt.selection.entry / name).read_bytes() == (
            cat.directory / receipt.selection.entry / name
        ).read_bytes()
    with pytest.raises(ValueError, match="new private"):
        module.recover(job.repository, receipt, output, seconds=30)


def test_remote_receipt_health_is_separate_from_restore_and_capacity(tmp_path, monkeypatch):
    job, pin, cat, receipt, _ = fake_cycle(tmp_path, monkeypatch, backend="r2", attempts=2)
    assert module.health(job, pin)["healthy"]  # fake control-flow evidence, no actual R2 use
    assert not module.health(job, pin, datetime.now(UTC) + timedelta(hours=1))["healthy"]
    assert not module.health(job, pin, receipt.completed_at - timedelta(seconds=1))["healthy"]
    assert not module.health(job, pin)["actual_host_loss_recovery"]
    module.cycle(job, pin)
    assert module.health(job, pin)["capacity_reached"]
    with pytest.raises(ValueError):
        module.cycle(job, pin)
    assert len(list(job.journal.glob("run-*"))) == 2


def test_failure_stops_later_cycles_and_does_not_become_success(tmp_path, monkeypatch, capsys):
    job, pin, cat = fixture(tmp_path, backend="r2")
    monkeypatch.setattr(module, "Restic", FakeRestic)
    monkeypatch.setattr(FakeRestic, "fail", True)
    monkeypatch.setattr(
        module, "capture_job", lambda *_: pytest.fail("no SQL before repository check")
    )
    with pytest.raises(ValueError):
        module.cycle(job, pin)
    report = module.health(job, pin)
    assert report["failed_or_incomplete"] == 1 and not report["healthy"]
    assert not list(job.journal.glob("run-*/success.json"))
    with pytest.raises(ValueError):
        module.cycle(job, pin)
    assert len(list(job.journal.glob("run-*"))) == 1
    config = tmp_path / "job.json"
    config.write_bytes(job.canonical_json().encode())
    assert module.main(["run", "--config", str(config), "--pin", pin]) == 2
    assert "private-remote-error-canary" not in capsys.readouterr().out


def test_job_and_repository_pins_and_local_permission_are_not_inferred(tmp_path):
    job, pin, cat = fixture(tmp_path)
    with pytest.raises(ValueError, match="canonical pin"):
        module.cycle(job, "f" * 64, allow_local_canary=True)
    with pytest.raises(ValueError, match="explicit canary"):
        module.cycle(job, pin)
    with pytest.raises(ValueError):
        module.initialize_journal(job, "e" * 64)
    repo = job.repository.model_copy(update={"executable_sha256": "f" * 64})
    with pytest.raises(ValueError, match="executable"):
        module.Restic(repo, time.monotonic() + 10)
    assert not list(job.journal.glob("run-*"))


@pytest.mark.parametrize(
    "settings",
    [
        {"max_cycle_seconds": 400},
        {"interval_seconds": 0},
        {"max_attempts": 1001},
        {"max_cycle_seconds": 0},
        {"max_snapshot_age_seconds": 0},
    ],
)
def test_explicit_finite_bounded_job_limits(tmp_path, settings):
    job, _, _ = fixture(tmp_path)
    raw = job.model_dump(mode="python") | settings
    with pytest.raises(ValueError):
        module.Job.model_validate(raw)


def test_lock_collision_and_incomplete_or_forged_success_fail_closed(tmp_path, monkeypatch):
    job, pin, cat, receipt, _ = fake_cycle(tmp_path, monkeypatch, backend="r2")
    lock = job.journal / ".job-lock"
    lock.write_bytes(b"invented stale lock")
    with pytest.raises(FileExistsError):
        module.cycle(job, pin)
    assert module.health(job, pin)["writer_lock_present"]
    attempt = next(job.journal.glob("run-*"))
    changed = receipt.model_copy(update={"repository_id": "c" * 64})
    (attempt / "success.json").write_bytes(changed.canonical_json().encode())
    assert module.health(job, pin)["failed_or_incomplete"] == 1


@pytest.mark.parametrize("mode", ["wrong-repo", "partial", "ambiguous", "wrong-bytes", "no-id"])
def test_actual_transport_refuses_wrong_repository_partial_or_ambiguous_backup(
    tmp_path, monkeypatch, mode
):
    job, _, _ = fixture(tmp_path)
    calls = []

    def run(arguments, **kwargs):
        calls.append(arguments)
        assert "--repository-file" in arguments and "--repo-file" not in arguments
        assert not any(x in arguments for x in ["init", "unlock", "forget", "prune"])
        assert "private-key-canary" not in str(arguments)
        if "config" in arguments:
            raw = json.dumps({"id": "f" * 64 if mode == "wrong-repo" else "a" * 64}).encode()
        elif "backup" in arguments:
            raw = json.dumps(
                {"message_type": "summary", **({} if mode == "no-id" else {"snapshot_id": "b" * 8})}
            ).encode()
            if mode == "partial":
                return SimpleNamespace(returncode=3, stdout=raw, stderr=b"private-provider-error")
        elif "snapshots" in arguments:
            raw = json.dumps([{"id": "b" * 64}] * (2 if mode == "ambiguous" else 1)).encode()
        else:
            raw = b"different" if mode == "wrong-bytes" else b"payload"
        return SimpleNamespace(returncode=0, stdout=raw, stderr=b"")

    monkeypatch.setattr(module.subprocess, "run", run)
    client = module.Restic(job.repository, time.monotonic() + 10)
    with pytest.raises(ValueError):
        client.upload(b"payload", "run-" + "a" * 32)
    assert calls


def test_disabled_task_uses_explicit_operator_arguments_and_overlap_guard(tmp_path):
    job, pin, _ = fixture(tmp_path, backend="r2")
    raw = module.render_task(job, tmp_path / "private job & params.json", pin, "machine\\operator")
    task = ET.fromstring(raw)
    ns = {"t": "http://schemas.microsoft.com/windows/2004/02/mit/task"}
    assert task.find("t:Settings/t:Enabled", ns).text == "false"
    assert task.find("t:Settings/t:MultipleInstancesPolicy", ns).text == "IgnoreNew"
    assert task.find("t:Principals/t:Principal/t:RunLevel", ns).text == "LeastPrivilege"
    assert "private job & params.json" in task.find("t:Actions/t:Exec/t:Arguments", ns).text
    assert "private-key-canary" not in raw.decode()
    assert not raw.startswith(b"<?xml")  # compatible with Windows Unicode COM registration
    shorter = job.model_copy(update={"interval_seconds": 30})
    with pytest.raises(ValueError, match="one minute"):
        module.render_task(
            shorter, tmp_path / "job.json", sha256(shorter.canonical_json().encode()), "operator"
        )


def test_recovery_wrong_pin_bytes_existing_output_and_traversal_are_rejected(tmp_path, monkeypatch):
    job, pin, cat, receipt, _ = fake_cycle(tmp_path, monkeypatch)
    raw = FakeRestic.raw
    monkeypatch.setattr(FakeRestic, "raw", raw + b" ")
    with pytest.raises(ValueError, match="independent receipt"):
        module.recover(job.repository, receipt, tmp_path / "bad", seconds=30)
    value = json.loads(raw)
    value["entry"] = "../escape"
    changed = module.encode(value)
    monkeypatch.setattr(FakeRestic, "raw", changed)
    forged = receipt.model_copy(
        update={"bundle_sha256": sha256(changed), "bundle_bytes": len(changed)}
    )
    with pytest.raises(ValueError):
        module.recover(job.repository, forged, tmp_path / "escape", seconds=30)
    assert not (tmp_path / "escape").exists()


def test_actual_journal_writer_death_is_visible_and_blocks_resume(tmp_path):
    job, pin, _ = fixture(tmp_path)
    # This subprocess deliberately exits after acquiring only this invented journal lock.
    child = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import os,sys; from pathlib import Path; "
                "root=Path(sys.argv[1]); "
                "fd=os.open(root/'.job-lock',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600); "
                "p=root/('run-'+'d'*32);p.mkdir();(p/'started.json').write_text('{}');os._exit(37)"
            ),
            str(job.journal),
        ],
        capture_output=True,
        timeout=30,
    )
    assert child.returncode == 37
    report = module.health(job, pin)
    assert report["writer_lock_present"] and report["failed_or_incomplete"] == 1
    with pytest.raises(FileExistsError):
        module.cycle(job, pin, allow_local_canary=True)
