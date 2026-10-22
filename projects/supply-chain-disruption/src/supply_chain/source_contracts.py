"""Separate public facts from retrospective shipment outcomes."""

from datetime import datetime
from typing import Annotated, Literal

from agent_harness.contracts import Contract, NonEmpty
from pydantic import AwareDatetime, Field, NaiveDatetime

Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class SourcePin(Contract):
    source_version: Literal["dataco-v5-nws-independent-v1"] = "dataco-v5-nws-independent-v1"
    dataco_sha256: Digest
    dataco_bytes: Annotated[int, Field(gt=0, le=150_000_000)]
    description_sha256: Digest
    description_bytes: Annotated[int, Field(gt=0, le=1_000_000)]
    nws_sha256: Digest
    nws_bytes: Annotated[int, Field(gt=0, le=30_000_000)]
    dataco_observed_at: AwareDatetime
    weather_captured_at: AwareDatetime
    weather_http_date: str | None = None
    weather_cache_control: str | None = None
    weather_http_expires: str | None = None


class ShipmentFact(Contract):
    source_key: Digest
    observed_at: AwareDatetime
    recorded_order_time: NaiveDatetime
    original_timezone: Literal["unverified"] = "unverified"
    availability: Literal["snapshot-observation-only"] = "snapshot-observation-only"
    destination_country: NonEmpty
    destination_region: NonEmpty
    shipping_mode: NonEmpty
    scheduled_days: Annotated[int, Field(ge=0, le=365)]
    quantity: Annotated[int, Field(gt=0, le=1_000_000)]
    category: NonEmpty


class ShipmentTarget(Contract):
    source_key: Digest
    source_order_id: NonEmpty
    source_item_id: NonEmpty
    recorded_shipping_time: NaiveDatetime
    actual_shipping_days: Annotated[int, Field(ge=0, le=365)]
    delivery_status: NonEmpty
    late_delivery_flag: Literal[0, 1]
    order_status: NonEmpty


class AlertFact(Contract):
    source_key: Digest
    captured_at: AwareDatetime
    sent: AwareDatetime
    effective: AwareDatetime
    onset: AwareDatetime | None
    expires: AwareDatetime
    ends: AwareDatetime | None
    status: NonEmpty
    message_type: NonEmpty
    event: NonEmpty
    area: NonEmpty
    severity: NonEmpty
    urgency: NonEmpty
    certainty: NonEmpty


def aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("scenario clock must have an explicit offset")
    return value
