"""Complete reference-relative service comparison counts; never a release approval.

Domain/H10 readers must verify artifacts before assemble(). Pure summarize() only computes
declared observations; it does not authenticate sources, labels, independence or permissions.
"""

import json
from collections import defaultdict
from decimal import Decimal
from math import ceil
from typing import Annotated, Literal, Self

from agent_harness.baseline_recording import VerifiedBaseline
from agent_harness.contracts import Contract, NonEmpty, Usage
from agent_harness.controls import add_money
from agent_harness.release_contracts import Sha256, pin, sha256
from agent_harness.release_evidence import VerifiedEvidence
from agent_harness.scorecard_stats import binomial_bounds
from pydantic import Field, model_validator

from olist_support.service_evaluation import ServiceScenario
from olist_support.service_h10 import ENVIRONMENT, FIXTURE, manifest_for

Variant = Literal["candidate", "rules", "always-review"]
VARIANTS: tuple[Variant, ...] = ("candidate", "rules", "always-review")
FIELDS = (
    "intent",
    "amount",
    "action",
    "review_reason",
    "truthful_confirmation",
    "exact_state",
    "duplicate_delivery",
    "proposal_isolation",
    "customer_authority",
    "audit_integrity",
    "state_safety",
    "correct",
    "routing_safe",
    "observed_review",
)


class ServicePopulation(Contract):
    version: Literal["olist-service-population-v1"] = "olist-service-population-v1"
    entries: Annotated[tuple[ServiceScenario, ...], Field(min_length=1)]
    release_allowed: Literal[False] = False

    @model_validator(mode="after")
    def valid_manifest(self) -> Self:
        manifest_for(self.entries)
        return self


class ServiceProtocol(Contract):
    version: Literal["olist-service-comparison-preparation-v1"] = (
        "olist-service-comparison-preparation-v1"
    )
    population_sha256: Sha256
    manifest_sha256: Sha256
    candidate_sha256: dict[Variant, Sha256]
    trial_ids: Annotated[tuple[NonEmpty, ...], Field(min_length=3, max_length=3)]
    expected_origin: Literal["mock"] = "mock"
    frozen_for_provider: Literal[False] = False
    release_allowed: Literal[False] = False

    @model_validator(mode="after")
    def complete(self) -> Self:
        if (
            set(self.candidate_sha256) != set(VARIANTS)
            or len(set(self.candidate_sha256.values())) != 3
            or len(set(self.trial_ids)) != 3
        ):
            raise ValueError("three distinct composition pins and trial IDs required")
        return self


class ServiceRow(Contract):
    variant: Variant
    case_id: NonEmpty
    trial_id: NonEmpty
    fields: dict[str, bool | None]
    unresolved: bool
    elapsed_seconds: Annotated[float, Field(ge=0, allow_inf_nan=False)] | None = None
    usage: Usage | None = None

    @model_validator(mode="after")
    def honest_fields(self) -> Self:
        if not set(self.fields).issubset({*FIELDS, "recovery"}):
            raise ValueError("unknown service score field")
        if self.fields.get("correct") is True and (
            self.unresolved
            or any(
                self.fields.get(k) is not True
                for k in FIELDS
                if k not in ("correct", "observed_review", "routing_safe")
            )
            or "recovery" in self.fields
            and self.fields["recovery"] is not True
        ):
            raise ValueError("correct service result cannot omit required observations")
        return self


def _metric(values: list[bool | None]) -> dict[str, int | float | None]:
    true, false = values.count(True), values.count(False)
    return {
        "passed": true,
        "failed": false,
        "unknown_or_missing": len(values) - true - false,
        "scheduled": len(values),
        "pass_fraction": true / len(values) if values else None,
    }


def _and(*values: bool | None) -> bool | None:
    return False if False in values else None if None in values else True


def _groups(population: ServicePopulation) -> dict[str, str]:
    parents: dict[str, str] = {}

    def find(key: str) -> str:
        parents.setdefault(key, key)
        while parents[key] != key:
            parents[key] = parents[parents[key]]
            key = parents[key]
        return key

    for scenario in population.entries:
        label = scenario.reference
        first = "case:" + scenario.case_id
        keys = (
            "source:" + label.case_id,
            "group:" + label.group_id,
            "language:" + label.language_family,
            "order:" + sha256(json.dumps([label.order.tenant_id, label.order.order_id]).encode()),
            "text:" + sha256(" ".join(label.reference.text.casefold().split()).encode()),
        )
        for key in keys:
            parents[find(key)] = find(first)
    return {s.case_id: find("case:" + s.case_id) for s in population.entries}


