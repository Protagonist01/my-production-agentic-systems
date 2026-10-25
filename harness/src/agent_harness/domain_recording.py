"""Partial domain H10 wiring with explicit synthetic transport, never live release evidence."""

import json
from dataclasses import dataclass, replace
from decimal import Decimal
from pathlib import Path
from typing import Literal, Protocol

from pydantic import JsonValue

import agent_harness
from agent_harness.baseline_recording import (
    BaselineManifest,
    DenyModels,
    VerifiedBaseline,
    read_baseline,
    record_baseline,
)
from agent_harness.cases import LoadedManifest
from agent_harness.contracts import (
    AgentInput,
    AgentResult,
    Contract,
    EvidenceReference,
    Failure,
    ModelGateway,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    RunContext,
    Usage,
)
from agent_harness.controls import ReservationQuote
from agent_harness.evaluation import EvalCase, ScoreResult
from agent_harness.fresh_recording import FreshComponents, record_candidate
from agent_harness.release_contracts import (
    CandidateSpec,
    EvidenceManifest,
    pin,
    sha256,
    verify_sources,
)
from agent_harness.release_evidence import VerifiedEvidence, read_evidence
from agent_harness.scorers import ScorerCompatibility, ScorerRegistry, ScorerSpec
from agent_harness.trial_runner import StateLease, TrialComponents
from agent_harness.trials import BatchReport, TrialSchedule, TrialTask, _write_exclusive

ENVIRONMENT = "h10-partial-stateless-v1"
FIXTURE = "no-business-state-v1"


class DomainAdapter(Protocol):
    @property
    def agent_id(self) -> str: ...
    @property
    def scorer_id(self) -> str: ...
    @property
    def version(self) -> str: ...
    @property
    def package_root(self) -> Path: ...
    @property
    def source_prefix(self) -> str: ...
    @property
    def configuration_sha256(self) -> str: ...
    @property
    def baseline_algorithm(self) -> str: ...
    def baseline(self, context: RunContext, input: AgentInput) -> dict[str, JsonValue]: ...
    def validate_case(self, case: EvalCase) -> None: ...
    def run(
        self, context: RunContext, input: AgentInput, gateway: ModelGateway
    ) -> dict[str, JsonValue]: ...
    def result(self, context: RunContext, payload: dict[str, JsonValue]) -> AgentResult: ...
    def fields(
        self, case: EvalCase, context: RunContext, payload: dict[str, JsonValue]
    ) -> dict[str, bool | None]: ...


@dataclass(frozen=True)
class MockJsonTransport:
    """New synthetic dispatch each time; zero usage is invented, not provider accounting."""

    content: str
    fail: bool = False
    unknown_cost: bool = False

    @property
    def recipe_sha256(self) -> str:
        return sha256(
            json.dumps(
                {"content": self.content, "fail": self.fail, "unknown_cost": self.unknown_cost},
                sort_keys=True,
            ).encode()
        )

    def generate(self, request: ModelRequest, *, timeout_seconds: float = 30.0) -> ModelResponse:
        return ModelResponse(
            provider=request.provider,
            model=request.model,
            model_revision=request.model_revision,
            output=None if self.fail else ModelMessage(role="assistant", content=self.content),
            failure=Failure(
                stage="model", code="timeout", message="invented mock failure", retryable=False
            )
            if self.fail
            else None,
            usage=Usage(
                model_calls=1,
                input_tokens=0,
                output_tokens=0,
                cost=None if self.unknown_cost else Decimal(0),
                cost_currency=None if self.unknown_cost else "USD",
            ),
        )


class MockAdmission:
    def quote(self, request: ModelRequest) -> ReservationQuote:
        return ReservationQuote(
            version="partial-domain-mock-v1",
            max_tokens=1024,
            max_cost=Decimal(0),
            currency="USD",
            evidence_ref="invented-mock-only",
        )


@dataclass(frozen=True)
class StatelessEnvironment:
    version: str = ENVIRONMENT
    fixture: str = FIXTURE

    def prepare(self, experiment_id: str, task: TrialTask) -> StateLease:
        return StateLease("stateless:" + task.fingerprint(), self.fixture, None)

    def release(self, lease: StateLease) -> None:
        if (
            lease.fixture != self.fixture
            or lease.access is not None
            or not lease.reference.startswith("stateless:")
        ):
            raise ValueError("unexpected stateless lease")


class SavedObservation(Contract):
    context_sha256: str
    payload: dict[str, JsonValue]


@dataclass
class Slot:
    observation: SavedObservation | None = None


def source_inventory(adapter: DomainAdapter) -> dict[str, str]:
    result = {}
    for prefix, root in (
        ("harness/src/agent_harness/", Path(str(agent_harness.__file__)).parent),
        (adapter.source_prefix, adapter.package_root),
    ):
        for path in root.rglob("*"):
            if path.is_file() and path.suffix in (".py", ".sql"):
                result[prefix + path.relative_to(root).as_posix()] = sha256(path.read_bytes())
    return result


def scorer_pin(adapter: DomainAdapter, sources: dict[str, str]) -> str:
    return sha256(
        json.dumps({"version": adapter.version, "sources": sources}, sort_keys=True).encode()
    )


