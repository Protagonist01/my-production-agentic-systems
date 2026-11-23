"""Managed PostgreSQL data restore into an empty dedicated target, never in-place.

This covers the four application schemas, not a hosted model-call allowance, an
off-host encrypted repository or a measured whole-host recovery objective.
"""

import base64
from datetime import UTC, datetime

from agent_harness.release_contracts import pin, sha256
from olist_support.backup import (
    MAX_BYTES,
    Archive,
    collect_tables,
    schema_pin,
    server_build,
    table_inventory,
)
from olist_support.business import ConnectionFactory
from olist_support.service_health import readiness
from psycopg import sql

from olist_demo_host import bootstrap


def capture(
    connect: ConnectionFactory, *, source_identity: str, code_revision: str, environment_lock: str
) -> Archive:
    if not source_identity.strip() or readiness(connect)["ready"] is not True:
        raise ValueError("declared source identity and pinned ready schema required")
    with connect() as connection, connection.transaction():
        connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        connection.execute("SET LOCAL statement_timeout=10000")
        connection.execute("SET LOCAL TIME ZONE 'UTC'")
        return Archive(
            created_at=datetime.now(UTC),
            source_identity_sha256=sha256(source_identity.encode()),
            code_revision=code_revision,
            environment_lock=environment_lock,
            postgres_major=connection.info.server_version // 10000,
            server_build=server_build(connection),
            schema_sha256=schema_pin(connection),
            tables=collect_tables(connection),
        )


def restore(
    admin_connect: ConnectionFactory, runtime_role: str, archive: Archive, *, archive_sha256: str
) -> dict[str, object]:
    archive = Archive.model_validate_json(archive.canonical_json())
    if pin(archive) != archive_sha256 or not archive.tables:
        raise ValueError("externally pinned nonempty archive required")
    inventory = tuple((t.namespace, t.table) for t in archive.tables)
    if len(set(inventory)) != len(inventory):
        raise ValueError("duplicate archived tables")
    decoded, size = [], 0
    for table in archive.tables:
        data = base64.b64decode(table.data_base64, validate=True)
        size += len(data)
        if size > MAX_BYTES or sha256(data) != table.data_sha256:
            raise ValueError("archive table digest/size differs")
        decoded.append(data)
    # Refuses any target with an application schema before DDL/truncation. A
    # partial failed restore stays visible; do not drop it or overwrite on retry.
    bootstrap(admin_connect, runtime_role)
    with admin_connect() as connection, connection.transaction():
        connection.execute("SET LOCAL statement_timeout=10000")
        connection.execute("SET LOCAL TIME ZONE 'UTC'")
        if (
            connection.info.server_version // 10000 != archive.postgres_major
            or server_build(connection) != archive.server_build
            or table_inventory(connection) != inventory
            or schema_pin(connection) != archive.schema_sha256
        ):
            raise ValueError("exact managed target build/schema required")
        connection.execute(
            sql.SQL("TRUNCATE {} RESTRICT").format(
                sql.SQL(",").join(sql.Identifier(s, t) for s, t in inventory)
            )
        )
        for table, data in zip(archive.tables, decoded, strict=True):
            with (
                connection.cursor() as cursor,
                cursor.copy(
                    sql.SQL("COPY {} FROM STDIN (FORMAT BINARY)").format(
                        sql.Identifier(table.namespace, table.table)
                    )
                ) as stream,
            ):
                stream.write(data)
    with admin_connect() as connection, connection.transaction():
        connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        connection.execute("SET LOCAL TIME ZONE 'UTC'")
        if collect_tables(connection) != archive.tables:
            raise ValueError("independent restored row readback differs")
    with admin_connect() as connection:
        # Do this after exact readback; old opaque sessions must not survive cutover.
        connection.execute("DELETE FROM olist_app.sessions")
    return {
        "application_rows_restored": True,
        "exact_pre_revocation_readback": True,
        "sessions_revoked": True,
        "model_budget_recovered": False,
        "off_host_encryption_verified": False,
        "host_loss_objective_met": False,
    }
