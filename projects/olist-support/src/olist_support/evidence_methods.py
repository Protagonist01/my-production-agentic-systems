"""Owner-accepted Olist method-coverage audit, separate from release qualification.

Trusted scope/claim pins must come from the control plane and verified domain readers,
never from the same untrusted records being audited. This module authenticates neither
reviewer identities nor factual source content and never grants release permission.
"""

import json
from dataclasses import dataclass
from typing import Annotated, Final, Literal, Self

from agent_harness.contracts import Contract, NonEmpty, WireContract
from agent_harness.evaluation_standards import StandardProfile
from agent_harness.evaluator_qualification import (
    QualificationDataset,
    QualificationProtocol,
    QualificationStudy,
    qualification_report,
)
from agent_harness.release_contracts import Sha256, pin, sha256
from pydantic import AwareDatetime, Field, model_validator

PROPOSAL: Final = "51e7b9ef21b70f551c1fe4715a485dce9db5bc9ec26c774f4bec7d87424ca7c7"
PROFILE: Final = "d365ff018ea6be9c05492eb51090aed5532b818ab692e1933008b7d65ccf5cc6"
FieldName = Literal[
    "intent",
    "amount",
    "action",
    "review_reason",
    "truthful_confirmation",
    "exact_state",
    "duplicate_delivery",
    "recovery",
]
Method = Literal[
    "external_reference",
    "validated_construction",
    "qualified_model",
    "independent_program",
    "state_observation",
    "fixed_template",
    "fault_observation",
]
SEMANTIC: Final[tuple[Method, ...]] = (
    "external_reference",
    "validated_construction",
    "qualified_model",
)
CLAIMS: Final[dict[str, dict[str, tuple[Method, ...]]]] = {
    "intent": {"meaning": SEMANTIC},
    "amount": {"requested_meaning": SEMANTIC, "arithmetic": ("independent_program",)},
    "action": {"eligibility": ("independent_program",), "observed_action": ("state_observation",)},
    "review_reason": {
        "failed_predicates": ("independent_program",),
        "semantic_applicability": SEMANTIC,
    },
    "truthful_confirmation": {"message_consistency": ("fixed_template",)},
    "exact_state": {"authoritative_state": ("state_observation",)},
    "duplicate_delivery": {"repeated_effect": ("state_observation",)},
    "recovery": {"declared_fault": ("fault_observation",)},
}


class MethodDesignAcceptance(WireContract):
    version: Literal["olist-v2-method-design-owner-acceptance-v1"]
    recorded_at: AwareDatetime
    recorded_at_is_owner_action_time: Literal[False]
    reply_reference: NonEmpty
    exact_reply: Literal["Approve this Olist v2 evidence-method design"]
    proposal_sha256: Literal["51e7b9ef21b70f551c1fe4715a485dce9db5bc9ec26c774f4bec7d87424ca7c7"]
    scope: Literal["olist_v2_method_design_and_implementation_only"]
    method_design_accepted: Literal[True]
    qualification_cohort_approved: Literal[False]
    statistical_protocol_approved: Literal[False]
    baseline_approved: Literal[False]
    threshold_freeze_approved: Literal[False]
    provider_calls_authorized: Literal[0]
    release_allowed: Literal[False]


class MethodCase(Contract):
    case_id: Sha256
    input_sha256: Sha256
    reference_sha256: Sha256
    source_keys: Annotated[tuple[NonEmpty, ...], Field(min_length=1)]
    slices: Annotated[tuple[NonEmpty, ...], Field(min_length=1)]
    split: Literal["development", "regression", "holdout"]

    @model_validator(mode="after")
    def unique(self) -> Self:
        if len(set(self.source_keys)) != len(self.source_keys) or len(set(self.slices)) != len(
            self.slices
        ):
            raise ValueError("duplicate source key or slice")
        return self


