"""Model-only original-baseline request/assessment; no target in candidate projection."""

import json
from typing import Literal

from agent_harness.cases import _unique_object
from agent_harness.citation_alignment import align_quote
from agent_harness.contracts import ModelRequest, ModelResponse
from agent_harness.model_budget import MODELS, Model
from agent_harness.release_contracts import pin

from revenue_integrity.paired_quality import QualityOutcome
from revenue_integrity.semantic_alignment import AlignedSemanticJudgment
from revenue_integrity.semantic_pilot import SemanticJudgment, model_request
from revenue_integrity.source_contracts import ExtractionInput


def comparison_request(value: ExtractionInput, model: Model) -> ModelRequest:
    if model not in MODELS:
        raise ValueError("unapproved model")
    original = model_request(value, max_context_chars=50000)
    return ModelRequest.model_validate_json(
        original.model_copy(update={"model": model}).canonical_json()
    )


def assess_model(
    value: ExtractionInput,
    request: ModelRequest,
    response: ModelResponse,
    trial_id: Literal["trial-1", "trial-2"],
    elapsed_seconds: float,
) -> tuple[QualityOutcome, dict[str, object] | None]:
    if request.model not in MODELS or request != comparison_request(value, request.model):
        raise ValueError("model comparison request/input differs")
    response = ModelResponse.model_validate_json(response.canonical_json())
    failure: str | None = response.failure.code if response.failure else None
    decision = None
    raw = None
    parsed = None
    if (
        not response.failure
        and response.output
        and response.output.content
        and not response.output.tool_calls
    ):
        try:
            json.loads(response.output.content, object_pairs_hook=_unique_object)
            judgment = SemanticJudgment.model_validate_json(response.output.content)
            raw = judgment.decision
            if (response.provider, response.model) != (request.provider, request.model):
                raise ValueError("model response route differs")
            quotes = tuple(align_quote(value.context, q) for q in judgment.quotes)
            intervals: list[tuple[int, int]] = []
            for quote in quotes:
                start, end = quote.span.start, quote.span.end
                if any(start < right and end > left for left, right in intervals):
                    raise ValueError("overlapping model quotations")
                intervals.append((start, end))
            parsed = AlignedSemanticJudgment(
                input_sha256=pin(value),
                response_sha256=pin(response),
                judgment=judgment,
                aligned_quotes=quotes,
            ).model_dump(mode="json")
            decision = judgment.decision
        except ValueError:
            failure = "invalid_evidence_or_judgment"
    else:
        failure = failure or "invalid_evidence_or_judgment"
    return QualityOutcome(
        case_id=value.case_id,
        variant="baseline" if request.model == MODELS[0] else "challenger",
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
