"""Pinned ABCD first-message applicability audit, never a semantic gold-label oracle.

Publisher subflows are latent conversation goals. Literal anchors identify review candidates;
they cannot certify intent, absence of a requested amount, independence or release readiness.
"""

import gzip
import hashlib
import io
import json
import re
from collections import Counter, defaultdict
from typing import Annotated, Any, Literal, Self

from agent_harness.contracts import AgentInput, Contract, NonEmpty
from agent_harness.release_contracts import Sha256, pin
from pydantic import Field, model_validator

NativeSplit = Literal["train", "dev", "test"]
Route = Literal["refund", "status", "unsupported"]
VERSION: Literal["olist-abcd-reference-applicability-v1"] = "olist-abcd-reference-applicability-v1"
MAX_ARCHIVE = 64 * 1024 * 1024
MAX_EXPANDED = 512 * 1024 * 1024

PROJECTION: dict[tuple[str, str], Route] = {
    ("product_defect", "refund_initiate"): "refund",
    ("shipping_issue", "status"): "status",
    ("manage_account", "status_shipping_question"): "status",
    ("order_issue", "status_delivery_time"): "status",
    ("account_access", "recover_username"): "unsupported",
    ("account_access", "recover_password"): "unsupported",
    ("account_access", "reset_2fa"): "unsupported",
}
ANCHORS = {
    "refund": re.compile(r"\b(?:refund|money back)\b", re.I),
    "status": re.compile(
        r"\b(?:order|package|shipment|delivery|shipped|shipping|tracking)\b", re.I
    ),
    "unsupported": re.compile(
        r"\b(?:password|username|log[ -]?in|sign[ -]?in|authentication|authenticate|2fa)\b", re.I
    ),
}
CONFLICT = re.compile(
    r"\b(?:refund status|track (?:my )?refund|already refunded|refund policy|"
    r"replacement|reship|exchange|instead|either|don't|do not|not sure)\b",
    re.I,
)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def text_pin(text: str) -> str:
    """Exact normalized-text overlap only, not a semantic/template duplicate detector."""
    return digest(" ".join(text.casefold().split()).encode())


class ExposureIndex(Contract):
    source_ids: tuple[NonEmpty, ...]
    normalized_text_sha256: tuple[Sha256, ...]
    provenance_ref: NonEmpty

    @model_validator(mode="after")
    def unique(self) -> Self:
        if len(set(self.source_ids)) != len(self.source_ids) or len(
            set(self.normalized_text_sha256)
        ) != len(self.normalized_text_sha256):
            raise ValueError("duplicate exposure identity")
        return self


class LiteralAnchor(Contract):
    start: Annotated[int, Field(ge=0)]
    end: Annotated[int, Field(gt=0)]
    text: NonEmpty


class ReferenceFrame(Contract):
    version: Literal["olist-abcd-reference-applicability-v1"] = VERSION
    archive_sha256: Sha256
    source_id: NonEmpty
    source_split: NativeSplit
    source_record_sha256: Sha256
    first_customer_index: Annotated[int, Field(ge=0)]
    input: AgentInput
    native_flow: NonEmpty
    native_subflow: NonEmpty
    turn_annotation: str | None
    normalized_text_sha256: Sha256
    proposed_route: Route | None
    anchor: LiteralAnchor | None
    exclusions: tuple[NonEmpty, ...]
    reference_scope: Literal["latent_publisher_goal_not_automatically_first_message_gold"] = (
        "latent_publisher_goal_not_automatically_first_message_gold"
    )
    amount_reference_established: Literal[False] = False
    semantic_gold_validated: Literal[False] = False
    independence_validated: Literal[False] = False
    release_allowed: Literal[False] = False

    @model_validator(mode="after")
    def exact_projection(self) -> Self:
        if self.input.observations or text_pin(self.input.request) != self.normalized_text_sha256:
            raise ValueError("reference frame must project only the exact first customer message")
        if self.proposed_route != PROJECTION.get((self.native_flow, self.native_subflow)):
            raise ValueError("publisher-to-workflow projection differs")
        if self.anchor is not None and (
            not self.anchor.start < self.anchor.end <= len(self.input.request)
            or self.input.request[self.anchor.start : self.anchor.end] != self.anchor.text
            or self.proposed_route is None
            or ANCHORS[self.proposed_route].fullmatch(self.anchor.text) is None
        ):
            raise ValueError("literal applicability anchor differs")
        return self


class ReferenceAudit(Contract):
    version: Literal["olist-abcd-reference-audit-v1"] = "olist-abcd-reference-audit-v1"
    archive_sha256: Sha256
    exposure_sha256: Sha256
    frames: tuple[ReferenceFrame, ...]
    release_allowed: Literal[False] = False

    @model_validator(mode="after")
    def bound_frames(self) -> Self:
        if len({f.source_id for f in self.frames}) != len(self.frames) or any(
            f.archive_sha256 != self.archive_sha256 for f in self.frames
        ):
            raise ValueError("duplicate or foreign reference frame")
        return self


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate source JSON field")
        result[key] = value
    return result


