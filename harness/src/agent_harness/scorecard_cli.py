"""Read pinned private journals; emit a new private JSON/Markdown report directory."""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from agent_harness.cases import ManifestPin, load_manifest
from agent_harness.fault_contracts import FaultPlan
from agent_harness.scorecard_compare import compare_batches
from agent_harness.scorecard_contracts import ReportPolicy
from agent_harness.scorecard_render import render_comparison, render_scorecard
from agent_harness.scorecards import build_scorecard
from agent_harness.trials import TrialJournal, _write_exclusive


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("manifest", "manifest-pin", "journal", "report-policy", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--code-revision", required=True)
    parser.add_argument("--fault-plan", type=Path)
    parser.add_argument("--baseline-journal", type=Path)
    parser.add_argument("--baseline-sha256")
    args = parser.parse_args(argv)
    if (args.baseline_journal is None) != (args.baseline_sha256 is None):
        parser.error("baseline journal and separately supplied digest must be paired")
    try:
        pin = ManifestPin.model_validate_json(args.manifest_pin.read_bytes())
        loaded = load_manifest(args.manifest, pin)
        policy = ReportPolicy.model_validate_json(args.report_policy.read_bytes())
        plan = (
            FaultPlan.model_validate_json(args.fault_plan.read_bytes()) if args.fault_plan else None
        )
        candidate = TrialJournal(args.journal).read(loaded, fault_plan=plan)
        report = build_scorecard(
            candidate, loaded, policy, reporter_revision=args.code_revision, fault_plan=plan
        )
        comparison = None
        if args.baseline_journal is not None:
            baseline = TrialJournal(args.baseline_journal).read(loaded, fault_plan=plan)
            comparison = compare_batches(
                baseline,
                candidate,
                loaded,
                policy,
                reporter_revision=args.code_revision,
                baseline_sha256=args.baseline_sha256,
                fault_plan=plan,
            )
        files = {
            "scorecard.json": report.canonical_json(),
            "scorecard.md": render_scorecard(report),
        }
        if comparison is not None:
            files.update(
                {
                    "comparison.json": comparison.canonical_json(),
                    "comparison.md": render_comparison(comparison),
                }
            )
        args.output.mkdir(mode=0o700)
        for name, content in files.items():
            _write_exclusive(args.output / name, content)
    except (ValueError, OSError) as error:
        print(
            f"Scorecard generation failed ({type(error).__name__}); no release decision",
            file=sys.stderr,
        )
        return 1
    print("Private scorecard written; no release decision")
    return 0


if __name__ == "__main__":
    from agent_harness.replay_example import _deny_network

    sys.addaudithook(_deny_network)
    raise SystemExit(main())
