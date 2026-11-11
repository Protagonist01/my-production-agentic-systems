"""New development comparator capture/readback; no provider or business authority."""

import argparse
import hashlib
import json
import os
import socket
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent_harness.contracts import RunContext
from agent_harness.offline_example import example_context
from agent_harness.release_contracts import pin
from olist_support.policy import POLICY_VERSION
from olist_support.policy_cases import external
from olist_support.workflow import IntentDecision, WorkflowRequest

from olist_diagnostics import Observation, Plan, summarize
from olist_routing_baseline import VERSION, ConservativePlanner


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(root, name, value):
    raw = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()
    fd = os.open(root / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return digest(root / name)


def prepare(packet):
    manifest = json.loads((packet / "manifest.json").read_bytes())
    assert manifest["complete"]
    for name, expected in manifest["files"].items():
        assert Path(name).name == name and digest(packet / name) == expected
    source = Plan.model_validate_json((packet / "plan.json").read_bytes())
    plan = Plan.model_validate_json(
        source.model_copy(update={"variants": (VERSION,)}).canonical_json()
    )
    inputs = json.loads((packet / "inputs.json").read_bytes())
    assert inputs == [
        {"case_id": c.case_id, "group": c.group, "text": c.reference.text} for c in source.cases
    ]
    return source, plan, inputs


def capture(packet, output):
    source, plan, inputs = prepare(packet)
    root = Path(__file__).resolve().parents[2]
    names = (
        "olist_routing_baseline.py",
        "olist_diagnostics.py",
        "uv.lock",
        "docs/evaluation/olist_conservative_experiment.py",
        "harness/src/agent_harness/contracts.py",
        "harness/src/agent_harness/baseline_recording.py",
        "projects/olist-support/src/olist_support/routing_contracts.py",
    )
    pins = {name: digest(root / name) for name in names}
    output.mkdir(mode=0o700)
    write(
        output,
        "before.json",
        {
            "source_pins": pins,
            "packet_manifest_sha256": digest(packet / "manifest.json"),
            "source_plan_sha256": pin(source),
            "plan_sha256": pin(plan),
        },
    )
    write(output, "plan.json", plan.model_dump(mode="json"))
    records = []
    network = {"attempts": 0}

    def denied(*args, **kwargs):
        network["attempts"] += 1
        raise RuntimeError("network denied")

    original = (
        socket.socket.connect,
        socket.socket.connect_ex,
        socket.create_connection,
        socket.getaddrinfo,
    )
    socket.socket.connect = socket.socket.connect_ex = socket.create_connection = (
        socket.getaddrinfo
    ) = denied
    try:
        planner = ConservativePlanner()
        for item in inputs:
            request = WorkflowRequest(order_id="invented-diagnostic-order", text=item["text"])
            for trial in plan.trials:
                now = datetime.now(UTC)
                ctx = example_context("selected-source-pins", pins["uv.lock"])
                ctx = RunContext.model_validate_json(
                    ctx.model_copy(
                        update={
                            "run_id": f"conservative-{item['case_id']}-{trial}",
                            "case_id": item["case_id"],
                            "agent_id": VERSION,
                            "trial_id": trial,
                            "clock": now,
                            "deadline": now + timedelta(seconds=30),
                            "versions": ctx.versions.model_copy(
                                update={
                                    "candidate": VERSION,
                                    "policy": POLICY_VERSION,
                                    "data_snapshot": pin(plan),
                                }
                            ),
                            "budget": ctx.budget.model_copy(
                                update={"max_model_calls": 1, "max_tokens": 1}
                            ),
                        }
                    ).canonical_json()
                )
                decision = planner.plan(ctx, request)
                assert decision.usage.model_calls == 0 and decision.usage.cost == 0
                assert decision.execution_run_id == ctx.run_id and decision.failure_code is None
                row = Observation(
                    plan_sha256=pin(plan),
                    case_id=item["case_id"],
                    variant=VERSION,
                    trial=trial,
                    predicted=decision.plan,
                    resolved=True,
                    cost=decision.usage.cost,
                    model_calls=0,
                )
                records.append(
                    {
                        "context": ctx.model_dump(mode="json"),
                        "request": request.model_dump(mode="json"),
                        "decision": decision.model_dump(mode="json"),
                        "observation": row.model_dump(mode="json"),
                    }
                )
        assert network["attempts"] == 0
    finally:
        (
            socket.socket.connect,
            socket.socket.connect_ex,
            socket.create_connection,
            socket.getaddrinfo,
        ) = original
        write(output, "records.json", records)
        write(output, "network.json", network)
    assert pins == {name: digest(root / name) for name in names}
    rows = tuple(Observation.model_validate_json(json.dumps(r["observation"])) for r in records)
    write(output, "report.json", summarize(plan, rows))
    files = {p.name: digest(p) for p in output.iterdir() if p.is_file()}
    write(
        output,
        "manifest.json",
        {"complete": True, "files": files, "provider_calls": 0, "release_allowed": False},
    )
    return {"manifest_sha256": digest(output / "manifest.json"), "observations": len(records)}


def readback(packet, output, expected):
    assert digest(output / "manifest.json") == expected
    manifest = json.loads((output / "manifest.json").read_bytes())
    assert (
        manifest["complete"] and manifest["provider_calls"] == 0 and not manifest["release_allowed"]
    )
    assert set(manifest["files"]) == {
        "before.json",
        "plan.json",
        "records.json",
        "network.json",
        "report.json",
    }
    for name, value in manifest["files"].items():
        assert digest(output / name) == value
    source, plan, inputs = prepare(packet)
    assert plan == Plan.model_validate_json((output / "plan.json").read_bytes())
    before = json.loads((output / "before.json").read_bytes())
    assert before["source_plan_sha256"] == pin(source) and before["plan_sha256"] == pin(plan)
    assert before["packet_manifest_sha256"] == digest(packet / "manifest.json")
    root = Path(__file__).resolve().parents[2]
    for name, value in before["source_pins"].items():
        file = (root / name).resolve()
        assert file.is_relative_to(root) and digest(file) == value
    texts = {item["case_id"]: item["text"] for item in inputs}
    records = json.loads((output / "records.json").read_bytes())
    rows = []
    seen = set()
    for item in records:
        ctx = RunContext.model_validate_json(json.dumps(item["context"]))
        request = WorkflowRequest.model_validate_json(json.dumps(item["request"]))
        decision = IntentDecision.model_validate_json(json.dumps(item["decision"]))
        row = Observation.model_validate_json(json.dumps(item["observation"]))
        assert row.case_id == ctx.case_id and row.trial == ctx.trial_id and row.variant == VERSION
        assert ctx.versions.candidate == VERSION and ctx.versions.data_snapshot == pin(plan)
        assert (
            ctx.mode == "offline_fake" and ctx.budget.max_model_calls == ctx.budget.max_tokens == 1
        )
        assert request.text == texts[row.case_id] and decision.execution_run_id == ctx.run_id
        assert decision.failure_code is None and row.predicted == decision.plan and row.resolved
        assert (
            decision.usage.model_calls == row.model_calls == 0
            and decision.usage.cost == row.cost == 0
        )
        assert decision.usage.cost_currency == "USD"
        assert all(
            getattr(row, n) is None
            for n in (
                "review",
                "proposed_refund",
                "unauthorized_effect",
                "disclosure",
                "correct_completion",
                "clarification_resolved",
                "recovered_correctly",
                "elapsed_seconds",
                "stage_timings_complete",
            )
        )
        key = row.case_id, row.trial
        assert key not in seen
        seen.add(key)
        rows.append(row)
    assert seen == {(c.case_id, t) for c in plan.cases for t in plan.trials}
    assert json.loads((output / "network.json").read_bytes()) == {"attempts": 0}
    report = json.loads((output / "report.json").read_bytes())
    assert report == summarize(plan, tuple(rows))
    return {
        "manifest_sha256": expected,
        "plan_sha256": pin(plan),
        "original_plan_sha256": pin(source),
        "overall": report["variants"][VERSION]["overall"],
        "provider_calls": 0,
        "release_allowed": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--verify-manifest")
    args = parser.parse_args()
    if not __debug__:
        parser.error("validation requires Python assertions enabled")
    packet, output = external(args.packet), external(args.output)
    result = (
        readback(packet, output, args.verify_manifest)
        if args.verify_manifest
        else capture(packet, output)
    )
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
