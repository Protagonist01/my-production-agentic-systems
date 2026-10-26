"""Trusted local readiness and private snapshots; restore always creates a new identity."""

import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path

import psycopg
from agent_harness.local_services import Workspace, private_json
from agent_harness.postgres import Server, Trial, drop_trial

from olist_support.backup import capture, read, restore, save
from olist_support.business import setup
from olist_support.console_auth import setup_console
from olist_support.recovery_exercise import RecoveryObjective, exercise
from olist_support.service_health import readiness
from olist_support.workflow_postgres import setup_checkpoints


def bootstrap(server: Server, trial: Trial) -> None:
    for function in (setup, setup_checkpoints, setup_console):
        with server.connect(trial.name) as admin:
            function(admin, trial.name)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    commands = parser.add_subparsers(dest="command", required=True)
    health = commands.add_parser("ready")
    health.add_argument("--trial", required=True)
    backup = commands.add_parser("backup")
    backup.add_argument("--trial", required=True)
    backup.add_argument("--output", type=Path, required=True)
    rebuild = commands.add_parser("restore-new")
    rebuild.add_argument("--archive", required=True, type=Path)
    rebuild.add_argument("--archive-sha256", required=True)
    rebuild.add_argument("--new-trial", required=True)
    drill = commands.add_parser("exercise")
    drill.add_argument("--trial", required=True)
    drill.add_argument("--new-trial", required=True)
    drill.add_argument("--archive", required=True, type=Path)
    drill.add_argument("--report", required=True, type=Path)
    drill.add_argument("--max-restore-seconds", required=True, type=float)
    args = parser.parse_args()
    started = time.monotonic()
    try:
        workspace = Workspace(args.root.resolve())
        server = workspace.server()
        if args.command == "ready":
            trial = workspace.load_trial(args.trial)
            result = readiness(lambda: server.connect_trial(trial))
            print(json.dumps(result, sort_keys=True))
            return 0 if result["ready"] else 2
        if args.command in ("backup", "exercise"):
            source = workspace.load_trial(args.trial)
            revision = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=workspace.root, text=True
            ).strip()
            if subprocess.check_output(
                ["git", "status", "--porcelain"], cwd=workspace.root, text=True
            ).strip():
                raise ValueError("freeze the application checkout before operational backup")
            lock = hashlib.sha256((workspace.root / "uv.lock").read_bytes()).hexdigest()
            if args.command == "exercise":
                objective = RecoveryObjective(max_restore_seconds=args.max_restore_seconds)
                destination = workspace.trial_path(args.new_trial)
                if destination.exists():
                    raise ValueError("restore target configuration already exists")
                target, report = exercise(
                    server,
                    source,
                    args.new_trial,
                    code_revision=revision,
                    environment_lock=lock,
                    archive_path=args.archive,
                    report_path=args.report,
                    objective=objective,
                    bootstrap=bootstrap,
                )
                try:
                    private_json(
                        destination,
                        {
                            "workspace_key": workspace.key,
                            "trial_id": args.new_trial,
                            "password": target.password,
                        },
                    )
                except BaseException:
                    drop_trial(server, target)
                    raise
                from agent_harness.release_contracts import pin

                print(
                    json.dumps(
                        {
                            "exercise_passed": report.passed,
                            "report_sha256": pin(report),
                            "archive_sha256": report.archive_sha256,
                            "provider_calls": 0,
                            "production_rpo_rto_verified": False,
                            "source_overwritten": False,
                        }
                    )
                )
                return 0 if report.passed else 2
            archive = capture(
                server,
                source,
                code_revision=revision,
                environment_lock=lock,
            )
            digest = save(args.output, archive)
            print(
                json.dumps(
                    {
                        "archive_sha256": digest,
                        "tables": len(archive.tables),
                        "provider_calls": 0,
                        "elapsed_seconds": time.monotonic() - started,
                    }
                )
            )
            return 0
        destination = workspace.trial_path(args.new_trial)
        if destination.exists():
            raise ValueError("restore target configuration already exists")
        archive = read(args.archive, args.archive_sha256)
        target = restore(
            server,
            workspace.key,
            args.new_trial,
            archive,
            archive_sha256=args.archive_sha256,
            bootstrap=bootstrap,
        )
        try:
            private_json(
                destination,
                {
                    "workspace_key": workspace.key,
                    "trial_id": args.new_trial,
                    "password": target.password,
                },
            )
        except BaseException:
            drop_trial(server, target)
            raise
        print(
            json.dumps(
                {
                    "restored": True,
                    "source_overwritten": False,
                    "elapsed_seconds": time.monotonic() - started,
                    "archive_sha256": args.archive_sha256,
                    "provider_calls": 0,
                }
            )
        )
        return 0
    except (ValueError, OSError, psycopg.Error, subprocess.SubprocessError):
        print(
            json.dumps(
                {
                    "error": "operation_refused",
                    "action": "verify_private_config_archive_pin_and_new_target",
                    "provider_calls": 0,
                }
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
