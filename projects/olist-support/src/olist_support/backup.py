"""Private same-schema Olist snapshots restored only into newly owned databases."""

import base64
import json
import os
import secrets
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, Literal, cast

from agent_harness.contracts import Contract, NonEmpty
from agent_harness.postgres import Server, Trial, create_trial, drop_trial, verify_ownership
from agent_harness.release_contracts import Sha256, pin, sha256
from psycopg import Connection, sql
from pydantic import AwareDatetime, Field

from olist_support.policy_cases import external

SCHEMAS = ("olist", "olist_app", "olist_graph")
Namespace = Literal["olist", "olist_app", "olist_graph"]
MAX_BYTES = 20_000_000


class TableCopy(Contract):
    namespace: Namespace
    table: Annotated[str, Field(pattern=r"^[a-z_][a-z0-9_]*$")]
    data_base64: NonEmpty
    data_sha256: Sha256
    rows: Annotated[int, Field(ge=0)]


class Archive(Contract):
    version: Literal["olist-private-snapshot-v1"] = "olist-private-snapshot-v1"
    created_at: AwareDatetime
    source_identity_sha256: Sha256
    code_revision: NonEmpty
    environment_lock: Sha256
    postgres_major: Annotated[int, Field(ge=17)]
    server_build: NonEmpty
    schema_sha256: Sha256
    tables: tuple[TableCopy, ...]


def table_inventory(connection: Connection[Any]) -> tuple[tuple[str, str], ...]:
    rows = connection.execute(
        "SELECT n.nspname,c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname=ANY(%s) AND c.relkind='r' ORDER BY n.nspname,c.relname",
        (list(SCHEMAS),),
    ).fetchall()
    if not rows or {s for s, _ in rows} != set(SCHEMAS):
        raise ValueError("all three installed Olist schemas are required")
    return tuple((str(s), str(t)) for s, t in rows)


def schema_pin(connection: Connection[Any]) -> str:
    columns = connection.execute(
        "SELECT n.nspname,c.relname,a.attnum,a.attname,format_type(a.atttypid,a.atttypmod),"
        "a.attnotnull,pg_get_expr(d.adbin,d.adrelid),a.attgenerated,a.attidentity "
        "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
        "JOIN pg_attribute a ON a.attrelid=c.oid LEFT JOIN pg_attrdef d ON "
        "d.adrelid=c.oid AND d.adnum=a.attnum WHERE n.nspname=ANY(%s) AND c.relkind='r' "
        "AND a.attnum>0 AND NOT a.attisdropped ORDER BY n.nspname,c.relname,a.attnum",
        (list(SCHEMAS),),
    ).fetchall()
    constraints = connection.execute(
        "SELECT n.nspname,c.relname,k.conname,pg_get_constraintdef(k.oid,true) "
        "FROM pg_constraint k "
        "JOIN pg_class c ON c.oid=k.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname=ANY(%s) ORDER BY n.nspname,c.relname,k.conname",
        (list(SCHEMAS),),
    ).fetchall()
    indexes = connection.execute(
        "SELECT schemaname,tablename,indexname,indexdef FROM pg_indexes WHERE schemaname=ANY(%s) "
        "ORDER BY schemaname,tablename,indexname",
        (list(SCHEMAS),),
    ).fetchall()
    if any(row[-1] or row[-2] for row in columns):
        raise ValueError("snapshot does not support generated/identity columns")
    if connection.execute(
        "SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname=ANY(%s) AND c.relkind='S' LIMIT 1",
        (list(SCHEMAS),),
    ).fetchone():
        raise ValueError("snapshot does not support sequence state")
    return sha256(
        json.dumps(
            [table_inventory(connection), columns, constraints, indexes], sort_keys=True
        ).encode()
    )


