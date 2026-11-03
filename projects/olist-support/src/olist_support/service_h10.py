"""H10 recording of the actual customer-confirmed service, mock/zero-call only.

No credentials, live dispatcher or allowance amendments. Historical routing recordings
cannot be read as this candidate. Source/reference qualification remains a separate gate.
"""

import json
import secrets
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Literal, cast, get_args

from agent_harness.baseline_recording import BaselineManifest, DenyModels, VerifiedBaseline
from agent_harness.cases import CaseEntry, CaseManifest, LoadedManifest, SnapshotSpec
from agent_harness.contracts import (
    AgentInput,
    AgentResult,
    EvidenceReference,
    Failure,
    FailureCode,
    ModelGateway,
    ModelRequest,
    RunContext,
)
from agent_harness.controls import AdmissionPolicy
from agent_harness.evaluation import EvalCase, ExpectedResult, ScoreResult
from agent_harness.fresh_recording import FreshComponents
from agent_harness.gateway import ModelTransport
from agent_harness.postgres import Server, Trial, create_trial, drop_trial
from agent_harness.release_contracts import CandidateSpec, EvidenceManifest, pin, sha256
from agent_harness.release_evidence import VerifiedEvidence
from agent_harness.scorers import ScorerCompatibility, ScorerRegistry, ScorerSpec
from agent_harness.trial_postgres import TrialDatabaseAccess
from agent_harness.trial_runner import StateLease, TrialComponents
from agent_harness.trials import BatchReport, TrialRow, TrialSchedule, TrialTask, _write_exclusive

from olist_support.baseline_recording import DeterministicPlanner
from olist_support.business import enroll, setup
from olist_support.business_contracts import BusinessReview
from olist_support.console_auth import provision, setup_console
from olist_support.console_cases import CaseStore
from olist_support.console_contracts import Decision, Principal, Submission
from olist_support.customer_intent import Confirmation, CustomerIntentStore
from olist_support.fresh_execution import InjectedCommitInterruption, NoSecondDispatch
from olist_support.h10_config import verify_runtime
from olist_support.policy import POLICY_VERSION
from olist_support.routing_contracts import RoutingPlan
from olist_support.routing_evaluation import RoutingPopulation
from olist_support.routing_h10 import fingerprints as routing_fingerprints
from olist_support.service_evaluation import (
    SCORER_VERSION,
    ServiceCapture,
    ServiceScenario,
    ServiceScript,
    score_service,
)
from olist_support.service_observation import ServiceSnapshot, collect_service_state
from olist_support.workflow import IntentDecision, Planner, RoutingGatewayPlanner, WorkflowRequest
from olist_support.workflow_postgres import setup_checkpoints

FIXTURE = "olist-confirmed-service-h10-sim-v1"
ENVIRONMENT = "olist-confirmed-service-environment-v1"
SCORER_ID = "olist-confirmed-service-state"
Variant = Literal["candidate", "rules", "always-review"]


def eval_case(scenario: ServiceScenario) -> EvalCase:
    scenario = ServiceScenario.model_validate_json(scenario.canonical_json())
    label = scenario.reference
    status = label.expected.outcome == "status" and not scenario.script.require_review
    return EvalCase(
        case_id=scenario.case_id,
        input=AgentInput(request=label.reference.text),
        snapshot_ref=label.order.source_manifest_sha256,
        source_kind=label.source_kind,
        source_version=FIXTURE,
        policy_version=POLICY_VERSION,
        scorer_version=SCORER_VERSION,
        expected=ExpectedResult(
            outcome="completed" if scenario.expects_commit or status else "review_required",
            output=None,
            eligible_for_autonomy=scenario.expects_commit,
            required_review=not scenario.expects_commit and not status,
            allowed_decisions=(
                "refund" if scenario.expects_commit else "status" if status else "review",
            ),
            expected_state_changes={
                "amount_minor": label.expected.refund_minor if scenario.expects_commit else None
            },
        ),
        hidden_state={"service_scenario": scenario.model_dump(mode="json")},
        risk="simulation_only",
        slices=(
            label.reference.expected.intent,
            label.split,
            "scripted_" + scenario.script.customer,
        ),
    )


