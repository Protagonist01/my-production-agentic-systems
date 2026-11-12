"""Bounded local document adapters. Extraction is evidence, never clinical authority.

Native executables are trusted operator configuration, not selected by attachments.
Run native parsers in an isolated worker for hostile uploads; these limits alone are
not an operating-system sandbox. No URL or attachment reference is dereferenced.
"""

import csv
import hashlib
import io
import json
import math
import os
import subprocess
import tempfile
import time
from contextlib import nullcontext
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Annotated, Literal, Self
from xml.etree import ElementTree as ET

from agent_harness.contracts import WireContract
from prior_auth.contracts import Digest, digest
from pydantic import Field, model_validator

from prior_auth_profiling import Profiler, Stage

Format = Literal["text", "ccda", "fhir", "pdf_text", "pdf_ocr"]
MAX_BYTES = 10_000_000
MAX_TEXT = 100_000
MAX_PAGES = 20


class DocumentError(ValueError):
    """Fixed error code only: parser output/clinical content must not enter logs."""


class Region(WireContract):
    page: Annotated[int, Field(ge=1, le=MAX_PAGES)]
    locator: Annotated[str, Field(min_length=1, max_length=160)]
    start: Annotated[int, Field(ge=0)]
    end: Annotated[int, Field(gt=0)]
    bbox: tuple[float, float, float, float] | None = None

    @model_validator(mode="after")
    def valid(self) -> Self:
        if self.end <= self.start:
            raise ValueError("empty region")
        if self.bbox is not None:
            x, y, x2, y2 = self.bbox
            if not all(math.isfinite(n) and n >= 0 for n in self.bbox) or x2 <= x or y2 <= y:
                raise ValueError("invalid region box")
        return self


class Document(WireContract):
    version: Literal["prior-auth-document-v2"] = "prior-auth-document-v2"
    source_sha256: Digest
    text_sha256: Digest
    format: Format
    text: Annotated[str, Field(min_length=1, max_length=MAX_TEXT)]
    regions: Annotated[tuple[Region, ...], Field(min_length=1, max_length=20_000)]
    extraction_review_required: bool

    @model_validator(mode="after")
    def pinned(self) -> Self:
        if self.text_sha256 != digest(self.text):
            raise ValueError("normalized text pin differs")
        previous = 0
        for region in self.regions:
            if region.start < previous or region.end > len(self.text):
                raise ValueError("invalid region offsets")
            previous = region.end
        return self

    def locate(self, start: int, end: int) -> tuple[Region, ...]:
        if not 0 <= start < end <= len(self.text):
            raise ValueError("citation range invalid")
        return tuple(r for r in self.regions if r.start < end and start < r.end)


def xml(raw: bytes) -> ET.Element:
    # Refuse entity expansion and external declarations before parser entry.
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper() or b"\x00" in raw:
        raise DocumentError("unsafe_xml")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        raise DocumentError("invalid_xml") from None
    if sum(1 for _ in root.iter()) > 50_000:
        raise DocumentError("xml_node_limit")
    return root


def narrative(node: ET.Element) -> str:
    # Preserve word boundaries across block/inline layout changes.
    if any(e.tag.rsplit("}", 1)[-1].lower() in {"script", "style", "iframe"} for e in node.iter()):
        raise DocumentError("active_narrative")
    return " ".join(" ".join(node.itertext()).split())


@dataclass(frozen=True)
class NativeTools:
    pdfinfo: Path
    pdftotext: Path
    pdftoppm: Path
    tesseract: Path
    timeout_seconds: int = 30
    profiler: Profiler | None = None
    document_deadline: float | None = None

    def run(self, tool: Path, args: list[str], directory: Path) -> bytes:
        stage: Stage = (
            "pdf_metadata"
            if tool == self.pdfinfo
            else "pdf_text"
            if tool == self.pdftotext
            else "pdf_raster"
            if tool == self.pdftoppm
            else "ocr"
        )
        with self.profiler.span(stage) if self.profiler else nullcontext():
            return self._run(tool, args, directory)

    def _run(self, tool: Path, args: list[str], directory: Path) -> bytes:
        if not tool.is_absolute() or not tool.is_file() or not 1 <= self.timeout_seconds <= 60:
            raise DocumentError("adapter_unavailable")
        # No shell; output goes to bounded temporary files, never to caller logs.
        with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
            process = subprocess.Popen([str(tool), *args], cwd=directory, stdout=out, stderr=err)
            deadline = time.monotonic() + self.timeout_seconds
            if self.document_deadline is not None:
                deadline = min(deadline, self.document_deadline)
            try:
                while process.poll() is None:
                    if (
                        time.monotonic() > deadline
                        or os.fstat(out.fileno()).st_size > 2_000_000
                        or os.fstat(err.fileno()).st_size > 100_000
                    ):
                        raise DocumentError("parser_resource_limit")
                    # Monitor generated page images too; never accept unbounded raster output.
                    if (
                        sum(p.stat().st_size for p in directory.iterdir() if p.is_file())
                        > 30_000_000
                    ):
                        raise DocumentError("parser_resource_limit")
                    time.sleep(0.02)
                if process.returncode or out.seek(0, 2) > 2_000_000 or err.seek(0, 2) > 100_000:
                    raise DocumentError("parser_failed")
                if sum(p.stat().st_size for p in directory.iterdir() if p.is_file()) > 30_000_000:
                    raise DocumentError("parser_resource_limit")
                out.seek(0)
                return out.read(2_000_001)
            finally:
                if process.poll() is None:
                    process.kill()
                process.wait()


