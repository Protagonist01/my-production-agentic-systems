"""Run the authenticated SIM console on an explicitly restricted Azure staging app."""

import hashlib
import os
import re
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from olist_support.console_api import create_app
from olist_support.console_auth import AuthStore
from olist_support.console_cases import CaseStore
from pydantic import SecretStr

from olist_demo_host import DatabaseConfiguration, preflight

PORT = 8080


def application(database: DatabaseConfiguration, *, hostname: str, revision: str) -> FastAPI:
    if not re.fullmatch(
        r"[a-z0-9][a-z0-9.-]{1,223}\.azurecontainerapps\.io", hostname
    ) or not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("Azure app hostname and source commit required")
    database.verify_transport()
    if preflight(database.connection)["ready"] is not True:
        raise ValueError("Azure PostgreSQL readiness or runtime role check failed")
    lock = hashlib.sha256(Path(__file__).with_name("uv.lock").read_bytes()).hexdigest()
    return create_app(
        CaseStore(database.connection),
        AuthStore(database.connection),
        origin=f"https://{hostname}",
        trial_id=hostname,
        code_revision=revision,
        environment_lock=lock,
        run_limit_minor=10_000,
        allow_public_https=True,
    )


def main() -> None:
    try:
        app = application(
            DatabaseConfiguration(dsn=SecretStr(os.environ["OLIST_RUNTIME_DATABASE_URL"])),
            hostname=os.environ["OLIST_AZURE_HOSTNAME"],
            revision=os.environ["OLIST_SOURCE_COMMIT"],
        )
    except (KeyError, OSError, ValueError):
        raise SystemExit("Olist staging startup refused. Check private configuration.") from None
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=PORT,
        proxy_headers=False,
        access_log=False,
        limit_concurrency=8,
        timeout_keep_alive=5,
        timeout_graceful_shutdown=30,
        log_level="warning",
    )


if __name__ == "__main__":
    main()
