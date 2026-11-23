"""Create a new owned Revenue walkthrough database or serve its protected loopback UI."""

import argparse
import json
import secrets
import subprocess
from pathlib import Path

import psycopg
import uvicorn
from agent_harness.local_services import Workspace, private_json
from revenue_integrity.console_auth import AuthStore, provision, setup_console
from revenue_integrity.operations import OperationStore, enroll, setup

from revenue_demo import DemoService, principal, provisioned_records
from revenue_demo_web import application
from revenue_profiled_runtime import connection_factory
from revenue_profiling import Recorder


def bootstrap(
    root: Path, trial_id: str, credentials: Path, *, resume: bool = False
) -> dict[str, object]:
    workspace = Workspace(root.resolve())
    credentials = credentials.expanduser().resolve()
    if any(
        (p / ".git").exists() and (p / "pyproject.toml").exists()
        for p in (credentials.parent, *credentials.parents)
    ):
        raise ValueError("private credentials must remain outside project checkouts")
    if workspace.trial_path(trial_id).exists() or (credentials.exists() and not resume):
        raise FileExistsError(
            "choose a new trial and private credentials file; no reset is performed"
        )
    if resume:
        value = json.loads(credentials.read_text(encoding="utf-8"))
        expected = {
            "operator": "demo-operator",
            "reviewer": "demo-reviewer",
            "trial_id": trial_id,
            "root": str(workspace.root),
            "constructed_demo": True,
        }
        if (
            not isinstance(value, dict)
            or set(value) != set(expected) | {"password"}
            or any(value[k] != v for k, v in expected.items())
        ):
            raise ValueError("resume credentials do not belong to this unstarted trial")
        password = value["password"]
        if not isinstance(password, str) or not 32 <= len(password) <= 128:
            raise ValueError("invalid private demo credential")
    else:
        password = secrets.token_urlsafe(32)
        private_json(
            credentials,
            {
                "operator": "demo-operator",
                "reviewer": "demo-reviewer",
                "password": password,
                "trial_id": trial_id,
                "root": str(workspace.root),
                "constructed_demo": True,
            },
        )
    workspace.up()
    trial = workspace.create(trial_id)
    server = workspace.server()
    with server.connect(trial.name) as admin, admin.transaction():
        setup(admin, trial.name)
        setup_console(admin, trial.name)
        for record in provisioned_records():
            enroll(admin, record)
        for role in ("operator", "reviewer"):
            provision(admin, principal(role), password)
    return {
        "created": True,
        "trial": trial_id,
        "credentials_file": str(credentials),
        "invoices": 6,
        "provider_calls": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("bootstrap", "serve"))
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--trial", required=True)
    parser.add_argument("--credentials", type=Path)
    parser.add_argument("--port", type=int, default=8878)
    parser.add_argument("--resume-bootstrap", action="store_true")
    args = parser.parse_args()
    try:
        root = args.root.resolve()
        if args.command == "bootstrap":
            if args.credentials is None:
                raise ValueError("a new private credentials file is required")
            print(
                json.dumps(
                    bootstrap(root, args.trial, args.credentials, resume=args.resume_bootstrap)
                )
            )
            return
        if args.credentials is not None or args.resume_bootstrap or not 1024 <= args.port <= 65535:
            raise ValueError("serve requires only an existing trial and unprivileged loopback port")
        workspace = Workspace(root)
        trial, server = workspace.load_trial(args.trial), workspace.server()
        recorder = Recorder(limit=10000)
        connect = connection_factory(
            recorder,
            host="127.0.0.1",
            port=server.port,
            user=trial.name,
            password=trial.password,
            dbname=trial.name,
            connect_timeout=5,
        )
        service = DemoService(OperationStore(connect), recorder)
        # Refuse mismatched schema/source before exposing the UI; this does not mutate state.
        for user in (principal("operator"), principal("reviewer")):
            for case in service.catalog.values():
                service._record(user, case)
        auth = AuthStore(connect)
        for role in ("operator", "reviewer"):
            actual = auth.principal_for("revenue-demo", "demo-" + role)
            if actual != principal(role):
                raise ValueError("demo identity differs from provisioned scope")
        app = application(
            service, auth, origin=f"http://127.0.0.1:{args.port}", trial_id=trial.name
        )
        print(
            json.dumps(
                {
                    "walkthrough": f"http://127.0.0.1:{args.port}/walkthrough",
                    "execution_mode": "constructed_parser_no_provider",
                    "provider_calls": 0,
                }
            ),
            flush=True,
        )
        uvicorn.run(
            app,
            host="127.0.0.1",
            port=args.port,
            access_log=False,
            proxy_headers=False,
            limit_concurrency=16,
            timeout_keep_alive=5,
            timeout_graceful_shutdown=30,
            log_level="warning",
        )
    except (ValueError, OSError, psycopg.Error, subprocess.SubprocessError):
        parser.error(
            "Revenue walkthrough refused; inspect private configuration, "
            "database readiness and trial identity"
        )


if __name__ == "__main__":
    main()
