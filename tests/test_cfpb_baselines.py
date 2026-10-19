"""Hand-counted denominators, fit isolation and deliberately weak rules."""

import json
from datetime import UTC, datetime

import pytest
from cfpb_triage.baselines import (
    ClassificationCounts,
    consumer_report,
    majority,
    pilot_report,
    risk_rules,
)
from cfpb_triage.review import BlindItem, Review, Selection, make_packet, text_digest
from cfpb_triage.source_io import digest_file
from test_cfpb_source import build, invented_row


def pilot():
    inputs, selections, reviews = [], [], []
    for i, (split, risk) in enumerate(
        (
            ("development", "routine"),
            ("development", "routine"),
            ("regression", "uncertain"),
            ("holdout", "elevated"),
        )
    ):
        narrative = "Invented ordinary billing disagreement. " * 3
        cid = text_digest(f"case-{i}")
        inputs.append(BlindItem(case_id=cid, narrative=narrative))
        selections.append(Selection(case_id=cid, group_id=text_digest(f"group-{i}"), split=split))
        from cfpb_triage.review import EvidenceSpan

        reviews.append(
            Review(
                case_id=cid,
                narrative_sha256=text_digest(narrative),
                guideline_sha256="b" * 64,
                reviewer_id="invented",
                reviewer_kind="ai",
                reviewed_at=datetime.now(UTC),
                risk=risk,
                ambiguity="clear",
                evidence=(EvidenceSpan(start=0, end=8, text="Invented"),),
                rationale="Invented judgment.",
            )
        )
    return tuple(inputs), tuple(selections), tuple(reviews)


def test_hand_counted_macro_f1_includes_predicted_only_class_and_null_empty():
    counts = ClassificationCounts()
    assert counts.report()["accuracy"] is None
    counts.add("a", "a")
    counts.add("a", "b")
    counts.add("c", "b")
    report = counts.report()
    assert report["denominator"] == 3 and report["correct"] == 1
    assert report["accuracy"] == pytest.approx(1 / 3)
    assert report["macro_f1"] == pytest.approx(2 / 9)
    b = next(x for x in report["classes"] if x["label"] == "b")
    assert b["support"] == 0 and b["recall"] is None and b["f1"] == 0


def test_majority_fits_development_only_and_zero_positive_support_is_null():
    items, selections, reviews = pilot()
    result = pilot_report(items, selections, reviews, reviewer_id="invented")
    assert result["fit_cases"] == 2 and result["majority_risk"] == "routine"
    assert result["splits"]["regression"]["majority"]["risk"]["denominator"] == 1
    assert result["splits"]["holdout"]["majority"]["risk"]["accuracy"] == 0
    assert result["splits"]["regression"]["majority"]["provisional_elevated_review_recall"] is None
    assert result["splits"]["holdout"]["majority"]["provisional_elevated_review_recall"] == 0
    changed = tuple(
        r.model_copy(update={"risk": "elevated"}) if s.split != "development" else r
        for r, s in zip(reviews, selections, strict=True)
    )
    assert (
        pilot_report(items, selections, changed, reviewer_id="invented")["majority_risk"]
        == "routine"
    )
    assert result["review"]["disagreement_cases"] is None


def test_missing_review_split_crossing_and_empty_fit_fail_before_scoring():
    items, selections, reviews = pilot()
    with pytest.raises(ValueError):
        pilot_report(items, selections[:-1], reviews, reviewer_id="invented")
    changed = list(selections)
    changed[-1] = changed[-1].model_copy(update={"group_id": changed[0].group_id})
    with pytest.raises(ValueError, match="crosses"):
        pilot_report(items, tuple(changed), reviews, reviewer_id="invented")
    with pytest.raises(ValueError, match="development"):
        majority(__import__("collections").Counter())


def test_rules_have_documented_negation_and_keyword_false_positive_limits():
    # This deliberately remains a false positive: no tuning on observed pilot failures.
    text = "Invented narrative: no fraud occurred, no stolen funds; ordinary fee question. " * 2
    assert risk_rules(text)[0] == "elevated"
    assert risk_rules("Invented too-short input.") == ("uncertain", "ambiguous")


def test_complete_invented_source_packet_pin_and_consumer_reference_denominators(tmp_path):
    rows = [
        invented_row(1, "2023-09-01", "Invented development fee inquiry."),
        invented_row(2, "2024-01-01", "Invented regression mortgage problem."),
        invented_row(3, "2024-03-01", "Invented holdout student loan problem."),
    ]
    rows[1]["Product"] = "Mortgage"
    rows[2]["Product"] = "Student loan"
    prepared, _ = build(tmp_path, rows)
    pin = digest_file(prepared / "manifest.json")
    packet = tmp_path / "packet"
    packet_pin = make_packet(prepared, pin, packet, per_split=1)
    assert packet_pin == digest_file(packet / "blind.json")
    hidden = json.loads((packet / "selection.json").read_text(encoding="utf-8"))
    assert hidden["packet_sha256"] == packet_pin
    assert "Product" not in (packet / "blind.json").read_text(encoding="utf-8")
    result = consumer_report(prepared, pin)
    assert result["fit_rows"] == 1 and result["prepared_rows"] == 3
    for split in ("development", "regression", "holdout"):
        assert result["splits"][split]["majority"]["product"]["denominator"] == 1
    assert result["splits"]["holdout"]["majority"]["product"]["accuracy"] == 0
    assert "not independently reviewed truth" in result["target_status"]