class MethodScope(Contract):
    field: FieldName
    part: NonEmpty
    method: Method
    input_sha256: Sha256
    reference_sha256: Sha256
    source_sha256: Sha256
    evaluator_sha256: Sha256
    slices: Annotated[tuple[NonEmpty, ...], Field(min_length=1)]
    permitted_use: Literal["development", "qualification"]
    authority_reference: NonEmpty
    granted_at: AwareDatetime
    expires_at: AwareDatetime
    qualification_report_sha256: Sha256 | None = None

    @model_validator(mode="after")
    def applicable_method(self) -> Self:
        if self.method not in CLAIMS[self.field].get(self.part, ()):
            raise ValueError("method cannot establish this claim part")
        if self.expires_at <= self.granted_at or len(set(self.slices)) != len(self.slices):
            raise ValueError("invalid scope interval or duplicate slice")
        if (self.method == "qualified_model") != (self.qualification_report_sha256 is not None):
            raise ValueError("model assessment requires a separately bound qualification report")
        return self


class MethodClaim(Contract):
    case_id: Sha256
    field: FieldName
    part: NonEmpty
    scope_sha256: Sha256
    input_sha256: Sha256
    reference_sha256: Sha256
    source_sha256: Sha256
    evaluator_sha256: Sha256
    evidence_sha256: Sha256
    observed_at: AwareDatetime
    disposition: Literal["supported", "contradicted", "unresolved"]


@dataclass(frozen=True)
class QualificationMaterial:
    dataset: QualificationDataset
    protocol: QualificationProtocol
    study: QualificationStudy


