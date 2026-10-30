"""Reference integrity checks must not be mistaken for fresh model qualification."""

import json

import pytest
from olist_support.cohort_draft import build_draft
from olist_support.reference_package import audit, pinned
from test_olist_policy import invented_view


def packet():
    views = tuple(
        invented_view().model_copy(
            update={"order_id": f"invented-{i}", "source_manifest_sha256": "b" * 64}
        )
        for i in range(6)
    )
    cases, metadata = build_draft(views, "a" * 64)
    return cases.model_dump(mode="json"), metadata


def run(cases, metadata, required=frozenset({"eligible_refund", "required_review"}), inputs=None):
    if inputs is None:
        inputs = [
            {"case_id": e["input"]["case_id"], "text": e["input"]["request"]["message"]}
            for e in cases["entries"]
        ]
    return audit(
        json.dumps(cases).encode(),
        json.dumps(metadata).encode(),
        json.dumps(inputs).encode(),
        required_holdout_slices=required,
    )


def test_conditional_agreement_preserves_provenance_and_unmeasured_claims():
    cases, metadata = packet()
    before = json.dumps(cases)
    report = run(cases, metadata)
    assert report["structural_checks_passed"]
    assert report["structured_action_amount_agreement"] == 12
    assert report["source_groups"] == 6
    assert report["source_groups_by_split"]["holdout"] == 2
    assert report["label_provenance"] == {"ai": 12}
    for field in (
        "semantic_labels_validated",
        "reason_labels_validated",
        "family_independence_validated",
        "recovery_executed",
        "fresh_candidate_evaluated",
        "release_allowed",
    ):
        assert report[field] is False
    assert report["provider_calls"] == 0 and json.dumps(cases) == before
    assert report["text_only_projection_verified"] is True
    assert "invented-" not in json.dumps(report)


def test_seeded_amount_error_missing_slice_and_clock_error_cannot_pass():
    cases, metadata = packet()
    cases["entries"][0]["expected"]["amount_minor"] -= 1
    report = run(cases, metadata, frozenset({"not_covered"}))
    assert report["structured_action_amount_agreement"] == 11
    assert report["disagreements"] == {"action_or_amount_disagreement": 1}
    assert report["missing_declared_holdout_slices"] == ["not_covered"]
    assert report["structural_checks_passed"] is False
    cases["entries"][0]["input"]["order"]["as_of_source_local"] = "invalid-clock"
    assert run(cases, metadata)["oracle_errors"] == 1


@pytest.mark.parametrize("change", ["duplicate", "missing", "family", "source", "recovery"])
def test_malformed_or_leaking_membership_refused(change):
    cases, metadata = packet()
    if change == "duplicate":
        metadata[-1] = metadata[0]
    elif change == "missing":
        metadata.pop()
    elif change == "family":
        metadata[-1]["language_family"] = metadata[0]["language_family"]
    elif change == "source":
        cases["entries"][0]["input"]["order"]["source_manifest_sha256"] = "c" * 64
    else:
        metadata[0]["recovery_required"] = True
    with pytest.raises(ValueError):
        run(cases, metadata)


def test_exact_pin_and_explicit_requirements(tmp_path):
    from hashlib import sha256

    path = tmp_path / "invented.json"
    path.write_bytes(b"{}")
    assert pinned(path, sha256(b"{}").hexdigest()) == b"{}"
    path.write_bytes(b"{}\n")
    with pytest.raises(ValueError, match="pin"):
        pinned(path, sha256(b"{}").hexdigest())
    with pytest.raises(ValueError, match="requirements"):
        run(*packet(), required=frozenset())


@pytest.mark.parametrize("change", ["label", "changed_text", "duplicate"])
def test_provider_projection_refuses_label_leakage_and_wrong_text(change):
    cases, metadata = packet()
    inputs = [
        {"case_id": e["input"]["case_id"], "text": e["input"]["request"]["message"]}
        for e in cases["entries"]
    ]
    if change == "label":
        inputs[0]["expected_action"] = "propose_full_refund"
    elif change == "changed_text":
        inputs[0]["text"] += " substituted input"
    else:
        inputs[-1] = inputs[0]
    with pytest.raises(ValueError):
        run(cases, metadata, inputs=inputs)
