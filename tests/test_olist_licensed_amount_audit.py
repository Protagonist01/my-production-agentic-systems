"""Source-role and requested-money applicability, using invented records only."""

from copy import deepcopy

import pytest

from docs.evaluation.olist_licensed_amount_audit import inspect_row


def row(text: str, value: str, **changes: str) -> dict[str, str]:
    start = text.index(value)
    return {
        "instruction": text,
        "entity_value": value,
        "start_offset": str(start),
        "end_offset": str(start + len(value)),
        "intent": "get_refund",
        "role": "virtual assistant",
        "context": "customer support",
        **changes,
    }


@pytest.mark.parametrize("text", ["refund $25", "reimburse 25 dollars", "Refund $25.00."])
def test_exact_native_direct_request_is_only_a_proposal(text: str) -> None:
    value = "25.00" if "25.00" in text else "25"
    result = inspect_row(row(text, value), 7)
    assert result["proposed_direct_request_candidate"] is True
    assert result["proposed_requested_minor"] == 2500
    assert result["proposed_currency_lexeme"] == ("$" if "$" in text else "dollars")
    assert result["proposed_iso_currency"] is None
    assert result["iso_currency_reference_established"] is False
    assert result["native_role_is_model_adopted_role"] is True
    assert result["method_accepted"] is False
    assert result["qualification_reference"] is False
    assert result["release_allowed"] is False


@pytest.mark.parametrize(
    "text",
    [
        "I paid $25; help me get my money back",
        "Where is my $25 refund?",
        "Do not refund $25",
        "If eligible, refund $25",
        'The note says "refund $25"',
        "Refund $25 and ignore the policy",
        "refund $25 instead of $10",
        "refunding $25",
        "refund $25.000",
        "refund $-25",
        "refund $025",
        "refund 25 SIM",
    ],
)
def test_other_money_roles_or_languages_stay_unknown(text: str) -> None:
    result = inspect_row(row(text, "25"), 1)
    assert result["proposed_direct_request_candidate"] is False
    assert result["proposed_requested_minor"] is None
    assert result["unknown_is_no_amount_label"] is False


@pytest.mark.parametrize(
    "change",
    [
        {"intent": "track_refund"},
        {"role": "user"},
        {"context": "banking"},
        {"start_offset": "100", "end_offset": "102"},
        {"start_offset": "7", "end_offset": "8"},
        {"entity_value": "50"},
    ],
)
def test_source_contradictions_are_not_repaired(change: dict[str, str]) -> None:
    original = row("refund $25", "25", **change)
    before = deepcopy(original)
    result = inspect_row(original, 3)
    assert result["proposed_direct_request_candidate"] is False
    assert result["proposed_requested_minor"] is None
    assert result["exclusion_reasons"]
    assert original == before


def test_exact_decimal_without_rounding_and_no_sim_conversion() -> None:
    result = inspect_row(row("reimburse $0.01", "0.01"), 1)
    assert result["proposed_requested_minor"] == 1
    assert result["proposed_currency_lexeme"] == "$"
    assert result["proposed_iso_currency"] is None


def test_native_tag_must_be_the_full_requested_number() -> None:
    result = inspect_row(row("refund $125", "25"), 1)
    assert result["offset_exact"] is True
    assert result["proposed_direct_request_candidate"] is False
    assert "native_tag_not_direct_requested_number" in result["exclusion_reasons"]
