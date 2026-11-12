"""Bounded language-only capture after explicit scope installation; never an app launcher."""

import hashlib
import importlib.metadata
import json
import os
import platform
import socket
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic

import httpx
from agent_harness.contracts import ModelRequest, ModelResponse
from agent_harness.cost_accounting import derive, verify_accounting
from agent_harness.gemini import GeminiTransport
from agent_harness.isolated_transport import IsolatedTransport
from agent_harness.release_contracts import pin as contract_pin

from docs.evaluation.olist_semantic_candidate import SemanticOutput, parse, request
from docs.evaluation.olist_semantic_controls import Scope, canonical, observe, pin, reserve


def environment_pin() -> str:
    return pin(
        canonical(
            {
                "python": platform.python_version(),
                "implementation": platform.python_implementation(),
                "executable": sys.executable,
                "system": platform.system(),
                "machine": platform.machine(),
                "distributions": sorted(
                    (d.metadata["Name"], d.version) for d in importlib.metadata.distributions()
                ),
            }
        )
    )


def runtime_sources(root: Path) -> dict[str, str]:
    files = {root / "uv.lock", root / "pyproject.toml"}
    for directory in ("harness/src", "projects/olist-support/src"):
        files.update((root / directory).rglob("*.py"))
    files.update(
        root / "docs/evaluation" / name
        for name in (
            "olist_semantic_candidate.py",
            "olist_semantic_controls.py",
            "run_olist_semantic_comparison.py",
            "read_olist_semantic_comparison.py",
        )
    )
    return {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(files)
    }


def verify_runtime(root: Path, scope: Scope) -> None:
    import agent_harness
    import olist_support

    for module in (agent_harness, olist_support):
        if not Path(module.__file__).resolve().is_relative_to(root.resolve()):
            raise ValueError("editable imports come from another checkout")
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    dirty = subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True).strip()
    if (
        dirty
        or revision != scope.code_revision
        or runtime_sources(root) != scope.source_files
        or environment_pin() != scope.environment_sha256
    ):
        raise ValueError("clean frozen code, imports, lock or environment differs")


@dataclass(frozen=True)
class SDKWorker:
    api_key: str = field(repr=False)
    project_sha256: str
    # This mapping is used only in fake-SDK readiness and cannot claim provider origin.
    fake_outputs: dict[str, str] | None = field(default=None, repr=False)

    @property
    def origin(self) -> str:
        return "mock" if self.fake_outputs is not None else "provider"

    def generate(self, req: ModelRequest, *, timeout_seconds: float) -> ModelResponse:
        fake = None
        if self.fake_outputs is not None:
            output = self.fake_outputs[req.fingerprint()]

            def deny_network(*args: object, **kwargs: object) -> None:
                raise RuntimeError("fake SDK readiness must not access network")

            socket.socket.connect = deny_network
            socket.socket.connect_ex = deny_network
            socket.create_connection = deny_network
            socket.getaddrinfo = deny_network

            def handle(http_request: httpx.Request) -> httpx.Response:
                if http_request.url.host != "generativelanguage.googleapis.com":
                    raise ValueError("fake SDK route differs")
                return httpx.Response(
                    200,
                    json={
                        "candidates": [
                            {
                                "content": {"role": "model", "parts": [{"text": output}]},
                                "finishReason": "STOP",
                            }
                        ],
                        "usageMetadata": {
                            "promptTokenCount": 100,
                            "candidatesTokenCount": 50,
                            "totalTokenCount": 150,
                        },
                        "modelVersion": req.model,
                        "responseId": "invented-readiness-response",
                    },
                )

            fake = httpx.MockTransport(handle)
        return GeminiTransport(
            self.api_key, free_tier_confirmed=True, http_transport=fake, http_timeout_seconds=90
        ).generate(req, timeout_seconds=timeout_seconds)


def write(path: Path, value: object) -> str:
    raw = (canonical(value) + "\n").encode()
    with path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return hashlib.sha256(raw).hexdigest()


