"""External source custody and independently supplied byte pins."""

import hashlib
import json
from pathlib import Path
from typing import Annotated, Literal

from agent_harness.contracts import Contract
from pydantic import AwareDatetime, Field

from prior_auth.contracts import Digest


class SourcePin(Contract):
    url: str
    retrieved_at: AwareDatetime
    bytes: Annotated[int, Field(gt=0, le=50_000_000)]
    sha256: Digest
    publisher: str
    provenance: Literal["government_policy", "publisher_synthetic"]
    use_reference: str
    use_note: str


def external(path: Path) -> Path:
    path = path.expanduser().resolve()
    if any((parent / ".git").exists() for parent in (path, *path.parents)):
        raise ValueError("source and evaluator storage must be outside Git")
    return path


def read_pinned(path: Path, pin: SourcePin) -> bytes:
    pin = SourcePin.model_validate_json(pin.canonical_json())
    with external(path).open("rb") as source:
        data = source.read(pin.bytes + 1)
    if len(data) != pin.bytes or hashlib.sha256(data).hexdigest() != pin.sha256:
        raise ValueError("source size or SHA256 differs from independently supplied pin")
    return data


def canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
