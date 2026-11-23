"""Card-free hosting preparation: strict remote connection and separate admin bootstrap.

No account creation, provider calls or automatic schema migration on server startup.
The hosted model gateway/allowance must be composed separately before public activation.
"""

import argparse
import json
import os
import re
from collections.abc import Callable
from typing import Any

import psycopg
from agent_harness.contracts import Contract
from olist_support.business import ConnectionFactory, setup
from olist_support.console_auth import setup_console
from olist_support.service_health import readiness
from olist_support.workflow_postgres import setup_checkpoints
from psycopg import Connection
from psycopg.conninfo import conninfo_to_dict
from pydantic import SecretStr


class DatabaseConfiguration(Contract):
    dsn: SecretStr

    def connection(self) -> Connection[tuple[Any, ...]]:
        return psycopg.connect(self.dsn.get_secret_value(), connect_timeout=10, prepare_threshold=0)

    def verify_transport(self) -> None:
        try:
            options = conninfo_to_dict(self.dsn.get_secret_value())
            host = str(options.get("host", ""))
            if (
                options.get("sslmode") != "verify-full"
                or not host
                or host in ("localhost", "127.0.0.1", "::1")
                or "," in host
                or "hostaddr" in options
                or not options.get("user")
                or not options.get("dbname")
                or not options.get("password")
            ):
                raise ValueError(
                    "remote TLS hostname verification and explicit credentials required"
                )
        except (psycopg.Error, ValueError):
            # Never echo a DSN/driver exception containing credentials.
            raise ValueError("invalid private remote PostgreSQL configuration") from None


def runtime_role_ready(connection: Connection[Any]) -> bool:
    """Runtime must neither own guarded schemas/tables nor inherit their owner role."""
    row = connection.execute(
        "SELECT rolsuper,rolcreaterole,rolcreatedb,rolbypassrls FROM pg_roles "
        "WHERE rolname=current_user"
    ).fetchone()
    if row != (False, False, False, False):
        return False
    # Console-created managed-service roles can inherit an administrator group
    # while their own rol* flags are false. Check memberships, not just flags.
    if connection.execute(
        "SELECT 1 FROM pg_roles r WHERE pg_has_role(current_user,r.oid,'MEMBER') "
        "AND (r.rolsuper OR r.rolcreaterole OR r.rolcreatedb OR r.rolbypassrls "
        "OR r.rolreplication OR r.rolname IN "
        "('neon_superuser','pg_read_all_data','pg_write_all_data','pg_signal_backend')) LIMIT 1"
    ).fetchone():
        return False
    owners = connection.execute(
        "SELECT pg_has_role(current_user,n.nspowner,'MEMBER') FROM pg_namespace n "
        "WHERE n.nspname=ANY(%s)",
        (["olist", "olist_app", "olist_intent", "olist_graph"],),
    ).fetchall()
    if len(owners) != 4 or any(value[0] for value in owners):
        return False
    if connection.execute(
        "SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname=ANY(%s) AND pg_has_role(current_user,c.relowner,'MEMBER') LIMIT 1",
        (["olist", "olist_app", "olist_intent", "olist_graph"],),
    ).fetchone():
        return False
    return True


def preflight(connect: ConnectionFactory) -> dict[str, object]:
    result = readiness(connect)
    if result["ready"] is not True:
        return result
    try:
        with connect() as connection:
            connection.execute("SET LOCAL statement_timeout=2000")
            if not runtime_role_ready(connection):
                return {"ready": False, "reason": "runtime_role_can_change_guarded_state"}
        return {
            "ready": True,
            "reason": "database_schema_and_runtime_role_ready",
            "provider_runtime_authorized": False,
            "remote_restore_verified": False,
            "public_activation_ready": False,
        }
    except psycopg.Error:
        return {"ready": False, "reason": "private_database_preflight_failed"}


def bootstrap(admin_connect: Callable[[], Connection[Any]], runtime_role: str) -> None:
    """Explicit trusted command against an empty dedicated database; never overwrite."""
    if re.fullmatch(r"[a-z][a-z0-9_]{2,62}", runtime_role) is None:
        raise ValueError("dedicated lowercase runtime role required")
    with admin_connect() as connection:
        role = connection.execute(
            "SELECT rolsuper,rolcreaterole,rolcreatedb,rolbypassrls FROM pg_roles WHERE rolname=%s",
            (runtime_role,),
        ).fetchone()
        if role != (False, False, False, False):
            raise ValueError("pre-create a separate unprivileged runtime role")
        if connection.execute(
            "SELECT 1 FROM pg_namespace WHERE nspname=ANY(%s)",
            (["olist", "olist_app", "olist_intent", "olist_graph"],),
        ).fetchone():
            raise ValueError(
                "empty dedicated target required; preserve partial installs for diagnosis"
            )
    # Separate admin connections avoid leaking checkpointer row_factory/search_path.
    for operation in (setup, setup_checkpoints, setup_console):
        with admin_connect() as connection:
            operation(connection, runtime_role)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", required=True)
    parser.parse_args()
    try:
        config = DatabaseConfiguration(dsn=SecretStr(os.environ["OLIST_RUNTIME_DATABASE_URL"]))
        config.verify_transport()
        result = preflight(config.connection)
    except (KeyError, ValueError, psycopg.Error):
        result = {"ready": False, "reason": "private_database_configuration_unavailable"}
    print(json.dumps(result, sort_keys=True))
    if result["ready"] is not True:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