def _normalize(raw: bytes, format: Format, tools: NativeTools | None = None) -> Document:
    if not raw or len(raw) > MAX_BYTES:
        raise DocumentError("document_size")
    parts: list[tuple[int, str, str, tuple[float, float, float, float] | None]] = []
    if format == "text":
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeError:
            raise DocumentError("invalid_utf8") from None
        if "\x00" in text:
            raise DocumentError("binary_text")
        parts.append((1, "text", text, None))
    elif format == "ccda":
        root = xml(raw)
        if root.tag != "{urn:hl7-org:v3}ClinicalDocument":
            raise DocumentError("unsupported_ccda")
        for i, section in enumerate(root.findall(".//{urn:hl7-org:v3}section")):
            for j, body in enumerate(section.findall("{urn:hl7-org:v3}text")):
                parts.append((1, f"section/{i}/text/{j}", narrative(body), None))
    elif format == "fhir":
        try:
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError
            resources = (
                [e["resource"] for e in data.get("entry", [])]
                if data.get("resourceType") == "Bundle"
                else [data]
            )
            if len(resources) > 100:
                raise ValueError
            for i, resource in enumerate(resources):
                if resource.get("resourceType") not in {
                    "Composition",
                    "DiagnosticReport",
                    "Observation",
                }:
                    continue
                text = resource.get("text", {}).get("div")
                if text is not None:
                    parts.append((1, f"resource/{i}/text/div", narrative(xml(text.encode())), None))
                if resource.get("resourceType") == "DiagnosticReport" and resource.get(
                    "conclusion"
                ):
                    parts.append((1, f"resource/{i}/conclusion", resource["conclusion"], None))
                sections = list(resource.get("section", []))
                seen = 0
                while sections:
                    section = sections.pop(0)
                    seen += 1
                    if seen > 100:
                        raise ValueError
                    if section.get("text", {}).get("div"):
                        parts.append(
                            (
                                1,
                                f"resource/{i}/section/{seen}",
                                narrative(xml(section["text"]["div"].encode())),
                                None,
                            )
                        )
                    sections.extend(section.get("section", []))
        except (ValueError, TypeError, KeyError, AttributeError, RecursionError):
            raise DocumentError("unsupported_fhir") from None
    elif format in {"pdf_text", "pdf_ocr"}:
        if tools is None:
            raise DocumentError("adapter_unavailable")
        tools = replace(tools, document_deadline=time.monotonic() + 120)
        if not raw.startswith(b"%PDF-"):
            raise DocumentError("invalid_pdf")
        with tempfile.TemporaryDirectory(prefix="pa-document-") as folder:
            directory = Path(folder)
            source = directory / "input.pdf"
            source.write_bytes(raw)
            info = tools.run(tools.pdfinfo, [str(source)], directory).decode("utf-8", "replace")
            pages = next(
                (
                    int(line.split(":", 1)[1])
                    for line in info.splitlines()
                    if line.startswith("Pages:")
                ),
                0,
            )
            if not 1 <= pages <= MAX_PAGES:
                raise DocumentError("page_limit")
            if format == "pdf_text":
                result = tools.run(tools.pdftotext, ["-bbox-layout", str(source), "-"], directory)
                # Poppler emits this fixed declaration. Remove only that exact inert
                # header; other DTDs/entities remain refused and no URL is fetched.
                result = result.replace(
                    b'<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" '
                    b'"http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">',
                    b"",
                    1,
                )
                for page, node in enumerate(
                    xml(result).iter("{http://www.w3.org/1999/xhtml}page"), 1
                ):
                    for word, item in enumerate(node.iter("{http://www.w3.org/1999/xhtml}word")):
                        box = tuple(float(item.attrib[k]) for k in ("xMin", "yMin", "xMax", "yMax"))
                        parts.append(
                            (
                                page,
                                f"word/{word}",
                                item.text or "",
                                (box[0], box[1], box[2], box[3]),
                            )
                        )
            else:
                for page in range(1, pages + 1):
                    image = directory / "page"
                    tools.run(
                        tools.pdftoppm,
                        [
                            "-f",
                            str(page),
                            "-l",
                            str(page),
                            "-scale-to",
                            "1600",
                            "-singlefile",
                            "-png",
                            str(source),
                            str(image),
                        ],
                        directory,
                    )
                    result = tools.run(
                        tools.tesseract,
                        [str(image.with_suffix(".png")), "stdout", "--psm", "6", "tsv"],
                        directory,
                    )
                    for word, row in enumerate(
                        csv.DictReader(io.StringIO(result.decode()), delimiter="\t")
                    ):
                        if row["text"].strip():
                            x, y, w, h = (float(row[k]) for k in ("left", "top", "width", "height"))
                            parts.append(
                                (page, f"ocr-word/{word}", row["text"], (x, y, x + w, y + h))
                            )
    else:
        raise DocumentError("unsupported_format")
    text = ""
    regions: list[Region] = []
    for page, locator, content, bbox in parts:
        content = content.strip()
        if not content:
            continue
        start = len(text) + bool(text)
        text += (" " if text else "") + content
        if len(text) > MAX_TEXT or len(regions) >= 20_000:
            raise DocumentError("text_limit")
        regions.append(Region(page=page, locator=locator, start=start, end=len(text), bbox=bbox))
    if not text:
        raise DocumentError("no_supported_narrative")
    return Document(
        source_sha256=hashlib.sha256(raw).hexdigest(),
        text_sha256=digest(text),
        format=format,
        text=text,
        regions=tuple(regions),
        extraction_review_required=format in {"pdf_text", "pdf_ocr"},
    )


def normalize(raw: bytes, format: Format, tools: NativeTools | None = None) -> Document:
    try:
        return _normalize(raw, format, tools)
    except DocumentError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError, OSError, RecursionError):
        raise DocumentError("invalid_document") from None
