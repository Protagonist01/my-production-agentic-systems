"""Invented parser/request checks; no model-quality observations or providers."""

import json

import pytest

from docs.evaluation.olist_semantic_candidate import parse, request


def explicit(**changes: object) -> str:
    return json.dumps(
        {
            "intent": "refund",
            "amount_status": "explicit",
            "requested_minor": 2500,
            "currency": "dollar_unspecified",
            "amount_evidence": "$25",
            **changes,
        }
    )


def test_request_has_only_fixed_instructions_schema_and_exact_input() -> None:
    text = "invented customer text"
    result = request(text)
    assert result.messages[-1].content == text
    assert len(result.messages) == 2
    assert not result.tools and result.tool_choice is None
    assert result.output_schema["additionalProperties"] is False
    assert result == request(text)


@pytest.mark.parametrize("text", ["", " ", "x" * 8193, {"text": "x", "expected": "refund"}])
def test_request_refuses_wrong_input_shape(text: object) -> None:
    with pytest.raises(ValueError):
        request(text)


def test_native_dollar_amount_stays_non_iso_non_sim() -> None:
    result = parse("refund $25", explicit())
    assert result.requested_minor == 2500
    assert result.currency == "dollar_unspecified"


@pytest.mark.parametrize(
    "changes",
    [
        {"requested_minor": 2501},
        {"requested_minor": "2500"},
        {"currency": "USD"},
        {"currency": "SIM"},
        {"amount_evidence": "$50"},
        {"intent": "status"},
        {"amount_status": "unclear"},
        {"amount_evidence": None},
    ],
)
def test_inconsistent_or_fabricated_output_refuses(changes: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        parse("refund $25", explicit(**changes))


def test_price_quote_presence_does_not_establish_requested_role() -> None:
    # This intentionally passes mechanics while exposing the semantic trust boundary.
    result = parse("I paid $25; refund only part of it", explicit())
    assert result.requested_minor == 2500
    # Accuracy still requires a separately admitted applicable reference/evaluator.


def test_unresolved_role_is_preserved_without_a_zero_value() -> None:
    raw = json.dumps(
        {
            "intent": "clarify",
            "amount_status": "unclear",
            "requested_minor": None,
            "currency": "unspecified",
            "amount_evidence": None,
        }
    )
    assert parse("I paid money; can you help?", raw).requested_minor is None


def test_duplicate_json_fields_refuse() -> None:
    with pytest.raises(ValueError):
        parse("refund $25", explicit()[:-1] + ', "requested_minor": 1}')


def test_quote_must_not_be_a_numeric_suffix() -> None:
    with pytest.raises(ValueError, match="fragment"):
        parse("refund 125 SIM", explicit(currency="SIM", amount_evidence="25 SIM"))


@pytest.mark.parametrize("literal", ["$25.000", "$-25", "$025", "$2,500"])
def test_no_rounding_or_silent_format_repair(literal: str) -> None:
    with pytest.raises(ValueError):
        parse("refund " + literal, explicit(amount_evidence=literal))
