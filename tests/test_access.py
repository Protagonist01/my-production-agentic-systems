"""Cross-consumer scope and unchanged Olist wire/permission behavior."""

import hashlib

import pytest
from agent_harness.access import ResourceScope
from olist_support.business_contracts import CallerGrant
from olist_support.console_contracts import Principal
from pydantic import ValidationError
from revenue_integrity.billing_access import BillingGrant


def test_exact_resource_scope_denies_crossed_tenant_kind_id_and_capability():
    scope = ResourceScope(
        tenant_id="tenant-a",
        actor_id="actor",
        resource_kind="kind-a",
        resource_ids=("id-a",),
        capabilities=("read",),
    )
    request = dict(
        tenant_id="tenant-a", resource_kind="kind-a", resource_id="id-a", capability="read"
    )
    scope.require(**request)
    for field, value in (
        ("tenant_id", "tenant-b"),
        ("resource_kind", "kind-b"),
        ("resource_id", "id-b"),
        ("capability", "write"),
    ):
        with pytest.raises(PermissionError, match="resource scope"):
            scope.require(**{**request, field: value})


def test_empty_allowlists_deny_and_wildcard_prefixes_have_no_magic():
    scope = ResourceScope(
        tenant_id="t",
        actor_id="a",
        resource_kind="kind",
        resource_ids=("*", "prefix-"),
        capabilities=("*",),
    )
    scope.require(tenant_id="t", resource_kind="kind", resource_id="*", capability="*")
    for resource, capability in (("other", "*"), ("prefix-child", "*"), ("*", "read")):
        with pytest.raises(PermissionError):
            scope.require(
                tenant_id="t", resource_kind="kind", resource_id=resource, capability=capability
            )
    with pytest.raises(PermissionError):
        scope.model_copy(update={"resource_ids": ()}).require(
            tenant_id="t", resource_kind="kind", resource_id="*", capability="*"
        )
    with pytest.raises(PermissionError):
        scope.model_copy(update={"capabilities": ()}).require(
            tenant_id="t", resource_kind="kind", resource_id="*", capability="*"
        )


def test_olist_wire_contract_capabilities_and_existing_error_remain_unchanged():
    grant = CallerGrant(
        tenant_id="invented-tenant",
        actor_id="invented-actor",
        order_ids=("invented-order",),
        capabilities=("read", "refund"),
    )
    assert hashlib.sha256(grant.canonical_json().encode()).hexdigest() == (
        "dc9606fe823fe6601f4873f7c464f6ccaaefa9b7693d68912b53219ad05ca3d5"
    )
    assert set(CallerGrant.model_fields) == {
        "schema_version",
        "tenant_id",
        "actor_id",
        "order_ids",
        "capabilities",
    }
    assert CallerGrant.model_validate_json(grant.canonical_json()) == grant
    grant.require("invented-tenant", "invented-order", "refund")
    for tenant, order, capability in (
        ("other", "invented-order", "read"),
        ("invented-tenant", "other", "read"),
        ("invented-tenant", "invented-order", "reconcile"),
    ):
        with pytest.raises(PermissionError) as error:
            grant.require(tenant, order, capability)
        assert str(error.value) == "caller grant does not authorize this tenant/order/capability"
    with pytest.raises(ValidationError):
        CallerGrant.model_validate_json(grant.canonical_json().replace('"refund"', '"reconcile"'))
    # No new generic resource-count bound may narrow the existing CallerGrant contract.
    large = grant.model_copy(update={"order_ids": tuple(f"order-{i}" for i in range(1001))})
    large.require("invented-tenant", "order-1000", "read")


def test_principal_scope_and_distinct_role_checks_still_apply():
    principal = Principal(
        username="invented-user",
        tenant_id="tenant-a",
        actor_id="actor",
        role="operator",
        order_ids=("same-id",),
    )
    principal.grant("same-id").require("tenant-a", "same-id", "read")
    principal.require("operator")
    with pytest.raises(PermissionError, match="role"):
        principal.require("reviewer")
    with pytest.raises(PermissionError, match="caller grant"):
        principal.grant("other")


def test_revenue_domain_grant_has_own_closed_read_reconcile_vocabulary():
    grant = BillingGrant(
        tenant_id="tenant-a",
        actor_id="actor",
        world_ids=("same-id",),
        capabilities=("read", "reconcile"),
    )
    assert BillingGrant.model_validate_json(grant.canonical_json()) == grant
    grant.require(tenant_id="tenant-a", world_id="same-id", capability="reconcile")
    for tenant, world, capability in (
        ("other", "same-id", "read"),
        ("tenant-a", "other", "read"),
        ("tenant-a", "same-id", "refund"),
    ):
        with pytest.raises(PermissionError):
            grant.require(tenant_id=tenant, world_id=world, capability=capability)
    with pytest.raises(ValidationError):
        BillingGrant.model_validate_json(grant.canonical_json().replace('"reconcile"', '"refund"'))
