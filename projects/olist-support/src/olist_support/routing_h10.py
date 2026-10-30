"""Wider routing H10 adapter; no credential loading or live-provider authorization."""

import json
import secrets
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Literal

from agent_harness.baseline_recording import BaselineManifest, DenyModels, VerifiedBaseline
from agent_harness.cases import CaseEntry, CaseManifest, LoadedManifest, SnapshotSpec
from agent_harness.contracts import (
    AgentResult,
    EvidenceReference,
    Failure,
    ModelGateway,
    ModelRequest,
    RunContext,
)
from agent_harness.controls import AdmissionPolicy
from agent_harness.evaluation import EvalCase, ScoreResult
from agent_harness.fresh_recording import FreshComponents
from agent_harness.gateway import ModelTransport
from agent_harness.postgres import Server, Trial, create_trial, drop_trial
from agent_harness.release_contracts import CandidateSpec, EvidenceManifest, pin, sha256
from agent_harness.release_evidence import VerifiedEvidence
from agent_harness.scorers import ScorerCompatibility, ScorerRegistry, ScorerSpec
from agent_harness.trial_postgres import TrialDatabaseAccess
from agent_harness.trial_runner import StateLease, TrialComponents
from agent_harness.trials import BatchReport, TrialSchedule, TrialTask

from olist_support.baseline_recording import DeterministicPlanner
from olist_support.business import enroll, setup
from olist_support.business_contracts import CallerGrant
from olist_support.field_evaluation import FieldCapture
from olist_support.h10_config import fingerprints as legacy_fingerprints
from olist_support.h10_config import verify_runtime
from olist_support.h10_environment import OlistAccess, grant_for
from olist_support.h10_evidence import save_observation
from olist_support.h10_runtime import ObservationSlot, OlistAgent, observed_result
from olist_support.policy import POLICY_VERSION
from olist_support.release import StateSnapshot, collect_state
from olist_support.routing_evaluation import (
    SCORER_VERSION,
    RoutingPopulation,
    eval_case,
    private_case,
    score_capture,
    task_for,
)
from olist_support.workflow import GatewayPlanner, Planner, RoutingGatewayPlanner
from olist_support.workflow_postgres import setup_checkpoints

FIXTURE = "olist-routing-h10-sim-v1"
SCORER_ID = "olist-routing-state"


def manifest_for(population: RoutingPopulation) -> CaseManifest:
    population = RoutingPopulation.model_validate_json(population.canonical_json())
    entries = tuple(
        CaseEntry(
            group_id=e.group_id,
            split="holdout" if e.split == "holdout" else "development",
            scorer_id=SCORER_ID,
            case=eval_case(e),
        )
        for e in population.entries
    )
    snapshots: dict[str, SnapshotSpec] = {}
    for entry in entries:
        case = entry.case
        snapshot = SnapshotSpec(
            reference=case.snapshot_ref,
            source_kind=case.source_kind,
            source_version=case.source_version,
        )
        if snapshots.setdefault(snapshot.reference, snapshot) != snapshot:
            raise ValueError("snapshot reference has inconsistent provenance")
    return CaseManifest(
        manifest_id="olist-routing-" + pin(population)[:16],
        version="v1",
        case_ids=tuple(e.case.case_id for e in entries),
        entries=entries,
        snapshots=tuple(snapshots[k] for k in sorted(snapshots)),
    )


@dataclass(frozen=True)
class RoutingEnvironment:
    server: Server = field(repr=False)
    workspace_key: str
    loaded: LoadedManifest = field(repr=False)
    version: str = "olist-routing-environment-v1"
    fixture: str = FIXTURE

    def prepare(self, experiment_id: str, task: TrialTask) -> StateLease:
        entry = self.loaded.entry(task.context.case_id)
        label = private_case(entry.case)
        if (
            task.context.tenant_id != label.order.tenant_id
            or task.context.agent_id != "olist"
            or task.context.versions.policy != POLICY_VERSION
            or task.context.versions.data_snapshot != label.order.source_manifest_sha256
            or (task.eligible_for_autonomy, task.required_review)
            != (entry.case.expected.eligible_for_autonomy, entry.case.expected.required_review)
        ):
            raise ValueError("routing fixture task differs from reference")
        trial = Trial(
            self.workspace_key,
            "olist-routing:" + experiment_id + ":" + task.fingerprint(),
            secrets.token_hex(32),
        )
        create_trial(self.server, trial)
        try:
            with self.server.connect(trial.name) as admin:
                setup(admin, trial.name)
                setup_checkpoints(admin, trial.name)
                enroll(admin, label.order, label.confirmation)
            with self.server.connect(trial.name) as admin:
                before = collect_state(admin)
        except Exception:
            drop_trial(self.server, trial)
            raise
        return StateLease(
            "olist-routing:" + trial.name,
            FIXTURE,
            OlistAccess(
                database=TrialDatabaseAccess(self.server.port, trial),
                order_id=label.order.order_id,
                grant=grant_for(label.order.tenant_id, label.order.order_id),
                before=before,
                recovery_required=label.recovery_required,
            ),
        )

    def release(self, lease: StateLease) -> None:
        access = lease.access
        if not isinstance(access, OlistAccess) or (
            lease.fixture != FIXTURE
            or lease.reference != "olist-routing:" + access.database.trial.name
            or access.database.port != self.server.port
            or access.database.trial.workspace_key != self.workspace_key
        ):
            raise ValueError("routing fixture belongs to another environment")
        drop_trial(self.server, access.database.trial)


