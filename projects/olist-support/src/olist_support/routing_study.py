"""Complete scheduled denominators for development routing comparisons; no release gate."""

from collections import Counter
from math import ceil
from typing import Annotated, Literal, Self

from agent_harness.baseline_recording import VerifiedBaseline
from agent_harness.contracts import Contract
from agent_harness.release_contracts import Sha256, pin
from agent_harness.release_evidence import VerifiedEvidence
from pydantic import Field, model_validator

from olist_support.routing_evaluation import RoutingPopulation

Variant = Literal["candidate", "legacy", "rules", "always-review"]
VARIANTS: tuple[Variant, ...] = ("candidate", "legacy", "rules", "always-review")


class RoutingProtocol(Contract):
    version: Literal["olist-routing-development-protocol-v1"] = (
        "olist-routing-development-protocol-v1"
    )
    population_sha256: Sha256
    manifest_sha256: Sha256
    candidate_sha256: dict[Variant, Sha256]
    trial_ids: Annotated[tuple[str, ...], Field(min_length=3, max_length=3)]
    provenance: Literal["development_only"] = "development_only"
    frozen_for_provider: Literal[False] = False
    release_allowed: Literal[False] = False

    @model_validator(mode="after")
    def complete(self) -> Self:
        if set(self.candidate_sha256) != set(VARIANTS):
            raise ValueError("all four declared comparator pins required")
        if len(set(self.candidate_sha256.values())) != 4:
            raise ValueError("different algorithms require different candidate pins")
        if len(set(self.trial_ids)) != len(self.trial_ids) or any(
            not t.strip() for t in self.trial_ids
        ):
            raise ValueError("distinct nonempty trials required")
        return self


class RoutingScoreRow(Contract):
    variant: Variant
    case_id: Sha256
    trial_id: str
    fields: dict[str, bool | None]
    unresolved: bool
    elapsed_seconds: Annotated[float, Field(ge=0)] | None = None

    @model_validator(mode="after")
    def no_false_completion(self) -> Self:
        required = {
            "intent",
            "amount",
            "action",
            "review_reason",
            "truthful_confirmation",
            "exact_state",
            "duplicate_delivery",
            "state_safety",
        }
        if self.fields.get("correct") is True and (
            self.unresolved
            or any(self.fields.get(k) is not True for k in required)
            or "recovery" in self.fields
            and self.fields["recovery"] is not True
        ):
            raise ValueError("correct routing row cannot hide missing/failed fields")
        return self


def summarize(
    protocol: RoutingProtocol, population: RoutingPopulation, rows: tuple[RoutingScoreRow, ...]
) -> dict[str, object]:
    protocol = RoutingProtocol.model_validate_json(protocol.canonical_json())
    population = RoutingPopulation.model_validate_json(population.canonical_json())
    if protocol.population_sha256 != pin(population):
        raise ValueError("routing population differs from protocol")
    expected = {
        (v, c.case_id, t) for v in VARIANTS for c in population.entries for t in protocol.trial_ids
    }
    indexed = {
        (r.variant, r.case_id, r.trial_id): RoutingScoreRow.model_validate_json(r.canonical_json())
        for r in rows
    }
    if len(indexed) != len(rows) or not set(indexed).issubset(expected):
        raise ValueError("duplicate or foreign routing row")
    recovery_ids = {c.case_id for c in population.entries if c.recovery_required}
    if any(
        r.fields.get("correct") is True
        and r.case_id in recovery_ids
        and r.fields.get("recovery") is not True
        for r in rows
    ):
        raise ValueError("correct routing row omits required recovery")
    groups: dict[Variant, object] = {}
    for variant in VARIANTS:
        keys = {k for k in expected if k[0] == variant}
        actual = [indexed[k] for k in sorted(keys) if k in indexed]
        metrics = {}
        for field in (
            "intent",
            "amount",
            "action",
            "review_reason",
            "truthful_confirmation",
            "exact_state",
            "duplicate_delivery",
            "correct",
            "state_safety",
            "recovery",
        ):
            applicable = {
                k
                for k in keys
                if field != "recovery"
                or next(c.recovery_required for c in population.entries if c.case_id == k[1])
            }
            field_rows = [indexed[k] for k in applicable if k in indexed]
            true = sum(r.fields.get(field) is True for r in field_rows)
            false = sum(r.fields.get(field) is False for r in field_rows)
            metrics[field] = {
                "correct": true,
                "incorrect": false,
                "unknown_or_missing": len(applicable) - true - false,
                "scheduled": len(applicable),
            }
        timings = sorted(r.elapsed_seconds for r in actual if r.elapsed_seconds is not None)
        groups[variant] = {
            "scheduled": len(keys),
            "observed": len(actual),
            "missing": len(keys) - len(actual),
            "unresolved": sum(r.unresolved for r in actual),
            "fields": metrics,
            "timing_observed": len(timings),
            "timing_unknown_or_missing": len(keys) - len(timings),
            "p95_observed_seconds": timings[ceil(len(timings) * 0.95) - 1] if timings else None,
            "trial_latency_complete": len(timings) == len(keys),
            "timing_scope": "parent_owned_trial_including_setup_cleanup",
            "latency_target_assessable": False,
        }
    return {
        "version": "olist-routing-development-summary-v1",
        "scheduled": len(expected),
        "observed": len(rows),
        "missing": len(expected) - len(rows),
        "source_groups": len({c.group_id for c in population.entries}),
        "declared_language_families": len({c.language_family for c in population.entries}),
        "reference_routes": dict(Counter(c.reference.expected.intent for c in population.entries)),
        "variants": groups,
        "qualification_met": False,
        "release_allowed": False,
        "semantic_gold_validated": False,
    }


