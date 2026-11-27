import pytest

from revenue_schedule_guard import MonthlyOrderTerms, checked_assessment


def test_clarification_refuses_saved_invoice_echo():
    answer = {
        "action": "request_information",
        "missing_fields": ["conditions", "unit_price_minor"],
        "total_minor": 4320,
        "delta_minor": 0,
        "evidence": ["USD 8.64 MRP per user-month"],
    }
    with pytest.raises(ValueError, match="unresolved assessment cannot carry"):
        checked_assessment(answer)
    valid = checked_assessment({**answer, "total_minor": None, "delta_minor": None})
    assert valid.missing_fields == ("conditions", "unit_price_minor")


def test_analysis_requires_verified_terms_and_exact_arithmetic():
    answer = {
        "action": "analyze",
        "missing_fields": [],
        "total_minor": 98916,
        "delta_minor": -1084,
        "evidence": ["USD 247.29 schedule rate", "four users"],
    }
    terms = MonthlyOrderTerms(unit_price_minor=24729, billable_users=4, issued_total_minor=100000)
    assert checked_assessment(answer, terms).delta_minor == -1084
    with pytest.raises(ValueError, match="verified order terms required"):
        checked_assessment(answer)
    with pytest.raises(ValueError, match="reported amounts disagree"):
        checked_assessment({**answer, "delta_minor": 1084}, terms)
