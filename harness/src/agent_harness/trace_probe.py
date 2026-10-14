"""H1 live smoke export/read-back against the user-selected local Langfuse project."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from importlib.metadata import version
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from google.genai import errors
from opentelemetry.sdk.trace import TracerProvider

from agent_harness.integration_smoke import MODEL, PACKAGES, live_check, local_environment

CLI_VERSION = "1.2.4"


def validate_readback(payload: dict[str, Any], trace_id: str) -> dict[str, Any]:
    envelope = payload.get("body")
    rows = envelope.get("data") if isinstance(envelope, dict) else None
    if payload.get("status") != 200:
        raise ValueError("Langfuse CLI did not report a successful API response")
    if not isinstance(rows, list):
        raise ValueError("Langfuse CLI returned no observation collection")
    names = {row["name"]: row for row in rows if isinstance(row, dict)}
    if len(rows) != 3 or set(names) != {
        "h1-provider-smoke",
        "gemini-structured",
        "gemini-tool-proposal",
    }:
        raise ValueError("Trace is missing its required root or generation observations")
    root = names["h1-provider-smoke"]
    if root.get("traceId") != trace_id or root.get("type") != "SPAN" or not root.get("id"):
        raise ValueError("Trace root identity/type did not match")
    for name in ("gemini-structured", "gemini-tool-proposal"):
        row = names[name]
        if (
            row.get("traceId") != trace_id
            or row.get("parentObservationId") != root.get("id")
            or row.get("type") != "GENERATION"
            or row.get("model") != MODEL
        ):
            raise ValueError("Trace correlation/type/model did not match")
        usage = row.get("usageDetails") or {}
        if any(type(usage.get(key)) is not int or usage[key] < 0 for key in ("input", "output")):
            raise ValueError("Trace did not retain known token usage")
        if not row.get("input") or not row.get("output"):
            raise ValueError("Trace did not retain the invented input/output")
    return {"trace_id": trace_id, "observation_count": len(rows), "readback_verified": True}


def trace_check(root: Path) -> dict[str, Any]:
    values = local_environment(
        root, ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_BASE_URL")
    )
    host = urlparse(values["LANGFUSE_BASE_URL"])
    if (
        not all(values.values())
        or host.scheme != "http"
        or host.hostname not in {"127.0.0.1", "localhost"}
        or host.username is not None
        or host.query
        or host.fragment
        or host.path not in {"", "/"}
    ):
        raise ValueError("Configure the dedicated local Langfuse project in ignored .env.local")
    npx = shutil.which("npx")
    if npx is None:
        raise ValueError("Node/npx required for the pinned Langfuse CLI read-back")
    # Read configuration before initializing the SDK. No global framework instrumentation.
    from langfuse import Langfuse

    client = Langfuse(
        public_key=values["LANGFUSE_PUBLIC_KEY"],
        secret_key=values["LANGFUSE_SECRET_KEY"],
        base_url=values["LANGFUSE_BASE_URL"],
        environment="h1-local-smoke",
        tracer_provider=TracerProvider(),
        timeout=20,
    )
    started = datetime.now(UTC)
    try:
        if not client.auth_check():
            raise ValueError("Local Langfuse authentication failed")
        with client.start_as_current_observation(
            name="h1-provider-smoke",
            input={"source_kind": "synthetic", "case_id": "invented-h1"},
            metadata={
                "versions": {name: version(name) for name in PACKAGES},
                "source_hashes": {
                    "integration_smoke": hashlib.sha256(
                        Path(__file__).with_name("integration_smoke.py").read_bytes()
                    ).hexdigest(),
                    "trace_probe": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    "environment_lock": hashlib.sha256((root / "uv.lock").read_bytes()).hexdigest(),
                },
            },
        ) as span:
            trace_id = client.get_current_trace_id()
            if trace_id is None:
                raise ValueError("Langfuse did not create a trace identity")
            report = live_check(root, trace_client=client)
            span.update(output={"status": "validated", "quality_evaluation": False})
        trace_url = client.get_trace_url(trace_id=trace_id)
        print("Trace emitted; verifying " + trace_id, file=sys.stderr, flush=True)
        client.flush()
    finally:
        client.shutdown()
    env = os.environ.copy()
    env.update(values)
    env["LANGFUSE_HOST"] = values["LANGFUSE_BASE_URL"]
    result = subprocess.run(
        [
            npx,
            "--yes",
            "langfuse-cli@" + CLI_VERSION,
            "api",
            "observations",
            "list",
            "--trace-id",
            trace_id,
            "--from-start-time",
            (started - timedelta(seconds=5)).isoformat(),
            "--to-start-time",
            (datetime.now(UTC) + timedelta(seconds=5)).isoformat(),
            "--fields",
            "core,basic,io,model,usage,metadata",
            "--limit",
            "10",
            "--expand-metadata",
            "output_schema,tool_schema,source_hashes,versions",
            "--json",
        ],
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    if result.returncode:
        raise ValueError("Langfuse CLI read-back failed; trace acceptance is incomplete")
    secrets_to_check = (values["LANGFUSE_SECRET_KEY"], local_environment(root)["GEMINI_API_KEY"])
    if any(secret and secret in result.stdout for secret in secrets_to_check):
        raise ValueError("A configured secret appeared in trace read-back")
    report["trace"] = validate_readback(json.loads(result.stdout), trace_id)
    report["trace"]["url"] = trace_url
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(trace_check(args.root), indent=2))
        return 0
    except errors.APIError as error:
        print(f"Traced smoke failed: Gemini HTTP {error.code}; no retry/fallback.", file=sys.stderr)
        return 1
    except Exception as error:
        # Capture no raw third-party exceptions/CLI output that could contain credentials.
        print(
            f"Traced H1 smoke failed ({type(error).__name__}); acceptance is incomplete.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
