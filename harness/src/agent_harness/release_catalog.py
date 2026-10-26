"""Pinned aggregate report inventory; never a blended quality score or release gate."""

import json
from pathlib import Path, PurePosixPath
from typing import Literal

from agent_harness.contracts import Contract, NonEmpty
from agent_harness.release_contracts import Sha256, sha256

Scope = Literal["olist", "cfpb", "revenue-original", "revenue-sim", "prior-auth", "supply"]
VERSIONS: dict[str, str] = {
    "olist": "olist-fresh-comparison-v1",
    "cfpb": "cfpb-release-report-v1",
    "revenue-original": "revenue-original-extraction-report-v1",
    "revenue-sim": "revenue-sim-billing-report-v1",
    "prior-auth": "prior-auth-release-report-v1",
    "supply": "supply-release-report-v1",
}


class ReportPin(Contract):
    scope: Scope
    relative_path: NonEmpty
    sha256: Sha256


class ReportInventory(Contract):
    references: tuple[ReportPin, ...]


def report_catalog(root: Path, references: tuple[ReportPin, ...]) -> dict[str, object]:
    if not references or len({r.scope for r in references}) != len(references):
        raise ValueError("nonempty unique domain report scopes required")
    entries = []
    for reference in references:
        reference = ReportPin.model_validate_json(reference.canonical_json())
        relative = PurePosixPath(reference.relative_path)
        if relative.is_absolute() or any(
            p in (".", "..") or ":" in p or "\\" in p for p in relative.parts
        ):
            raise ValueError("report path must stay in the private inventory root")
        path = root.joinpath(*relative.parts)
        if root.is_symlink() or any(
            p.is_symlink() for p in (path, *path.parents) if p == root or p.is_relative_to(root)
        ):
            raise ValueError("report inventory symlink rejected")
        if not path.resolve().is_relative_to(root.resolve()) or path.stat().st_size > 20_000_000:
            raise ValueError("report path/size exceeds inventory scope")
        raw = path.read_bytes()
        if sha256(raw) != reference.sha256:
            raise ValueError("report differs from external byte pin")
        payload = json.loads(raw)
        if not isinstance(payload, dict) or payload.get("version") != VERSIONS[reference.scope]:
            raise ValueError("domain report version differs")
        if payload.get("release_allowed") is not False:
            raise ValueError("catalog accepts descriptive reports, not release authorizations")
        # Forward no report text, input IDs, private paths, labels, model outputs or arbitrary dict.
        summary = payload.get("all")
        counts = {}
        if isinstance(summary, dict):
            for name in ("scheduled", "correct", "missing", "failed", "unresolved", "completed"):
                if name in summary:
                    value = summary[name]
                    if type(value) is not int or value < 0:
                        raise ValueError("invalid aggregate report denominator")
                    counts[name] = value
        entries.append(
            dict(
                scope=reference.scope,
                version=payload["version"],
                report_sha256=reference.sha256,
                counts=counts,
                release_allowed=False,
            )
        )
    missing = sorted(set(VERSIONS) - {r.scope for r in references})
    return dict(
        version="cross-vertical-report-catalog-v1",
        entries=entries,
        missing_report_scopes=missing,
        reports_complete=not missing,
        release_allowed=False,
        blended_accuracy=None,
        limitations=(
            "Byte-pinned descriptive reports only. Independent reviews, representative cohorts, "
            "fresh receipts, methodological/state/fault gates and operations evidence require "
            "separate verification."
        ),
    )


def main() -> int:
    import argparse
    import sys

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--inventory-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        raw = args.inventory.read_bytes()
        if len(raw) > 1_000_000 or sha256(raw) != args.inventory_sha256:
            raise ValueError("inventory differs from external pin/size limit")
        inventory = ReportInventory.model_validate_json(raw)
        result = report_catalog(args.root, inventory.references)
        with args.output.open("xb") as output:
            output.write(json.dumps(result, sort_keys=True, separators=(",", ":")).encode())
        print(
            json.dumps(
                {
                    "catalog_sha256": sha256(args.output.read_bytes()),
                    "reports_complete": result["reports_complete"],
                    "release_allowed": False,
                }
            )
        )
        return 0
    except (OSError, ValueError, KeyError):
        print(
            "Report catalog refused; verify input pins, report scopes and a new output path.",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
