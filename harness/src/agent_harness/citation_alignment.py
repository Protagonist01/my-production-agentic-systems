"""Whitespace-only quotation alignment to unique exact original spans, never meaning."""

from typing import Literal

from agent_harness.contracts import Contract
from agent_harness.evaluation_planning import EvidenceSpan
from agent_harness.release_contracts import Sha256, sha256

MAX_SOURCE_CHARS = 200_000
MAX_QUOTE_CHARS = 10_000


class AlignedQuote(Contract):
    version: Literal["whitespace-source-span-v1"] = "whitespace-source-span-v1"
    quote_sha256: Sha256
    span: EvidenceSpan
    method: Literal["exact", "whitespace_only"]
    normalization: Literal["unicode-isspace-runs-strip-v1"] = "unicode-isspace-runs-strip-v1"
    semantic_support: Literal["not_assessed"] = "not_assessed"


def _mapped(text: str) -> tuple[str, tuple[tuple[int, int], ...]]:
    chars: list[str] = []
    offsets: list[tuple[int, int]] = []
    index = 0
    while index < len(text):
        start = index
        if text[index].isspace():
            while index < len(text) and text[index].isspace():
                index += 1
            # Leading/trailing whitespace is not part of a quotation's mapped span.
            if chars and index < len(text):
                chars.append(" ")
                offsets.append((start, index))
        else:
            chars.append(text[index])
            offsets.append((index, index + 1))
            index += 1
    return "".join(chars), tuple(offsets)


def align_quote(source: str, quote: str) -> AlignedQuote:
    """Fail closed on ambiguity; preserve every non-whitespace Unicode code point.

    Repeated exact occurrences also refuse. No token-boundary, semantic, OCR, punctuation,
    case, Unicode compatibility or fuzzy matching is performed. Offsets are code points.
    """
    if type(source) is not str or type(quote) is not str:
        raise ValueError("citation source and quote must be strings")
    if not 0 < len(source) <= MAX_SOURCE_CHARS or not 0 < len(quote) <= MAX_QUOTE_CHARS:
        raise ValueError("citation size outside bounds")
    normalized, offsets = _mapped(source)
    sought, _ = _mapped(quote)
    if not sought:
        raise ValueError("quotation contains no non-whitespace text")
    first = normalized.find(sought)
    if first < 0:
        raise ValueError("quotation cannot align without changing non-whitespace characters")
    if normalized.find(sought, first + 1) >= 0:
        raise ValueError("quotation has ambiguous source occurrences")
    start = offsets[first][0]
    end = offsets[first + len(sought) - 1][1]
    original = source[start:end]
    span = EvidenceSpan(
        source_sha256=sha256(source.encode("utf-8")), start=start, end=end, text=original
    )
    if not span.verify(source):
        raise ValueError("mapped citation differs from exact original span")
    return AlignedQuote(
        quote_sha256=sha256(quote.encode("utf-8")),
        span=span,
        method="exact" if original == quote else "whitespace_only",
    )


def verify_alignment(source: str, quote: str, alignment: AlignedQuote) -> None:
    """Reconstruct the deterministic proof; a modified DTO/hash/offset cannot assert success."""
    alignment = AlignedQuote.model_validate_json(alignment.canonical_json())
    if align_quote(source, quote) != alignment:
        raise ValueError("citation alignment differs from source/quote")
