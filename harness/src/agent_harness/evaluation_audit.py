"""Offline CLI for a separately pinned private evaluation design and domain scores."""

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from agent_harness.cases import _unique_object
from agent_harness.evaluation_standards import (
    StandardProfile,
    StandardProtocol,
    StandardStudy,
    audit_study,
)
from agent_harness.release_contracts import pin


def read_audit(
    profile_path: Path,
    protocol_path: Path,
    study_path: Path,
    profile_pin: str,
    protocol_pin: str,
    study_pin: str,
) -> tuple[StandardProfile, StandardProtocol, StandardStudy, dict[str, object]]:
    payloads = [path.read_bytes() for path in (profile_path, protocol_path, study_path)]
    for payload in payloads:
        # Human review must not depend on which duplicate JSON key a parser selects.
        json.loads(payload, object_pairs_hook=_unique_object)
    profile = StandardProfile.model_validate_json(payloads[0])
    protocol = StandardProtocol.model_validate_json(payloads[1])
    study = StandardStudy.model_validate_json(payloads[2])
    if (pin(profile), pin(protocol), pin(study)) != (profile_pin, protocol_pin, study_pin):
        raise ValueError("evaluation inputs differ from separately supplied canonical pins")
    return profile, protocol, study, audit_study(profile, protocol, study, now=datetime.now(UTC))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("profile", "protocol", "study"):
        parser.add_argument("--" + name, required=True, type=Path)
        parser.add_argument("--" + name + "-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        _, _, _, result = read_audit(
            args.profile,
            args.protocol,
            args.study,
            args.profile_sha256,
            args.protocol_sha256,
            args.study_sha256,
        )
        # No raw input, reference labels, IDs or quoted records are written to the report.
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(result, sort_keys=True, indent=2) + "\n")
        print(
            "Evaluation audit written; "
            + (
                "methodology qualified"
                if result["methodology_qualified"]
                else "qualification blocked"
            )
            + "; no release approval"
        )
        return 0 if result["methodology_qualified"] else 1
    except (ValueError, OSError) as error:
        print(
            f"Evaluation audit failed ({type(error).__name__}); qualification blocked",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    from agent_harness.replay_example import _deny_network

    sys.addaudithook(_deny_network)
    raise SystemExit(main())
