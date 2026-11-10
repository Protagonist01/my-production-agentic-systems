"""Run exposed authored routing diagnostics, not whole-service or release evaluation."""

import argparse
import hashlib
import json
import os
import socket
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent_harness.contracts import RunContext
from agent_harness.offline_example import example_context
from agent_harness.release_contracts import pin
from olist_support.baseline_recording import DeterministicPlanner
from olist_support.policy import POLICY_VERSION
from olist_support.policy_cases import external
from olist_support.routing_contracts import RoutingPlan
from olist_support.workflow import WorkflowRequest

from olist_diagnostics import Observation, Plan, summarize


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    packet, output = external(args.packet), external(args.output)
    manifest = json.loads((packet / "manifest.json").read_bytes())
    assert manifest["complete"]
    for name, expected in manifest["files"].items():
        assert Path(name).name == name and digest(packet / name) == expected
    plan = Plan.model_validate_json((packet / "plan.json").read_bytes())
    assert not plan.provider_calls_authorized and not plan.release_allowed
    inputs = json.loads((packet / "inputs.json").read_bytes())
    assert inputs == [
        {"case_id": c.case_id, "group": c.group, "text": c.reference.text} for c in plan.cases
    ]
    root = Path(__file__).resolve().parents[2]
    sources = [
        "docs/evaluation/run_olist_diagnostic_baselines.py",
        "olist_diagnostics.py",
        "uv.lock",
        "projects/olist-support/src/olist_support/baseline_recording.py",
        "projects/olist-support/src/olist_support/fresh_release.py",
        "projects/olist-support/src/olist_support/workflow.py",
        "projects/olist-support/src/olist_support/routing_contracts.py",
        "harness/src/agent_harness/contracts.py",
        "harness/src/agent_harness/baseline_recording.py",
    ]
    source_pins = {name: digest(root / name) for name in sources}
    output.mkdir(mode=0o700)  # existing or partial runs cannot be overwritten

    def write(name, document):
        raw = (json.dumps(document, sort_keys=True, indent=2) + "\n").encode()
        fd = os.open(output / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        return hashlib.sha256(raw).hexdigest()

    write(
        "before.json",
        {
            "source_pins": source_pins,
            "packet_manifest_sha256": digest(packet / "manifest.json"),
            "plan_sha256": pin(plan),
            "reference_scope": "exposed_authored_development",
        },
    )
    network = {"attempts": 0}

    def denied(*args, **kwargs):
        network["attempts"] += 1
        raise RuntimeError("network denied in zero-call diagnostic run")

    original = (
        socket.socket.connect,
        socket.socket.connect_ex,
        socket.create_connection,
        socket.getaddrinfo,
    )
    socket.socket.connect = socket.socket.connect_ex = socket.create_connection = (
        socket.getaddrinfo
    ) = denied
    records, rows = [], []
    try:
        for variant in ("rules", "always-review"):
            assert variant in plan.variants
            planner = DeterministicPlanner(variant)
            for item in inputs:
                request = WorkflowRequest(order_id="invented-diagnostic-order", text=item["text"])
                for trial in plan.trials:
                    now = datetime.now(UTC)
                    context = example_context("diagnostic-source-pins", source_pins["uv.lock"])
                    context = RunContext.model_validate_json(
                        context.model_copy(
                            update={
                                "run_id": f"diagnostic-{variant}-{item['case_id']}-{trial}",
                                "agent_id": "olist-diagnostic-baseline",
                                "case_id": item["case_id"],
                                "trial_id": trial,
                                "clock": now,
                                "deadline": now + timedelta(seconds=30),
                                "business_event_id": "diagnostic-" + item["case_id"],
                                "budget": context.budget.model_copy(
                                    update={"max_model_calls": 1, "max_tokens": 1}
                                ),
                                "versions": context.versions.model_copy(
                                    update={
                                        "candidate": variant,
                                        "policy": POLICY_VERSION,
                                        "data_snapshot": pin(plan),
                                    }
                                ),
                            }
                        ).canonical_json()
                    )
                    start = time.monotonic_ns()
                    decision = planner.plan(context, request)
                    elapsed = (time.monotonic_ns() - start) / 1_000_000_000
                    usage = decision.usage
                    assert usage is not None and usage.model_calls == 0 and usage.cost == 0
                    assert (
                        usage.cost_currency == "USD" and decision.execution_run_id == context.run_id
                    )
                    predicted = RoutingPlan(
                        routing_version="olist-intent-routing-v2",
                        intent=decision.plan.intent,
                        requested_minor=decision.plan.requested_minor,
                    )
                    row = Observation(
                        plan_sha256=pin(plan),
                        case_id=item["case_id"],
                        variant=variant,
                        trial=trial,
                        predicted=predicted,
                        resolved=decision.failure_code is None,
                        cost=usage.cost,
                        model_calls=usage.model_calls,
                    )
                    rows.append(row)
                    records.append(
                        {
                            "context": context.model_dump(mode="json"),
                            "request": request.model_dump(mode="json"),
                            "decision": decision.model_dump(mode="json"),
                            "observation": row.model_dump(mode="json"),
                            "planner_elapsed_seconds": elapsed,
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
        write("records.json", records)  # preserve partial records on failure
        write("network.json", network)
    assert source_pins == {name: digest(root / name) for name in sources}
    files = {
        name: digest(output / name) for name in ("before.json", "records.json", "network.json")
    }
    files["report.json"] = write("report.json", summarize(plan, tuple(rows)))
    write(
        "manifest.json",
        {
            "complete": True,
            "files": files,
            "provider_calls": 0,
            "service_effects_observed": False,
            "independent_language_gold": False,
            "release_allowed": False,
        },
    )
    print(
        json.dumps(
            {
                "output": str(output),
                "observations": len(rows),
                "network_attempts": network["attempts"],
                "manifest_sha256": digest(output / "manifest.json"),
            }
        )
    )


if __name__ == "__main__":
    main()
