"""Draft project partitions with native split provenance and conservative lexical linkage.

Connected groups precede assignment and exposure exclusion. Lexical similarity is a
declared approximation: no assertion of semantic-family or statistical independence.
"""

import re
from collections import Counter, defaultdict
from typing import Annotated, Literal, Self

from agent_harness.contracts import Contract, NonEmpty
from agent_harness.release_contracts import Sha256, pin, sha256
from pydantic import Field, model_validator

from olist_support.reference_audit import (
    ExposureIndex,
    NativeSplit,
    ReferenceAudit,
    Route,
    text_pin,
)

ProjectSplit = Literal["development", "regression", "holdout", "excluded"]


class ExposureTexts(Contract):
    exposure_sha256: Sha256
    texts: Annotated[tuple[NonEmpty, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique(self) -> Self:
        hashes = [text_pin(t) for t in self.texts]
        if len(set(hashes)) != len(hashes):
            raise ValueError("one text per exposed normalized-text identity required")
        return self


class PartitionEntry(Contract):
    source_id: NonEmpty
    frame_sha256: Sha256
    native_split: NativeSplit
    proposed_route: Route | None
    project_split: ProjectSplit
    connected_group: Sha256
    exclusions: tuple[NonEmpty, ...]


class ProjectPartitions(Contract):
    version: Literal["olist-reference-project-partitions-v1"] = (
        "olist-reference-project-partitions-v1"
    )
    audit_sha256: Sha256
    exposure_sha256: Sha256
    exposure_texts_sha256: Sha256
    preparation_authorization_ref: NonEmpty
    assignment: Literal["sha256_group_percent_20_development_20_regression_60_holdout_v1"] = (
        "sha256_group_percent_20_development_20_regression_60_holdout_v1"
    )
    linkage: Literal["native_id_exact_normalized_or_token_jaccard_at_least_four_fifths"] = (
        "native_id_exact_normalized_or_token_jaccard_at_least_four_fifths"
    )
    entries: tuple[PartitionEntry, ...]
    native_splits_retained_as_metadata: Literal[True] = True
    labels_accepted: Literal[False] = False
    independence_validated: Literal[False] = False
    frozen_for_provider: Literal[False] = False
    release_allowed: Literal[False] = False


def partition(
    audit: ReferenceAudit,
    exposure: ExposureIndex,
    exposed: ExposureTexts,
    *,
    authorization_ref: str,
) -> ProjectPartitions:
    audit = ReferenceAudit.model_validate_json(audit.canonical_json())
    exposure = ExposureIndex.model_validate_json(exposure.canonical_json())
    exposed = ExposureTexts.model_validate_json(exposed.canonical_json())
    if pin(exposure) != audit.exposure_sha256 or exposed.exposure_sha256 != pin(exposure):
        raise ValueError("project partition exposure binding differs")
    if {text_pin(t) for t in exposed.texts} != set(exposure.normalized_text_sha256):
        raise ValueError("complete exposed-text inventory is required for lexical linkage")
    # Include excluded mapped records, so an excluded intermediary cannot split a family.
    frames = [
        f
        for f in audit.frames
        if f.proposed_route is not None or f.source_id in exposure.source_ids
    ]
    nodes = [("source:" + f.source_id, f.input.request) for f in frames]
    nodes.extend(("exposed:" + text_pin(t), t) for t in exposed.texts)
    parents = {key: key for key, _ in nodes}

    def find(key: str) -> str:
        while parents[key] != key:
            parents[key] = parents[parents[key]]
            key = parents[key]
        return key

    signatures: list[frozenset[str]] = []
    normalized: list[str] = []
    for key, text in nodes:
        signature = frozenset(re.findall(r"\w+", text.casefold()))
        fingerprints = text_pin(text)
        for previous, other in enumerate(signatures):
            if fingerprints == normalized[previous] or (
                signature
                and other
                and min(len(signature), len(other)) * 5 >= max(len(signature), len(other)) * 4
                and len(signature & other) * 5 >= len(signature | other) * 4
            ):
                parents[find(nodes[previous][0])] = find(key)
        signatures.append(signature)
        normalized.append(fingerprints)
    members: dict[str, list[str]] = defaultdict(list)
    for key, _ in nodes:
        members[find(key)].append(key)
    identities = {
        root: sha256("\n".join(sorted(values)).encode()) for root, values in members.items()
    }
    exposed_groups = {find("exposed:" + text_pin(t)) for t in exposed.texts}
    exposed_groups.update(
        find("source:" + f.source_id) for f in frames if f.source_id in exposure.source_ids
    )
    results = []
    for frame in audit.frames:
        key = "source:" + frame.source_id
        # Unmapped goals remain explicitly excluded, rather than receiving invented labels.
        root = find(key) if key in parents else key
        identity = identities.get(root, sha256(key.encode()))
        reasons = [r for r in frame.exclusions if r != "normalized_text_crosses_native_splits"]
        if root in exposed_groups:
            reasons.append("connected_to_previous_exposure")
        percent = int(sha256(("olist-project-partition-v1|" + identity).encode()), 16) % 100
        split: ProjectSplit = (
            "excluded"
            if reasons
            else "development"
            if percent < 20
            else ("regression" if percent < 40 else "holdout")
        )
        results.append(
            PartitionEntry(
                source_id=frame.source_id,
                frame_sha256=pin(frame),
                native_split=frame.source_split,
                proposed_route=frame.proposed_route,
                project_split=split,
                connected_group=identity,
                exclusions=tuple(reasons),
            )
        )
    return ProjectPartitions(
        audit_sha256=pin(audit),
        exposure_sha256=pin(exposure),
        exposure_texts_sha256=pin(exposed),
        preparation_authorization_ref=authorization_ref,
        entries=tuple(results),
    )


def summarize_partitions(value: ProjectPartitions) -> dict[str, object]:
    value = ProjectPartitions.model_validate_json(value.canonical_json())
    groups: dict[str, set[str]] = defaultdict(set)
    for entry in value.entries:
        if entry.project_split != "excluded":
            groups[entry.connected_group].add(entry.project_split)
    if any(len(splits) != 1 for splits in groups.values()):
        raise ValueError("connected project group crosses partitions")
    return {
        "version": value.version,
        "audit_sha256": value.audit_sha256,
        "rows_by_project_split": dict(
            sorted(Counter(e.project_split for e in value.entries).items())
        ),
        "connected_groups_by_project_split": {
            split: sum(split in splits for splits in groups.values())
            for split in ("development", "regression", "holdout")
        },
        "native_splits_retained_as_metadata": True,
        "labels_accepted": False,
        "rows_by_project_and_proposed_route": dict(
            sorted(
                Counter(
                    e.project_split + ":" + (e.proposed_route or "unmapped") for e in value.entries
                ).items()
            )
        ),
        "groups_by_project_and_proposed_route": {
            split + ":" + route: len(
                {
                    e.connected_group
                    for e in value.entries
                    if e.project_split == split and e.proposed_route == route
                }
            )
            for split in ("development", "regression", "holdout")
            for route in ("refund", "status", "unsupported")
        },
        "independence_validated": False,
        "frozen_for_provider": False,
        "release_allowed": False,
    }


def verify_partitions(
    value: ProjectPartitions, audit: ReferenceAudit, exposure: ExposureIndex, texts: ExposureTexts
) -> None:
    expected = partition(
        audit, exposure, texts, authorization_ref=value.preparation_authorization_ref
    )
    if expected.canonical_json() != value.canonical_json():
        raise ValueError(
            "project partitions differ from deterministic source/exposure recomputation"
        )
