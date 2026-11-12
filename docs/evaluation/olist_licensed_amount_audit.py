"""Audit an exact licensed publisher source; proposed references never grant authority."""

import argparse
import csv
import hashlib
import io
import json
import re
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path

REVISION = "8b6ca3d9559a4a9abab94f7978fae67019215a82"
CSV = "data/train/Bitext_Sample_Customer_Support_Training_Dataset.csv"
PINS = {
    CSV: "079b0cec48d34c319c9877b6d178390bf7187a7f7a604958e0ed5a096bba5af6",
    "LICENSE.txt": "f6054388eae4947a769ca2020c54e6d394eb01c41d58db55bb6cfd24ce71cdd8",
    "README.md": "bff261543a14237450bf3c8d887c98787e80492abeb3c2d8015fded3a5f6a23d",
    "TAGS.md": "53a349c1e04467fa298b7b1e0f297339b521d80467fb20e0f4636a2e932f76ec",
}
FIELDS = (
    "context",
    "role",
    "instruction",
    "intent",
    "entity_type",
    "entity_value",
    "start_offset",
    "end_offset",
    "category",
    "tags",
    "response",
)
# These are proposed applicability conditions, not a universal English interpretation.
NUMBER = r"(?:0|[1-9][0-9]{0,15})(?:\.[0-9]{2})?"
DIRECT = re.compile(
    rf"(?:refund|reimburse) (?:\$(?P<prefix>{NUMBER})|(?P<suffix>{NUMBER}) dollars)[.!?]?",
    re.IGNORECASE,
)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def inspect_row(row: dict[str, str], ordinal: int) -> dict[str, object]:
    """Keep source spans and contradictions; never infer a null amount or repair a tag."""
    text, value = row["instruction"], row["entity_value"]
    start, end = int(row["start_offset"]), int(row["end_offset"])
    in_bounds = 0 <= start < end <= len(text)
    exact = in_bounds and text[start:end] == value
    direct = DIRECT.fullmatch(text)
    reasons = []
    if row["intent"] != "get_refund":
        reasons.append("native_intent_not_get_refund")
    # The pinned README defines role as the role the model should adopt, not the speaker.
    # It separately defines instruction as the user request. Preserve both conventions.
    if row["role"] != "virtual assistant" or row["context"] != "customer support":
        reasons.append("native_model_role_or_context_differs")
    if not exact:
        reasons.append("native_value_span_not_exact")
    if direct is None:
        reasons.append("outside_proposed_direct_request_language")
    else:
        name = "prefix" if direct.group("prefix") is not None else "suffix"
        if (start, end) != direct.span(name) or value != direct.group(name):
            reasons.append("native_tag_not_direct_requested_number")
    candidate = not reasons
    amount = int(Decimal(value) * 100) if candidate else None
    return {
        "ordinal": ordinal,
        "source_record_sha256": digest(canonical(row)),
        "input_sha256": digest(text.encode()),
        "normalized_input_sha256": digest(" ".join(text.casefold().split()).encode()),
        "native_intent": row["intent"],
        "native_role": row["role"],
        "native_role_is_model_adopted_role": True,
        "native_value": value,
        "native_start": start,
        "native_end": end,
        "offset_in_bounds": in_bounds,
        "offset_exact": exact,
        "number_masked_template_sha256": digest(
            re.sub(r"[0-9]+(?:\.[0-9]+)?", "<number>", text.casefold()).encode()
        ),
        "proposed_direct_request_candidate": candidate,
        "proposed_requested_minor": amount,
        # A dollar sign/word does not uniquely identify USD, CAD, AUD, etc.
        "proposed_currency_lexeme": (
            "$" if direct and direct.group("prefix") is not None else "dollars"
        )
        if candidate
        else None,
        "proposed_iso_currency": None,
        "iso_currency_reference_established": False,
        "amount_unit": "nominal_dollar_hundredths" if candidate else None,
        "unknown_is_no_amount_label": False,
        "exclusion_reasons": reasons,
        "method_accepted": False,
        "qualification_reference": False,
        "release_allowed": False,
    }


