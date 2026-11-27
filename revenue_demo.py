"""Constructed Revenue walkthrough over the unchanged durable SIM operation store."""

import json
from collections.abc import Callable
from datetime import date
from typing import Annotated, Any, Literal, Self

from agent_harness.contracts import Contract
from agent_harness.release_contracts import Sha256, sha256
from pydantic import Field, model_validator
from revenue_integrity.billing_contracts import BillingInput, Invoice, SubscriptionTerms
from revenue_integrity.console_contracts import Principal, Submission
from revenue_integrity.console_service import ConsoleService, Operations, finding
from revenue_integrity.extraction import (
    SyntheticDocument,
    parse_synthetic,
    reconcile_extracted,
    synthetic_document,
)
from revenue_integrity.operation_contracts import BusinessReview, Proposal, RevenueRecord

from revenue_assessment import DocumentBinding, RequestScope, preflight
from revenue_demo_model import Answer, ModelReceipts
from revenue_profiling import Recorder


class DemoCase(Contract):
    case_id: str
    title: str
    invoice_id: str
    billing: BillingInput
    document: SyntheticDocument
    binding: DocumentBinding
    source_kind: Literal["constructed_SIM_walkthrough"] = "constructed_SIM_walkthrough"

    @model_validator(mode="after")
    def bound(self) -> Self:
        if self.document.case_id != self.billing.case_id or self.case_id != self.billing.case_id:
            raise ValueError("case/source identity differs")
        if self.binding.document_sha256 != sha256(self.document.text.encode()):
            raise ValueError("document binding differs")
        if self.billing.amendments or self.billing.credits:
            raise ValueError("walkthrough has no independently sourced adjustment documents")
        return self


def cases() -> tuple[DemoCase, ...]:
    """Fixed public invented inputs; never real customer documents or legal references."""
    descriptions: tuple[tuple[str, str, int, dict[str, Any]], ...] = (
        ("underbilled", "Underbilled subscription", 2500, {}),
        ("overbilled", "Overbilled subscription", 3500, {}),
        ("correct", "Invoice already correct", 3000, {}),
        ("missing", "Missing unit price", 2500, {"unit_price_minor": None}),
        (
            "conflict",
            "Conflicting agreement terms",
            2500,
            {"conflicting_terms": ("Price schedule disputed",)},
        ),
        ("cap", "Adjustment above the SIM cap", 0, {"unit_price_minor": 5000}),
    )
    result = []
    for name, title, issued, changes in descriptions:
        identity = sha256(("revenue-walkthrough-v1:" + name).encode())
        fields: dict[str, Any] = {
            "start": date(2025, 1, 1),
            "end": None,
            "seats": 3,
            "unit_price_minor": 1000,
        }
        fields.update(changes)
        terms = SubscriptionTerms.model_validate(fields)
        billing = BillingInput(
            case_id=identity,
            tenant_id="revenue-demo",
            account_id="demo-account",
            subscription_id="demo-subscription-" + name,
            period_start=date(2025, 1, 1),
            period_end=date(2025, 2, 1),
            terms=terms,
            invoice=Invoice(amount_minor=issued),
        )
        document = synthetic_document(identity, terms)
        result.append(
            DemoCase(
                case_id=identity,
                title=title,
                invoice_id="demo-invoice-" + name,
                billing=billing,
                document=document,
                binding=DocumentBinding(
                    document_sha256=sha256(document.text.encode()),
                    tenant_id=billing.tenant_id,
                    account_id=billing.account_id,
                    product_id=billing.subscription_id,
                    effective_from=terms.start,
                    current_version=True,
                    authority_ref="trusted constructed fixture catalog v1",
                ),
            )
        )
    return tuple(result)


class Analyze(Contract):
    case_id: Annotated[str, Field(min_length=1, max_length=256)]
    document: Annotated[str, Field(min_length=1, max_length=8000)]
    question: Annotated[str, Field(min_length=1, max_length=1024)]


class Propose(Contract):
    analysis: Analyze
    expected_version: Annotated[int, Field(ge=0)]
    analysis_digest: Sha256
    operation_id: Annotated[str, Field(min_length=1, max_length=256, pattern=r"\S")]


