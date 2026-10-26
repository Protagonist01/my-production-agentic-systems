"""Pinned, network-denied planning checks; no reservation, dispatch or release authority."""

import argparse
import json
import sys
from pathlib import Path

from agent_harness.cases import _unique_object
from agent_harness.contracts import WireContract
from agent_harness.evaluation_planning import (
    AllowanceSnapshots,
    AttemptPlan,
    EvidenceMatrix,
    forecast_attempts,
    validate_matrix,
)
from agent_harness.evaluation_standards import StandardProfile
from agent_harness.release_contracts import pin


def read[T: WireContract](path: Path, cls: type[T], expected: str | None = None) -> T:
    with path.open("rb") as stream:
        payload = stream.read(1_000_001)
    if len(payload) > 1_000_000:
        raise ValueError("planning input too large")
    json.loads(payload, object_pairs_hook=_unique_object)
    value = cls.model_validate_json(payload)
    if expected is not None and pin(value) != expected:
        raise ValueError("planning input differs from supplied pin")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    matrix = commands.add_parser("matrix")
    matrix.add_argument("--matrix", required=True, type=Path)
    matrix.add_argument("--matrix-sha256", required=True)
    matrix.add_argument("--profiles", required=True, type=Path)
    forecast = commands.add_parser("forecast")
    for name in ("plan", "snapshots"):
        forecast.add_argument("--" + name, required=True, type=Path)
        forecast.add_argument("--" + name + "-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "matrix":
            proposal = read(args.matrix, EvidenceMatrix, args.matrix_sha256)
            profiles = tuple(
                read(path, StandardProfile) for path in sorted(args.profiles.glob("*.json"))
            )
            count = validate_matrix(proposal, profiles)
            print(json.dumps({"pending_fields": count, "release_allowed": False}, sort_keys=True))
            return 0
        result = forecast_attempts(
            read(args.plan, AttemptPlan, args.plan_sha256),
            read(args.snapshots, AllowanceSnapshots, args.snapshots_sha256).snapshots,
        )
        print(result.canonical_json())
        return 0 if result.fits_declared_snapshots else 1
    except (ValueError, OSError) as error:
        # Do not echo malformed inputs, source text, or filesystem paths.
        print(f"Planning check failed ({type(error).__name__}); no authorization", file=sys.stderr)
        return 1


if __name__ == "__main__":
    from agent_harness.replay_example import _deny_network

    sys.addaudithook(_deny_network)
    raise SystemExit(main())
