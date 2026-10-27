"""Explicit paired-continuation worker; legacy HTTP30 defaults remain unchanged."""

from dataclasses import dataclass, field
from typing import Annotated, Literal

from pydantic import Field

from agent_harness.contracts import ModelRequest, ModelResponse
from agent_harness.controls import ExecutionPolicy


class PairedExecutionPolicy(ExecutionPolicy):
    max_attempts: Literal[1] = 1
    attempt_timeout_seconds: Annotated[float, Field(gt=0, le=110)] = 110.0


@dataclass(frozen=True)
class PairedWorker:
    api_key: str = field(repr=False)
    free_tier_confirmed: bool

    def generate(self, request: ModelRequest, *, timeout_seconds: float) -> ModelResponse:
        from agent_harness.gemini import GeminiTransport

        return GeminiTransport(
            self.api_key,
            free_tier_confirmed=self.free_tier_confirmed,
            http_timeout_seconds=90,
        ).generate(request, timeout_seconds=timeout_seconds)