def verify_runtime(adapter: DomainAdapter, candidate: CandidateSpec) -> None:
    actual = source_inventory(adapter)
    if (
        candidate.source_files != {**actual, "uv.lock": candidate.environment_lock}
        or candidate.scorer_sha256 != scorer_pin(adapter, candidate.source_files)
        or candidate.model_config_sha256 != adapter.configuration_sha256
    ):
        raise ValueError("partial domain recorder differs from complete source/scorer inventory")


def scores(
    adapter: DomainAdapter, case: EvalCase, context: RunContext, saved: SavedObservation
) -> tuple[ScoreResult, ...]:
    adapter.validate_case(case)
    if saved.context_sha256 != pin(context):
        raise ValueError("saved observation differs from trial identity")
    reference = EvidenceReference(
        reference="partial-domain-observation:" + pin(saved), kind="state"
    )
    return tuple(
        ScoreResult(
            metric=name,
            scorer_version=adapter.version,
            eligible=True,
            value=float(value) if value is not None else None,
            evidence=(reference,),
            failure=Failure(
                stage="scorer",
                code="scorer_error",
                message="required domain evidence unobserved",
                retryable=False,
            )
            if value is None
            else None,
        )
        for name, value in adapter.fields(case, context, saved.payload).items()
    )


@dataclass(frozen=True)
class DomainAgent:
    adapter: DomainAdapter
    slot: Slot

    def run(self, context: RunContext, input: AgentInput, gateway: ModelGateway) -> AgentResult:
        if input.observations or self.slot.observation is not None:
            raise ValueError("partial recorder requires closed input and a fresh observation slot")
        self.slot.observation = SavedObservation(
            context_sha256=pin(context), payload=self.adapter.run(context, input, gateway)
        )
        return self.adapter.result(context, self.slot.observation.payload)


@dataclass(frozen=True)
class DomainScorer:
    adapter: DomainAdapter
    context: RunContext
    slot: Slot
    root: Path

    def score(self, case: EvalCase, result: AgentResult) -> tuple[ScoreResult, ...]:
        saved = self.slot.observation
        if saved is None or result != self.adapter.result(self.context, saved.payload):
            raise ValueError("result diverges from actual domain observation")
        values = scores(self.adapter, case, self.context, saved)
        self.root.mkdir(mode=0o700, exist_ok=True)
        if self.root.is_symlink():
            raise ValueError("observation directory cannot be symlinked")
        _write_exclusive(self.root / (pin(self.context) + ".json"), saved.canonical_json())
        return values


@dataclass(frozen=True)
class MockDomainFactory:
    candidate: CandidateSpec
    loaded: LoadedManifest
    adapter: DomainAdapter
    transport: MockJsonTransport
    root: Path
    origin: Literal["mock"] = "mock"

    def validate(self) -> None:
        verify_runtime(self.adapter, self.candidate)
        if (
            type(self.transport) is not MockJsonTransport
            or self.origin != "mock"
            or self.candidate.execution.max_attempts != 1
            or self.candidate.recording_budget.max_cost != 0
            or self.candidate.prompt_sha256 != self.transport.recipe_sha256
        ):
            raise ValueError("partial domain composition is explicitly mock-only with one attempt")
        for entry in self.loaded.manifest.entries:
            self.adapter.validate_case(entry.case)
            if entry.scorer_id != self.adapter.scorer_id:
                raise ValueError("domain scorer registry identity differs")

    def build(self, context: RunContext, state: StateLease) -> FreshComponents:
        if (
            context.agent_id != self.adapter.agent_id
            or state.fixture != FIXTURE
            or state.access is not None
        ):
            raise ValueError("domain scope/fixture differs")
        slot = Slot()
        registry = ScorerRegistry()
        registry.register(
            ScorerSpec(
                scorer_id=self.adapter.scorer_id,
                version=self.adapter.version,
                compatible=tuple(
                    ScorerCompatibility(snapshot_ref=snapshot, policy_version=policy)
                    for snapshot, policy in sorted(
                        {
                            (e.case.snapshot_ref, e.case.policy_version)
                            for e in self.loaded.manifest.entries
                        }
                    )
                ),
            ),
            DomainScorer(self.adapter, context, slot, self.root),
        )
        return FreshComponents(
            DomainAgent(self.adapter, slot), self.transport, MockAdmission(), registry
        )


def record_domain(
    schedule: TrialSchedule,
    loaded: LoadedManifest,
    factory: MockDomainFactory,
    output: Path,
    *,
    candidate_sha256: str,
    source_root: Path,
) -> EvidenceManifest:
    factory.validate()
    if loaded.pin != factory.loaded.pin or schedule.fault_plan is not None:
        raise ValueError("partial domain manifest/fault composition differs")
    verify_sources(source_root, factory.candidate)
    return record_candidate(
        schedule,
        loaded,
        replace(factory, root=output / "observations"),
        StatelessEnvironment(),
        output,
        candidate=factory.candidate,
        candidate_sha256=candidate_sha256,
        source_root=source_root,
    )