def audit_archive(raw: bytes, expected_sha256: str, exposure: ExposureIndex) -> ReferenceAudit:
    """Verify exact separately supplied source pin, native identities, spans and overlap.

    No sampling, label acceptance, split reassignment, network or model calls occur here.
    The exposure index is a trusted supplied inventory; code cannot attest its completeness.
    """
    exposure = ExposureIndex.model_validate_json(exposure.canonical_json())
    if len(raw) > MAX_ARCHIVE or digest(raw) != expected_sha256:
        raise ValueError("source archive bytes differ from external pin or size limit")
    with gzip.GzipFile(fileobj=io.BytesIO(raw)) as archive:
        expanded = archive.read(MAX_EXPANDED + 1)
    if len(expanded) > MAX_EXPANDED:
        raise ValueError("expanded source exceeds limit")
    data = json.loads(expanded, object_pairs_hook=_unique)
    if not isinstance(data, dict) or set(data) != {"train", "dev", "test"}:
        raise ValueError("native source split inventory differs")
    seen: set[str] = set()
    frames: list[ReferenceFrame] = []
    for split in ("train", "dev", "test"):
        if not isinstance(data[split], list):
            raise ValueError("native split must be a record list")
        for record in data[split]:
            source_id = str(record["convo_id"])
            if not source_id or source_id in seen:
                raise ValueError("duplicate or empty native conversation identity")
            seen.add(source_id)
            scenario = record["scenario"]
            flow, subflow = scenario["flow"], scenario["subflow"]
            first = next(
                (i for i, t in enumerate(record["delexed"]) if t["speaker"] == "customer"), None
            )
            if first is None:
                raise ValueError("native conversation has no customer message")
            turn = record["delexed"][first]
            text = turn["text"]
            if not isinstance(text, str) or not text or len(text) > 8192:
                raise ValueError("native customer text differs from supported input shape")
            targets = turn["targets"]
            if not isinstance(targets, list) or len(targets) != 5:
                raise ValueError("native turn annotation shape differs")
            annotation = targets[0]
            if annotation is not None and not isinstance(annotation, str):
                raise ValueError("native turn intent annotation differs")
            proposed = PROJECTION.get((flow, subflow))
            match = ANCHORS[proposed].search(text) if proposed else None
            excluded = []
            if proposed is None:
                excluded.append("native_goal_outside_declared_projection")
            if annotation != subflow:
                excluded.append("turn_annotation_differs_from_scenario")
            if match is None:
                excluded.append("no_literal_scope_anchor")
            if CONFLICT.search(text):
                excluded.append("visible_conflict_requires_applicability_review")
            normalized = text_pin(text)
            if source_id in exposure.source_ids:
                excluded.append("previously_exposed_source")
            if normalized in exposure.normalized_text_sha256:
                excluded.append("previously_exposed_normalized_text")
            frames.append(
                ReferenceFrame(
                    archive_sha256=expected_sha256,
                    source_id=source_id,
                    source_split=split,
                    source_record_sha256=digest(
                        json.dumps(
                            record, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                        ).encode()
                    ),
                    first_customer_index=first,
                    input=AgentInput(request=text),
                    native_flow=flow,
                    native_subflow=subflow,
                    turn_annotation=annotation,
                    normalized_text_sha256=normalized,
                    proposed_route=proposed,
                    anchor=LiteralAnchor(start=match.start(), end=match.end(), text=match.group())
                    if match
                    else None,
                    exclusions=tuple(excluded),
                )
            )
    splits: dict[str, set[str]] = defaultdict(set)
    for frame in frames:
        splits[frame.normalized_text_sha256].add(frame.source_split)
    frames = [
        f.model_copy(
            update={"exclusions": (*f.exclusions, "normalized_text_crosses_native_splits")}
        )
        if len(splits[f.normalized_text_sha256]) > 1
        else f
        for f in frames
    ]
    return ReferenceAudit(
        archive_sha256=expected_sha256, exposure_sha256=pin(exposure), frames=tuple(frames)
    )


def summarize(audit: ReferenceAudit) -> dict[str, object]:
    """Aggregate source metadata only; review candidates are not qualified references."""
    audit = ReferenceAudit.model_validate_json(audit.canonical_json())
    counts: Counter[str] = Counter()
    exclusions: Counter[str] = Counter()
    eligible: Counter[str] = Counter()
    for frame in audit.frames:
        counts[frame.source_split + ":" + (frame.proposed_route or "unmapped")] += 1
        exclusions.update(frame.exclusions)
        if not frame.exclusions:
            eligible[frame.source_split + ":" + str(frame.proposed_route)] += 1
    return {
        "version": audit.version,
        "archive_sha256": audit.archive_sha256,
        "exposure_sha256": audit.exposure_sha256,
        "source_records": len(audit.frames),
        "native_split_route_counts": dict(sorted(counts.items())),
        "literal_review_candidate_counts": dict(sorted(eligible.items())),
        "exclusion_counts": dict(sorted(exclusions.items())),
        "normalized_text_groups": len({f.normalized_text_sha256 for f in audit.frames}),
        "new_labels_accepted": 0,
        "provider_calls": 0,
        "semantic_gold_validated": False,
        "independence_validated": False,
        "amount_reference_established": False,
        "qualification_ready": False,
        "release_allowed": False,
    }


def verify_audit(
    audit: ReferenceAudit, raw: bytes, expected_sha256: str, exposure: ExposureIndex
) -> None:
    if audit.canonical_json() != audit_archive(raw, expected_sha256, exposure).canonical_json():
        raise ValueError("reference audit differs from pinned source/exposure recomputation")
