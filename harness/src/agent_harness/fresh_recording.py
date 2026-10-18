"""Owned uncached dispatch inside H6 workers; no prior-response or resume input."""

import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, Protocol, cast
from uuid import uuid4

from agent_harness.cases import LoadedManifest
from agent_harness.contracts import Agent, ModelRequest, ModelResponse, RunContext
from agent_harness.controls import AdmissionPolicy, BoundedGateway, SharedControls, add_money
from agent_harness.faults import FaultSession
from agent_harness.gateway import ModelTransport, ProviderGateway
from agent_harness.release_contracts import (
    AttemptReceipt,
    CandidateSpec,
    EvidenceManifest,
    pin,
    sha256,
    verify_sources,
)
from agent_harness.scorers import ScorerRegistry
from agent_harness.trial_runner import (
    StateLease,
    TrialComponents,
    TrialEnvironment,
    run_trials,
)
from agent_harness.trials import TrialSchedule, _write_exclusive, validate_schedule


@dataclass(frozen=True)
class FreshComponents:
    agent: Agent
    transport: ModelTransport
    admission: AdmissionPolicy
    scorers: ScorerRegistry


class FreshFactory(Protocol):
    @property
    def candidate(self) -> CandidateSpec: ...

    @property
    def origin(self) -> Literal["provider", "mock"]: ...

    def build(self, context: RunContext, state: StateLease) -> FreshComponents: ...


class FaultFreshFactory(FreshFactory, Protocol):
    def build_faults(
        self, context: RunContext, state: StateLease, faults: FaultSession
    ) -> FreshComponents: ...


def validate_fresh(schedule: TrialSchedule, spec: CandidateSpec) -> None:
    if len(schedule.trial_ids) != 3 or schedule.max_parallel != 1:
        raise ValueError("fresh recording requires three trials and sequential budget partitions")
    costs = spec.recording_budget.max_cost * 0
    for task in schedule.tasks:
        ctx = task.context
        if ctx.mode != "fresh_candidate" or (
            ctx.versions.candidate,
            ctx.versions.code_revision,
            ctx.versions.environment_lock,
        ) != (spec.candidate, spec.code_revision, spec.environment_lock):
            raise ValueError("fresh task differs from pinned candidate")
        if ctx.budget.cost_currency != spec.recording_budget.cost_currency:
            raise ValueError("recording budget currency mismatch")
        costs = add_money(costs, ctx.budget.max_cost)
    if (
        sum(t.context.budget.max_model_calls for t in schedule.tasks)
        > spec.recording_budget.max_model_calls
        or sum(t.context.budget.max_tokens for t in schedule.tasks)
        > spec.recording_budget.max_tokens
        or costs > spec.recording_budget.max_cost
    ):
        raise ValueError("trial budget partitions exceed recording budget")


class ReceiptGateway(ProviderGateway):
    """Serialize calls and persist each attempt before the response reaches agent code."""

    def __init__(
        self, transport: ModelTransport, context: RunContext, root: Path, execution_id: str
    ) -> None:
        super().__init__(transport)
        self.context, self.root, self.execution_id = context, root, execution_id
        self.serial = threading.Lock()

    def generate(
        self, context: RunContext, request: ModelRequest, *, timeout_seconds: float | None = None
    ) -> ModelResponse:
        with self.serial:
            if context != self.context or context.mode != "fresh_candidate":
                raise ValueError("agent changed capture identity")
            started = datetime.now(UTC)
            response = super().generate(context, request, timeout_seconds=timeout_seconds)
            exchange = self.exchanges[-1]
            receipt = AttemptReceipt(
                execution_id=self.execution_id,
                nonce=uuid4().hex,
                started_at=started,
                finished_at=datetime.now(UTC),
                exchange=exchange,
            )
            _write_exclusive(self.root / f"{exchange.occurrence}.json", receipt.canonical_json())
            return response


@dataclass(frozen=True)
class CaptureFactory:
    factory: FreshFactory
    root: Path
    execution_id: str
    spec: CandidateSpec

    def wrap(self, parts: FreshComponents, context: RunContext) -> TrialComponents:
        # Identity excludes labels: use the context itself for the capture directory.
        gateway = ReceiptGateway(
            parts.transport, context, self.root / pin(context), self.execution_id
        )
        controlled = BoundedGateway(
            gateway, SharedControls(), parts.admission, policy=self.spec.execution
        )
        return TrialComponents(parts.agent, controlled, parts.scorers)

    def build(self, context: RunContext, state: StateLease) -> TrialComponents:
        return self.wrap(self.factory.build(context, state), context)

    def build_faults(
        self, context: RunContext, state: StateLease, faults: FaultSession
    ) -> TrialComponents:
        if not callable(getattr(self.factory, "build_faults", None)):
            raise ValueError("fresh fault case requires reviewed fault-aware composition")
        return self.wrap(
            cast(FaultFreshFactory, self.factory).build_faults(context, state, faults), context
        )


def record_candidate(
    schedule: TrialSchedule,
    loaded: LoadedManifest,
    factory: FreshFactory,
    environment: TrialEnvironment,
    output: Path,
    *,
    candidate: CandidateSpec,
    candidate_sha256: str,
    source_root: Path,
) -> EvidenceManifest:
    spec = CandidateSpec.model_validate_json(candidate.canonical_json())
    if pin(spec) != candidate_sha256 or factory.candidate != spec:
        raise ValueError("composition differs from independently pinned candidate")
    verify_sources(source_root, spec)
    validate_schedule(schedule, loaded)
    validate_fresh(schedule, spec)
    if schedule.case_ids != loaded.manifest.case_ids:
        raise ValueError("fresh recording requires the whole reviewed population")
    started = datetime.now(UTC)
    execution_id = uuid4().hex
    output.mkdir(mode=0o700)
    captures = output / "receipts"
    captures.mkdir(mode=0o700)
    for task in schedule.tasks:
        (captures / pin(task.context)).mkdir(mode=0o700)
    batch = run_trials(
        schedule,
        loaded,
        CaptureFactory(factory, captures, execution_id, spec),
        environment,
        output / "journal",
    )
    # Source changes during execution cannot be sealed as the reviewed candidate.
    verify_sources(source_root, spec)
    receipts = {
        p.relative_to(captures).as_posix(): sha256(p.read_bytes())
        for p in sorted(captures.glob("*/*.json"))
    }
    manifest = EvidenceManifest(
        execution_id=execution_id,
        origin=factory.origin,
        candidate=spec,
        started_at=started,
        finished_at=datetime.now(UTC),
        batch_sha256=pin(batch),
        receipts=receipts,
    )
    _write_exclusive(output / "evidence.json", manifest.canonical_json())
    return manifest
