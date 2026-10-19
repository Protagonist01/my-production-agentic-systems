"""Official Postgres checkpointer in a separate, administrator-created schema."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from psycopg import Connection, sql
from psycopg.rows import dict_row

from olist_support.business import ConnectionFactory


def serializer() -> JsonPlusSerializer:
    return JsonPlusSerializer(
        pickle_fallback=False, allowed_json_modules=(), allowed_msgpack_modules=()
    )


def setup_checkpoints(admin: Connection[Any], runtime_role: str) -> None:
    admin.commit()
    admin.autocommit = True
    admin.execute("CREATE SCHEMA IF NOT EXISTS olist_graph")
    admin.execute("REVOKE ALL ON SCHEMA olist_graph FROM PUBLIC")
    admin.execute("SET search_path TO olist_graph")
    admin.row_factory = dict_row
    PostgresSaver(admin, serde=serializer()).setup()
    admin.execute(
        sql.SQL("GRANT USAGE ON SCHEMA olist_graph TO {}").format(sql.Identifier(runtime_role))
    )
    admin.execute(
        sql.SQL("GRANT SELECT,INSERT,UPDATE ON ALL TABLES IN SCHEMA olist_graph TO {}").format(
            sql.Identifier(runtime_role)
        )
    )


@contextmanager
def saver(connect: ConnectionFactory) -> Iterator[PostgresSaver]:
    with connect() as connection:
        connection.commit()
        connection.autocommit = True
        connection.prepare_threshold = 0
        connection.row_factory = dict_row
        connection.execute("SET search_path TO olist_graph")
        yield PostgresSaver(connection, serde=serializer())
