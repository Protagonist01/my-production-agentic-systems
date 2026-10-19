"""Invented blind sampling and reviewer evidence; no real complaint fixture."""

import json
from datetime import UTC, datetime

import pytest
from cfpb_triage.review import (
    BlindItem,
    EvidenceSpan,
    Review,
    Selection,
    load_json,
    rank,
    review_summary,
    select_cases,
    text_digest,
    validate_reviews,
)
from pydantic import ValidationError


def population():
    return [
        Selection(
            case_id=text_digest(f"case-{split}-{g}-{edit}"),
            group_id=text_digest(f"group-{split}-{g}"),
            split=split,
        )
        for split in ("development", "regression", "holdout")
        for g in range(5)
        for edit in range(2)
    ]


def item():
    return BlindItem(case_id="a" * 64, narrative="Invented account access lost. Unicode é.")


def label(**changes):
    x = item()
    values = dict(
        case_id=x.case_id,
        narrative_sha256=text_digest(x.narrative),
        guideline_sha256="c" * 64,
        reviewer_id="invented-ai",
        reviewer_kind="ai",
        reviewed_at=datetime.now(UTC),
        risk="elevated",
        ambiguity="clear",
        rationale="Invented rationale.",
        evidence=(EvidenceSpan(start=9, end=28, text="account access lost"),),
    )
    values.update(changes)
    return Review(**values)


def test_fixed_sample_is_order_invariant_unique_by_group_and_preserves_splits():
    pop = population()
    selected = select_cases(pop)
    assert selected == select_cases(list(reversed(pop)))
    assert len(selected) == len({x.group_id for x in selected}) == 12
    for split in ("development", "regression", "holdout"):
        assert sum(x.split == split for x in selected) == 4
        eligible = {x.group_id for x in pop if x.split == split}
        expected = sorted(eligible, key=lambda g: (rank(g, domain="group"), g))[:4]
        assert {x.group_id for x in selected if x.split == split} == set(expected)


@pytest.mark.parametrize("kind", ["duplicate", "cross_split", "insufficient", "bool_count"])
def test_bad_populations_cannot_silently_change_denominators(kind):
    pop = population()
    kwargs = {}
    if kind == "duplicate":
        pop.append(pop[0])
    elif kind == "cross_split":
        pop.append(Selection(case_id="f" * 64, group_id=pop[0].group_id, split="holdout"))
    elif kind == "insufficient":
        pop = pop[:2]
    else:
        kwargs["per_split"] = True
    with pytest.raises(ValueError):
        select_cases(pop, **kwargs)


def test_blind_packet_schema_excludes_target_and_split_metadata():
    with pytest.raises(ValidationError):
        BlindItem(case_id="a" * 64, narrative="Invented", product="target")
    assert set(item().model_dump()) == {"schema_version", "case_id", "narrative"}


def test_complete_exact_evidence_and_single_reviewer_do_not_imply_agreement():
    validate_reviews((item(),), (label(),))
    summary = review_summary((item(),), (label(),))
    assert summary["human_reviews"] == 0 and summary["comparable_cases"] == 0
    assert summary["disagreement_cases"] is None
    assert summary["human_validation_established"] is False
    second = label(reviewer_id="invented-second", risk="routine", evidence=())
    summary = review_summary((item(),), (label(), second))
    assert summary["comparable_cases"] == summary["disagreement_cases"] == 1


@pytest.mark.parametrize("kind", ["missing", "duplicate", "extra", "digest", "span", "no_evidence"])
def test_invalid_reviews_fail_closed(kind):
    rows = (label(),)
    if kind == "missing":
        rows = ()
    elif kind == "duplicate":
        rows = (label(), label())
    elif kind == "extra":
        rows = (label(case_id="b" * 64),)
    elif kind == "digest":
        rows = (label(narrative_sha256="b" * 64),)
    elif kind == "span":
        rows = (label(evidence=(EvidenceSpan(start=9, end=29, text="wrong text"),)),)
    else:
        rows = (label(evidence=()),)
    with pytest.raises(ValueError):
        validate_reviews((item(),), rows)


def test_prediction_visibility_and_fake_human_gold_cannot_be_schema_defaults():
    with pytest.raises(ValidationError):
        label(predictions_seen=True)
    with pytest.raises(ValidationError):
        label(status="gold")


def test_pinned_json_rejects_byte_tamper_duplicate_fields_and_repo_output(tmp_path):
    p = tmp_path / "private.json"
    p.write_text('{"field":1,"field":2}', encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        load_json(p, text_digest(p.read_text(encoding="utf-8")))
    p.write_text(json.dumps({"invented": 1}), encoding="utf-8")
    with pytest.raises(ValueError, match="pin"):
        load_json(p, "a" * 64)
    (tmp_path / ".git").mkdir()
    with pytest.raises(ValueError, match="outside Git"):
        load_json(p, text_digest(p.read_text(encoding="utf-8")))


def test_evidence_end_cannot_exceed_narrative_even_when_python_slice_clamps():
    x = item()
    tail = EvidenceSpan(start=9, end=len(x.narrative) + 100, text=x.narrative[9:])
    with pytest.raises(ValueError, match="exact narrative span"):
        validate_reviews((x,), (label(evidence=(tail,)),))
