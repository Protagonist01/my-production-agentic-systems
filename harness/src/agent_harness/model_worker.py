"""Explicit two-model worker; no Flash flag or HTTP-window mismatch at dispatch."""

from dataclasses import dataclass, field

from agent_harness.contracts import ModelRequest, ModelResponse


@dataclass(frozen=True)
class ModelComparisonWorker:
    api_key: str = field(repr=False)
    free_tier_confirmed: bool

    def generate(self, request: ModelRequest, *, timeout_seconds: float) -> ModelResponse:
        from agent_harness.gemini import GeminiTransport

        return GeminiTransport(
            self.api_key,
            free_tier_confirmed=self.free_tier_confirmed,
            flash_comparison=True,
            http_timeout_seconds=90,
        ).generate(request, timeout_seconds=timeout_seconds)
