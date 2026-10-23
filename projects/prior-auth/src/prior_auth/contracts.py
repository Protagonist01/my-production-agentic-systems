"""Closed evidence contracts. No evaluator labels or authorization actions in input."""

import hashlib
from datetime import date
from typing import Annotated, Literal, Self

from agent_harness.contracts import Contract
from pydantic import Field, model_validator

Id = Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{1,96}$")]
Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
CriterionId = Literal[
    "adult_osa",
    "education",
    "clinical_evaluation",
    "sleep_test",
    "physician_order",
    "severity",
    "event_count",
]
State = Literal["met", "not_met", "insufficient", "conflict"]


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class Span(Contract):
    """Half-open Python Unicode character offsets into the exact referenced text."""

    start: Annotated[int, Field(ge=0)]
    end: Annotated[int, Field(gt=0)]
    quote: Annotated[str, Field(min_length=1, max_length=8000)]

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if self.start >= self.end or self.end - self.start != len(self.quote):
            raise ValueError("span length differs from quote")
        return self

    def require(self, text: str) -> None:
        if self.end > len(text) or text[self.start : self.end] != self.quote:
            raise ValueError("citation does not match pinned text")


class Criterion(Contract):
    criterion_id: CriterionId
    description: Annotated[str, Field(min_length=1, max_length=2000)]
    source: Span


class Policy(Contract):
    policy_id: Literal["cms-ncd-240-4-v3"]
    source_url: str
    source_sha256: Digest
    text_sha256: Digest
    effective_from: date
    effective_until: date | None = None
    scope: Literal["adult-initial-cpap-evidence"] = "adult-initial-cpap-evidence"
    criteria: tuple[Criterion, ...]
    review_status: Literal["ai_provisional", "qualified_reviewed"]
    review_ref: str

    @model_validator(mode="after")
    def complete(self) -> Self:
        expected = {
            "adult_osa",
            "education",
            "clinical_evaluation",
            "sleep_test",
            "physician_order",
            "severity",
            "event_count",
        }
        if {c.criterion_id for c in self.criteria} != expected or len(self.criteria) != 7:
            raise ValueError("complete unique selected policy criteria required")
        if self.effective_until is not None and self.effective_until <= self.effective_from:
            raise ValueError("invalid policy interval")
        return self


class Redaction(Contract):
    source: Span
    kind: Literal["name", "date", "address", "contact", "identifier", "other"]


class NoteInput(Contract):
    case_id: Id
    tenant_id: Id
    note_sha256: Digest
    text: Annotated[str, Field(min_length=1, max_length=100000)]
    service_date: date
    policy_id: Literal["cms-ncd-240-4-v3"]
    policy_sha256: Digest
    use: Literal["initial", "ongoing", "other"]
    provenance: Literal["published_illustrative", "edited_illustrative", "invented"]

    @model_validator(mode="after")
    def pinned(self) -> Self:
        if digest(self.text) != self.note_sha256:
            raise ValueError("note bytes differ from content pin")
        return self


class Claim(Contract):
    criterion_id: CriterionId
    state: State
    evidence: tuple[Span, ...]
    rationale: Annotated[str, Field(min_length=1, max_length=2000)]


class CandidateAssessment(Contract):
    case_id: Id
    note_sha256: Digest
    policy_sha256: Digest
    claims: tuple[Claim, ...]


class CheckedClaim(Contract):
    criterion_id: CriterionId
    state: State
    evidence: tuple[Span, ...]
    reason: str


class AssessmentResult(Contract):
    case_id: Id
    note_sha256: Digest
    policy_sha256: Digest
    claims: tuple[CheckedClaim, ...]
    disposition: Literal["evidence_complete_for_review", "request_information", "qualified_review"]
    retrieval_failure: bool
    assessment_failure: bool
    clinical_validation: Literal[False] = False
