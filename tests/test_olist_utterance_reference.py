"""Invented source rows verify provenance/refusal mechanics, never language accuracy."""

import csv
import io
import json
import subprocess
import sys

import pytest
from agent_harness.contracts import AgentInput
from agent_harness.release_contracts import pin, sha256
from olist_support.reference_audit import ExposureIndex, text_pin
from olist_support.utterance_reference import (
    COLUMNS,
    UtteranceAudit,
    UtteranceFrame,
    audit_csv,
    summary,
    verify,
)


def payload(*rows):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(COLUMNS)
    writer.writerows(rows)
    return stream.getvalue().encode()


def row(text="Please refund this order", intent="get_refund", category="REFUND"):
    return ("invented-source-flag", text, category, intent, "HIDDEN native response")


def exposure(*texts):
    return ExposureIndex(
        source_ids=(),
        normalized_text_sha256=tuple(text_pin(t) for t in texts),
        provenance_ref="invented exposure inventory",
    )


def audit(raw, index=None):
    return audit_csv(raw, sha256(raw), "a" * 40, index or exposure())


def test_exact_instruction_only_and_native_annotations_remain_proposals():
    raw = payload(row(), row("Where is my order", "track_order", "ORDER"))
    value = audit(raw)
    assert [f.proposed_route for f in value.frames] == ["refund", "status"]
    assert (
        value.frames[0].input.model_dump()
        == AgentInput(request="Please refund this order").model_dump()
    )
    assert "HIDDEN" not in value.canonical_json()
    assert value.frames[0].native_flags == "invented-source-flag"
    assert value.frames[0].annotation_unit == "individual_instruction"
    assert not value.benchmark_source_accepted and not value.release_allowed
    assert not value.frames[0].mapping_accepted and not value.frames[0].semantic_gold_validated
    assert value.frames[0].full_service_reference_blockers == (
        "requested_amount_reference_unestablished",
    )


def test_placeholder_values_are_not_substituted_or_converted_to_null_amount_references():
    raw = payload(
        row("Refund {{Refund Amount}} {{Currency Symbol}}"), row("Help", "other", "OTHER")
    )
    value = audit(raw)
    frame = value.frames[0]
    with pytest.raises(ValueError, match="projection"):
        UtteranceFrame.model_validate_json(
            frame.model_copy(update={"full_service_reference_blockers": ()}).canonical_json()
        )
    assert frame.unresolved_slots == ("{{Refund Amount}}", "{{Currency Symbol}}")
    assert frame.input.request == "Refund {{Refund Amount}} {{Currency Symbol}}"
    assert frame.amount_reference_status == "not_supplied_or_validated"
    assert "requested_minor" not in frame.model_dump()
    assert "unresolved_source_slots" in frame.full_service_reference_blockers
    assert value.frames[1].proposed_route is None
    report = summary(value)
    assert report["slot_free_unexcluded_proposal_counts"] == {}
    assert report["unexcluded_intent_proposal_counts"] == {"refund": 1}
    assert (
        report["full_service_reference_blockers"]["requested_amount_reference_unestablished"] == 2
    )
    assert not report["amount_reference_established"] and not report["frozen_for_provider"]


def test_duplicate_text_label_conflicts_exposure_and_category_disagreement_are_excluded():
    raw = payload(
        row(),
        row("  PLEASE refund this order  ", "track_refund", "REFUND"),
        row("Forgot my password", "recover_password", "WRONG"),
    )
    value = audit(raw, exposure("please REFUND this order"))
    assert len({f.source_ordinal for f in value.frames}) == 3
    for frame in value.frames[:2]:
        assert "conflicting_native_text_labels" in frame.exclusions
        assert "previously_exposed_normalized_text" in frame.exclusions
    assert "native_category_differs_from_mapping" in value.frames[2].exclusions
    assert summary(value)["slot_free_unexcluded_proposal_counts"] == {}


def test_wrong_pin_header_empty_fields_extra_columns_and_oversized_instruction_refuse():
    raw = payload(row())
    with pytest.raises(ValueError, match="external pin"):
        audit_csv(raw, "b" * 64, "a" * 40, exposure())
    for malformed in (
        raw.replace(b"flags,instruction", b"flags,flags"),
        payload(row("")),
        payload((*row(), "extra")),
        payload(row("x" * 8193)),
        payload(),
    ):
        with pytest.raises(ValueError):
            audit(malformed)


def test_recompute_rejects_changed_input_exclusions_native_hash_and_exposure():
    raw = payload(row())
    value = audit(raw)
    verify(value, raw, sha256(raw), exposure())
    for change in (
        {"exclusions": ("forged",)},
        {"source_row_sha256": "b" * 64},
        {"input": AgentInput(request="Different text")},
    ):
        altered = value.frames[0].model_copy(update=change)
        with pytest.raises(ValueError, match="recomputation"):
            verify(value.model_copy(update={"frames": (altered,)}), raw, sha256(raw), exposure())
    with pytest.raises(ValueError, match="recomputation"):
        verify(value, raw, sha256(raw), exposure("Please refund this order"))


def test_forged_authority_source_bindings_and_hidden_observations_refuse():
    value = audit(payload(row()))
    frame = value.frames[0]
    for key in (
        "mapping_accepted",
        "semantic_gold_validated",
        "independence_validated",
        "frozen_for_provider",
        "release_allowed",
    ):
        with pytest.raises(ValueError):
            UtteranceFrame.model_validate_json(
                frame.model_copy(update={key: True}).canonical_json()
            )
    for change in (
        {"source_ordinal": 2},
        {"source_revision": "b" * 40},
        {"source_csv_sha256": "b" * 64},
    ):
        with pytest.raises(ValueError, match="foreign instruction"):
            UtteranceAudit.model_validate_json(
                value.model_copy(
                    update={"frames": (frame.model_copy(update=change),)}
                ).canonical_json()
            )
    with pytest.raises(ValueError, match="projection"):
        UtteranceFrame.model_validate_json(
            frame.model_copy(
                update={
                    "input": AgentInput(
                        request=frame.input.request,
                        observations=({"reference": "invented", "text": "Hidden native label"},),
                    )
                }
            ).canonical_json()
        )


def test_offline_cli_private_outputs_exclusive_and_refusals_do_not_echo_source(tmp_path):
    raw = payload(row("Private invented refund instruction"))
    source, index = tmp_path / "source.csv", tmp_path / "exposure.json"
    source.write_bytes(raw)
    index.write_text(exposure().canonical_json())
    output = tmp_path / "new-private-output"
    args = [
        sys.executable,
        "-m",
        "olist_support.utterance_reference",
        "--source",
        str(source),
        "--source-sha256",
        sha256(raw),
        "--source-revision",
        "a" * 40,
        "--exposure",
        str(index),
        "--exposure-sha256",
        pin(exposure()),
        "--output",
        str(output),
    ]
    completed = subprocess.run(args, text=True, capture_output=True, check=False)
    assert completed.returncode == 0 and "Private invented" not in completed.stdout
    assert json.loads(completed.stdout)["provider_calls"] == 0
    value = UtteranceAudit.model_validate_json((output / "audit.json").read_bytes())
    verify(value, raw, sha256(raw), exposure())
    refused = subprocess.run(args, text=True, capture_output=True, check=False)
    assert refused.returncode == 1 and "Private invented" not in refused.stderr
    (tmp_path / ".git").mkdir()
    args[-1] = str(tmp_path / "unsafe-repository-output")
    refused = subprocess.run(args, text=True, capture_output=True, check=False)
    assert refused.returncode == 1 and not (tmp_path / "unsafe-repository-output").exists()
