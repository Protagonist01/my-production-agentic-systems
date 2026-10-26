"""Reviewed, versioned model-call fixtures; no automatic capture or response reuse."""

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from agent_harness.contracts import Contract, NonEmpty, RunContext
from agent_harness.gateway import ModelExchange

Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Scope = tuple[str, str, str, str, str]
MAX_FIXTURE_BYTES = 16 * 1024 * 1024


def trial_scope(context: RunContext) -> Scope:
    return (
        context.run_id,
        context.tenant_id,
        context.agent_id,
        context.case_id,
        context.trial_id,
    )


class RecordingProvenance(Contract):
    """Claims supplied by the capture owner; review is not automated PII detection."""

    source_kind: Literal["original", "hybrid", "synthetic"]
    source_version: NonEmpty
    snapshot_ref: NonEmpty
    policy_version: NonEmpty
    scorer_version: NonEmpty
    content_policy: NonEmpty
    content_review_ref: NonEmpty


class Recording(Contract):
    provenance: RecordingProvenance
    exchanges: Annotated[tuple[ModelExchange, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def complete_sequences(self) -> Self:
        groups: dict[Scope, list[ModelExchange]] = {}
        for exchange in self.exchanges:
            groups.setdefault(trial_scope(exchange.context), []).append(exchange)
            context = exchange.context
            if context.mode not in ("fresh_candidate", "monitoring", "offline_fake"):
                raise ValueError("cannot record replayed calls as new capture")
            if context.mode == "offline_fake" and self.provenance.source_kind != "synthetic":
                raise ValueError("offline fake captures require synthetic provenance")
            if (
                context.versions.data_snapshot != self.provenance.snapshot_ref
                or context.versions.policy != self.provenance.policy_version
            ):
                raise ValueError("recording provenance differs from captured context")
            if (exchange.request.provider, exchange.request.model) != (
                exchange.response.provider,
                exchange.response.model,
            ):
                raise ValueError("recorded response route differs from request")
            if exchange.response.failure is None and (
                exchange.request.model_revision is not None
                and exchange.request.model_revision != exchange.response.model_revision
            ):
                raise ValueError("successful recorded response revision differs from request")
        # Require canonical allocation order per scope, not asynchronous completion order.
        for group in groups.values():
            if [row.occurrence for row in group] != list(range(1, len(group) + 1)):
                raise ValueError("recording occurrences must be contiguous and ordered from one")
            if any(row.context != group[0].context for row in group):
                raise ValueError("recorded context changes within a trial")
        if tuple(
            sorted(self.exchanges, key=lambda row: (trial_scope(row.context), row.occurrence))
        ) != (self.exchanges):
            raise ValueError("recording scopes must be in canonical order")
        return self

    def digest(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


def make_recording(
    exchanges: tuple[ModelExchange, ...], provenance: RecordingProvenance
) -> Recording:
    """Normalize allocation order while retaining every repeated call and typed outcome."""
    rows = tuple(ModelExchange.model_validate(row) for row in exchanges)
    recording = Recording(
        provenance=RecordingProvenance.model_validate(provenance),
        exchanges=tuple(sorted(rows, key=lambda row: (trial_scope(row.context), row.occurrence))),
    )
    return Recording.model_validate_json(recording.canonical_json())


class RecordingError(ValueError):
    """Safe diagnostics; malformed fixture contents are never echoed."""


def _reviewed_bytes(recording: Recording, forbidden_values: tuple[str, ...]) -> bytes:
    recording = Recording.model_validate(recording)
    text = recording.canonical_json()
    # Inspect decoded string leaves too: JSON escaping must not evade the explicit deny list.
    leaves: list[str] = []

    def collect(value: object) -> None:
        if isinstance(value, str):
            leaves.append(value)
        elif isinstance(value, dict):
            for key, child in value.items():
                collect(key)
                collect(child)
        elif isinstance(value, list):
            for child in value:
                collect(child)

    collect(json.loads(text))
    if any(not value for value in forbidden_values):
        raise RecordingError("forbidden recording values must be nonempty")
    credential = re.compile(
        r"AIza[0-9A-Za-z_-]{30,}|gsk_[0-9A-Za-z]{20,}|"
        r"(?:sk|pk)-lf-[0-9a-fA-F-]{30,}|Bearer\s+\S+|"
        r"https?://[^/\s:@]+:[^/\s@]+@",
        re.IGNORECASE,
    )
    if any(
        credential.search(leaf) or any(value in leaf for value in forbidden_values)
        for leaf in leaves
    ):
        raise RecordingError("recording content review failed: forbidden credential/value")
    data = (text + "\n").encode("utf-8")
    if len(data) > MAX_FIXTURE_BYTES:
        raise RecordingError("recording exceeds fixture byte limit")
    return data


def write_recording(
    path: Path, recording: Recording, *, forbidden_values: tuple[str, ...] = ()
) -> str:
    """Publish complete bytes without replacing any existing path, including symlinks.

    A private staging file is fsynced, then linked exclusively into the destination.
    Filesystems without hard links fail closed; this is a local fixture primitive.
    """
    data = _reviewed_bytes(recording, forbidden_values)
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".capture-", delete=False) as file:
            temporary = file.name
            file.write(data)
            file.flush()
            os.fsync(file.fileno())
        os.link(temporary, path)
    finally:
        if temporary is not None:
            os.unlink(temporary)
    return hashlib.sha256(data.rstrip(b"\n")).hexdigest()


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise RecordingError("recording contains duplicate JSON keys")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise RecordingError("recording contains a non-finite JSON value")


def load_recording(path: Path, *, expected_digest: str) -> Recording:
    """Verify a trusted external content pin before constructing a replay gateway."""
    if re.fullmatch(r"[0-9a-f]{64}", expected_digest) is None:
        raise RecordingError("recording requires a lowercase SHA-256 content pin")
    with path.open("rb") as file:
        raw = file.read(MAX_FIXTURE_BYTES + 1)
    if len(raw) > MAX_FIXTURE_BYTES:
        raise RecordingError("recording exceeds fixture byte limit")
    try:
        value = json.loads(raw, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
        # Validate via JSON to preserve strict tuple/Decimal/datetime wire semantics.
        recording = Recording.model_validate_json(json.dumps(value, allow_nan=False))
    except (ValueError, TypeError, RecursionError, UnicodeError):
        raise RecordingError("invalid or unsupported recording document") from None
    if recording.digest() != expected_digest:
        raise RecordingError("recording content differs from pinned SHA-256")
    return recording
