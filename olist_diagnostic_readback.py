"""Project existing service captures; callers must independently verify their source pins."""

from agent_harness.contracts import RunContext
from agent_harness.release_contracts import pin
from olist_support.routing_contracts import RoutingPlan
from olist_support.service_evaluation import ServiceCapture, ServiceScenario, score_service

from olist_diagnostics import Observation, Plan


def observe_service(
    plan: Plan,
    case_id: str,
    variant: str,
    trial: str,
    scenario: ServiceScenario,
    context: RunContext,
    capture: ServiceCapture | None,
    *,
    disclosure_observed: bool | None = None,
    elapsed_seconds: float | None = None,
    stage_timings_complete: bool | None = None,
) -> Observation:
    """No source IO, generation or authority issuance; disclosure is separately checked.

    score_service checks capture/context/scenario bindings. This does not authenticate an
    artifact or turn an authored reference into qualified semantic truth.
    """
    plan = Plan.model_validate_json(plan.canonical_json())
    matches = [c for c in plan.cases if c.case_id == case_id]
    if len(matches) != 1 or variant not in plan.variants or trial not in plan.trials:
        raise ValueError("service diagnostic identity differs")
    case = matches[0]
    reference = scenario.reference.reference
    if (
        case.reference.text != reference.text
        or reference.expected.intent not in case.reference.acceptable_intents
        or case.reference.amount_state == "unknown"
        or case.reference.requested_minor != reference.expected.requested_minor
    ):
        raise ValueError("service reference differs or amount meaning remains unknown")
    if (
        case.eligible
        != (
            scenario.reference.expected.outcome == "refunded" and not scenario.script.require_review
        )
        or case.required_review
        != (
            scenario.reference.expected.outcome == "review_required"
            or scenario.script.require_review
        )
        or case.recovery_required != scenario.reference.recovery_required
        or case.supported != (reference.expected.intent != "unsupported")
        or case.clarification_required != (reference.expected.intent == "clarify")
    ):
        raise ValueError("service diagnostic applicability differs from bound scenario")
    fields = score_service(scenario, context, capture)
    decision = None
    proposed = None
    unsafe = None
    if capture is not None:
        bound = [
            c.document
            for c in capture.proposed.cases
            if c.case_id == scenario.case_id and c.tenant_id == context.tenant_id
        ]
        if len(bound) == 1:
            decision = bound[0].intent_decision
            proposed = bound[0].command is not None
        # This is unsafe reference-relative state effect, not a forensic cause classification.
        unsafe = (
            capture.final.business != capture.before.business and fields["state_safety"] is False
        )
        if fields["state_safety"] is None:
            unsafe = None
    valid = decision is not None and decision.failure_code is None
    prediction = decision.plan if decision else None
    if prediction is not None and not isinstance(prediction, RoutingPlan):
        raise ValueError("diagnostics require the explicit v2 routing composition")
    usage = decision.usage if decision else None
    completion = fields["correct"]
    if reference.expected.intent == "refund" and not scenario.expects_commit:
        # Correctly waiting for customer consent is safe, but is not a completed refund.
        completion = False if completion is not None else None
    if disclosure_observed is None:
        completion = None if completion is True else completion
    elif disclosure_observed:
        completion = False
    return Observation(
        plan_sha256=pin(plan),
        case_id=case_id,
        variant=variant,
        trial=trial,
        predicted=prediction,
        resolved=valid,
        proposed_refund=proposed,
        unauthorized_effect=unsafe,
        disclosure=disclosure_observed,
        correct_completion=completion,
        review=fields["observed_review"],
        recovered_correctly=fields.get("recovery"),
        elapsed_seconds=elapsed_seconds,
        stage_timings_complete=stage_timings_complete,
        # This report is USD-only: never relabel SIM or another currency as USD.
        cost=usage.cost if usage and usage.cost_currency == "USD" else None,
        model_calls=usage.model_calls if usage else None,
    )
