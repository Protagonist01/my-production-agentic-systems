"""Fail-closed CI boundaries; no GitHub token or advisory network needed here."""

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("ci_checks", ROOT / "ci_checks.py")
assert SPEC is not None and SPEC.loader is not None
ci = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ci)


def event(body=None):
    return {
        "pull_request": {
            "base": {"repo": {"full_name": ci.REPOSITORY}},
            "body": body
            or (
                "Refs #14\n\n## Problem and behavior\n"
                "Concrete implemented behavior with an invented example.\n"
                "## Acceptance evidence\n"
                "Actual offline checks and their measured results are recorded.\n"
                "## Risks and remaining limits\n"
                "Hosted evidence is still pending; no production success claim.\n"
            ),
        }
    }


def test_pr_text_is_parsed_as_data_and_primary_issue_is_required():
    sample = event()
    sample["pull_request"]["body"] += "\nUntrusted text: $(not-a-shell-command) `not-a-command`\n"
    assert ci.validate_pr(sample) == 14


@pytest.mark.parametrize(
    "change", ["missing-issue", "two-issues", "missing-evidence", "wrong-repo"]
)
def test_invalid_pr_evidence_fails_closed(change):
    sample = event()
    if change == "missing-issue":
        sample["pull_request"]["body"] = sample["pull_request"]["body"].replace("Refs #14", "")
    elif change == "two-issues":
        sample["pull_request"]["body"] += "\nRefs #13\n"
    elif change == "missing-evidence":
        sample["pull_request"]["body"] = sample["pull_request"]["body"].replace(
            "Actual offline checks and their measured results are recorded.", ""
        )
    else:
        sample["pull_request"]["base"]["repo"]["full_name"] = "other/repository"
    with pytest.raises(ValueError):
        ci.validate_pr(sample)


@pytest.mark.parametrize("result", ["failure", "skipped", "cancelled", ""])
def test_final_gate_rejects_any_required_job_not_successful(result):
    results = dict.fromkeys(["quality", "postgres", "dependencies", "secrets", "pr"], "success")
    results["postgres"] = result
    with pytest.raises(ValueError, match="postgres"):
        ci.gate(results, pull_request=True)


def test_pr_job_skip_is_allowed_only_for_non_pr_event():
    results = dict.fromkeys(["quality", "postgres", "dependencies", "secrets"], "success")
    results["pr"] = "skipped"
    ci.gate(results, pull_request=False)
    with pytest.raises(ValueError, match="PR evidence"):
        ci.gate(results, pull_request=True)
    results["pr"] = "success"
    ci.gate(results, pull_request=True)


def test_missing_token_does_not_silently_accept_unconfirmed_issue(tmp_path, monkeypatch):
    path = tmp_path / "event.json"
    path.write_text(json.dumps(event()), encoding="utf-8")
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    assert ci.main(["pr", "--event-file", str(path)]) == 1


def test_failed_dependency_export_cannot_become_a_successful_audit(monkeypatch):
    monkeypatch.setattr(ci.shutil, "which", lambda name: "invented-uv")
    calls = []

    def export_fails(arguments, **kwargs):
        calls.append(arguments)
        return subprocess.CompletedProcess(arguments, 17, "", "invented error")

    monkeypatch.setattr(ci.subprocess, "run", export_fails)
    assert ci.audit() == 17
    assert len(calls) == 1


def test_workflow_uses_read_only_pinned_actions_and_explicit_interpreters():
    workflow = yaml.load((ROOT / ".github/workflows/ci.yml").read_text(), Loader=yaml.BaseLoader)
    assert set(workflow["on"]) == {"push", "pull_request"}
    assert all(value == "read" for value in workflow["permissions"].values())
    quality = workflow["jobs"]["quality"]
    assert set(quality["strategy"]["matrix"]["python"]) == {"3.12", "3.13"}
    assert quality["env"]["UV_PYTHON"] == "${{ matrix.python }}"
    for job in workflow["jobs"].values():
        for step in job["steps"]:
            if "uses" in step:
                assert len(step["uses"].split("@")[1]) == 40
            assert "continue-on-error" not in step
            assert "secrets.OPENAI" not in str(step) and "secrets.LANGFUSE" not in str(step)
    assert set(workflow["jobs"]["gate"]["needs"]) == {
        "quality",
        "postgres",
        "dependencies",
        "secrets",
        "pr",
    }
