"""Reviewed fixed Gemini Free-tier admission, separate from observed accounting."""

from decimal import Decimal

from agent_harness.contracts import ModelRequest
from agent_harness.controls import ReservationQuote

# Publisher model card inspected 2026-10-15; reserve full input AND output ceilings.
GEMINI_TOKEN_CEILING = 1_048_576 + 65_536


class GeminiFreeAdmission:
    def __init__(self, *, free_tier_confirmed: bool, flash_comparison: bool = False) -> None:
        if not free_tier_confirmed:
            raise ValueError("Explicit billing-disabled Free-project attestation required")
        self.flash_comparison = flash_comparison

    def quote(self, request: ModelRequest) -> ReservationQuote:
        if self.flash_comparison and (request.provider, request.endpoint, request.model) == (
            "google-gemini-developer-api",
            "https://generativelanguage.googleapis.com",
            "gemini-3.8-flash",
        ):
            return ReservationQuote(
                version="gemini-3.8-flash-free-ceiling-2026-10-23",
                max_tokens=GEMINI_TOKEN_CEILING,
                max_cost=Decimal(0),
                currency="USD",
                evidence_ref="https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash",
            )
        if (request.provider, request.endpoint, request.model) != (
            "google-gemini-developer-api",
            "https://generativelanguage.googleapis.com",
            "gemini-3.5-flash-lite",
        ):
            raise ValueError("No reviewed ceiling for this route")
        return ReservationQuote(
            version="gemini-3.5-flash-lite-free-ceiling-2026-10-15",
            max_tokens=GEMINI_TOKEN_CEILING,
            max_cost=Decimal(0),
            currency="USD",
            evidence_ref="https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite",
        )
