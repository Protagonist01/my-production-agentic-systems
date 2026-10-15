"""Evaluator-only case populations, reviewed byte pins and grouped splits."""

import hashlib
import json
from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from agent_harness.contracts import Contract
from agent_harness.evaluation import EvalCase

Identifier = Annotated[str, Field(min_length=1, pattern=r"\S")]
Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Split = Literal["development", "holdout"]


class SnapshotSpec(Contract):
    reference: Identifier
    source_kind: Literal["original", "hybrid", "synthetic"]
    source_version: Identifier


class CaseEntry(Contract):
    group_id: Identifier
    split: Split
    scorer_id: Identifier
    case: EvalCase


class CaseManifest(Contract):
    manifest_id: Identifier
    version: Identifier
    case_ids: Annotated[tuple[Identifier, ...], Field(min_length=1)]
    snapshots: Annotated[tuple[SnapshotSpec, ...], Field(min_length=1)]
    entries: Annotated[tuple[CaseEntry, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def exact_population(self) -> Self:
        ids = tuple(entry.case.case_id for entry in self.entries)
        if any(not identity.strip() for identity in ids):
            raise ValueError("case IDs cannot be whitespace")
        if len(set(self.case_ids)) != len(self.case_ids) or len(set(ids)) != len(ids):
            raise ValueError("duplicate case IDs")
        if set(ids) != set(self.case_ids):
            raise ValueError("missing or unlisted case IDs")
        snapshots = {snapshot.reference: snapshot for snapshot in self.snapshots}
        if len(snapshots) != len(self.snapshots):
            raise ValueError("duplicate snapshot references")
        used = set()
        groups: dict[str, Split] = {}
        for entry in self.entries:
            case = entry.case
            snapshot = snapshots.get(case.snapshot_ref)
            if snapshot is None or (case.source_kind, case.source_version) != (
                snapshot.source_kind,
                snapshot.source_version,
            ):
                raise ValueError("incompatible snapshot provenance")
            used.add(case.snapshot_ref)
            if entry.group_id in groups and groups[entry.group_id] != entry.split:
                raise ValueError("group crosses development/holdout splits")
            groups[entry.group_id] = entry.split
        if used != set(snapshots):
            raise ValueError("unused snapshot declaration")
        return self


class ManifestPin(Contract):
    """Supply from reviewed configuration, separately from the manifest being loaded."""

    manifest_id: Identifier
    version: Identifier
    sha256: Digest


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


class LoadedManifest:
    """Retain private serialized evidence; callers get fresh deep validated copies."""

    def __init__(self, payload: bytes, pin: ManifestPin) -> None:
        pin = ManifestPin.model_validate_json(pin.canonical_json())
        if hashlib.sha256(payload).hexdigest() != pin.sha256:
            raise ValueError("manifest digest differs from reviewed pin")
        # Duplicate keys must fail, rather than letting a JSON parser choose a label.
        json.loads(payload, object_pairs_hook=_unique_object)
        manifest = CaseManifest.model_validate_json(payload)
        if (manifest.manifest_id, manifest.version) != (pin.manifest_id, pin.version):
            raise ValueError("manifest identity/version differs from reviewed pin")
        self._manifest = manifest.canonical_json()
        self._pin = pin.canonical_json()

    @property
    def manifest(self) -> CaseManifest:
        return CaseManifest.model_validate_json(self._manifest)

    @property
    def pin(self) -> ManifestPin:
        return ManifestPin.model_validate_json(self._pin)

    def entry(self, case_id: str) -> CaseEntry:
        for entry in self.manifest.entries:
            if entry.case.case_id == case_id:
                return entry
        raise ValueError("case ID absent from manifest")


def load_manifest(path: Path, pin: ManifestPin) -> LoadedManifest:
    # One read: verification and parsing cannot observe different file versions.
    return LoadedManifest(path.read_bytes(), pin)
