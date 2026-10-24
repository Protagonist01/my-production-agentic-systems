"""Private operator-selected process-death drill; not provider or H10 quality evidence."""

import multiprocessing
import os
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any, Literal

from agent_harness.contracts import Contract, RunContext
from agent_harness.process_control import OwnedProcess
from agent_harness.release_contracts import pin, sha256
from agent_harness.trial_runner import WorkerCleanupError
from agent_harness.trials import _write_exclusive

from olist_support.business import BusinessStore
from olist_support.business_contracts import CallerGrant
from olist_support.fresh_execution import NoSecondDispatch
from olist_support.h10_environment import OlistAccess, grant_for
from olist_support.h10_manifest import domain_task
from olist_support.policy_cases import PolicyCase
from olist_support.release import StateSnapshot, _expected_state, collect_state
from olist_support.workflow import (
    FixedPlanner,
    IntentPlan,
    SupportWorkflow,
    WorkflowRequest,
    WorkflowResult,
)
from olist_support.workflow_postgres import saver

EXIT_CODE = 23


class CrashEvidence(Contract):
    version: Literal["olist-operator-process-crash-v1"] = "olist-operator-process-crash-v1"
    context: RunContext
    request: WorkflowRequest
    grant: CallerGrant
    run_limit_minor: int
    before: StateSnapshot
    committed: StateSnapshot | None = None
    resumed: StateSnapshot | None = None
    duplicate: StateSnapshot | None = None
    result: WorkflowResult | None = None
    duplicate_result: WorkflowResult | None = None
    after_commit_boundary: bool = False
    exit_code: int | None = None
    errors: tuple[str, ...] = ()


def _crash_worker(
    context: RunContext, access: OlistAccess, request: WorkflowRequest, boundary: Any
) -> None:
    with open(os.devnull, "w") as sink, redirect_stdout(sink), redirect_stderr(sink):

        def fault(stage: str) -> None:
            if stage == "after_commit":
                # RawValue is shared with the observing parent; no credential/file output.
                boundary.value = 1
                os._exit(EXIT_CODE)

        with saver(access.database.connect) as checkpoints:
            SupportWorkflow(
                BusinessStore(access.database.connect), FixedPlanner(IntentPlan(intent="refund"))
            ).run(
                context,
                request,
                access.grant,
                checkpoints,
                run_limit_minor=access.run_limit_minor,
                fault=fault,
            )


def collect_crash(
    context: RunContext,
    access: OlistAccess,
    request: WorkflowRequest,
    output: Path,
    *,
    timeout_seconds: float = 90.0,
) -> CrashEvidence:
    """Parent owns state, must release only after this returns or ordinary failure.

    WorkerCleanupError means a live owned worker may remain: preserve state and stop.
    The function never receives administrator access, evaluator labels or a model.
    """
    context = RunContext.model_validate_json(context.canonical_json())
    request = WorkflowRequest.model_validate_json(request.canonical_json())
    if (
        context.mode != "offline_fake"
        or context.agent_id != "olist"
        or not 0 < timeout_seconds <= 300
    ):
        raise ValueError("process drill requires explicit offline Olist scope")
    if (
        request.order_id != access.order_id
        or access.grant != grant_for(context.tenant_id, access.order_id)
        or access.run_limit_minor != 10000
    ):
        raise ValueError("process drill grant/order/limit differs from controlled SIM fixture")
    output.mkdir(mode=0o700)
    connect = access.database.connect
    with connect() as connection:
        before = collect_state(connection)
    if before != access.before:
        raise ValueError("process drill must start from the parent's fresh before-state")
    errors = []
    ctx = multiprocessing.get_context("spawn")
    boundary = ctx.RawValue("b", 0)
    process = OwnedProcess(
        ctx.Process(target=_crash_worker, args=(context, access, request, boundary), daemon=True)
    )
    started = False
    exit_code = None
    try:
        process.start()
        started = True
        process.join(timeout_seconds)
        if process.is_alive():
            errors.append("worker_timeout")
        exit_code = process.exitcode
    except Exception:
        errors.append("worker_start_or_execution_error")
    finally:
        if started:
            if process.is_alive():
                process.terminate()
                process.join(1.0)
            if process.is_alive():
                process.kill()
                process.join(1.0)
            if process.is_alive():
                raise WorkerCleanupError("process drill worker could not be reaped; preserve state")
        process.close()
    if exit_code != EXIT_CODE or not boundary.value:
        errors.append("after_commit_process_death_unobserved")
    committed = resumed = duplicate = result = duplicate_result = None
    try:
        with connect() as connection:
            committed = collect_state(connection)
        if not errors:
            with saver(connect) as checkpoints:
                result = SupportWorkflow(BusinessStore(connect), NoSecondDispatch()).run(
                    context.model_copy(update={"run_id": context.run_id + "-restart"}),
                    request,
                    access.grant,
                    checkpoints,
                    run_limit_minor=access.run_limit_minor,
                )
            with connect() as connection:
                resumed = collect_state(connection)
            with saver(connect) as checkpoints:
                duplicate_result = SupportWorkflow(BusinessStore(connect), NoSecondDispatch()).run(
                    context.model_copy(update={"run_id": context.run_id + "-duplicate"}),
                    request,
                    access.grant,
                    checkpoints,
                    run_limit_minor=access.run_limit_minor,
                )
            with connect() as connection:
                duplicate = collect_state(connection)
    except Exception:
        errors.append("state_read_or_restart_error")
    evidence = CrashEvidence(
        context=context,
        request=request,
        grant=access.grant,
        run_limit_minor=access.run_limit_minor,
        before=before,
        committed=committed,
        resumed=resumed,
        duplicate=duplicate,
        result=result,
        duplicate_result=duplicate_result,
        after_commit_boundary=bool(boundary.value),
        exit_code=exit_code,
        errors=tuple(errors),
    )
    _write_exclusive(output / "crash.json", evidence.canonical_json())
    return evidence


