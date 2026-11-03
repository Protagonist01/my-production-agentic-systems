"""Network-denied private ABCD applicability audit; no dataset freeze or provider authority."""

import argparse
import json
import sys
from pathlib import Path

from agent_harness.cases import _unique_object
from agent_harness.release_contracts import pin
from agent_harness.trials import _write_exclusive

from olist_support.project_partitions import ExposureTexts, partition, summarize_partitions
from olist_support.reference_audit import MAX_ARCHIVE, ExposureIndex, audit_archive, summarize


def read_bytes(path: Path, limit: int) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ValueError("audit input must be a regular file")
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError("audit input exceeds size limit")
    return raw


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--archive-sha256", required=True)
    parser.add_argument("--exposure", type=Path, required=True)
    parser.add_argument("--exposure-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--exposed-texts", type=Path)
    parser.add_argument("--exposed-texts-sha256")
    parser.add_argument("--partition-preparation-ref")
    args = parser.parse_args(argv)
    try:
        raw_exposure = read_bytes(args.exposure, 1_000_000)
        json.loads(raw_exposure, object_pairs_hook=_unique_object)
        exposure = ExposureIndex.model_validate_json(raw_exposure)
        if pin(exposure) != args.exposure_sha256:
            raise ValueError("exposure differs from supplied canonical pin")
        audit = audit_archive(read_bytes(args.archive, MAX_ARCHIVE), args.archive_sha256, exposure)
        summary = summarize(audit)
        project = None
        supplied = (args.exposed_texts, args.exposed_texts_sha256, args.partition_preparation_ref)
        if any(x is not None for x in supplied):
            if any(x is None for x in supplied):
                raise ValueError(
                    "project partitions need complete exposure text pins and preparation reference"
                )
            raw_texts = read_bytes(args.exposed_texts, 1_000_000)
            json.loads(raw_texts, object_pairs_hook=_unique_object)
            texts = ExposureTexts.model_validate_json(raw_texts)
            if pin(texts) != args.exposed_texts_sha256:
                raise ValueError("exposed text inventory differs from supplied pin")
            project = partition(
                audit, exposure, texts, authorization_ref=args.partition_preparation_ref
            )
        args.output.mkdir(mode=0o700)  # New private directory only; never replace old evidence.
        _write_exclusive(args.output / "audit.json", audit.canonical_json())
        _write_exclusive(
            args.output / "summary.json", json.dumps(summary, sort_keys=True, indent=2)
        )
        _write_exclusive(
            args.output / "pins.json",
            json.dumps(
                {
                    "audit_sha256": pin(audit),
                    "archive_sha256": args.archive_sha256,
                    "exposure_sha256": pin(exposure),
                    "provider_calls": 0,
                    "release_allowed": False,
                },
                sort_keys=True,
                indent=2,
            ),
        )
        if project is not None:
            _write_exclusive(args.output / "partitions.json", project.canonical_json())
            project_summary = summarize_partitions(project)
            _write_exclusive(
                args.output / "partition-summary.json",
                json.dumps(project_summary, sort_keys=True, indent=2),
            )
            _write_exclusive(
                args.output / "partition-pin.json",
                json.dumps({"partitions_sha256": pin(project)}, sort_keys=True),
            )
            summary["project_partitions"] = project_summary
        print(json.dumps(summary, sort_keys=True))
        return 0
    except (ValueError, OSError, EOFError, KeyError, TypeError, StopIteration):
        print("Reference audit refused; no source text or authorization emitted.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    from agent_harness.replay_example import _deny_network

    sys.addaudithook(_deny_network)
    raise SystemExit(main())
