"""Seeded wider-reference/state/report failures; no provider or language accuracy claim."""

from dataclasses import replace

import pytest
from agent_harness.contracts import AgentInput
from agent_harness.release_contracts import pin
from langgraph.checkpoint.memory import InMemorySaver
from olist_routing_fixtures import INTENTS, composition, label_for
from olist_support.field_evaluation import FieldCapture
from olist_support.h10_environment import grant_for
from olist_support.release import Observation, OrderState, StateSnapshot, expected_state
from olist_support.routing_evaluation import (
    RoutingPopulation,
    eval_case,
    private_case,
    score_capture,
    task_for,
)
from olist_support.routing_h10 import RoutingBinding, manifest_for, observed_scores
from olist_support.routing_study import RoutingProtocol, RoutingScoreRow, summarize
from olist_support.workflow import FixedPlanner, SupportWorkflow
from test_olist_release import case_for, enrollment_pin
from test_olist_workflow import GRANT, REQUEST, StubStore, context


def witness(intent="clarify"):
    label = label_for(intent)
    c = context().model_copy(update={"case_id": label.case_id, "agent_id": "olist"})
    grant = grant_for(c.tenant_id, label.order.order_id)
    task = task_for(label, c, grant, 10000)
    before = StateSnapshot(
        orders=(
            OrderState(
                tenant_id=c.tenant_id,
                order_id=label.order.order_id,
                record_sha256=enrollment_pin(case_for()),
                version=0,
                refunded_minor=0,
            ),
        ),
        ledger=(),
        budgets=(),
    )
    after = expected_state(
        label.order, label.confirmation, label.expected.refund_minor, task, before
    )
    result = SupportWorkflow(StubStore(), FixedPlanner(label.reference.expected)).run(
        c, REQUEST, GRANT, InMemorySaver(), run_limit_minor=10000
    )
    if intent == "refund":
        receipt = after.ledger[0].receipt
        result = result.model_copy(update={"receipt": receipt})
    from olist_support.workflow import IntentDecision

    decision = IntentDecision(plan=label.reference.expected)
    row = FieldCapture(
        case_id=label.case_id,
        trial_id=c.trial_id,
        observation=Observation(
            case_id=label.case_id,
            trial_id=c.trial_id,
            before=before,
            after=after,
            outcome=result.outcome,
            receipt=result.receipt,
            message=result.message,
        ),
        decision=decision,
        workflow_result=result,
        duplicate_delivery_unchanged=True,
        before_redelivery=after,
        redelivered_result=result,
    )
    return label, c, task, before, row


@pytest.mark.parametrize("intent", INTENTS)
def test_all_routes_bind_text_and_score_without_fake_policy_intents(intent):
    label, _, task, before, row = witness(intent)
    case = eval_case(label)
    assert case.agent_input() == AgentInput(request=label.reference.text)
    assert private_case(case) == label
    assert "routing_case" not in case.agent_input().canonical_json()
    assert all(score_capture(label, task, before, row).values())


def test_missing_changed_reason_effect_duplicate_and_scope_do_not_pass():
    label, _, task, before, row = witness()
    missing = score_capture(label, task, before, None)
    assert all(v is None for v in missing.values())
    changed = row.workflow_result.model_copy(update={"reason": "wrong"})
    assert (
        score_capture(label, task, before, row.model_copy(update={"workflow_result": changed}))[
            "correct"
        ]
        is False
    )
    bad = row.model_copy(update={"before_redelivery": None})
    assert score_capture(label, task, before, bad)["duplicate_delivery"] is False
    tampered = row.observation.model_copy(
        update={"after": before.model_copy(update={"orders": ()})}
    )
    fields = score_capture(label, task, before, row.model_copy(update={"observation": tampered}))
    assert fields["state_safety"] is False and fields["correct"] is False
    with pytest.raises(ValueError, match="identity"):
        score_capture(label, task, before, row.model_copy(update={"case_id": "b" * 64}))
    with pytest.raises(ValueError, match="trusted"):
        score_capture(label, task, before.model_copy(update={"orders": ()}), row)


def test_missing_recovery_and_forged_manifest_or_splits_refused():
    label, _, task, before, row = witness("refund")
    recovery = label.model_copy(update={"recovery_required": True})
    assert score_capture(recovery, task, before, row)["recovery"] is None
    assert score_capture(recovery, task, before, row)["correct"] is False
    with pytest.raises(ValueError):
        private_case(eval_case(label).model_copy(update={"input": AgentInput(request="changed")}))
    other = label.model_copy(update={"case_id": "b" * 64, "split": "holdout"})
    with pytest.raises(ValueError, match="crosses"):
        RoutingPopulation(entries=(label, other))


