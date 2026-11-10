"""Private offline reports, no key loading, network, dispatch or live allowance changes."""

import argparse
import json
from pathlib import Path

from cfpb_triage.classical import TfidfBaseline
from cfpb_triage.economics import WorkSample, economic_report
from cfpb_triage.evaluation_corpus import development_cases
from cfpb_triage.evaluation_v2 import VARIANTS, Observation, Reference, scorecard
from cfpb_triage.routing_experiments import OperatingLimits, baseline, calibrate, calibrate_cascade


def references(path: Path) -> tuple[Reference, ...]:
    return tuple(
        Reference.model_validate_json(json.dumps(row)) for row in json.loads(read_private(path))
    )


def observations(path: Path) -> tuple[Observation, ...]:
    return tuple(
        Observation.model_validate_json(json.dumps(row)) for row in json.loads(read_private(path))
    )


def read_private(path: Path) -> str:
    path = path.resolve()
    if path.stat().st_size > 50000000 or any((p / ".git").exists() for p in path.parents):
        raise ValueError("bounded private input outside Git required")
    return path.read_text(encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=("draft", "score", "baselines", "calibrate", "calibrate-cascade", "economics"),
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cases", type=Path)
    parser.add_argument("--rows", type=Path)
    parser.add_argument("--training", type=Path)
    parser.add_argument("--limits", type=Path)
    parser.add_argument("--trials", type=int, default=1)
    parser.add_argument("--scheduled-per-arm", type=int)
    parser.add_argument("--scope-threshold", type=float)
    args = parser.parse_args()
    # Raw draft data may only be written outside Git worktrees, never auto-published.
    target = args.output.resolve()
    if any((p / ".git").exists() for p in (target.parent, *target.parents)):
        raise ValueError("private output outside a Git tree required")
    if args.command == "draft":
        result: object = [c.model_dump(mode="json") for c in development_cases()]
    elif args.command == "economics":
        if not args.rows or args.scheduled_per_arm is None:
            parser.error("economics requires --rows and --scheduled-per-arm")
        samples = tuple(
            WorkSample.model_validate_json(json.dumps(r))
            for r in json.loads(read_private(args.rows))
        )
        result = economic_report(samples, scheduled_per_arm=args.scheduled_per_arm)
    else:
        if not args.cases:
            parser.error("--cases required")
        cases = references(args.cases)
        if args.command == "baselines":
            if not args.training:
                parser.error("baselines requires --training")
            model = TfidfBaseline()
            model.fit(references(args.training))
            result = {
                "rules_and_review": [
                    baseline(c, always_review=a).model_dump(mode="json")
                    for c in cases
                    for a in (True, False)
                ],
                "tfidf": [r.model_dump(mode="json") for r in model.observations(cases)],
                "metadata": model.metadata(),
                "model_comparators": "import separately approved cheap/strong observations",
            }
        else:
            if not args.rows:
                parser.error("--rows required")
            rows = observations(args.rows)
            if args.command in ("calibrate", "calibrate-cascade"):
                if not args.limits:
                    parser.error("calibrate requires explicit --limits")
                limits = OperatingLimits.model_validate_json(read_private(args.limits))
                if args.command == "calibrate-cascade":
                    if args.scope_threshold is None:
                        parser.error("cascade requires an explicit --scope-threshold")
                    result = calibrate_cascade(
                        cases,
                        rows,
                        limits,
                        trials=args.trials,
                        scope_threshold=args.scope_threshold,
                    )
                else:
                    result = calibrate(cases, rows, limits, trials=args.trials)
            else:
                result = scorecard(cases, rows, variants=VARIANTS, trials=args.trials)
    with target.open("x", encoding="utf-8") as output:
        output.write(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, LookupError):
        raise SystemExit(
            "CFPB evaluation failed; check private inputs, pins and output path"
        ) from None
