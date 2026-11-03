"""Service reference/script/context boundaries; no SQL, SDK or source-data exports."""

from dataclasses import replace

import pytest
from olist_routing_fixtures import label_for
from olist_service_fixtures import composition
from olist_support.service_evaluation import ServiceScenario, ServiceScript, score_service
from olist_support.service_h10 import eval_case, manifest_for, private_scenario


def test_script_requires_an_explicit_amount_and_independent_reviewer_flag():
    with pytest.raises(ValueError):
        ServiceScript(customer="confirm")
    with pytest.raises(ValueError):
        ServiceScript(amount_minor=5000)
    with pytest.raises(ValueError):
        ServiceScript(reviewer="approve")


def test_missing_observations_stay_unknown_and_context_cannot_be_rewritten():
    scenario, _, schedule, _ = composition("refund")
    ctx = schedule.tasks[0].context
    values = score_service(scenario, ctx, None)
    assert values and all(v is None for v in values.values())
    with pytest.raises(ValueError, match="context differs"):
        score_service(scenario, ctx.model_copy(update={"business_event_id": "other"}), None)


def test_reference_and_customer_scripts_stay_out_of_agent_input_and_variants_stay_grouped():
    reference = label_for("refund")
    withheld = ServiceScenario(reference=reference, script=ServiceScript())
    confirm = ServiceScenario(
        reference=reference, script=ServiceScript(customer="confirm", amount_minor=5000)
    )
    manifest = manifest_for((withheld, confirm))
    assert manifest.entries[0].group_id == manifest.entries[1].group_id
    assert withheld.case_id != confirm.case_id
    assert private_scenario(eval_case(confirm)) == confirm
    assert eval_case(confirm).agent_input().request == reference.reference.text
    assert not eval_case(confirm).agent_input().observations
    assert not eval_case(withheld).expected.eligible_for_autonomy
    assert eval_case(confirm).expected.eligible_for_autonomy
    with pytest.raises(ValueError, match="duplicate"):
        manifest_for((confirm, confirm))


def test_mock_service_composition_refuses_live_routes_or_provider_controls():
    _, _, _, factory = composition()
    factory.validate()
    live = factory.route.model_copy(update={"provider": "google", "endpoint": "live"})
    with pytest.raises(ValueError):
        replace(factory, route=live).validate()
    with pytest.raises(ValueError, match="mock-only"):
        replace(
            factory,
            candidate=factory.candidate.model_copy(update={"provider_control_sha256": "a" * 64}),
        ).validate()