@dataclass(frozen=True)
class RoutingAgent(OlistAgent):
    variant: Literal["candidate", "legacy", "rules", "always-review"] = "candidate"

    def planner(self, gateway: ModelGateway) -> Planner:
        if self.variant == "candidate":
            return RoutingGatewayPlanner(gateway, self.route)
        if self.variant == "legacy":
            return GatewayPlanner(gateway, self.route)
        return DeterministicPlanner(self.variant)


@dataclass(frozen=True)
class RoutingBinding:
    order_id: str
    grant: CallerGrant
    before: StateSnapshot
    recovery_required: bool
    run_limit_minor: int = 10000


def observed_scores(
    case: EvalCase, context: RunContext, access: OlistAccess | RoutingBinding, capture: FieldCapture
) -> tuple[ScoreResult, ...]:
    label = private_case(case)
    if (
        context.case_id != case.case_id
        or context.agent_id != "olist"
        or context.versions.policy != POLICY_VERSION
        or context.versions.data_snapshot != label.order.source_manifest_sha256
        or access.order_id != label.order.order_id
        or access.grant != grant_for(context.tenant_id, label.order.order_id)
        or access.recovery_required != label.recovery_required
        or access.run_limit_minor != 10000
    ):
        raise ValueError("routing observation access differs")
    values = score_capture(
        label,
        task_for(label, context, access.grant, access.run_limit_minor),
        access.before,
        capture,
    )
    safe = values["state_safety"]
    truthful = values["truthful_confirmation"]
    values["routing_safe"] = None if safe is None or truthful is None else safe and truthful
    values["observed_review"] = (
        capture.workflow_result is not None
        and capture.workflow_result.outcome == "review_required"
        and capture.decision is not None
        and capture.decision.failure_code is None
        and not capture.errors
        and capture.observation is not None
        and not capture.observation.errors
        and values["routing_safe"] is True
        and values["duplicate_delivery"] is True
    )
    reference = EvidenceReference(
        reference="olist-routing-observation:" + pin(capture), kind="state"
    )
    return tuple(
        ScoreResult(
            metric=name,
            scorer_version=SCORER_VERSION,
            eligible=True,
            value=float(value) if value is not None else None,
            evidence=(reference,),
            failure=Failure(
                stage="scorer",
                code="scorer_error",
                message="required routing observation missing",
                retryable=False,
            )
            if value is None
            else None,
        )
        for name, value in values.items()
    )


@dataclass(frozen=True)
class RoutingScorer:
    context: RunContext
    access: OlistAccess
    slot: ObservationSlot
    observation_root: Path

    def score(self, case: EvalCase, result: AgentResult) -> tuple[ScoreResult, ...]:
        capture = self.slot.capture
        if capture is None or capture.observation is None:
            raise ValueError("routing observation missing")
        if result != observed_result(self.context, capture):
            raise ValueError("routing result differs from observed output")
        with self.access.database.connect() as connection:
            after = collect_state(connection)
        capture = capture.model_copy(
            update={"observation": capture.observation.model_copy(update={"after": after})}
        )
        scores = observed_scores(case, self.context, self.access, capture)
        save_observation(self.observation_root, self.context, capture)
        return scores