def summarize(
    protocol: ServiceProtocol, population: ServicePopulation, rows: tuple[ServiceRow, ...]
) -> dict[str, object]:
    protocol = ServiceProtocol.model_validate_json(protocol.canonical_json())
    population = ServicePopulation.model_validate_json(population.canonical_json())
    manifest = manifest_for(population.entries)
    if (
        pin(population) != protocol.population_sha256
        or sha256(manifest.canonical_json().encode()) != protocol.manifest_sha256
    ):
        raise ValueError("service population/manifest differs from protocol")
    scenarios = {s.case_id: s for s in population.entries}
    case_expectations = {e.case.case_id: e.case.expected for e in manifest.entries}
    expected = {(v, c, t) for v in VARIANTS for c in scenarios for t in protocol.trial_ids}
    actual: dict[tuple[str, str, str], ServiceRow] = {}
    for original in rows:
        row = ServiceRow.model_validate_json(original.canonical_json())
        key = row.variant, row.case_id, row.trial_id
        if key in actual or key not in expected:
            raise ValueError("duplicate or unscheduled service row")
        if (
            row.fields.get("correct") is True
            and scenarios[row.case_id].reference.recovery_required
            and row.fields.get("recovery") is not True
        ):
            raise ValueError("correct service result omits scheduled recovery")
        actual[key] = row
    connected = _groups(population)
    group_splits: dict[str, set[str]] = defaultdict(set)
    for scenario in population.entries:
        group_splits[connected[scenario.case_id]].add(scenario.reference.split)
    if any(len(splits) != 1 for splits in group_splits.values()):
        raise ValueError("connected source/text/language/order group crosses splits")
    variants: dict[str, object] = {}
    for variant in VARIANTS:
        keys = sorted(k for k in expected if k[0] == variant)

        def value(key: tuple[str, str, str], name: str) -> bool | None:
            row = actual.get(key)
            result = row.fields.get(name) if row else None
            # A saved fallback plan can agree with a reference despite a failed attempt.
            # Keep observed state facts, but never award quality credit to unresolved runs.
            if (
                row
                and row.unresolved
                and result is True
                and name
                in ("intent", "amount", "action", "review_reason", "correct", "observed_review")
            ):
                return None
            return result

        fields = {}
        for name in (*FIELDS, "recovery"):
            applicable = [
                k for k in keys if name != "recovery" or scenarios[k[1]].reference.recovery_required
            ]
            fields[name] = _metric([value(k, name) for k in applicable])
        eligible = [k for k in keys if scenarios[k[1]].expects_commit]
        review = [k for k in keys if case_expectations[k[1]].required_review]
        durations = []
        for key in keys:
            observed = actual.get(key)
            if observed and observed.elapsed_seconds is not None:
                durations.append(observed.elapsed_seconds)
        durations.sort()
        usage = [actual[k].usage for k in keys if k in actual and actual[k].usage is not None]
        costs: dict[str, Decimal] = {}
        for item in usage:
            if item is not None and item.cost is not None and item.cost_currency is not None:
                costs[item.cost_currency] = add_money(
                    costs.get(item.cost_currency, Decimal(0)), item.cost
                )
        groups: dict[str, list[bool | None]] = defaultdict(list)
        for key in keys:
            groups[connected[key[1]]].append(value(key, "correct"))
        failed_groups = sum(False in vs for vs in groups.values())
        unknown_groups = sum(
            False not in vs and not all(v is True for v in vs) for vs in groups.values()
        )
        lower, _ = binomial_bounds(failed_groups, len(groups))
        _, upper = binomial_bounds(failed_groups + unknown_groups, len(groups))
        cases_pass = sum(
            all(value((variant, c, t), "correct") is True for t in protocol.trial_ids)
            for c in scenarios
        )
        variants[variant] = {
            "scheduled": len(keys),
            "observed": sum(k in actual for k in keys),
            "missing": sum(k not in actual for k in keys),
            "unresolved": sum(actual[k].unresolved for k in keys if k in actual),
            "fields": fields,
            "joint_intent_amount": _metric(
                [_and(value(k, "intent"), value(k, "amount")) for k in keys]
            ),
            "eligible_completion": _metric(
                [
                    _and(
                        value(k, "action"),
                        value(k, "exact_state"),
                        value(k, "customer_authority"),
                        value(k, "truthful_confirmation"),
                    )
                    for k in eligible
                ]
            ),
            "required_review_routing": _metric(
                [
                    _and(
                        value(k, "action"),
                        value(k, "review_reason"),
                        value(k, "observed_review"),
                        value(k, "routing_safe"),
                    )
                    for k in review
                ]
            ),
            "all_repetition_case_passes": cases_pass,
            "cases_scheduled": len(scenarios),
            "declared_connected_groups": len(groups),
            "observed_failed_groups": failed_groups,
            "unknown_groups": unknown_groups,
            "conditional_group_error_bounds": {
                "lower": lower,
                "upper": upper,
                "method": "exact_boundary_wilson_interior_95_percent",
                "independence_authenticated": False,
            },
            "timing": {
                "scope": "parent_trial_setup_execution_cleanup",
                "observed": len(durations),
                "unknown_or_missing": len(keys) - len(durations),
                "p95_observed_seconds": durations[ceil(len(durations) * 0.95) - 1]
                if durations
                else None,
                "complete": len(durations) == len(keys),
                "api_latency_target_assessable": False,
            },
            "usage": {
                "observed_rows": len(usage),
                "missing_rows": len(keys) - len(usage),
                "reported_model_calls": sum(u.model_calls for u in usage if u is not None),
                "known_input_tokens": sum(u.input_tokens or 0 for u in usage if u is not None),
                "input_tokens_unknown_or_missing": len(keys)
                - sum(u.input_tokens is not None for u in usage if u is not None),
                "known_output_tokens": sum(u.output_tokens or 0 for u in usage if u is not None),
                "output_tokens_unknown_or_missing": len(keys)
                - sum(u.output_tokens is not None for u in usage if u is not None),
                "known_reported_costs": {c: str(v) for c, v in sorted(costs.items())},
                "cost_unknown_or_missing": len(keys)
                - sum(u.cost is not None for u in usage if u is not None),
                "billing_cost_verified": False,
            },
        }
    return {
        "version": "olist-service-comparison-report-v1",
        "scheduled": len(expected),
        "observed": len(actual),
        "missing": len(expected) - len(actual),
        "variants": variants,
        "evidence_scope": "reference_relative_preparation",
        "release_allowed": False,
        "qualification_met": False,
        "semantic_gold_validated": False,
    }


