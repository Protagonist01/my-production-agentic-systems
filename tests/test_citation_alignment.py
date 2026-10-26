"""Invented quotations test exact mapping/refusal, never semantics or model quality."""

import pytest
from agent_harness.citation_alignment import AlignedQuote, align_quote, verify_alignment
from agent_harness.release_contracts import sha256
from pydantic import ValidationError


@pytest.mark.parametrize("gap", [" ", "\t", "\r\n", "\n \t", "\u00a0", "\u2003", "\u2028"])
def test_whitespace_only_changes_return_original_offsets_and_exact_source(gap):
    source = f"é prefix: Payment{gap}is{gap}due. suffix"
    quote = "Payment is due."
    result = align_quote(source, quote)
    assert (
        source[result.span.start : result.span.end]
        == result.span.text
        == f"Payment{gap}is{gap}due."
    )
    assert result.span.start == len("é prefix: ")
    assert result.span.verify(source)
    assert result.quote_sha256 == sha256(quote.encode())
    assert result.semantic_support == "not_assessed"
    verify_alignment(source, quote, result)


def test_quotation_edge_whitespace_does_not_expand_the_original_evidence():
    result = align_quote("\t Exact text. \r\n", "  Exact\ntext. ")
    assert result.span.text == "Exact text." and result.span.start == 2
    assert result.method == "whitespace_only"
    assert align_quote("prefix Exact text. end", "Exact text.").method == "exact"


@pytest.mark.parametrize(
    "source,quote",
    [
        ("term term", "term"),
        ("term\ntext and term text", "term text"),
        ("aaaa", "aaa"),
        ("PAYMENT", "payment"),
        ("100.00", "100,00"),
        ("payment is due", "payment is not due"),
        ("pay\u200bment", "payment"),
        ("Ａ", "A"),
        ("café", "cafe\u0301"),
        ("wordword", "word word"),
        ("one two", "onetwo"),
        ("one-two", "one two"),
        ("text", " \t\n"),
        ("", "text"),
        ("text", ""),
        ("x" * 200001, "x"),
        ("x", "x" * 10001),
    ],
    ids=[f"refusal-{i}" for i in range(17)],
)
def test_ambiguous_semantically_changed_and_unbounded_matches_refuse(source, quote):
    with pytest.raises(ValueError):
        align_quote(source, quote)


def test_alignment_proof_refuses_source_quote_offsets_and_hash_tampering():
    source, quote = "prefix One\n two. end", "One two."
    proof = align_quote(source, quote)
    for changed in (
        proof.model_copy(update={"quote_sha256": "f" * 64}),
        proof.model_copy(update={"method": "exact"}),
        proof.model_copy(update={"span": proof.span.model_copy(update={"start": 0})}),
    ):
        with pytest.raises(ValueError):
            verify_alignment(source, quote, changed)
    with pytest.raises(ValueError):
        verify_alignment(source + "!", quote, proof)
    with pytest.raises(ValueError):
        verify_alignment(source, "One  two.", proof)
    with pytest.raises(ValidationError):
        AlignedQuote.model_validate_json(
            proof.model_copy(update={"semantic_support": "verified"}).canonical_json()
        )
