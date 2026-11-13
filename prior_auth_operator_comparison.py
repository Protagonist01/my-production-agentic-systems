"""Separate exposed-case development comparison; no new labels, source data or models."""

import argparse
import hashlib
import json
from pathlib import Path

from prior_auth.source_io import external

from prior_auth_demo import demo_request
from prior_auth_diagnostics import run as original_run
from prior_auth_operator_rules import VERSION, conflict_rules
from prior_auth_pipeline import checked, prepare
from prior_auth_profiling import Profiler
from prior_auth_scorecards import Observation, PlannedCase, score

ROOT = Path(__file__).resolve().parent
CASES = ("conflict-0", "conflict-1")
CODE = (
    "prior_auth_operator_comparison.py",
    "prior_auth_operator_rules.py",
    "prior_auth_scorecards.py",
    "prior_auth_diagnostics.py",
    "prior_auth_demo.py",
    "prior_auth_pipeline.py",
    "prior_auth_intake.py",
    "prior_auth_documents.py",
    "prior_auth_profiling.py",
    "uv.lock",
    "projects/prior-auth/src/prior_auth/assessment.py",
    "projects/prior-auth/src/prior_auth/contracts.py",
    "projects/prior-auth/src/prior_auth/redaction.py",
    "harness/src/agent_harness/contracts.py",
)
FILES = (
    "cases.json",
    "always_review.json",
    "rules.json",
    "conflict_rules.json",
    "report.json",
    "original/cases.json",
    "original/always_review.json",
    "original/rules.json",
    "original/report.json",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as output:
        output.write(json.dumps(value, sort_keys=True, indent=2) + "\n")


def run(directory: Path) -> dict[str, object]:
    directory = external(directory)
    directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    original_run(directory / "original")
    original = json.loads((directory / "original/report.json").read_text(encoding="utf-8"))
    cases = tuple(
        PlannedCase.model_validate_json(json.dumps(row))
        for row in json.loads((directory / "original/cases.json").read_text(encoding="utf-8"))
        if row["case_id"] in CASES
    )
    rows: list[Observation] = []
    for key in CASES:
        raw = b"AHI: 18 events/hour. AHI: 2 events/hour."
        if key.endswith("1"):
            raw = raw.replace(b". ", b".\n")
        request = demo_request(raw, case_id=key)
        profiler = Profiler()
        prepared = prepare(raw, request, profiler)
        prior = next(pin for pin in original["inputs"] if pin["case_id"] == key)
        if (
            prior["request_sha256"] != prepared.request_sha256
            or prior["source_sha256"] != prepared.source_sha256
            or prepared.note is None
        ):
            raise ValueError("exposed-case bytes/request differ from original fixture")
        result = checked(
            prepared.note, prepared.policy, conflict_rules(prepared.note, prepared.policy), profiler
        )
        rows.append(
            Observation(
                case_id=key,
                trial=1,
                result=result,
                intake=prepared.decision.outcome,
                elapsed_ms=None,
                model_calls=0,
                tokens=0,
                cost=0.0,
                privacy_fault=False,
                external_effect=False,
            )
        )
    for name in ("always_review", "rules"):
        values = json.loads((directory / "original" / f"{name}.json").read_text(encoding="utf-8"))
        write(directory / f"{name}.json", [row for row in values if row["case_id"] in CASES])
    write(directory / "cases.json", [case.model_dump(mode="json") for case in cases])
    write(directory / "conflict_rules.json", [row.model_dump(mode="json") for row in rows])
    comparators = {}
    for name in ("always_review", "rules", "conflict_rules"):
        observations = tuple(
            Observation.model_validate_json(json.dumps(row))
            for row in json.loads((directory / f"{name}.json").read_text(encoding="utf-8"))
        )
        comparators[name] = score(cases, observations, trials=1)
    report: dict[str, object] = {
        "version": "prior-auth-exposed-conflict-comparison-v1",
        "variant": VERSION,
        "case_ids": list(CASES),
        "scope": "two-exposed-development-regressions",
        "provider_attempts": 0,
        "clinical_validation": False,
        "qualification": False,
        "references": "unchanged authored proposals; criterion states unknown",
        "comparators": comparators,
    }
    write(directory / "report.json", report)
    write(
        directory / "manifest.json",
        {
            "version": "prior-auth-exposed-capture-v1",
            "source": {name: sha(ROOT / name) for name in CODE},
            "files": {name: sha(directory / name) for name in FILES},
        },
    )
    return report


def readback(directory: Path) -> dict[str, object]:
    directory = external(directory)
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if manifest != {
        "version": "prior-auth-exposed-capture-v1",
        "source": {name: sha(ROOT / name) for name in CODE},
        "files": {name: sha(directory / name) for name in FILES},
    }:
        raise ValueError("capture or source pin differs")
    cases = tuple(
        PlannedCase.model_validate_json(json.dumps(row))
        for row in json.loads((directory / "cases.json").read_text(encoding="utf-8"))
    )
    if tuple(case.case_id for case in cases) != CASES or any(
        case.split != "development"
        or case.reference is None
        or any(state is not None for state in case.reference.expected_states)
        for case in cases
    ):
        raise ValueError("exposed development reference inventory differs")
    report = json.loads((directory / "report.json").read_text(encoding="utf-8"))
    if (
        report["case_ids"] != list(CASES)
        or report["variant"] != VERSION
        or report["provider_attempts"] != 0
        or report["qualification"] is not False
        or report["clinical_validation"] is not False
    ):
        raise ValueError("capture scope differs")
    for name in ("always_review", "rules", "conflict_rules"):
        rows = tuple(
            Observation.model_validate_json(json.dumps(row))
            for row in json.loads((directory / f"{name}.json").read_text(encoding="utf-8"))
        )
        if len(rows) != 2 or any(row.model_calls != 0 for row in rows):
            raise ValueError("actual observation inventory differs")
        if score(cases, rows, trials=1) != report["comparators"][name]:
            raise ValueError("scorecard readback differs")
    return {
        "readback": "passed",
        "observations": 6,
        "provider_attempts": 0,
        "clinical_validation": False,
        "qualification": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("run", "readback"))
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    report = run(args.directory) if args.command == "run" else readback(args.directory)
    print(
        json.dumps(
            {key: value for key, value in report.items() if key != "comparators"}, sort_keys=True
        )
    )


if __name__ == "__main__":
    main()
