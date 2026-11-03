"""Pinned Bitext instruction-level reference preparation, without gold or release authority.

The source supplies hybrid-synthetic instruction labels, not requested amounts, seed IDs
or a native holdout. Copied annotations and proposed workflow mappings remain distinct.
"""

import argparse
import csv
import io
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Annotated, Literal, Self

from agent_harness.contracts import AgentInput, Contract, NonEmpty
from agent_harness.release_contracts import Sha256, pin, sha256
from agent_harness.trials import _write_exclusive
from pydantic import Field, model_validator

from olist_support.policy_cases import external
from olist_support.reference_audit import ExposureIndex, text_pin
from olist_support.reference_audit_cli import read_bytes

MAX_CSV = 32 * 1024 * 1024
COLUMNS = ("flags", "instruction", "category", "intent", "response")
Revision = Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]
Route = Literal["refund", "status", "unsupported"]
MAPPING: dict[str, tuple[str, Route]] = {
    "get_refund": ("REFUND", "refund"),
    "track_order": ("ORDER", "status"),
    "track_refund": ("REFUND", "unsupported"),
    "check_refund_policy": ("REFUND", "unsupported"),
    "change_shipping_address": ("SHIPPING", "unsupported"),
    "recover_password": ("ACCOUNT", "unsupported"),
}


def template_pin(text: str) -> str:
    normalized = " ".join(text.casefold().split())
    normalized = re.sub(r"\{\{[^{}]+\}\}", "{slot}", normalized)
    return sha256(re.sub(r"\d+", "{number}", normalized).encode())


class UtteranceFrame(Contract):
    source_revision: Revision
    source_csv_sha256: Sha256
    source_ordinal: Annotated[int, Field(gt=0)]
    source_row_sha256: Sha256
    input: AgentInput
    native_intent: NonEmpty
    native_category: NonEmpty
    native_flags: NonEmpty
    normalized_text_sha256: Sha256
    lexical_template_sha256: Sha256
    unresolved_slots: tuple[NonEmpty, ...]
    full_service_reference_blockers: tuple[
        Literal["requested_amount_reference_unestablished", "unresolved_source_slots"], ...
    ]
    proposed_route: Route | None
    exclusions: tuple[NonEmpty, ...]
    source_kind: Literal["publisher_hybrid_synthetic"] = "publisher_hybrid_synthetic"
    annotation_unit: Literal["individual_instruction"] = "individual_instruction"
    amount_reference_status: Literal["not_supplied_or_validated"] = "not_supplied_or_validated"
    mapping_accepted: Literal[False] = False
    semantic_gold_validated: Literal[False] = False
    independence_validated: Literal[False] = False
    frozen_for_provider: Literal[False] = False
    release_allowed: Literal[False] = False

    @model_validator(mode="after")
    def exact_projection(self) -> Self:
        mapping = MAPPING.get(self.native_intent)
        if (
            self.input.observations
            or text_pin(self.input.request) != self.normalized_text_sha256
            or template_pin(self.input.request) != self.lexical_template_sha256
            or self.unresolved_slots != tuple(re.findall(r"\{\{[^{}]+\}\}", self.input.request))
            or self.proposed_route != (mapping[1] if mapping else None)
            or self.full_service_reference_blockers
            != (
                "requested_amount_reference_unestablished",
                *(("unresolved_source_slots",) if self.unresolved_slots else ()),
            )
        ):
            raise ValueError("instruction-only projection or proposed mapping differs")
        return self


class UtteranceAudit(Contract):
    version: Literal["olist-bitext-utterance-preparation-v2"] = (
        "olist-bitext-utterance-preparation-v2"
    )
    source_revision: Revision
    source_csv_sha256: Sha256
    exposure_sha256: Sha256
    mapping_sha256: Sha256
    frames: Annotated[tuple[UtteranceFrame, ...], Field(min_length=1)]
    native_partitions_supplied: Literal[False] = False
    seed_or_author_ids_supplied: Literal[False] = False
    benchmark_source_accepted: Literal[False] = False
    release_allowed: Literal[False] = False

    @model_validator(mode="after")
    def bindings(self) -> Self:
        if (
            self.mapping_sha256 != mapping_pin()
            or tuple(f.source_ordinal for f in self.frames) != tuple(range(1, len(self.frames) + 1))
            or any(
                f.source_revision != self.source_revision
                or f.source_csv_sha256 != self.source_csv_sha256
                for f in self.frames
            )
        ):
            raise ValueError("duplicate, reordered or foreign instruction frame/mapping")
        return self


def mapping_pin() -> str:
    return sha256(json.dumps(MAPPING, sort_keys=True, separators=(",", ":")).encode())


