"""Fixed-denominator exposed-development reporting; no model or source mutation."""

import json
from collections import Counter
from typing import Annotated, Literal, Self

from agent_harness.cases import _unique_object
from agent_harness.contracts import Contract, ModelRequest, ModelResponse, NonEmpty
from pydantic import Field, model_validator

from revenue_integrity.evidence_selection import (
    Selection,
    copy_selection,
    interpretation_request,
    selection_request,
)
from revenue_integrity.semantic_alignment import parse_aligned_judgment
from revenue_integrity.semantic_pilot import SemanticJudgment, model_request
from revenue_integrity.source_contracts import ExtractionInput

Variant = Literal["baseline", "task_wording", "evidence_selection", "challenger"]
VARIANTS: tuple[Variant, ...] = ("baseline", "task_wording", "evidence_selection")


class QualityOutcome(Contract):
    case_id: NonEmpty
    variant: Variant
    trial_id: Literal["trial-1", "trial-2"]
    decision: Literal["accept", "reject", "abstain"] | None
    raw_decision: Literal["accept", "reject", "abstain"] | None
    evidence_valid: bool
    failure: NonEmpty | None
    input_tokens: Annotated[int, Field(ge=0)] | None
    output_tokens: Annotated[int, Field(ge=0)] | None
    cost_known: bool
    elapsed_seconds: Annotated[float, Field(ge=0)]

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if (
            (self.failure is None) != self.evidence_valid
            or (self.evidence_valid and self.decision is None)
            or (not self.evidence_valid and self.decision is not None)
        ):
            raise ValueError("outcome decision/integrity/failure differs")
        return self


def assess(
    value: ExtractionInput,
    request: ModelRequest,
    response: ModelResponse,
    variant: Variant,
    trial_id: Literal["trial-1", "trial-2"],
    elapsed_seconds: float,
) -> tuple[QualityOutcome, dict[str, object] | None]:
    """Label-free response assessment; reference agreement happens only in summarize."""
    factories = {
        "baseline": lambda v: model_request(v, max_context_chars=50000),
        "task_wording": interpretation_request,
        "evidence_selection": selection_request,
    }
    if request != factories[variant](value):
        raise ValueError("paired request differs from frozen variant/input")
    response = ModelResponse.model_validate_json(response.canonical_json())
    raw = None
    if response.output and response.output.content:
        try:
            json.loads(response.output.content, object_pairs_hook=_unique_object)
            raw = (
                Selection.model_validate_json(response.output.content).decision
                if variant == "evidence_selection"
                else SemanticJudgment.model_validate_json(response.output.content).decision
            )
        except ValueError:
            pass
    failure: str | None = response.failure.code if response.failure else None
    parsed = None
    decision = None
    try:
        if variant == "evidence_selection":
            selected = copy_selection(value, request, response)
            decision = selected.selection.decision
            parsed = selected.model_dump(mode="json")
        else:
            aligned = parse_aligned_judgment(value, response, max_context_chars=50000)
            decision = aligned.judgment.decision
            parsed = aligned.model_dump(mode="json")
    except ValueError:
        failure = failure or "invalid_evidence_or_judgment"
    return QualityOutcome(
        case_id=value.case_id,
        variant=variant,
        trial_id=trial_id,
        decision=decision,
        raw_decision=raw,
        evidence_valid=parsed is not None,
        failure=failure,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        cost_known=response.usage.cost is not None,
        elapsed_seconds=elapsed_seconds,
    ), parsed