def assemble(
    protocol: RoutingProtocol,
    population: RoutingPopulation,
    evidence: dict[Variant, "VerifiedEvidence | VerifiedBaseline"],
) -> dict[str, object]:
    """Use domain-verified readers first; pin algorithms/schedules before projection.

    Missing variants remain missing. This projection never certifies an evidence object,
    annotation, provider authority or application release by itself.
    """
    from olist_support.routing_h10 import FIXTURE, manifest_for

    manifest = manifest_for(population)
    rows = []
    for variant, verified in evidence.items():
        if (
            variant not in VARIANTS
            or pin(verified.manifest.candidate) != protocol.candidate_sha256[variant]
        ):
            raise ValueError("routing comparison candidate differs from protocol")
        schedule = verified.batch.schedule
        expected_origin = "mock" if variant in ("candidate", "legacy") else "deterministic"
        if (
            variant in ("candidate", "legacy")
            and getattr(verified.manifest, "origin", None) != expected_origin
            or variant in ("rules", "always-review")
            and getattr(verified.manifest, "algorithm", None) != "olist-routing-" + variant + "-v1"
        ):
            raise ValueError("routing comparison evidence origin differs")
        if (
            schedule.manifest.sha256 != protocol.manifest_sha256
            or schedule.manifest.manifest_id != manifest.manifest_id
            or schedule.manifest.version != manifest.version
            or schedule.state_fixture != FIXTURE
            or set(schedule.trial_ids) != set(protocol.trial_ids)
        ):
            raise ValueError("routing comparison schedule differs")
        for row in verified.batch.rows:
            fields: dict[str, bool | None] = {}
            unresolved = bool(row.errors) or row.report is None
            if row.report is not None:
                report = row.report.report
                unresolved = unresolved or report.result.outcome in ("failed", "blocked")
                for score in report.scores:
                    if score.metric in fields:
                        raise ValueError("duplicate routing score metric")
                    if score.failure is not None:
                        fields[score.metric] = None
                        unresolved = True
                    elif score.value in (0.0, 1.0):
                        fields[score.metric] = bool(score.value)
                    else:
                        raise ValueError("routing scores must be explicit binary fields")
            rows.append(
                RoutingScoreRow(
                    variant=variant,
                    case_id=row.task.context.case_id,
                    trial_id=row.task.context.trial_id,
                    fields=fields,
                    unresolved=unresolved,
                    elapsed_seconds=row.timing.elapsed_seconds if row.timing is not None else None,
                )
            )
    return summarize(protocol, population, tuple(rows))
