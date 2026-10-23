"""Server provisioned scopes and exact browser decisions; no client authority."""

import json
from typing import Annotated, Literal, Self

from agent_harness.contracts import Contract
from pydantic import AwareDatetime, Field, model_validator

from supply_chain.action_contracts import Grant, Id
from supply_chain.source_contracts import AlertFact

Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class IncidentScope(Contract):
    event_id: Id
    shipment_ids: Annotated[tuple[Id, ...], Field(min_length=1, max_length=12)]

    @model_validator(mode="after")
    def unique(self) -> Self:
        if len(set(self.shipment_ids)) != len(self.shipment_ids):
            raise ValueError("unique shipment scope required")
        return self


class Principal(Contract):
    username: Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9_.-]{2,63}$")]
    tenant_id: Id
    actor_id: Id
    role: Literal["operator", "reviewer", "confirmer", "viewer"]
    scopes: Annotated[tuple[IncidentScope, ...], Field(min_length=1, max_length=20)]

    @model_validator(mode="after")
    def unique(self) -> Self:
        if len({scope.event_id for scope in self.scopes}) != len(self.scopes):
            raise ValueError("unique incident scopes required")
        return self

    def grant(self, event: str) -> Grant:
        scope = next((s for s in self.scopes if s.event_id == event), None)
        if scope is None:
            raise PermissionError("incident scope denied")
        caps = {
            "operator": ("read", "propose", "apply"),
            "reviewer": ("read", "review"),
            "confirmer": ("read", "confirm"),
            "viewer": ("read",),
        }
        return Grant.model_validate_json(
            json.dumps(
                dict(
                    tenant_id=self.tenant_id,
                    actor_id=self.actor_id,
                    event_ids=(event,),
                    shipment_ids=scope.shipment_ids,
                    capabilities=caps[self.role],
                )
            )
        )


class Selection(Contract):
    event_id: Id
    shipment_id: Id
    payload_sha256: Digest


class Decision(Selection):
    approve: bool


class Confirmation(Selection):
    success: bool


class Assessment(Contract):
    event_id: Id


class IncidentContext(Contract):
    tenant_id: Id
    event_id: Id
    label: Annotated[str, Field(min_length=1, max_length=160)]
    source_kind: Literal["invented", "s1-public-observation"]
    source_ref: str | None = None
    alert: AlertFact | None = None
    max_alert_age_seconds: Annotated[int, Field(ge=1, le=1800)] = 1800

    @model_validator(mode="after")
    def origin(self) -> Self:
        if self.source_kind == "s1-public-observation" and self.source_ref is None:
            raise ValueError("S1 public context requires a pinned source reference")
        return self


class Notice(Contract):
    notice_id: Digest
    tenant_id: Id
    event_id: Id
    shipment_id: Id
    state: str
    body: Annotated[str, Field(min_length=1, max_length=2000)]
    created_at: AwareDatetime
    read: bool = False
