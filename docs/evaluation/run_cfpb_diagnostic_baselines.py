"""Execute unchanged deterministic comparators on the existing authored CFPB pack."""

import argparse
import hashlib
import json
import os
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from cfpb_triage.evaluation_corpus import development_cases
from cfpb_triage.evaluation_v2 import VARIANTS, Observation, scorecard
from cfpb_triage.routing_experiments import baseline

ROOT = Path(__file__).resolve().parents[2]
TRIALS = 3
EXECUTED = ("rules", "always_review")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def private(path):
    path = path.resolve()
    require(
        not any((p / ".git").exists() for p in (path, *path.parents)),
        "private evidence must remain outside Git",
    )
    return path


def sources():
    paths = {
        ROOT / "uv.lock",
        Path(__file__).resolve(),
        ROOT / "docs/evaluation/read_cfpb_diagnostic_baselines.py",
    }
    for package in ("harness/src/agent_harness", "projects/cfpb-triage/src/cfpb_triage"):
        paths.update((ROOT / package).rglob("*.py"))
        paths.update((ROOT / package).rglob("*.sql"))
    return {p.relative_to(ROOT).as_posix(): digest(p) for p in sorted(paths)}


def write(root, name, document):
    raw = (
        json.dumps(document, sort_keys=True, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    ).encode()
    fd = os.open(root / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return hashlib.sha256(raw).hexdigest()


def summary(cases, rows, report):
    variants = {}
    for variant in VARIANTS:
        selected = [r for r in rows if r.variant == variant]
        metrics = report["reports"][variant + "/stress"]
        variants[variant] = {
            "scheduled": len(cases) * TRIALS,
            "observed": len(selected),
            "missing": metrics["missing"],
            "route_counts": dict(Counter(r.action for r in selected)),
            "scope_false_accepts": metrics["scope_false_accepts"],
            "scope_false_rejects": metrics["scope_false_rejects"],
            "required_review_missed": metrics["required_review_missed"],
            "unnecessary_reviews": metrics["unnecessary_reviews"],
            "composite_success_not_established": len(selected) - metrics["correct_completed"],
            "evidence_relevance_unknown": metrics["evidence_relevance_unknown"],
            "security_effect_unknown": metrics["unknown_safety"] + metrics["missing"],
            "cost_unknown": metrics["cost_unknown"],
        }
    return {
        "purpose": "unchanged_comparators_exposed_authored_development",
        "cases": len(cases),
        "declared_families": len({c.family for c in cases}),
        "trials": TRIALS,
        "scheduled": len(cases) * len(VARIANTS) * TRIALS,
        "observed": len(rows),
        "variants": variants,
        "timing_scope": "comparator_function_only_not_service_or_human_elapsed",
        "model_attempts": 0,
        "qualified_labels": False,
        "release_allowed": False,
    }


def run(output):
    output = private(output)
    output.mkdir(mode=0o700)  # Never overwrite an older complete or partial run.
    cases = development_cases()
    pins = sources()
    plan = {
        "schema_version": 1,
        "variants": list(VARIANTS),
        "trials": TRIALS,
        "executed": list(EXECUTED),
        "reference_scope": "exposed_authored_training",
        "provider_calls_authorized": False,
        "threshold_fitting": False,
        "release_allowed": False,
        "source_pins": pins,
    }
    files = {
        "plan.json": write(output, "plan.json", plan),
        "references.json": write(
            output, "references.json", [c.model_dump(mode="json") for c in cases]
        ),
        "inputs.json": write(
            output, "inputs.json", [{"case_id": c.case_id, "text": c.text} for c in cases]
        ),
    }
    network = {"attempts": 0}

    def deny(event, arguments):
        if event in {
            "socket.connect",
            "socket.sendto",
            "socket.sendmsg",
            "socket.getaddrinfo",
            "socket.gethostbyname",
            "socket.gethostbyaddr",
        }:
            network["attempts"] += 1
            raise RuntimeError("network denied during comparator execution")

    sys.addaudithook(deny)
    rows = []
    try:
        for variant in EXECUTED:
            for case in cases:
                for trial in range(1, TRIALS + 1):
                    started_at, started_ns = datetime.now(UTC), time.perf_counter_ns()
                    prediction = baseline(case, always_review=variant == "always_review")
                    elapsed = (time.perf_counter_ns() - started_ns) / 1e9
                    # Preserve the frozen algorithm's claims. No human/cost/security facts added.
                    row = Observation.model_validate_json(
                        prediction.model_copy(
                            update={
                                "trial": trial,
                                "latency_seconds": elapsed,
                                "started_at": started_at,
                                "finished_at": datetime.now(UTC),
                            }
                        ).canonical_json()
                    )
                    rows.append(row)
        require(sources() == pins, "source changed during execution")
        report = scorecard(cases, tuple(rows), variants=VARIANTS, trials=TRIALS)
        files["records.json"] = write(
            output, "records.json", [r.model_dump(mode="json") for r in rows]
        )
        files["report.json"] = write(output, "report.json", report)
        files["summary.json"] = write(output, "summary.json", summary(cases, rows, report))
    except BaseException:
        write(
            output,
            "failure.json",
            {
                "complete": False,
                "code": "execution_failed",
                "network_attempts": network["attempts"],
            },
        )
        raise
    finally:
        files["network.json"] = write(output, "network.json", network)
    manifest = {
        "complete": True,
        "files": files,
        "model_attempts": 0,
        "source_inventory_sha256": hashlib.sha256(
            json.dumps(pins, sort_keys=True).encode()
        ).hexdigest(),
    }
    pin = write(output, "manifest.json", manifest)
    print(json.dumps({"manifest_sha256": pin, "observed": len(rows), "model_attempts": 0}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        run(args.output)
    except (ValueError, OSError, LookupError):
        raise SystemExit("CFPB baseline capture failed; preserve the partial run") from None
