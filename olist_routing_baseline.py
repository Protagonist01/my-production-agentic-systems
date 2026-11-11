"""Versioned conservative language comparator; never grants action authority."""

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from agent_harness.baseline_recording import zero_usage
from agent_harness.contracts import RunContext
from olist_support.routing_contracts import RoutingPlan
from olist_support.workflow import IntentDecision, WorkflowRequest

VERSION = "olist-conservative-rules-v1"
Route = Literal["refund", "reship", "status", "clarify", "unsupported", "review"]

# Closed, inspectable feature rules; exposed development, not a general language parser.
UNRELATED = re.compile(r"\b(poem|poetry|web scraper|python code|subscription|weather|recipe)\b")
PRIVATE = re.compile(
    r"\b(passwords?|session tokens?|api keys?)\b|"
    r"\b(?:other|another) customer(?:'s)?\b|\ball .*?accounts\b"
)
PRESSURE = re.compile(
    r"\b(ignore|bypass|override|administrator|system prompt|without .*?confirmation|"
    r"skip .*?confirmation|twice|repeat|receipt already exists)\b"
)
QUOTED = re.compile(r'"|[“”]|\b(quoted|quote|untrusted note)\b')
REFUND = re.compile(r"\b(refund|reimburse|money back)\b|\breturn\s+\d")
REPLACE = re.compile(r"\b(replacement|replace|reship|resend)\b")
STATUS = re.compile(
    r"\bwhere (?:is|are) (?:my|the|our) (?:order|package|shipment)\b|"
    r"\b(?:order|delivery|shipping|shipment|package) status\b|"
    r"\b(?:track|tracking)\b.*?\b(?:order|package|shipment)\b"
)
NEGATED_REFUND = re.compile(r"^(?:do not|don't|never) refund(?: me)?[.!?]?$", re.I)
NEGATION = re.compile(r"\b(no|not|never|don't|didn't|isn't|wasn't|cannot|can't)\b")
AMOUNT = re.compile(
    r"\b(?:refund|reimburse|return)\s+(?:me\s+)?"
    r"(?P<amount>[0-9]+\.[0-9]{2})\s+sim\b",
    re.I,
)


@dataclass(frozen=True)
class Interpretation:
    plan: RoutingPlan
    reason: str


def interpret(text: str) -> Interpretation:
    """Decide from input only; no reference, source label, order facts or tool access."""
    if not text.strip() or len(text) > 8192:
        raise ValueError("bounded nonempty text required")

    def result(intent: Route, reason: str, amount: int | None = None) -> Interpretation:
        return Interpretation(
            RoutingPlan(
                routing_version="olist-intent-routing-v2", intent=intent, requested_minor=amount
            ),
            reason,
        )

    normalized = " ".join(text.casefold().split())
    if PRIVATE.search(normalized):
        return result("unsupported", "private_or_cross_account_request")
    if QUOTED.search(normalized):
        return result("review", "quoted_scope_not_parsed")
    if PRESSURE.search(normalized):
        return result("review", "instruction_or_execution_pressure")
    # Recognize a narrow whole-clause negation, not arbitrary negation scope.
    clauses = re.split(r";\s*|[.!?]\s+", normalized)
    remaining = [c for c in clauses if not NEGATED_REFUND.fullmatch(c)]
    primary = "; ".join(remaining)
    if NEGATION.search(primary):
        return result("clarify", "unrecognized_negation_scope")
    refund, replacement, status = (bool(p.search(primary)) for p in (REFUND, REPLACE, STATUS))
    unrelated = bool(UNRELATED.search(primary))
    if unrelated:
        return result(
            "clarify" if refund or replacement or status or "order" in primary else "unsupported",
            "mixed_scope" if refund or replacement or status or "order" in primary else "unrelated",
        )
    if re.search(
        r"\b(?:status of|existing|already (?:requested|received))\b.*?\brefund\b", primary
    ):
        return result("unsupported", "existing_refund_status_not_supported")
    if sum((refund, replacement, status)) > 1:
        return result("clarify", "multiple_requested_routes")
    if status:
        return result("status", "order_status_feature")
    if replacement:
        return result("reship", "replacement_feature")
    if refund:
        amounts = list(AMOUNT.finditer(primary))
        if len(amounts) > 1:
            return result("clarify", "multiple_requested_amounts")
        if amounts:
            # Reject prefix/suffix captures such as -5.00, 15.000 or 1,000.00.
            match = amounts[0]
            residual = primary[: match.start()] + primary[match.end() :]
            residual = re.sub(
                r"\b(?:i paid|paid|payment was)\s+[0-9]+\.[0-9]{2}\s+sim\b", "", residual
            )
            if re.search(r"[0-9$€£]|\b(?:sim|dollars?|percent|half)\b", residual):
                return result("clarify", "other_amount_or_currency_unresolved")
            start, end = match.span("amount")
            if (start and primary[start - 1] in "+-.,0123456789") or (
                end < len(primary) and primary[end] in ".,0123456789"
            ):
                return result("clarify", "malformed_requested_amount")
            if len(match.group("amount").split(".")[0]) > 17:
                return result("clarify", "requested_amount_out_of_range")
            amount = int(Decimal(match.group("amount")) * 100)
            if amount > 2**63 - 1:
                return result("clarify", "requested_amount_out_of_range")
            return result("refund", "refund_adjacent_sim_amount", amount)
        if re.search(r"[0-9$€£]|\b(?:sim|dollars?|percent|half)\b", primary):
            return result("clarify", "amount_role_or_format_unrecognized")
        return result("refund", "refund_without_numeric_amount")
    return result("clarify", "no_supported_route_feature")


@dataclass(frozen=True)
class ConservativePlanner:
    def plan(self, context: RunContext, request: WorkflowRequest) -> IntentDecision:
        return IntentDecision(
            plan=interpret(request.text).plan,
            usage=zero_usage(context.budget.cost_currency),
            execution_run_id=context.run_id,
        )
