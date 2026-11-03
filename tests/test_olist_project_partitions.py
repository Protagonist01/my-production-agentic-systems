"""Draft group linkage and owner-selected project partition preparation, not gold labels."""

import json
import subprocess
import sys

import pytest
from agent_harness.release_contracts import pin
from olist_support.project_partitions import (
    ExposureTexts,
    partition,
    summarize_partitions,
    verify_partitions,
)
from olist_support.reference_audit import ReferenceAudit, audit_archive, digest
from test_olist_reference_audit import archive, exposure, record


def inputs(*, exposed=("Please refund my old order now",)):
    raw = archive(
        train=(
            record(1, "Please refund my old order now"),
            record(2, "Please refund my old order now please"),
        ),
        dev=(record(3, "Please refund my old order now please quickly"),),
        test=(
            record(
                4,
                "Password forgotten; please recover access",
                flow="account_access",
                subflow="recover_password",
            ),
            record(5, "Where is this shipment?", flow="shipping_issue", subflow="status"),
        ),
    )
    index = exposure(texts=exposed)
    texts = ExposureTexts(exposure_sha256=pin(index), texts=exposed)
    return audit_archive(raw, digest(raw), index), index, texts


def test_connected_exposure_excludes_exact_reworded_and_transitive_neighbors():
    audit, index, texts = inputs()
    value = partition(audit, index, texts, authorization_ref="invented owner preparation")
    by_id = {e.source_id: e for e in value.entries}
    assert len({by_id[str(i)].connected_group for i in (1, 2, 3)}) == 1
    assert all(by_id[str(i)].project_split == "excluded" for i in (1, 2, 3))
    assert all("connected_to_previous_exposure" in by_id[str(i)].exclusions for i in (1, 2, 3))
    assert by_id["4"].native_split == by_id["5"].native_split == "test"
    assert not value.labels_accepted and not value.frozen_for_provider


def test_native_cross_split_duplicates_stay_in_one_project_partition_with_native_metadata():
    raw = archive(
        train=(record(1, "Please refund this jacket"),),
        test=(record(2, "Please refund this jacket"),),
    )
    index = exposure(texts=("Some unrelated past exposure",))
    texts = ExposureTexts(exposure_sha256=pin(index), texts=("Some unrelated past exposure",))
    audit = audit_archive(raw, digest(raw), index)
    assert all("normalized_text_crosses_native_splits" in f.exclusions for f in audit.frames)
    value = partition(audit, index, texts, authorization_ref="invented approved interpretation")
    assert {e.native_split for e in value.entries} == {"train", "test"}
    assert len({e.project_split for e in value.entries}) == 1
    assert value.entries[0].project_split != "excluded"
    assert len({e.connected_group for e in value.entries}) == 1


def test_order_independent_group_ids_and_repeatable_assignments():
    audit, index, texts = inputs()
    first = partition(audit, index, texts, authorization_ref="invented")
    reversed_audit = audit.model_copy(update={"frames": tuple(reversed(audit.frames))})
    second = partition(reversed_audit, index, texts, authorization_ref="invented")
    assert {e.source_id: (e.connected_group, e.project_split) for e in first.entries} == {
        e.source_id: (e.connected_group, e.project_split) for e in second.entries
    }
    verify_partitions(first, audit, index, texts)
    summary = summarize_partitions(first)
    assert summary["native_splits_retained_as_metadata"] and not summary["independence_validated"]


def test_incomplete_exposure_and_forged_partition_assignment_refuse():
    audit, index, texts = inputs()
    with pytest.raises(ValueError, match="complete exposed-text"):
        partition(
            audit,
            index,
            ExposureTexts(exposure_sha256=pin(index), texts=("Other",)),
            authorization_ref="invented",
        )
    value = partition(audit, index, texts, authorization_ref="invented")
    entries = (value.entries[0].model_copy(update={"project_split": "holdout"}), *value.entries[1:])
    with pytest.raises(ValueError, match="recomputation"):
        verify_partitions(value.model_copy(update={"entries": entries}), audit, index, texts)
    with pytest.raises(ValueError, match="duplicate or foreign"):
        ReferenceAudit.model_validate_json(
            audit.model_copy(update={"frames": (audit.frames[0],) * 2}).canonical_json()
        )


def test_private_cli_binds_complete_project_inputs_and_refuses_partial_authority(tmp_path):
    raw = archive(test=(record(1, "Please refund this jacket"),))
    index = exposure(texts=("An unrelated previous message",))
    texts = ExposureTexts(exposure_sha256=pin(index), texts=("An unrelated previous message",))
    source, exposed, text_file = (
        tmp_path / name for name in ("source.gz", "index.json", "texts.json")
    )
    source.write_bytes(raw)
    exposed.write_text(index.canonical_json())
    text_file.write_text(texts.canonical_json())
    args = [
        sys.executable,
        "-m",
        "olist_support.reference_audit_cli",
        "--archive",
        str(source),
        "--archive-sha256",
        digest(raw),
        "--exposure",
        str(exposed),
        "--exposure-sha256",
        pin(index),
        "--exposed-texts",
        str(text_file),
        "--exposed-texts-sha256",
        pin(texts),
        "--output",
        str(tmp_path / "prepared"),
    ]
    refused = subprocess.run(args, text=True, capture_output=True, check=False)
    assert refused.returncode == 1 and not (tmp_path / "prepared").exists()
    result = subprocess.run(
        [*args, "--partition-preparation-ref", "invented preparation approval"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0 and "Please refund" not in result.stdout
    from olist_support.project_partitions import ProjectPartitions

    value = ProjectPartitions.model_validate_json(
        (tmp_path / "prepared" / "partitions.json").read_bytes()
    )
    verify_partitions(value, audit_archive(raw, digest(raw), index), index, texts)
    assert json.loads(result.stdout)["project_partitions"]["release_allowed"] is False
