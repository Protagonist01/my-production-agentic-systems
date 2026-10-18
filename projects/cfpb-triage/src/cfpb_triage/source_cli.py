"""Explicit archived CFPB acquisition/preparation; print only aggregate evidence."""

import argparse
import json
import sqlite3
import sys
import zipfile
from collections.abc import Sequence
from pathlib import Path

from cfpb_triage.source import prepare_snapshot, verify_prepared
from cfpb_triage.source_contracts import SourcePin
from cfpb_triage.source_io import acquire_sources, digest_file, verify_sources


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("acquire", "prepare", "verify", "verify-source"))
    parser.add_argument("--source", type=Path)
    parser.add_argument("--source-pin", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--manifest-sha256")
    parser.add_argument("--code-revision")
    args = parser.parse_args(argv)
    try:
        if args.command == "verify":
            if args.output is None or args.manifest_sha256 is None:
                parser.error("verify requires --output and --manifest-sha256")
            manifest = verify_prepared(args.output, args.manifest_sha256)
            print(json.dumps({"verified": True, "prepared": manifest["prepared"]}))
            return 0
        if args.source is None or args.source_pin is None:
            parser.error("source operation requires --source and --source-pin")
        pin = SourcePin.model_validate_json(args.source_pin.read_bytes())
        if args.command == "acquire":
            acquire_sources(args.source, pin)
            print(json.dumps({"source_verified": True, "source_pin": pin.model_dump(mode="json")}))
        elif args.command == "verify-source":
            verify_sources(args.source / "source.zip", args.source / "taxonomy.pdf", pin)
            print(json.dumps({"source_verified": True}))
        else:
            if args.output is None or args.code_revision is None:
                parser.error("prepare requires --output and --code-revision")
            manifest = prepare_snapshot(
                args.source / "source.zip",
                args.source / "taxonomy.pdf",
                pin,
                args.output,
                code_revision=args.code_revision,
            )
            print(
                json.dumps(
                    {
                        "manifest_sha256": digest_file(args.output / "manifest.json"),
                        "profile": manifest["profile"],
                        "prepared": manifest["prepared"],
                    }
                )
            )
        return 0
    except (ValueError, OSError, KeyError, sqlite3.Error, zipfile.BadZipFile):
        # Do not print source rows, paths, parser values or database contents on failures.
        print(
            "CFPB source operation failed; check pins, schema and new external output.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
