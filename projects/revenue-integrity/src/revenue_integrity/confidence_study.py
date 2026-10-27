"""Frozen 148-family reference-relative study, never a production release decision."""

from collections import Counter
from typing import Literal, Self

from agent_harness.contracts import Contract
from agent_harness.evaluator_qualification import QualificationCase, QualificationDataset
from agent_harness.release_contracts import Sha256, pin, sha256
from pydantic import AwareDatetime, model_validator

from revenue_integrity.prospective_semantics import ExposureInventory, ProspectiveTrial
from revenue_integrity.release_evaluation import ExtractionCase
from revenue_integrity.semantic_pilot import model_request

EXCLUDED = ("Document Name", "Parties", "Agreement Date", "Effective Date")


class ConfidenceCohort(Contract):
    version: Literal["cuad-confidence-study-v1"] = "cuad-confidence-study-v1"
    source_manifest_sha256: Sha256
    exposure_inventory_sha256s: tuple[Sha256, ...]
    evaluator_source_sha256: Sha256
    frozen_at: AwareDatetime
    cases: tuple[ExtractionCase, ...]
    dataset: QualificationDataset
    schedule: tuple[ProspectiveTrial, ...]
    max_context_chars: Literal[50000] = 50000
    max_per_category: Literal[16] = 16
    maximum_attempts: Literal[296] = 296
    release_allowed: Literal[False] = False

    @model_validator(mode="after")
    def bound(self) -> Self:
        if len(self.cases) != 148 or len(self.dataset.cases) != 148:
            raise ValueError("confidence cohort requires 148 references")
        if (
            len(set(self.exposure_inventory_sha256s)) != len(self.exposure_inventory_sha256s)
            or not self.exposure_inventory_sha256s
        ):
            raise ValueError("confidence cohort requires unique exposure inventories")
        families: set[str] = set()
        contexts: set[str] = set()
        categories: Counter[str] = Counter()
        references = {c.case_id: c for c in self.dataset.cases}
        expected = set()
        for case in self.cases:
            value, target = case.input, case.target
            context = sha256(value.context.encode())
            ref = references.get(value.case_id)
            if (
                value.case_id != target.case_id
                or target.split != "development"
                or target.family_id in families
                or context in contexts
                or target.category in EXCLUDED
                or len(value.context) > self.max_context_chars
                or any(
                    value.context[a.start : a.start + len(a.text)] != a.text for a in target.answers
                )
                or ref is None
                or ref.input_sha256 != pin(model_request(value, max_context_chars=50000))
                or ref.reference_sha256 != pin(target)
                or ref.expected_accept != (not target.impossible)
                or set(ref.independence_keys) != {target.family_id, context}
                or ref.slices != ("answerability",)
                or ref.reference_kind != "published_reference"
                or ref.exposure != "public_reference"
            ):
                raise ValueError("confidence source/reference/independence binding differs")
            families.add(target.family_id)
            contexts.add(context)
            categories[target.category] += 1
            for trial in ("trial-1", "trial-2"):
                expected.add((value.case_id, trial, ref.input_sha256))
        if max(categories.values()) > 16 or Counter(
            (r.split, r.expected_accept) for r in references.values()
        ) != {
            ("calibration", True): 2,
            ("calibration", False): 2,
            ("holdout", True): 72,
            ("holdout", False): 72,
        }:
            raise ValueError("confidence category/class/split balance differs")
        if (
            len(self.schedule) != 296
            or {(r.case_id, r.trial_id, r.request_sha256) for r in self.schedule} != expected
        ):
            raise ValueError("confidence schedule differs")
        return self


def prepare_confidence(
    cases: tuple[ExtractionCase, ...],
    exposures: tuple[ExposureInventory, ...],
    *,
    source_manifest_sha256: str,
    evaluator_source_sha256: str,
    frozen_at: AwareDatetime,
) -> ConfidenceCohort:
    """Deterministic class/category balancing, one case per known family/context.

    Select answerable first because that subset is smaller. Among eligible cases prefer
    the currently least-used category, then case hash. Source/exposure provenance and
    inferred family quality remain caller-verified inputs. No outcome-based resampling.
    """
    exposures = tuple(ExposureInventory.model_validate_json(e.canonical_json()) for e in exposures)
    if (
        not exposures
        or len({pin(e) for e in exposures}) != len(exposures)
        or any(e.source_manifest_sha256 != source_manifest_sha256 for e in exposures)
    ):
        raise ValueError("unique same-source exposure inventories required")
    cases = tuple(ExtractionCase.model_validate_json(c.canonical_json()) for c in cases)
    if len({c.input.case_id for c in cases}) != len(cases):
        raise ValueError("duplicate source case")
    families = {r.family_id for e in exposures for r in e.records}
    contexts = {r.context_sha256 for e in exposures for r in e.records if r.context_sha256}
    requests = {r.request_sha256 for e in exposures for r in e.records if r.request_sha256}
    candidates = []
    for case in cases:
        value, target = case.input, case.target
        if value.case_id != target.case_id or any(
            value.context[a.start : a.start + len(a.text)] != a.text for a in target.answers
        ):
            raise ValueError("publisher reference differs")
        if (
            target.split == "development"
            and target.family_id not in families
            and sha256(value.context.encode()) not in contexts
            and len(value.context) <= 50000
            and target.category not in EXCLUDED
        ):
            candidates.append(case)
    context_pins = {c.input.case_id: sha256(c.input.context.encode()) for c in candidates}
    request_pins = {
        c.input.case_id: pin(model_request(c.input, max_context_chars=50000)) for c in candidates
    }
    chosen: list[ExtractionCase] = []
    references: list[QualificationCase] = []
    categories: Counter[str] = Counter()
    for accepted in (True, False):
        for index in range(74):
            eligible = [
                c
                for c in candidates
                if (not c.target.impossible) == accepted
                and c.target.family_id not in families
                and context_pins[c.input.case_id] not in contexts
                and categories[c.target.category] < 16
                and request_pins[c.input.case_id] not in requests
            ]
            if not eligible:
                raise ValueError(
                    "insufficient disjoint confidence-study families under fixed policy"
                )
            case = min(eligible, key=lambda c: (categories[c.target.category], c.input.case_id))
            request = pin(model_request(case.input, max_context_chars=50000))
            context = sha256(case.input.context.encode())
            chosen.append(case)
            families.add(case.target.family_id)
            contexts.add(context)
            requests.add(request)
            categories[case.target.category] += 1
            references.append(
                QualificationCase(
                    case_id=case.input.case_id,
                    input_sha256=request,
                    independence_keys=(case.target.family_id, context),
                    split="calibration" if index < 2 else "holdout",
                    slices=("answerability",),
                    expected_accept=accepted,
                    reference_sha256=pin(case.target),
                    reference_kind="published_reference",
                    exposure="public_reference",
                    applicability_ref="original-publisher-answerability-only-not-legal-or-billing-truth",
                )
            )
    dataset = QualificationDataset(
        version="cuad-confidence-study-v1",
        agent="revenue",
        field="answerability",
        frozen_at=frozen_at,
        cases=tuple(references),
    )
    return ConfidenceCohort(
        source_manifest_sha256=source_manifest_sha256,
        exposure_inventory_sha256s=tuple(pin(e) for e in exposures),
        evaluator_source_sha256=evaluator_source_sha256,
        frozen_at=frozen_at,
        cases=tuple(chosen),
        dataset=dataset,
        schedule=tuple(
            ProspectiveTrial(case_id=r.case_id, trial_id=trial, request_sha256=r.input_sha256)
            for trial in ("trial-1", "trial-2")
            for r in references
        ),
    )
