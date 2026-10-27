"""Explicit exposed-case development candidate; never fresh qualification or release."""

import json
from typing import Literal

from agent_harness.cases import _unique_object
from agent_harness.citation_alignment import align_quote
from agent_harness.contracts import ModelMessage, ModelRequest, ModelResponse
from agent_harness.release_contracts import pin, sha256

from revenue_integrity.semantic_alignment import AlignedSemanticJudgment
from revenue_integrity.semantic_pilot import SemanticJudgment
from revenue_integrity.source_contracts import ExtractionInput

EXPECTED_PROMPT_SHA256 = "3ed3b393766efab954e9c272f520fa96a4cf523ae39579b79c145f4e800ebcad"


def development_request(value: ExtractionInput, frozen_request: ModelRequest) -> ModelRequest:
    """Revalidate the reviewed private model-only request, without evaluator metadata.

    The exact reviewed prompt and schema bytes stay pinned by the proposal. This function
    cannot substitute another prompt, route, decoding policy or context projection.
    """
    value = ExtractionInput.model_validate_json(value.canonical_json())
    request = ModelRequest.model_validate_json(frozen_request.canonical_json())
    from revenue_integrity.semantic_pilot import model_request

    old = model_request(value, max_context_chars=50000)
    schema = json.loads(json.dumps(old.output_schema))
    schema["properties"]["quotes"]["maxItems"] = 1
    if (
        request.provider != old.provider
        or request.endpoint != old.endpoint
        or request.model != "gemini-3.8-flash"
        or request.parameters
        != {"temperature": 0.0, "max_output_tokens": 2048, "thinking_level": "LOW"}
        or len(request.messages) != 2
        or request.messages[0].role != "system"
        or request.messages[0] != ModelMessage(role="system", content=request.messages[0].content)
        or sha256((request.messages[0].content or "").encode()) != EXPECTED_PROMPT_SHA256
        or request.messages[1] != old.messages[1]
        or request.output_schema != schema
        or request.tools != old.tools
        or request.tool_choice != old.tool_choice
    ):
        raise ValueError("development request route/projection differs")
    return request


def parse_development(
    value: ExtractionInput,
    request: ModelRequest,
    response: ModelResponse,
) -> AlignedSemanticJudgment:
    """Require the actual frozen route and one <=300-character unique source quotation."""
    request = development_request(value, request)
    response = ModelResponse.model_validate_json(response.canonical_json())
    if (
        response.failure
        or response.provider != request.provider
        or response.model != request.model
        or response.output is None
        or response.output.content is None
        or response.output.tool_calls
    ):
        raise ValueError("development response failed/route differs")
    text = response.output.content
    json.loads(text, object_pairs_hook=_unique_object)
    judgment = SemanticJudgment.model_validate_json(text)
    if judgment.decision == "accept" and (
        len(judgment.quotes) != 1 or len(judgment.quotes[0]) > 300
    ):
        raise ValueError("development accept requires one short quotation")
    aligned = tuple(align_quote(value.context, quote) for quote in judgment.quotes)
    return AlignedSemanticJudgment(
        input_sha256=pin(value),
        response_sha256=pin(response),
        judgment=judgment,
        aligned_quotes=aligned,
    )


DEVELOPMENT_ONLY: Literal[True] = True
