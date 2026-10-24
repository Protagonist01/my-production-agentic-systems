"""Independent field mutations; invented observations are not model-quality evidence."""

import pytest
from olist_support.field_evaluation import score_fields, to_standard_row
from olist_support.fresh_release import RecoveryObservation
from olist_support.workflow import IntentDecision, IntentPlan, WorkflowResult
from test_olist_fresh import fixture


def observed():
    plan, cases, _, row = fixture()
    observation = row.observation
    result = WorkflowResult(
        outcome=observation.outcome,
        message=observation.message,
        receipt=observation.receipt,
        reason="ledger_and_state_verified",
    )
    return cases.entries[0], plan.tasks[0], row.model_copy(update={"workflow_result": result})


def test_actual_fields_pass_but_old_reason_and_missing_recovery_stay_unknown():
    case, task, row = observed()
    assert score_fields(case, task, row).correct
    old = row.model_copy(update={"workflow_result": None})
    assert score_fields(case, task, old).fields["review_reason"] is None
    assert score_fields(case, task, old).unresolved
    fault = score_fields(case, task, row, recovery_required=True)
    assert fault.fields["recovery"] is None and fault.unresolved
    projected = to_standard_row(case, task, old, baseline=None)
    assert projected.outcome == "unresolved"
    assert "review_reason" not in projected.fields
    assert projected.baseline_correct is None


def test_wrong_actual_reason_fails_even_with_exact_state_and_correct_action():
    case, task, row = observed()
    row = row.model_copy(
        update={
            "workflow_result": row.workflow_result.model_copy(update={"reason": "wrong_reason"})
        }
    )
    result = score_fields(case, task, row)
    assert result.fields["exact_state"] is True
    assert result.fields["review_reason"] is False
    assert not result.correct and not result.unresolved


def test_recovery_needs_exact_committed_resumed_and_final_state():
    case, task, row = observed()
    after = row.observation.after
    recovery = RecoveryObservation(committed=after, resumed=after)
    row = row.model_copy(update={"recovery_observation": recovery})
    assert score_fields(case, task, row, recovery_required=True).correct
    changed = row.model_copy(
        update={
            "recovery_observation": recovery.model_copy(update={"resumed": row.observation.before})
        }
    )
    verdict = score_fields(case, task, changed, recovery_required=True)
    assert verdict.fields["recovery"] is False and not verdict.correct


def test_scope_mismatch_and_same_mode_baseline_refuse_projection():
    case, task, row = observed()
    with pytest.raises(ValueError, match="scheduled trial"):
        score_fields(case, task, row.model_copy(update={"trial_id": "other", "observation": None}))
    with pytest.raises(ValueError, match="comparator"):
        to_standard_row(case, task, row, baseline=row)
    assert score_fields(case, task, None).unresolved


def test_response_cannot_diverge_from_independent_observation():
    case, task, row = observed()
    changed = row.model_copy(
        update={
            "workflow_result": row.workflow_result.model_copy(
                update={"message": "invented changed response"}
            )
        }
    )
    with pytest.raises(ValueError, match="observed response"):
        score_fields(case, task, changed)


def test_required_review_reason_and_intent_are_independent_of_no_effect_safety():
    case, task, row = observed()
    case = case.model_copy(
        update={
            "expected": case.expected.model_copy(
                update={
                    "action": "review",
                    "amount_minor": None,
                    "reason": "invented_required_review",
                }
            )
        }
    )
    observation = row.observation.model_copy(
        update={
            "after": row.observation.before,
            "outcome": "review_required",
            "receipt": None,
            "message": "This request requires review. No new refund is confirmed.",
        }
    )
    result = WorkflowResult(
        outcome="review_required", message=observation.message, reason="invented_required_review"
    )
    row = row.model_copy(update={"observation": observation, "workflow_result": result})
    verdict = score_fields(case, task, row)
    assert verdict.correct and verdict.fields["amount"] is True
    changed = row.model_copy(update={"decision": IntentDecision(plan=IntentPlan(intent="reship"))})
    verdict = score_fields(case, task, changed)
    assert verdict.fields["exact_state"] is True and verdict.unsafe is False
    assert verdict.fields["intent"] is False and not verdict.correct
