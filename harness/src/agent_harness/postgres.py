"""Disposable trial databases. Administration is trusted, never an agent capability."""

import hashlib
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from importlib.resources import files
from typing import Any

import psycopg
from psycopg import Connection, sql

FIXTURE_ID = "foundation-v1"


def resource_text(directory: str, name: str) -> str:
    return files("agent_harness").joinpath(directory, name).read_text(encoding="utf-8")


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def trial_name(workspace_key: str, trial_id: str) -> str:
    if len(workspace_key) != 16 or any(c not in "0123456789abcdef" for c in workspace_key):
        raise ValueError("Invalid workspace key")
    if not trial_id.strip() or len(trial_id) > 256:
        raise ValueError("Trial identity must be nonempty and at most 256 characters")
    return f"pa_{workspace_key}_{content_hash(trial_id)[:20]}"


@dataclass(frozen=True)
class Trial:
    workspace_key: str
    trial_id: str
    password: str = field(repr=False)

    @property
    def name(self) -> str:
        return trial_name(self.workspace_key, self.trial_id)

    @property
    def marker(self) -> str:
        return f"production-agents:{self.workspace_key}:{content_hash(self.trial_id)}"


@dataclass(frozen=True)
class Server:
    port: int
    password: str = field(repr=False)

    def connect(self, database: str = "postgres") -> Connection[tuple[Any, ...]]:
        return psycopg.connect(
            host="127.0.0.1",
            port=self.port,
            user="postgres",
            password=self.password,
            dbname=database,
            connect_timeout=5,
            autocommit=True,
        )

    def connect_trial(
        self, trial: Trial, database: str | None = None
    ) -> Connection[tuple[Any, ...]]:
        return psycopg.connect(
            host="127.0.0.1",
            port=self.port,
            user=trial.name,
            password=trial.password,
            dbname=database or trial.name,
            connect_timeout=5,
        )


def migrate(connection: Connection[tuple[Any, ...]]) -> None:
    """Serial, transactional DDL; refuse any change to previously applied bytes."""
    with connection.transaction():
        connection.execute("SELECT pg_advisory_xact_lock(73412001)")
        connection.execute("CREATE SCHEMA IF NOT EXISTS harness_meta")
        connection.execute("REVOKE ALL ON SCHEMA harness_meta FROM PUBLIC")
        connection.execute(
            "CREATE TABLE IF NOT EXISTS harness_meta.migrations "
            "(name text PRIMARY KEY, checksum text NOT NULL)"
        )
        directory = files("agent_harness").joinpath("migrations")
        migrations = sorted(
            (p for p in directory.iterdir() if p.name.endswith(".sql")), key=lambda p: p.name
        )
        names = {p.name for p in migrations}
        applied = dict(connection.execute("SELECT name, checksum FROM harness_meta.migrations"))
        if set(applied) - names:
            raise ValueError("Applied migration is missing from this code revision")
        for path in migrations:
            text = path.read_text(encoding="utf-8")
            checksum = content_hash(text)
            if path.name in applied:
                if applied[path.name] != checksum:
                    raise ValueError(f"Applied migration changed: {path.name}")
                continue
            connection.execute(text)
            connection.execute(
                "INSERT INTO harness_meta.migrations VALUES (%s, %s)", (path.name, checksum)
            )


def seed(connection: Connection[tuple[Any, ...]]) -> None:
    text = resource_text("fixtures", FIXTURE_ID + ".sql")
    with connection.transaction():
        connection.execute(
            "CREATE TABLE harness_meta.snapshot "
            "(fixture_id text PRIMARY KEY, checksum text NOT NULL)"
        )
        connection.execute(text)
        connection.execute(
            "INSERT INTO harness_meta.snapshot VALUES (%s, %s)", (FIXTURE_ID, content_hash(text))
        )