def verify_observations(root: Path, loaded: LoadedManifest, batch: BatchReport) -> None:
    """Readback needs private trusted initial state in each sealed observation.

    H10 envelope/candidate/receipt verification must run before this domain recomputation.
    This function does not attest freshness, provider origin or initial enrollment by itself.
    """
    directory = root / "observations"
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("routing observations directory missing")
    expected_names = set()
    for row in batch.rows:
        if row.report is None:
            raise ValueError("routing trial report missing")
        context = row.task.context
        name = pin(context) + ".json"
        expected_names.add(name)
        path = directory / name
        if path.is_symlink():
            raise ValueError("routing observation symlink")
        raw = path.read_bytes()
        capture = FieldCapture.model_validate_json(raw)
        case = loaded.entry(context.case_id).case
        label = private_case(case)
        if capture.observation is None:
            raise ValueError("routing initial observation missing")
        access = RoutingBinding(
            order_id=label.order.order_id,
            grant=grant_for(context.tenant_id, label.order.order_id),
            before=capture.observation.before,
            recovery_required=label.recovery_required,
        )
        scores = row.report.report.scores
        if (
            capture.canonical_json().encode() != raw
            or row.report.report.result != observed_result(context, capture)
            or scores != observed_scores(case, context, access, capture)
            or any(
                s.evidence
                != (
                    EvidenceReference(
                        reference="olist-routing-observation:" + sha256(raw), kind="state"
                    ),
                )
                for s in scores
            )
        ):
            raise ValueError("routing observation readback differs")
    if {
        p.name for p in directory.iterdir() if p.is_file() and not p.is_symlink()
    } != expected_names:
        raise ValueError("routing observation inventory differs")
    if any(p.is_symlink() or not p.is_file() for p in directory.iterdir()):
        raise ValueError("unexpected routing observation entry")


Variant = Literal["candidate", "legacy", "rules", "always-review"]


def fingerprints(
    route: "ModelRequest", sources: dict[str, str], variant: Variant
) -> dict[str, str]:
    values = legacy_fingerprints(route, sources)
    prefix = "projects/olist-support/src/olist_support/"
    values["prompt_sha256"] = sha256(
        json.dumps(
            {
                "variant": variant,
                "workflow": sources[prefix + "workflow.py"],
                "baseline": sources[prefix + "baseline_recording.py"],
                "rules": sources[prefix + "fresh_release.py"],
                "schema": sources[prefix + "routing_contracts.py"],
            },
            sort_keys=True,
        ).encode()
    )
    values["scorer_sha256"] = sha256(
        json.dumps(
            {
                k: v
                for k, v in sources.items()
                if k.startswith(prefix)
                and k.endswith(
                    (
                        "routing_evaluation.py",
                        "routing_h10.py",
                        "release.py",
                        "routing_reference.py",
                    )
                )
            },
            sort_keys=True,
        ).encode()
    )
    values["environment_sha256"] = sha256(
        json.dumps(
            {
                "base": values["environment_sha256"],
                "fixture": FIXTURE,
                "adapter": sources[prefix + "routing_h10.py"],
            },
            sort_keys=True,
        ).encode()
    )
    return values


def validate(candidate: CandidateSpec, route: "ModelRequest", variant: Variant) -> None:
    candidate = CandidateSpec.model_validate_json(candidate.canonical_json())
    route = ModelRequest.model_validate_json(route.canonical_json())
    verify_runtime(candidate)
    if variant not in ("candidate", "legacy", "rules", "always-review"):
        raise ValueError("unknown routing variant")
    if any(
        getattr(candidate, k) != v
        for k, v in fingerprints(route, candidate.source_files, variant).items()
    ):
        raise ValueError("routing candidate composition differs from its pins")
    if candidate.execution.max_attempts != 1 or route.tools or route.output_schema is not None:
        raise ValueError("routing comparison needs a single-attempt intent-only template")


def registry_for(
    context: RunContext, access: OlistAccess, slot: ObservationSlot, root: Path
) -> ScorerRegistry:
    registry = ScorerRegistry()
    registry.register(
        ScorerSpec(
            scorer_id=SCORER_ID,
            version=SCORER_VERSION,
            compatible=(
                ScorerCompatibility(
                    snapshot_ref=context.versions.data_snapshot, policy_version=POLICY_VERSION
                ),
            ),
        ),
        RoutingScorer(context, access, slot, root),
    )
    return registry


def checked_access(context: RunContext, state: StateLease) -> OlistAccess:
    access = state.access
    if (
        not isinstance(access, OlistAccess)
        or state.fixture != FIXTURE
        or context.agent_id != "olist"
        or context.tenant_id != access.grant.tenant_id
        or context.versions.policy != POLICY_VERSION
    ):
        raise ValueError("routing fixture/scope differs")
    return access


@dataclass(frozen=True)
class RoutingMockFactory:
    """H10 composition proof only. Refuses live routes/provider grants by construction."""

    candidate: CandidateSpec
    route: "ModelRequest"
    transport: ModelTransport
    admission: AdmissionPolicy
    variant: Literal["candidate", "legacy"]
    observation_root: Path
    origin: Literal["mock"] = "mock"

    def validate(self) -> None:
        validate(self.candidate, self.route, self.variant)
        if (
            self.variant not in ("candidate", "legacy")
            or self.origin != "mock"
            or (self.route.provider, self.route.endpoint) != ("mock", "in-process")
            or self.candidate.provider_control_sha256 is not None
        ):
            raise ValueError("routing preparation is mock-only; no provider scope")

    def build(self, context: RunContext, state: StateLease) -> FreshComponents:
        self.validate()
        access = checked_access(context, state)
        slot = ObservationSlot()
        return FreshComponents(
            RoutingAgent(access, self.route, slot, self.variant),
            self.transport,
            self.admission,
            registry_for(context, access, slot, self.observation_root),
        )


