"""Bounded spawned trial execution; state administration remains in the parent."""

import ctypes
import multiprocessing
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
from multiprocessing.reduction import ForkingPickler
from pathlib import Path
from typing import Protocol, Self, cast

from pydantic import model_validator

from agent_harness.cases import LoadedManifest
from agent_harness.contracts import Agent, Contract, ModelGateway, RunContext
from agent_harness.fault_contracts import FaultPlan
from agent_harness.faults import FaultSession
from agent_harness.process_control import OwnedProcess
from agent_harness.scorers import ManifestCaseReport, ScorerRegistry
from agent_harness.telemetry import TraceSession
from agent_harness.telemetry_contracts import TraceHealth
from agent_harness.trials import (
    BatchReport,
    TrialError,
    TrialJournal,
    TrialRow,
    TrialSchedule,
    TrialTask,
    validate_schedule,
)

MAX_TRIAL_BYTES = 4 * 1024 * 1024
MAX_MANIFEST_BYTES = 8 * 1024 * 1024
CLEANUP_SECONDS = 0.25


@dataclass(frozen=True)
class StateLease:
    reference: str
    fixture: str
    access: object = field(repr=False)


class TrialEnvironment(Protocol):
    @property
    def version(self) -> str: ...

    @property
    def fixture(self) -> str: ...

    def prepare(self, experiment_id: str, task: TrialTask) -> StateLease: ...
    def release(self, lease: StateLease) -> None: ...


@dataclass(frozen=True)
class TrialComponents:
    agent: Agent
    gateway: ModelGateway
    scorers: ScorerRegistry
    trace: TraceSession | None = None


class TrialFactory(Protocol):
    def build(self, context: RunContext, state: StateLease) -> TrialComponents: ...


class FaultTrialFactory(Protocol):
    def build_faults(
        self, context: RunContext, state: StateLease, faults: FaultSession
    ) -> TrialComponents: ...


class _WorkerResult(Contract):
    report: ManifestCaseReport | None = None
    error: TrialError | None = None
    telemetry: TraceHealth | None = None

    @model_validator(mode="after")
    def exactly_one(self) -> Self:
        if (self.report is None) == (self.error is None):
            raise ValueError("worker requires one report or error")
        if self.report is not None and self.report.report.telemetry != self.telemetry:
            raise ValueError("worker telemetry differs from case report")
        return self


def _worker(
    factory: TrialFactory,
    loaded: LoadedManifest,
    context: RunContext,
    lease: StateLease,
    buffer: ctypes.Array[ctypes.c_ubyte],
    size: ctypes.c_int,
    plan: FaultPlan | None,
) -> None:
    with open(os.devnull, "w") as sink, redirect_stdout(sink), redirect_stderr(sink):
        trace = None
        try:
            context = RunContext.model_validate_json(context.canonical_json())
            case = loaded.entry(context.case_id).case
            faults = None
            if case.faults:
                if plan is None or not callable(getattr(factory, "build_faults", None)):
                    raise ValueError("fault trial requires explicit fault-aware factory")
                faults = FaultSession(context, case.faults, plan)
                parts = cast(FaultTrialFactory, factory).build_faults(context, lease, faults)
            else:
                parts = factory.build(context, lease)
            trace = parts.trace
            bound = parts.scorers.bind(loaded)
            report = bound.run_case(
                context, context.case_id, parts.agent, parts.gateway, faults=faults, trace=trace
            )
            result = _WorkerResult(report=report, telemetry=report.report.telemetry)
        except BaseException:
            result = _WorkerResult(error="execution_error")
        if trace is not None:
            result = result.model_copy(update={"telemetry": trace.finish()})
        encoded = result.canonical_json().encode("utf-8")
        if len(encoded) > MAX_TRIAL_BYTES:
            encoded = _WorkerResult(error="invalid_frame").canonical_json().encode()
        ctypes.memmove(buffer, encoded, len(encoded))
        size.value = len(encoded)


class WorkerCleanupError(RuntimeError):
    """Do not release state or admit additional work after failed owned-worker cleanup."""


