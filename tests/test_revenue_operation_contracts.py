"""Invented shape/scope controls independent of any running database."""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError
from revenue_integrity.operation_contracts import (
    ChangeCommand,
    Proposal,
    RevenueGrant,
    RevenueRecord,
)
from revenue_integrity.operations import OperationStore


def command(**changes):
    values = dict(
        tenant_id="invented",
        business_operation_id="operation",
        kind="invoice_correct",
        resource_id="invoice",
        expected_version=0,
        invoice_amount_minor=10000,
    )
    values.update(changes)
    return ChangeCommand(**values)


@pytest.mark.parametrize(
    "changes",
    [
        {"kind": "crm_trim"},
        {"target_account_id": "account"},
        {"invoice_amount_minor": True},
        {"invoice_amount_minor": -1},
        {"expected_version": True},
        {"extra": "untrusted"},
        {"kind": "account_merge", "invoice_amount_minor": None, "target_account_id": "target"},
        {"kind": "compensate", "invoice_amount_minor": None},
    ],
)
def test_exact_action_shape(changes):
    with pytest.raises(ValidationError):
        command(**changes)


def test_kind_scopes_are_not_interchangeable_and_no_wildcards():
    grant = RevenueGrant(
        tenant_id="invented",
        actor_id="operator",
        invoice_ids=("invoice",),
        account_ids=("*",),
        capabilities=("read",),
    )
    grant.require("invented", "invoice", "invoice", "read")
    for args in [
        ("other", "invoice", "invoice", "read"),
        ("invented", "account", "invoice", "read"),
        ("invented", "invoice", "invoice", "apply"),
        ("invented", "account", "anything", "read"),
    ]:
        with pytest.raises(PermissionError):
            grant.require(*args)


def test_deny_before_connection_and_revalidate_unchecked_grants():
    def connect():
        raise AssertionError("must not open database")

    store = OperationStore(connect)
    grant = RevenueGrant(tenant_id="invented", actor_id="operator")
    with pytest.raises(PermissionError):
        store.propose(grant, command())
    with pytest.raises(PermissionError):
        store.records(grant)
    with pytest.raises(ValidationError):
        store.records(grant.model_copy(update={"capabilities": ("unknown",)}))


def test_record_identity_and_timezone_rules():
    with pytest.raises(ValidationError):
        RevenueRecord(tenant_id="t", resource_id="a", kind="invoice")
    with pytest.raises(ValidationError):
        RevenueRecord(tenant_id="t", resource_id="a", kind="account", amount_minor=1)
    now = datetime.now(UTC)
    with pytest.raises(ValidationError):
        Proposal(
            command=command(),
            proposer_id="a",
            created_at=now.replace(tzinfo=None),
            expires_at=now + timedelta(seconds=1),
        )
