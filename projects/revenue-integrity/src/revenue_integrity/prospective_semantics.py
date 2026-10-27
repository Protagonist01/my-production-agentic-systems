"""Prepare disjoint future semantic trials; no provider dispatch or release authorization."""

from collections import Counter
from typing import Annotated, Literal, Self

from agent_harness.contracts import Contract, NonEmpty
from agent_harness.evaluator_qualification import QualificationCase, QualificationDataset
from agent_harness.release_contracts import Sha256, pin, sha256
from pydantic import AwareDatetime, Field, model_validator

from revenue_integrity.release_evaluation import ExtractionCase
from revenue_integrity.semantic_pilot import model_request


class ExposureRecord(Contract):
    family_id: Sha256
    context_sha256: Sha256 | None
    request_sha256: Sha256 | None


class ExposureInventory(Contract):
    version: Literal["semantic-exposure-inventory-v1"] = "semantic-exposure-inventory-v1"
    source_manifest_sha256: Sha256
    # Pointers to inspected source evidence; a pointer alone does not authenticate exposure.
    evidence_sha256: Annotated[tuple[Sha256, ...], Field(min_length=1)]
    records: Annotated[tuple[ExposureRecord, ...], Field(min_length=1)]


class ProspectiveTrial(Contract):
    case_id: Sha256
    trial_id: Literal["trial-1", "trial-2"]
    request_sha256: Sha256


class ProspectiveCohort(Contract):
    version: Literal["prospective-answerability-v2-preparation"] = (
        "prospective-answerability-v2-preparation"
    )
    source_manifest_sha256: Sha256
    exposure_inventory_sha256s: Annotated[tuple[Sha256, ...], Field(min_length=1)]
    evaluator_source_sha256: Sha256
    selection_sha256: Sha256
    parser: Literal["semantic-answerability-parser-v2"] = "semantic-answerability-parser-v2"
    # Contains private evaluator references; never pass the bundle to a provider.
    cases: tuple[ExtractionCase, ...]
    dataset: QualificationDataset
    schedule: tuple[ProspectiveTrial, ...]
    proposed_max_attempts: Literal[24] = 24
    dispatch_allowed: Literal[False] = False
    release_allowed: Literal[False] = False

    @model_validator(mode="after")
    def bound(self) -> Self:
        if len(self.cases) != 12 or len({c.input.case_id for c in self.cases}) != 12:
            raise ValueError("prospective cohort requires twelve unique cases")
        if (
            len({c.target.family_id for c in self.cases}) != 12
            or len({sha256(c.input.context.encode()) for c in self.cases}) != 12
        ):
            raise ValueError("prospective source families/contexts repeat")
        references = {c.case_id: c for c in self.dataset.cases}
        expected: set[tuple[str, str, str]] = set()
        for case in self.cases:
            value, target = case.input, case.target
            reference = references.get(value.case_id)
            if (
                target.case_id != value.case_id
                or target.split != "development"
                or (
                    reference is None
                    or reference.reference_sha256 != pin(target)
                    or reference.input_sha256 != pin(model_request(value))
                    or reference.expected_accept != (not target.impossible)
                    or set(reference.independence_keys)
                    != {target.family_id, sha256(value.context.encode())}
                )
            ):
                raise ValueError("prospective reference/input differs")
            for trial in ("trial-1", "trial-2"):
                expected.add((value.case_id, trial, reference.input_sha256))
        actual = {(t.case_id, t.trial_id, t.request_sha256) for t in self.schedule}
        if len(self.schedule) != 24 or actual != expected or len(references) != 12:
            raise ValueError("prospective schedule differs")
        if sum(c.expected_accept for c in self.dataset.cases) != 6 or Counter(
            (c.split, c.expected_accept) for c in self.dataset.cases
        ) != {
            ("calibration", True): 2,
            ("calibration", False): 2,
            ("holdout", True): 4,
            ("holdout", False): 4,
        }:
            raise ValueError("prospective class/split balance differs")
        return self


