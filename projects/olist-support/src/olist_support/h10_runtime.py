"""Trusted H10 composition: real workflow, restricted SQL and independent field scores."""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast, get_args

from agent_harness.contracts import (
    AgentInput,
    AgentResult,
    Failure,
    FailureCode,
    ModelGateway,
    ModelRequest,
    RunContext,
)
from agent_harness.controls import AdmissionPolicy
from agent_harness.evaluation import EvalCase, ScoreResult
from agent_harness.fresh_recording import FreshComponents
from agent_harness.gateway import ModelTransport
from agent_harness.release_contracts import CandidateSpec
from agent_harness.scorers import ScorerCompatibility, ScorerRegistry, ScorerSpec
from agent_harness.trial_runner import StateLease

from olist_support.business import BusinessStore, identity_hash
from olist_support.field_evaluation import FieldCapture
from olist_support.fresh_execution import (
    InjectedCommitInterruption,
    NoSecondDispatch,
    ObservedPlanner,
)
from olist_support.fresh_release import RecoveryObservation
from olist_support.h10_environment import FIXTURE, OlistAccess, grant_for
from olist_support.h10_manifest import SCORER_ID, SCORER_VERSION, private_case
from olist_support.policy import POLICY_VERSION
from olist_support.release import Observation, StateSnapshot, collect_state
from olist_support.workflow import GatewayPlanner, Planner, SupportWorkflow, WorkflowRequest
from olist_support.workflow_postgres import saver


@dataclass
class ObservationSlot:
    """Evaluator instrumentation shared only within one owned worker invocation."""

    capture: FieldCapture | None = None


@dataclass(frozen=True)
class OlistAgent:
    access: OlistAccess
    route: ModelRequest
    slot: ObservationSlot

    def planner(self, gateway: ModelGateway) -> Planner:
        return GatewayPlanner(gateway, self.route)

    def state(self) -> StateSnapshot:
        with self.access.database.connect() as connection:
            return collect_state(connection)

    def run(self, context: RunContext, input: AgentInput, gateway: ModelGateway) -> AgentResult:
        if input.observations or self.slot.capture is not None:
            raise ValueError(
                "Olist recording requires text-only input and a fresh observation slot"
            )
        planner = ObservedPlanner(self.planner(gateway))
        connect = self.access.database.connect
        request = WorkflowRequest(order_id=self.access.order_id, text=input.request)
        interrupted = None

        def fault(point: str) -> None:
            if point == "after_commit":
                raise InjectedCommitInterruption("controlled H10 evaluation interruption")

        with saver(connect) as checkpoints:
            try:
                result = SupportWorkflow(BusinessStore(connect), planner).run(
                    context,
                    request,
                    self.access.grant,
                    checkpoints,
                    run_limit_minor=self.access.run_limit_minor,
                    fault=fault if self.access.recovery_required else None,
                )
            except InjectedCommitInterruption:
                interrupted = self.state()
                result = None
        if interrupted is not None:
            with saver(connect) as checkpoints:
                result = SupportWorkflow(BusinessStore(connect), NoSecondDispatch()).run(
                    context.model_copy(update={"run_id": context.run_id + "-resume"}),
                    request,
                    self.access.grant,
                    checkpoints,
                    run_limit_minor=self.access.run_limit_minor,
                )
        if result is None or planner.decision is None or planner.decision.usage is None:
            raise ValueError("Olist workflow did not preserve its actual model attempt")
        first = self.state()
        with saver(connect) as checkpoints:
            duplicate = SupportWorkflow(BusinessStore(connect), NoSecondDispatch()).run(
                context.model_copy(update={"run_id": context.run_id + "-duplicate"}),
                request,
                self.access.grant,
                checkpoints,
                run_limit_minor=self.access.run_limit_minor,
            )
        after = self.state()
        duplicate_ok = duplicate == result and after == first
        errors = []
        if not duplicate_ok:
            errors.append("duplicate_delivery_changed_state_or_result")
        if self.access.recovery_required and interrupted is None:
            errors.append("commit_interruption_not_observed")
        if planner.decision.failure_code is not None:
            errors.append("model_attempt_failed")
        self.slot.capture = FieldCapture(
            case_id=context.case_id,
            trial_id=context.trial_id,
            observation=Observation(
                case_id=context.case_id,
                trial_id=context.trial_id,
                before=self.access.before,
                after=after,
                outcome=result.outcome,
                receipt=result.receipt,
                message=result.message,
                errors=tuple(errors),
            ),
            decision=planner.decision,
            workflow_result=result,
            duplicate_delivery_unchanged=duplicate_ok,
            before_redelivery=first,
            redelivered_result=duplicate,
            recovery_observation=(
                RecoveryObservation(committed=interrupted, resumed=first)
                if interrupted is not None
                else None
            ),
            errors=tuple(errors),
        )
        return observed_result(context, self.slot.capture)


