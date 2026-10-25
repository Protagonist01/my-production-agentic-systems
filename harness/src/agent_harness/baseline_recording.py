"""Separate executed deterministic comparators; never fresh-provider evidence."""

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal, Protocol
from uuid import uuid4

from pydantic import AwareDatetime

from agent_harness.cases import LoadedManifest
from agent_harness.contracts import (
    Agent,
    AgentInput,
    AgentResult,
    Contract,
    ModelGateway,
    ModelRequest,
    ModelResponse,
    NonEmpty,
    RunContext,
    Usage,
)
from agent_harness.release_contracts import CandidateSpec, Sha256, pin, verify_sources
from agent_harness.trial_runner import (
    StateLease,
    TrialComponents,
    TrialEnvironment,
    TrialFactory,
    run_trials,
)
from agent_harness.trials import (
    BatchReport,
    TrialJournal,
    TrialSchedule,
    _write_exclusive,
    validate_schedule,
)


def zero_usage(currency: str) -> Usage:
    return Usage(
        model_calls=0, input_tokens=0, output_tokens=0, cost=Decimal(0), cost_currency=currency
    )


class BaselineManifest(Contract):
    version: Literal["executed-deterministic-baseline-v1"] = "executed-deterministic-baseline-v1"
    origin: Literal["deterministic"] = "deterministic"
    execution_id: NonEmpty
    algorithm: NonEmpty
    candidate: CandidateSpec
    started_at: AwareDatetime
    finished_at: AwareDatetime
    batch_sha256: Sha256


@dataclass(frozen=True)
class VerifiedBaseline:
    manifest: BaselineManifest
    batch: BatchReport


class BaselineFactory(TrialFactory, Protocol):
    @property
    def candidate(self) -> CandidateSpec: ...
    @property
    def algorithm(self) -> str: ...
    def validate(self) -> None: ...


@dataclass
class DenyModels:
    attempted: bool = False

    def generate(self, context: RunContext, request: ModelRequest) -> ModelResponse:
        self.attempted = True
        raise ValueError("deterministic baseline cannot call a model gateway")


@dataclass(frozen=True)
class GuardAgent:
    delegate: Agent
    gate: DenyModels

    def run(self, context: RunContext, input: AgentInput, gateway: ModelGateway) -> AgentResult:
        result = self.delegate.run(context, input, self.gate)
        if self.gate.attempted or result.usage != zero_usage(context.budget.cost_currency):
            raise ValueError(
                "deterministic baseline attempted model use or claimed nonzero/unknown usage"
            )
        return result


@dataclass(frozen=True)
class GuardFactory:
    delegate: BaselineFactory

    def build(self, context: RunContext, state: StateLease) -> TrialComponents:
        parts = self.delegate.build(context, state)
        gate = DenyModels()
        return replace(parts, agent=GuardAgent(parts.agent, gate), gateway=gate)


def validate_baseline(schedule: TrialSchedule, loaded: LoadedManifest, spec: CandidateSpec) -> None:
    validate_schedule(schedule, loaded)
    if (
        len(schedule.trial_ids) != 3
        or schedule.max_parallel != 1
        or schedule.fault_plan is not None
    ):
        raise ValueError(
            "baseline requires three sequential trials without an unimplemented fault plan"
        )
    for task in schedule.tasks:
        ctx = task.context
        if (
            ctx.mode != "offline_fake"
            or ctx.budget.cost_currency != spec.recording_budget.cost_currency
            or (
                ctx.versions.candidate,
                ctx.versions.code_revision,
                ctx.versions.environment_lock,
            )
            != (spec.candidate, spec.code_revision, spec.environment_lock)
        ):
            raise ValueError("deterministic task differs from pinned offline baseline")


def record_baseline(
    schedule: TrialSchedule,
    loaded: LoadedManifest,
    factory: BaselineFactory,
    environment: TrialEnvironment,
    output: Path,
    *,
    candidate_sha256: str,
    source_root: Path,
) -> BaselineManifest:
    factory.validate()
    validate_baseline(schedule, loaded, factory.candidate)
    if pin(factory.candidate) != candidate_sha256:
        raise ValueError("baseline candidate differs from external pin")
    verify_sources(source_root, factory.candidate)
    output.mkdir(mode=0o700)
    started = datetime.now(UTC)
    batch = run_trials(schedule, loaded, GuardFactory(factory), environment, output / "journal")
    manifest = BaselineManifest(
        execution_id=str(uuid4()),
        algorithm=factory.algorithm,
        candidate=factory.candidate,
        started_at=started,
        finished_at=datetime.now(UTC),
        batch_sha256=pin(batch),
    )
    _write_exclusive(output / "baseline.json", manifest.canonical_json())
    return manifest


def read_baseline(
    root: Path, loaded: LoadedManifest, *, evidence_sha256: str, candidate_sha256: str
) -> VerifiedBaseline:
    path = root / "baseline.json"
    if root.is_symlink() or path.is_symlink():
        raise ValueError("baseline symlink rejected")
    raw = path.read_bytes()
    manifest = BaselineManifest.model_validate_json(raw)
    if (
        raw != manifest.canonical_json().encode()
        or pin(manifest) != evidence_sha256
        or pin(manifest.candidate) != candidate_sha256
        or manifest.finished_at < manifest.started_at
    ):
        raise ValueError("baseline differs from canonical external pins/interval")
    if {p.name for p in root.iterdir()} - {"baseline.json", "journal", "observations"}:
        raise ValueError("unexpected deterministic artifact; provider receipts are forbidden")
    if (root / "journal").is_symlink():
        raise ValueError("baseline journal symlink rejected")
    batch = TrialJournal(root / "journal").read(loaded)
    validate_baseline(batch.schedule, loaded, manifest.candidate)
    if pin(batch) != manifest.batch_sha256 or batch.missing:
        raise ValueError("baseline journal differs from sealed batch")
    for row in batch.rows:
        if row.errors or row.report is None or row.timing is None:
            raise ValueError("deterministic execution evidence is incomplete")
        if row.report.report.result.usage != zero_usage(row.task.context.budget.cost_currency):
            raise ValueError("baseline requires observed zero model/token/cost usage")
    return VerifiedBaseline(manifest, batch)
