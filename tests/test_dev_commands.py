"""Command boundary checks; real setup/check/example are exercised separately."""

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("dev_commands", ROOT / "dev.py")
assert SPEC is not None and SPEC.loader is not None
dev = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(dev)


@pytest.mark.parametrize("command", ["eval-record", "eval-compare"])
def test_planned_commands_fail_without_uv_or_project_dependencies(command, tmp_path) -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "dev.py"), command],
        cwd=tmp_path,
        env={**os.environ, "PATH": ""},
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 2
    assert "not implemented" in result.stderr and "Prerequisite: H" in result.stderr
    assert "Running" not in result.stdout


def test_missing_uv_fails_clearly(monkeypatch, capsys) -> None:
    monkeypatch.setattr(dev.shutil, "which", lambda name: None)
    assert dev.main(["setup"]) == 1
    assert "uv is unavailable" in capsys.readouterr().err


def test_check_stops_on_the_first_failed_child_and_preserves_exit_code(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(dev.shutil, "which", lambda name: "invented-uv")

    def fail_types(arguments):
        calls.append(arguments)
        return 13 if "mypy" in arguments else 0

    monkeypatch.setattr(dev, "execute", fail_types)
    assert dev.main(["check"]) == 13
    assert len(calls) == 4
    assert not any("lint-imports" in call or "pytest" in call for call in calls)
    assert calls[-1] == dev.uv_command("types", "invented-uv")


def test_child_runs_in_root_with_space_arguments_and_real_failure_status(
    monkeypatch, tmp_path
) -> None:
    working = tmp_path / "checkout with spaces"
    working.mkdir()
    monkeypatch.setattr(dev, "ROOT", working)
    child = (
        "import pathlib,sys; "
        "assert pathlib.Path.cwd().name == 'checkout with spaces'; "
        "assert sys.argv[1] == 'one argument with spaces'; sys.exit(7)"
    )
    assert dev.execute([sys.executable, "-c", child, "one argument with spaces"]) == 7


def test_process_start_failure_is_not_success(monkeypatch, capsys) -> None:
    def cannot_start(*args, **kwargs):
        raise FileNotFoundError("invented missing executable")

    monkeypatch.setattr(dev.subprocess, "run", cannot_start)
    assert dev.execute(["missing-executable"]) == 1
    assert "Could not start command" in capsys.readouterr().err


@pytest.mark.parametrize("dirty", ["", " M dev.py\n", "?? new_module.py\n"])
def test_example_revision_marks_tracked_and_untracked_changes(monkeypatch, dirty) -> None:
    monkeypatch.setattr(dev.shutil, "which", lambda name: "invented-git")
    responses = iter(
        [
            subprocess.CompletedProcess([], 0, "invented-head\n", ""),
            subprocess.CompletedProcess([], 0, dirty, ""),
        ]
    )
    monkeypatch.setattr(dev.subprocess, "run", lambda *args, **kwargs: next(responses))
    assert dev.source_revision() == "invented-head" + ("+dirty" if dirty else "")


def test_missing_revision_requires_an_explicit_identifier(monkeypatch, capsys) -> None:
    monkeypatch.setattr(dev.shutil, "which", lambda name: None if name == "git" else "invented-uv")
    assert dev.main(["example"]) == 1
    assert "--code-revision" in capsys.readouterr().err
    calls = []
    monkeypatch.setattr(dev, "execute", lambda arguments: calls.append(arguments) or 0)
    assert dev.main(["example", "--code-revision", "export-v1"]) == 0
    assert "export-v1" in calls[0]
    assert str(ROOT / "uv.lock") in calls[0]


def test_wrong_option_and_unknown_command_fail_before_dispatch(monkeypatch) -> None:
    def must_not_dispatch(arguments):
        raise AssertionError("Invalid CLI reached execution")

    monkeypatch.setattr(dev, "execute", must_not_dispatch)
    for arguments in (["check", "--code-revision", "invalid"], ["unknown-feature"]):
        with pytest.raises(SystemExit) as error:
            dev.main(arguments)
        assert error.value.code == 2


def test_replay_dispatches_current_code_with_revision_and_lock(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(dev.shutil, "which", lambda name: "invented-uv")
    monkeypatch.setattr(dev, "execute", lambda arguments: calls.append(arguments) or 7)
    assert dev.main(["eval-replay", "--code-revision", "current-code"]) == 7
    assert "agent_harness.replay_example" in calls[0] and "current-code" in calls[0]
    assert str(ROOT / "uv.lock") in calls[0]


def test_telemetry_command_uses_invented_probe_with_current_source(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(dev.shutil, "which", lambda name: "invented-uv")
    monkeypatch.setattr(dev, "source_revision", lambda: "actual-head+dirty")
    monkeypatch.setattr(dev, "execute", lambda args: calls.append(args) or 1)
    assert dev.main(["telemetry-check"]) == 1
    assert "agent_harness.telemetry_probe" in calls[0]
    assert "actual-head+dirty" in calls[0] and str(ROOT) in calls[0]
    assert "agent_harness.trace_probe" not in calls[0]


def test_scorecard_requires_explicit_inputs_and_dispatches_current_reporter_source(monkeypatch):
    calls = []
    monkeypatch.setattr(dev.shutil, "which", lambda name: "invented-uv")
    monkeypatch.setattr(dev, "source_revision", lambda: "actual-reporter+dirty")
    monkeypatch.setattr(dev, "execute", lambda args: calls.append(args) or 9)
    args = [
        "scorecard",
        "--manifest",
        "private manifest.json",
        "--manifest-pin",
        "reviewed pin.json",
        "--journal",
        "private journal",
        "--report-policy",
        "reviewed policy.json",
        "--output",
        "new report",
    ]
    assert dev.main(args) == 9
    assert "agent_harness.scorecard_cli" in calls[0] and "actual-reporter+dirty" in calls[0]
    assert "private manifest.json" in calls[0]
    for invalid in (
        ["scorecard"],
        ["check", "--output", "unexpected"],
        [*args, "--baseline-journal", "one-sided"],
    ):
        with pytest.raises(SystemExit) as error:
            dev.main(invalid)
        assert error.value.code == 2
    assert len(calls) == 1
