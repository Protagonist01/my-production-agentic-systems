"""Separate structural/metric readback; an external manifest pin is required."""

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent_harness.contracts import RunContext
from agent_harness.release_contracts import pin
from olist_support.policy_cases import external
from olist_support.workflow import IntentDecision, WorkflowRequest

from olist_diagnostics import Observation, Plan, summarize


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    packet, run = external(args.packet), external(args.run)
    assert digest(run / "manifest.json") == args.manifest_sha256
    manifest = json.loads((run / "manifest.json").read_bytes())
    assert manifest["complete"] and manifest["provider_calls"] == 0
    assert set(manifest["files"]) == {"before.json", "records.json", "network.json", "report.json"}
    for name, expected in manifest["files"].items():
        assert digest(run / name) == expected
    before = json.loads((run / "before.json").read_bytes())
    assert digest(packet / "manifest.json") == before["packet_manifest_sha256"]
    pm = json.loads((packet / "manifest.json").read_bytes())
    assert pm["complete"]
    for name, expected in pm["files"].items():
        assert Path(name).name == name and digest(packet / name) == expected
    for name, expected in before["source_pins"].items():
        source = (root / name).resolve()
        assert source.is_relative_to(root) and digest(source) == expected
    plan = Plan.model_validate_json((packet / "plan.json").read_bytes())
    assert pin(plan) == before["plan_sha256"]
    inputs = {i["case_id"]: i for i in json.loads((packet / "inputs.json").read_bytes())}
    cases = {c.case_id: c for c in plan.cases}
    assert len(inputs) == len(cases)
    records = json.loads((run / "records.json").read_bytes())
    seen, rows, counts = set(), [], Counter()
    for r in records:
        context = RunContext.model_validate_json(json.dumps(r["context"]))
        request = WorkflowRequest.model_validate_json(json.dumps(r["request"]))
        decision = IntentDecision.model_validate_json(json.dumps(r["decision"]))
        row = Observation.model_validate_json(json.dumps(r["observation"]))
        key = row.variant, row.case_id, row.trial
        assert key not in seen and row.variant in ("rules", "always-review")
        seen.add(key)
        assert context.case_id == row.case_id and context.trial_id == row.trial
        assert context.versions.candidate == row.variant and context.mode == "offline_fake"
        assert context.budget.max_model_calls == 1 and context.budget.max_tokens == 1
        assert decision.execution_run_id == context.run_id and decision.failure_code is None
        assert request.text == cases[row.case_id].reference.text == inputs[row.case_id]["text"]
        assert row.predicted.intent == decision.plan.intent
        assert row.predicted.requested_minor == decision.plan.requested_minor
        assert row.resolved and decision.usage.model_calls == row.model_calls == 0
        assert decision.usage.cost == row.cost == 0 and decision.usage.cost_currency == "USD"
        assert row.elapsed_seconds is None and row.stage_timings_complete is None
        assert all(
            getattr(row, name) is None
            for name in (
                "review",
                "proposed_refund",
                "unauthorized_effect",
                "disclosure",
                "correct_completion",
                "clarification_resolved",
                "recovered_correctly",
            )
        )
        assert r["planner_elapsed_seconds"] >= 0
        counts[(row.variant, row.predicted.intent)] += 1
        rows.append(row)
    assert seen == {
        (v, c.case_id, t)
        for v in ("rules", "always-review")
        for c in plan.cases
        for t in plan.trials
    }
    assert json.loads((run / "network.json").read_bytes()) == {"attempts": 0}
    report = json.loads((run / "report.json").read_bytes())
    assert report == summarize(plan, tuple(rows))
    output = {
        "scope": "routing_only_exposed_authored_development",
        "rows": len(rows),
        "manifest_sha256": args.manifest_sha256,
        "plan_sha256": pin(plan),
        "variants": {
            v: {
                "observed": report["variants"][v]["overall"]["observed"],
                "missing": report["variants"][v]["overall"]["missing"],
                "joint_correct": report["variants"][v]["overall"][
                    "reference_relative_joint_intent_amount"
                ],
                "route_counts": {i: n for (variant, i), n in counts.items() if variant == v},
                "service_effect_unknown": report["variants"][v]["overall"]["unauthorized_effect"][
                    "unknown_or_missing"
                ],
            }
            for v in plan.variants
        },
        "provider_calls": 0,
        "qualification": False,
        "release_allowed": False,
    }
    print(json.dumps(output, sort_keys=True))


if __name__ == "__main__":
    main()