def assemble(
    protocol: ServiceProtocol,
    population: ServicePopulation,
    evidence: dict[Variant, VerifiedEvidence | VerifiedBaseline],
) -> dict[str, object]:
    """Project already domain/H10-verified artifacts; never authenticate a constructed object."""
    rows = []
    for variant, verified in evidence.items():
        if (
            variant not in VARIANTS
            or pin(verified.manifest.candidate) != protocol.candidate_sha256[variant]
        ):
            raise ValueError("service comparator composition differs")
        if (
            variant == "candidate"
            and (
                not isinstance(verified, VerifiedEvidence)
                or verified.manifest.origin != protocol.expected_origin
            )
        ) or (
            variant != "candidate"
            and (
                not isinstance(verified, VerifiedBaseline)
                or verified.manifest.algorithm != "olist-confirmed-service-" + variant + "-v1"
            )
        ):
            raise ValueError("service comparator origin/algorithm differs")
        schedule = verified.batch.schedule
        if (
            schedule.manifest.sha256 != protocol.manifest_sha256
            or schedule.state_fixture != FIXTURE
            or schedule.environment_version != ENVIRONMENT
            or schedule.trial_ids != protocol.trial_ids
            or set(schedule.case_ids) != {s.case_id for s in population.entries}
        ):
            raise ValueError("service comparator schedule differs")
        for row in verified.batch.rows:
            fields: dict[str, bool | None] = {}
            report = row.report.report if row.report else None
            if report:
                for score in report.scores:
                    if (
                        score.metric in fields
                        or score.failure is None
                        and score.value not in (0, 1)
                    ):
                        raise ValueError(
                            "service score must be unique binary or explicitly unknown"
                        )
                    fields[score.metric] = None if score.failure else bool(score.value)
            rows.append(
                ServiceRow(
                    variant=variant,
                    case_id=row.task.context.case_id,
                    trial_id=row.task.context.trial_id,
                    fields=fields,
                    unresolved=bool(row.errors)
                    or report is None
                    or report.result.outcome in ("failed", "blocked"),
                    elapsed_seconds=row.timing.elapsed_seconds if row.timing else None,
                    usage=report.result.usage if report else None,
                )
            )
    return summarize(protocol, population, tuple(rows))
