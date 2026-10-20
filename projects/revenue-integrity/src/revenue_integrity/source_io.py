"""Private path, archive inventory and same-buffer byte-pin verification."""

import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any

from revenue_integrity.source_contracts import SourcePin


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def external(path: Path) -> Path:
    path = path.expanduser().resolve()
    if any((parent / ".git").exists() for parent in (path, *path.parents)):
        raise ValueError("original source and evaluator storage must remain outside Git checkouts")
    return path


def load_pin(path: Path, expected_sha256: str) -> SourcePin:
    raw = path.read_bytes()
    if sha256(raw) != expected_sha256:
        raise ValueError("source manifest differs from independently supplied byte pin")
    return SourcePin.model_validate_json(raw)


def pinned_member(archive: Path, pin: SourcePin) -> bytes:
    """Hash the exact buffer opened as ZIP; do not hash one path and then reopen it."""
    import io

    archive = external(archive)
    with archive.open("rb") as file:
        raw = file.read(pin.archive_bytes + 1)
    if len(raw) != pin.archive_bytes or sha256(raw) != pin.archive_sha256:
        raise ValueError("archive size or SHA256 differs from reviewed source pin")
    with zipfile.ZipFile(io.BytesIO(raw)) as source:
        members = source.infolist()
        names = [entry.filename for entry in members]
        if len(names) != len(set(names)) or pin.member not in names:
            raise ValueError("missing or duplicate archive member")
        if any(
            entry.flag_bits & 1
            or entry.file_size > 200_000_000
            or entry.filename.startswith(("/", "\\"))
            or ".." in entry.filename.replace("\\", "/").split("/")
            for entry in members
        ):
            raise ValueError("unsafe, encrypted or oversized archive member")
        entry = source.getinfo(pin.member)
        if entry.file_size != pin.member_bytes:
            raise ValueError("source member size differs from pin")
        raw = source.read(entry)
    if sha256(raw) != pin.member_sha256:
        raise ValueError("source member differs from byte pin")
    return raw


def canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