def qualification_pin(report: dict[str, object]) -> str:
    return sha256(
        json.dumps(report, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    )


def audit_methods(
    profile: StandardProfile,
    cases: tuple[MethodCase, ...],
    claims: tuple[MethodClaim, ...],
    scopes: tuple[MethodScope, ...],
    *,
    acceptance_raw: bytes,
    expected_acceptance_sha256: str,
    trusted_scope_pins: frozenset[str],
    verified_claim_pins: frozenset[str],
    qualifications: dict[str, QualificationMaterial],
    now: AwareDatetime,
) -> dict[str, object]:
    """Check admitted claim scope/coverage only; no source IO, dispatch or release audit."""
    profile = StandardProfile.model_validate_json(profile.canonical_json())
    if pin(profile) != PROFILE or sha256(acceptance_raw) != expected_acceptance_sha256:
        raise ValueError("Olist profile or separately trusted acceptance pin differs")
    acceptance = MethodDesignAcceptance.model_validate_json(acceptance_raw)
    if now.tzinfo is None or acceptance.recorded_at > now:
        raise ValueError("method audit requires an aware clock after design acceptance")
    cases = tuple(MethodCase.model_validate_json(c.canonical_json()) for c in cases)
    claims = tuple(MethodClaim.model_validate_json(c.canonical_json()) for c in claims)
    scopes = tuple(MethodScope.model_validate_json(s.canonical_json()) for s in scopes)
    by_case = {c.case_id: c for c in cases}
    by_scope = {pin(s): s for s in scopes}
    if not cases or len(by_case) != len(cases) or len(by_scope) != len(scopes):
        raise ValueError("explicit unique cases and scopes required")
    expected = {
        (c.case_id, f, p)
        for c in cases
        for f in profile.required_fields
        if f != "recovery" or "crash_restart" in c.slices
        for p in CLAIMS[f]
    }
    records: dict[tuple[str, str, str], MethodClaim] = {}
    for row in claims:
        row_key = row.case_id, row.field, row.part
        if row_key not in expected or row_key in records:
            raise ValueError(
                "duplicate or unscheduled claim; evidence cannot vote away a contradiction"
            )
        records[row_key] = row
    blockers: set[str] = set()
    required_slices = set(profile.required_holdout_slices)
    present_slices = {s for c in cases if c.split == "holdout" for s in c.slices}
    for missing in required_slices - present_slices:
        blockers.add("holdout_slice_missing:" + missing)
    parents: dict[str, str] = {}

    def find(value: str) -> str:
        parents.setdefault(value, value)
        while parents[value] != value:
            parents[value] = parents[parents[value]]
            value = parents[value]
        return value

    for case in cases:
        first = "case:" + case.case_id
        for value in ("input:" + case.input_sha256, *("source:" + k for k in case.source_keys)):
            parents[find(value)] = find(first)
        if case.split != "holdout":
            blockers.add("case_not_qualification_holdout:" + case.case_id)
    groups: dict[str, set[str]] = {}
    for case in cases:
        groups.setdefault(find("case:" + case.case_id), set()).add(case.split)
    if any(len(s) > 1 for s in groups.values()):
        blockers.add("connected_source_or_input_crosses_splits")
    admitted = 0
    for key in sorted(expected):
        marker = ":".join(key)
        claim = records.get(key)
        if claim is None:
            blockers.add("claim_missing:" + marker)
            continue
        row = claim
        case = by_case[row.case_id]
        scope = by_scope.get(row.scope_sha256)
        failures = []
        if pin(row) not in verified_claim_pins:
            failures.append("domain_claim_not_independently_admitted")
        if row.observed_at > now:
            failures.append("future_observation")
        if row.disposition != "supported":
            failures.append("claim_" + row.disposition)
        if scope is None or row.scope_sha256 not in trusted_scope_pins:
            failures.append("scope_not_separately_accepted")
        else:
            if scope.permitted_use != "qualification":
                failures.append("scope_is_development_only")
            if not scope.granted_at <= now < scope.expires_at:
                failures.append("scope_not_current")
            if not scope.granted_at <= row.observed_at < scope.expires_at:
                failures.append("observation_outside_scope_interval")
            if (scope.field, scope.part) != (row.field, row.part):
                failures.append("scope_claim_differs")
            if not set(case.slices).issubset(scope.slices):
                failures.append("scope_slice_differs")
            for name in ("input_sha256", "reference_sha256"):
                if getattr(row, name) != getattr(case, name):
                    failures.append("case_binding_differs")
            for name in ("input_sha256", "reference_sha256", "source_sha256", "evaluator_sha256"):
                if getattr(row, name) != getattr(scope, name):
                    failures.append("scope_binding_differs")
            if scope.method == "qualified_model":
                bound = scope.qualification_report_sha256
                material = qualifications.get(bound or "")
                if material is None:
                    failures.append("qualification_material_missing")
                else:
                    report = qualification_report(
                        material.dataset, material.protocol, material.study, now=now
                    )
                    if (
                        qualification_pin(report) != bound
                        or report["criteria_met"] is not True
                        or material.dataset.agent != "olist"
                        or material.dataset.field != row.field + "." + row.part
                        or material.protocol.evaluator_sha256 != row.evaluator_sha256
                        or material.study.finished_at > scope.granted_at
                        or not set(case.slices).issubset(material.protocol.required_slices)
                    ):
                        failures.append("qualification_report_failed_or_scope_differs")
        for failure in failures:
            blockers.add(failure + ":" + marker)
        admitted += not failures
    return {
        "version": "olist-evidence-method-coverage-audit-v2",
        "profile_sha256": pin(profile),
        "accepted_design_sha256": expected_acceptance_sha256,
        "cases": len(cases),
        "declared_connected_groups_not_authenticated": len(groups),
        "required_claims": len(expected),
        "supplied_claims": len(claims),
        "admitted_supported_claims": admitted,
        "blockers": sorted(blockers),
        "method_coverage_met": not blockers,
        "factual_source_io_performed": False,
        "domain_readers_and_external_trust_required": True,
        "remaining_release_gates": [
            "frozen_statistical_protocol",
            "reference_sampling_and_independence",
            "fresh_candidate_and_baseline_results",
            "performance_accounting_and_host_recovery",
            "release_authorization",
        ],
        "qualification_allowed": False,
        "human_review_supplied": False,
        "provider_calls_authorized": 0,
        "release_allowed": False,
    }