def assess_crash(
    evidence: CrashEvidence, label: PolicyCase, context: RunContext
) -> dict[str, object]:
    evidence = CrashEvidence.model_validate_json(evidence.canonical_json())
    label = PolicyCase.model_validate_json(label.canonical_json())
    if (
        evidence.context != context
        or context.case_id != label.input.case_id
        or context.mode != "offline_fake"
        or context.agent_id != "olist"
    ):
        raise ValueError("process evidence belongs to different offline case/context")
    if (
        evidence.request
        != WorkflowRequest(order_id=label.input.order.order_id, text=label.input.request.message)
        or evidence.grant != grant_for(context.tenant_id, label.input.order.order_id)
        or evidence.run_limit_minor != 10000
    ):
        raise ValueError("process evidence differs from request/grant/limit")
    task = domain_task(label, context, evidence.grant, evidence.run_limit_minor)
    expected = _expected_state(label, task, evidence.before)
    eligible = label.expected.action == "propose_full_refund"
    process_death = evidence.after_commit_boundary and evidence.exit_code == EXIT_CODE
    exact = (
        eligible
        and expected is not None
        and evidence.committed == expected
        and evidence.resumed == expected
        and evidence.duplicate == expected
    )
    result = evidence.result
    truthful = bool(
        result
        and result.outcome == "refunded"
        and result.receipt is not None
        and expected is not None
        and task.command is not None
        and result.receipt
        == next(
            (
                r.receipt
                for r in expected.ledger
                if r.operation_id == task.command.business_operation_id
            ),
            None,
        )
        and result == evidence.duplicate_result
    )
    return {
        "version": evidence.version,
        "evidence_sha256": pin(evidence),
        "mechanism_only": True,
        "provider_calls": 0,
        "process_death_observed": process_death,
        "exact_state_after_restart_and_duplicate": exact,
        "original_receipt_and_duplicate_result_preserved": truthful,
        "passed": not evidence.errors and process_death and exact and truthful,
        "release_allowed": False,
        "limitations": (
            "Operator-selected SIM refund, one after-commit hard exit; no model "
            "classification, fresh H10 receipt or complete fault matrix."
        ),
    }


def read_crash(
    root: Path, *, evidence_sha256: str, label: PolicyCase, context: RunContext
) -> dict[str, object]:
    path = root / "crash.json"
    if root.is_symlink() or path.is_symlink() or {p.name for p in root.iterdir()} != {"crash.json"}:
        raise ValueError("process evidence inventory differs")
    raw = path.read_bytes()
    if sha256(raw) != evidence_sha256:
        raise ValueError("process evidence differs from external pin")
    evidence = CrashEvidence.model_validate_json(raw)
    if evidence.canonical_json().encode() != raw:
        raise ValueError("process evidence is not canonical")
    return assess_crash(evidence, label, context)
