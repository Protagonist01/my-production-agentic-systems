"""Explicit paired-continuation worker; legacy HTTP30 defaults remain unchanged."""

from dataclasses import dataclass, field

from agent_harness.contracts import ModelRequest, ModelResponse
from agent_harness.controls import PairedExecutionPolicy as PairedExecutionPolicy


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
