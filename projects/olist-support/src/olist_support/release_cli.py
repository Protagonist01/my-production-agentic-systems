"""Private offline Olist report command. No provider, approval or promotion path."""

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath

import agent_harness
from pydantic import TypeAdapter, ValidationError

import olist_support
from olist_support.policy_cases import PolicyCases, external
from olist_support.release import Observation, OfflinePlan, pin, report


def verify_sources(plan: OfflinePlan, source_root: Path) -> None:
    root = source_root.resolve(strict=True)
    required = {"uv.lock"}
    packages = (
        ("harness/src/agent_harness", agent_harness),
        ("projects/olist-support/src/olist_support", olist_support),
    )
    for prefix, package in packages:
        package_root = Path(str(package.__file__)).parent
        required.update(
            prefix + "/" + p.relative_to(package_root).as_posix()
            for p in package_root.rglob("*.py")
        )
        required.update(p.relative_to(root).as_posix() for p in (root / prefix).rglob("*.py"))
    if not required.issubset(plan.source_files):
        raise ValueError("source inventory omits executing package modules or lock")
    for name, expected in plan.source_files.items():
        portable = PurePosixPath(name)
        if portable.is_absolute() or ".." in portable.parts or "\\" in name or ":" in name:
            raise ValueError("source inventory requires portable relative paths")
        path = (root / name).resolve(strict=True)
        if (
            not path.is_relative_to(root)
            or hashlib.sha256(path.read_bytes()).hexdigest() != expected
        ):
            raise ValueError("source inventory bytes differ from reviewed plan")
    scorer = "projects/olist-support/src/olist_support/release.py"
    if plan.source_files["uv.lock"] != plan.lock_sha256:
        raise ValueError("lock pin differs from source inventory")
    if plan.source_files[scorer] != plan.scorer_sha256:
        raise ValueError("scorer pin differs from source inventory")
    if hashlib.sha256(Path(__file__).with_name("release.py").read_bytes()).hexdigest() != (
        plan.scorer_sha256
    ):
        raise ValueError("running scorer differs from reviewed source")
    for prefix, package in packages:
        package_root = Path(str(package.__file__)).parent
        for name in required:
            if name.startswith(prefix + "/"):
                runtime = package_root / name.removeprefix(prefix + "/")
                if hashlib.sha256(runtime.read_bytes()).hexdigest() != plan.source_files[name]:
                    raise ValueError("running package differs from reviewed source inventory")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--cases-pin", required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--plan-pin", required=True)
    parser.add_argument("--observations", type=Path, required=True)
    parser.add_argument("--observations-sha256", required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        cases_raw = external(args.cases).read_bytes()
        cases = PolicyCases.model_validate_json(cases_raw)
        plan = OfflinePlan.model_validate_json(external(args.plan).read_bytes())
        raw = external(args.observations).read_bytes()
        if pin(cases) != args.cases_pin or pin(plan) != args.plan_pin:
            raise ValueError("external plan/case pin mismatch")
        if hashlib.sha256(raw).hexdigest() != args.observations_sha256:
            raise ValueError("external observation byte pin mismatch")
        rows = TypeAdapter(tuple[Observation, ...]).validate_json(raw)
        verify_sources(plan, args.source_root)
        result = report(plan, cases, rows).model_copy(
            update={
                "cases_file_sha256": hashlib.sha256(cases_raw).hexdigest(),
                "observations_file_sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
        output = external(args.output)
        # Existing output is never replaced. A restricted external parent is required on Windows.
        fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(result.canonical_json() + "\n")
        print(
            json.dumps(
                {
                    "scheduled_trials": result.scheduled_trials,
                    "categories": result.categories,
                    "release_allowed": False,
                }
            )
        )
        return 0 if result.categories["correct"] == result.scheduled_trials else 2
    except (OSError, ValueError, ValidationError):
        # Pydantic diagnostics can contain private case text/labels. Retain them only locally.
        print("Offline report rejected: invalid inputs, source pins or output path.")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