def audit_csv(
    raw: bytes, expected_sha256: str, source_revision: str, exposure: ExposureIndex
) -> UtteranceAudit:
    exposure = ExposureIndex.model_validate_json(exposure.canonical_json())
    if len(raw) > MAX_CSV or sha256(raw) != expected_sha256:
        raise ValueError("source CSV differs from external pin or size limit")
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline=""), strict=True)
    if tuple(reader.fieldnames or ()) != COLUMNS:
        raise ValueError("native instruction CSV schema differs")
    frames = []
    labels: dict[str, set[str]] = defaultdict(set)
    exposed = set(exposure.normalized_text_sha256)
    for ordinal, row in enumerate(reader, 1):
        if (
            ordinal > 100_000
            or set(row) != set(COLUMNS)
            or any(not isinstance(v, str) or not v.strip() or len(v) > 65536 for v in row.values())
        ):
            raise ValueError("native CSV row is empty, malformed or exceeds row limit")
        text = row["instruction"]
        if len(text) > 8192:
            raise ValueError("native instruction exceeds application input bound")
        normalized = text_pin(text)
        mapping = MAPPING.get(row["intent"])
        slots = tuple(re.findall(r"\{\{[^{}]+\}\}", text))
        exclusions = []
        if mapping is None:
            exclusions.append("native_intent_not_mapped")
        elif row["category"] != mapping[0]:
            exclusions.append("native_category_differs_from_mapping")
        if normalized in exposed:
            exclusions.append("previously_exposed_normalized_text")
        labels[normalized].add(row["intent"])
        frames.append(
            UtteranceFrame(
                source_revision=source_revision,
                source_csv_sha256=expected_sha256,
                source_ordinal=ordinal,
                source_row_sha256=sha256(
                    json.dumps(
                        row, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                    ).encode()
                ),
                input=AgentInput(request=text),
                native_intent=row["intent"],
                native_category=row["category"],
                native_flags=row["flags"],
                normalized_text_sha256=normalized,
                lexical_template_sha256=template_pin(text),
                unresolved_slots=slots,
                full_service_reference_blockers=(
                    "requested_amount_reference_unestablished",
                    *(("unresolved_source_slots",) if slots else ()),
                ),
                proposed_route=mapping[1] if mapping else None,
                exclusions=tuple(exclusions),
            )
        )
    return UtteranceAudit(
        source_revision=source_revision,
        source_csv_sha256=expected_sha256,
        exposure_sha256=pin(exposure),
        mapping_sha256=mapping_pin(),
        frames=tuple(
            f.model_copy(update={"exclusions": (*f.exclusions, "conflicting_native_text_labels")})
            if len(labels[f.normalized_text_sha256]) > 1
            else f
            for f in frames
        ),
    )


def summary(audit: UtteranceAudit) -> dict[str, object]:
    audit = UtteranceAudit.model_validate_json(audit.canonical_json())
    return {
        "version": audit.version,
        "source_revision": audit.source_revision,
        "source_csv_sha256": audit.source_csv_sha256,
        "exposure_sha256": audit.exposure_sha256,
        "mapping_sha256": audit.mapping_sha256,
        "source_rows": len(audit.frames),
        "rows_by_native_intent": dict(
            sorted(Counter(f.native_intent for f in audit.frames).items())
        ),
        "proposed_route_counts": dict(
            sorted(Counter(f.proposed_route or "unmapped" for f in audit.frames).items())
        ),
        "unexcluded_intent_proposal_counts": dict(
            sorted(Counter(f.proposed_route for f in audit.frames if not f.exclusions).items())
        ),
        "slot_free_unexcluded_proposal_counts": dict(
            sorted(
                Counter(
                    f.proposed_route
                    for f in audit.frames
                    if not f.exclusions and not f.unresolved_slots
                ).items()
            )
        ),
        "full_service_reference_blockers": dict(
            sorted(
                Counter(r for f in audit.frames for r in f.full_service_reference_blockers).items()
            )
        ),
        "exclusion_counts": dict(
            sorted(Counter(r for f in audit.frames for r in f.exclusions).items())
        ),
        "normalized_text_buckets": len({f.normalized_text_sha256 for f in audit.frames}),
        "lexical_template_buckets_not_independent_families": len(
            {f.lexical_template_sha256 for f in audit.frames}
        ),
        "native_partitions_supplied": False,
        "seed_or_author_ids_supplied": False,
        "semantic_gold_validated": False,
        "amount_reference_established": False,
        "benchmark_source_accepted": False,
        "provider_calls": 0,
        "frozen_for_provider": False,
        "release_allowed": False,
    }


def verify(
    audit: UtteranceAudit, raw: bytes, expected_sha256: str, exposure: ExposureIndex
) -> None:
    expected = audit_csv(raw, expected_sha256, audit.source_revision, exposure)
    if expected.canonical_json() != audit.canonical_json():
        raise ValueError("utterance audit differs from pinned source/exposure recomputation")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--exposure", type=Path, required=True)
    parser.add_argument("--exposure-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        from agent_harness.cases import _unique_object

        raw_exposure = read_bytes(args.exposure, 1_000_000)
        json.loads(raw_exposure, object_pairs_hook=_unique_object)
        exposure = ExposureIndex.model_validate_json(raw_exposure)
        if pin(exposure) != args.exposure_sha256:
            raise ValueError("exposure canonical pin differs")
        value = audit_csv(
            read_bytes(args.source, MAX_CSV), args.source_sha256, args.source_revision, exposure
        )
        output = external(args.output)
        output.mkdir(mode=0o700)
        report = summary(value)
        _write_exclusive(output / "audit.json", value.canonical_json())
        _write_exclusive(output / "summary.json", json.dumps(report, sort_keys=True, indent=2))
        _write_exclusive(output / "pin.json", json.dumps({"audit_sha256": pin(value)}))
        print(json.dumps(report, sort_keys=True))
        return 0
    except (ValueError, OSError, csv.Error, TypeError):
        print("Utterance reference preparation refused; source content withheld.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    from agent_harness.replay_example import _deny_network

    sys.addaudithook(_deny_network)
    raise SystemExit(main())
