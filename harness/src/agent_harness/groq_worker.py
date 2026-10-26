"""Importable owned worker; no Groq/HTTP dependencies until explicitly executed."""

from dataclasses import dataclass, field

from agent_harness.contracts import ModelRequest, ModelResponse


@dataclass(frozen=True)
class GroqWorker:
    api_key: str = field(repr=False)
    free_tier_confirmed: bool

    def generate(self, request: ModelRequest, *, timeout_seconds: float) -> ModelResponse:
        from agent_harness.groq import GroqTransport

        return GroqTransport(self.api_key, free_tier_confirmed=self.free_tier_confirmed).generate(
            request, timeout_seconds=timeout_seconds
        )
