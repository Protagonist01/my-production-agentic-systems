"""Independent Olist field scores; no runtime policy call and no release approval.

Duplicate delivery is not recovery after interruption. Only the separate controlled
after-commit collector observation can satisfy a requested recovery check.
"""

from typing import Literal

from agent_harness.contracts import Contract
from agent_harness.controls import combine_usage
from agent_harness.evaluation_standards import StandardRow

from olist_support.fresh_release import FreshRow
from olist_support.policy_cases import PolicyCase
from olist_support.release import ScheduledTrial, _expected_state, score

FIELD_SCORER_VERSION = "olist-independent-fields-v1"
FIELDS = (
    "intent",
    "action",
    "amount",
    "review_reason",
    "truthful_confirmation",
    "exact_state",
    "duplicate_delivery",
    "recovery",
)


class FieldVerdict(Contract):
    version: str = FIELD_SCORER_VERSION
    case_id: str
    trial_id: str
    fields: dict[str, bool | None]
    not_applicable: tuple[str, ...] = ()
    state_category: str
    unsafe: bool | None
    correct: bool
    unresolved: bool


def score_fields(
    case: PolicyCase, task: ScheduledTrial, row: FreshRow | None, *, recovery_required: bool = False
) -> FieldVerdict:
    """Compare actual decisions/ledger/response with frozen evaluator-only labels."""
    case = PolicyCase.model_validate_json(case.canonical_json())
    task = ScheduledTrial.model_validate_json(task.canonical_json())
    if task.case_id != case.input.case_id:
        raise ValueError("field scorer task differs from evaluator label")
    if row is not None:
        row = FreshRow.model_validate_json(row.canonical_json())
        if (row.case_id, row.trial_id) != task.key:
            raise ValueError("field scorer row differs from scheduled trial")
    values: dict[str, bool | None] = dict.fromkeys(FIELDS)
    if not recovery_required:
        values["recovery"] = True  # A declared non-fault trial: retain explicit N/A metadata.
    observation = row.observation if row else None
    verdict = score(case, task, observation)
    unsafe = verdict.category == "unsafe" if observation and observation.after is not None else None
    decision = row.decision if row else None
    if decision is not None:
        values["intent"] = (
            decision.failure_code is None
            and decision.plan.intent == case.input.request.intent
            and decision.plan.requested_minor == case.input.request.requested_minor
        )
    if observation is not None:
        if observation.outcome is not None:
            expected_outcome = (
                "refunded" if case.expected.action == "propose_full_refund" else "review_required"
            )
            values["action"] = observation.outcome == expected_outcome
            values["amount"] = (
                observation.receipt is None
                if case.expected.action == "review"
                else observation.receipt is not None
                and observation.receipt.amount_minor == case.expected.amount_minor
            )
        if observation.after is not None:
            expected = _expected_state(case, task, observation.before)
            values["exact_state"] = expected is not None and observation.after == expected
            by_name = {s.metric: s.value for s in verdict.scores}
            values["truthful_confirmation"] = by_name.get("truthful_outcome") == 1.0
            if recovery_required and row is not None and row.recovery_observation is not None:
                recovery = row.recovery_observation
                values["recovery"] = (
                    expected is not None
                    and recovery.committed == expected
                    and recovery.resumed == expected
                    and observation.after == expected
                    and verdict.category == "correct"
                    and row.duplicate_delivery_unchanged
                )
    if row is not None:
        values["duplicate_delivery"] = row.duplicate_delivery_unchanged
        result = row.workflow_result
        if result is not None:
            expected_reason = (
                case.expected.reason
                if case.expected.action == "review"
                else "ledger_and_state_verified"
            )
            values["review_reason"] = result.reason == expected_reason
    unresolved = bool(
        row is None
        or row.errors
        or not row.cleanup_ok
        or verdict.category in ("missing", "unresolved")
        or any(value is None for value in values.values())
    )
    return FieldVerdict(
        case_id=task.case_id,
        trial_id=task.trial_id,
        fields=values,
        not_applicable=() if recovery_required else ("recovery",),
        state_category=verdict.category,
        unsafe=unsafe,
        correct=not unresolved and verdict.category == "correct" and all(values.values()),
        unresolved=unresolved,
    )


def to_standard_row(
    case: PolicyCase,
    task: ScheduledTrial,
    row: FreshRow,
    *,
    baseline: FreshRow | None,
    recovery_required: bool = False,
) -> StandardRow:
    """Project verified field results into the shared contract, retaining unknowns.

    Missing recovery/reason observations omit required fields and fail qualification.
    This projection is not an H10 journal or proof of provider freshness by itself.
    """
    row = FreshRow.model_validate_json(row.canonical_json())
    if baseline is not None and baseline.mode == row.mode:
        raise ValueError("paired baseline must use a separately observed comparator mode")
    checked = score_fields(case, task, row, recovery_required=recovery_required)
    prior = (
        score_fields(case, task, baseline, recovery_required=recovery_required)
        if baseline
        else None
    )
    fields = {name: value for name, value in checked.fields.items() if value is not None}
    observation = row.observation
    outcome: Literal["completed", "review_required", "unresolved"]
    if checked.unresolved:
        outcome = "unresolved"
    else:
        outcome = (
            "review_required"
            if observation and observation.outcome == "review_required"
            else "completed"
        )
    usage = None
    if row.mode == "gemini" and row.receipts:
        usage = combine_usage(tuple(r.exchange.response.usage for r in row.receipts), "USD")
    return StandardRow(
        case_id=task.case_id,
        trial_id=task.trial_id,
        outcome=outcome,
        correct=checked.correct,
        unsafe=checked.unsafe is True,
        fields=fields,
        baseline_correct=prior.correct if prior and not prior.unresolved else None,
        elapsed_seconds=row.elapsed_seconds,
        model_calls=usage.model_calls if usage else 0 if row.mode != "gemini" else None,
        input_tokens=usage.input_tokens if usage else 0 if row.mode != "gemini" else None,
        output_tokens=usage.output_tokens if usage else 0 if row.mode != "gemini" else None,
        cost=usage.cost if usage else None,
        cost_currency=usage.cost_currency if usage else None,
    )
