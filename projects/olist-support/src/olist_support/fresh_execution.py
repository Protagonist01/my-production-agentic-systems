"""One isolated SIM workflow trial, independently observed before and after all attempts."""

import time
from pathlib import Path

from agent_harness.contracts import RunContext
from agent_harness.postgres import Server, Trial, drop_trial
from agent_harness.release_contracts import AttemptReceipt

from olist_support.business import BusinessStore, enroll, setup
from olist_support.fresh_release import FreshRow, Mode
from olist_support.policy_cases import PolicyCase
from olist_support.release import Observation, ScheduledTrial, collect_state
from olist_support.workflow import (
    IntentDecision,
    Planner,
    SupportWorkflow,
    WorkflowRequest,
)
from olist_support.workflow_postgres import saver, setup_checkpoints


class ObservedPlanner:
    def __init__(self, delegate: Planner) -> None:
        self.delegate = delegate
        self.decision: IntentDecision | None = None

    def plan(self, context: RunContext, request: WorkflowRequest) -> IntentDecision:
        self.decision = self.delegate.plan(context, request)
        return self.decision


class NoSecondDispatch:
    def plan(self, context: RunContext, request: WorkflowRequest) -> IntentDecision:
        raise ValueError("duplicate workflow delivery attempted another model call")


def execute_trial(
    server: Server,
    trial: Trial,
    case: PolicyCase,
    task: ScheduledTrial,
    context: RunContext,
    planner: Planner,
    *,
    mode: Mode,
    receipt_root: Path | None = None,
) -> FreshRow:
    """Caller creates only this owned trial; capture errors never imply rollback."""
    started = time.monotonic()
    observed = ObservedPlanner(planner)
    before = after = None
    result = None
    duplicate_ok = cleanup_ok = False
    errors: list[str] = []
    try:
        with server.connect(trial.name) as admin:
            setup(admin, trial.name)
            setup_checkpoints(admin, trial.name)
            enroll(admin, case.input.order, case.input.confirmation)
        with server.connect(trial.name) as admin:
            before = collect_state(admin)
        connect = lambda: server.connect_trial(trial)  # noqa: E731
        store = BusinessStore(connect)
        request = WorkflowRequest(
            order_id=case.input.order.order_id, text=case.input.request.message
        )
        with saver(connect) as checkpoints:
            result = SupportWorkflow(store, observed).run(
                context, request, task.grant, checkpoints, run_limit_minor=task.run_limit_minor
            )
        with server.connect(trial.name) as admin:
            first_after = collect_state(admin)
        resumed_context = context.model_copy(update={"run_id": context.run_id + "-delivery"})
        with saver(connect) as checkpoints:
            resumed = SupportWorkflow(BusinessStore(connect), NoSecondDispatch()).run(
                resumed_context,
                request,
                task.grant,
                checkpoints,
                run_limit_minor=task.run_limit_minor,
            )
        with server.connect(trial.name) as admin:
            after = collect_state(admin)
        duplicate_ok = resumed == result and after == first_after
        if not duplicate_ok:
            errors.append("duplicate_delivery_changed_state_or_result")
        if observed.decision and observed.decision.failure_code:
            errors.append("model_attempt_failed")
    except Exception:
        # Exception text can include source rows, SQL or credentials; fixed codes only.
        errors.append("execution_or_state_collection_failed")
        if before is not None:
            try:
                with server.connect(trial.name) as admin:
                    after = collect_state(admin)
            except Exception:
                errors.append("final_state_unavailable")
    finally:
        try:
            drop_trial(server, trial)
            cleanup_ok = True
        except Exception:
            errors.append("owned_trial_cleanup_failed")
    if not duplicate_ok and not errors:
        errors.append("duplicate_delivery_unverified")
    receipts: tuple[AttemptReceipt, ...] = ()
    if receipt_root is not None:
        receipts = tuple(
            AttemptReceipt.model_validate_json(p.read_bytes())
            for p in sorted(receipt_root.glob("*.json"))
        )
    observation = (
        Observation(
            case_id=task.case_id,
            trial_id=task.trial_id,
            before=before,
            after=after,
            outcome=result.outcome if result else None,
            receipt=result.receipt if result else None,
            message=result.message if result else None,
            errors=tuple(errors),
        )
        if before is not None
        else None
    )
    return FreshRow(
        case_id=task.case_id,
        trial_id=task.trial_id,
        mode=mode,
        observation=observation,
        decision=observed.decision,
        receipts=receipts,
        elapsed_seconds=time.monotonic() - started,
        duplicate_delivery_unchanged=duplicate_ok,
        cleanup_ok=cleanup_ok,
        errors=tuple(errors),
    )