def private_scenario(case: EvalCase) -> ServiceScenario:
    if set(case.hidden_state) != {"service_scenario"}:
        raise ValueError("service reference metadata differs")
    scenario = ServiceScenario.model_validate_json(
        json.dumps(case.hidden_state["service_scenario"])
    )
    if eval_case(scenario) != case:
        raise ValueError("service case differs from its reference and actor script")
    return scenario


def manifest_for(scenarios: tuple[ServiceScenario, ...]) -> CaseManifest:
    labels = {s.reference.case_id: s.reference for s in scenarios}
    if any(labels[s.reference.case_id] != s.reference for s in scenarios):
        raise ValueError("inconsistent copies of the same source reference")
    RoutingPopulation(entries=tuple(labels.values()))
    cases = tuple(eval_case(s) for s in scenarios)
    if len({c.case_id for c in cases}) != len(cases):
        raise ValueError("duplicate service scenario")
    snapshots: dict[str, SnapshotSpec] = {}
    for case in cases:
        snapshot = SnapshotSpec(
            reference=case.snapshot_ref,
            source_kind=case.source_kind,
            source_version=case.source_version,
        )
        if snapshots.setdefault(case.snapshot_ref, snapshot) != snapshot:
            raise ValueError("service snapshot provenance differs")
    return CaseManifest(
        manifest_id="olist-confirmed-" + sha256("".join(pin(s) for s in scenarios).encode())[:16],
        version="v1",
        case_ids=tuple(c.case_id for c in cases),
        entries=tuple(
            CaseEntry(
                group_id=s.reference.group_id,
                split="holdout" if s.reference.split == "holdout" else "development",
                scorer_id=SCORER_ID,
                case=c,
            )
            for s, c in zip(scenarios, cases, strict=True)
        ),
        snapshots=tuple(snapshots[k] for k in sorted(snapshots)),
    )


def validate_population(loaded: LoadedManifest) -> None:
    scenarios = tuple(private_scenario(e.case) for e in loaded.manifest.entries)
    if manifest_for(scenarios) != loaded.manifest:
        raise ValueError("service manifest group/split/scorer differs")


@dataclass(frozen=True)
class ServiceAccess:
    database: TrialDatabaseAccess
    order_id: str
    operator: Principal
    reviewer: Principal
    customer: Principal
    event_key: str
    script: ServiceScript
    before: ServiceSnapshot
    recovery_required: bool

    def observe(self) -> ServiceSnapshot:
        with self.database.connect() as connection:
            return collect_service_state(connection)


@dataclass(frozen=True)
class ServiceEnvironment:
    server: Server = field(repr=False)
    workspace_key: str
    loaded: LoadedManifest = field(repr=False)
    version: str = ENVIRONMENT
    fixture: str = FIXTURE

    def prepare(self, experiment_id: str, task: TrialTask) -> StateLease:
        entry = self.loaded.entry(task.context.case_id)
        scenario = private_scenario(entry.case)
        scenario.check_context(task.context)
        if (task.eligible_for_autonomy, task.required_review) != (
            entry.case.expected.eligible_for_autonomy,
            entry.case.expected.required_review,
        ):
            raise ValueError("service task eligibility differs")
        trial = Trial(
            self.workspace_key,
            FIXTURE + ":" + experiment_id + ":" + task.fingerprint(),
            secrets.token_hex(32),
        )
        create_trial(self.server, trial)
        try:
            with self.server.connect(trial.name) as admin:
                setup(admin, trial.name)
                setup_checkpoints(admin, trial.name)
                setup_console(admin, trial.name)
                enroll(admin, scenario.reference.order, scenario.reference.confirmation)
                for role in ("operator", "reviewer", "customer"):
                    provision(admin, scenario.actor(role), secrets.token_urlsafe(32))
            database = TrialDatabaseAccess(self.server.port, trial)
            with database.connect() as connection:
                before = collect_service_state(connection)
        except Exception:
            drop_trial(self.server, trial)
            raise
        return StateLease(
            FIXTURE + ":" + trial.name,
            FIXTURE,
            ServiceAccess(
                database,
                scenario.reference.order.order_id,
                scenario.actor("operator"),
                scenario.actor("reviewer"),
                scenario.actor("customer"),
                scenario.event_key,
                scenario.script,
                before,
                scenario.reference.recovery_required,
            ),
        )

    def release(self, lease: StateLease) -> None:
        access = lease.access
        if not isinstance(access, ServiceAccess) or (
            lease.fixture != FIXTURE
            or lease.reference != FIXTURE + ":" + access.database.trial.name
            or access.database.port != self.server.port
            or access.database.trial.workspace_key != self.workspace_key
        ):
            raise ValueError("service fixture belongs to another environment")
        drop_trial(self.server, access.database.trial)


