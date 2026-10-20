"""Small importable spawn targets; child bootstrap does not load pytest/test_controls."""

import json
import os
import time
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from agent_harness.contracts import ModelMessage, ModelResponse, Usage


def response():
    return ModelResponse(
        provider="invented",
        model="invented-v1",
        output=ModelMessage(role="assistant", content="invented answer"),
        usage=Usage(
            model_calls=1,
            input_tokens=2,
            output_tokens=3,
            cost=Decimal("0.01"),
            cost_currency="USD",
        ),
    )


@dataclass
class Worker:
    action: str = "success"
    marker: str | None = None

    def generate(self, value, *, timeout_seconds):
        if self.marker:
            Path(self.marker).write_text(str(os.getpid()))
        if self.action == "hang":
            time.sleep(60)
        if self.action == "crash":
            os._exit(9)
        if self.action == "error":
            raise RuntimeError("private child error")
        if self.action == "oversize":
            return response().model_copy(
                update={"output": ModelMessage(role="assistant", content="x" * (1024 * 1024 + 1))}
            )
        return response()


@dataclass
class SdkWorker:
    code: int
    markers: str

    def generate(self, value, *, timeout_seconds):
        import sys

        started = time.monotonic()
        path = Path(self.markers) / f"{os.getpid()}.json"
        evidence = {"phases": [], "seconds": [], "http_calls": 0}

        def stage(name):
            evidence["phases"].append(name)
            evidence["seconds"].append(time.monotonic() - started)
            path.write_text(json.dumps(evidence))

        stage("entered")
        import httpx
        from agent_harness.gemini import GeminiTransport
        from agent_harness.replay_example import _deny_network

        stage("sdk_loaded")
        sys.addaudithook(_deny_network)

        def handler(http_request):
            evidence["http_calls"] += 1
            stage("mock_http")
            assert http_request.extensions["timeout"]["read"] <= timeout_seconds
            if self.code == 408:
                raise httpx.ReadTimeout("invented")
            return httpx.Response(
                self.code,
                json={
                    "error": {
                        "code": self.code,
                        "message": "private provider body",
                        "status": "INVENTED",
                    }
                },
            )

        result = GeminiTransport(
            "invented-key", free_tier_confirmed=True, http_transport=httpx.MockTransport(handler)
        ).generate(value, timeout_seconds=timeout_seconds)
        evidence["code"] = result.failure.code
        stage("completed")
        return result
