"""CI boundaries callable locally: locked dependency audit, PR evidence and final gate."""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from collections.abc import Mapping
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
REPOSITORY = "Protagonist01/my-production-agentic-systems"
REQUIRED_SECTIONS = ("Problem and behavior", "Acceptance evidence", "Risks and remaining limits")


def validate_pr(event: Mapping[str, Any]) -> int:
    """Only data parsing; PR-controlled titles/branches/bodies never enter shell code."""
    pull = event.get("pull_request")
    if not isinstance(pull, dict):
        raise ValueError("Expected pull request event data")
    base = pull.get("base")
    repository = base.get("repo") if isinstance(base, dict) else None
    if not isinstance(repository, dict) or repository.get("full_name") != REPOSITORY:
        raise ValueError("Expected a pull request targeting this repository")
    body = pull.get("body")
    if not isinstance(body, str):
        raise ValueError("PR needs a body with issue and acceptance evidence")
    references = re.findall(r"(?im)^\s*Refs\s+#([1-9]\d*)\b", body)
    if len(set(references)) != 1:
        raise ValueError("PR must have exactly one primary repository issue: Refs #<number>")
    headings = list(re.finditer(r"(?m)^##\s+([^\n]+)\s*$", body))
    sections = {
        heading.group(1).strip(): body[
            heading.end() : headings[i + 1].start() if i + 1 < len(headings) else len(body)
        ].strip()
        for i, heading in enumerate(headings)
    }
    for title in REQUIRED_SECTIONS:
        content = sections.get(title, "")
        if (
            len(content) < 20
            or "Describe the trigger" in content
            or "State remaining failures" in content
        ):
            raise ValueError(f"PR needs substantive section: {title}")
    return int(references[0])


def confirm_issue(number: int, token: str) -> None:
    request = urllib.request.Request(
        f"https://api.github.com/repos/{REPOSITORY}/issues/{number}",
        headers={
            "Authorization": "Bearer " + token,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "production-agents-ci",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        issue = json.load(response)
    if issue.get("number") != number or "pull_request" in issue:
        raise ValueError("Reference must identify a repository issue, not another PR")


def gate(results: Mapping[str, str], *, pull_request: bool) -> None:
    for name in ("quality", "postgres", "dependencies", "secrets"):
        if results.get(name) != "success":
            raise ValueError(f"Required job {name} did not succeed: {results.get(name, 'missing')}")
    expected = "success" if pull_request else "skipped"
    if results.get("pr") != expected:
        raise ValueError(f"PR evidence job must be {expected} for this event")


def audit() -> int:
    uv = shutil.which("uv")
    if uv is None:
        raise ValueError("uv required for exact locked dependency export")
    output = ROOT / "artifacts" / "locked-audit-requirements.txt"
    output.parent.mkdir(exist_ok=True)
    export = subprocess.run(
        [
            uv,
            "export",
            "--locked",
            "--all-packages",
            "--all-groups",
            "--no-emit-workspace",
            "--no-header",
            "--output-file",
            str(output),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if export.returncode:
        print("Locked dependency export failed", file=sys.stderr)
        return export.returncode
    if not output.read_text(encoding="utf-8").strip():
        raise ValueError("Dependency export unexpectedly empty")
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pip_audit",
            "--requirement",
            str(output),
            "--require-hashes",
            "--disable-pip",
            "--strict",
            "--progress-spinner",
            "off",
        ],
        cwd=ROOT,
        check=False,
    ).returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["audit", "pr", "gate"])
    parser.add_argument("--event-file", type=Path)
    args = parser.parse_args(argv)
    if args.event_file is not None and args.command != "pr":
        parser.error("--event-file is only supported by pr")
    try:
        if args.command == "audit":
            return audit()
        if args.command == "pr":
            path = args.event_file or Path(os.environ.get("GITHUB_EVENT_PATH", ""))
            issue = validate_pr(json.loads(path.read_text(encoding="utf-8")))
            token = os.environ.get("GITHUB_TOKEN", "")
            if not token:
                raise ValueError("Read-only GitHub token required to confirm the linked issue")
            confirm_issue(issue, token)
            print(f"PR evidence references repository issue #{issue}")
        else:
            gate(
                {
                    name: os.environ.get("RESULT_" + name.upper(), "")
                    for name in ("quality", "postgres", "dependencies", "secrets", "pr")
                },
                pull_request=os.environ.get("GITHUB_EVENT_NAME") == "pull_request",
            )
            print("All required CI jobs passed")
        return 0
    except (ValueError, OSError, urllib.error.URLError) as error:
        print(f"CI check failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
