"""Explicit intake states and exact policy applicability. Bindings are trusted import assertions."""

from datetime import date
from typing import Annotated, Literal, Self

from agent_harness.contracts import WireContract
from prior_auth.contracts import Digest, Id, Policy, digest
from pydantic import Field, model_validator

DocumentKind = Literal[
    "sleep_report",
    "physician_order",
    "clinical_note",
    "education_record",
    "insurance_form",
    "other",
]
IntakeOutcome = Literal[
    "accepted",
    "unrelated_request",
    "unrelated_document",
    "binding_review",
    "wrong_subject",
    "unsupported_policy",
    "ambiguous_policy",
    "unreadable",
    "relevance_review",
    "unsafe_document",
    "redaction_review",
]


class CaseBinding(WireContract):
    tenant_id: Id
    case_id: Id
    subject_key: Digest
    provider_id: Id
    payer_id: Id
    plan_id: Id
    service: Id
    service_date: date
    purpose: Literal["initial_evidence", "other"]


class DocumentBinding(WireContract):
    document_id: Id
    tenant_id: Id
    case_id: Id
    subject_key: Digest | None
    provider_id: Id
    kind: DocumentKind
    service: Id
    binding_review_ref: Id | None
    relevance: Literal["relevant", "unrelated", "uncertain"]
    relevance_review_ref: Id | None
    redaction_review_ref: Id | None
    # These assertions are supplied by trusted import, not inferred from the document/model.


class PolicyEntry(WireContract):
    payer_id: Id
    plan_id: Id
    service: Id
    effective_from: date
    effective_until: date | None = None
    policy_sha256: Digest
    configuration_ref: Id
    use: Literal["development", "qualified"] = "development"

    @model_validator(mode="after")
    def interval(self) -> Self:
        if self.effective_until is not None and self.effective_until <= self.effective_from:
            raise ValueError("policy interval invalid")
        return self


class Registry(WireContract):
    version: Literal["prior-auth-registry-v2"] = "prior-auth-registry-v2"
    entries: Annotated[tuple[PolicyEntry, ...], Field(min_length=1, max_length=100)]

    def select(self, case: CaseBinding) -> tuple[PolicyEntry | None, IntakeOutcome]:
        matches = [
            e
            for e in self.entries
            if (e.payer_id, e.plan_id, e.service) == (case.payer_id, case.plan_id, case.service)
            and e.effective_from <= case.service_date
            and (e.effective_until is None or case.service_date < e.effective_until)
        ]
        if len(matches) != 1:
            return None, "ambiguous_policy" if matches else "unsupported_policy"
        return matches[0], "accepted"


class IntakeDecision(WireContract):
    outcome: IntakeOutcome
    policy_sha256: Digest | None = None
    admitted: bool
    reason: Literal[
        "supported",
        "request_scope",
        "document_scope",
        "subject_unverified",
        "subject_mismatch",
        "policy_scope",
        "policy_ambiguous",
        "empty_text",
        "relevance_unverified",
        "content_refused",
        "redaction_unverified",
    ]

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if self.admitted != (self.outcome == "accepted"):
            raise ValueError("intake admission/outcome differ")
        if self.admitted and (self.policy_sha256 is None or self.reason != "supported"):
            raise ValueError("accepted intake requires exact policy")
        return self


def decide(
    case: CaseBinding,
    document: DocumentBinding,
    registry: Registry,
    policy: Policy,
    *,
    readable: bool,
    safe: bool = True,
) -> IntakeDecision:
    case = CaseBinding.model_validate_json(case.canonical_json())
    document = DocumentBinding.model_validate_json(document.canonical_json())
    registry = Registry.model_validate_json(registry.canonical_json())
    if (case.tenant_id, case.case_id) != (document.tenant_id, document.case_id):
        raise PermissionError("document/case scope mismatch")
    if case.purpose != "initial_evidence" or case.service != "initial-cpap":
        return IntakeDecision(outcome="unrelated_request", admitted=False, reason="request_scope")
    if not document.binding_review_ref or document.subject_key is None:
        return IntakeDecision(outcome="binding_review", admitted=False, reason="subject_unverified")
    if document.subject_key != case.subject_key:
        return IntakeDecision(outcome="wrong_subject", admitted=False, reason="subject_mismatch")
    if not safe:
        return IntakeDecision(outcome="unsafe_document", admitted=False, reason="content_refused")
    if (
        document.service != case.service
        or document.kind == "other"
        or document.relevance == "unrelated"
    ):
        return IntakeDecision(outcome="unrelated_document", admitted=False, reason="document_scope")
    if document.relevance != "relevant" or not document.relevance_review_ref:
        return IntakeDecision(
            outcome="relevance_review", admitted=False, reason="relevance_unverified"
        )
    entry, status = registry.select(case)
    if entry is None:
        return IntakeDecision(
            outcome=status,
            admitted=False,
            reason="policy_ambiguous" if status == "ambiguous_policy" else "policy_scope",
        )
    if (
        entry.policy_sha256 != digest(policy.canonical_json())
        or not policy.effective_from <= case.service_date
        or (policy.effective_until is not None and case.service_date >= policy.effective_until)
    ):
        return IntakeDecision(outcome="unsupported_policy", admitted=False, reason="policy_scope")
    if not document.redaction_review_ref:
        return IntakeDecision(
            outcome="redaction_review", admitted=False, reason="redaction_unverified"
        )
    if not readable:
        return IntakeDecision(outcome="unreadable", admitted=False, reason="empty_text")
    return IntakeDecision(
        outcome="accepted", admitted=True, reason="supported", policy_sha256=entry.policy_sha256
    )
