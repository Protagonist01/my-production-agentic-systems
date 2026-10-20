"""Offline original-CUAD preparation and source-to-store verification."""

import argparse
import json
import sqlite3
import zipfile
from collections.abc import Sequence
from pathlib import Path

from revenue_integrity.source import import_corpus, verify_corpus
from revenue_integrity.source_io import load_pin


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--archive", type=Path, required=True)
    prepare.add_argument("--source-manifest", type=Path, required=True)
    prepare.add_argument("--source-manifest-sha256", required=True)
    prepare.add_argument("--output", type=Path, required=True)
    verify = commands.add_parser("verify")
    verify.add_argument("--archive", type=Path, required=True)
    verify.add_argument("--output", type=Path, required=True)
    verify.add_argument("--manifest-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            result = import_corpus(
                args.archive,
                load_pin(args.source_manifest, args.source_manifest_sha256),
                args.output,
            )
        else:
            result = verify_corpus(args.archive, args.output, args.manifest_sha256)
    except (
        ValueError,
        OSError,
        KeyError,
        TypeError,
        sqlite3.DatabaseError,
        zipfile.BadZipFile,
    ) as error:
        # Validation exceptions can include full source records; never print their payloads.
        print(
            json.dumps(
                {"error": "source preparation or verification failed", "kind": type(error).__name__}
            )
        )
        return 1
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
