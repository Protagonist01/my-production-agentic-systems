"""Keep extraction errors visible separately from correct-terms arithmetic."""

from datetime import date

from agent_harness.release_contracts import sha256
from revenue_integrity.billing_contracts import Amendment
from test_revenue_reconcile import case

from revenue_billing_paths import compare_constructed
from revenue_diagnostics import fixtures, rules
from revenue_profiling import Recorder


def test_correct_and_extracted_paths_can_disagree_without_writing():
    fixture = fixtures()[0]
    meaning = rules(fixture, Recorder()).meaning
    comparison = compare_constructed(
        case(), meaning, {sha256(fixture.input.context.encode()): fixture.input.context}, Recorder()
    )
    assert comparison.correct_terms.should_be_minor == 3000
    assert comparison.extracted_terms.should_be_minor == 3000
    assert not comparison.billing_write_authorized
    raw = meaning.model_dump()
    raw["terms"][0]["value"] = 9000  # valid quote, wrong interpretation
    from revenue_assessment import Meaning

    comparison = compare_constructed(
        case(),
        Meaning.model_validate(raw),
        {sha256(fixture.input.context.encode()): fixture.input.context},
        Recorder(),
    )
    assert comparison.correct_terms.should_be_minor == 3000
    assert comparison.extracted_terms.should_be_minor == 27000
    assert comparison.correct_terms != comparison.extracted_terms


def test_unrepresented_amendments_or_exceptions_cannot_be_silently_dropped():
    fixture = fixtures()[0]
    meaning = rules(fixture, Recorder()).meaning
    documents = {sha256(fixture.input.context.encode()): fixture.input.context}
    comparison = compare_constructed(
        case(amendments=(Amendment(effective=date(2025, 1, 1), sequence=1, seats=4),)),
        meaning,
        documents,
        Recorder(),
    )
    assert comparison.extracted_terms is None
    assert comparison.correct_terms.should_be_minor == 4000
    f = fixtures()[11]
    comparison = compare_constructed(
        case(),
        rules(f, Recorder()).meaning,
        {sha256(f.input.context.encode()): f.input.context},
        Recorder(),
    )
    assert comparison.extracted_path_reason == "unrepresented_condition_or_exception"
