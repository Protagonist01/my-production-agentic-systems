"""Parser v2 is explicit; v1 results and semantic labels are never rewritten."""

import json

import pytest
from agent_harness.baseline_recording import zero_usage
from agent_harness.contracts import ModelMessage, ModelResponse
from revenue_integrity.semantic_alignment import parse_aligned_judgment
from revenue_integrity.semantic_pilot import parse_judgment
from revenue_integrity.source_contracts import ExtractionInput


def value(context="Unique clause:\n Payment\t is due."):
    return ExtractionInput(case_id="a" * 64, context=context, question="When is payment due?")


def response(decision="accept", quotes=("Payment is due.",)):
    return ModelResponse(
        provider="google-gemini-developer-api",
        model="gemini-3.5-flash-lite",
        output=ModelMessage(
            role="assistant", content=json.dumps({"decision": decision, "quotes": list(quotes)})
        ),
        usage=zero_usage("USD"),
    )


def test_new_parser_maps_source_without_changing_legacy_failure_or_raw_output():
    original = response()
    before = original.canonical_json()
    with pytest.raises(ValueError, match="not literal"):
        parse_judgment(value(), original)
    result = parse_aligned_judgment(value(), original)
    assert result.aligned_quotes[0].span.text == "Payment\t is due."
    assert result.judgment.quotes == ("Payment is due.",)
    assert result.semantic_support == "not_assessed" and not result.release_allowed
    assert original.canonical_json() == before
    with pytest.raises(ValueError):
        parse_judgment(value(), original)


@pytest.mark.parametrize(
    "quotes",
    [
        ("Payment is not due.",),
        ("Payment is due.", "Payment is due."),
        ("Payment", "Payment is due."),
    ],
)
def test_wrong_negation_duplicate_and_overlapping_citations_refuse(quotes):
    with pytest.raises(ValueError):
        parse_aligned_judgment(value(), response(quotes=quotes))


def test_ambiguous_exact_quote_refuses_and_absent_reference_labels_are_not_consulted():
    with pytest.raises(ValueError, match="ambiguous"):
        parse_aligned_judgment(value("Payment is due. Payment is due."), response())
    for decision in ("reject", "abstain"):
        result = parse_aligned_judgment(value(), response(decision, ()))
        assert result.judgment.decision == decision and result.aligned_quotes == ()
    with pytest.raises(ValueError):
        parse_aligned_judgment(value(), response("reject"))
