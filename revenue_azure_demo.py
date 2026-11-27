"""Isolated Azure runtime and explicit bootstrap for the constructed Revenue walkthrough."""

import argparse
import os
import re
from typing import Any

import psycopg
import uvicorn
from psycopg.conninfo import conninfo_to_dict
from revenue_integrity.console_auth import AuthStore, provision, setup_console
from revenue_integrity.operations import OperationStore, enroll, setup
from starlette.types import ASGIApp

from revenue_demo import DemoService, principal, provisioned_records
from revenue_demo_model import ModelReceipts, OpenRouterAssessment, setup_model_receipts
from revenue_demo_web import application
from revenue_profiling import Recorder

SCHEMAS = ["revenue", "revenue_app"]


def database_options(dsn: str) -> dict[str, str | int | None]:
    options = conninfo_to_dict(dsn)
    host = options.get("host")
    database = options.get("dbname")
    if (
        options.get("sslmode") != "verify-full"
        or not isinstance(host, str)
        or not re.fullmatch(r"[a-z0-9.-]+\.postgres\.database\.azure\.com", host)
        or "hostaddr" in options
        or not options.get("password")
        or not options.get("user")
        or not isinstance(database, str)
        or not database.startswith("revenue_demo_")
    ):
        raise ValueError("dedicated Azure PostgreSQL demo database and verified TLS required")
    return options


def bootstrap() -> None:
    url = os.environ["REVENUE_DEMO_ADMIN_DSN"]
    database_options(url)
    role = os.environ["REVENUE_DEMO_RUNTIME_ROLE"]
    operator = os.environ["REVENUE_DEMO_OPERATOR_PASSWORD"]
    reviewer = os.environ["REVENUE_DEMO_REVIEWER_PASSWORD"]
    if operator == reviewer or any(not 32 <= len(p) <= 128 for p in (operator, reviewer)):
        raise ValueError("distinct strong demo credentials required")
    with psycopg.connect(url, connect_timeout=5, prepare_threshold=None) as admin:
        admin.execute("SELECT pg_advisory_xact_lock(73413048)")
        if admin.execute("SELECT 1 FROM pg_namespace WHERE nspname=ANY(%s)", (SCHEMAS,)).fetchone():
            raise ValueError("demo schemas already exist")
        if (
            admin.execute(
                "SELECT rolsuper,rolcreaterole,rolcreatedb,rolbypassrls,rolreplication "
                "FROM pg_roles WHERE rolname=%s AND rolcanlogin",
                (role,),
            ).fetchone()
            != (False,) * 5
        ):
            raise ValueError("separate unprivileged demo runtime role required")
        setup(admin, role)
        setup_console(admin, role)
        for record in provisioned_records():
            enroll(admin, record)
        provision(admin, principal("operator"), operator)
        provision(admin, principal("reviewer"), reviewer)


def enable_model() -> None:
    url = os.environ["REVENUE_DEMO_ADMIN_DSN"]
    database_options(url)
    role = os.environ["REVENUE_DEMO_RUNTIME_ROLE"]
    with psycopg.connect(url, connect_timeout=5) as db:
        setup_model_receipts(db, role)


def runtime() -> ASGIApp:
    hostname = os.environ["REVENUE_DEMO_HOSTNAME"]
    url = os.environ["REVENUE_DEMO_RUNTIME_DSN"]
    database_options(url)

    def connect() -> psycopg.Connection[tuple[Any, ...]]:
        return psycopg.connect(
            url,
            connect_timeout=2,
            options="-c statement_timeout=5000 -c lock_timeout=1000",
            application_name="revenue-demo",
        )

    with connect() as db:
        if (
            db.execute(
                "SELECT 1 FROM pg_roles r WHERE pg_has_role(current_user,r.oid,'MEMBER') "
                "AND (r.rolsuper OR r.rolcreaterole OR r.rolcreatedb OR r.rolbypassrls OR "
                "r.rolreplication OR r.rolname IN ('azure_pg_admin','pg_read_all_data',"
                "'pg_write_all_data')) LIMIT 1"
            ).fetchone()
            or db.execute(
                "SELECT 1 FROM pg_namespace WHERE nspname=ANY(%s) "
                "AND pg_has_role(current_user,nspowner,'MEMBER') LIMIT 1",
                (SCHEMAS,),
            ).fetchone()
        ):
            raise ValueError("runtime must not have database administration privileges")
        if not db.execute(
            "SELECT 1 FROM pg_roles WHERE rolname=current_user AND rolconnlimit BETWEEN 1 AND 8"
        ).fetchone():
            raise ValueError("a database connection budget of at most eight is required")

    def ready() -> bool:
        try:
            with connect() as db:
                db.execute("SET LOCAL statement_timeout=500")
                return db.execute("SELECT 1 FROM revenue.records LIMIT 1").fetchone() == (1,)
        except psycopg.Error:
            return False

    auth = AuthStore(connect)
    key = os.environ.get("REVENUE_DEMO_OPENROUTER_KEY")
    if os.environ.get("REVENUE_DEMO_MODEL_REQUIRED") == "1" and not key:
        raise ValueError("Revenue model configuration is required")
    model = (OpenRouterAssessment(key), ModelReceipts(connect)) if key else None
    if model:
        with connect() as db:
            db.execute("SELECT slot FROM revenue_app.model_attempts LIMIT 1")
            db.execute("SELECT slot FROM revenue_app.model_receipts LIMIT 1")
    service = DemoService(OperationStore(connect), Recorder(limit=10000), model=model)
    for name in ("operator", "reviewer"):
        user = principal(name)
        if auth.principal_for(user.tenant_id, user.username) != user:
            raise ValueError("unexpected demo account")
        for case in service.catalog.values():
            service._record(user, case)
    return application(
        service,
        auth,
        origin=f"https://{hostname}",
        trial_id=hostname,
        allow_hosted_demo=True,
        ready=ready,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("bootstrap", "enable-model", "serve"))
    mode = parser.parse_args().mode
    try:
        if mode == "bootstrap":
            bootstrap()
            return
        if mode == "enable-model":
            enable_model()
            return
        app = runtime()
    except (KeyError, OSError, ValueError, PermissionError, psycopg.Error):
        raise SystemExit(
            "Revenue Azure demo startup refused. Check private configuration."
        ) from None
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8080,
        proxy_headers=False,
        access_log=False,
        limit_concurrency=8,
        timeout_keep_alive=5,
        timeout_graceful_shutdown=30,
    )


if __name__ == "__main__":
    main()