def _isolated(
    factory: TrialFactory,
    loaded: LoadedManifest,
    task: TrialTask,
    lease: StateLease,
    timeout_seconds: float,
    plan: FaultPlan | None = None,
) -> _WorkerResult:
    try:
        # Windows starts a bootstrap process before serializing spawn arguments.
        # Reject ordinary unpicklable factory/state objects before creating that process.
        ForkingPickler.dumps((factory, loaded, task.context, lease, plan))
    except Exception:
        return _WorkerResult(error="worker_start_error")
    end = time.monotonic() + timeout_seconds
    ctx = multiprocessing.get_context("spawn")
    buffer = ctx.RawArray(ctypes.c_ubyte, MAX_TRIAL_BYTES)
    size = ctx.RawValue(ctypes.c_int, 0)
    process = OwnedProcess(
        ctx.Process(
            target=_worker,
            args=(factory, loaded, task.context, lease, buffer, size, plan),
            daemon=True,
        )
    )
    started = False
    try:
        try:
            process.start()
            started = True
        except Exception:
            return _WorkerResult(error="worker_start_error")
        process.join(max(0.0, end - time.monotonic()))
        if process.is_alive() or time.monotonic() >= end:
            return _WorkerResult(error="timeout")
        if process.exitcode != 0 or not 0 < size.value <= MAX_TRIAL_BYTES:
            return _WorkerResult(error="worker_crash")
        try:
            return _WorkerResult.model_validate_json(bytes(buffer[: size.value]))
        except ValueError:
            return _WorkerResult(error="invalid_frame")
    finally:
        if started:
            if process.is_alive():
                process.terminate()
                process.join(CLEANUP_SECONDS)
            if process.is_alive():
                process.kill()
                process.join(CLEANUP_SECONDS)
            if process.is_alive():
                raise WorkerCleanupError("Owned trial worker could not be reaped")
        process.close()


def _coordinate(
    task: TrialTask,
    schedule: TrialSchedule,
    loaded: LoadedManifest,
    factory: TrialFactory,
    environment: TrialEnvironment,
    abort: threading.Event,
) -> TrialRow:
    errors: list[TrialError] = []
    report = None
    telemetry = None
    lease = None
    state_ref = None
    can_release = True
    if abort.is_set():
        return TrialRow(task=task, errors=("worker_cleanup_error",))
    try:
        lease = environment.prepare(schedule.experiment_id, task)
        if not lease.reference.strip() or lease.fixture != schedule.state_fixture:
            raise ValueError("prepared state differs from scheduled fixture")
        state_ref = lease.reference
    except Exception:
        errors.append("setup_error")
    try:
        if not errors and lease is not None:
            if abort.is_set():
                errors.append("worker_cleanup_error")
            else:
                duration = (task.context.deadline - task.context.clock).total_seconds()
                result = _isolated(
                    factory,
                    loaded,
                    task,
                    lease,
                    min(schedule.worker_timeout_seconds, duration),
                    schedule.fault_plan,
                )
                report = result.report
                telemetry = result.telemetry
                if result.error is not None:
                    errors.append(result.error)
                if report is not None and (
                    report.manifest != schedule.manifest or report.report.context != task.context
                ):
                    report = None
                    errors.append("invalid_frame")
    except WorkerCleanupError:
        can_release = False
        abort.set()
        errors.append("worker_cleanup_error")
    except Exception:
        errors.append("execution_error")
    finally:
        if lease is not None and can_release:
            try:
                environment.release(lease)
            except Exception:
                errors.append("cleanup_error")
    return TrialRow(
        task=task, state_ref=state_ref, report=report, errors=tuple(errors), telemetry=telemetry
    )


def run_trials(
    schedule: TrialSchedule,
    loaded: LoadedManifest,
    factory: TrialFactory,
    environment: TrialEnvironment,
    journal_path: Path,
) -> BatchReport:
    schedule = TrialSchedule.model_validate_json(schedule.canonical_json())
    validate_schedule(schedule, loaded)
    if (environment.version, environment.fixture) != (
        schedule.environment_version,
        schedule.state_fixture,
    ):
        raise ValueError("environment version/fixture differs from schedule")
    if len(loaded.manifest.canonical_json().encode()) > MAX_MANIFEST_BYTES:
        raise ValueError("trial manifest exceeds worker input bound")
    journal = TrialJournal.create(journal_path, schedule)
    abort = threading.Event()

    def execute(task: TrialTask) -> None:
        row = _coordinate(task, schedule, loaded, factory, environment, abort)
        # Disk failures propagate. Recovery exposes a missing/corrupt row, never a pass.
        journal.append(row)

    with ThreadPoolExecutor(max_workers=schedule.max_parallel) as pool:
        futures = [pool.submit(execute, task) for task in schedule.tasks]
        for future in futures:
            future.result()
    return journal.read(loaded, fault_plan=schedule.fault_plan)