@contextmanager
def administration(server: Server, trial: Trial) -> Iterator[Connection[tuple[Any, ...]]]:
    """Serialize lifecycle commands for this generated identity on this server."""
    with server.connect() as admin:
        admin.execute("SET lock_timeout = '5s'")
        admin.execute("SELECT pg_advisory_lock(hashtextextended(%s, 0))", (trial.name,))
        try:
            yield admin
        finally:
            admin.execute("SELECT pg_advisory_unlock(hashtextextended(%s, 0))", (trial.name,))


def verify_ownership(admin: Connection[tuple[Any, ...]], trial: Trial) -> None:
    database = admin.execute(
        "SELECT shobj_description(oid, 'pg_database') FROM pg_database WHERE datname = %s",
        (trial.name,),
    ).fetchone()
    role = admin.execute(
        "SELECT shobj_description(oid, 'pg_authid') FROM pg_roles WHERE rolname = %s",
        (trial.name,),
    ).fetchone()
    if database != (trial.marker,) or role != (trial.marker,):
        raise ValueError("Database/role ownership marker mismatch; refusing lifecycle action")


def populate(admin: Connection[tuple[Any, ...]], server: Server, trial: Trial) -> None:
    name = sql.Identifier(trial.name)
    admin.execute(
        sql.SQL("CREATE DATABASE {} TEMPLATE template0 ALLOW_CONNECTIONS false").format(name)
    )
    admin.execute(sql.SQL("COMMENT ON DATABASE {} IS {}").format(name, sql.Literal(trial.marker)))
    admin.execute(sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(name))
    admin.execute(sql.SQL("ALTER DATABASE {} ALLOW_CONNECTIONS true").format(name))
    with server.connect(trial.name) as connection:
        migrate(connection)
        seed(connection)
        with connection.transaction():
            connection.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC")
            connection.execute(sql.SQL("GRANT USAGE ON SCHEMA runtime TO {}").format(name))
            connection.execute(
                sql.SQL(
                    "GRANT SELECT, INSERT, UPDATE, DELETE ON "
                    "runtime.checkpoints, runtime.reviews TO {}"
                ).format(name)
            )
            connection.execute(sql.SQL("GRANT SELECT, INSERT ON runtime.ledger TO {}").format(name))
    admin.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(name, name))


def create_trial(server: Server, trial: Trial) -> None:
    with administration(server, trial) as admin:
        name = sql.Identifier(trial.name)
        if admin.execute("SELECT 1 FROM pg_database WHERE datname = %s", (trial.name,)).fetchone():
            raise ValueError("Trial already exists; use reset explicitly")
        admin.execute(
            sql.SQL(
                "CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION "
                "PASSWORD {}"
            ).format(name, sql.Literal(trial.password))
        )
        admin.execute(sql.SQL("COMMENT ON ROLE {} IS {}").format(name, sql.Literal(trial.marker)))
        # A failed bootstrap remains visibly incomplete; do not report success or erase evidence.
        populate(admin, server, trial)


def drop_database(admin: Connection[tuple[Any, ...]], trial: Trial) -> None:
    """Postgres refuses active connections. Never terminate another process's session."""
    admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(trial.name)))


def reset_trial(server: Server, trial: Trial) -> None:
    with administration(server, trial) as admin:
        verify_ownership(admin, trial)
        with server.connect(trial.name) as connection:
            migrate(connection)
            recorded = connection.execute(
                "SELECT fixture_id, checksum FROM harness_meta.snapshot"
            ).fetchall()
        expected = [(FIXTURE_ID, content_hash(resource_text("fixtures", FIXTURE_ID + ".sql")))]
        if recorded != expected:
            raise ValueError("Reset fixture differs from the recorded snapshot")
        drop_database(admin, trial)
        populate(admin, server, trial)


def drop_trial(server: Server, trial: Trial) -> None:
    with administration(server, trial) as admin:
        verify_ownership(admin, trial)
        drop_database(admin, trial)
        admin.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(trial.name)))