@dataclass(frozen=True)
class VersionedBaseline:
    """Represent the existing algorithm in the new schema without improving its heuristics."""

    algorithm: Literal["rules", "always-review"]

    def plan(self, context: RunContext, request: WorkflowRequest) -> IntentDecision:
        decision = DeterministicPlanner(self.algorithm).plan(context, request)
        return decision.model_copy(
            update={
                "plan": RoutingPlan(
                    routing_version="olist-intent-routing-v2",
                    intent=decision.plan.intent,
                    requested_minor=decision.plan.requested_minor,
                )
            }
        )


@dataclass
class ServiceSlot:
    capture: ServiceCapture | None = None


def observed_result(context: RunContext, capture: ServiceCapture) -> AgentResult:
    case = capture.returned
    decision, result = case.intent_decision, case.result
    if decision is None or decision.usage is None or result is None:
        raise ValueError("service decision/result/usage missing")
    failed = decision.failure_code is not None
    review = case.status in ("review_required", "approved", "rejected")
    return AgentResult(
        run_id=context.run_id,
        case_id=context.case_id,
        trial_id=context.trial_id,
        decision="refund" if result.receipt else "review" if review else result.outcome,
        outcome="failed"
        if failed
        else "blocked"
        if capture.errors
        else "review_required"
        if review
        else "completed",
        output=result.message,
        usage=decision.usage,
        review_ref="olist-case:" + case.case_id if review else None,
        state_change_refs=(result.receipt.ledger_id,) if result.receipt else (),
        failure=Failure(
            stage="agent" if decision.failure_code == "invalid_intent_response" else "model",
            code=cast(FailureCode, decision.failure_code)
            if decision.failure_code in get_args(FailureCode)
            else "invalid_response",
            message="intent attempt failed",
            retryable=False,
        )
        if failed
        else None,
    )


