"""Capture/readback refuses missing, altered and invented-success evidence."""

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
READER = ROOT / "docs/evaluation/read_cfpb_diagnostic_baselines.py"
RUNNER = ROOT / "docs/evaluation/run_cfpb_diagnostic_baselines.py"


@pytest.fixture(scope="module")
def captured(tmp_path_factory):
    root = tmp_path_factory.mktemp("cfpb-baselines") / "capture"
    result = subprocess.run(
        [sys.executable, str(RUNNER), "--output", str(root)],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    pin = json.loads(result.stdout)["manifest_sha256"]
    return root, pin


def reader():
    spec = importlib.util.spec_from_file_location("cfpb_baseline_reader", READER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_full_schedule_stays_visible_and_publication_is_exclusive(captured):
    root, pin = captured
    result = reader().readback(root, pin)
    assert result["observed"] == 96 and result["missing"] == 192
    summary = json.loads((root / "summary.json").read_bytes())
    assert all(
        x["security_effect_unknown"] == x["cost_unknown"] == 48
        for x in summary["variants"].values()
    )
    assert not summary["qualified_labels"] and not summary["release_allowed"]
    repeated = subprocess.run(
        [sys.executable, str(RUNNER), "--output", str(root)], capture_output=True, timeout=60
    )
    assert repeated.returncode != 0
    assert hashlib.sha256((root / "manifest.json").read_bytes()).hexdigest() == pin


@pytest.mark.parametrize("tamper", ["missing", "prediction", "security", "score", "wrong_pin"])
def test_readback_refuses_tampering(captured, tmp_path, tamper):
    original, pin = captured
    copied = tmp_path / "modified"
    shutil.copytree(original, copied)
    if tamper == "wrong_pin":
        pin = "0" * 64
    elif tamper == "score":
        report = json.loads((copied / "report.json").read_bytes())
        report["reports"]["rules/stress"]["correct_completed"] = 48
        (copied / "report.json").write_text(json.dumps(report))
    else:
        rows = json.loads((copied / "records.json").read_bytes())
        if tamper == "missing":
            rows.pop()
        elif tamper == "prediction":
            rows[0]["scope"] = "in_scope"
        else:
            rows[0]["unauthorized_write"] = False
        (copied / "records.json").write_text(json.dumps(rows))
    with pytest.raises(ValueError, match="mismatch"):
        reader().readback(copied, pin)


def test_reforged_summary_cannot_claim_a_known_security_effect(captured, tmp_path):
    original, _ = captured
    copied = tmp_path / "reforged"
    shutil.copytree(original, copied)
    rows = json.loads((copied / "records.json").read_bytes())
    rows[0]["unauthorized_write"] = False
    raw = json.dumps(rows).encode()
    (copied / "records.json").write_bytes(raw)
    manifest = json.loads((copied / "manifest.json").read_bytes())
    manifest["files"]["records.json"] = hashlib.sha256(raw).hexdigest()
    raw = json.dumps(manifest).encode()
    (copied / "manifest.json").write_bytes(raw)
    with pytest.raises(ValueError, match="mismatch"):
        reader().readback(copied, hashlib.sha256(raw).hexdigest())
