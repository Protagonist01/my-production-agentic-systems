"""Read-only local service readiness; safe status codes without source/credential output."""

from importlib.resources import files

import psycopg

from olist_support.business import ConnectionFactory, sha


def readiness(connect: ConnectionFactory) -> dict[str, object]:
    try:
        from langgraph.checkpoint.postgres import PostgresSaver

        with connect() as connection, connection.transaction():
            connection.execute("SET LOCAL statement_timeout=2000")
            connection.execute("SET LOCAL lock_timeout=1000")
            for schema, resource in (("olist", "business.sql"), ("olist_app", "console.sql")):
                from psycopg import sql

                actual = connection.execute(
                    sql.SQL("SELECT version,sha256 FROM {}.schema_pin").format(
                        sql.Identifier(schema)
                    )
                ).fetchall()
                if actual != [
                    (1, sha(files("olist_support").joinpath(resource).read_text(encoding="utf-8")))
                ]:
                    return {
                        "ready": False,
                        "reason": "schema_version_mismatch",
                        "action": "verify_pinned_application_and_schema",
                    }
            migrations = connection.execute(
                "SELECT v FROM olist_graph.checkpoint_migrations ORDER BY v"
            ).fetchall()
            if migrations != [(v,) for v in range(len(PostgresSaver.MIGRATIONS))]:
                return {
                    "ready": False,
                    "reason": "checkpoint_version_mismatch",
                    "action": "verify_checkpoint_dependency_lock",
                }
            connection.execute(
                "SELECT source_view,confirmation,refunded_minor FROM olist.orders LIMIT 0"
            )
            connection.execute("SELECT document,request_hash,version FROM olist_app.cases LIMIT 0")
            connection.execute(
                "SELECT password_hash,principal,enabled FROM olist_app.accounts LIMIT 0"
            )
            connection.execute("SELECT checkpoint,metadata FROM olist_graph.checkpoints LIMIT 0")
            return {"ready": True, "reason": "ready", "business_unit": "SIM"}
    except (psycopg.errors.UndefinedTable, psycopg.errors.InvalidSchemaName):
        return {
            "ready": False,
            "reason": "schema_missing",
            "action": "run_trusted_console_bootstrap",
        }
    except psycopg.errors.InsufficientPrivilege:
        return {
            "ready": False,
            "reason": "schema_access_denied",
            "action": "verify_runtime_role_bootstrap",
        }
    except psycopg.Error:
        return {
            "ready": False,
            "reason": "database_unavailable",
            "action": "check_private_database_configuration",
        }


def require_ready(connect: ConnectionFactory) -> None:
    result = readiness(connect)
    if result["ready"] is not True:
        raise ServiceNotReady(str(result["reason"]) + "; " + str(result["action"]))


class ServiceNotReady(ValueError):
    """Only fixed safe reason/action strings enter this startup error."""
