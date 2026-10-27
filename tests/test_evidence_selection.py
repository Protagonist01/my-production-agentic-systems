"""Invented integrity checks; never evidence of improved model interpretation."""

import json

import pytest
from agent_harness.baseline_recording import zero_usage
from agent_harness.contracts import ModelMessage, ModelResponse
from revenue_integrity.evidence_selection import (
    copy_selection,
    interpretation_request,
    selection_request,
    source_catalog,
)
from revenue_integrity.semantic_pilot import model_request
from revenue_integrity.source_contracts import ExtractionInput


def value(text="Invented: no exclusive rights.\nΩ\t🙂"):
    return ExtractionInput(
        case_id="a" * 64, context=text, question="Is an exclusive right granted?"
    )


def response(content='{"decision":"accept","evidence_ids":["s0"]}'):
    return ModelResponse(
        provider="google-gemini-developer-api",
        model="gemini-3.5-flash-lite",
        output=ModelMessage(role="assistant", content=content),
        usage=zero_usage("USD"),
    )


def test_interpretation_variant_changes_only_system_instruction():
    original = model_request(value(), max_context_chars=50000)
    variant = interpretation_request(value())
    assert original.messages[0] != variant.messages[0]
    assert original.messages[1:] == variant.messages[1:]
    assert original.model_copy(update={"messages": variant.messages}) == variant
    assert "publisher" not in variant.canonical_json().lower()


def test_catalog_covers_every_character_and_duplicate_text_has_distinct_source_positions():
    v = value(("Ω\t🙂" * 100) + ("Ω\t🙂" * 100) + "tail")
    spans = source_catalog(v)
    assert "".join(s.text for s in spans) == v.context
    assert spans[0].text == spans[1].text and spans[0].evidence_id != spans[1].evidence_id
    raw = response('{"decision":"accept","evidence_ids":["s1","s2"]}')
    result = copy_selection(v, selection_request(v), raw)
    assert [s.start for s in result.spans] == [300, 600]
    assert all(v.context[s.start : s.start + len(s.text)] == s.text for s in result.spans)
    assert result.semantic_support == "not_assessed" and not result.release_allowed


def test_copying_integrity_deliberately_does_not_establish_semantic_correctness():
    v = value()
    result = copy_selection(v, selection_request(v), response())
    assert result.spans[0].text == v.context  # Valid copy even though invented decision is wrong.
    assert result.semantic_support == "not_assessed"


@pytest.mark.parametrize(
    "content",
    [
        '{"decision":"accept","evidence_ids":[]}',
        '{"decision":"reject","evidence_ids":["s0"]}',
        '{"decision":"accept","evidence_ids":["s0","s0"]}',
        '{"decision":"accept","evidence_ids":["s999"]}',
        '{"decision":"accept","decision":"reject","evidence_ids":[]}',
        '{"decision":"accept","evidence_ids":["s0"],"quote":"edited"}',
    ],
)
def test_invalid_or_fabricated_selections_refuse(content):
    with pytest.raises(ValueError):
        copy_selection(value(), selection_request(value()), response(content))


def test_input_or_request_substitution_refuses_and_reject_has_no_evidence():
    v = value()
    request = selection_request(v)
    with pytest.raises(ValueError, match="binding"):
        copy_selection(value("changed"), request, response())
    with pytest.raises(ValueError, match="binding"):
        copy_selection(v, request.model_copy(update={"parameters": {}}), response())
    rejected = copy_selection(v, request, response('{"decision":"reject","evidence_ids":[]}'))
    assert rejected.spans == ()
    user = json.loads(request.messages[1].content)
    assert set(user) == {"question", "source_catalog"}
    assert "target" not in user and "expected" not in user
