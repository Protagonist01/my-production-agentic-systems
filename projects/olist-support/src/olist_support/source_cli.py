"""Create a new private Olist orders store and optional aggregate-only report."""

import argparse
import json
import sqlite3
import sys
from collections.abc import Sequence
from pathlib import Path

from agent_harness.trials import _write_exclusive

from olist_support.source import import_snapshot, source_time


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "source-manifest", "output", "repository-root"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--source-manifest-sha256", required=True)
    parser.add_argument("--observed-at", required=True, help="Source-local YYYY-MM-DD HH:MM:SS")
    parser.add_argument("--aggregate-report", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.aggregate_report is not None and args.aggregate_report.exists():
            raise ValueError("aggregate report already exists")
        result = import_snapshot(
            args.source,
            args.source_manifest,
            args.source_manifest_sha256,
            args.output,
            observed_at=source_time(args.observed_at),
            repository=args.repository_root,
        )
        text = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2)
        if args.aggregate_report is not None:
            _write_exclusive(args.aggregate_report, text + "\n")
        print(
            json.dumps(
                {
                    "orders": result["totals"]["orders"],
                    "database_sha256": result["database_sha256"],
                    "source_manifest_sha256": result["source_manifest_sha256"],
                    "quality_evaluation": False,
                }
            )
        )
        return 0
    except (ValueError, OSError, sqlite3.Error) as error:
        print(
            f"Olist import failed ({type(error).__name__}); partial private output may remain",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    from agent_harness.replay_example import _deny_network

    sys.addaudithook(_deny_network)
    raise SystemExit(main())
