"""Catalog failures remain visible without deleting the last verified snapshot."""

import base64
import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from agent_harness.release_contracts import sha256
from olist_support.backup import SCHEMAS, Archive, TableCopy

import olist_backup_catalog as module


def archive(*, seconds_old=600, source="a" * 64):
    raw = b"invented binary fixture; not a PostgreSQL restore witness"
    return Archive(
        created_at=datetime.now(UTC) - timedelta(seconds=seconds_old),
        source_identity_sha256=source,
        code_revision="invented-test-revision",
        environment_lock="b" * 64,
        postgres_major=17,
        server_build="invented-server",
        schema_sha256="c" * 64,
        tables=tuple(
            TableCopy(
                namespace=namespace,
                table="invented",
                data_base64=base64.b64encode(raw).decode(),
                data_sha256=sha256(raw),
                rows=1,
            )
            for namespace in SCHEMAS
        ),
    )


def catalog(tmp_path, capacity=10):
    return module.BackupCatalog.initialize(
        tmp_path / "private-backups",
        module.Marker(source_identity_sha256="a" * 64, max_entries=capacity),
    )


def test_freshness_uses_snapshot_not_newer_completion_and_mtime(tmp_path):
    cat = catalog(tmp_path)
    source = archive(seconds_old=1000)
    selected = cat.publish(lambda: source)
    report = cat.status(max_age_seconds=900)
    assert report["latest"]["entry"] == selected.entry
    assert report["latest"]["age_seconds"] >= 1000
    assert not report["healthy"] and not report["fresh_snapshot_available"]
    assert not report["actual_restore_verified"] and not report["host_loss_rpo_rto_verified"]
    assert report["provider_calls"] == 0 and not report["release_allowed"]
    boundary = cat.status(max_age_seconds=1000, now=source.created_at + timedelta(seconds=1000))
    # Completion happened after that boundary; a clock behind completion must fail closed.
    assert boundary["invalid"] == 1


