"""Separate extraction/billing/effect obligations; N/A is never a fabricated pass."""

import json
from typing import Literal, Self, cast

from agent_harness.contracts import Contract, RunContext
from agent_harness.release_contracts import Sha256, pin, sha256
from pydantic import model_validator

from revenue_integrity.billing_contracts import BillingCase
from revenue_integrity.operation_contracts import Receipt
from revenue_integrity.release_evaluation import (
    BillingObservation,
    ExtractionCase,
    ExtractionObservation,
)
from revenue_integrity.state_evidence import (
    InvoiceEvidence,
    InvoiceExpectation,
    OperationState,
    assess_invoice,
)


class TrialBinding(Contract):
    candidate_sha256: Sha256
    context: RunContext


class DenialObservation(Contract):
    kind: Literal["wrong_tenant", "missing_capability", "self_review"]
    rejected: bool
    before: OperationState
    after: OperationState


class EffectTrial(Contract):
    binding: TrialBinding
    invoice: InvoiceEvidence
    expected: InvoiceExpectation
    denials: tuple[DenialObservation, ...]
    compensation_before: OperationState | None = None
    compensation_after: OperationState | None = None
    compensation_result: Receipt | None = None
    compensation_duplicate: Receipt | None = None


class ApplicableCheck(Contract):
    name: str
    applicable: bool
    passed: bool | None
    evidence_ref: str | None = None
    reason: str | None = None

    @model_validator(mode="after")
    def applicability(self) -> Self:
        if not self.applicable and (self.passed is not None or not self.reason):
            raise ValueError("not-applicable checks need an explanation and no pass credit")
        if self.passed is not None and not self.evidence_ref:
            raise ValueError("observed check needs a bound evidence reference")
        return self


def check_summary(checks: tuple[ApplicableCheck, ...]) -> dict[str, object]:
    if not checks or not any(c.applicable for c in checks):
        raise ValueError("study needs declared applicable obligations")
    if len({c.name for c in checks}) != len(checks):
        raise ValueError("duplicate scoped check")
    return dict(
        applicable=sum(c.applicable for c in checks),
        passed=sum(c.applicable and c.passed is True for c in checks),
        failed=sum(c.applicable and c.passed is False for c in checks),
        unobserved=sum(c.applicable and c.passed is None for c in checks),
        not_applicable=sum(not c.applicable for c in checks),
        complete=all(not c.applicable or c.passed is not None for c in checks),
        release_allowed=False,
    )


def assess_effects(value: EffectTrial, binding: TrialBinding) -> dict[str, object]:
    value = EffectTrial.model_validate_json(value.canonical_json())
    binding = TrialBinding.model_validate_json(binding.canonical_json())
    if (
        value.binding != binding
        or binding.context.agent_id != "revenue"
        or value.expected.run_id != binding.context.run_id
        or value.expected.command.tenant_id != binding.context.tenant_id
        or value.expected.command.resource_id != binding.context.case_id
    ):
        raise ValueError("Revenue effects differ from candidate/case/trial scope")
    invoice = assess_invoice(value.invoice, value.expected)
    denial_ok = (
        len(value.denials) == 3
        and {d.kind for d in value.denials} == {"wrong_tenant", "missing_capability", "self_review"}
        and all(d.rejected and d.before == d.after == value.invoice.before for d in value.denials)
    )
    original = value.invoice.result
    undo = value.compensation_result
    before, after = value.compensation_before, value.compensation_after
    compensated = False
    if undo is not None and before is not None and after is not None:
        expected_record = original.before.model_copy(update={"version": original.after.version + 1})
        proposal = next((p for p in before.proposals if p.command == undo.command), None)
        new_proposals = tuple(p for p in before.proposals if p not in value.invoice.after.proposals)
        compensated = (
            before.records == value.invoice.after.records
            and before.ledger == value.invoice.after.ledger
            and len(new_proposals) == 1
            and before.proposals
            == tuple(
                sorted(
                    (*value.invoice.after.proposals, *new_proposals),
                    key=lambda p: (p.command.tenant_id, p.command.business_operation_id),
                )
            )
            and proposal == new_proposals[0]
            and proposal.status == "approved"
            and proposal.reviewer_id not in (None, proposal.proposer_id, undo.actor_id)
            and undo.reviewer_id == proposal.reviewer_id
            and undo.actor_id == value.expected.operator.actor_id
            and undo.original_run_id == binding.context.run_id + "-compensate"
            and undo.ledger_id
            == sha256(
                json.dumps([undo.command.tenant_id, undo.command.business_operation_id]).encode()
            )
            and proposal.created_at <= undo.committed_at < proposal.expires_at
            and undo.command.kind == "compensate"
            and undo.command.tenant_id == original.command.tenant_id
            and undo.command.resource_id == original.command.resource_id
            and undo.command.original_operation_id == original.command.business_operation_id
            and undo.command.expected_version == original.after.version
            and undo.before == original.after
            and undo.after == expected_record
            and undo.target is None
            and undo == value.compensation_duplicate
            and after.proposals == before.proposals
            and after.records
            == tuple(expected_record if r == original.after else r for r in before.records)
            and after.ledger
            == tuple(
                sorted(
                    (*before.ledger, undo),
                    key=lambda r: (r.command.tenant_id, r.command.business_operation_id),
                )
            )
        )
    ref = "revenue-effect-trial:" + pin(value)
    checks = (
        ApplicableCheck(name="authorization", applicable=True, passed=denial_ok, evidence_ref=ref),
        ApplicableCheck(
            name="exact_state", applicable=True, passed=invoice["passed"] is True, evidence_ref=ref
        ),
        ApplicableCheck(
            name="recovery",
            applicable=True,
            passed=invoice["passed"] is True,
            evidence_ref=ref,
            reason="Store reconstruction/redelivery, not hard process death",
        ),
        ApplicableCheck(
            name="compensation",
            applicable=True,
            passed=compensated if undo else None,
            evidence_ref=ref if undo else None,
        ),
    )
    return dict(
        binding_sha256=pin(binding),
        evidence_sha256=pin(value),
        checks=[c.model_dump(mode="json") for c in checks],
        **check_summary(checks),
    )


