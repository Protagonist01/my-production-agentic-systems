"""Prospective Revenue diagnostics criteria; never activates a release profile."""

from datetime import datetime
from typing import Annotated, Any, Literal, Self

from agent_harness.contracts import Contract
from agent_harness.evaluator_qualification import (
    QualificationDataset,
    QualificationProtocol,
    QualificationStudy,
    qualification_report,
)
from agent_harness.release_contracts import Sha256, pin
from pydantic import AwareDatetime, Field, model_validator

from revenue_evaluation import Observation, Plan, Variant, scorecard

Rate = Annotated[float, Field(ge=0, le=1)]


class Criteria(Contract):
    plan_sha256: Sha256
    frozen_at: AwareDatetime
    minimum_accuracy: Rate
    minimum_eligible_coverage: Rate
    maximum_false_admission: Rate
    maximum_group_error_upper: Rate
    maximum_p95_seconds: Annotated[float, Field(gt=0)]
    minimum_groups: Annotated[int, Field(gt=0)]
    required_slices: Annotated[tuple[str, ...], Field(min_length=1)]
    rationale_ref: str = Field(min_length=1)
    accepted: Literal[False] = False

    @model_validator(mode="after")
    def unique(self) -> Self:
        if len(set(self.required_slices)) != len(self.required_slices):
            raise ValueError("duplicate required slice")
        return self


class Study(Contract):
    criteria_sha256: Sha256
    started_at: AwareDatetime
    finished_at: AwareDatetime
    observations: tuple[Observation, ...]


def audit(plan: Plan, criteria: Criteria, study: Study, variant: Variant) -> dict[str, Any]:
    plan = Plan.model_validate_json(plan.canonical_json())
    criteria = Criteria.model_validate_json(criteria.canonical_json())
    study = Study.model_validate_json(study.canonical_json())
    if criteria.plan_sha256 != pin(plan) or study.criteria_sha256 != pin(criteria):
        raise ValueError("protocol/plan/study pin differs")
    if not criteria.frozen_at <= study.started_at <= study.finished_at:
        raise ValueError("criteria must precede every scheduled observation")
    if variant not in plan.variants:
        raise ValueError("unscheduled comparator")
    report = scorecard(plan, study.observations)
    measured = report["variants"][variant]
    failures: list[str] = []
    scopes = {"overall": measured}
    for name in criteria.required_slices:
        if name not in measured["slices"]:
            failures.append("missing_slice:" + name)
        else:
            scopes[name] = measured["slices"][name]
    for name, scope in scopes.items():
        checks = (
            (
                "accuracy",
                scope["reference_relative_correct"]["rate"],
                criteria.minimum_accuracy,
                True,
            ),
            (
                "coverage",
                scope["eligible_analysis_coverage"]["rate"],
                criteria.minimum_eligible_coverage,
                True,
            ),
            (
                "false_admission",
                scope["unrelated_or_insufficient_admitted"]["rate"],
                criteria.maximum_false_admission,
                False,
            ),
            (
                "group_error",
                scope["group_error_interval"][1],
                criteria.maximum_group_error_upper,
                False,
            ),
            ("latency", scope["latency"]["p95_seconds"], criteria.maximum_p95_seconds, False),
        )
        for field, value, threshold, lower in checks:
            applicable = {
                "coverage": scope["eligible_analysis_coverage"]["denominator"],
                "false_admission": scope["unrelated_or_insufficient_admitted"]["denominator"],
            }.get(field, 1)
            if not applicable:
                continue
            if value is None or (value < threshold if lower else value > threshold):
                failures.append(name + ":" + field)
        if scope["independent_group_proxy_count"] < criteria.minimum_groups:
            failures.append(name + ":groups")
        for field in ("invalid_proposals", "unauthorized_effects"):
            if scope[field]["rate"] != 0:
                failures.append(name + ":" + field)
        if scope["critical_reference_failures"]:
            failures.append(name + ":critical_reference_failure")
    return {
        "criteria_sha256": pin(criteria),
        "diagnostic_criteria_met": not failures,
        "failed_checks": failures,
        "report": report,
        "release_allowed": False,
        "criteria_accepted": False,
        "reference_authority_authenticated": False,
    }


def evaluator_diagnostics(
    dataset: QualificationDataset,
    protocol: QualificationProtocol,
    study: QualificationStudy,
    *,
    now: datetime,
) -> dict[str, object]:
    """Reuse the shared frozen, full-schedule judge test, not candidate self-agreement."""
    if dataset.agent != "revenue-integrity":
        raise ValueError("Revenue evaluator dataset required")
    report = qualification_report(dataset, protocol, study, now=now)
    return {
        "qualification_diagnostic": report,
        "evaluator_activated": False,
        "billing_meaning_certified": False,
        "release_allowed": False,
    }
