"""Independent recognizer for a proposed, closed constructed-language reference grammar.

Does not import the generator or parse arbitrary customer language. Agreement is an
implementation cross-check, not independent semantic validation or transaction authority.
"""

import re
from decimal import Decimal
from typing import Literal

from agent_harness.contracts import Contract

from olist_support.routing_contracts import RoutingPlan


class CheckedMoney(Contract):
    role: Literal["requested_refund", "payment_mention"]
    start: int
    end: int
    minor: int


class CheckedMessage(Contract):
    expected: RoutingPlan
    money: tuple[CheckedMoney, ...]


def inspect(text: str) -> CheckedMessage:
    """Full match only; named captures establish roles within the proposed grammar."""
    number = r"(?:0|[1-9][0-9]{0,16})\.[0-9]{2}"
    requested = rf"(?P<requested>{number} SIM)"
    paid = rf"(?P<paid>{number} SIM)"
    patterns: tuple[
        tuple[str, Literal["refund", "reship", "clarify", "status", "unsupported"]], ...
    ] = (
        (rf"Please refund exactly {requested}\.", "refund"),
        (rf"Please refund exactly (?P<requested>SIM {number})\.", "refund"),
        (rf"I paid {paid}\. Please refund exactly {requested}\.", "refund"),
        (r"Please refund my full payment\.", "refund"),
        (r"Please reship this order\. Do not refund it\.", "reship"),
        (rf"I paid {paid}\. Please reship this order\. Do not refund it\.", "reship"),
        (r"I have not chosen between a refund and a reshipment\. What are my options\?", "clarify"),
        (r"I need help with this order\. I have not chosen an action\.", "clarify"),
        (rf"I paid {paid}\. What is this order's shipping status\?", "status"),
        (r"What is the status of my existing refund\?", "unsupported"),
    )
    for pattern, intent in patterns:
        match = re.fullmatch(pattern, text, flags=re.ASCII)
        if match is None:
            continue
        money = []
        requested_minor = None
        roles: tuple[tuple[str, Literal["requested_refund", "payment_mention"]], ...] = (
            ("paid", "payment_mention"),
            ("requested", "requested_refund"),
        )
        for name, role in roles:
            if name not in match.groupdict():
                continue
            literal = match.group(name)
            value = literal.removeprefix("SIM ").removesuffix(" SIM")
            minor = int(Decimal(value) * Decimal(100))
            if not 0 <= minor <= 2**63 - 1:
                raise ValueError("controlled amount outside supported integer range")
            if name == "requested":
                requested_minor = minor
            money.append(
                CheckedMoney(role=role, start=match.start(name), end=match.end(name), minor=minor)
            )
        return CheckedMessage(
            expected=RoutingPlan(
                routing_version="olist-intent-routing-v2",
                intent=intent,
                requested_minor=requested_minor,
            ),
            money=tuple(sorted(money, key=lambda span: span.start)),
        )
    raise ValueError("text is outside the proposed controlled reference grammar")
