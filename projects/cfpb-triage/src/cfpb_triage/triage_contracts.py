"""Closed classifier contracts; evaluator targets never enter ComplaintInput."""

import hashlib
from typing import Annotated, Literal, Self

from agent_harness.contracts import Contract, Usage
from pydantic import Field, model_validator

from cfpb_triage.review import EvidenceSpan
from cfpb_triage.source_contracts import ComplaintInput, Digest

Id = Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{1,96}$")]
Route = Literal["cheap", "strong"]


class Taxonomy(Contract):
    version: str
    source_manifest: Digest
    fit_split: Literal["development"] = "development"
    pairs: dict[str, tuple[str, ...]]

    @model_validator(mode="after")
    def valid(self) -> Self:
        if not self.pairs or len(self.pairs) > 100:
            raise ValueError("bounded nonempty taxonomy required")
        for product, issues in self.pairs.items():
            if not product or not issues or len(set(issues)) != len(issues):
                raise ValueError("unique nonempty taxonomy pairs required")
        return self

    def digest(self) -> str:
        return hashlib.sha256(self.canonical_json().encode()).hexdigest()


class Prediction(Contract):
    product: Annotated[str, Field(min_length=1, max_length=200)] | None
    issue: Annotated[str, Field(min_length=1, max_length=300)] | None
    priority: Literal["routine", "elevated", "uncertain"]
    ambiguity: Literal["clear", "ambiguous"]
    confidence: Annotated[float, Field(ge=0, le=1)]
    evidence: Annotated[tuple[EvidenceSpan, ...], Field(max_length=3)]

    def check(self, complaint: ComplaintInput, taxonomy: Taxonomy) -> None:
        if (self.product is None) != (self.issue is None):
            raise ValueError("product and issue must both be present or absent")
        if self.product is not None and self.issue not in taxonomy.pairs.get(self.product, ()):
            raise ValueError("taxonomy pair is unsupported")
        if self.product is not None and not self.evidence:
            raise ValueError("classification requires exact narrative evidence")
        if self.priority == "elevated" and not self.evidence:
            raise ValueError("elevated priority requires exact narrative evidence")
        for span in self.evidence:
            if span.end <= span.start or span.end > len(complaint.narrative):
                raise ValueError("evidence outside current narrative")
            if complaint.narrative[span.start : span.end] != span.text:
                raise ValueError("evidence quote differs from current narrative")


class ExtractedPrediction(Contract):
    """The model quotes text; trusted code computes unique Unicode offsets."""

    product: Annotated[str, Field(min_length=1, max_length=200)] | None
    issue: Annotated[str, Field(min_length=1, max_length=300)] | None
    priority: Literal["routine", "elevated", "uncertain"]
    ambiguity: Literal["clear", "ambiguous"]
    confidence: Annotated[float, Field(ge=0, le=1)]
    quotes: Annotated[
        tuple[Annotated[str, Field(min_length=1, max_length=500)], ...], Field(max_length=3)
    ]

    def locate(self, complaint: ComplaintInput, taxonomy: Taxonomy) -> Prediction:
        spans = []
        if len(set(self.quotes)) != len(self.quotes):
            raise ValueError("duplicate evidence quotes")
        for quote in self.quotes:
            start = complaint.narrative.find(quote)
            if start < 0 or complaint.narrative.find(quote, start + 1) >= 0:
                raise ValueError("evidence quote must have one exact occurrence")
            spans.append(EvidenceSpan(start=start, end=start + len(quote), text=quote))
        prediction = Prediction(
            product=self.product,
            issue=self.issue,
            priority=self.priority,
            ambiguity=self.ambiguity,
            confidence=self.confidence,
            evidence=tuple(spans),
        )
        prediction.check(complaint, taxonomy)
        return prediction


class Attempt(Contract):
    route: Route
    model: str
    prediction: Prediction | None = None
    failure: (
        Literal[
            "timeout",
            "rate_limited",
            "invalid_response",
            "budget_exhausted",
            "permission_denied",
            "unavailable",
            "replay_mismatch",
            "scorer_error",
        ]
        | None
    ) = None
    usage: Usage | None = None


class RouterPolicy(Contract):
    version: Literal["cfpb-router-v1"] = "cfpb-router-v1"
    taxonomy_sha256: Digest
    # 1.01 intentionally admits no prediction, including confidence 1.0.
    cheap_threshold: Annotated[float, Field(ge=0, le=1.01)] = 1.01
    strong_threshold: Annotated[float, Field(ge=0, le=1.01)] = 1.01
    fit_split: Literal["development"] = "development"
    fit_manifest_sha256: Digest
    fit_cases: Annotated[int, Field(ge=0)]
    max_development_auto_error: Annotated[float, Field(ge=0, le=1)] = 0.0
    target_review_fraction: Annotated[float, Field(ge=0, le=1)] = 0.5
    label_status: Literal["ai_provisional"] = "ai_provisional"


class Decision(Contract):
    case_id: Digest
    narrative_sha256: Digest
    taxonomy_sha256: Digest
    policy_sha256: Digest
    outcome: Literal["classified", "review_required"]
    reason: Literal[
        "supported_route", "uncertain_or_high_priority", "below_threshold", "model_failure"
    ]
    prediction: Prediction | None
    attempts: Annotated[tuple[Attempt, ...], Field(max_length=2)]
    mode: Literal["cheap_first", "always_strong"]


def digest_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
