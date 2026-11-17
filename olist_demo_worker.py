"""Spawn-safe SDK worker with an explicit network-denied readiness mode."""

import importlib.metadata
import platform
import socket
import sys
from contextlib import ExitStack
from dataclasses import dataclass, field
from unittest.mock import patch

import httpx
from agent_harness.contracts import ModelRequest, ModelResponse
from agent_harness.isolated_transport import AttemptTiming, IsolatedTransport

from olist_demo_acceptance import canonical, digest


def environment_pin() -> str:
    return digest(
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


@dataclass(frozen=True)
class SDKWorker:
    api_key: str = field(repr=False)
    project_sha256: str
    fake_outputs: dict[str, str] | None = field(default=None, repr=False)

    @property
    def origin(self) -> str:
        return "mock" if self.fake_outputs is not None else "provider"

    def generate(self, request: ModelRequest, *, timeout_seconds: float) -> ModelResponse:
        from agent_harness.gemini import GeminiTransport

        with ExitStack() as stack:
            fake = None
            if self.fake_outputs is not None:
                content = self.fake_outputs[request.fingerprint()]

                def deny_network(*args: object, **kwargs: object) -> None:
                    raise RuntimeError("readiness forbids network")

                for target, name in (
                    (socket.socket, "connect"),
                    (socket.socket, "connect_ex"),
                    (socket, "create_connection"),
                    (socket, "getaddrinfo"),
                ):
                    stack.enter_context(patch.object(target, name, side_effect=deny_network))

                def handle(wire: httpx.Request) -> httpx.Response:
                    if wire.url.host != "generativelanguage.googleapis.com":
                        raise ValueError("readiness route differs")
                    return httpx.Response(
                        200,
                        json={
                            "candidates": [
                                {
                                    "content": {"role": "model", "parts": [{"text": content}]},
                                    "finishReason": "STOP",
                                }
                            ],
                            "usageMetadata": {
                                "promptTokenCount": 100,
                                "candidatesTokenCount": 50,
                                "totalTokenCount": 150,
                            },
                            "modelVersion": request.model,
                            "responseId": "invented-demo-readiness",
                        },
                    )

                fake = httpx.MockTransport(handle)
            return GeminiTransport(
                self.api_key, free_tier_confirmed=True, http_transport=fake, http_timeout_seconds=90
            ).generate(request, timeout_seconds=timeout_seconds)


class SDKTransport:
    """Retain independently selected worker origin and real process phase timings."""

    def __init__(self, worker: SDKWorker) -> None:
        self.worker = worker
        self.transport = IsolatedTransport(worker)

    @property
    def last_timing(self) -> AttemptTiming | None:
        return self.transport.last_timing

    def generate(self, request: ModelRequest, *, timeout_seconds: float) -> ModelResponse:
        return self.transport.generate(request, timeout_seconds=timeout_seconds)
