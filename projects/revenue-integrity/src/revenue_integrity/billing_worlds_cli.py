"""Prepare and verify private fictional SIM worlds without invoking a reconciler."""

import argparse
import json
import sqlite3
from collections.abc import Sequence
from pathlib import Path

from revenue_integrity.billing_worlds import prepare, verify


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    make = commands.add_parser("prepare")
    make.add_argument("--output", type=Path, required=True)
    check = commands.add_parser("verify")
    check.add_argument("--output", type=Path, required=True)
    check.add_argument("--manifest-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        result = (
            prepare(args.output)
            if args.command == "prepare"
            else verify(args.output, args.manifest_sha256)
        )
    except (ValueError, OSError, KeyError, TypeError, sqlite3.DatabaseError) as error:
        print(
            json.dumps(
                {
                    "error": "billing-world preparation or verification failed",
                    "kind": type(error).__name__,
                }
            )
        )
        return 1
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