@dataclass(frozen=True)
class ServiceAgent:
    access: ServiceAccess
    route: ModelRequest
    slot: ServiceSlot
    variant: Variant = "candidate"

    def run(self, context: RunContext, input: AgentInput, gateway: ModelGateway) -> AgentResult:
        if input.observations or self.slot.capture is not None:
            raise ValueError("service recording requires text-only input and a fresh slot")
        access = self.access
        planner: Planner = (
            RoutingGatewayPlanner(gateway, self.route)
            if self.variant == "candidate"
            else VersionedBaseline(self.variant)
        )
        cases = CaseStore(access.database.connect, planner=planner)
        request = Submission(
            event_key=access.event_key,
            order_id=access.order_id,
            text=input.request,
            intent="refund",
            require_review=access.script.require_review,
        )
        first = cases.submit(access.operator, request, context, run_limit_minor=10000)
        proposed = access.observe()
        if first.case_id != context.case_id or first.context != context:
            raise ValueError("service rewrote the frozen model context")
        # A second submission must recover the saved decision without another model call.
        reader = CaseStore(access.database.connect, planner=NoSecondDispatch())
        if reader.submit(access.operator, request, context, run_limit_minor=10000) != first:
            raise ValueError("duplicate service submission differs")
        current = first
        if access.script.reviewer != "none" and current.status == "review_required":
            if current.command is not None or access.script.reviewer == "reject":
                current = reader.decide(
                    access.reviewer,
                    current.case_id,
                    Decision(
                        decision=access.script.reviewer,
                        expected_version=current.version,
                        action_digest=current.action_digest,
                        rationale="Scripted evaluator decision.",
                    ),
                )
        interrupted = None
        payload = None
        intents = CustomerIntentStore(CaseStore(access.database.connect))
        if (
            access.script.customer == "confirm"
            and current.command is not None
            and current.command.amount_minor == access.script.amount_minor
            and (
                current.status == "approved"
                or current.status == "review_required"
                and not access.script.require_review
            )
        ):
            offer = intents.issue(access.customer, current.case_id)
            payload = Confirmation(
                challenge=offer["challenge"],
                action="refund",
                amount_minor=access.script.amount_minor,
                unit="SIM",
            )
            intents.confirm(access.customer, current.case_id, payload)

            def fault(point: str) -> None:
                if point == "after_commit":
                    raise InjectedCommitInterruption("controlled service response loss")

            try:
                current = intents.execute(
                    access.customer,
                    current.case_id,
                    payload,
                    run_limit_minor=10000,
                    fault=fault if access.recovery_required else None,
                )
            except InjectedCommitInterruption:
                interrupted = access.observe()
                # A new service composition reads the committed case/receipt; no model.
                intents = CustomerIntentStore(CaseStore(access.database.connect))
                current = intents.execute(
                    access.customer, current.case_id, payload, run_limit_minor=10000
                )
            except BusinessReview:
                # A blocked transaction stays an observed non-completion, never a retry.
                current = reader.detail(access.operator, current.case_id)[0]
        final = access.observe()
        duplicate = (
            intents.execute(access.customer, current.case_id, payload, run_limit_minor=10000)
            if payload is not None and current.status == "committed"
            else reader.submit(access.operator, request, context, run_limit_minor=10000)
        )
        redelivery = access.observe()
        self.slot.capture = ServiceCapture(
            context=context,
            before=access.before,
            proposed=proposed,
            final=final,
            returned=current,
            redelivery=redelivery,
            redelivered=duplicate,
            interrupted=interrupted,
        )
        return observed_result(context, self.slot.capture)


def observed_scores(
    scenario: ServiceScenario, context: RunContext, capture: ServiceCapture
) -> tuple[ScoreResult, ...]:
    reference = EvidenceReference(
        reference="olist-service-observation:" + pin(capture), kind="state"
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
                message="required service observation missing",
                retryable=False,
            )
            if value is None
            else None,
        )
        for name, value in score_service(scenario, context, capture).items()
    )


@dataclass(frozen=True)
class ServiceScorer:
    context: RunContext
    access: ServiceAccess
    slot: ServiceSlot
    root: Path

    def score(self, case: EvalCase, result: AgentResult) -> tuple[ScoreResult, ...]:
        scenario = private_scenario(case)
        capture = self.slot.capture
        if capture is None or capture.before != self.access.before:
            raise ValueError("trusted service initial observation missing")
        if result != observed_result(self.context, capture):
            raise ValueError("service result differs from observed output")
        # Independent of the agent's claimed state; read again after it has returned.
        capture = capture.model_copy(update={"final": self.access.observe()})
        scores = observed_scores(scenario, self.context, capture)
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        if self.root.is_symlink() or not self.root.is_dir():
            raise ValueError("service observation root must be a private directory")
        _write_exclusive(self.root / (pin(self.context) + ".json"), capture.canonical_json())
        return scores


def verify_row(root: Path, loaded: LoadedManifest, row: TrialRow) -> tuple[ScoreResult, ...]:
    if row.report is None or row.errors:
        raise ValueError("service trial report missing or failed")
    context = row.task.context
    path = root / (pin(context) + ".json")
    if root.is_symlink() or not root.is_dir() or path.is_symlink():
        raise ValueError("service observation directory/file differs")
    raw = path.read_bytes()
    capture = ServiceCapture.model_validate_json(raw)
    scores = observed_scores(private_scenario(loaded.entry(context.case_id).case), context, capture)
    if (
        raw != capture.canonical_json().encode()
        or row.report.report.result != observed_result(context, capture)
        or row.report.report.scores != scores
    ):
        raise ValueError("service observation readback differs")
    return scores