def test_selects_newest_snapshot_even_when_older_snapshot_published_last(tmp_path, capsys):
    cat = catalog(tmp_path)
    newer = cat.publish(lambda: archive(seconds_old=120))
    older = cat.publish(lambda: archive(seconds_old=600))
    report = cat.status(max_age_seconds=900)
    assert report["healthy"] and report["completed"] == 2
    assert report["latest"]["entry"] == newer.entry != older.entry
    assert (
        module.main(
            [
                "--catalog",
                str(cat.directory),
                "status",
                "--catalog-sha256",
                cat.marker_sha256,
                "--max-age-seconds",
                "900",
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["latest"]["entry"] == newer.entry


@pytest.mark.parametrize("stage", ["producer", "archive.json", "complete.json", "fsync"])
def test_failed_publication_preserves_old_archive_and_reports_incomplete(
    tmp_path, monkeypatch, stage
):
    cat = catalog(tmp_path)
    old = cat.publish(lambda: archive())
    before = (cat.directory / old.entry / "archive.json").read_bytes()
    original = module.new_file

    def write(path, raw):
        if path.name == stage:
            raise OSError("private-failure-canary")
        original(path, raw)

    def producer():
        if stage == "producer":
            raise OSError("private-failure-canary")
        return archive()

    monkeypatch.setattr(module, "new_file", write)
    if stage == "fsync":

        def no_flush(fd):
            raise OSError("private-fsync-canary")

        monkeypatch.setattr(module.os, "fsync", no_flush)
    with pytest.raises(OSError):
        cat.publish(producer)
    report = cat.status(max_age_seconds=900)
    assert report["fresh_snapshot_available"] and not report["healthy"]
    assert report["incomplete"] == 1 and report["latest"]["entry"] == old.entry
    assert (cat.directory / old.entry / "archive.json").read_bytes() == before
    assert not (cat.directory / ".writer-lock").exists()


@pytest.mark.parametrize("target", ["archive.json", "complete.json"])
def test_corrupt_newer_entry_never_silently_makes_catalog_healthy(tmp_path, target):
    cat = catalog(tmp_path)
    old = cat.publish(lambda: archive(seconds_old=600))
    newer = cat.publish(lambda: archive(seconds_old=100))
    (cat.directory / newer.entry / target).write_bytes(b'{"secret":"private-canary"}')
    report = cat.status(max_age_seconds=900)
    assert report["invalid"] == 1 and report["latest"]["entry"] == old.entry
    assert not report["healthy"] and "private-canary" not in json.dumps(report)


def test_inner_table_digest_is_checked_even_if_archive_is_rehashed(tmp_path):
    cat = catalog(tmp_path)
    original = archive()
    bad_table = original.tables[0].model_copy(update={"data_sha256": "f" * 64})
    bad = original.model_copy(update={"tables": (bad_table, *original.tables[1:])})
    with pytest.raises(ValueError, match="table bytes"):
        cat.publish(lambda: bad)
    assert cat.status(max_age_seconds=900)["incomplete"] == 1


@pytest.mark.parametrize("seconds", [0, -1, float("nan"), float("inf"), 86401])
def test_explicit_freshness_limit_is_finite_positive_and_bounded(tmp_path, seconds):
    with pytest.raises(ValueError):
        catalog(tmp_path).status(max_age_seconds=seconds)


def test_future_clock_naive_clock_and_empty_catalog_are_not_healthy(tmp_path):
    cat = catalog(tmp_path)
    assert not cat.status(max_age_seconds=900)["healthy"]
    cat.publish(lambda: archive())
    report = cat.status(max_age_seconds=900, now=datetime.now(UTC) - timedelta(hours=1))
    assert report["invalid"] == 1 and report["latest"] is None
    with pytest.raises(ValueError):
        cat.status(max_age_seconds=900, now=datetime.now())


def test_capacity_stops_before_producer_and_deletes_nothing(tmp_path):
    cat = catalog(tmp_path, capacity=1)
    selected = cat.publish(lambda: archive())
    report = cat.status(max_age_seconds=900)
    assert report["capacity_reached"] and not report["healthy"]
    with pytest.raises(ValueError, match="capacity"):
        cat.publish(lambda: pytest.fail("capacity check must precede SQL"))
    assert (cat.directory / selected.entry / "archive.json").exists()


def test_leftover_or_concurrent_writer_lock_requires_operator_investigation(tmp_path):
    cat = catalog(tmp_path)
    with cat.writing():
        assert cat.status(max_age_seconds=900)["writer_lock_present"]
        with pytest.raises(FileExistsError):
            cat.publish(lambda: pytest.fail("writer collision must precede SQL"))
    module.new_file(cat.directory / ".writer-lock", b"invented stale lock")
    with pytest.raises(FileExistsError):
        cat.publish(lambda: pytest.fail("stale lock cannot be cleared automatically"))
    assert (cat.directory / ".writer-lock").exists()


def test_actual_writer_process_exit_preserves_previous_snapshot_and_failure(tmp_path):
    cat = catalog(tmp_path)
    old = cat.publish(lambda: archive())
    child = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import os,sys; from pathlib import Path; "
                "from olist_backup_catalog import BackupCatalog; "
                "BackupCatalog(Path(sys.argv[1]),sys.argv[2]).publish(lambda: os._exit(37))"
            ),
            str(cat.directory),
            cat.marker_sha256,
        ],
        capture_output=True,
        timeout=30,
    )
    assert child.returncode == 37
    report = cat.status(max_age_seconds=900)
    assert report["incomplete"] == 1 and report["writer_lock_present"]
    assert report["latest"]["entry"] == old.entry and not report["healthy"]


