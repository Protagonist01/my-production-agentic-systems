"""Constructed SIM policy and validated public operational facts, never outcomes."""

import hashlib
from datetime import datetime
from typing import Annotated, Literal, Self

from agent_harness.contracts import Contract
from pydantic import AwareDatetime, Field, model_validator

Id = Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{1,96}$")]
Minor = Annotated[int, Field(ge=0, le=2**31 - 1)]
Version = Annotated[int, Field(ge=0, le=2**31 - 1)]
Action = Literal["wait", "expedite", "reroute"]


def fingerprint(value: Contract) -> str:
    return hashlib.sha256(value.canonical_json().encode()).hexdigest()


class ReviewRequired(ValueError):
    """Safe unresolved outcome; caller cannot override eligibility with approval."""


class DemoPolicy(Contract):
    policy_version: Literal["supply-sim-v1"] = "supply-sim-v1"
    currency: Literal["SIM"] = "SIM"
    action_cap_minor: Literal[10000] = 10000
    event_cap_minor: Literal[50000] = 50000
    approval_above_minor: Literal[2500] = 2500
    wait_seconds: Literal[1800] = 1800
    max_replans: Literal[2] = 2


POLICY = DemoPolicy()


class Shipment(Contract):
    tenant_id: Id
    shipment_id: Id
    region: Id
    version: Version = 0
    observed_at: AwareDatetime
    expires_at: AwareDatetime
    facts_complete: bool = True
    alert_conflict: bool = False
    capacity: Annotated[int, Field(ge=0, le=1000)] = 1
    estimated_delay_hours: Annotated[int, Field(ge=0, le=720)]
    delay_cost_minor_per_hour: Annotated[int, Field(ge=0, le=10000)] = 1000
    provenance: Literal["invented", "source-observation-hybrid"] = "invented"
    source_ref: str | None = None

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if self.expires_at <= self.observed_at:
            raise ValueError("facts must expire after observation")
        if (self.provenance == "source-observation-hybrid") != (self.source_ref is not None):
            raise ValueError("hybrid observations require source reference")
        return self

    def require_fresh(self, now: datetime) -> None:
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("aware scenario clock required")
        if not self.facts_complete:
            raise ReviewRequired("missing_facts")
        if self.alert_conflict:
            raise ReviewRequired("conflicting_facts")
        if not self.observed_at <= now < self.expires_at:
            raise ReviewRequired("stale_or_future_facts")


class Option(Contract):
    action: Action
    cost_minor: Minor
    estimated_remaining_hours: Annotated[int, Field(ge=0, le=720)]
    estimated_total_minor: Minor


def options(shipment: Shipment, now: datetime) -> tuple[Option, ...]:
    """Server-owned bounded catalog. No caller-provided prices or realized outcomes."""
    shipment = Shipment.model_validate_json(shipment.canonical_json())
    shipment.require_fresh(now)
    choices: list[Option] = []
    for action, cost, reduction in (("wait", 0, 0), ("expedite", 2000, 3), ("reroute", 8000, 10)):
        if action != "wait" and shipment.capacity == 0:
            continue
        remaining = max(0, shipment.estimated_delay_hours - reduction)
        choices.append(
            Option(
                action=action,  # type: ignore[arg-type]
                cost_minor=cost,
                estimated_remaining_hours=remaining,
                estimated_total_minor=cost + remaining * shipment.delay_cost_minor_per_hour,
            )
        )
    return tuple(choices)


class Grant(Contract):
    """Trusted service composition; never accept this object as client authentication."""

    tenant_id: Id
    actor_id: Id
    event_ids: tuple[Id, ...]
    shipment_ids: tuple[Id, ...]
    capabilities: tuple[Literal["read", "propose", "apply", "review", "confirm"], ...]

    def require(self, tenant: str, shipment: str, capability: str) -> None:
        if (
            tenant != self.tenant_id
            or shipment not in self.shipment_ids
            or capability not in self.capabilities
        ):
            raise PermissionError("supply scope denied")

    def require_event(self, event_id: str) -> None:
        if event_id not in self.event_ids:
            raise PermissionError("incident scope denied")


class Command(Contract):
    tenant_id: Id
    event_id: Id
    shipment_id: Id
    expected_shipment_version: Version
    expected_budget_version: Version
    action: Action

    @property
    def operation_id(self) -> str:
        # A new workflow run/replan never creates a second effect for the same incident.
        return hashlib.sha256(
            (self.tenant_id + "\x00" + self.event_id + "\x00" + self.shipment_id).encode()
        ).hexdigest()


class Proposal(Contract):
    command: Command
    option: Option
    proposer_id: Id
    proposed_at: AwareDatetime
    expires_at: AwareDatetime
    payload_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    status: Literal["pending", "approved", "rejected", "expired"]
    reviewer_id: Id | None = None


class Receipt(Contract):
    command: Command
    payload_sha256: str
    cost_minor: Minor
    committed_at: AwareDatetime
    confirmation_deadline: AwareDatetime
    execution_run_id: Id
    shipment_version: Version
    budget_version: Version


class Snapshot(Contract):
    proposal: Proposal
    receipt: Receipt | None = None
    outcome: Literal[
        "pending",
        "approved",
        "rejected",
        "expired",
        "awaiting_confirmation",
        "confirmed",
        "confirmation_failed",
        "confirmation_timeout",
    ]


class Portfolio(Contract):
    """One SQL snapshot; budget covers the incident, rows cover the caller's scope."""

    event_id: Id
    as_of: AwareDatetime
    budget_version: Version
    spent_minor: Minor
    replans_used: Annotated[int, Field(ge=0, le=2)]
    shipments: tuple[Shipment, ...]
    snapshots: tuple[Snapshot, ...]