def audit(source: Path) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, str]]]:
    snapshot = {name: (source / name).read_bytes() for name in PINS}
    if any(digest(snapshot[name]) != pin for name, pin in PINS.items()):
        raise ValueError("publisher source/license/documentation pins differ")
    reader = csv.DictReader(io.StringIO(snapshot[CSV].decode("utf-8-sig"), newline=""))
    if tuple(reader.fieldnames or ()) != FIELDS:
        raise ValueError("native CSV schema differs")
    rows = list(reader)
    if len(rows) != 4514 or any(
        set(r) != set(FIELDS) or any(v is None for v in r.values()) for r in rows
    ):
        raise ValueError("native CSV row inventory differs")
    frames = [
        inspect_row(r, i) for i, r in enumerate(rows, 1) if r["entity_type"] == "refund_amount"
    ]
    candidates = [r for r in frames if r["proposed_direct_request_candidate"]]
    summary = {
        "version": "olist-licensed-amount-applicability-v1",
        "source_revision": REVISION,
        "source_pins": PINS,
        "native_rows": len(rows),
        "amount_annotations": len(frames),
        "exact_native_spans": sum(bool(r["offset_exact"]) for r in frames),
        "out_of_bounds_native_spans": sum(not r["offset_in_bounds"] for r in frames),
        "proposed_direct_request_candidates": len(candidates),
        "candidate_ordinals": [r["ordinal"] for r in candidates],
        "distinct_candidate_templates": len(
            {r["number_masked_template_sha256"] for r in candidates}
        ),
        "distinct_candidate_values": len({r["proposed_requested_minor"] for r in candidates}),
        "exclusions": dict(Counter(reason for r in frames for reason in r["exclusion_reasons"])),
        "license_evidence": "CDLA-Sharing-1.0_file_published_in_same_revision",
        "prior_hugging_face_permission_inferred": False,
        "annotation_repair": False,
        "source_currency_converted_to_sim": False,
        "iso_currency_reference_established": False,
        "template_groups_prove_independence": False,
        "new_method_accepted": False,
        "accepted_reference_count": 0,
        "semantic_gold_validated": False,
        "provider_calls": 0,
        "release_allowed": False,
    }
    return summary, frames, rows


def prepare(source: Path, output: Path) -> str:
    summary, frames, rows = audit(source)
    output.mkdir(exist_ok=False, parents=True)
    proposed = []
    for frame in frames:
        if not frame["proposed_direct_request_candidate"]:
            continue
        row = rows[int(str(frame["ordinal"])) - 1]
        proposed.append(
            {"input": {"text": row["instruction"]}, "native_reference": row, "proposal": frame}
        )
    files = {"summary.json": summary, "frames.json": frames, "proposed-references.json": proposed}
    pins = {}
    for name, value in files.items():
        raw = canonical(value)
        with (output / name).open("xb") as stream:
            stream.write(raw)
        pins[name] = digest(raw)
    manifest = {
        "version": "olist-licensed-amount-audit-manifest-v1",
        "files": pins,
        "source_pins": PINS,
        "script_sha256": digest(Path(__file__).read_bytes()),
        "method_accepted": False,
        "provider_calls": 0,
        "release_allowed": False,
    }
    raw = canonical(manifest)
    with (output / "manifest.json").open("xb") as stream:
        stream.write(raw)
    return digest(raw)


def verify(source: Path, output: Path, external_pin: str) -> dict[str, object]:
    raw = (output / "manifest.json").read_bytes()
    if digest(raw) != external_pin:
        raise ValueError("external manifest pin differs")
    manifest = json.loads(raw)
    if (
        manifest["script_sha256"] != digest(Path(__file__).read_bytes())
        or manifest["source_pins"] != PINS
        or manifest["method_accepted"] is not False
        or manifest["provider_calls"] != 0
        or manifest["release_allowed"] is not False
    ):
        raise ValueError("audit implementation or authority differs")
    summary, frames, rows = audit(source)
    proposed = [
        {
            "input": {"text": rows[int(str(f["ordinal"])) - 1]["instruction"]},
            "native_reference": rows[int(str(f["ordinal"])) - 1],
            "proposal": f,
        }
        for f in frames
        if f["proposed_direct_request_candidate"]
    ]
    expected = {
        "summary.json": summary,
        "frames.json": frames,
        "proposed-references.json": proposed,
    }
    if set(manifest["files"]) != set(expected):
        raise ValueError("audit file inventory differs")
    for name, value in expected.items():
        original = (output / name).read_bytes()
        if digest(original) != manifest["files"][name] or original != canonical(value):
            raise ValueError("recomputed source applicability differs")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--verify-manifest")
    args = parser.parse_args()
    if args.verify_manifest:
        print(json.dumps(verify(args.source, args.output, args.verify_manifest)))
    else:
        print(json.dumps({"manifest_sha256": prepare(args.source, args.output)}))


if __name__ == "__main__":
    if sys.flags.optimize:
        raise SystemExit("normal Python execution required")
    main()
