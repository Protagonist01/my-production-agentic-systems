"""Portable development commands. Requires Python 3.12+ and uv on PATH."""

import argparse
import shutil
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHECKS = ("lock", "lint", "format-check", "types", "imports", "test")
PLANNED = {
    "eval-replay": "H3 #17: immutable recordings and strict offline replay",
    "eval-record": "H10 #24: fresh candidate recording and release evidence",
    "eval-compare": "H9 #23: scorecards and case-level baseline comparison",
}
SERVICE_COMMANDS = {
    "db-up": "up",
    "db-status": "status",
    "db-down": "down",
    "db-destroy": "destroy",
    "trial-create": "trial-create",
    "trial-reset": "trial-reset",
    "trial-drop": "trial-drop",
}


def uv_command(command: str, executable: str) -> list[str]:
    """One argument map for individual checks and the aggregate check command."""
    run = [executable, "run", "--locked", "--all-packages", "--link-mode", "copy"]
    sources = ["dev.py", "ci_checks.py", "harness", "projects", "tests"]
    commands = {
        "setup": [executable, "sync", "--locked", "--all-packages", "--link-mode", "copy"],
        "lock": [executable, "lock", "--check"],
        "lint": [*run, "python", "-m", "ruff", "check", *sources],
        "format-check": [*run, "python", "-m", "ruff", "format", "--check", *sources],
        "types": [*run, "python", "-m", "mypy"],
        "imports": [*run, "lint-imports", "--no-cache"],
        "test": [*run, "python", "-m", "pytest", "-q"],
        "build": [executable, "build", "--all-packages"],
        "audit": [*run, "python", "ci_checks.py", "audit"],
        "integration-check": [
            *run,
            "python",
            "-m",
            "agent_harness.integration_smoke",
            "offline",
            "--root",
            str(ROOT),
        ],
        "integration-live": [
            *run,
            "python",
            "-m",
            "agent_harness.integration_smoke",
            "live",
            "--root",
            str(ROOT),
        ],
        "db-check": [
            *run,
            "python",
            "-m",
            "pytest",
            "-q",
            "tests/integration",
            "-o",
            "addopts=--strict-config --strict-markers",
        ],
        "trace-check": [
            *run,
            "python",
            "-m",
            "agent_harness.trace_probe",
            "--root",
            str(ROOT),
        ],
    }
    return commands[command]


def execute(arguments: Sequence[str]) -> int:
    """Run in this checkout; no shell quoting, activation or current-directory dependency."""
    try:
        return subprocess.run(list(arguments), cwd=ROOT, check=False).returncode
    except OSError as error:
        print(f"Could not start command: {error}", file=sys.stderr)
        return 1


def source_revision() -> str:
    """A dirty checkout must not claim that its executed source equals clean HEAD."""
    git = shutil.which("git")
    if git is None:
        raise ValueError("Git is unavailable; example requires --code-revision for source exports.")
    head = subprocess.run(
        [git, "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    status = subprocess.run(
        [git, "status", "--porcelain", "--untracked-files=normal"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if head.returncode or status.returncode or not head.stdout.strip():
        raise ValueError("Cannot determine source revision; supply --code-revision explicitly.")
    return head.stdout.strip() + ("+dirty" if status.stdout.strip() else "")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=[
            "setup",
            *CHECKS,
            "check",
            "build",
            "audit",
            "integration-check",
            "integration-live",
            "trace-check",
            "gateway-live",
            "example",
            *PLANNED,
            *SERVICE_COMMANDS,
            "db-check",
        ],
    )
    parser.add_argument(
        "--code-revision",
        help="Explicit source identifier for example when Git is unavailable",
    )
    parser.add_argument("--trial", help="Trial identity for trial-create/reset/drop")
    parser.add_argument("--confirm-workspace", help="Exact workspace identity for db-destroy")
    args = parser.parse_args(argv)
    if args.code_revision is not None and args.command not in ("example", "gateway-live"):
        parser.error("--code-revision is only supported by example/gateway-live")
    if args.command.startswith("trial-") != (args.trial is not None):
        parser.error("--trial is required only for trial commands")
    if args.confirm_workspace is not None and args.command != "db-destroy":
        parser.error("--confirm-workspace is only supported by db-destroy")
    if args.command in PLANNED:
        print(
            f"{args.command} is not implemented. Prerequisite: {PLANNED[args.command]}",
            file=sys.stderr,
        )
        return 2
    uv = shutil.which("uv")
    if uv is None:
        print("uv is unavailable on PATH. See README setup prerequisites.", file=sys.stderr)
        return 1
    if args.command in SERVICE_COMMANDS:
        arguments = [
            uv,
            "run",
            "--locked",
            "--all-packages",
            "--link-mode",
            "copy",
            "python",
            "-m",
            "agent_harness.local_services",
            SERVICE_COMMANDS[args.command],
            "--root",
            str(ROOT),
        ]
        if args.trial is not None:
            arguments.extend(["--trial", args.trial])
        if args.confirm_workspace is not None:
            arguments.extend(["--confirm-workspace", args.confirm_workspace])
        return execute(arguments)
    if args.command in ("example", "gateway-live"):
        try:
            revision = args.code_revision if args.code_revision is not None else source_revision()
            if not revision.strip():
                raise ValueError("--code-revision must not be empty")
        except (ValueError, OSError) as error:
            print(str(error), file=sys.stderr)
            return 1
        return execute(
            [
                uv,
                "run",
                "--locked",
                "--all-packages",
                "--link-mode",
                "copy",
                "python",
                "-m",
                "agent_harness.offline_example"
                if args.command == "example"
                else "agent_harness.gateway_probe",
                "--code-revision",
                revision,
                *(
                    ["--lockfile", str(ROOT / "uv.lock")]
                    if args.command == "example"
                    else ["--root", str(ROOT)]
                ),
            ]
        )
    steps = CHECKS if args.command == "check" else (args.command,)
    for step in steps:
        print(f"Running {step}", flush=True)
        result = execute(uv_command(step, uv))
        if result:
            return result
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
