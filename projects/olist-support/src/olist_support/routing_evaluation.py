"""Wider, evaluator-only routing labels and independent workflow/state scores."""

import json
from typing import Annotated, Literal, Self

from agent_harness.contracts import AgentInput, Contract, RunContext
from agent_harness.evaluation import EvalCase, ExpectedResult
from pydantic import Field, model_validator

from olist_support.business import sha
from olist_support.business_contracts import CallerGrant, RefundCommand
from olist_support.evaluation_oracle import OracleFacts, OracleRequest, evaluate_policy
from olist_support.field_evaluation import FieldCapture
from olist_support.policy import POLICY_VERSION, ScenarioConfirmation
from olist_support.policy_cases import Digest, Split
from olist_support.release import ScheduledTrial, StateSnapshot, expected_state
from olist_support.routing_reference import RoutingReference
from olist_support.views import OrderView

SCORER_VERSION = "olist-routing-state-v1"


class ExpectedWorkflow(Contract):
    outcome: Literal["refunded", "status", "review_required"]
    reason: Annotated[str, Field(min_length=1)]
    refund_minor: Annotated[int, Field(gt=0, le=10000)] | None = None

    @model_validator(mode="after")
    def effect(self) -> Self:
        if (self.outcome == "refunded") != (self.refund_minor is not None):
            raise ValueError("only refunded labels carry a positive SIM effect")
        return self


class RoutingCase(Contract):
    case_id: Digest
    group_id: Digest
    language_family: Annotated[str, Field(min_length=1)]
    split: Split
    source_kind: Literal["hybrid", "synthetic"]
    reference_source_sha256: Digest
    reference: RoutingReference
    order: OrderView
    confirmation: ScenarioConfirmation | None
    expected: ExpectedWorkflow
    recovery_required: bool = False

    @model_validator(mode="after")
    def coherent(self) -> Self:
        intent = self.reference.expected.intent
        outcome = self.expected.outcome
        if (intent == "status") != (outcome == "status"):
            raise ValueError("status references require a status outcome")
        if outcome == "refunded" and intent != "refund":
            raise ValueError("a non-refund reference cannot authorize an expected effect")
        if self.recovery_required and outcome != "refunded":
            raise ValueError("after-commit recovery requires an expected committed refund")
        if self.confirmation and (self.confirmation.tenant_id, self.confirmation.order_id) != (
            self.order.tenant_id,
            self.order.order_id,
        ):
            raise ValueError("confirmation differs from fixture scope")
        if len(self.reference.text) > 8192:
            raise ValueError("reference exceeds workflow text bound")
        if intent in ("refund", "reship"):
            facts = (
                None
                if self.confirmation is None
                else OracleFacts.model_validate(
                    self.confirmation.model_dump(exclude={"provenance"})
                )
            )
            check = evaluate_policy(
                self.order,
                OracleRequest(
                    intent=intent, requested_minor=self.reference.expected.requested_minor
                ),
                facts,
            )
            if (check.action == "propose_full_refund") != (outcome == "refunded") or (
                check.amount_minor != self.expected.refund_minor
            ):
                raise ValueError("expected SIM effect differs from independent policy table")
        return self


class RoutingPopulation(Contract):
    version: Literal["olist-routing-population-v1"] = "olist-routing-population-v1"
    entries: Annotated[tuple[RoutingCase, ...], Field(min_length=1)]
    release_allowed: Literal[False] = False

    @model_validator(mode="after")
    def grouped(self) -> Self:
        ids: set[str] = set()
        groups: dict[str, str] = {}
        families: dict[str, str] = {}
        orders: dict[tuple[str, str], str] = {}
        for entry in self.entries:
            if entry.case_id in ids:
                raise ValueError("duplicate routing case")
            ids.add(entry.case_id)
            if groups.setdefault(entry.group_id, entry.split) != entry.split:
                raise ValueError("source group crosses splits")
            if families.setdefault(entry.language_family, entry.split) != entry.split:
                raise ValueError("language family crosses splits")
            key = (entry.order.tenant_id, entry.order.order_id)
            if orders.setdefault(key, entry.split) != entry.split:
                raise ValueError("fixture order crosses splits")
        return self


def eval_case(label: RoutingCase) -> EvalCase:
    label = RoutingCase.model_validate_json(label.canonical_json())
    outcome = label.expected.outcome
    return EvalCase(
        case_id=label.case_id,
        input=AgentInput(request=label.reference.text),
        snapshot_ref=label.order.source_manifest_sha256,
        source_kind=label.source_kind,
        source_version="olist-routing-population-v1",
        policy_version=POLICY_VERSION,
        scorer_version=SCORER_VERSION,
        expected=ExpectedResult(
            outcome="review_required" if outcome == "review_required" else "completed",
            output=None,
            eligible_for_autonomy=outcome == "refunded",
            required_review=outcome == "review_required",
            allowed_decisions=(
                "refund"
                if outcome == "refunded"
                else "review"
                if outcome == "review_required"
                else "status",
            ),
            expected_state_changes={"amount_minor": label.expected.refund_minor},
        ),
        hidden_state={"routing_case": label.model_dump(mode="json")},
        risk="simulation_only",
        slices=(label.reference.expected.intent, label.split),
    )