def capture(
    root: Path,
    ledger: Path,
    scope: Scope,
    expected_scope_pin: str,
    requests: tuple[ModelRequest, ...],
    canary_expected: tuple[SemanticOutput, ...],
    worker: SDKWorker,
    output: Path,
) -> dict[str, object]:
    """No scope activation, key discovery, resume, retries, business actions or scoring."""
    if pin(scope.canonical_json()) != expected_scope_pin or worker.origin != scope.origin:
        raise ValueError("scope pin or worker origin differs")
    if worker.project_sha256 != scope.project_sha256 or not worker.api_key:
        raise ValueError("explicit worker credential/project association required")
    if len(requests) != 74 or len(canary_expected) != 2:
        raise ValueError("complete frozen request/canary inventory required")
    if (
        pin(canonical([x.model_dump(mode="json") for x in canary_expected]))
        != scope.canary_expectations_sha256
    ):
        raise ValueError("frozen invented canary expectations differ")
    requests = tuple(ModelRequest.model_validate_json(r.canonical_json()) for r in requests)
    inputs = [
        {"case_id": scope.slots[i].case_id, "input": {"text": requests[i].messages[-1].content}}
        for i in range(2, 74, 3)
    ]
    if pin(canonical(inputs)) != scope.input_packet_sha256:
        raise ValueError("frozen input-only packet differs")
    for slot, req in zip(scope.slots, requests, strict=True):
        if req.fingerprint() != slot.request_sha256 or req != request(req.messages[-1].content):
            raise ValueError("candidate input, route, fixed prompt or schema differs")
    if any((p / ".git").exists() for p in (output.resolve(), *output.resolve().parents)):
        raise ValueError("raw capture must remain outside Git checkouts")
    verify_runtime(root, scope)
    output.mkdir(exist_ok=False, parents=True)
    request_pin = write(output / "requests.json", [r.model_dump(mode="json") for r in requests])
    write(
        output / "before.json",
        {
            "scope_sha256": expected_scope_pin,
            "origin": worker.origin,
            "requests_sha256": request_pin,
            "provider_calls_authorized_here": 0,
        },
    )
    rows = []
    for slot, req in zip(scope.slots, requests, strict=True):
        verify_runtime(root, scope)
        now = datetime.now(UTC)
        reserve(ledger, expected_scope_pin, slot, now=now, origin=worker.origin)
        transport = IsolatedTransport(worker)
        started = monotonic()
        response = transport.generate(req, timeout_seconds=scope.parent_timeout_seconds)
        elapsed = monotonic() - started
        # Save the raw response before accounting/parse/observation can fail.
        write(output / f"raw-{slot.ordinal:02d}.json", response.model_dump(mode="json"))
        raw_usage = response.usage
        response = derive(
            req,
            response,
            scope.tariff,
            contract_pin(scope.tariff),
            scope.project_sha256,
            now=datetime.now(UTC),
            allowance_sha256=scope.allowance_sha256,
            capture_scope_sha256=expected_scope_pin,
        )
        verify_accounting(req, response)
        extracted, failure = None, None
        try:
            verify_runtime(root, scope)
            if (
                response.failure is not None
                or response.output is None
                or response.output.content is None
            ):
                raise ValueError("provider_failure_or_missing_output")
            extracted = parse(req.messages[-1].content, response.output.content)
            if slot.phase == "canary" and extracted != canary_expected[slot.ordinal - 1]:
                raise ValueError("invented_canary_expectation_mismatch")
            if raw_usage.input_tokens is None or raw_usage.output_tokens is None:
                raise ValueError("provider_usage_incomplete")
        except ValueError:
            failure = "failed_parent_readiness_or_response_check"
        timing = {
            "elapsed_seconds": elapsed,
            "worker": transport.last_timing.model_dump(mode="json")
            if transport.last_timing
            else None,
            "parent_failure": failure,
        }
        observe(
            ledger,
            expected_scope_pin,
            slot,
            response,
            timing,
            continue_allowed=failure is None,
            now=datetime.now(UTC),
            origin=worker.origin,
        )
        rows.append(
            {
                "ordinal": slot.ordinal,
                "phase": slot.phase,
                "request_sha256": req.fingerprint(),
                "response": response.model_dump(mode="json"),
                "timing": timing,
                "extracted": extracted.model_dump(mode="json") if extracted else None,
            }
        )
        print(
            json.dumps(
                {
                    "ordinal_observed": slot.ordinal,
                    "phase": slot.phase,
                    "origin": worker.origin,
                    "continue_allowed": failure is None,
                }
            ),
            flush=True,
        )
        if failure is not None:
            break
    result = {
        "origin": worker.origin,
        "scheduled": 74,
        "consumed": len(rows),
        "missing": 74 - len(rows),
        "actual_provider_attempts": len(rows) if worker.origin == "provider" else 0,
        "rows": rows,
        "semantic_accuracy_scored": False,
        "business_effects_executed": False,
        "qualification": False,
        "release_allowed": False,
    }
    final_pin = write(output / "capture.json", result)
    write(
        output / "completion.json",
        {
            "capture_sha256": final_pin,
            "scope_sha256": expected_scope_pin,
            "origin": worker.origin,
            "scheduled": 74,
            "consumed": len(rows),
        },
    )
    return result
