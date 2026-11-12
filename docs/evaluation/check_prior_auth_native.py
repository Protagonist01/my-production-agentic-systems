"""Required native Poppler/Tesseract canaries on invented text and image-only PDFs."""

import re
import shutil
import sys
import tempfile
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from prior_auth_documents import DocumentError, NativeTools, normalize  # noqa: E402


def pdf(objects: list[bytes]) -> bytes:
    output, offsets = b"%PDF-1.4\n", [0]
    for index, value in enumerate(objects, 1):
        offsets.append(len(output))
        output += f"{index} 0 obj\n".encode() + value + b"\nendobj\n"
    xref = len(output)
    output += f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode()
    output += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:])
    output += (
        f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return output


def text_pdf(pages: int = 1) -> bytes:
    stream = (
        b"BT /F1 24 Tf 50 720 Td (AHI: 18 events/hour.) Tj 0 -40 Td (Invented sleep report.) Tj ET"
    )
    kids = " ".join(f"{5 + index} 0 R" for index in range(pages))
    page = (
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 3 0 R >> >> /Contents 4 0 R >>"
    )
    return pdf(
        [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            f"<< /Type /Pages /Count {pages} /Kids [{kids}] >>".encode(),
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
            f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream",
        ]
        + [page] * pages
    )


def image_pdf(ppm: bytes) -> bytes:
    header = re.match(rb"P6\s+(\d+)\s+(\d+)\s+255\s", ppm)
    if header is None:
        raise ValueError("canary raster header differs")
    w, h = int(header[1]), int(header[2])
    pixels = ppm[header.end() :]
    assert len(pixels) == w * h * 3
    image = zlib.compress(pixels)
    stream = b"q 612 0 0 792 0 0 cm /Im0 Do Q"
    return pdf(
        [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Count 1 /Kids [3 0 R] >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /XObject << /Im0 4 0 R >> >> /Contents 5 0 R >>",
            (
                f"<< /Type /XObject /Subtype /Image /Width {w} /Height {h} "
                "/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /FlateDecode "
                f"/Length {len(image)} >>\n"
                "stream\n"
            ).encode()
            + image
            + b"\nendstream",
            f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream",
        ]
    )


def main() -> None:
    names = ("pdfinfo", "pdftotext", "pdftoppm", "tesseract")
    found = [shutil.which(name) for name in names]
    if not all(found):
        raise SystemExit("required native document tools unavailable")
    tools = NativeTools(*(Path(tool).resolve() for tool in found if tool))
    with tempfile.TemporaryDirectory(prefix="pa-native-canary-") as temp:
        directory = Path(temp)
        source = directory / "text.pdf"
        source.write_bytes(text_pdf())
        text = normalize(source.read_bytes(), "pdf_text", tools)
        assert "AHI: 18 events/hour." in text.text
        assert text.regions[0].bbox and text.regions[0].page == 1
        tools.run(
            tools.pdftoppm,
            ["-singlefile", "-scale-to", "1600", str(source), str(directory / "scan")],
            directory,
        )
        scanned = image_pdf((directory / "scan.ppm").read_bytes())
        try:
            normalize(scanned, "pdf_text", tools)
        except DocumentError as error:
            assert str(error) == "no_supported_narrative"
        else:
            raise AssertionError("image-only PDF unexpectedly has an extractable text layer")
        ocr = normalize(scanned, "pdf_ocr", tools)
        assert "AHI:" in ocr.text and "18" in ocr.text and ocr.extraction_review_required
        assert ocr.regions[0].bbox and ocr.regions[0].locator.startswith("ocr-word/")
        try:
            normalize(text_pdf(21), "pdf_text", tools)
        except DocumentError as error:
            assert str(error) == "page_limit"
        else:
            raise AssertionError("page bound bypassed")
    print(
        "Prior Auth native canaries: text PDF, image-only OCR, source regions, page refusal passed"
    )


if __name__ == "__main__":
    main()
