"""Explicit tariff-derived Free text cost; preserves raw unknown billing and tokens."""

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal

from pydantic import AwareDatetime

from agent_harness.contracts import Contract, ModelRequest, ModelResponse, NonEmpty, Usage
from agent_harness.gateway import DeadlineTransport
from agent_harness.release_contracts import Sha256, pin


class FreeTariff(Contract):
    version: Literal["gemini-free-text-tariff-2026-10-25"] = "gemini-free-text-tariff-2026-10-25"
    source_url: Literal["https://ai.google.dev/gemini-api/docs/pricing"] = (
        "https://ai.google.dev/gemini-api/docs/pricing"
    )
    source_snapshot_sha256: Sha256
    project_sha256: Sha256
    free_project_attestation_ref: NonEmpty
    review_ref: NonEmpty
    reviewed_at: AwareDatetime
    expires_at: AwareDatetime
    models: tuple[Literal["gemini-3.5-flash-lite", "gemini-3.8-flash"], ...]


class CostAccounting(Contract):
    basis: Literal["reviewed-free-text-tariff-derived-not-provider-billing"] = (
        "reviewed-free-text-tariff-derived-not-provider-billing"
    )
    request_sha256: Sha256
    tariff: FreeTariff
    tariff_sha256: Sha256
    derived_at: AwareDatetime
    raw_usage: Usage
    allowance_sha256: Sha256 | None = None


def derive(
    request: ModelRequest,
    response: ModelResponse,
    tariff: FreeTariff,
    tariff_sha256: str,
    project_sha256: str,
    *,
    now: datetime,
    allowance_sha256: str | None = None,
) -> ModelResponse:
    request = ModelRequest.model_validate_json(request.canonical_json())
    response = ModelResponse.model_validate_json(response.canonical_json())
    tariff = FreeTariff.model_validate_json(tariff.canonical_json())
    if (
        pin(tariff) != tariff_sha256
        or project_sha256 != tariff.project_sha256
        or not tariff.models
        or not tariff.reviewed_at <= now < tariff.expires_at
        or request.provider != "google-gemini-developer-api"
        or request.endpoint != "https://generativelanguage.googleapis.com"
        or request.model not in tariff.models
        or response.provider != request.provider
        or response.model != request.model
        or request.tools
        or any(m.role == "tool" or m.tool_calls for m in request.messages)
        or response.accounting is not None
    ):
        raise ValueError("cost policy/route/project/interval mismatch")
    raw = response.usage
    # No inference for failed/missing accounting or unknown token components.
    if (
        response.failure is not None
        or raw.model_calls != 1
        or raw.input_tokens is None
        or raw.output_tokens is None
        or raw.cost is not None
    ):
        return response
    attachment = CostAccounting(
        request_sha256=pin(request),
        tariff=tariff,
        tariff_sha256=tariff_sha256,
        derived_at=now,
        raw_usage=raw,
        allowance_sha256=allowance_sha256,
    )
    return response.model_copy(
        update={
            "usage": raw.model_copy(update={"cost": Decimal(0), "cost_currency": "USD"}),
            "accounting": attachment.model_dump(mode="json"),
        }
    )


def control_pin(allowance: str, tariff: str, project: str) -> str:
    from agent_harness.release_contracts import sha256

    return sha256(
        json.dumps(
            dict(allowance=allowance, tariff=tariff, project=project), sort_keys=True
        ).encode()
    )


def verify_accounting(
    request: ModelRequest, response: ModelResponse, *, expected_control_sha256: str | None = None
) -> None:
    if response.accounting is None:
        return
    saved = CostAccounting.model_validate_json(json.dumps(response.accounting))
    if expected_control_sha256 is not None and (
        saved.allowance_sha256 is None
        or control_pin(saved.allowance_sha256, saved.tariff_sha256, saved.tariff.project_sha256)
        != expected_control_sha256
    ):
        raise ValueError("cost evidence differs from reviewed provider controls")
    raw = response.model_copy(update={"usage": saved.raw_usage, "accounting": None})
    reconstructed = derive(
        request,
        raw,
        saved.tariff,
        saved.tariff_sha256,
        saved.tariff.project_sha256,
        now=saved.derived_at,
        allowance_sha256=saved.allowance_sha256,
    )
    if reconstructed != response:
        raise ValueError("derived cost differs from raw usage and frozen tariff")


@dataclass(frozen=True)
class AccountedTransport:
    delegate: DeadlineTransport
    tariff: FreeTariff
    tariff_sha256: str
    project_sha256: str
    allowance_sha256: str | None = None

    def generate(self, request: ModelRequest, *, timeout_seconds: float = 30.0) -> ModelResponse:
        # Validate the policy before any dispatch, using a non-dispatched sentinel.
        from agent_harness.gateway import failed_response

        derive(
            request,
            failed_response(request, "permission_denied", "preflight", dispatched=False),
            self.tariff,
            self.tariff_sha256,
            self.project_sha256,
            now=datetime.now(UTC),
            allowance_sha256=self.allowance_sha256,
        )
        response = self.delegate.generate(request, timeout_seconds=timeout_seconds)
        return derive(
            request,
            response,
            self.tariff,
            self.tariff_sha256,
            self.project_sha256,
            now=datetime.now(UTC),
            allowance_sha256=self.allowance_sha256,
        )
