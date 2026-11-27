"""Provision one fictional workspace in a dedicated, empty Azure database."""

import argparse
import os
from typing import Annotated, Literal

import psycopg
from agent_harness.contracts import Contract
from olist_support.business import enroll
from olist_support.console_auth import provision
from olist_support.console_contracts import Principal
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict
from pydantic import Field, SecretStr

from olist_demo_acceptance import cases
from olist_demo_fixtures import fixture
from olist_demo_host import DatabaseConfiguration, bootstrap, preflight

DATABASE = "olist_demo"
RUNTIME_ROLE = "olist_runtime"
ORDER = "SIM-ORD-1042"
TENANT = "olist-portfolio-stage"


class Credentials(Contract):
    operator: Annotated[SecretStr, Field(min_length=15, max_length=128)]
    reviewer: Annotated[SecretStr, Field(min_length=15, max_length=128)]
    customer: Annotated[SecretStr, Field(min_length=15, max_length=128)]


def provision_demo(
    admin: DatabaseConfiguration, runtime: DatabaseConfiguration, accounts: Credentials
) -> None:
    admin.verify_transport()
    runtime.verify_transport()
    owner, worker = (conninfo_to_dict(c.dsn.get_secret_value()) for c in (admin, runtime))
    people: tuple[tuple[Literal["operator", "reviewer", "customer"], str], ...] = (
        ("operator", accounts.operator.get_secret_value()),
        ("reviewer", accounts.reviewer.get_secret_value()),
        ("customer", accounts.customer.get_secret_value()),
    )
    target = (owner["host"], owner.get("port", "5432"), owner["dbname"])
    if (
        target != (worker["host"], worker.get("port", "5432"), worker["dbname"])
        or target[2] != DATABASE
        or not str(target[0]).endswith(".postgres.database.azure.com")
        or worker["user"] != RUNTIME_ROLE
        or owner["user"] == RUNTIME_ROLE
        or len({str(owner["password"]), str(worker["password"]), *(p for _, p in people)}) != 5
        or len(str(worker["password"])) < 24
    ):
        raise ValueError("separate credentials for a dedicated Azure database required")

    # Keep the session lock across the checkpointer's separate DDL connection.
    with admin.connection() as guard:
        guard.autocommit = True
        if guard.execute("SELECT pg_try_advisory_lock(73412063)").fetchone() != (True,):
            raise ValueError("another bootstrap is in progress")
        if (
            guard.execute("SELECT 1 FROM pg_namespace WHERE nspname LIKE 'olist%'").fetchone()
            or guard.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (RUNTIME_ROLE,)).fetchone()
        ):
            raise ValueError("empty dedicated database and unused runtime role required")
        with guard.transaction():
            guard.execute(
                sql.SQL(
                    "CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
                    "NOREPLICATION NOBYPASSRLS PASSWORD {}"
                ).format(sql.Identifier(RUNTIME_ROLE), sql.Literal(str(worker["password"])))
            )
            guard.execute("REVOKE CONNECT ON DATABASE olist_demo FROM PUBLIC")
            guard.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC")
            guard.execute("GRANT CONNECT ON DATABASE olist_demo TO olist_runtime")

        bootstrap(admin.connection, RUNTIME_ROLE)
        selected = next(case for case in cases() if case.case_id == "olist-demo-refund-1")
        order = fixture(selected, tenant_id=TENANT, order_id=ORDER)
        with guard.transaction():
            enroll(guard, order.view, order.facts)
            for role, password in people:
                user = f"demo-{role}"
                provision(
                    guard,
                    Principal(
                        tenant_id=TENANT,
                        username=user,
                        actor_id=user,
                        role=role,
                        order_ids=(ORDER,),
                    ),
                    password,
                )
        if preflight(runtime.connection)["ready"] is not True:
            raise ValueError("restricted runtime database readiness failed")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install-model-ledger", action="store_true")
    args = parser.parse_args()
    try:
        if args.install_model_ledger:
            from olist_nemotron import install_ledger

            admin = DatabaseConfiguration(dsn=SecretStr(os.environ["OLIST_ADMIN_DATABASE_URL"]))
            admin.verify_transport()
            install_ledger(admin.connection)
            print("Olist OpenRouter ledger installed.", flush=True)
            return
        provision_demo(
            DatabaseConfiguration(dsn=SecretStr(os.environ["OLIST_ADMIN_DATABASE_URL"])),
            DatabaseConfiguration(dsn=SecretStr(os.environ["OLIST_RUNTIME_DATABASE_URL"])),
            Credentials.model_validate_json(os.environ["OLIST_DEMO_ACCOUNTS"]),
        )
    except (KeyError, ValueError, psycopg.Error):
        raise SystemExit(
            "Olist bootstrap refused. Inspect the dedicated database privately."
        ) from None
    print("Olist SIM workspace initialized and restricted runtime verified.", flush=True)


if __name__ == "__main__":
    main()
