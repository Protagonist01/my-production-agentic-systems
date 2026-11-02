"""Customer confirmation contracts reject model-style authority and wrong transaction data."""

from datetime import UTC, datetime, timedelta

import pytest
from olist_support.business_contracts import RefundCommand
from olist_support.console_contracts import Principal
from olist_support.customer_intent import Authority, Confirmation
from pydantic import ValidationError


@pytest.mark.parametrize(
    "change",
    [
        {"action": "status"},
        {"unit": "USD"},
        {"amount_minor": "5000"},
        {"amount_minor": True},
        {"amount_minor": 0},
        {"amount_minor": 10001},
        {"customer_approved": True},
        {"challenge": "short"},
    ],
)
def test_confirmation_requires_explicit_exact_typed_transaction_fields(change):
    with pytest.raises(ValidationError):
        Confirmation.model_validate_json(
            __import__("json").dumps(
                {
                    "challenge": "invented-not-a-token-" * 3,
                    "action": "refund",
                    "amount_minor": 5000,
                    "unit": "SIM",
                    **change,
                }
            )
        )


def test_customer_scope_is_read_only_and_authority_has_bounded_aware_interval():
    customer = Principal(
        username="invented-customer",
        tenant_id="tenant",
        actor_id="customer",
        role="customer",
        order_ids=("order",),
    )
    with pytest.raises(PermissionError):
        customer.grant("order").require("tenant", "order", "refund")
    now = datetime.now(UTC)
    fields = dict(
        customer=customer,
        case_id="case",
        case_version=1,
        request_sha256="a" * 64,
        command=RefundCommand(
            tenant_id="tenant",
            order_id="order",
            business_operation_id="operation",
            amount_minor=5000,
            expected_version=0,
        ),
        action_digest="b" * 64,
        record_pin="c" * 64,
        issued_at=now,
        expires_at=now + timedelta(minutes=5),
    )
    assert Authority(**fields).customer == customer
    with pytest.raises(ValueError):
        Authority(**{**fields, "expires_at": now + timedelta(minutes=6)})
    with pytest.raises(ValueError):
        Authority(**{**fields, "confirmed_at": now - timedelta(seconds=1)})
