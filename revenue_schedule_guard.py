"""Validate a pricing assessment before displaying amounts or using them downstream."""

import json
from typing import Any, Literal, Self

from agent_harness.contracts import Contract
from pydantic import Field, model_validator


class MonthlyOrderTerms(Contract):
    """Verified terms for a single monthly line with no adjustments."""

    unit_price_minor: int = Field(ge=0, strict=True)
    billable_users: int = Field(ge=0, strict=True)
    issued_total_minor: int = Field(ge=0, strict=True)


class ScheduleAssessment(Contract):
    action: Literal["analyze", "request_information", "review"]
    missing_fields: tuple[Literal["quantity", "conditions", "unit_price_minor"], ...]
    total_minor: int | None = Field(strict=True)
    delta_minor: int | None = Field(strict=True)
    evidence: tuple[str, ...]

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if len(set(self.missing_fields)) != len(self.missing_fields):
            raise ValueError("duplicate missing field")
        if self.action == "analyze":
            if self.total_minor is None or self.delta_minor is None or self.missing_fields:
                raise ValueError("analysis requires a total and delta with no missing fields")
        elif self.total_minor is not None or self.delta_minor is not None:
            raise ValueError("unresolved assessment cannot carry a total or delta")
        if self.action == "request_information" and not self.missing_fields:
            raise ValueError("clarification must name missing fields")
        return self


def checked_assessment(
    output: dict[str, Any], verified_terms: MonthlyOrderTerms | None = None
) -> ScheduleAssessment:
    """Check model output against trusted order facts before accepting its amounts."""
    answer = ScheduleAssessment.model_validate_json(json.dumps(output, allow_nan=False))
    if answer.action == "analyze":
        if verified_terms is None:
            raise ValueError("verified order terms required")
        total = verified_terms.unit_price_minor * verified_terms.billable_users
        delta = total - verified_terms.issued_total_minor
        if (answer.total_minor, answer.delta_minor) != (total, delta):
            raise ValueError("reported amounts disagree with verified order terms")
    return answer
