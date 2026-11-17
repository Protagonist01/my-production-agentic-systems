"""One bounded authored regression inventory; no model and no clinical reference claim."""

from dataclasses import asdict

import pytest

from prior_auth_demo_regression import EXPECTED, execute, run, source, witnesses


@pytest.mark.parametrize("witness", witnesses(), ids=lambda w: w.case_id)
def test_declared_intake_state_route_and_citation_guards(witness):
    row = execute(witness)
    assert row["passed"], row
    assert row["provider_calls"] == 0 and not row["clinical_validation"]
    if row["expected_route"] is None:
        assert row["states"] is None


def test_pack_is_complete_repeatable_and_keeps_reference_separate():
    first, second = run(), run()
    assert first == second
    assert first["scheduled"] == first["observed"] == first["passed"] == 19
    assert first["input_manifest_sha256"] == (
        "e4c76c34ae2eaabc40b1f9768c386af5bfe7fb7a42ccd3093f9c2a3c582b9e30"
    )
    assert first["reference_sha256"] == (
        "1ab15fde8f2cb8399326b89a3e74670b80dfc63a8d1fd4d8fb84a35ec73f4df2"
    )
    assert not first["model_quality_evaluated"]
    assert {w.case_id for w in witnesses()} == set(EXPECTED)
    assert all("expected" not in str(asdict(w)) for w in witnesses())
    assert all("expected_route" not in source(w).decode() for w in witnesses())


def test_full_notes_contain_missing_quote_subconditions_but_incomplete_quotes_fail():
    for key in ("incomplete-test-quote", "incomplete-order-quote", "incomplete-adult-quote"):
        witness = next(w for w in witnesses() if w.case_id == key)
        row = execute(witness)
        assert row["states"][witness.quote_key] == "insufficient"
        assert row["reasons"][witness.quote_key] == "missing_or_unrecognized_support"
        assert row["route"] == "request_information"
