"""Required disposable Postgres evidence: python dev.py db-check (never skipped)."""

import json
import shutil
import subprocess
from pathlib import Path

import psycopg
import pytest
from agent_harness.local_services import Workspace
from agent_harness.postgres import (
    FIXTURE_ID,
    content_hash,
    create_trial,
    drop_trial,
    migrate,
    reset_trial,
    resource_text,
)

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def workspaces(tmp_path_factory):
    if shutil.which("docker") is None:
        pytest.fail("Docker required for db-check; no database acceptance test may be skipped")
    parent = tmp_path_factory.mktemp("postgres workspaces")
    managed = []
    try:
        for name in ("checkout a with spaces", "checkout b with spaces"):
            root = parent / name
            root.mkdir()
            shutil.copyfile(ROOT / "compose.yaml", root / "compose.yaml")
            workspace = Workspace(root)
            workspace.config(initialize=True)
            managed.append(workspace)
            workspace.up()
        yield managed
    finally:
        for workspace in reversed(managed):
            workspace.down(destroy=True)


@pytest.fixture
def trials(workspaces, request):
    workspace = workspaces[0]
    server = workspace.server()
    first = workspace.create(request.node.name + ":a")
    second = workspace.create(request.node.name + ":b")
    try:
        yield server, first, second
    finally:
        drop_trial(server, second)
        drop_trial(server, first)


def checkpoint(server, trial):
    with server.connect_trial(trial) as connection:
        return connection.execute(
            "SELECT payload, version FROM runtime.checkpoints WHERE checkpoint_key = %s",
            ("invented-checkpoint",),
        ).fetchone()


def test_two_workspace_servers_do_not_share_services_ports_volumes_or_writes(workspaces):
    first, second = workspaces
    first_server, second_server = first.server(), second.server()
    assert first.project != second.project and first_server.port != second_server.port
    ids = []
    volumes = []
    for workspace, server in ((first, first_server), (second, second_server)):
        with server.connect() as admin:
            ids.append(
                admin.execute("SELECT system_identifier FROM pg_control_system()").fetchone()
            )
        container = workspace.compose("ps", "-q", "postgres")
        assert container
        mounts = json.loads(
            subprocess.check_output(
                [shutil.which("docker"), "inspect", "--format", "{{json .Mounts}}", container],
                text=True,
            )
        )
        volumes.append([m["Name"] for m in mounts if m["Type"] == "volume"])
    assert ids[0] != ids[1]
    assert len(volumes[0]) == len(volumes[1]) == 1
    assert volumes[0] != volumes[1]
    a = first.create("same-trial")
    b = second.create("same-trial")
    try:
        with first_server.connect_trial(a) as connection:
            connection.execute('UPDATE runtime.checkpoints SET payload = \'{"step":"mutated"}\'')
        assert checkpoint(first_server, a)[0]["step"] == "mutated"
        assert checkpoint(second_server, b)[0]["step"] == "start"
        # Same trial names cannot make another service's credentials valid.
        with pytest.raises(psycopg.OperationalError):
            second_server.connect_trial(a)
    finally:
        drop_trial(second_server, b)
        drop_trial(first_server, a)


def test_trial_login_cannot_connect_to_other_trial_database(trials):
    server, first, second = trials
    with pytest.raises(psycopg.OperationalError, match="permission denied for database"):
        server.connect_trial(first, second.name)
    with server.connect_trial(first) as connection:
        role = connection.execute(
            "SELECT rolsuper, rolcreatedb, rolcreaterole FROM pg_roles WHERE rolname = current_user"
        ).fetchone()
        assert role == (False, False, False)
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            connection.execute("CREATE SCHEMA attacker")


def test_workspace_restart_preserves_trial_state(workspaces):
    workspace = workspaces[1]
    server = workspace.server()
    trial = workspace.create("restart-persistence")
    try:
        with server.connect_trial(trial) as connection:
            connection.execute("UPDATE runtime.checkpoints SET version = 6")
        workspace.down()
        workspace.up()
        assert checkpoint(workspace.server(), trial)[1] == 6
    finally:
        drop_trial(workspace.server(), trial)


def test_failed_migration_rolls_back_ddl_and_history(trials, tmp_path, monkeypatch):
    from agent_harness import postgres

    server, first, _ = trials
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "001_foundation.sql").write_text(
        resource_text("migrations", "001_foundation.sql")
    )
    (migrations / "002_invented_failure.sql").write_text(
        "CREATE TABLE runtime.must_rollback (id int); SELECT * FROM missing_invented_table;"
    )
    monkeypatch.setattr(postgres, "files", lambda name: tmp_path)
    with server.connect(first.name) as admin:
        with pytest.raises(psycopg.errors.UndefinedTable):
            migrate(admin)
        assert admin.execute("SELECT to_regclass('runtime.must_rollback')").fetchone() == (None,)
        assert admin.execute("SELECT count(*) FROM harness_meta.migrations").fetchone() == (1,)


