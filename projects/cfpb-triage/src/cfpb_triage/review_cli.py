"""Offline private review preparation and aggregate-only deterministic baselines."""

import argparse
import json
from pathlib import Path

from pydantic import ValidationError

from cfpb_triage.baselines import consumer_report, pinned_pilot
from cfpb_triage.review import make_packet


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("packet", "consumer"):
        cmd = commands.add_parser(name)
        cmd.add_argument("--prepared", type=Path, required=True)
        cmd.add_argument("--manifest-pin", required=True)
        cmd.add_argument("--output", type=Path, required=True)
    pilot = commands.add_parser("pilot")
    for name in ("packet", "selection", "reviews"):
        pilot.add_argument("--" + name, type=Path, required=True)
        pilot.add_argument("--" + name + "-pin", required=True)
    pilot.add_argument("--reviewer", required=True)
    pilot.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "packet":
            print(
                json.dumps(
                    {
                        "packet_sha256": make_packet(args.prepared, args.manifest_pin, args.output),
                        "cases": 12,
                        "review_status": "unreviewed",
                        "outbound_provider_calls": 0,
                    }
                )
            )
            return
        if args.command == "consumer":
            result = consumer_report(args.prepared, args.manifest_pin)
        else:
            result = pinned_pilot(
                args.packet,
                args.packet_pin,
                args.selection,
                args.selection_pin,
                args.reviews,
                args.reviews_pin,
                reviewer_id=args.reviewer,
            )
        with args.output.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
        print(
            json.dumps(
                {"report": str(args.output), "outbound_provider_calls": 0, "mode": result["mode"]}
            )
        )
    except ValidationError:
        # Pydantic errors can include full private input values; keep CLI errors redacted.
        parser.error("private review artifact fails its closed schema; inspect it locally")


if __name__ == "__main__":
    main()