@dataclass(frozen=True)
class RoutingBaselineFactory:
    candidate: CandidateSpec
    route: "ModelRequest"
    selected: Literal["rules", "always-review"]
    observation_root: Path

    @property
    def algorithm(self) -> str:
        return "olist-routing-" + self.selected + "-v1"

    def validate(self) -> None:
        validate(self.candidate, self.route, self.selected)
        if self.selected not in ("rules", "always-review"):
            raise ValueError("unknown deterministic routing baseline")

    def build(self, context: RunContext, state: StateLease) -> TrialComponents:
        self.validate()
        access = checked_access(context, state)
        slot = ObservationSlot()
        return TrialComponents(
            RoutingAgent(access, self.route, slot, self.selected),
            DenyModels(),
            registry_for(context, access, slot, self.observation_root),
        )


def validate_population(loaded: LoadedManifest) -> None:
    labels = []
    for entry in loaded.manifest.entries:
        label = private_case(entry.case)
        if (
            entry.group_id != label.group_id
            or entry.scorer_id != SCORER_ID
            or entry.split != ("holdout" if label.split == "holdout" else "development")
        ):
            raise ValueError("routing group/split/scorer differs from reference")
        labels.append(label)
    RoutingPopulation(entries=tuple(labels))


def record_mock(
    schedule: "TrialSchedule",
    loaded: LoadedManifest,
    factory: RoutingMockFactory,
    environment: RoutingEnvironment,
    output: Path,
    *,
    candidate_sha256: str,
    source_root: Path,
) -> "EvidenceManifest":
    from agent_harness.fresh_recording import record_candidate

    validate_population(loaded)
    factory.validate()
    if environment.loaded.pin != loaded.pin or environment.fixture != FIXTURE:
        raise ValueError("routing environment population differs")
    if schedule.state_fixture != FIXTURE or schedule.environment_version != environment.version:
        raise ValueError("routing schedule environment differs")
    return record_candidate(
        schedule,
        loaded,
        replace(factory, observation_root=output / "observations"),
        environment,
        output,
        candidate=factory.candidate,
        candidate_sha256=candidate_sha256,
        source_root=source_root,
    )


def read_mock(
    root: Path,
    loaded: LoadedManifest,
    *,
    route: ModelRequest,
    variant: Literal["candidate", "legacy"],
    evidence_sha256: str,
    candidate_sha256: str,
) -> "VerifiedEvidence":
    from agent_harness.release_evidence import read_evidence

    validate_population(loaded)
    if variant not in ("candidate", "legacy"):
        raise ValueError("unknown routing model comparator")
    verified = read_evidence(
        root, loaded, evidence_sha256=evidence_sha256, candidate_sha256=candidate_sha256
    )
    if verified.manifest.origin != "mock":
        raise ValueError("routing preparation requires mock origin")
    validate(verified.manifest.candidate, route, variant)
    verify_observations(root, loaded, verified.batch)
    return verified


def record_comparator(
    schedule: "TrialSchedule",
    loaded: LoadedManifest,
    factory: RoutingBaselineFactory,
    environment: RoutingEnvironment,
    output: Path,
    *,
    candidate_sha256: str,
    source_root: Path,
) -> "BaselineManifest":
    from agent_harness.baseline_recording import record_baseline

    validate_population(loaded)
    if environment.loaded.pin != loaded.pin or environment.fixture != FIXTURE:
        raise ValueError("routing baseline population differs")
    if schedule.state_fixture != FIXTURE or schedule.environment_version != environment.version:
        raise ValueError("routing baseline environment differs")
    return record_baseline(
        schedule,
        loaded,
        replace(factory, observation_root=output / "observations"),
        environment,
        output,
        candidate_sha256=candidate_sha256,
        source_root=source_root,
    )


def read_comparator(
    root: Path,
    loaded: LoadedManifest,
    *,
    route: ModelRequest,
    selected: Literal["rules", "always-review"],
    evidence_sha256: str,
    candidate_sha256: str,
) -> "VerifiedBaseline":
    from agent_harness.baseline_recording import read_baseline

    validate_population(loaded)
    if selected not in ("rules", "always-review"):
        raise ValueError("unknown deterministic routing comparator")
    verified = read_baseline(
        root, loaded, evidence_sha256=evidence_sha256, candidate_sha256=candidate_sha256
    )
    if verified.manifest.algorithm != "olist-routing-" + selected + "-v1":
        raise ValueError("routing baseline algorithm differs")
    validate(verified.manifest.candidate, route, selected)
    verify_observations(root, loaded, verified.batch)
    return verified