def summarize(
    expected: dict[str, bool],
    controls: frozenset[str],
    rows: tuple[QualityOutcome, ...],
    *,
    comparison: Literal["variants", "models"] = "variants",
) -> dict[str, object]:
    variants: tuple[Variant, ...] = (
        ("baseline", "challenger") if comparison == "models" else VARIANTS
    )
    if (
        len(expected) != 12
        or sum(expected.values()) != 6
        or len(controls) != 4
        or not controls <= expected.keys()
    ):
        raise ValueError("expected twelve balanced cases and four controls")
    rows = tuple(QualityOutcome.model_validate_json(r.canonical_json()) for r in rows)
    indexed = {(r.case_id, r.variant, r.trial_id): r for r in rows}
    if len(indexed) != len(rows) or any(
        r.case_id not in expected or r.variant not in variants for r in rows
    ):
        raise ValueError("duplicate or foreign comparison row")

    def correct(row: QualityOutcome) -> bool:
        return (
            row.failure is None
            and row.evidence_valid
            and row.decision in ("accept", "reject")
            and (row.decision == "accept") == expected[row.case_id]
        )

    metrics: dict[str, object] = {}
    family: dict[tuple[str, Variant], bool | None] = {}
    for variant in variants:
        members = [r for r in rows if r.variant == variant]
        for case in expected:
            pair = [indexed.get((case, variant, t)) for t in ("trial-1", "trial-2")]
            family[(case, variant)] = (
                None
                if any(r is None for r in pair)
                else all(correct(r) for r in pair if r is not None)
            )
        metrics[variant] = {
            "scheduled": 24,
            "observed": len(members),
            "missing": 24 - len(members),
            "correct": sum(correct(r) for r in members),
            "scheduled_agreement": sum(correct(r) for r in members) / 24,
            "decided": sum(
                r.decision in ("accept", "reject") and r.evidence_valid and not r.failure
                for r in members
            ),
            "raw_reference_agreement_count": sum(
                r.raw_decision in ("accept", "reject")
                and (r.raw_decision == "accept") == expected[r.case_id]
                for r in members
            ),
            "evidence_valid": sum(r.evidence_valid for r in members),
            "raw_accepts": sum(r.raw_decision == "accept" for r in members),
            "accepts_with_valid_evidence": sum(
                r.decision == "accept" and r.evidence_valid for r in members
            ),
            "class_results": {
                name: {
                    "scheduled": 12,
                    "observed": sum(expected[r.case_id] == label for r in members),
                    "correct": sum(correct(r) for r in members if expected[r.case_id] == label),
                    "unresolved_observed": sum(
                        r.decision not in ("accept", "reject") or not r.evidence_valid
                        for r in members
                        if expected[r.case_id] == label
                    ),
                    "missing": 12 - sum(expected[r.case_id] == label for r in members),
                }
                for name, label in (("answerable", True), ("no_answer", False))
            },
            "failures": dict(Counter(r.failure for r in members if r.failure)),
            "false_accepts": sum(
                r.decision == "accept"
                and r.evidence_valid
                and not r.failure
                and not expected[r.case_id]
                for r in members
            ),
            "false_rejects": sum(
                r.decision == "reject"
                and r.evidence_valid
                and not r.failure
                and expected[r.case_id]
                for r in members
            ),
            "known_input_tokens": sum(r.input_tokens or 0 for r in members),
            "known_output_tokens": sum(r.output_tokens or 0 for r in members),
            "unknown_input_token_rows": sum(r.input_tokens is None for r in members),
            "unknown_output_token_rows": sum(r.output_tokens is None for r in members),
            "unknown_cost_rows": sum(not r.cost_known for r in members),
            "total_elapsed_seconds": sum(r.elapsed_seconds for r in members),
            "consistently_correct_families": sum(family[(c, variant)] is True for c in expected),
            "unobserved_family_pairs": sum(family[(c, variant)] is None for c in expected),
            "consistently_correct_controls": sum(family[(c, variant)] is True for c in controls),
        }
    paired = {}
    for variant in variants[1:]:
        comparable = [
            c
            for c in expected
            if family[(c, "baseline")] is not None and family[(c, variant)] is not None
        ]
        gains = sum(
            family[(c, "baseline")] is False and family[(c, variant)] is True for c in comparable
        )
        regressions = sum(
            family[(c, "baseline")] is True and family[(c, variant)] is False for c in comparable
        )
        paired[variant] = {
            "comparable_families": len(comparable),
            "unobserved_families": 12 - len(comparable),
            "gained_consistently_correct_families": gains,
            "lost_consistently_correct_families": regressions,
            "net_consistently_correct_families": gains - regressions,
            "control_regressions": sum(
                family[(c, "baseline")] is True and family[(c, variant)] is False
                for c in comparable
                if c in controls
            ),
        }
    return {
        "version": "model-only-development-report-v1"
        if comparison == "models"
        else "paired-quality-development-report-v1",
        "scheduled": len(variants) * 24,
        "observed": len(rows),
        "missing": len(variants) * 24 - len(rows),
        "metrics": metrics,
        "paired_vs_fresh_baseline": paired,
        "all_scheduled_reference_correct": len(rows) == len(variants) * 24
        and all(correct(r) for r in rows),
        "all_cases_exposed": True,
        "qualification_met": False,
        "release_allowed": False,
        "limits": [
            "Exposed development cases; no representative reliability or confidence claim.",
            "Publisher agreement and exact copying do not establish relevant legal support.",
            "Raw decision and source-integrity metrics overlap; do not add them.",
            "Missing scheduled rows remain in denominators; no replacement/retry.",
        ],
    }
