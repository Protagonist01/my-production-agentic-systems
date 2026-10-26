"""Network-denied, pinned evaluator diagnostics; writes no approval or live configuration."""

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from agent_harness.evaluation_plan_cli import read
from agent_harness.evaluator_qualification import (
    QualificationDataset,
    QualificationProtocol,
    QualificationStudy,
    qualification_report,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("dataset", "protocol", "study"):
        parser.add_argument("--" + name, required=True, type=Path)
        parser.add_argument("--" + name + "-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = qualification_report(
            read(args.dataset, QualificationDataset, args.dataset_sha256),
            read(args.protocol, QualificationProtocol, args.protocol_sha256),
            read(args.study, QualificationStudy, args.study_sha256),
            now=datetime.now(UTC),
        )
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(result, sort_keys=True, indent=2) + "\n")
        print(
            "Evaluator diagnostics written; criteria "
            + ("met" if result["criteria_met"] else "not met")
            + "; no release or human approval"
        )
        return 0 if result["criteria_met"] else 1
    except (ValueError, OSError) as error:
        print(
            f"Evaluator diagnostics failed ({type(error).__name__}); no approval", file=sys.stderr
        )
        return 1


if __name__ == "__main__":
    from agent_harness.replay_example import _deny_network

    sys.addaudithook(_deny_network)
    raise SystemExit(main())
