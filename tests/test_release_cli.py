"""Explicit CLI pins, private output and no implicit baseline promotion."""

import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta

import pytest
from agent_harness import release_cli
from agent_harness.release_contracts import BaselineApproval, ReleasePolicy, pin
from agent_harness.scorecard_contracts import ReportPolicy
from release_fixtures import capture, inputs


@pytest.fixture(scope="module")
def cli_inputs(tmp_path_factory):
    root = tmp_path_factory.mktemp("release-cli-private")
    loaded, old, old_path = capture(root, "baseline")
    _, new, new_path = capture(root, "candidate")
    policy = ReleasePolicy(
        version="invented-cli-policy",
        max_age_seconds=3600,
        min_autonomous_completion=1.0,
        max_review_rate=0.0,
        report=ReportPolicy(
            version="invented-cli-report", required_case_ids=loaded.manifest.case_ids
        ),
    )
    approval = BaselineApproval(
        version="invented-only",
        baseline_sha256=pin(old.manifest),
        release_policy_sha256=pin(policy),
        reviewer="invented-reviewer",
        review_ref="invented-offline-not-a-domain-approval",
        approved_at=old.manifest.finished_at,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    files = {
        "manifest": loaded.manifest,
        "manifest-pin": loaded.pin,
        "candidate-spec": new.manifest.candidate,
        "release-policy": policy,
        "baseline-approval": approval,
    }
    args = []
    for name, value in files.items():
        path = root / (name + ".json")
        path.write_text(value.canonical_json(), encoding="utf-8")
        if name != "baseline-approval":
            args += ["--" + name, str(path)]
    args += [
        "--candidate-spec-sha256",
        pin(new.manifest.candidate),
        "--candidate-evidence",
        str(new_path),
        "--candidate-evidence-sha256",
        pin(new.manifest),
        "--baseline-evidence",
        str(old_path),
        "--baseline-evidence-sha256",
        pin(old.manifest),
        "--baseline-spec-sha256",
        pin(old.manifest.candidate),
        "--release-policy-sha256",
        pin(policy),
    ]
    return root, args, approval


def test_compare_subprocess_writes_result_without_approval_or_release(cli_inputs):
    root, args, _ = cli_inputs
    output = root / "comparison"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_harness.release_cli",
            "eval-compare",
            *args,
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    body = json.loads((output / "result.json").read_text())
    assert body["release_decision"] == "not_performed"
    assert body["baseline_approval"] == "not_established"
    assert body["regressed_cases"] == []
    assert "PRIVATE" not in (output / "result.json").read_text()
    assert release_cli.main(["eval-compare", *args, "--output", str(output)]) == 1


def test_mock_release_exits_nonzero_and_keeps_approval_unchanged(cli_inputs):
    root, args, approval = cli_inputs
    approval_path = root / "baseline-approval.json"
    before = approval_path.read_bytes()
    output = root / "blocked-release"
    assert (
        release_cli.main(
            [
                "eval-release",
                *args,
                "--output",
                str(output),
                "--baseline-approval",
                str(approval_path),
                "--baseline-approval-sha256",
                pin(approval),
            ]
        )
        == 1
    )
    decision = json.loads((output / "result.json").read_text())
    assert not decision["allowed"]
    assert "candidate_mock_evidence" in decision["blockers"]
    assert "baseline_mock_evidence" in decision["blockers"]
    assert "evaluation:evaluation_standard_inputs_missing" in decision["blockers"]
    from agent_harness.release_contracts import sha256

    assert decision["evaluation_audit_sha256"] == sha256(
        (output / "evaluation-audit.json").read_bytes()
    )
    assert approval_path.read_bytes() == before


def test_failed_audit_sidecar_write_never_publishes_decision(cli_inputs, monkeypatch):
    root, args, approval = cli_inputs
    output = root / "audit-write-failure"
    original = release_cli._write_exclusive

    def fail_sidecar(path, content):
        if path.name == "evaluation-audit.json":
            raise OSError("invented sidecar failure")
        original(path, content)

    monkeypatch.setattr(release_cli, "_write_exclusive", fail_sidecar)
    assert (
        release_cli.main(
            [
                "eval-release",
                *args,
                "--output",
                str(output),
                "--baseline-approval",
                str(root / "baseline-approval.json"),
                "--baseline-approval-sha256",
                pin(approval),
            ]
        )
        == 1
    )
    assert not (output / "result.json").exists()


def test_partial_methodology_arguments_are_rejected(cli_inputs):
    root, args, approval = cli_inputs
    with pytest.raises(SystemExit):
        release_cli.main(
            [
                "eval-release",
                *args,
                "--output",
                str(root / "partial-audit"),
                "--baseline-approval",
                str(root / "baseline-approval.json"),
                "--baseline-approval-sha256",
                pin(approval),
                "--evaluation-profile",
                "missing.json",
            ]
        )
    assert not (root / "partial-audit").exists()


def test_missing_or_wrong_pins_fail_before_new_output(cli_inputs):
    root, args, _ = cli_inputs
    with pytest.raises(SystemExit):
        release_cli.main(["eval-release", *args, "--output", str(root / "no-approval")])
    changed = list(args)
    changed[changed.index("--candidate-spec-sha256") + 1] = "0" * 64
    output = root / "wrong-pin"
    assert release_cli.main(["eval-compare", *changed, "--output", str(output)]) == 1
    assert not output.exists()


def test_record_command_refuses_previous_response_inputs(cli_inputs):
    root, args, _ = cli_inputs
    with pytest.raises(SystemExit):
        release_cli.main(
            [
                "eval-record",
                *args,
                "--schedule",
                str(root / "schedule.json"),
                "--composition",
                str(root / "composition.json"),
                "--source-root",
                str(root),
                "--output",
                str(root / "bad-record"),
            ]
        )
    assert not (root / "bad-record").exists()


def test_actual_record_cli_creates_three_new_mock_dispatches(tmp_path):
    from pathlib import Path

    from agent_harness.release_contracts import sha256
    from agent_harness.release_evidence import read_evidence

    loaded, schedule, spec, config, _ = inputs(tmp_path)
    root = Path(__file__).resolve().parents[1]
    inventory = {
        p.relative_to(root).as_posix(): sha256(p.read_bytes())
        for p in (root / "harness/src/agent_harness").glob("*.py")
    }
    inventory["uv.lock"] = sha256((root / "uv.lock").read_bytes())
    spec = spec.model_copy(
        update={"source_files": inventory, "environment_lock": inventory["uv.lock"]}
    )
    schedule = schedule.model_copy(
        update={
            "tasks": tuple(
                t.model_copy(
                    update={
                        "context": t.context.model_copy(
                            update={
                                "versions": t.context.versions.model_copy(
                                    update={"environment_lock": spec.environment_lock}
                                )
                            }
                        )
                    }
                )
                for t in schedule.tasks
            )
        }
    )
    files = {
        "manifest": loaded.manifest,
        "manifest-pin": loaded.pin,
        "candidate-spec": spec,
        "composition": config,
        "schedule": schedule,
    }
    args = []
    for name, value in files.items():
        path = tmp_path / (name + ".json")
        path.write_text(value.canonical_json(), encoding="utf-8")
        args += ["--" + name, str(path)]
    output = tmp_path / "cli-recording"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_harness.release_cli",
            "eval-record",
            *args,
            "--candidate-spec-sha256",
            pin(spec),
            "--source-root",
            str(root),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    verified = read_evidence(
        output, loaded, evidence_sha256=summary["evidence_sha256"], candidate_sha256=pin(spec)
    )
    assert len(verified.receipts) == 3 and verified.manifest.origin == "mock"
    assert verified.batch.autonomous_completions == 3
