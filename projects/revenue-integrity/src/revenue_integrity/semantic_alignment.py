"""Opt-in parser v2 for unique whitespace-aligned citations; legacy pilot stays literal."""

import json
from typing import Literal

from agent_harness.cases import _unique_object
from agent_harness.citation_alignment import AlignedQuote, align_quote
from agent_harness.contracts import Contract, ModelResponse
from agent_harness.release_contracts import Sha256, pin

from revenue_integrity.semantic_pilot import SemanticJudgment, model_request
from revenue_integrity.source_contracts import ExtractionInput


class AlignedSemanticJudgment(Contract):
    version: Literal["semantic-answerability-parser-v2"] = "semantic-answerability-parser-v2"
    input_sha256: Sha256
    response_sha256: Sha256
    judgment: SemanticJudgment
    aligned_quotes: tuple[AlignedQuote, ...]
    semantic_support: Literal["not_assessed"] = "not_assessed"
    release_allowed: Literal[False] = False


def parse_aligned_judgment(
    value: ExtractionInput, response: ModelResponse, *, max_context_chars: int = 20000
) -> AlignedSemanticJudgment:
    """Preserve model decision and raw quotes; return exact mapped source evidence separately."""
    value = ExtractionInput.model_validate_json(value.canonical_json())
    response = ModelResponse.model_validate_json(response.canonical_json())
    route = model_request(value, max_context_chars=max_context_chars)
    if response.failure or (response.provider, response.model) != (route.provider, route.model):
        raise ValueError("aligned assessment failed or route differs")
    if response.output is None or response.output.content is None or response.output.tool_calls:
        raise ValueError("aligned assessment lacks plain structured text")
    text = response.output.content
    json.loads(text, object_pairs_hook=_unique_object)
    judgment = SemanticJudgment.model_validate_json(text)
    aligned = tuple(align_quote(value.context, quote) for quote in judgment.quotes)
    occupied: list[tuple[int, int]] = []
    for citation in aligned:
        start, end = citation.span.start, citation.span.end
        if any(start < right and end > left for left, right in occupied):
            raise ValueError("aligned quotations overlap or duplicate evidence")
        occupied.append((start, end))
    return AlignedSemanticJudgment(
        input_sha256=pin(value),
        response_sha256=pin(response),
        judgment=judgment,
        aligned_quotes=aligned,
    )
