"""Explicit per-worker Gemini composition with a single shared durable allowance."""

from dataclasses import dataclass, field
from datetime import UTC, datetime

from agent_harness.contracts import RunContext
from agent_harness.cost_accounting import AccountedTransport, FreeTariff, control_pin
from agent_harness.provider_budget import AttemptLedger, BudgetedTransport
from agent_harness.release_contracts import pin


@dataclass(frozen=True)
class GeminiCaptureControls:
    api_key: str = field(repr=False)
    ledger: AttemptLedger
    tariff: FreeTariff
    tariff_sha256: str
    project_sha256: str

    @property
    def sha256(self) -> str:
        return control_pin(self.ledger.allowance_sha256, self.tariff_sha256, self.project_sha256)

    def validate(self) -> None:
        if not self.api_key or pin(self.tariff) != self.tariff_sha256:
            raise ValueError("provider controls need explicit credentials and pinned tariff")
        with self.ledger.connect() as db:
            allowance = self.ledger.authorization(db)
        now = datetime.now(UTC)
        if (
            allowance.project_sha256 != self.project_sha256
            or self.tariff.project_sha256 != self.project_sha256
            or not self.tariff.models
            or not allowance.approved_at <= now < allowance.expires_at
            or not self.tariff.reviewed_at <= now < self.tariff.expires_at
            or not set(self.tariff.models).issubset(allowance.models)
        ):
            raise ValueError("provider project/models differ from shared allowance")

    def transport(self, context: RunContext) -> AccountedTransport:
        self.validate()
        from agent_harness.gemini import GeminiTransport

        raw = GeminiTransport(self.api_key, free_tier_confirmed=True, flash_comparison=True)
        return AccountedTransport(
            BudgetedTransport(raw, self.ledger, context, self.project_sha256),
            self.tariff,
            self.tariff_sha256,
            self.project_sha256,
            self.ledger.allowance_sha256,
        )