@pytest.mark.parametrize("change", ["future", "missing_schema", "duplicate_table"])
def test_future_or_incomplete_inventory_cannot_be_published(tmp_path, change):
    cat = catalog(tmp_path)
    value = archive(seconds_old=-3600 if change == "future" else 600)
    if change == "missing_schema":
        value = value.model_copy(update={"tables": value.tables[:-1]})
    if change == "duplicate_table":
        value = value.model_copy(update={"tables": (*value.tables, value.tables[0])})
    with pytest.raises(ValueError):
        cat.publish(lambda: value)
    assert cat.status(max_age_seconds=900)["incomplete"] == 1


def test_frozen_checkout_rejects_other_checkout_before_claiming_its_revision(tmp_path):
    with pytest.raises(ValueError, match="own checkout"):
        module.frozen_checkout(tmp_path)


@pytest.mark.parametrize("failure", ["dirty_before", "changed_after"])
def test_cli_freeze_failure_is_visible_and_never_publishes_completion(
    tmp_path, monkeypatch, capsys, failure
):
    source = SimpleNamespace(marker="invented-source-marker")
    cat = module.BackupCatalog.initialize(
        tmp_path / "private-backups",
        module.Marker(source_identity_sha256=sha256(source.marker.encode()), max_entries=4),
    )
    workspace = SimpleNamespace(root=tmp_path, load_trial=lambda _: source, server=lambda: object())
    monkeypatch.setattr(module, "Workspace", lambda _: workspace)
    calls = []

    def frozen(root):
        calls.append("freeze")
        if failure == "dirty_before":
            raise ValueError("private-dirty-checkout-canary")
        return ("a" * 40 if len(calls) == 1 else "b" * 40, "c" * 64)

    captured = []

    def capture(*args, **kwargs):
        captured.append(True)
        return archive(source=sha256(source.marker.encode()))

    monkeypatch.setattr(module, "frozen_checkout", frozen)
    monkeypatch.setattr(module, "capture", capture)
    assert (
        module.main(
            [
                "--catalog",
                str(cat.directory),
                "capture",
                "--catalog-sha256",
                cat.marker_sha256,
                "--root",
                str(tmp_path),
                "--trial",
                "invented",
            ]
        )
        == 2
    )
    assert len(captured) == (0 if failure == "dirty_before" else 1)
    report = cat.status(max_age_seconds=900)
    assert report["incomplete"] == 1 and report["completed"] == 0 and not report["healthy"]
    assert "private-dirty-checkout-canary" not in capsys.readouterr().out


def test_wrong_source_pin_changed_marker_unexpected_path_and_reinitialization_refuse(tmp_path):
    cat = catalog(tmp_path)
    with pytest.raises(ValueError):
        module.BackupCatalog(cat.directory, "f" * 64)
    with pytest.raises(FileExistsError):
        module.BackupCatalog.initialize(cat.directory, cat.marker)
    with pytest.raises(ValueError, match="source"):
        cat.publish(lambda: archive(source="e" * 64))
    unexpected = cat.directory / "../unrelated"
    unexpected.write_text("untouched")
    (cat.directory / "unexpected").mkdir()
    with pytest.raises(ValueError, match="inventory"):
        cat.status(max_age_seconds=900)
    assert unexpected.read_text() == "untouched"
    (cat.directory / "catalog.json").write_text("{}")
    with pytest.raises(ValueError, match="marker changed"):
        cat.status(max_age_seconds=900)


def test_git_directory_and_cli_errors_do_not_expose_private_detail(tmp_path, capsys):
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    (checkout / ".git").mkdir()
    with pytest.raises(ValueError):
        module.BackupCatalog.initialize(
            checkout / "backups", module.Marker(source_identity_sha256="a" * 64, max_entries=2)
        )
    cat = catalog(tmp_path)
    (cat.directory / "catalog.json").write_text("private-error-canary")
    assert (
        module.main(
            [
                "--catalog",
                str(cat.directory),
                "status",
                "--catalog-sha256",
                cat.marker_sha256,
                "--max-age-seconds",
                "900",
            ]
        )
        == 2
    )
    output = capsys.readouterr().out
    assert "backup_operation_refused" in output and "private-error-canary" not in output