def collect_tables(connection: Connection[Any]) -> tuple[TableCopy, ...]:
    result = []
    size = 0
    for schema, table in table_inventory(connection):
        identifier = sql.Identifier(schema, table)
        with (
            connection.cursor() as cursor,
            cursor.copy(
                sql.SQL(
                    "COPY (SELECT * FROM {} AS t ORDER BY to_jsonb(t)::text) "
                    "TO STDOUT (FORMAT BINARY)"
                ).format(identifier)
            ) as stream,
        ):
            chunks = []
            for block in stream:
                raw = bytes(block)
                size += len(raw)
                if size > MAX_BYTES:
                    raise ValueError("private snapshot exceeds size limit")
                chunks.append(raw)
        data = b"".join(chunks)
        count_row = connection.execute(
            sql.SQL("SELECT count(*) FROM {}").format(identifier)
        ).fetchone()
        if count_row is None:
            raise ValueError("snapshot count unavailable")
        count = int(count_row[0])
        result.append(
            TableCopy(
                namespace=cast(Namespace, schema),
                table=table,
                data_base64=base64.b64encode(data).decode(),
                data_sha256=sha256(data),
                rows=count,
            )
        )
    return tuple(result)


def server_build(connection: Connection[Any]) -> str:
    row = connection.execute("SELECT version()").fetchone()
    if row is None:
        raise ValueError("Postgres build unavailable")
    return str(row[0])


def capture(
    server: Server,
    source: Trial,
    *,
    code_revision: str,
    environment_lock: str,
) -> Archive:
    with server.connect() as admin:
        verify_ownership(admin, source)
    with server.connect(source.name) as connection, connection.transaction():
        connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        connection.execute("SET LOCAL statement_timeout=10000")
        connection.execute("SET LOCAL TIME ZONE 'UTC'")
        return Archive(
            created_at=datetime.now(UTC),
            source_identity_sha256=sha256(source.marker.encode()),
            code_revision=code_revision,
            environment_lock=environment_lock,
            postgres_major=connection.info.server_version // 10000,
            server_build=server_build(connection),
            schema_sha256=schema_pin(connection),
            tables=collect_tables(connection),
        )


def save(path: Path, archive: Archive) -> str:
    path = external(path)
    raw = Archive.model_validate_json(archive.canonical_json()).canonical_json().encode()
    if len(raw) > MAX_BYTES * 2:
        raise ValueError("archive exceeds size limit")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as output:
        output.write(raw)
    return sha256(raw)


def read(path: Path, expected_sha256: str) -> Archive:
    if path.is_symlink() or path.stat().st_size > MAX_BYTES * 2:
        raise ValueError("archive path/size invalid")
    path = external(path)
    raw = path.read_bytes()
    if sha256(raw) != expected_sha256:
        raise ValueError("archive differs from external pin")
    archive = Archive.model_validate_json(raw)
    if raw != archive.canonical_json().encode():
        raise ValueError("archive must be canonical")
    return archive


def restore(
    server: Server,
    workspace_key: str,
    new_trial_id: str,
    archive: Archive,
    *,
    archive_sha256: str,
    bootstrap: Callable[[Server, Trial], None],
) -> Trial:
    archive = Archive.model_validate_json(archive.canonical_json())
    if pin(archive) != archive_sha256 or not archive.tables:
        raise ValueError("restore requires exact archive pin and nonempty inventory")
    inventory = tuple((t.namespace, t.table) for t in archive.tables)
    if len(set(inventory)) != len(inventory):
        raise ValueError("duplicate archive tables")
    decoded = []
    size = 0
    for table in archive.tables:
        data = base64.b64decode(table.data_base64, validate=True)
        size += len(data)
        if size > MAX_BYTES or sha256(data) != table.data_sha256:
            raise ValueError("table bytes differ from archive digest/limit")
        decoded.append(data)
    target = Trial(workspace_key, new_trial_id, secrets.token_hex(32))
    # Creation refuses any existing identity before the bootstrap or truncate can execute.
    create_trial(server, target)
    try:
        bootstrap(server, target)
        with server.connect(target.name) as connection, connection.transaction():
            connection.execute("SET LOCAL statement_timeout=10000")
            connection.execute("SET LOCAL TIME ZONE 'UTC'")
            if (
                connection.info.server_version // 10000 != archive.postgres_major
                or server_build(connection) != archive.server_build
                or table_inventory(connection) != inventory
                or schema_pin(connection) != archive.schema_sha256
            ):
                raise ValueError("restored application/schema/Postgres version differs")
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
        with server.connect(target.name) as connection, connection.transaction():
            connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            connection.execute("SET LOCAL TIME ZONE 'UTC'")
            if collect_tables(connection) != archive.tables:
                raise ValueError(
                    "restored rows differ from archived checkpoint/review/ledger state"
                )
    except BaseException:
        drop_trial(server, target)
        raise
    return target