def scoped_fields(
    scope: Literal["original-extraction", "sim-billing", "sim-effects"],
    observed: dict[str, bool | None],
    *,
    evidence_ref: str,
) -> tuple[ApplicableCheck, ...]:
    required = {
        "original-extraction": {
            "span_precision_check",
            "span_recall_check",
            "supported_terms",
            "abstention",
        },
        "sim-billing": {
            "reconciliation_amount",
            "reconciliation_reason",
            "supported_terms",
            "abstention",
        },
        "sim-effects": {"authorization", "exact_state", "recovery", "compensation"},
    }
    all_fields = set().union(*required.values())
    if set(observed) - required[scope]:
        raise ValueError("unrelated domain fields supplied to scoped study")
    return tuple(
        ApplicableCheck(
            name=name,
            applicable=name in required[scope],
            passed=observed.get(name) if name in required[scope] else None,
            evidence_ref=evidence_ref if observed.get(name) is not None else None,
            reason=None
            if name in required[scope]
            else "Outside the " + scope + " study; no pass credit",
        )
        for name in sorted(all_fields)
    )


def extraction_checks(
    reference: "ExtractionCase", observation: "ExtractionObservation", binding: TrialBinding
) -> tuple[ApplicableCheck, ...]:
    """Literal span obligations only; semantic support awaits qualified review."""
    from revenue_integrity.release_evaluation import ExtractionPlan, extraction_report

    context = binding.context
    if (
        context.agent_id != "revenue"
        or context.case_id != reference.input.case_id
        or observation.case_id != context.case_id
        or observation.trial_id != context.trial_id
    ):
        raise ValueError("Revenue extraction differs from candidate/case/trial scope")
    plan = ExtractionPlan(
        source_manifest_sha256=context.versions.data_snapshot,
        cases=(reference,),
        trial_ids=(context.trial_id,),
    )
    counts = cast(dict[str, int], extraction_report(plan, (observation,))["all"])
    ref = "revenue-original-trial:" + sha256(
        (binding.canonical_json() + plan.canonical_json() + observation.canonical_json()).encode()
    )
    values = list(
        scoped_fields(
            "original-extraction",
            {
                "span_precision_check": counts["invalid"] == 0
                and counts["submitted_spans"] == counts["matched_spans"],
                "span_recall_check": counts["reference_spans"] == counts["matched_spans"],
                "abstention": counts["correct"] == 1,
                "supported_terms": None,
            },
            evidence_ref=ref,
        )
    )
    for i, check in enumerate(values):
        denominator = {
            "span_precision_check": "submitted_spans",
            "span_recall_check": "reference_spans",
        }.get(check.name)
        if denominator and counts[denominator] == 0:
            values[i] = ApplicableCheck(
                name=check.name,
                applicable=False,
                passed=None,
                reason="Undefined zero span denominator: " + denominator,
            )
    values.append(
        ApplicableCheck(
            name="execution_health",
            applicable=True,
            passed=counts["unresolved"] == 0,
            evidence_ref=ref,
        )
    )
    return tuple(values)


def billing_checks(
    reference: "BillingCase", observation: "BillingObservation", binding: TrialBinding
) -> tuple[ApplicableCheck, ...]:
    from revenue_integrity.release_evaluation import BillingPlan, billing_report

    context = binding.context
    if (
        context.agent_id != "revenue"
        or context.case_id != reference.input.case_id
        or context.tenant_id != reference.input.tenant_id
        or observation.case_id != context.case_id
        or observation.trial_id != context.trial_id
    ):
        raise ValueError("Revenue billing differs from candidate/case/trial scope")
    plan = BillingPlan(
        source_manifest_sha256=context.versions.data_snapshot,
        cases=(reference,),
        trial_ids=(context.trial_id,),
    )
    report = billing_report(plan, (observation,))
    counts = cast(dict[str, int], report["all"])
    ref = "revenue-billing-trial:" + sha256(
        (binding.canonical_json() + plan.canonical_json() + observation.canonical_json()).encode()
    )
    observed = observation.result
    healthy = observed is not None and observation.failure_code is None and counts["invalid"] == 0
    return (
        *scoped_fields(
            "sim-billing",
            {
                "reconciliation_amount": healthy
                and observed is not None
                and observed.should_be_minor == reference.expected.should_be_minor,
                "reconciliation_reason": healthy
                and observed is not None
                and observed.reasons == (reference.expected.reason,),
                "supported_terms": None,
                "abstention": healthy
                and observed is not None
                and (observed.disposition == "review")
                == (reference.expected.disposition == "review"),
            },
            evidence_ref=ref,
        ),
        ApplicableCheck(name="execution_health", applicable=True, passed=healthy, evidence_ref=ref),
    )
