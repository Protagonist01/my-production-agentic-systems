"""Explicit reviewed redaction spans, stable offsets and bounded note segmentation."""

import re

from prior_auth.contracts import Redaction, Span


def redact(text: str, redactions: tuple[Redaction, ...]) -> str:
    """Length-preserving masking; automatic PHI discovery is not claimed."""
    if not text or len(text) > 100000:
        raise ValueError("bounded source note required")
    ordered = sorted(redactions, key=lambda value: value.source.start)
    end = 0
    chars = list(text)
    for value in ordered:
        value.source.require(text)
        if value.source.start < end:
            raise ValueError("overlapping redaction spans")
        end = value.source.end
        for index in range(value.source.start, end):
            if chars[index] not in "\r\n":
                chars[index] = "█"
    return "".join(chars)


def segments(text: str) -> tuple[Span, ...]:
    """Line-level citation units preserve punctuation, Unicode and exact offsets."""
    result = []
    for match in re.finditer(r"[^\r\n]+", text):
        if match.group().strip():
            start = match.start()
            while start < match.end():
                end = min(start + 4000, match.end())
                if end < match.end():
                    boundary = text.rfind(" ", start, end)
                    if boundary > start:
                        end = boundary + 1
                result.append(Span(start=start, end=end, quote=text[start:end]))
                start = end
    return tuple(result)
