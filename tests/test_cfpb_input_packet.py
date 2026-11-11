"""No proposal acceptance, label leakage or execution authorization during projection."""

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[1] / "docs/evaluation/prepare_cfpb_input_packet.py"


def helper():
    spec = importlib.util.spec_from_file_location("cfpb_input_preparation", PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def save(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def draft(tmp_path):
    module = helper()
    root = tmp_path / "draft"
    root.mkdir()
    originals, proposals, provenance = [], [], []
    for n in range(12):
        text = f"Invented private financial query {n}"
        pin = hashlib.sha256(text.encode()).hexdigest()
        identity = f"case-{n}"
        originals.append(
            {
                "case_id": identity,
                "original_text": text,
                "source": "banking77",
                "publisher_split": "train",
                "project_mapping_status": "unreviewed_proposal",
                "text_sha256": pin,
                "publisher_label": "hidden-publisher-label",
            }
        )
        proposals.append(
            {
                "case_id": identity,
                "text_sha256": pin,
                "accepted": False,
                "status": "AI_proposed_for_development_review_only",
                "proposed_scope": "insufficient",
                "product": None,
                "issue": None,
                "priority": None,
                "ambiguity": None,
            }
        )
        provenance.append({"case_id": identity})
    files = {}
    for name in module.SOURCE_FILES:
        value = {
            "selected-originals.json": originals,
            "proposed-mappings.json": proposals,
            "selection-provenance.json": provenance,
        }.get(name, "invented source receipt")
        files[name] = save(root / name, value)
    pin = save(
        root / "manifest.json",
        {
            "complete": True,
            "cases": 12,
            "labels_accepted": False,
            "provider_attempts": 0,
            "source_test_records_decoded": False,
            "release_allowed": False,
            "files": files,
        },
    )
    return module, root, pin


def test_input_only_projection_preserves_bytes_and_pending_state(tmp_path):
    module, root, source_pin = draft(tmp_path)
    output = tmp_path / "packet"
    pin = module.prepare(root, source_pin, output)
    result = module.verify(root, source_pin, output, pin)
    assert (
        result["verified"]
        and not result["execution_authorized"]
        and not result["mappings_accepted"]
    )
    inputs = json.loads((output / "inputs.json").read_bytes())
    assert len(inputs) == 12 and all(
        set(r) == {"schema_version", "case_id", "narrative"} for r in inputs
    )
    assert "hidden-publisher-label" not in (output / "inputs.json").read_text()
    assert "hidden-publisher-label" in (output / "evaluator-only.json").read_text()
    readiness = json.loads((output / "readiness.json").read_bytes())
    assert readiness["trials"] is None and readiness["operating_limits"] is None
    assert not readiness["training_or_scoring_performed"] and readiness["blockers"]
    with pytest.raises(FileExistsError):
        module.prepare(root, source_pin, output)
    assert hashlib.sha256((root / "manifest.json").read_bytes()).hexdigest() == source_pin


@pytest.mark.parametrize(
    "target,field,value",
    [
        ("inputs.json", "publisher_label", "leaked target"),
        ("readiness.json", "execution_authorized", True),
        ("readiness.json", "mapping_acceptance", True),
        ("readiness.json", "trials", 3),
    ],
)
def test_rehashed_tampering_cannot_add_labels_or_authority(tmp_path, target, field, value):
    module, root, source_pin = draft(tmp_path)
    output = tmp_path / "packet"
    module.prepare(root, source_pin, output)
    document = json.loads((output / target).read_bytes())
    if target == "inputs.json":
        document[0][field] = value
    else:
        document[field] = value
    changed = save(output / target, document)
    manifest = json.loads((output / "manifest.json").read_bytes())
    manifest["files"][target] = changed
    pin = save(output / "manifest.json", manifest)
    with pytest.raises(ValueError, match="refused"):
        module.verify(root, source_pin, output, pin)


def test_source_change_wrong_pin_and_source_test_split_refuse(tmp_path):
    module, root, source_pin = draft(tmp_path)
    with pytest.raises(ValueError):
        module.prepare(root, "0" * 64, tmp_path / "bad-pin")
    rows = json.loads((root / "selected-originals.json").read_bytes())
    rows[0]["publisher_split"] = "test"
    manifest = json.loads((root / "manifest.json").read_bytes())
    manifest["files"]["selected-originals.json"] = save(root / "selected-originals.json", rows)
    pin = save(root / "manifest.json", manifest)
    with pytest.raises(ValueError):
        module.prepare(root, pin, tmp_path / "test-input")


def test_duplicate_json_keys_and_path_escape_are_rejected(tmp_path):
    module = helper()
    with pytest.raises(ValueError):
        module.decode(b'{"execution_authorized":false,"execution_authorized":true}')
    with pytest.raises(ValueError):
        module.raw_file(tmp_path, "../private.json")
