"""Compare correct-term and extracted-term SIM arithmetic without changing any invoice."""

import json
from datetime import date
from typing import Literal

from agent_harness.contracts import Contract
from revenue_integrity.billing_contracts import BillingInput, SubscriptionTerms
from revenue_integrity.reconcile import Reconciliation, reconcile

from revenue_assessment import Meaning
from revenue_profiling import Recorder


class BillingComparison(Contract):
    correct_terms: Reconciliation
    extracted_terms: Reconciliation | None
    extraction_comparable: bool
    extracted_path_reason: str
    billing_write_authorized: Literal[False] = False


def compare_constructed(
    value: BillingInput,
    meaning: Meaning,
    documents: dict[str, str],
    recorder: Recorder,
) -> BillingComparison:
    """Diagnostic only: correct terms come from a separate authored/programmatic reference.

    Only a deliberately narrow complete SIM monthly vocabulary is projectable. Never
    discard unrepresented amendments, credits, uplift, conditions or exceptions.
    """
    value = BillingInput.model_validate_json(value.canonical_json())
    meaning = Meaning.model_validate_json(meaning.canonical_json())
    correct = recorder.call("reconciliation", reconcile, value)
    meaning.verify(documents)
    terms = {term.field: term for term in meaning.terms}
    if any(term.state != "supported" for term in terms.values()):
        reason = "unresolved_terms"
    elif value.amendments or value.credits or value.terms.annual_uplift_bps is not None:
        reason = "unrepresented_adjustment_or_uplift"
    elif terms["currency"].value != "SIM" or terms["billing_period"].value != "monthly":
        reason = "unsupported_unit_or_period"
    elif terms["conditions"].value != "active subscription" or terms["exceptions"].value != "none":
        reason = "unrepresented_condition_or_exception"
    else:
        data = value.model_dump(mode="json")
        data["terms"] = SubscriptionTerms.model_validate_json(
            json.dumps(
                {
                    "start": terms["effective_from"].value,
                    "end": terms["effective_until"].value,
                    "seats": terms["quantity"].value,
                    "unit_price_minor": terms["unit_price_minor"].value,
                }
            )
        ).model_dump(mode="json")
        extracted = BillingInput.model_validate_json(json.dumps(data))
        if date.fromisoformat(str(terms["effective_from"].value)) > value.period_start:
            reason = "extracted_effective_period_differs"
        else:
            return BillingComparison(
                correct_terms=correct,
                extracted_terms=recorder.call("reconciliation", reconcile, extracted),
                extraction_comparable=True,
                extracted_path_reason="constructed_SIM_only",
            )
    return BillingComparison(
        correct_terms=correct,
        extracted_terms=None,
        extraction_comparable=False,
        extracted_path_reason=reason,
    )
