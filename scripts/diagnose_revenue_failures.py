"""Reproduce descriptive diagnostics from the completed private capture; no network.

Run with --capture-root <confidence-study-directory> --output <new-safe-json-file>.
This checks saved pins/observations, not the active provider ledger or cloud billing.
"""

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from agent_harness.cases import _unique_object
from agent_harness.contracts import ModelRequest, ModelResponse
from agent_harness.release_contracts import pin, sha256
from revenue_integrity.confidence_study import ConfidenceCohort
from revenue_integrity.semantic_alignment import parse_aligned_judgment
from revenue_integrity.semantic_pilot import SemanticJudgment


def diagnose(root: Path) -> dict:
    cohort = ConfidenceCohort.model_validate_json((root / "cohort.json").read_bytes())
    plan = json.loads((root / "capture/plan.json").read_bytes())
    assert pin(cohort) == plan["cohort_sha256"]
    schedule = json.loads((root / "capture/schedule.json").read_bytes())
    schedule_bytes = json.dumps(
        schedule, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    assert sha256(schedule_bytes) == plan["schedule_sha256"]
    study = json.loads((root / "capture/study.json").read_bytes())
    files = sorted((root / "capture/rows").glob("*.json"))
    assert len(files) == len(schedule) == len(study["rows"]) == 296
    cases = {c.input.case_id: c for c in cohort.cases}
    refs = {c.case_id: c for c in cohort.dataset.cases}
    outcomes = Counter()
    overlap = Counter()
    pairs = defaultdict(list)
    lengths = defaultdict(Counter)
    categories = defaultdict(Counter)
    for index, file in enumerate(files):
        row = json.loads(file.read_bytes())
        request = ModelRequest.model_validate_json(json.dumps(row["request"]))
        response = ModelResponse.model_validate_json(json.dumps(row["response"]))
        observation = row["observation"]
        assert observation == study["rows"][index]
        assert row["request"] == schedule[index]["request"]
        assert row["context"] == schedule[index]["context"]
        assert pin(request) == observation["input_sha256"]
        case = cases[observation["case_id"]]
        try:
            parsed = parse_aligned_judgment(case.input, response, max_context_chars=50000)
        except ValueError:
            assert observation["decision"] is None and observation["failure_code"]
        else:
            assert parsed.model_dump(mode="json") == row["aligned"]
            assert observation["decision"] == parsed.judgment.decision
        if refs[observation["case_id"]].split != "holdout":
            continue
        expected = "reject" if case.target.impossible else "accept"
        raw = None
        if response.output and response.output.content:
            try:
                json.loads(response.output.content, object_pairs_hook=_unique_object)
                raw = SemanticJudgment.model_validate_json(response.output.content).decision
            except ValueError:
                pass
        status = (
            "correct"
            if observation["decision"] == expected
            else "wrong_decision"
            if observation["decision"] is not None
            else "provider_failure"
            if response.failure
            else "citation_invalid"
        )
        outcomes[status] += 1
        overlap["raw_wrong_decision"] += raw is not None and raw != expected
        overlap["invalid_but_raw_correct"] += observation["decision"] is None and raw == expected
        overlap["invalid_and_raw_wrong"] += (
            observation["decision"] is None and raw is not None and raw != expected
        )
        pairs[observation["case_id"]].append((observation["trial_id"], raw, status, expected))
        n = len(case.input.context)
        band = "up_to_20000" if n <= 20000 else "20001_to_35000" if n <= 35000 else "35001_to_50000"
        lengths[band]["scheduled"] += 1
        lengths[band][status] += 1
        categories[case.target.category][status] += 1
    trial_pairs = Counter()
    for members in pairs.values():
        assert len(members) == 2 and {m[0] for m in members} == {"trial-1", "trial-2"}
        trial_pairs["same_raw_decision"] += (
            members[0][1] is not None and members[0][1] == members[1][1]
        )
        trial_pairs["both_wrong_raw"] += all(r is not None and r != e for _, r, _, e in members)
        failed = sum(s != "correct" for _, _, s, _ in members)
        trial_pairs["both_failed"] += failed == 2
        trial_pairs["only_one_failed"] += failed == 1
    assert sum(outcomes.values()) == 288 and len(pairs) == 144
    return {
        "version": "revenue-exposed-failure-diagnostics-v1",
        "cohort_sha256": pin(cohort),
        "plan_sha256": sha256((root / "capture/plan.json").read_bytes()),
        "validation_observations": 288,
        "validation_families": len(pairs),
        "disjoint_outcomes": dict(outcomes),
        "overlapping_raw_decision_diagnostics": dict(overlap),
        "trial_pairs": dict(trial_pairs),
        "context_length_bands": dict(lengths),
        "category_outcomes": dict(categories),
        "provider_calls": 0,
        "release_allowed": False,
        "limits": [
            "Descriptive reanalysis of exposed cases, not a new qualification experiment.",
            "Length/category associations do not establish causes or generalization.",
            "Publisher disagreement is not independently adjudicated model or label error.",
            "Checks saved capture bindings, not active allowance or cloud billing.",
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = diagnose(args.capture_root)
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(result, output, indent=2, sort_keys=True)
        output.write("\n")
    print(json.dumps({"verified_rows": 296, "provider_calls": 0, "output": str(args.output)}))
