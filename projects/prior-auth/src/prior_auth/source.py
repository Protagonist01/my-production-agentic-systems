"""Pinned CMS policy prose and publisher-synthetic C-CDA narrative preparation."""

import hashlib
import io
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree

from prior_auth.contracts import Span
from prior_auth.source_io import SourcePin, read_pinned

NS = "{urn:hl7-org:v3}"


class TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style"):
            self.hidden += 1
        if tag in ("p", "li", "br", "div", "h1", "h2", "h3"):
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style"):
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data: str) -> None:
        if not self.hidden:
            self.parts.append(data)


def cms_policy(path: Path, pin: SourcePin) -> str:
    if pin.provenance != "government_policy":
        raise ValueError("government policy source required")
    parser = TextParser()
    parser.feed(read_pinned(path, pin).decode("utf-8-sig"))
    text = "\n".join(
        " ".join(line.split()) for line in "".join(parser.parts).splitlines() if line.strip()
    )
    start = text.find("B.")
    marker = "Nationally Covered Indications"
    at = text.find(marker)
    if at < 0:
        raise ValueError("policy coverage section unavailable")
    start = text.rfind("\n", 0, at) + 1 if start < 0 or start > at else start
    # Keep only coverage prose before the separate CED study provisions.
    end = text.find("Coverage with Evidence Development", at)
    if end <= at or "March 13, 2008" not in text:
        raise ValueError("pinned national policy version or boundary unavailable")
    section = text[start:end].strip()
    if not 1000 <= len(section) <= 20000:
        raise ValueError("unexpected policy prose size")
    return section


def ccda_narratives(path: Path, pin: SourcePin) -> tuple[tuple[str, str], ...]:
    """Return section narratives only. Header demographics never enter candidate text."""
    if pin.provenance != "publisher_synthetic":
        raise ValueError("publisher-synthetic source required")
    raw = read_pinned(path, pin)
    results = []
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        members = archive.infolist()
        if len(members) > 1000 or len({m.filename for m in members}) != len(members):
            raise ValueError("duplicate or excessive archive members")
        if sum(m.file_size for m in members) > 500_000_000:
            raise ValueError("uncompressed archive too large")
        for member in sorted(members, key=lambda m: m.filename):
            if (
                member.flag_bits & 1
                or member.file_size > 20_000_000
                or member.filename.startswith(("/", "\\"))
                or ".." in member.filename.replace("\\", "/").split("/")
            ):
                raise ValueError("unsafe source member")
            if not member.filename.endswith(".xml"):
                continue
            document = archive.read(member)
            if b"<!DOCTYPE" in document.upper() or b"<!ENTITY" in document.upper():
                raise ValueError("DTD/entity declarations are not accepted")
            root = ElementTree.fromstring(document)
            if root.tag != NS + "ClinicalDocument":
                raise ValueError("unexpected C-CDA document")
            sections = []
            for section in root.findall(".//" + NS + "structuredBody//" + NS + "section"):
                title = section.find(NS + "title")
                body = section.find(NS + "text")
                if body is not None:
                    content = " ".join(" ".join(body.itertext()).split())
                    if content:
                        sections.append(
                            ((title.text or "Section") if title is not None else "Section")
                            + ": "
                            + content
                        )
            narrative = "\n".join(sections)
            if not narrative or len(narrative) > 100000:
                continue
            # Content identity rather than a filename containing synthetic names.
            results.append((hashlib.sha256(document).hexdigest(), narrative))
    if not results:
        raise ValueError("no bounded narrative records")
    return tuple(results)


def unique_span(text: str, quote: str) -> Span:
    if not quote or text.count(quote) != 1:
        raise ValueError("unique exact source quote required")
    at = text.index(quote)
    return Span(start=at, end=at + len(quote), quote=quote)


def matching_spans(text: str, quote: str) -> tuple[Span, ...]:
    """Retain every exact occurrence rather than guessing which duplicate was meant."""
    if not quote or len(quote) > 2000:
        raise ValueError("bounded exact quote required")
    spans = []
    at = text.find(quote)
    while at >= 0:
        spans.append(Span(start=at, end=at + len(quote), quote=quote))
        if len(spans) > 4:
            raise ValueError("too many exact quote occurrences; include more context")
        at = text.find(quote, at + 1)
    if not spans:
        raise ValueError("quote absent from pinned text")
    return tuple(spans)
