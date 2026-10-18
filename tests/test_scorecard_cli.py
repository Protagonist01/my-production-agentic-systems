"""Read-only journal CLI, explicit pins and exclusive private report publication."""

import json
import os
import socket
import subprocess
import sys

import pytest
from agent_harness.fault_contracts import digest
from agent_harness.scorecard_cli import main
from agent_harness.scorecard_contracts import ReportPolicy, Scorecard
from agent_harness.trials import TrialJournal
from scorecard_fixtures import batch, population


def inputs(root, statuses=None):
    loaded, schedule = population()
    value = batch(loaded, schedule, statuses)
    journal = TrialJournal.create(root / "journal", schedule)
    for row in value.rows:
        journal.append(row)
    (root / "manifest.json").write_text(loaded.manifest.canonical_json())
    (root / "pin.json").write_text(loaded.pin.canonical_json())
    (root / "policy.json").write_text(
        ReportPolicy(version="reviewed-v1", required_case_ids=("case-0",)).canonical_json()
    )
    args = [
        "--manifest",
        str(root / "manifest.json"),
        "--manifest-pin",
        str(root / "pin.json"),
        "--journal",
        str(journal.path),
        "--report-policy",
        str(root / "policy.json"),
        "--output",
        str(root / "report"),
        "--code-revision",
        "invented-reporter",
    ]
    return loaded, value, args


def test_module_cli_runs_without_provider_keys_or_network_and_preserves_missing_rows(tmp_path):
    loaded, value, args = inputs(tmp_path, {("case-1", "trial-0"): "missing"})
    before = {p.name: p.read_bytes() for p in (tmp_path / "journal").rglob("*.json")}
    result = subprocess.run(
        [sys.executable, "-m", "agent_harness.scorecard_cli", *args],
        capture_output=True,
        text=True,
        timeout=30,
        env={
            k: v for k, v in os.environ.items() if not any(s in k for s in ("API_KEY", "LANGFUSE"))
        },
    )
    assert result.returncode == 0, result.stderr
    assert "no release decision" in result.stdout
    report = Scorecard.model_validate_json((tmp_path / "report/scorecard.json").read_bytes())
    assert report.overall.missing_rows == 1 and report.overall.scheduled_trials == 3
    assert before == {p.name: p.read_bytes() for p in (tmp_path / "journal").rglob("*.json")}
    assert {p.name for p in (tmp_path / "report").iterdir()} == {"scorecard.json", "scorecard.md"}
    if os.name != "nt":
        assert (tmp_path / "report").stat().st_mode & 0o077 == 0
        assert (tmp_path / "report/scorecard.json").stat().st_mode & 0o077 == 0
    assert main(args) == 1  # Never overwrite a report.


def test_comparison_requires_external_baseline_digest_and_does_not_autoselect(tmp_path):
    loaded, old, args = inputs(tmp_path)
    journal = TrialJournal.create(tmp_path / "candidate", old.schedule)
    for row in batch(loaded, old.schedule, {("case-0", "trial-0"): "missing"}).rows:
        journal.append(row)
    args[args.index("--journal") + 1] = str(journal.path)
    args += ["--baseline-journal", str(tmp_path / "journal")]
    with pytest.raises(SystemExit) as error:
        main(args)
    assert error.value.code == 2 and not (tmp_path / "report").exists()
    args += ["--baseline-sha256", "0" * 64]
    assert main(args) == 1 and not (tmp_path / "report").exists()
    args[-1] = digest(old)
    assert main(args) == 0
    comparison = json.loads((tmp_path / "report/comparison.json").read_text())
    assert comparison["newly_failing_required_cases"] == ["case-0"]
    assert comparison["baseline_approval"] == "not_established_by_comparison"


@pytest.mark.parametrize("change", ["pin", "policy", "row", "filename"])
def test_bad_inputs_never_create_output_or_leak_error_bodies(tmp_path, capsys, change):
    loaded, value, args = inputs(tmp_path)
    if change == "pin":
        data = json.loads((tmp_path / "pin.json").read_text())
        data["sha256"] = "0" * 64
        (tmp_path / "pin.json").write_text(json.dumps(data))
    elif change == "policy":
        (tmp_path / "policy.json").write_text('{"private-error-canary": "unknown"}')
    else:
        target = next((tmp_path / "journal/rows").iterdir())
        if change == "row":
            target.write_text("private-error-canary")
        else:
            target.rename(target.with_name("changed-name.json"))
    assert main(args) == 1 and not (tmp_path / "report").exists()
    assert "private-error-canary" not in capsys.readouterr().err


def test_inline_cli_does_not_install_process_global_network_hook(tmp_path, monkeypatch):
    loaded, value, args = inputs(tmp_path)
    hooks = []
    monkeypatch.setattr(sys, "addaudithook", hooks.append)

    def forbidden(*a, **kw):
        pytest.fail("report CLI attempted network")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    assert main(args) == 0 and hooks == []


def test_write_failure_is_non_success_and_partial_output_is_never_overwritten(
    tmp_path, monkeypatch, capsys
):
    import agent_harness.scorecard_cli as cli

    loaded, value, args = inputs(tmp_path)
    original = cli._write_exclusive
    writes = []

    def fail_second(path, text):
        writes.append(path.name)
        if len(writes) == 2:
            raise OSError("private-file-error-canary")
        original(path, text)

    monkeypatch.setattr(cli, "_write_exclusive", fail_second)
    assert cli.main(args) == 1
    first = (tmp_path / "report/scorecard.json").read_bytes()
    assert not (tmp_path / "report/scorecard.md").exists()
    assert cli.main(args) == 1
    assert (tmp_path / "report/scorecard.json").read_bytes() == first
    logs = capsys.readouterr()
    assert "Private scorecard written" not in logs.out
    assert "private-file-error-canary" not in logs.err