def verify_observations(root: Path, loaded: LoadedManifest, batch: BatchReport) -> None:
    directory = root / "observations"
    for row in batch.rows:
        verify_row(directory, loaded, row)
    expected = {pin(r.task.context) + ".json" for r in batch.rows}
    if {p.name for p in directory.iterdir()} != expected or any(
        p.is_symlink() or not p.is_file() for p in directory.iterdir()
    ):
        raise ValueError("service observation inventory differs")


def fingerprints(route: ModelRequest, sources: dict[str, str], variant: Variant) -> dict[str, str]:
    values = routing_fingerprints(route, sources, variant)
    prefix = "projects/olist-support/src/olist_support/"
    binding = json.dumps(
        {
            "fixture": FIXTURE,
            "variant": variant,
            "sources": {k: v for k, v in sources.items() if k.startswith(prefix)},
        },
        sort_keys=True,
    ).encode()
    # Bind the complete service, schema, observer, actor driver and scorer composition.
    for key in ("prompt_sha256", "tools_sha256", "scorer_sha256", "environment_sha256"):
        values[key] = sha256(values[key].encode() + binding)
    return values


def validate(candidate: CandidateSpec, route: ModelRequest, variant: Variant) -> None:
    verify_runtime(candidate)
    if variant not in ("candidate", "rules", "always-review") or any(
        getattr(candidate, k) != v
        for k, v in fingerprints(route, candidate.source_files, variant).items()
    ):
        raise ValueError("service composition differs from pinned behavior")
    if candidate.execution.max_attempts != 1 or route.tools or route.output_schema is not None:
        raise ValueError("service recording requires a single-attempt text-only route")


def checked_access(context: RunContext, state: StateLease) -> ServiceAccess:
    access = state.access
    if not isinstance(access, ServiceAccess) or state.fixture != FIXTURE:
        raise ValueError("customer-confirmed service fixture required")
    # Only fixture inputs reach the agent; evaluator reference labels remain in the manifest.
    from olist_support.business import identity_hash
    from olist_support.console_cases import MODEL_SERVICE_AGENT, MODEL_SERVICE_CANDIDATE

    if (
        context.case_id
        != identity_hash(
            "console-case", access.operator.tenant_id, access.operator.actor_id, access.event_key
        )
        or context.business_event_id != context.case_id
        or context.tenant_id != access.operator.tenant_id
        or context.agent_id != MODEL_SERVICE_AGENT
        or context.versions.candidate != MODEL_SERVICE_CANDIDATE
        or context.versions.policy != POLICY_VERSION
    ):
        raise ValueError("service fixture identity differs")
    return access


def registry_for(
    context: RunContext, access: ServiceAccess, slot: ServiceSlot, root: Path
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
        ServiceScorer(context, access, slot, root),
    )
    return registry


@dataclass(frozen=True)
class ServiceMockFactory:
    candidate: CandidateSpec
    route: ModelRequest
    transport: ModelTransport
    admission: AdmissionPolicy
    observation_root: Path
    origin: Literal["mock"] = "mock"

    def validate(self) -> None:
        validate(self.candidate, self.route, "candidate")
        if (
            self.origin != "mock"
            or (self.route.provider, self.route.endpoint) != ("mock", "in-process")
            or self.candidate.provider_control_sha256 is not None
        ):
            raise ValueError("service preparation is mock-only; no live provider scope")

    def build(self, context: RunContext, state: StateLease) -> FreshComponents:
        self.validate()
        access, slot = checked_access(context, state), ServiceSlot()
        return FreshComponents(
            ServiceAgent(access, self.route, slot),
            self.transport,
            self.admission,
            registry_for(context, access, slot, self.observation_root),
        )


