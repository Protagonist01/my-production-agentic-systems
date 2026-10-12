"""Prove forbidden import paths fail using the real architecture checker."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from test_workspace import MEMBERS, ROOT


def check_isolated_sources(
    tmp_path: Path, edits: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    for member, module in MEMBERS.items():
        shutil.copytree(ROOT / member / "src" / module, tmp_path / module)
    for relative_path, content in edits.items():
        path = tmp_path / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    config = tmp_path / ".importlinter"
    shutil.copyfile(ROOT / ".importlinter", config)
    return subprocess.run(
        [
            sys.executable,
            "-c",
            "from importlinter.cli import lint_imports_command; lint_imports_command()",
            "--config",
            str(config),
            "--no-cache",
        ],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(tmp_path)},
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def test_vertical_can_use_shared_harness(tmp_path: Path) -> None:
    result = check_isolated_sources(
        tmp_path, {"olist_support/allowed.py": "import agent_harness\n"}
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "2 kept, 0 broken" in result.stdout


@pytest.mark.parametrize(
    "edits,contract",
    [
        ({"agent_harness/bad.py": "import olist_support\n"}, "Harness cannot import"),
        ({"olist_support/bad.py": "from cfpb_triage import __doc__\n"}, "Industry packages"),
        (
            {
                "agent_harness/bad.py": "from . import bridge\n",
                "agent_harness/bridge.py": "import prior_auth\n",
            },
            "Harness cannot import",
        ),
        (
            {
                "olist_support/bad.py": "import agent_harness.bridge\n",
                "agent_harness/bridge.py": "import supply_chain\n",
            },
            "Industry packages",
        ),
    ],
)
def test_forbidden_import_fails(tmp_path: Path, edits: dict[str, str], contract: str) -> None:
    result = check_isolated_sources(tmp_path, edits)
    assert result.returncode != 0, "An architecture violation passed."
    assert contract in result.stdout and "BROKEN" in result.stdout, result.stdout + result.stderr