def read_domain(
    root: Path,
    loaded: LoadedManifest,
    adapter: DomainAdapter,
    *,
    evidence_sha256: str,
    candidate_sha256: str,
) -> VerifiedEvidence:
    verified = read_evidence(
        root, loaded, evidence_sha256=evidence_sha256, candidate_sha256=candidate_sha256
    )
    verify_runtime(adapter, verified.manifest.candidate)
    if verified.manifest.origin != "mock":
        raise ValueError("partial domain reader accepts only mock preparation evidence")
    verify_observations(root, loaded, adapter, verified.batch)
    return verified


def verify_observations(
    root: Path, loaded: LoadedManifest, adapter: DomainAdapter, batch: BatchReport
) -> None:
    directory = root / "observations"
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("observation directory missing or invalid")
    expected = set()
    for row in batch.rows:
        if row.report is None:
            raise ValueError("domain report missing")
        context = row.task.context
        name = pin(context) + ".json"
        expected.add(name)
        path = directory / name
        if path.is_symlink():
            raise ValueError("observation symlink rejected")
        raw = path.read_bytes()
        saved = SavedObservation.model_validate_json(raw)
        if (
            saved.canonical_json().encode() != raw
            or row.report.report.result != adapter.result(context, saved.payload)
            or row.report.report.scores
            != scores(adapter, loaded.entry(context.case_id).case, context, saved)
        ):
            raise ValueError("domain observation differs from sealed result/scores")
    if {p.name for p in directory.iterdir()} != expected or any(
        not p.is_file() or p.is_symlink() for p in directory.iterdir()
    ):
        raise ValueError("unexpected or missing domain observations")


@dataclass(frozen=True)
class BaselineDomainAgent:
    adapter: DomainAdapter
    slot: Slot

    def run(self, context: RunContext, input: AgentInput, gateway: ModelGateway) -> AgentResult:
        if input.observations or self.slot.observation is not None:
            raise ValueError("baseline requires closed input and a new observation slot")
        self.slot.observation = SavedObservation(
            context_sha256=pin(context), payload=self.adapter.baseline(context, input)
        )
        return self.adapter.result(context, self.slot.observation.payload)


@dataclass(frozen=True)
class DomainBaselineFactory:
    candidate: CandidateSpec
    loaded: LoadedManifest
    adapter: DomainAdapter
    root: Path

    @property
    def algorithm(self) -> str:
        return self.adapter.baseline_algorithm

    def validate(self) -> None:
        verify_runtime(self.adapter, self.candidate)
        if self.candidate.prompt_sha256 != sha256(self.algorithm.encode()):
            raise ValueError("baseline algorithm differs from frozen configuration")
        for entry in self.loaded.manifest.entries:
            self.adapter.validate_case(entry.case)
            if entry.scorer_id != self.adapter.scorer_id:
                raise ValueError("baseline domain scorer identity differs")

    def build(self, context: RunContext, state: StateLease) -> TrialComponents:
        if (
            context.agent_id != self.adapter.agent_id
            or state.fixture != FIXTURE
            or state.access is not None
        ):
            raise ValueError("baseline domain scope/fixture differs")
        slot = Slot()
        registry = ScorerRegistry()
        registry.register(
            ScorerSpec(
                scorer_id=self.adapter.scorer_id,
                version=self.adapter.version,
                compatible=tuple(
                    ScorerCompatibility(snapshot_ref=s, policy_version=p)
                    for s, p in sorted(
                        {
                            (e.case.snapshot_ref, e.case.policy_version)
                            for e in self.loaded.manifest.entries
                        }
                    )
                ),
            ),
            DomainScorer(self.adapter, context, slot, self.root),
        )
        return TrialComponents(BaselineDomainAgent(self.adapter, slot), DenyModels(), registry)


def record_domain_baseline(
    schedule: TrialSchedule,
    loaded: LoadedManifest,
    factory: DomainBaselineFactory,
    output: Path,
    *,
    candidate_sha256: str,
    source_root: Path,
) -> BaselineManifest:
    if loaded.pin != factory.loaded.pin:
        raise ValueError("baseline manifest differs from factory")
    return record_baseline(
        schedule,
        loaded,
        replace(factory, root=output / "observations"),
        StatelessEnvironment(),
        output,
        candidate_sha256=candidate_sha256,
        source_root=source_root,
    )


def read_domain_baseline(
    root: Path,
    loaded: LoadedManifest,
    adapter: DomainAdapter,
    *,
    evidence_sha256: str,
    candidate_sha256: str,
) -> VerifiedBaseline:
    verified = read_baseline(
        root, loaded, evidence_sha256=evidence_sha256, candidate_sha256=candidate_sha256
    )
    verify_runtime(adapter, verified.manifest.candidate)
    if (
        verified.manifest.algorithm != adapter.baseline_algorithm
        or verified.manifest.candidate.prompt_sha256 != sha256(adapter.baseline_algorithm.encode())
    ):
        raise ValueError("baseline algorithm/configuration differs from executing adapter")
    verify_observations(root, loaded, adapter, verified.batch)
    return verified
