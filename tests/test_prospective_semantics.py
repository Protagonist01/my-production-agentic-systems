"""Invented reference/exposure inventories test prospective selection, not semantic truth."""

from collections import Counter
from datetime import UTC, datetime

import pytest
from agent_harness.release_contracts import pin, sha256
from pydantic import ValidationError
from revenue_integrity.prospective_semantics import (
    CohortSelection,
    ExposureInventory,
    ExposureRecord,
    ProspectiveCohort,
    prepare_prospective,
)
from revenue_integrity.release_evaluation import ExtractionCase
from revenue_integrity.semantic_pilot import model_request
from revenue_integrity.source_contracts import ExtractionInput, PublishedTarget, Span


def samples(count=60):
    return tuple(
        ExtractionCase(
            input=ExtractionInput(
                case_id=sha256(str(i).encode()),
                context=f"Annual invented clause {i}.",
                question=f"Term in invented agreement {i}?",
            ),
            target=PublishedTarget(
                case_id=sha256(str(i).encode()),
                category=f"category-{i // 2}",
                answers=() if i % 2 else (Span(start=0, text="Annual"),),
                impossible=bool(i % 2),
                family_id=sha256(f"family-{i}".encode()),
                split="development",
            ),
        )
        for i in range(count)
    )


def exposure(records=None):
    return ExposureInventory(
        source_manifest_sha256="a" * 64,
        evidence_sha256=("b" * 64,),
        records=records
        or (ExposureRecord(family_id="c" * 64, context_sha256=None, request_sha256=None),),
    )


def prepare(cases=None, exposures=None, **changes):
    return prepare_prospective(
        samples() if cases is None else cases,
        (exposure(),) if exposures is None else exposures,
        **(
            dict(
                source_manifest_sha256="a" * 64,
                evaluator_source_sha256="d" * 64,
                frozen_at=datetime(2026, 10, 27, tzinfo=UTC),
            )
            | changes
        ),
    )


def test_balanced_fixed_schedule_references_and_request_hashes_are_bound():
    source = samples()
    before = tuple(pin(c) for c in source)
    cohort = prepare(source)
    assert len(cohort.cases) == 12 and len(cohort.schedule) == 24
    assert Counter(c.expected_accept for c in cohort.dataset.cases) == {True: 6, False: 6}
    assert Counter(c.split for c in cohort.dataset.cases) == {"calibration": 4, "holdout": 8}
    assert len({c.target.family_id for c in cohort.cases}) == 12
    assert len({sha256(c.input.context.encode()) for c in cohort.cases}) == 12
    assert max(Counter(c.target.category for c in cohort.cases).values()) <= 2
    requests = {c.input.case_id: pin(model_request(c.input)) for c in cohort.cases}
    assert all(t.request_sha256 == requests[t.case_id] for t in cohort.schedule)
    assert all(
        c.reference_sha256
        == pin(next(x.target for x in cohort.cases if x.input.case_id == c.case_id))
        for c in cohort.dataset.cases
    )
    assert tuple(pin(c) for c in source) == before
    assert not cohort.dispatch_allowed and not cohort.release_allowed
    assert cohort.selection_sha256 == pin(CohortSelection())


@pytest.mark.parametrize("kind", ["family", "context", "request"])
def test_each_exposure_identity_excludes_renamed_case_or_family(kind):
    source = samples()
    base = prepare(source)
    chosen = base.cases[0]
    record = ExposureRecord(
        family_id=chosen.target.family_id if kind == "family" else "f" * 64,
        context_sha256=sha256(chosen.input.context.encode()) if kind == "context" else None,
        request_sha256=pin(model_request(chosen.input)) if kind == "request" else None,
    )
    result = prepare(source, (exposure((record,)),))
    assert chosen.input.case_id not in {c.input.case_id for c in result.cases}
    assert len(result.cases) == 12


def test_duplicate_contexts_with_distinct_families_do_not_inflate_new_groups():
    source = list(samples())
    first = prepare(tuple(source)).cases[0]
    second = next(c for c in source if c.input.case_id != first.input.case_id)
    source[source.index(second)] = second.model_copy(
        update={"input": second.input.model_copy(update={"context": first.input.context})}
    )
    result = prepare(tuple(source))
    assert len({c.input.context for c in result.cases}) == 12


def test_source_binding_duplicate_exposure_and_missing_exclusion_inventory_refuse():
    with pytest.raises(ValueError, match="another source"):
        prepare(exposures=(exposure().model_copy(update={"source_manifest_sha256": "e" * 64}),))
    for inventories in ((), (exposure(), exposure())):
        with pytest.raises(ValueError, match="unique exposure"):
            prepare(exposures=inventories)
    with pytest.raises(ValidationError):
        ExposureInventory.model_validate_json(
            exposure().model_copy(update={"evidence_sha256": ()}).canonical_json()
        )


def test_invalid_population_does_not_silently_relabel_or_relax_constraints():
    source = samples()
    with pytest.raises(ValueError, match="duplicate source"):
        prepare((*source, source[0]))
    bad = source[0].model_copy(
        update={
            "target": source[0].target.model_copy(
                update={"answers": (Span(start=0, text="absent"),)}
            )
        }
    )
    with pytest.raises(ValueError, match="span differs"):
        prepare((bad, *source[1:]))
    with pytest.raises(ValueError, match="insufficient"):
        prepare(source, selection=CohortSelection(max_context_chars=1))
    holdout = tuple(
        c.model_copy(update={"target": c.target.model_copy(update={"split": "holdout"})})
        for c in source
    )
    with pytest.raises(ValueError, match="insufficient"):
        prepare(holdout)
    with pytest.raises(ValidationError):
        ProspectiveCohort.model_validate_json(
            prepare().model_copy(update={"dispatch_allowed": True}).canonical_json()
        )


def test_all_prior_families_excluded_cannot_reset_into_a_fresh_population():
    source = samples()
    records = tuple(
        ExposureRecord(family_id=c.target.family_id, context_sha256=None, request_sha256=None)
        for c in source
    )
    with pytest.raises(ValueError, match="insufficient"):
        prepare(source, (exposure(records),))


@pytest.mark.parametrize("change", ["schedule", "label", "request", "source_family"])
def test_frozen_bundle_revalidation_detects_substitution(change):
    cohort = prepare()
    if change == "schedule":
        forged = cohort.model_copy(update={"schedule": cohort.schedule[:-1]})
    elif change == "label":
        row = cohort.dataset.cases[0]
        dataset = cohort.dataset.model_copy(
            update={
                "cases": (
                    row.model_copy(update={"expected_accept": not row.expected_accept}),
                    *cohort.dataset.cases[1:],
                )
            }
        )
        forged = cohort.model_copy(update={"dataset": dataset})
    elif change == "request":
        row = cohort.schedule[0].model_copy(update={"request_sha256": "f" * 64})
        forged = cohort.model_copy(update={"schedule": (row, *cohort.schedule[1:])})
    else:
        row = cohort.cases[0].model_copy(
            update={
                "target": cohort.cases[0].target.model_copy(
                    update={"family_id": cohort.cases[1].target.family_id}
                )
            }
        )
        forged = cohort.model_copy(update={"cases": (row, *cohort.cases[1:])})
    with pytest.raises(ValidationError):
        ProspectiveCohort.model_validate_json(forged.canonical_json())
