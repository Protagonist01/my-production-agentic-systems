"""Invented publisher DTOs verify aggregation; no real legal/clinical judgment."""

import pytest
from agent_harness.release_contracts import sha256
from revenue_integrity.reference_applicability import reference_coverage
from revenue_integrity.source_contracts import PublishedTarget, Span


def target(index, impossible=False, split="development", family=None, category="invented"):
    return PublishedTarget(
        case_id=sha256(str(index).encode()),
        category=category,
        answers=() if impossible else (Span(start=0, text="invented"),),
        impossible=impossible,
        family_id=sha256(str(family or index).encode()),
        split=split,
    )


def test_reference_applicability_keeps_answerability_families_and_split_denominators():
    values = (
        target(1),
        target(2, impossible=True, family=1),
        target(3, split="holdout"),
        target(4, impossible=True, split="holdout"),
    )
    report = reference_coverage(values, source_manifest_sha256="a" * 64)
    assert report["totals"] == {
        "questions": 4,
        "answerable": 2,
        "no_answer": 2,
        "spans": 2,
        "families": 3,
        "answerable_families": 2,
        "no_answer_families": 2,
    }
    assert report["categories"]["invented"]["holdout"]["questions"] == 2
    assert "sim_invoice_delta" in report["not_established"]
    assert not report["source_verification_performed_by_aggregator"]
    assert not report["release_allowed"]


def test_reference_population_duplicates_leakage_and_bad_digest_refuse():
    with pytest.raises(ValueError, match="duplicate"):
        reference_coverage((target(1), target(1)), source_manifest_sha256="a" * 64)
    with pytest.raises(ValueError, match="crosses splits"):
        reference_coverage(
            (target(1), target(2, split="holdout", family=1)), source_manifest_sha256="a" * 64
        )
    with pytest.raises(ValueError, match="empty"):
        reference_coverage((), source_manifest_sha256="a" * 64)
    with pytest.raises(ValueError, match="digest"):
        reference_coverage((target(1),), source_manifest_sha256="not-a-pin")