@dataclass(frozen=True)
class ServiceBaselineFactory:
    candidate: CandidateSpec
    route: ModelRequest
    selected: Literal["rules", "always-review"]
    observation_root: Path

    @property
    def algorithm(self) -> str:
        return "olist-confirmed-service-" + self.selected + "-v1"

    def validate(self) -> None:
        validate(self.candidate, self.route, self.selected)

    def build(self, context: RunContext, state: StateLease) -> TrialComponents:
        self.validate()
        access, slot = checked_access(context, state), ServiceSlot()
        return TrialComponents(
            ServiceAgent(access, self.route, slot, self.selected),
            DenyModels(),
            registry_for(context, access, slot, self.observation_root),
        )


@dataclass(frozen=True)
class ParentFence:
    """Recompute private readback before another trial; missing/unsafe evidence stops."""

    root: Path
    loaded: LoadedManifest

    def __call__(self, row: TrialRow) -> None:
        scores = verify_row(self.root, self.loaded, row)
        safe = next(s for s in scores if s.metric == "routing_safe")
        if safe.value != 1 or safe.failure is not None:
            raise ValueError("unsafe or unknown service state; recording stopped")


def check_environment(
    schedule: TrialSchedule, loaded: LoadedManifest, environment: ServiceEnvironment
) -> None:
    validate_population(loaded)
    if (
        environment.loaded.pin != loaded.pin
        or schedule.state_fixture != FIXTURE
        or schedule.environment_version != ENVIRONMENT
        or schedule.max_parallel != 1
    ):
        raise ValueError("service recording requires its own sequential environment")


def record_mock(
    schedule: TrialSchedule,
    loaded: LoadedManifest,
    factory: ServiceMockFactory,
    environment: ServiceEnvironment,
    output: Path,
    *,
    candidate_sha256: str,
    source_root: Path,
) -> EvidenceManifest:
    from agent_harness.fresh_recording import record_candidate

    check_environment(schedule, loaded, environment)
    factory.validate()
    root = output / "observations"
    return record_candidate(
        schedule,
        loaded,
        replace(factory, observation_root=root),
        environment,
        output,
        candidate=factory.candidate,
        candidate_sha256=candidate_sha256,
        source_root=source_root,
        after_trial=ParentFence(root, loaded),
    )


def read_mock(
    root: Path,
    loaded: LoadedManifest,
    *,
    route: ModelRequest,
    evidence_sha256: str,
    candidate_sha256: str,
) -> VerifiedEvidence:
    from agent_harness.release_evidence import read_evidence

    validate_population(loaded)
    verified = read_evidence(
        root, loaded, evidence_sha256=evidence_sha256, candidate_sha256=candidate_sha256
    )
    if verified.manifest.origin != "mock":
        raise ValueError("service preparation requires mock origin")
    validate(verified.manifest.candidate, route, "candidate")
    verify_observations(root, loaded, verified.batch)
    return verified


def record_comparator(
    schedule: TrialSchedule,
    loaded: LoadedManifest,
    factory: ServiceBaselineFactory,
    environment: ServiceEnvironment,
    output: Path,
    *,
    candidate_sha256: str,
    source_root: Path,
) -> BaselineManifest:
    from agent_harness.baseline_recording import record_baseline

    check_environment(schedule, loaded, environment)
    root = output / "observations"
    return record_baseline(
        schedule,
        loaded,
        replace(factory, observation_root=root),
        environment,
        output,
        candidate_sha256=candidate_sha256,
        source_root=source_root,
        after_trial=ParentFence(root, loaded),
    )


def read_comparator(
    root: Path,
    loaded: LoadedManifest,
    *,
    route: ModelRequest,
    selected: Literal["rules", "always-review"],
    evidence_sha256: str,
    candidate_sha256: str,
) -> VerifiedBaseline:
    from agent_harness.baseline_recording import read_baseline

    validate_population(loaded)
    verified = read_baseline(
        root, loaded, evidence_sha256=evidence_sha256, candidate_sha256=candidate_sha256
    )
    if verified.manifest.algorithm != "olist-confirmed-service-" + selected + "-v1":
        raise ValueError("service baseline algorithm differs")
    validate(verified.manifest.candidate, route, selected)
    verify_observations(root, loaded, verified.batch)
    return verified
