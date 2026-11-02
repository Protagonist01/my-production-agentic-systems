"""Compatibility of durable staff records and opt-in model decision metadata."""

import json
from datetime import UTC, datetime

from agent_harness.offline_example import example_context
from olist_support.console_contracts import CaseRecord, Submission
from olist_support.routing_contracts import RoutingPlan
from olist_support.workflow import IntentDecision


def record():
    return CaseRecord(
        case_id="invented-case",
        tenant_id="invented-tenant",
        order_id="invented-order",
        submitted_actor="invented-operator",
        status="review_required",
        version=1,
        request=Submission(
            event_key="invented-event",
            order_id="invented-order",
            text="Invented request",
            intent="refund",
        ),
        context=example_context("invented-code", "invented-lock"),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def test_default_staff_wire_omits_new_planner_fields_and_reads_historical_json():
    case = record()
    raw = json.loads(case.canonical_json())
    assert set(raw) == {
        "schema_version",
        "case_id",
        "tenant_id",
        "order_id",
        "submitted_actor",
        "status",
        "version",
        "request",
        "context",
        "created_at",
        "updated_at",
        "result",
        "proposal",
        "evidence",
        "confirmation",
        "command",
        "record_pin",
        "action_digest",
        "approved_by",
        "approval_version",
        "error_code",
    }
    assert CaseRecord.model_validate_json(json.dumps(raw)) == case


def test_planner_wire_keeps_fine_intent_and_requested_amount_on_roundtrip():
    decision = IntentDecision(
        plan=RoutingPlan(
            routing_version="olist-intent-routing-v2", intent="refund", requested_minor=3000
        )
    )
    case = record().model_copy(update={"intent_source": "planner", "intent_decision": decision})
    raw = json.loads(case.canonical_json())
    assert raw["intent_source"] == "planner"
    assert raw["intent_decision"]["plan"]["requested_minor"] == 3000
    restored = CaseRecord.model_validate_json(json.dumps(raw))
    assert restored.intent_decision.plan == decision.plan
    assert isinstance(restored.intent_decision.plan, RoutingPlan)
