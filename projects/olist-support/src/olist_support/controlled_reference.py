"""Proposed constructed field references; no native-label edits, model calls or release gate."""

from typing import Annotated, Literal, Self

from agent_harness.contracts import AgentInput, Contract
from agent_harness.release_contracts import Sha256, pin, sha256
from pydantic import Field, model_validator

from olist_support.controlled_reference_check import inspect
from olist_support.routing_contracts import RoutingPlan

Minor = Annotated[int, Field(ge=0, le=2**63 - 1)]
Template = Literal[
    "refund_suffix",
    "refund_prefix",
    "refund_paid_contrast",
    "refund_full",
    "reship",
    "reship_paid",
    "clarify_alternatives",
    "clarify_help",
    "status_paid",
    "refund_status",
]


class ControlledSpec(Contract):
    template: Template
    requested_minor: Minor | None = None
    paid_minor: Minor | None = None

    @model_validator(mode="after")
    def slots(self) -> Self:
        requested = self.template in ("refund_suffix", "refund_prefix", "refund_paid_contrast")
        paid = self.template in ("refund_paid_contrast", "reship_paid", "status_paid")
        if requested != (self.requested_minor is not None) or paid != (self.paid_minor is not None):
            raise ValueError("controlled template requires exact slot roles")
        return self


class MoneyWitness(Contract):
    role: Literal["requested_refund", "payment_mention"]
    start: Annotated[int, Field(ge=0)]
    end: Annotated[int, Field(gt=0)]
    minor: Minor


def _render(spec: ControlledSpec) -> tuple[str, RoutingPlan, tuple[MoneyWitness, ...]]:
    """Construct with integer arithmetic; the checker independently recognizes whole text."""
    parts: list[str] = []
    witnesses: list[MoneyWitness] = []

    def amount(
        value: int, role: Literal["requested_refund", "payment_mention"], prefix: bool
    ) -> None:
        major, fraction = divmod(value, 100)
        literal = f"SIM {major}.{fraction:02d}" if prefix else f"{major}.{fraction:02d} SIM"
        start = sum(map(len, parts))
        parts.append(literal)
        witnesses.append(
            MoneyWitness(role=role, start=start, end=start + len(literal), minor=value)
        )

    if spec.paid_minor is not None:
        parts.append("I paid ")
        amount(spec.paid_minor, "payment_mention", False)
        parts.append(". ")
    template = spec.template
    if spec.requested_minor is not None:
        parts.append("Please refund exactly ")
        amount(spec.requested_minor, "requested_refund", template == "refund_prefix")
        parts.append(".")
    elif template == "refund_full":
        parts.append("Please refund my full payment.")
    elif template in ("reship", "reship_paid"):
        parts.append("Please reship this order. Do not refund it.")
    elif template == "clarify_alternatives":
        parts.append("I have not chosen between a refund and a reshipment. What are my options?")
    elif template == "clarify_help":
        parts.append("I need help with this order. I have not chosen an action.")
    elif template == "status_paid":
        parts.append("What is this order's shipping status?")
    else:
        parts.append("What is the status of my existing refund?")
    intent: Literal["refund", "reship", "clarify", "status", "unsupported"]
    if template.startswith("refund_") and template != "refund_status":
        intent = "refund"
    elif template.startswith("reship"):
        intent = "reship"
    elif template.startswith("clarify"):
        intent = "clarify"
    elif template == "status_paid":
        intent = "status"
    else:
        intent = "unsupported"
    return (
        "".join(parts),
        RoutingPlan(
            routing_version="olist-intent-routing-v2",
            intent=intent,
            requested_minor=spec.requested_minor,
        ),
        tuple(witnesses),
    )


class ControlledReference(Contract):
    version: Literal["olist-controlled-field-reference-proposal-v1"] = (
        "olist-controlled-field-reference-proposal-v1"
    )
    spec: ControlledSpec
    spec_sha256: Sha256
    case_id: Sha256
    group_id: Sha256
    input: AgentInput
    expected: RoutingPlan
    money: tuple[MoneyWitness, ...]
    provenance: Literal["authored_closed_grammar_proposal"] = "authored_closed_grammar_proposal"
    partition: Literal["development"] = "development"
    method_accepted: Literal[False] = False
    semantic_gold_validated: Literal[False] = False
    independent_family_validated: Literal[False] = False
    frozen_for_provider: Literal[False] = False
    release_allowed: Literal[False] = False

    @model_validator(mode="after")
    def reconstruct(self) -> Self:
        text, expected, money = _render(self.spec)
        if (
            self.spec_sha256 != pin(self.spec)
            or self.case_id != sha256(("olist-controlled-case-v1|" + pin(self.spec)).encode())
            or self.group_id != sha256(("olist-controlled-parent-v1|" + expected.intent).encode())
            or self.input != AgentInput(request=text)
            or self.expected != expected
            or self.money != money
        ):
            raise ValueError("constructed reference differs from its specification")
        checked = inspect(text)
        if checked.expected != expected or [s.model_dump() for s in checked.money] != [
            s.model_dump() for s in money
        ]:
            raise ValueError("independent constructed grammar/role/arithmetic check differs")
        return self


def construct(spec: ControlledSpec) -> ControlledReference:
    spec = ControlledSpec.model_validate_json(spec.canonical_json())
    text, expected, money = _render(spec)
    return ControlledReference(
        spec=spec,
        spec_sha256=pin(spec),
        case_id=sha256(("olist-controlled-case-v1|" + pin(spec)).encode()),
        group_id=sha256(("olist-controlled-parent-v1|" + expected.intent).encode()),
        input=AgentInput(request=text),
        expected=expected,
        money=money,
    )


def draft() -> tuple[ControlledReference, ...]:
    """Twelve authored examples for method review, never a fresh qualification cohort."""
    specs = [
        ControlledSpec(template="refund_suffix", requested_minor=value)
        for value in (0, 10_000, 10_001)
    ] + [
        ControlledSpec(template="refund_prefix", requested_minor=9_999),
        ControlledSpec(template="refund_paid_contrast", requested_minor=2_500, paid_minor=10_000),
        ControlledSpec(template="refund_full"),
        ControlledSpec(template="reship"),
        ControlledSpec(template="reship_paid", paid_minor=9_999),
        ControlledSpec(template="clarify_alternatives"),
        ControlledSpec(template="clarify_help"),
        ControlledSpec(template="status_paid", paid_minor=10_000),
        ControlledSpec(template="refund_status"),
    ]
    return tuple(construct(spec) for spec in specs)
