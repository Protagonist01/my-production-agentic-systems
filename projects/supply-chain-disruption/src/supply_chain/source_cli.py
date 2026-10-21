"""Explicit offline source commands; no network or raw-source stdout."""

import argparse
import json
import sqlite3
from collections.abc import Sequence
from pathlib import Path

from supply_chain.source import capture_weather, prepare, verify


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("prepare", "verify"):
        sub = commands.add_parser(command)
        for name in ("dataco", "description", "nws", "output"):
            sub.add_argument("--" + name, type=Path, required=True)
        if command == "prepare":
            sub.add_argument("--source-pin", type=Path, required=True)
            sub.add_argument("--source-pin-sha256", required=True)
        else:
            sub.add_argument("--manifest-sha256", required=True)
    capture = commands.add_parser("capture-weather")
    capture.add_argument("--output", type=Path, required=True)
    capture.add_argument("--user-agent", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "capture-weather":
            receipt = capture_weather(args.output, args.user_agent)
            result = {"captured": True, "alerts": receipt["alerts"], "sha256": receipt["sha256"]}
        elif args.command == "prepare":
            result = prepare(
                args.dataco,
                args.description,
                args.nws,
                args.source_pin,
                args.source_pin_sha256,
                args.output,
            )
            result = {
                "prepared": True,
                "shipment_lines": result["counts"]["shipment_lines"],
                "alerts": result["alerts"],
                "causal_join": False,
            }
        else:
            result = verify(
                args.output, args.manifest_sha256, args.dataco, args.description, args.nws
            )
    except (ValueError, OSError, sqlite3.Error, KeyError, TypeError):
        parser.exit(2, "Source preparation/verification failed; private details omitted.\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
