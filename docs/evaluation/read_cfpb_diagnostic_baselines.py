"""Separate custody/consistency readback, not independent financial-risk adjudication."""

import argparse
import hashlib
import json
from pathlib import Path

from cfpb_triage.evaluation_corpus import development_cases
from cfpb_triage.evaluation_v2 import VARIANTS, Observation, scorecard
from cfpb_triage.routing_experiments import baseline

ROOT = Path(__file__).resolve().parents[2]


def require(condition):
    if not condition:
        raise ValueError("capture custody, source or observation mismatch")


def readback(root, expected):
    root = root.resolve()
    require(not any((p / ".git").exists() for p in (root, *root.parents)))
    require(hashlib.sha256((root / "manifest.json").read_bytes()).hexdigest() == expected)
    manifest = json.loads((root / "manifest.json").read_bytes())
    require(manifest["complete"] and manifest["model_attempts"] == 0)
    require(
        set(manifest["files"])
        == {
            "plan.json",
            "references.json",
            "inputs.json",
            "records.json",
            "report.json",
            "summary.json",
            "network.json",
        }
    )
    for name, pin in manifest["files"].items():
        require(hashlib.sha256((root / name).read_bytes()).hexdigest() == pin)
    plan = json.loads((root / "plan.json").read_bytes())
    require(plan["variants"] == list(VARIANTS) and plan["trials"] == 3)
    require(plan["executed"] == ["rules", "always_review"])
    require(
        not plan["provider_calls_authorized"]
        and not plan["threshold_fitting"]
        and not plan["release_allowed"]
        and plan["reference_scope"] == "exposed_authored_training"
    )
    for name, pin in plan["source_pins"].items():
        path = (ROOT / name).resolve()
        require(path.is_relative_to(ROOT) and hashlib.sha256(path.read_bytes()).hexdigest() == pin)
    require(
        hashlib.sha256(json.dumps(plan["source_pins"], sort_keys=True).encode()).hexdigest()
        == manifest["source_inventory_sha256"]
    )
    cases = development_cases()
    require(
        json.loads((root / "references.json").read_bytes())
        == [c.model_dump(mode="json") for c in cases]
    )
    require(
        json.loads((root / "inputs.json").read_bytes())
        == [{"case_id": c.case_id, "text": c.text} for c in cases]
    )
    by_id = {c.case_id: c for c in cases}
    rows = tuple(
        Observation.model_validate_json(json.dumps(r))
        for r in json.loads((root / "records.json").read_bytes())
    )
    keys = {(r.case_id, r.variant, r.trial) for r in rows}
    require(
        len(keys) == len(rows) == 96
        and keys
        == {
            (c.case_id, v, t)
            for c in cases
            for v in ("rules", "always_review")
            for t in range(1, 4)
        }
    )
    for row in rows:
        original = baseline(by_id[row.case_id], always_review=row.variant == "always_review")
        differences = {
            k for k in Observation.model_fields if getattr(original, k) != getattr(row, k)
        }
        require(differences <= {"trial", "latency_seconds", "started_at", "finished_at"})
        require(
            row.latency_seconds is not None
            and row.started_at is not None
            and row.finished_at is not None
        )
        require(
            all(
                getattr(row, field) is None
                for field in (
                    "evidence_relevant",
                    "unauthorized_write",
                    "disclosure",
                    "cost",
                    "currency",
                )
            )
        )
        require(not row.timings)
    require(json.loads((root / "network.json").read_bytes()) == {"attempts": 0})
    report = scorecard(cases, rows, variants=VARIANTS, trials=3)
    require(report == json.loads((root / "report.json").read_bytes()))
    # Independently count observed/missing routes, without treating shared scoring as a new oracle.
    captured = json.loads((root / "summary.json").read_bytes())
    require(captured["observed"] == 96 and captured["scheduled"] == 288)
    for variant in VARIANTS:
        actual = [r for r in rows if r.variant == variant]
        public = captured["variants"][variant]
        require(public["observed"] == len(actual) and public["missing"] == 48 - len(actual))
        require(
            public["route_counts"]
            == {a: sum(r.action == a for r in actual) for a in sorted({r.action for r in actual})}
        )
        require(public["security_effect_unknown"] == public["cost_unknown"] == 48)
        metrics = report["reports"][variant + "/stress"]
        for key in (
            "scope_false_accepts",
            "scope_false_rejects",
            "required_review_missed",
            "unnecessary_reviews",
            "evidence_relevance_unknown",
        ):
            require(public[key] == metrics[key])
        require(
            public["composite_success_not_established"]
            == len(actual) - metrics["correct_completed"]
        )
    require(captured["qualified_labels"] is False and captured["release_allowed"] is False)
    return {
        "verified": True,
        "manifest_sha256": expected,
        "observed": len(rows),
        "missing": 192,
        "scope": "custody_and_consistency_not_independent_semantic_truth",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(readback(args.run, args.manifest_sha256)))
    except (ValueError, OSError, LookupError):
        raise SystemExit("CFPB readback refused the capture") from None
