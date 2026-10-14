"""Checkout-specific disposable Postgres services; invoked through dev.py."""

import argparse
import hashlib
import json
import os
import secrets
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psycopg

from agent_harness.postgres import Server, Trial, create_trial, drop_trial, reset_trial

# Existing official Postgres 17 image, resolved to immutable repository digest.
POSTGRES_IMAGE = "postgres@sha256:67f41722b7a8cbdb868a44a4995c846eddfdc2973bccb291ce937dce88ad5675"


def workspace_key(root: Path) -> str:
    return hashlib.sha256(str(root.resolve()).encode("utf-8")).hexdigest()[:16]


def private_json(path: Path, value: dict[str, Any]) -> None:
    """Exclusive creation prevents a competing init from overwriting credentials."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as file:
        if os.name != "nt":
            os.chmod(path, 0o600)
        json.dump(value, file, indent=2)


@dataclass(frozen=True)
class Workspace:
    root: Path

    @property
    def key(self) -> str:
        return workspace_key(self.root)

    @property
    def project(self) -> str:
        return "pa-" + self.key

    @property
    def local(self) -> Path:
        return self.root / ".agent-local"

    def config(self, *, initialize: bool = False) -> dict[str, Any]:
        path = self.local / "instance.json"
        if initialize and not path.exists():
            try:
                private_json(
                    path,
                    {
                        "root": str(self.root.resolve()),
                        "workspace_key": self.key,
                        "admin_password": secrets.token_hex(32),
                        "image": POSTGRES_IMAGE,
                    },
                )
            except FileExistsError:
                pass
        value: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        if value.get("root") != str(self.root.resolve()) or value.get("workspace_key") != self.key:
            raise ValueError("Local state belongs to another checkout; refusing to use it")
        if value.get("image") != POSTGRES_IMAGE:
            raise ValueError("Local state uses another image; follow the upgrade runbook")
        if not isinstance(value.get("admin_password"), str) or len(value["admin_password"]) < 32:
            raise ValueError("Invalid local administrator configuration")
        return value

    def compose(self, *arguments: str) -> str:
        docker = shutil.which("docker")
        if docker is None:
            raise ValueError("Docker is unavailable; install/start Docker Desktop or Engine")
        config = self.config()
        env_file = self.local / "compose.env"
        env_file.touch(exist_ok=True)
        env = os.environ.copy()
        env.update(
            {
                "AGENTS_POSTGRES_IMAGE": config["image"],
                "AGENTS_POSTGRES_PASSWORD": config["admin_password"],
            }
        )
        result = subprocess.run(
            [
                docker,
                "compose",
                "--project-name",
                self.project,
                "--project-directory",
                str(self.root.resolve()),
                "--env-file",
                str(env_file.resolve()),
                "-f",
                str((self.root / "compose.yaml").resolve()),
                *arguments,
            ],
            cwd=self.root,
            env=env,
            text=True,
            capture_output=True,
            check=False,
            timeout=240,
        )
        if result.returncode:
            # Avoid dumping interpolated config, SQL or environment on failures.
            raise ValueError(
                f"Docker Compose failed (exit {result.returncode}); check Docker status"
            )
        return result.stdout.strip()

    def up(self) -> None:
        self.config(initialize=True)
        self.compose("up", "-d", "--wait", "--wait-timeout", "90")

    def server(self) -> Server:
        config = self.config()
        mapping = self.compose("port", "postgres", "5432")
        host, separator, port = mapping.rpartition(":")
        if separator != ":" or host != "127.0.0.1" or not port.isdigit():
            raise ValueError("Expected one loopback Postgres mapping; service may be stopped")
        return Server(int(port), config["admin_password"])

    def trial_path(self, trial_id: str) -> Path:
        name = Trial(self.key, trial_id, "").name
        return self.local / "trials" / (name + ".json")

    def load_trial(self, trial_id: str) -> Trial:
        value = json.loads(self.trial_path(trial_id).read_text(encoding="utf-8"))
        if value.get("workspace_key") != self.key or value.get("trial_id") != trial_id:
            raise ValueError("Trial configuration identity mismatch")
        password = value.get("password")
        if not isinstance(password, str) or len(password) < 32:
            raise ValueError("Invalid trial credentials")
        return Trial(self.key, trial_id, password)

    def create(self, trial_id: str) -> Trial:
        path = self.trial_path(trial_id)
        trial = Trial(self.key, trial_id, secrets.token_hex(32))
        # Persist first so a failed bootstrap keeps an identity for explicit recovery.
        private_json(
            path,
            {
                "workspace_key": self.key,
                "trial_id": trial_id,
                "password": trial.password,
            },
        )
        create_trial(self.server(), trial)
        return trial

    def drop(self, trial_id: str) -> None:
        trial = self.load_trial(trial_id)
        drop_trial(self.server(), trial)
        self.trial_path(trial_id).unlink()

    def down(self, *, destroy: bool = False) -> None:
        self.compose("down", *(["--volumes"] if destroy else []))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=[
            "up",
            "status",
            "down",
            "destroy",
            "trial-create",
            "trial-reset",
            "trial-drop",
        ],
    )
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--trial")
    parser.add_argument("--confirm-workspace")
    args = parser.parse_args(argv)
    workspace = Workspace(args.root.resolve())
    trial_command = args.command.startswith("trial-")
    if trial_command != (args.trial is not None):
        parser.error("--trial is required only for trial commands")
    if args.confirm_workspace is not None and args.command != "destroy":
        parser.error("--confirm-workspace is only supported by destroy")
    if args.command == "destroy" and args.confirm_workspace != workspace.project:
        parser.error(f"Destroy requires --confirm-workspace {workspace.project}")
    try:
        if args.command == "up":
            workspace.up()
        elif args.command == "status":
            server = workspace.server()
            with server.connect() as connection:
                version = connection.execute("SHOW server_version").fetchone()
            print(
                json.dumps(
                    {
                        "workspace": workspace.project,
                        "port": server.port,
                        "postgres_version": version[0] if version else None,
                    }
                )
            )
            return 0
        elif args.command in ("down", "destroy"):
            workspace.down(destroy=args.command == "destroy")
        elif args.command == "trial-create":
            trial = workspace.create(args.trial)
            print(f"Created {trial.name}; credentials are in ignored local trial configuration")
            return 0
        elif args.command == "trial-reset":
            reset_trial(workspace.server(), workspace.load_trial(args.trial))
        else:
            workspace.drop(args.trial)
        print(f"{args.command} completed for {workspace.project}")
        return 0
    except (OSError, ValueError, psycopg.Error, subprocess.TimeoutExpired) as error:
        if isinstance(error, ValueError):
            print(str(error), file=sys.stderr)
        else:
            print(
                f"Local database command failed: {type(error).__name__}; "
                "check local configuration/service and active sessions",
                file=sys.stderr,
            )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
