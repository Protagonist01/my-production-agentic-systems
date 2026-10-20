"""Original CUAD extraction input and evaluator-only published span contracts."""

from typing import Annotated, Literal, Self

from agent_harness.contracts import Contract, NonEmpty
from pydantic import Field, model_validator

Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
SOURCE_COMMIT = "67faa0e6023b04fcaae6cc09497ab00e5d63a2a2"
SOURCE_URL = f"https://raw.githubusercontent.com/The-Atticus-Project/cuad/{SOURCE_COMMIT}/data.zip"
POLICY = "cuad-issuer-template-v1"
Split = Literal["development", "holdout"]


class SourcePin(Contract):
    """A trusted, independently supplied raw-byte pin, never inferred from an archive."""

    source_url: NonEmpty
    source_commit: Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]
    archive_sha256: Digest
    archive_bytes: Annotated[int, Field(gt=0, le=100_000_000)]
    member: NonEmpty
    member_sha256: Digest
    member_bytes: Annotated[int, Field(gt=0, le=200_000_000)]
    contract_count: Annotated[int, Field(gt=0, le=10000)]
    category_count: Annotated[int, Field(gt=0, le=1000)]
    license: Literal["CC-BY-4.0"] = "CC-BY-4.0"


class ExtractionInput(Contract):
    """Only this projection may be passed to a candidate extractor."""

    case_id: Digest
    context: NonEmpty
    question: NonEmpty


class Span(Contract):
    start: Annotated[int, Field(ge=0)]
    text: NonEmpty


class PublishedTarget(Contract):
    """Publisher-authored references, not generated billing or newly reviewed gold."""

    case_id: Digest
    category: NonEmpty
    answers: tuple[Span, ...]
    impossible: bool
    family_id: Digest
    split: Split
    source_kind: Literal["original"] = "original"
    label_authority: Literal["CUAD-published-expert-annotations"] = (
        "CUAD-published-expert-annotations"
    )

    @model_validator(mode="after")
    def answerability(self) -> Self:
        if self.impossible != (not self.answers):
            raise ValueError("published answerability conflicts with answer spans")
        return self
