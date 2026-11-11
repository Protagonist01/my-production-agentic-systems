"""Restore a discovered real four-schema snapshot without rewinding newer source effects."""

from datetime import UTC, datetime, timedelta

from agent_harness.postgres import drop_trial
from agent_harness.release_contracts import sha256
from olist_support.backup import capture, read, restore
from olist_support.console_cases import CaseStore
from olist_support.operations_cli import bootstrap
from olist_support.service_health import readiness
from test_olist_business import app as app
from test_olist_console import console as console
from test_olist_console import create_case, decide, observed

from olist_backup_catalog import BackupCatalog, Marker


def test_catalog_selected_snapshot_restores_pending_and_committed_state_with_newer_source_intact(
    console, tmp_path
):
    server, source, _ = console
    store, pending, operator, reviewer = create_case(console)
    store, committed, operator2, reviewer2 = create_case(console)
    approved = decide(store, committed, reviewer2, console=console)
    result = store.resume(
        reviewer2, committed.case_id, approved.action_digest, run_limit_minor=10000
    )
    catalog = BackupCatalog.initialize(
        tmp_path / "private-catalog",
        Marker(source_identity_sha256=sha256(source.marker.encode()), max_entries=4),
    )
    selected = catalog.publish(
        lambda: capture(
            server, source, code_revision="invented-test-code", environment_lock="a" * 64
        )
    )
    status = catalog.status(max_age_seconds=900)
    assert status["healthy"] and status["completed"] == 1
    assert status["latest"]["archive_sha256"] == selected.archive_sha256
    # A newer source commit must survive restoring the selected older checkpoint elsewhere.
    later = decide(store, pending, reviewer, console=console)
    store.resume(reviewer, pending.case_id, later.action_digest, run_limit_minor=10000)
    after = observed(console, pending)
    archive = read(catalog.directory / selected.entry / "archive.json", selected.archive_sha256)
    target = restore(
        server,
        source.workspace_key,
        "catalog-recovery-target",
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
            == result
        )
        assert observed(console, pending) == after
        assert readiness(lambda: server.connect_trial(target))["ready"]
        assert not catalog.status(max_age_seconds=900, now=datetime.now(UTC) + timedelta(hours=1))[
            "healthy"
        ]
        assert not status["actual_restore_verified"] and not status["host_loss_rpo_rto_verified"]
    finally:
        drop_trial(server, target)