def observed_result(context: RunContext, capture: FieldCapture) -> AgentResult:
    """Bind the shared result to what the workflow actually returned, without labels."""
    result, decision = capture.workflow_result, capture.decision
    if result is None or decision is None or decision.usage is None:
        raise ValueError("Olist observed result/usage is missing")
    failed = decision.failure_code is not None
    review = result.outcome == "review_required" and not capture.errors
    return AgentResult(
        run_id=context.run_id,
        case_id=context.case_id,
        trial_id=context.trial_id,
        decision="refund" if result.receipt else "review" if review else result.outcome,
        outcome=(
            "failed"
            if failed
            else "blocked"
            if capture.errors
            else "review_required"
            if review
            else "completed"
        ),
        output=result.message,
        usage=decision.usage,
        review_ref=(
            "olist-checkpoint:"
            + identity_hash("thread", context.tenant_id, context.business_event_id)
            if review
            else None
        ),
        state_change_refs=(result.receipt.ledger_id,) if result.receipt else (),
        failure=(
            Failure(
                stage="agent" if decision.failure_code == "invalid_intent_response" else "model",
                code=cast(FailureCode, decision.failure_code)
                if decision.failure_code in get_args(FailureCode)
                else "invalid_response",
                message="intent attempt failed",
                retryable=False,
            )
            if failed
            else None
        ),
    )


@dataclass(frozen=True)
class OlistScorer:
    context: RunContext
    access: OlistAccess
    slot: ObservationSlot
    observation_root: Path

    def score(self, case: EvalCase, result: AgentResult) -> tuple[ScoreResult, ...]:
        from olist_support.h10_evidence import observed_scores, save_observation

        label, recovery = private_case(case)
        capture = self.slot.capture
        if capture is None or capture.workflow_result is None or capture.observation is None:
            raise ValueError("Olist independent observation is missing")
        if (
            (result.run_id, result.case_id, result.trial_id)
            != (self.context.run_id, case.case_id, self.context.trial_id)
            or label.input.order.order_id != self.access.order_id
            or recovery != self.access.recovery_required
            or self.access.grant != grant_for(self.context.tenant_id, self.access.order_id)
            or self.access.run_limit_minor != 10000
            or capture.observation.before != self.access.before
            or result != observed_result(self.context, capture)
        ):
            raise ValueError("Olist result differs from worker observation/identity")
        # Read independently after the agent returns; never trust a claimed ledger delta.
        with self.access.database.connect() as connection:
            after = collect_state(connection)
        capture = capture.model_copy(
            update={"observation": capture.observation.model_copy(update={"after": after})}
        )
        scores = observed_scores(case, self.context, capture)
        save_observation(self.observation_root, self.context, capture)
        return scores


@dataclass(frozen=True)
class OlistFreshFactory:
    """Explicit trusted transport/admission; never imports credentials or a live SDK."""

    candidate: CandidateSpec
    route: ModelRequest
    transport: ModelTransport
    admission: AdmissionPolicy
    origin: Literal["provider", "mock"]
    observation_root: Path | None = None

    def validate(self) -> None:
        from olist_support.h10_config import validate_composition

        validate_composition(self.candidate, self.route, self.transport, self.origin)
        if self.origin == "provider":
            from agent_harness.admission import GeminiFreeAdmission

            if type(self.admission) is not GeminiFreeAdmission or (
                self.candidate.recording_budget.max_cost != 0
                or self.candidate.recording_budget.cost_currency != "USD"
            ):
                raise ValueError("provider recording requires the reviewed Gemini Free admission")

    def build(self, context: RunContext, state: StateLease) -> FreshComponents:
        self.validate()
        if (
            not isinstance(state.access, OlistAccess)
            or state.fixture != FIXTURE
            or context.agent_id != "olist"
            or context.tenant_id != state.access.grant.tenant_id
            or context.versions.policy != POLICY_VERSION
            or self.candidate.execution.max_attempts != 1
            or self.observation_root is None
        ):
            raise ValueError("Olist composition requires its restricted single-attempt fixture")
        slot = ObservationSlot()
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
            OlistScorer(context, state.access, slot, self.observation_root),
        )
        return FreshComponents(
            OlistAgent(state.access, self.route, slot), self.transport, self.admission, registry
        )
