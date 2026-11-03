"""Invented source records test projection/leakage controls, never natural-language accuracy."""

import gzip
import json
import subprocess
import sys

import pytest
from agent_harness.release_contracts import pin
from olist_support.reference_audit import (
    ExposureIndex,
    ReferenceFrame,
    audit_archive,
    digest,
    summarize,
    text_pin,
    verify_audit,
)


def record(identity, text, subflow="refund_initiate", flow="product_defect", annotation=None):
    return {
        "convo_id": identity,
        "scenario": {"flow": flow, "subflow": subflow, "secret": "HIDDEN"},
        "original": [["customer", "HIDDEN original"]],
        "delexed": [
            {
                "speaker": "agent",
                "text": "HIDDEN greeting",
                "targets": [subflow] * 5,
                "candidates": ["HIDDEN"],
            },
            {
                "speaker": "customer",
                "text": text,
                "targets": [annotation or subflow, None, None, [], -1],
                "candidates": ["HIDDEN"],
            },
            {
                "speaker": "agent",
                "text": "HIDDEN future",
                "targets": [subflow] * 5,
                "candidates": [],
            },
        ],
    }


def archive(train=(), dev=(), test=()):
    return gzip.compress(
        json.dumps({"train": list(train), "dev": list(dev), "test": list(test)}).encode()
    )


def exposure(ids=(), texts=()):
    return ExposureIndex(
        source_ids=ids,
        normalized_text_sha256=tuple(text_pin(t) for t in texts),
        provenance_ref="invented previous exposures",
    )


def test_only_first_customer_text_reaches_candidate_and_publisher_label_is_not_gold():
    raw = archive(test=(record(1, "Please refund my order."), record(2, "Hello!")))
    audit = audit_archive(raw, digest(raw), exposure())
    assert audit.frames[0].input.request == "Please refund my order."
    assert "HIDDEN" not in audit.frames[0].input.canonical_json()
    assert audit.frames[0].anchor.text == "refund" and not audit.frames[0].exclusions
    assert "no_literal_scope_anchor" in audit.frames[1].exclusions
    assert not audit.frames[0].semantic_gold_validated
    assert not audit.frames[0].amount_reference_established and not audit.release_allowed


def test_exposed_ids_normalized_text_and_cross_split_duplicates_are_excluded():
    raw = archive(
        train=(record(1, "Please REFUND my order."),),
        dev=(record(2, "please refund  my order."),),
        test=(record(3, "Refund a different item."),),
    )
    audit = audit_archive(raw, digest(raw), exposure(("1",), ("Refund a different item.",)))
    assert "previously_exposed_source" in audit.frames[0].exclusions
    assert "normalized_text_crosses_native_splits" in audit.frames[0].exclusions
    assert "normalized_text_crosses_native_splits" in audit.frames[1].exclusions
    assert "previously_exposed_normalized_text" in audit.frames[2].exclusions
    assert not summarize(audit)["literal_review_candidate_counts"]


def test_native_annotation_disagreement_conflicts_and_unmapped_goals_stay_visible():
    raw = archive(
        test=(
            record(1, "refund or replacement instead", annotation="return_size"),
            record(2, "help with a purchase", subflow="manage_create", flow="order_issue"),
        )
    )
    audit = audit_archive(raw, digest(raw), exposure())
    assert "turn_annotation_differs_from_scenario" in audit.frames[0].exclusions
    assert "visible_conflict_requires_applicability_review" in audit.frames[0].exclusions
    assert audit.frames[1].proposed_route is None


def test_exact_archive_pin_duplicate_identity_and_duplicate_json_fields_refuse():
    raw = archive(test=(record(1, "refund"),))
    with pytest.raises(ValueError, match="external pin"):
        audit_archive(raw, "a" * 64, exposure())
    duplicate = archive(train=(record(1, "refund"),), test=(record(1, "refund"),))
    with pytest.raises(ValueError, match="conversation identity"):
        audit_archive(duplicate, digest(duplicate), exposure())
    duplicate_json = gzip.compress(b'{"train":[],"train":[],"dev":[],"test":[]}')
    with pytest.raises(ValueError, match="duplicate source JSON"):
        audit_archive(duplicate_json, digest(duplicate_json), exposure())


def test_recomputation_rejects_mutated_anchor_input_or_exclusions():
    raw = archive(test=(record(1, "Please refund my order."),))
    audit = audit_archive(raw, digest(raw), exposure())
    verify_audit(audit, raw, digest(raw), exposure())
    altered = audit.frames[0].model_copy(update={"exclusions": ("invented",)})
    with pytest.raises(ValueError, match="recomputation"):
        verify_audit(audit.model_copy(update={"frames": (altered,)}), raw, digest(raw), exposure())
    altered_anchor = audit.frames[0].anchor.model_copy(update={"start": 0})
    altered_frame = audit.frames[0].model_copy(update={"anchor": altered_anchor})
    with pytest.raises(ValueError, match="anchor"):
        ReferenceFrame.model_validate_json(altered_frame.canonical_json())


def test_cli_is_network_denied_private_exclusive_and_does_not_echo_source_on_refusal(tmp_path):
    raw = archive(test=(record(1, "Private invented REFUND request"),))
    source = tmp_path / "source.gz"
    source.write_bytes(raw)
    exposed = exposure()
    index = tmp_path / "exposure.json"
    index.write_text(exposed.canonical_json())
    args = [
        sys.executable,
        "-m",
        "olist_support.reference_audit_cli",
        "--archive",
        str(source),
        "--archive-sha256",
        digest(raw),
        "--exposure",
        str(index),
        "--exposure-sha256",
        pin(exposed),
        "--output",
        str(tmp_path / "output"),
    ]
    success = subprocess.run(args, text=True, capture_output=True, check=False)
    assert success.returncode == 0 and "Private invented" not in success.stdout
    refused = subprocess.run(args, text=True, capture_output=True, check=False)
    assert refused.returncode == 1 and "Private invented" not in refused.stderr
    assert json.loads((tmp_path / "output" / "pins.json").read_text())["provider_calls"] == 0