def test_safe_legacy_abstention_cannot_become_fine_routing_success():
    label, c, task, before, row = witness()
    from olist_support.workflow import IntentDecision, IntentPlan

    result = row.workflow_result.model_copy(
        update={
            "reason": "intent_requires_review",
            "message": "This request requires review. No new refund is confirmed.",
        }
    )
    row = row.model_copy(
        update={
            "decision": IntentDecision(plan=IntentPlan(intent="review")),
            "workflow_result": result,
            "redelivered_result": result,
            "observation": row.observation.model_copy(update={"message": result.message}),
        }
    )
    fields = score_capture(label, task, before, row)
    assert fields["action"] and fields["state_safety"] and fields["truthful_confirmation"]
    assert not fields["intent"] and not fields["correct"]
    scores = observed_scores(
        eval_case(label), c, RoutingBinding(label.order.order_id, task.grant, before, False), row
    )
    assert next(s.value for s in scores if s.metric == "observed_review") == 1


def test_report_keeps_missing_denominators_and_refuses_foreign_or_duplicate_rows():
    population = RoutingPopulation(entries=(label_for(),))
    protocol = RoutingProtocol(
        population_sha256=pin(population),
        manifest_sha256=pin(manifest_for(population)),
        candidate_sha256={
            v: str(i) * 64
            for i, v in enumerate(("candidate", "legacy", "rules", "always-review"), 1)
        },
        trial_ids=("one", "two", "three"),
    )
    result = summarize(protocol, population, ())
    assert result["scheduled"] == result["missing"] == 12
    assert not result["qualification_met"] and not result["release_allowed"]
    row = RoutingScoreRow(
        variant="candidate",
        case_id=population.entries[0].case_id,
        trial_id="one",
        fields={"intent": True},
        unresolved=False,
    )
    report = summarize(protocol, population, (row,))
    assert report["variants"]["candidate"]["fields"]["amount"]["unknown_or_missing"] == 3
    with pytest.raises(ValueError):
        summarize(protocol, population, (row, row))
    with pytest.raises(ValueError):
        summarize(protocol, population, (row.model_copy(update={"trial_id": "foreign"}),))


def test_factory_refuses_wrong_algorithm_pins_and_live_routes():
    _, _, _, factory = composition()
    factory.validate()
    with pytest.raises(ValueError, match="mock-only"):
        replace(factory, origin="provider").validate()
    with pytest.raises(ValueError, match="composition"):
        replace(factory, variant="legacy").validate()
    route = factory.route.model_copy(update={"provider": "google-gemini-developer-api"})
    from olist_support.routing_h10 import fingerprints

    spec = factory.candidate.model_copy(
        update={**fingerprints(route, factory.candidate.source_files, "candidate")}
    )
    with pytest.raises(ValueError, match="mock-only"):
        replace(factory, candidate=spec, route=route).validate()


def test_missing_final_state_and_foreign_refund_receipt_are_not_confirmed_success():
    label, _, task, before, row = witness("refund")
    missing = row.model_copy(
        update={"observation": row.observation.model_copy(update={"after": None})}
    )
    fields = score_capture(label, task, before, missing)
    assert fields["state_safety"] is None and fields["truthful_confirmation"] is None
    assert fields["correct"] is False
    receipt = row.workflow_result.receipt.model_copy(update={"order_id": "other-order"})
    result = row.workflow_result.model_copy(update={"receipt": receipt})
    forged = row.model_copy(
        update={
            "workflow_result": result,
            "redelivered_result": result,
            "observation": row.observation.model_copy(update={"receipt": receipt}),
        }
    )
    assert score_capture(label, task, before, forged)["truthful_confirmation"] is False


def test_reference_effect_must_match_independent_structured_policy():
    label = label_for("refund")
    from olist_support.routing_evaluation import RoutingCase

    with pytest.raises(ValueError, match="policy table"):
        RoutingCase.model_validate_json(
            label.model_copy(update={"confirmation": None}).canonical_json()
        )


def test_correct_report_row_cannot_hide_unknown_or_unresolved_evidence():
    with pytest.raises(ValueError, match="hide"):
        RoutingScoreRow(
            variant="candidate",
            case_id="a" * 64,
            trial_id="one",
            fields={"correct": True},
            unresolved=False,
        )