def test_reset_restores_known_snapshot_without_touching_other_trial(trials):
    server, first, second = trials
    with server.connect_trial(first) as connection:
        connection.execute(
            'UPDATE runtime.checkpoints SET payload = \'{"step":"changed"}\', version=2'
        )
    with server.connect_trial(second) as connection:
        connection.execute("UPDATE runtime.reviews SET status = 'resolved'")
    reset_trial(server, first)
    assert checkpoint(server, first) == ({"step": "start", "source_kind": "synthetic"}, 1)
    with server.connect_trial(second) as connection:
        assert connection.execute("SELECT status FROM runtime.reviews").fetchone() == ("resolved",)
    with server.connect(first.name) as admin:
        assert admin.execute("SELECT * FROM harness_meta.snapshot").fetchall() == [
            (FIXTURE_ID, content_hash(resource_text("fixtures", FIXTURE_ID + ".sql")))
        ]


def test_migration_is_idempotent_and_detects_changed_or_missing_applied_files(trials):
    server, first, _ = trials
    with server.connect(first.name) as admin:
        migrate(admin)
        assert admin.execute("SELECT count(*) FROM harness_meta.migrations").fetchone() == (1,)
        checksum = admin.execute("SELECT checksum FROM harness_meta.migrations").fetchone()[0]
        admin.execute("UPDATE harness_meta.migrations SET checksum = 'changed'")
        with pytest.raises(ValueError, match="migration changed"):
            migrate(admin)
        admin.execute("UPDATE harness_meta.migrations SET checksum = %s", (checksum,))
        admin.execute("INSERT INTO harness_meta.migrations VALUES ('removed.sql', 'invented')")
        with pytest.raises(ValueError, match="missing"):
            migrate(admin)
        admin.execute("DELETE FROM harness_meta.migrations WHERE name = 'removed.sql'")


def test_changed_fixture_refuses_reset_and_preserves_existing_writes(trials):
    server, first, _ = trials
    with server.connect_trial(first) as connection:
        connection.execute("UPDATE runtime.checkpoints SET version = 2")
    with server.connect(first.name) as admin:
        admin.execute("UPDATE harness_meta.snapshot SET checksum = 'different-fixture'")
    with pytest.raises(ValueError, match="differs"):
        reset_trial(server, first)
    assert checkpoint(server, first)[1] == 2


def test_trial_cannot_modify_snapshot_metadata_or_existing_ledger(trials):
    server, first, _ = trials
    for statement in (
        "UPDATE runtime.ledger SET payload = '{}'",
        "DELETE FROM runtime.ledger",
        "TRUNCATE runtime.ledger",
        "UPDATE harness_meta.snapshot SET checksum = 'changed'",
    ):
        with server.connect_trial(first) as connection:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                connection.execute(statement)
    with server.connect_trial(first) as connection:
        connection.execute("INSERT INTO runtime.ledger VALUES ('invented-append', '{}')")


def test_failed_transaction_rolls_back_partial_state(trials):
    server, first, _ = trials
    with pytest.raises(psycopg.errors.CheckViolation):
        with server.connect_trial(first) as connection:
            connection.execute("UPDATE runtime.checkpoints SET version = 9")
            connection.execute("UPDATE runtime.reviews SET status = 'not-a-status'")
    assert checkpoint(server, first)[1] == 1


def test_reset_refuses_active_session_and_does_not_force_disconnect(trials):
    server, first, _ = trials
    with server.connect_trial(first) as active:
        with pytest.raises(psycopg.errors.ObjectInUse):
            reset_trial(server, first)
        assert active.execute("SELECT 1").fetchone() == (1,)
    reset_trial(server, first)


def test_ownership_marker_and_existing_trial_prevent_accidental_replacement(trials):
    server, first, _ = trials
    with pytest.raises(ValueError, match="already exists"):
        create_trial(server, first)
    with server.connect() as admin:
        from psycopg import sql

        admin.execute(
            sql.SQL("COMMENT ON DATABASE {} IS 'another-owner'").format(sql.Identifier(first.name))
        )
    try:
        with pytest.raises(ValueError, match="ownership marker"):
            reset_trial(server, first)
    finally:
        with server.connect() as admin:
            admin.execute(
                sql.SQL("COMMENT ON DATABASE {} IS {}").format(
                    sql.Identifier(first.name), sql.Literal(first.marker)
                )
            )
