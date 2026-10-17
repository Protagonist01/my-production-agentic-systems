"""Invented H8 local OTLP export/read-back; no live model or private case publication."""

import argparse
import hashlib
import json
import os
import secrets
import shutil
import subprocess
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from agent_harness.contracts import (
    AgentInput,
    AgentResult,
    ModelGateway,
    PublicObservation,
    RunContext,
)
from agent_harness.evaluation import run_case
from agent_harness.langfuse_export import LangfuseExporter
from agent_harness.offline_example import (
    FakeAgent,
    FakeGateway,
    FakeScorer,
    example_case,
    example_context,
)
from agent_harness.telemetry import TraceSession

CANARY = "private-h8-invented-identifier-secret-7153"
CLI_VERSION = "1.2.4"


@dataclass
class ProbeAgent:
    trace: TraceSession

    def run(self, context: RunContext, input: AgentInput, gateway: ModelGateway) -> AgentResult:
        def node() -> AgentResult:
            result = FakeAgent().run(context, input, gateway)
            self.trace.invoke("policy", CANARY, lambda: "allow")
            # Invented tool consumes the model result and returns it unchanged.
            output = self.trace.invoke("tool", CANARY, lambda: result.output or "")
            return result.model_copy(update={"output": output})

        return self.trace.invoke("node", CANARY, node)


def validate_readback(
    raw: str, trace_id: str, forbidden: tuple[str, ...], expected: dict[str, str] | None = None
) -> dict[str, Any]:
    if any(value and value in raw for value in forbidden):
        raise ValueError("privacy canary in backend response")
    payload = json.loads(raw)
    if payload.get("status") != 200:
        raise ValueError("CLI API status failed")
    rows = payload["body"]["data"]
    if len(rows) != 7 or any(row["traceId"] != trace_id for row in rows):
        raise ValueError("incomplete backend trace")
    by_name = {row["name"]: row for row in rows}
    if len(by_name) != 7:
        raise ValueError("duplicate or missing observation")
    parents = {
        "agent": "run",
        "scorer": "run",
        "node": "agent",
        "model": "node",
        "tool": "node",
        "policy": "node",
    }
    types = {
        "run": "CHAIN",
        "agent": "AGENT",
        "node": "SPAN",
        "model": "GENERATION",
        "tool": "TOOL",
        "policy": "GUARDRAIL",
        "scorer": "EVALUATOR",
    }
    for kind, expected_type in types.items():
        row = by_name["harness-" + kind]
        if row["type"] != expected_type:
            raise ValueError("backend observation type differs")
        parent = parents.get(kind)
        if row.get("parentObservationId") != (
            by_name["harness-" + parent]["id"] if parent else None
        ):
            raise ValueError("backend hierarchy differs")
    model = by_name["harness-model"]
    if not str(model.get("model")).startswith("model-") or any(
        (model.get("usageDetails") or {}).get(key) != 0 for key in ("input", "output")
    ):
        raise ValueError("backend model usage differs")
    metadata = by_name["harness-run"].get("metadata") or {}
    if (by_name["harness-run"].get("output") or {}).get("outcome") != "completed":
        raise ValueError("backend runtime outcome missing")
    required = (
        "version_code_revision",
        "version_candidate",
        "version_policy",
        "version_environment_lock",
        "version_data_snapshot",
        "source_version",
        "scorer_version",
    )
    if any(not isinstance(metadata.get(key), str) or len(metadata[key]) != 64 for key in required):
        raise ValueError("backend version evidence missing")
    sources = metadata.get("source_refs", [])
    if isinstance(sources, str):
        sources = json.loads(sources)
    if metadata.get("source_count") != 1 or len(sources) != 1 or len(sources[0]) != 64:
        raise ValueError("backend source evidence missing")
    if expected and any(metadata.get(key) != value for key, value in expected.items()):
        raise ValueError("backend version evidence differs")
    if len((by_name["harness-tool"].get("metadata") or {}).get("result_ref", "")) != 64:
        raise ValueError("backend tool result reference missing")
    return {
        "observations": len(rows),
        "hierarchy_verified": True,
        "canaries_absent": True,
        "versions_verified": bool(expected),
        "project_id": rows[0]["projectId"],
    }


