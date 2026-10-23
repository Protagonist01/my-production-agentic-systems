"""Verify external publisher sources and prepare private narrative/policy artifacts."""

import argparse
import hashlib
import json
from pathlib import Path

from prior_auth.policy import compile_policy
from prior_auth.source import ccda_narratives, cms_policy
from prior_auth.source_io import SourcePin, canonical, external


def load_pin(path: Path, sha256: str) -> SourcePin:
    raw = external(path).read_bytes()
    if len(raw) > 100000 or hashlib.sha256(raw).hexdigest() != sha256:
        raise ValueError("source pin bytes differ from independent expected digest")
    return SourcePin.model_validate_json(raw)


def prepare(
    archive: Path, archive_pin: SourcePin, policy_source: Path, policy_pin: SourcePin, output: Path
) -> dict[str, object]:
    output = external(output)
    if output.exists():
        raise ValueError("output exists; preserve prior preparation")
    prose = cms_policy(policy_source, policy_pin)
    policy = compile_policy(prose, policy_pin)
    narratives = ccda_narratives(archive, archive_pin)
    output.mkdir(parents=True)
    policy_bytes = policy.canonical_json().encode("utf-8")
    (output / "policy.json").write_bytes(policy_bytes)
    (output / "policy-prose.txt").write_text(prose, encoding="utf-8")
    (output / "narratives.json").write_bytes(canonical(narratives))
    report: dict[str, object] = dict(
        source_kind="publisher_synthetic",
        source_sha256=archive_pin.sha256,
        policy_source_sha256=policy_pin.sha256,
        policy_sha256=hashlib.sha256(policy_bytes).hexdigest(),
        normalized_policy_sha256=policy.text_sha256,
        bounded_narratives=len(narratives),
        sleep_related=sum(
            "sleep" in text.casefold() or "apnea" in text.casefold() for _, text in narratives
        ),
        clinical_validation=False,
        reviewer_status=policy.review_status,
        coverage_note="Bounded section narratives; not a complete record or coding catalog",
    )
    (output / "report.json").write_bytes(canonical(report))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--archive-pin", type=Path, required=True)
    parser.add_argument("--archive-pin-sha256", required=True)
    parser.add_argument("--policy-source", type=Path, required=True)
    parser.add_argument("--policy-pin", type=Path, required=True)
    parser.add_argument("--policy-pin-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = prepare(
            args.archive,
            load_pin(args.archive_pin, args.archive_pin_sha256),
            args.policy_source,
            load_pin(args.policy_pin, args.policy_pin_sha256),
            args.output,
        )
        print(json.dumps(result, sort_keys=True))
    except (ValueError, OSError) as error:
        parser.error(type(error).__name__ + "; inspect private source files and independent pins")


if __name__ == "__main__":
    main()
