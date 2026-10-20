"""Trusted local provisioning and loopback support-console entrypoint."""

import argparse
import getpass
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import psycopg
import uvicorn
from agent_harness.local_services import Workspace
from pydantic import ValidationError

from olist_support.business import setup
from olist_support.console_api import create_app
from olist_support.console_auth import AuthStore, provision, setup_console
from olist_support.console_cases import CaseStore
from olist_support.console_contracts import Principal
from olist_support.policy_cases import external
from olist_support.workflow_postgres import setup_checkpoints


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--trial", required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("bootstrap")
    account = commands.add_parser("account")
    account.add_argument("--principal", type=Path, required=True)
    serve = commands.add_parser("serve")
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--run-limit-minor", type=int, required=True)
    args = parser.parse_args()
    try:
        root = args.root.resolve()
        workspace = Workspace(root)
        if args.command == "bootstrap":
            workspace.up()
            trial = (
                workspace.load_trial(args.trial)
                if workspace.trial_path(args.trial).exists()
                else workspace.create(args.trial)
            )
            server = workspace.server()
            with server.connect(trial.name) as admin:
                setup(admin, trial.name)
            with server.connect(trial.name) as admin:
                setup_checkpoints(admin, trial.name)
            with server.connect(trial.name) as admin:
                setup_console(admin, trial.name)
            print(json.dumps({"console": "ready", "provider_calls": 0, "business_unit": "SIM"}))
            return
        trial, server = workspace.load_trial(args.trial), workspace.server()
        if args.command == "account":
            user = Principal.model_validate_json(external(args.principal).read_bytes())
            password = getpass.getpass("New account password (15–128 characters): ")
            if password != getpass.getpass("Repeat password: "):
                raise ValueError("password confirmation differs")
            with server.connect(trial.name) as admin:
                provision(admin, user, password)
            print(json.dumps({"account": "provisioned", "provider_calls": 0}))
            return
        if not 1024 <= args.port <= 65535:
            raise ValueError("explicit unprivileged loopback port required")
        revision = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True
        ).strip()
        dirty = subprocess.check_output(
            ["git", "status", "--porcelain", "--untracked-files=normal"], cwd=root, text=True
        )
        if dirty.strip():
            revision += "+dirty"
        lock = hashlib.sha256((root / "uv.lock").read_bytes()).hexdigest()

        def connect() -> psycopg.Connection[Any]:
            return server.connect_trial(trial)

        app = create_app(
            CaseStore(connect),
            AuthStore(connect),
            origin=f"http://127.0.0.1:{args.port}",
            trial_id=trial.name,
            code_revision=revision,
            environment_lock=lock,
            run_limit_minor=args.run_limit_minor,
        )
        # Local-only service: do not trust proxy-provided identity/address headers.
        # Request paths contain case identifiers, so disable automatic access logs.
        uvicorn.run(
            app,
            host="127.0.0.1",
            port=args.port,
            proxy_headers=False,
            access_log=False,
            limit_concurrency=16,
            timeout_keep_alive=5,
            log_level="warning",
        )
    except (
        ValidationError,
        ValueError,
        OSError,
        psycopg.Error,
        subprocess.SubprocessError,
    ) as error:
        parser.error(
            "console operation failed: " + type(error).__name__ + "; inspect private configuration"
        )


if __name__ == "__main__":
    main()
