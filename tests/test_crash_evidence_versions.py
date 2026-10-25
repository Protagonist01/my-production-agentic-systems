"""Existing after-commit canonical artifacts retain their version and byte shape."""

import json

import pytest
from agent_harness.offline_example import example_context
from olist_support.crash_evidence import CrashEvidence
from olist_support.h10_environment import grant_for
from olist_support.release import StateSnapshot
from olist_support.workflow import WorkflowRequest


def original():
    context = example_context("invented", "0" * 64).model_copy(update={"mode": "offline_fake"})
    return CrashEvidence(
        context=context,
        request=WorkflowRequest(order_id="invented-order", text="Refund please"),
        grant=grant_for(context.tenant_id, "invented-order"),
        run_limit_minor=10000,
        before=StateSnapshot(orders=(), ledger=(), budgets=()),
    )


def test_v1_omits_new_optional_boundary_and_round_trips_identical_bytes():
    evidence = original()
    raw = evidence.canonical_json()
    assert json.loads(raw)["version"] == "olist-operator-process-crash-v1"
    assert "before_commit_boundary" not in json.loads(raw)
    assert CrashEvidence.model_validate_json(raw).canonical_json() == raw


@pytest.mark.parametrize(
    "update",
    [
        {"before_commit_boundary": True},
        {"version": "olist-operator-process-crash-v2"},
        {
            "version": "olist-operator-process-crash-v2",
            "before_commit_boundary": True,
            "after_commit_boundary": True,
        },
    ],
)
def test_versions_cannot_implicitly_relabel_or_mix_crash_boundaries(update):
    with pytest.raises(ValueError):
        CrashEvidence.model_validate_json(original().model_copy(update=update).canonical_json())
