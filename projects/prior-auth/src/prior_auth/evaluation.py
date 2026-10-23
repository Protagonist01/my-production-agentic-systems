"""Evaluator-only labels and explicit outcome denominators; never candidate input."""

from typing import Literal

from agent_harness.contracts import Contract

from prior_auth.assessment import CRITERIA
from prior_auth.contracts import AssessmentResult, CriterionId, NoteInput, State


class ExpectedCriterion(Contract):
    criterion_id: CriterionId
    state: State
    support_quotes: tuple[str, ...]
    rationale: str


class EvaluationCase(Contract):
    input: NoteInput
    group_id: str
    parent_id: str | None = None
    split: Literal["development", "holdout"]
    source_ref: str
    edit_description: str | None = None
    label_status: Literal["ai_provisional"] = "ai_provisional"
    expected: tuple[ExpectedCriterion, ...]
    expected_disposition: Literal[
        "evidence_complete_for_review", "request_information", "qualified_review"
    ]
    label_rationale: str

    def validate_labels(self) -> None:
        if len(self.expected) != len(CRITERIA) or {c.criterion_id for c in self.expected} != set(
            CRITERIA
        ):
            raise ValueError("complete unique independent labels required")
        for criterion in self.expected:
            for quote in criterion.support_quotes:
                if quote not in self.input.text:
                    raise ValueError("expected quote absent from case text")
            if criterion.state == "met" and not criterion.support_quotes:
                raise ValueError("expected met requires independent supporting quote")
        if self.expected_disposition == "evidence_complete_for_review" and any(
            criterion.state != "met" for criterion in self.expected
        ):
            raise ValueError("evidence-complete expected disposition contradicts criterion labels")


def validate_cohort(cases: tuple[EvaluationCase, ...]) -> None:
    if not cases or len({c.input.case_id for c in cases}) != len(cases):
        raise ValueError("unique nonempty case cohort required")
    groups: dict[str, str] = {}
    notes: dict[str, str] = {}
    by_id = {c.input.case_id: c for c in cases}
    for case in cases:
        case.validate_labels()
        if case.group_id in groups and groups[case.group_id] != case.split:
            raise ValueError("related records cross split boundary")
        groups[case.group_id] = case.split
        if case.input.note_sha256 in notes and notes[case.input.note_sha256] != case.split:
            raise ValueError("duplicate note crosses split boundary")
        notes[case.input.note_sha256] = case.split
        if case.parent_id is not None:
            parent = by_id.get(case.parent_id)
            if parent is None or parent.group_id != case.group_id or not case.edit_description:
                raise ValueError(
                    "edited case requires same-group source parent and edit provenance"
                )


def score(case: EvaluationCase, result: AssessmentResult | None) -> dict[str, int | str]:
    case.validate_labels()
    expected = {c.criterion_id: c.state for c in case.expected}
    if result is None:
        return dict(
            case_id=case.input.case_id,
            completed=0,
            missing=1,
            correct=0,
            criterion_correct=0,
            criterion_denominator=len(CRITERIA),
            unsupported_met=0,
            proposed_evidence_complete=0,
            incorrect_evidence_complete=0,
        )
    if (
        result.case_id != case.input.case_id
        or result.note_sha256 != case.input.note_sha256
        or result.policy_sha256 != case.input.policy_sha256
    ):
        raise ValueError("scorer result belongs to different input or policy")
    actual = {c.criterion_id: c.state for c in result.claims}
    correct = actual == expected and result.disposition == case.expected_disposition
    proposed = int(result.disposition == "evidence_complete_for_review")
    return dict(
        case_id=case.input.case_id,
        completed=1,
        missing=0,
        correct=int(correct),
        criterion_correct=sum(actual.get(key) == expected[key] for key in CRITERIA),
        criterion_denominator=len(CRITERIA),
        unsupported_met=sum(
            actual.get(key) == "met" and expected[key] != "met" for key in CRITERIA
        ),
        proposed_evidence_complete=proposed,
        incorrect_evidence_complete=int(
            bool(proposed) and case.expected_disposition != "evidence_complete_for_review"
        ),
    )
