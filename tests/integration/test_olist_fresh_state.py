"""Real SQL collection, persisted duplicate delivery and cleanup; invented model responses."""

import secrets
import uuid

import pytest
from agent_harness.admission import GEMINI_TOKEN_CEILING, GeminiFreeAdmission
from agent_harness.contracts import ModelMessage, ModelResponse, Usage
from agent_harness.controls import BoundedGateway, ExecutionPolicy, SharedControls
from agent_harness.fresh_recording import ReceiptGateway
from agent_harness.gateway import failed_response
from agent_harness.postgres import Trial, create_trial
from olist_support.business import sha
from olist_support.business_contracts import RefundCommand
from olist_support.fresh_cli import route_template
from olist_support.fresh_execution import execute_trial
from olist_support.fresh_release import RulesPlanner
from olist_support.release import score
from olist_support.workflow import GatewayPlanner
from test_olist_business import app as app
from test_olist_release import case_for, task_for
from test_olist_workflow import context


@pytest.mark.parametrize("kind", ["rules", "mock_model", "model_timeout", "planner_exception"])
def test_collector_scores_actual_state_recovers_without_redispatch_and_drops_owned_trial(
    app, tmp_path, kind
):
    server, parent, _ = app
    trial = Trial(parent.workspace_key, "fresh-" + uuid.uuid4().hex[:16], secrets.token_hex(32))
    create_trial(server, trial)
    case = case_for()
    request = case.input.request.model_copy(
        update={
            "message": (
                "Primary request: please refund the full paid amount for this canceled order."
            )
        }
    )
    case = case.model_copy(update={"input": case.input.model_copy(update={"request": request})})
    run = "invented-fresh-" + uuid.uuid4().hex
    view = case.input.order
    command = RefundCommand(
        tenant_id=view.tenant_id,
        order_id=view.order_id,
        business_operation_id=sha("olist-full-refund-v1|" + run),
        amount_minor=5000,
        expected_version=0,
    )
    task = task_for(case, run=run, command=command)
    ctx = context(event=run, run=run)
    ctx = ctx.model_copy(
        update={
            "mode": "fresh_candidate",
            "case_id": task.case_id,
            "versions": ctx.versions.model_copy(
                update={"data_snapshot": view.source_manifest_sha256}
            ),
            "budget": ctx.budget.model_copy(
                update={"max_model_calls": 1, "max_tokens": GEMINI_TOKEN_CEILING}
            ),
        }
    )
    receipts = tmp_path / "receipts"
    receipts.mkdir()
    calls = []

    class Transport:
        def generate(self, wire, *, timeout_seconds):
            calls.append(wire)
            assert wire.messages[1].content == request.message
            assert view.order_id not in wire.canonical_json()
            if kind == "model_timeout":
                return failed_response(wire, "timeout", "invented", dispatched=False)
            return ModelResponse(
                provider=wire.provider,
                model=wire.model,
                output=ModelMessage(role="assistant", content='{"intent":"refund"}'),
                usage=Usage(
                    model_calls=1, input_tokens=10, output_tokens=4, cost=None, cost_currency=None
                ),
            )

    class Raises:
        def plan(self, *args):
            raise ValueError("private-invented-exception-canary")

    if kind in ("mock_model", "model_timeout"):
        capture = ReceiptGateway(Transport(), ctx, receipts, "invented-execution")
        gateway = BoundedGateway(
            capture,
            SharedControls(),
            GeminiFreeAdmission(free_tier_confirmed=True),
            policy=ExecutionPolicy(max_attempts=1),
        )
        planner = GatewayPlanner(gateway, route_template())
    elif kind == "rules":
        planner = RulesPlanner()
    else:
        planner = Raises()
    row = execute_trial(
        server,
        trial,
        case,
        task,
        ctx,
        planner,
        mode="gemini" if kind in ("mock_model", "model_timeout") else "rules",
        receipt_root=receipts if kind in ("mock_model", "model_timeout") else None,
    )
    assert row.cleanup_ok
    assert "private-invented-exception-canary" not in row.canonical_json()
    assert len(calls) == (1 if kind in ("mock_model", "model_timeout") else 0)
    assert len(row.receipts) == len(calls)
    assert row.observation is not None
    if kind in ("rules", "mock_model"):
        assert row.duplicate_delivery_unchanged and not row.errors
        assert score(case, task, row.observation).category == "correct"
        assert len(row.observation.after.ledger) == 1
    else:
        assert row.observation.after == row.observation.before and row.errors
        assert score(case, task, row.observation).category == "unresolved"
    with server.connect() as admin:
        assert not admin.execute(
            "SELECT 1 FROM pg_database WHERE datname=%s", (trial.name,)
        ).fetchone()