class DemoService(ConsoleService):
    """No new write authority: require independently provisioned source facts and consent."""

    def __init__(
        self,
        store: Operations,
        recorder: Recorder,
        *,
        model: tuple[Callable[[str], Answer], ModelReceipts] | None = None,
    ):
        super().__init__(store)
        self.recorder = recorder
        self.model = model
        self.catalog = {c.case_id: c for c in cases()}

    def source(self, principal: Principal, case_id: str) -> DemoCase:
        principal = Principal.model_validate_json(principal.canonical_json())
        case = self.catalog.get(case_id)
        if case is None:
            raise LookupError("case unavailable")
        grant = principal.grant()
        grant.require(case.billing.tenant_id, "invoice", case.invoice_id, "read")
        grant.require(case.billing.tenant_id, "account", case.billing.account_id, "read")
        return case

    def list_cases(self, principal: Principal) -> list[dict[str, Any]]:
        result = []
        for case in self.catalog.values():
            try:
                self.source(principal, case.case_id)
            except PermissionError:
                continue
            result.append(
                {
                    "case_id": case.case_id,
                    "title": case.title,
                    "invoice_id": case.invoice_id,
                    "document": case.document.text,
                    "source_sha256": case.binding.document_sha256,
                    "invoice_minor": case.billing.invoice.amount_minor,
                    "unit": "SIM",
                }
            )
        return result

    def _record(self, principal: Principal, case: DemoCase) -> RevenueRecord:
        records = self.store.records(principal.grant())
        matches = [r for r in records if r.resource_id == case.invoice_id and r.kind == "invoice"]
        if len(matches) != 1:
            raise LookupError("provisioned invoice unavailable")
        record = RevenueRecord.model_validate_json(matches[0].canonical_json())
        if record.billing_input != case.billing or record.account_id != case.billing.account_id:
            raise BusinessReview("source_facts_changed")
        return record

    def analyze(self, principal: Principal, payload: Analyze) -> dict[str, Any]:
        payload = Analyze.model_validate_json(payload.canonical_json())
        case = self.source(principal, payload.case_id)
        record = self._record(principal, case)
        result = self._analyze(principal, payload, case, record)
        if self.model is None or result["action"] not in (
            "proposable",
            "no_change",
            "request_information",
        ):
            return result

        extract, receipts = self.model
        slot = receipts.reserve(principal.actor_id, result["analysis_digest"])
        result["execution_mode"] = "openrouter_nemotron"
        if slot is None:
            return self._model_review(result, "model_allowance_exhausted")

        result["model_calls"] = 1
        try:
            answer = self.recorder.call("gateway", extract, case.document.text)
        except ValueError:
            return self._model_review(result, "model_unavailable")

        expected = {
            citation["field"]: citation
            for citation in result["citations"]
            if citation["field"] in ("unit_price_minor", "seats")
        }
        verified = []
        for item in answer.evidence:
            citation = expected.pop(item.field, None)
            if citation is None or item.quote != citation["quote"]:
                return self._model_review(result, "model_evidence_disagrees")
            if item.value != json.loads(citation["quote"].split("=", 1)[1]):
                return self._model_review(result, "model_evidence_disagrees")
            verified.append(citation)
        if expected:
            return self._model_review(result, "model_evidence_disagrees")

        receipts.accept(slot)
        result["citations"] = verified
        if result["action"] == "proposable":
            result["reason"] = "model_and_stored_facts_agree"
        return result

    @staticmethod
    def _model_review(result: dict[str, Any], reason: str) -> dict[str, Any]:
        return {
            **result,
            "action": "review",
            "reason": reason,
            "citations": [],
            "expected_minor": None,
            "delta_minor": None,
        }

    def _analyze(
        self, principal: Principal, payload: Analyze, case: DemoCase, record: RevenueRecord
    ) -> dict[str, Any]:
        from revenue_integrity.source_contracts import ExtractionInput

        if record.amount_minor is None:
            raise BusinessReview("invoice_amount_missing")

        public = ExtractionInput(
            case_id=case.case_id, context=payload.document, question=payload.question
        )
        request = RequestScope(
            tenant_id=case.billing.tenant_id,
            invoice_id=case.invoice_id,
            account_id=case.billing.account_id,
            product_id=case.billing.subscription_id,
            period_start=case.billing.period_start,
            period_end=case.billing.period_end,
        )
        with self.recorder.phase("request", input_bytes=len(payload.document.encode())):
            blocked = self.recorder.call(
                "relevance", preflight, request, public, case.binding, principal.grant()
            )
            action, reason = "review", "request_outside_constructed_vocabulary"
            citations: list[dict[str, Any]] = []
            comparison = None
            if blocked:
                action, reason = blocked.action, blocked.reason
            elif payload.question == "Write a birthday poem.":
                action, reason = "outside_scope", "request_unrelated"
            elif payload.question == "Check this invoice.":
                try:
                    document = SyntheticDocument(case_id=case.case_id, text=payload.document)
                    parsed = self.recorder.call("extraction", parse_synthetic, document)
                    self.recorder.call("citation_check", parse_synthetic, document)
                    data = case.billing.model_dump()
                    data["invoice"] = Invoice(amount_minor=record.amount_minor).model_dump()
                    current = BillingInput.model_validate(data)
                    comparison = self.recorder.call(
                        "reconciliation", reconcile_extracted, current, document, parsed
                    )
                    citations = [
                        {"field": c.field, "start": c.span.start, "quote": c.span.text}
                        for c in parsed.citations
                    ]
                    if comparison.disposition == "review":
                        reason = comparison.reasons[0]
                        if parsed.terms.unit_price_minor is None or parsed.terms.seats is None:
                            action = "request_information"
                    elif comparison.delta_minor == 0:
                        action, reason = "no_change", "invoice_already_correct"
                    elif abs(comparison.delta_minor or 0) > 10000:
                        reason = "adjustment_above_cap"
                    elif finding(record).should_be_minor != comparison.should_be_minor:
                        reason = "independent_stored_facts_disagree"
                    else:
                        action, reason = "proposable", "constructed_source_and_stored_facts_agree"
                except (ValueError, TypeError):
                    action, reason = "review", "invalid_constructed_document"
            result = {
                "case_id": case.case_id,
                "invoice_id": case.invoice_id,
                "expected_version": record.version,
                "source_sha256": case.binding.document_sha256,
                "action": action,
                "reason": reason,
                "citations": citations,
                "issued_minor": record.amount_minor,
                "expected_minor": comparison.should_be_minor if comparison else None,
                "delta_minor": comparison.delta_minor if comparison else None,
                "unit": "SIM",
                "execution_mode": "constructed_parser_no_provider",
                "model_calls": 0,
                "meaning_qualified": False,
                "release_allowed": False,
            }
            result["analysis_digest"] = sha256(
                json.dumps(result, sort_keys=True, separators=(",", ":")).encode()
            )
            return result

    def propose(self, principal: Principal, payload: Submission) -> Proposal:
        # The inherited API must not bypass source assessment via its ordinary endpoint.
        raise BusinessReview("use_checked_walkthrough_proposal")

    def propose_checked(self, principal: Principal, payload: Propose) -> Proposal:
        payload = Propose.model_validate_json(payload.canonical_json())
        if principal.role != "operator":
            raise PermissionError("operator required")
        case = self.source(principal, payload.analysis.case_id)
        record = self._record(principal, case)
        prior = [
            p
            for p in self.store.proposals(principal.grant())
            if p.command.business_operation_id == payload.operation_id
        ]
        # Revalidate the original analyzed view for an exact operation-key retry after apply.
        if prior:
            p = prior[0]
            if (
                p.proposer_id != principal.actor_id
                or p.command.resource_id != case.invoice_id
                or p.command.kind != "invoice_correct"
                or p.command.expected_version != payload.expected_version
                or p.command.invoice_amount_minor is None
            ):
                raise BusinessReview("operation_key_reused")
            record = record.model_copy(
                update={
                    "version": p.command.expected_version,
                    "amount_minor": p.command.invoice_amount_minor - p.adjustment_minor,
                }
            )
        checked = self._analyze(principal, payload.analysis, case, record)
        if (
            checked["action"] != "proposable"
            or checked["analysis_digest"] != payload.analysis_digest
            or record.version != payload.expected_version
        ):
            raise BusinessReview("assessment_changed_or_requires_review")
        if self.model is not None and not self.model[1].accepted(
            principal.actor_id, checked["analysis_digest"]
        ):
            raise BusinessReview("model_assessment_required")
        return super().propose(
            principal,
            Submission(
                operation_id=payload.operation_id,
                kind="invoice_correct",
                resource_id=case.invoice_id,
                expected_version=payload.expected_version,
            ),
        )


def provisioned_records() -> tuple[RevenueRecord, ...]:
    catalog = cases()
    account = RevenueRecord(tenant_id="revenue-demo", resource_id="demo-account", kind="account")
    return (
        account,
        *(
            RevenueRecord(
                tenant_id=c.billing.tenant_id,
                resource_id=c.invoice_id,
                kind="invoice",
                account_id=c.billing.account_id,
                amount_minor=c.billing.invoice.amount_minor,
                billing_input=c.billing,
            )
            for c in catalog
        ),
    )


def principal(role: Literal["operator", "reviewer"]) -> Principal:
    return Principal(
        username="demo-" + role,
        tenant_id="revenue-demo",
        actor_id="demo-" + role,
        role=role,
        invoice_ids=tuple(c.invoice_id for c in cases()),
        account_ids=("demo-account",),
    )