def check(root: Path, code_revision: str) -> dict[str, Any]:
    names = ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_BASE_URL")
    values = {name: os.environ.get(name, "") for name in names}
    path = root / ".env.local"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            name, sep, value = line.partition("=")
            if sep and name.strip() in values and not values[name.strip()]:
                values[name.strip()] = value.strip().strip('"').strip("'")
    origin = values["LANGFUSE_BASE_URL"]
    if urlsplit(origin).hostname not in ("localhost", "127.0.0.1", "::1"):
        raise ValueError("probe requires the configured local Langfuse")
    npx = shutil.which("npx")
    if npx is None:
        raise ValueError("npx required for independent CLI read-back")
    start = datetime.now(UTC) - timedelta(minutes=1)
    exporter = LangfuseExporter(origin, values[names[0]], values[names[1]])
    trace = TraceSession(exporter, secrets.token_bytes(32))
    context = example_context(
        code_revision, hashlib.sha256((root / "uv.lock").read_bytes()).hexdigest()
    )
    context = context.model_copy(update={"tenant_id": CANARY, "business_event_id": CANARY})
    case = example_case()
    case = case.model_copy(
        update={
            "input": case.input.model_copy(
                update={
                    "request": CANARY,
                    "observations": (PublicObservation(reference=CANARY, text=CANARY),),
                }
            )
        }
    )
    case = case.model_copy(
        update={"expected": case.expected.model_copy(update={"output": CANARY.upper()})}
    )
    report = run_case(context, case, ProbeAgent(trace), FakeGateway(), FakeScorer(), trace=trace)
    if (
        report.telemetry is None
        or not report.telemetry.healthy
        or report.result.outcome != "completed"
        or report.scores[0].value != 1.0
    ):
        raise ValueError("runtime or exporter health failed")
    env = dict(os.environ, **values, LANGFUSE_HOST=origin)
    command = [
        npx,
        "--yes",
        "langfuse-cli@" + CLI_VERSION,
        "api",
        "observations",
        "list",
        "--trace-id",
        trace.trace_id,
        "--from-start-time",
        start.isoformat(),
        "--to-start-time",
        (datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
        "--fields",
        "core,basic,io,model,usage,metadata",
        "--limit",
        "20",
        "--expand-metadata",
        "version_code_revision,version_candidate,version_policy,version_environment_lock,version_data_snapshot,source_version,scorer_version,source_refs,source_count,result_ref",
        "--json",
    ]
    checked = None
    for _ in range(8):
        result = subprocess.run(
            command, env=env, capture_output=True, text=True, timeout=60, check=False
        )
        if result.returncode:
            raise ValueError("Langfuse CLI read-back failed")
        try:
            checked = validate_readback(
                result.stdout,
                trace.trace_id,
                (CANARY, CANARY.upper(), values[names[0]], values[names[1]]),
                {
                    "version_" + name: trace.reference(
                        "version_" + name, getattr(context.versions, name)
                    )
                    for name in (
                        "code_revision",
                        "candidate",
                        "data_snapshot",
                        "policy",
                        "environment_lock",
                    )
                },
            )
            break
        except (ValueError, KeyError):
            time.sleep(1)
    if checked is None:
        raise ValueError("backend verification failed")
    project = checked.pop("project_id")
    return {
        "health": report.telemetry.model_dump(),
        **checked,
        "outbound_model_calls": 0,
        "quality_evaluation": False,
        "code_revision": code_revision,
        "environment_lock": context.versions.environment_lock,
        "trace_url": origin.rstrip("/") + "/project/" + project + "/traces/" + trace.trace_id,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--code-revision", required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(check(args.root, args.code_revision), sort_keys=True))
    except Exception as error:
        # Safe fixed error class only; CLI/server payloads and credential values stay private.
        print(json.dumps({"error": type(error).__name__, "check": "h8-local-telemetry"}))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
