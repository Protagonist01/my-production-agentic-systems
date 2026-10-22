"""Explicit hybrid observation adapter. Never infer weather causality or outcomes."""

from datetime import datetime, timedelta

from supply_chain.action_contracts import Shipment
from supply_chain.source_contracts import ShipmentFact


def hybrid_observation(
    fact: ShipmentFact,
    *,
    tenant_id: str,
    shipment_id: str,
    region: str,
    clock: datetime,
    estimated_delay_hours: int,
    delay_cost_minor_per_hour: int,
    max_age_seconds: int,
) -> Shipment:
    """Caller supplies constructed estimates separately; source is observation only.

    Callers must obtain the fact from the S1 pinned public reader. This accepts no
    ShipmentTarget, delivery-status fields, alert history or realized intervention cost.
    """
    fact = ShipmentFact.model_validate_json(fact.canonical_json())
    if not 1 <= max_age_seconds <= 1800:
        raise ValueError("explicit 1..1800 second observation allowance required")
    result = Shipment(
        tenant_id=tenant_id,
        shipment_id=shipment_id,
        region=region,
        observed_at=fact.observed_at,
        expires_at=fact.observed_at + timedelta(seconds=max_age_seconds),
        estimated_delay_hours=estimated_delay_hours,
        delay_cost_minor_per_hour=delay_cost_minor_per_hour,
        provenance="source-observation-hybrid",
        source_ref="dataco-v5:" + fact.source_key,
    )
    result.require_fresh(clock)
    return result
