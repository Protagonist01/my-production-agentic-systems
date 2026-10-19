"""Fixed blind sampling and explicit provisional reviewer evidence; no model call."""

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Annotated, Any, Literal

from agent_harness.contracts import Contract, NonEmpty
from pydantic import AwareDatetime, Field

from cfpb_triage.source import read_inputs, read_targets, verify_prepared
from cfpb_triage.source_contracts import ComplaintInput, Digest, Split
from cfpb_triage.source_io import external_path

GUIDELINE: Literal["cfpb-narrative-risk-v1"] = "cfpb-narrative-risk-v1"
SEED = "cfpb-c2-blind-pilot-v1"
Risk = Literal["elevated", "routine", "uncertain"]
Ambiguity = Literal["clear", "ambiguous"]


def text_digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def rank(value: str, *, domain: str) -> str:
    return text_digest(f"{SEED}|{domain}|{value}")


class Selection(Contract):
    case_id: Digest
    group_id: Digest
    split: Split


class BlindItem(Contract):
    case_id: Digest
    narrative: NonEmpty


class EvidenceSpan(Contract):
    start: Annotated[int, Field(ge=0)]
    end: Annotated[int, Field(gt=0)]
    text: NonEmpty


class Review(Contract):
    case_id: Digest
    narrative_sha256: Digest
    guideline: Literal["cfpb-narrative-risk-v1"] = GUIDELINE
    guideline_sha256: Digest
    reviewer_id: NonEmpty
    reviewer_kind: Literal["ai", "human"]
    reviewed_at: AwareDatetime
    risk: Risk
    ambiguity: Ambiguity
    evidence: tuple[EvidenceSpan, ...]
    rationale: NonEmpty
    status: Literal["provisional"] = "provisional"
    predictions_seen: Literal[False] = False


def select_cases(targets: list[Selection], *, per_split: int = 4) -> tuple[Selection, ...]:
    if type(per_split) is not int or not 1 <= per_split <= 100:
        raise ValueError("per_split must be an integer from one to 100")
    groups: dict[str, list[Selection]] = defaultdict(list)
    ids: set[str] = set()
    for entry in targets:
        entry = Selection.model_validate_json(entry.canonical_json())
        if entry.case_id in ids:
            raise ValueError("duplicate source case")
        ids.add(entry.case_id)
        if groups[entry.group_id] and groups[entry.group_id][0].split != entry.split:
            raise ValueError("group crosses temporal splits")
        groups[entry.group_id].append(entry)
    result = []
    for split in ("development", "regression", "holdout"):
        available = [g for g, rows in groups.items() if rows[0].split == split]
        if len(available) < per_split:
            raise ValueError("insufficient distinct groups in a split")
        for group in sorted(available, key=lambda g: (rank(g, domain="group"), g))[:per_split]:
            result.append(
                min(groups[group], key=lambda r: (rank(r.case_id, domain="case"), r.case_id))
            )
    return tuple(sorted(result, key=lambda r: (rank(r.case_id, domain="presentation"), r.case_id)))


def make_packet(prepared: Path, manifest_pin: str, output: Path, *, per_split: int = 4) -> str:
    """Read verified source; write a new external blind packet without target metadata."""
    manifest = verify_prepared(prepared, manifest_pin)
    selections = select_cases(
        [
            Selection(case_id=t.case_id, group_id=t.group_id, split=t.split)
            for t in read_targets(prepared / "evaluator.sqlite")
        ],
        per_split=per_split,
    )
    wanted = {s.case_id for s in selections}
    texts: dict[str, ComplaintInput] = {
        item.case_id: item
        for item in read_inputs(prepared / "agent.sqlite")
        if item.case_id in wanted
    }
    # Recheck provenance after consuming the stores; no moving source can be sealed.
    verify_prepared(prepared, manifest_pin)
    packet = [
        BlindItem(case_id=s.case_id, narrative=texts[s.case_id].narrative) for s in selections
    ]
    output = external_path(output)
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    payload = (
        json.dumps([p.model_dump(mode="json") for p in packet], ensure_ascii=False, indent=2) + "\n"
    )
    pin = text_digest(payload)
    (output / "blind.json").write_text(payload, encoding="utf-8", newline="\n")
    (output / "selection.json").write_text(
        json.dumps(
            {
                "seed": SEED,
                "source_manifest_sha256": manifest_pin,
                "packet_sha256": pin,
                "guideline": GUIDELINE,
                "source_kind": manifest["source_kind"],
                "cases": [s.model_dump(mode="json") for s in selections],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    for path in output.iterdir():
        path.chmod(0o600)
    return pin


def validate_reviews(items: tuple[BlindItem, ...], reviews: tuple[Review, ...]) -> None:
    """No absent/extra/duplicate judgments or forged evidence spans become accepted rows."""
    lookup = {i.case_id: BlindItem.model_validate_json(i.canonical_json()) for i in items}
    if len(lookup) != len(items) or not lookup:
        raise ValueError("empty/duplicate blind inventory")
    seen: set[tuple[str, str]] = set()
    reviewers: dict[str, set[str]] = defaultdict(set)
    identities: dict[str, str] = {}
    guideline_pins: set[str] = set()
    for raw in reviews:
        r = Review.model_validate_json(raw.canonical_json())
        key = (r.case_id, r.reviewer_id)
        if key in seen or r.case_id not in lookup:
            raise ValueError("duplicate/extra review")
        seen.add(key)
        reviewers[r.reviewer_id].add(r.case_id)
        if identities.setdefault(r.reviewer_id, r.reviewer_kind) != r.reviewer_kind:
            raise ValueError("reviewer identity changes kind")
        guideline_pins.add(r.guideline_sha256)
        item = lookup[r.case_id]
        if r.narrative_sha256 != text_digest(item.narrative):
            raise ValueError("review refers to different narrative bytes")
        if r.risk == "elevated" and not r.evidence:
            raise ValueError("elevated judgment requires concrete evidence")
        for span in r.evidence:
            if span.end <= span.start or item.narrative[span.start : span.end] != span.text:
                raise ValueError("review evidence is not an exact narrative span")
    if not reviewers or any(ids != set(lookup) for ids in reviewers.values()):
        raise ValueError("every reviewer must cover the complete blind batch")
    if len(guideline_pins) != 1:
        raise ValueError("reviews use different guideline bytes")


def review_summary(items: tuple[BlindItem, ...], reviews: tuple[Review, ...]) -> dict[str, Any]:
    validate_reviews(items, reviews)
    per_case: dict[str, list[tuple[Risk, Ambiguity]]] = defaultdict(list)
    for r in reviews:
        per_case[r.case_id].append((r.risk, r.ambiguity))
    comparable = [rows for rows in per_case.values() if len(rows) > 1]
    return {
        "cases": len(items),
        "reviews": len(reviews),
        "reviewers": len({r.reviewer_id for r in reviews}),
        "human_reviews": sum(r.reviewer_kind == "human" for r in reviews),
        "status": "provisional",
        "comparable_cases": len(comparable),
        "disagreement_cases": sum(len(set(rows)) > 1 for rows in comparable)
        if comparable
        else None,
        "human_validation_established": False,
    }


def load_json(path: Path, pin: str) -> Any:
    payload = external_path(path).read_bytes()
    if hashlib.sha256(payload).hexdigest() != pin:
        raise ValueError("private review artifact differs from independently supplied pin")

    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON field")
            result[key] = value
        return result

    return json.loads(payload, object_pairs_hook=unique)