def private_case(case: EvalCase) -> RoutingCase:
    if set(case.hidden_state) != {"routing_case"}:
        raise ValueError("routing manifest metadata differs")
    label = RoutingCase.model_validate_json(json.dumps(case.hidden_state["routing_case"]))
    if eval_case(label) != case:
        raise ValueError("routing case differs from its evaluator reference")
    return label


def task_for(
    label: RoutingCase, context: RunContext, grant: CallerGrant, limit: int
) -> ScheduledTrial:
    if context.case_id != label.case_id or context.tenant_id != label.order.tenant_id:
        raise ValueError("routing task differs from reference identity")
    amount = label.expected.refund_minor
    return ScheduledTrial(
        case_id=context.case_id,
        trial_id=context.trial_id,
        run_id=context.run_id,
        grant=grant,
        run_limit_minor=limit,
        command=None
        if amount is None
        else RefundCommand(
            tenant_id=context.tenant_id,
            order_id=label.order.order_id,
            business_operation_id=sha("olist-full-refund-v1|" + context.business_event_id),
            amount_minor=amount,
            expected_version=0,
        ),
    )


def score_capture(
    label: RoutingCase,
    task: ScheduledTrial,
    before: StateSnapshot,
    row: FieldCapture | None,
) -> dict[str, bool | None]:
    """Accepted fields; missing observations remain unknown, never a pass."""
    label = RoutingCase.model_validate_json(label.canonical_json())
    task = ScheduledTrial.model_validate_json(task.canonical_json())
    before = StateSnapshot.model_validate_json(before.canonical_json())
    if task.case_id != label.case_id:
        raise ValueError("routing score task differs")
    fields: dict[str, bool | None] = dict.fromkeys(
        (
            "intent",
            "amount",
            "action",
            "review_reason",
            "truthful_confirmation",
            "exact_state",
            "duplicate_delivery",
            "state_safety",
            "correct",
        )
    )
    if label.recovery_required:
        fields["recovery"] = None
    if row is None:
        return fields
    row = FieldCapture.model_validate_json(row.canonical_json())
    observation, result, decision = row.observation, row.workflow_result, row.decision
    if (row.case_id, row.trial_id) != task.key:
        raise ValueError("routing observation identity differs")
    if observation is not None and (
        (observation.case_id, observation.trial_id) != task.key or observation.before != before
    ):
        raise ValueError("routing observation differs from trusted initial state")
    if (
        result is not None
        and observation is not None
        and (result.outcome, result.message, result.receipt)
        != (observation.outcome, observation.message, observation.receipt)
    ):
        raise ValueError("routing workflow result differs from observed output")
    expected = expected_state(
        label.order, label.confirmation, label.expected.refund_minor, task, before
    )
    after = observation.after if observation is not None else None
    if decision is not None:
        fields["intent"] = decision.plan.intent == label.reference.expected.intent
        fields["amount"] = decision.plan.requested_minor == label.reference.expected.requested_minor
    if after is not None:
        fields["exact_state"] = expected is not None and after == expected
        fields["state_safety"] = after == before or expected is not None and after == expected
    if result is not None:
        fields["action"] = result.outcome == label.expected.outcome
        fields["review_reason"] = result.reason == label.expected.reason
        fields["duplicate_delivery"] = (
            row.duplicate_delivery_unchanged
            and after is not None
            and row.before_redelivery == after
            and row.redelivered_result == result
        )
        if after is not None:
            truth = False
            if result.outcome == "review_required":
                truth = result.receipt is None and result.message in (
                    "This request requires review. No new refund is confirmed.",
                    "Please clarify what action you want for this order. "
                    "No new refund is confirmed.",
                    "This request needs support review outside this workflow. "
                    "No new refund is confirmed.",
                )
            elif result.outcome == "status":
                truth = (
                    result.receipt is None
                    and after == before
                    and result.message
                    == (
                        "Recorded source status: "
                        + str(label.order.final_source_status or "unknown")
                        + ". No new refund was requested."
                    )
                )
            elif (
                result.receipt is not None
                and expected is not None
                and after == expected
                and task.command is not None
            ):
                truth = any(
                    r.receipt == result.receipt
                    and r.operation_id == task.command.business_operation_id
                    and r.tenant_id == task.command.tenant_id
                    for r in expected.ledger
                ) and result.message == (
                    f"A refund of {result.receipt.amount_minor // 100}."
                    f"{result.receipt.amount_minor % 100:02d} "
                    "SIM is committed in the controlled simulation ledger."
                )
            fields["truthful_confirmation"] = truth
    if label.recovery_required and row.recovery_observation is not None:
        fields["recovery"] = expected is not None and (
            row.recovery_observation.committed == row.recovery_observation.resumed == expected
        )
    fields["correct"] = (
        all(v is True for k, v in fields.items() if k != "correct")
        and decision is not None
        and decision.failure_code is None
        and not row.errors
        and observation is not None
        and not observation.errors
    )
    return fields