class CohortSelection(Contract):
    max_context_chars: Annotated[int, Field(gt=0, le=20000)] = 12000
    max_cases_per_category: Annotated[int, Field(gt=0, le=12)] = 2
    excluded_categories: tuple[NonEmpty, ...] = (
        "Document Name",
        "Parties",
        "Agreement Date",
        "Effective Date",
    )

    @model_validator(mode="after")
    def unique(self) -> Self:
        if len(set(self.excluded_categories)) != len(self.excluded_categories):
            raise ValueError("duplicate excluded category")
        return self


def prepare_prospective(
    cases: tuple[ExtractionCase, ...],
    exposures: tuple[ExposureInventory, ...],
    *,
    source_manifest_sha256: str,
    evaluator_source_sha256: str,
    frozen_at: AwareDatetime,
    selection: CohortSelection | None = None,
) -> ProspectiveCohort:
    """Select six answerable/six no-answer cases, unique by family and original context.

    Trust boundary: callers verify source/population and exposure evidence bytes. This pure
    function checks supplied contracts/disjointness, not semantic near-duplicates or honesty.
    """
    selection = CohortSelection.model_validate_json(
        (selection or CohortSelection()).canonical_json()
    )
    exposures = tuple(ExposureInventory.model_validate_json(e.canonical_json()) for e in exposures)
    if not exposures or len({pin(e) for e in exposures}) != len(exposures):
        raise ValueError("nonempty unique exposure inventories required")
    if any(e.source_manifest_sha256 != source_manifest_sha256 for e in exposures):
        raise ValueError("exposure inventory belongs to another source")
    prior = tuple(record for e in exposures for record in e.records)
    families = {r.family_id for r in prior}
    contexts = {r.context_sha256 for r in prior if r.context_sha256 is not None}
    requests = {r.request_sha256 for r in prior if r.request_sha256 is not None}
    candidates = tuple(ExtractionCase.model_validate_json(c.canonical_json()) for c in cases)
    if len({c.input.case_id for c in candidates}) != len(candidates):
        raise ValueError("duplicate source case")
    counts = {True: 0, False: 0}
    categories: Counter[str] = Counter()
    chosen: list[ExtractionCase] = []
    references: list[QualificationCase] = []
    for case in sorted(candidates, key=lambda c: c.input.case_id):
        value, target = case.input, case.target
        if value.case_id != target.case_id:
            raise ValueError("publisher reference identity differs")
        if any(value.context[s.start : s.start + len(s.text)] != s.text for s in target.answers):
            raise ValueError("publisher reference span differs")
        context_pin = sha256(value.context.encode("utf-8"))
        if (
            target.split != "development"
            or target.family_id in families
            or context_pin in contexts
            or len(value.context) > selection.max_context_chars
            or target.category in selection.excluded_categories
            or categories[target.category] >= selection.max_cases_per_category
            or counts[not target.impossible] >= 6
        ):
            continue
        request_pin = pin(model_request(value))
        if request_pin in requests:
            continue
        accepted = not target.impossible
        counts[accepted] += 1
        categories[target.category] += 1
        families.add(target.family_id)
        contexts.add(context_pin)
        requests.add(request_pin)
        chosen.append(case)
        references.append(
            QualificationCase(
                case_id=value.case_id,
                input_sha256=request_pin,
                independence_keys=(target.family_id, context_pin),
                split="calibration" if counts[accepted] <= 2 else "holdout",
                slices=("answerability",),
                expected_accept=accepted,
                reference_sha256=pin(target),
                reference_kind="published_reference",
                applicability_ref="original-publisher-answerability-only-not-legal-or-billing-truth",
                exposure="public_reference",
            )
        )
    if counts != {True: 6, False: 6}:
        raise ValueError("insufficient disjoint balanced references under fixed selection policy")
    return ProspectiveCohort(
        source_manifest_sha256=source_manifest_sha256,
        exposure_inventory_sha256s=tuple(pin(e) for e in exposures),
        evaluator_source_sha256=evaluator_source_sha256,
        selection_sha256=pin(selection),
        cases=tuple(chosen),
        dataset=QualificationDataset(
            version="prospective-answerability-v2",
            agent="revenue",
            field="answerability",
            frozen_at=frozen_at,
            cases=tuple(references),
        ),
        schedule=tuple(
            ProspectiveTrial(
                case_id=c.case_id,
                trial_id=trial,
                request_sha256=c.input_sha256,
            )
            for trial in ("trial-1", "trial-2")
            for c in references
        ),
    )
