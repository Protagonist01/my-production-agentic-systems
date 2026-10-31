"""Development-only complete denominators for separately sealed three-trial recordings."""

import json
from typing import Literal, Self

from agent_harness.baseline_recording import VerifiedBaseline
from agent_harness.contracts import Contract
from agent_harness.cost_accounting import control_pin
from agent_harness.release_contracts import Sha256, pin, sha256
from agent_harness.release_evidence import VerifiedEvidence
from agent_harness.routing_budget import RoutingExtension
from pydantic import model_validator

from olist_support.routing_evaluation import RoutingPopulation
from olist_support.routing_h10 import FIXTURE, manifest_for
from olist_support.routing_study import (
    VARIANTS,
    RoutingProtocol,
    RoutingScoreRow,
    Variant,
    summarize,
)


class ControlledStudyProtocol(Contract):
    version: Literal["olist-controlled-development-protocol-v2"] = (
        "olist-controlled-development-protocol-v2"
    )
    extension: RoutingExtension
    tariff_sha256: Sha256
    project_sha256: Sha256
    candidate_sha256: dict[Variant, Sha256]
    expected_origin: Literal["mock", "provider"]
    release_allowed: Literal[False] = False
    independent_gold: Literal[False] = False

    @model_validator(mode="after")
    def variants(self) -> Self:
        if self.extension.execution_origin != self.expected_origin:
            raise ValueError("controlled protocol origin differs from allowance scope")
        if (
            set(self.candidate_sha256) != set(VARIANTS)
            or len(set(self.candidate_sha256.values())) != 4
        ):
            raise ValueError("four distinct controlled comparator pins required")
        return self

    @property
    def scope_sha256(self) -> str:
        return sha256(
            json.dumps(
                {"history": self.extension.historical_pins, "routing": pin(self.extension)},
                sort_keys=True,
            ).encode()
        )

    @property
    def control_sha256(self) -> str:
        return control_pin(
            self.extension.historical_pins[0],
            self.tariff_sha256,
            self.project_sha256,
            self.scope_sha256,
        )


def assemble_controlled(
    protocol: ControlledStudyProtocol,
    population: RoutingPopulation,
    evidence: dict[tuple[Variant, str], VerifiedEvidence | VerifiedBaseline],
) -> dict[str, object]:
    """Use domain-verified readers first. Absent/unverifiable recordings remain missing.

    This does not authenticate arbitrary Python evidence objects, approve a scope or turn
    development projections into independent gold. Original v1 mock assembly is unchanged.
    """
    protocol = ControlledStudyProtocol.model_validate_json(protocol.canonical_json())
    population = RoutingPopulation.model_validate_json(population.canonical_json())
    ext = protocol.extension
    if pin(population) != ext.population_sha256 or {c.case_id for c in population.entries} != {
        s.case_id for s in ext.slots[2:]
    }:
        raise ValueError("controlled study population differs from frozen scope")
    indexed = {c.case_id: c for c in population.entries}
    if any(s.case_sha256 != pin(indexed[s.case_id]) for s in ext.slots[2:]):
        raise ValueError("controlled case reference differs from scope")
    rows = []
    for (variant, case_id), saved in evidence.items():
        if variant not in VARIANTS or case_id not in indexed:
            raise ValueError("foreign controlled recording")
        single = manifest_for(RoutingPopulation(entries=(indexed[case_id],)))
        spec = saved.manifest.candidate
        if pin(spec) != protocol.candidate_sha256[variant]:
            raise ValueError("controlled comparator pin differs")
        if variant in ("candidate", "legacy"):
            if (
                not isinstance(saved, VerifiedEvidence)
                or saved.manifest.origin != protocol.expected_origin
                or spec.provider_control_sha256 != protocol.control_sha256
            ):
                raise ValueError("controlled evidence origin or scope differs")
        elif (
            not isinstance(saved, VerifiedBaseline)
            or saved.manifest.algorithm != "olist-routing-" + variant + "-v1"
        ):
            raise ValueError("controlled deterministic origin differs")
        schedule = saved.batch.schedule
        expected_slots = [s for s in ext.slots[2:] if s.case_id == case_id and s.variant == variant]
        if (
            schedule.case_ids != (case_id,)
            or schedule.trial_ids != ("trial-1", "trial-2", "trial-3")
            or schedule.manifest.sha256 != sha256(single.canonical_json().encode())
            or schedule.state_fixture != FIXTURE
            or len(saved.batch.rows) != 3
        ):
            raise ValueError("controlled three-trial recording schedule differs")
        for row in saved.batch.rows:
            ctx = row.task.context
            if variant in ("candidate", "legacy"):
                slot = next((s for s in expected_slots if s.trial_id == ctx.trial_id), None)
                if slot is None or (ctx.run_id, ctx.tenant_id, ctx.business_event_id) != (
                    slot.run_id,
                    slot.tenant_id,
                    slot.business_event_id,
                ):
                    raise ValueError("controlled recording identity differs from reserved slot")
            fields: dict[str, bool | None] = {}
            unresolved = bool(row.errors) or row.report is None
            if row.report is not None:
                report = row.report.report
                unresolved = unresolved or report.result.outcome in ("failed", "blocked")
                for score in report.scores:
                    if score.metric in fields:
                        raise ValueError("duplicate controlled score")
                    if score.failure:
                        fields[score.metric] = None
                        unresolved = True
                    elif score.value in (0.0, 1.0):
                        fields[score.metric] = bool(score.value)
                    else:
                        raise ValueError("controlled scores must be binary or explicitly unknown")
            rows.append(
                RoutingScoreRow(
                    variant=variant,
                    case_id=case_id,
                    trial_id=ctx.trial_id,
                    fields=fields,
                    unresolved=unresolved,
                    elapsed_seconds=row.timing.elapsed_seconds if row.timing else None,
                )
            )
    manifest = manifest_for(population)
    projection = RoutingProtocol(
        population_sha256=pin(population),
        manifest_sha256=sha256(manifest.canonical_json().encode()),
        candidate_sha256=protocol.candidate_sha256,
        trial_ids=("trial-1", "trial-2", "trial-3"),
    )
    result = summarize(projection, population, tuple(rows))
    result.update(
        version="olist-controlled-development-summary-v2",
        evidence_origin=protocol.expected_origin,
        extension_sha256=pin(ext),
        recordings_observed=len(evidence),
        recordings_scheduled=96,
    )
    return result
