"""Closed stdin/stdout normalization worker; executed only in the restricted image."""

import base64
import json
import sys
from pathlib import Path
from typing import Any

from prior_auth_documents import MAX_BYTES, DocumentError, NativeTools, normalize


def main() -> None:
    output: dict[str, Any]
    try:
        raw = sys.stdin.buffer.read(14_000_001)
        if len(raw) > 14_000_000:
            raise ValueError("input size")
        value = json.loads(raw)
        if not isinstance(value, dict) or set(value) != {"format", "data"}:
            raise ValueError("closed input")
        data = base64.b64decode(value["data"], validate=True)
        if len(data) > MAX_BYTES:
            raise ValueError("input size")
        tools = NativeTools(
            Path("/usr/bin/pdfinfo"),
            Path("/usr/bin/pdftotext"),
            Path("/usr/bin/pdftoppm"),
            Path("/usr/bin/tesseract"),
            timeout_seconds=20,
        )
        document = normalize(data, value["format"], tools)
        output = {"document": document.model_dump(mode="json")}
    except DocumentError as error:
        # These are fixed normalization codes; no parser body/exception leaks.
        output = {"error": str(error)}
    except Exception:
        output = {"error": "isolated_parser_failed"}
    sys.stdout.write(json.dumps(output, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
