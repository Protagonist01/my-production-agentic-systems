"""Accepted reference preservation, authority separation and complete service preparation."""

import json

import pytest
from agent_harness.release_contracts import pin, sha256
from olist_controlled_service_fixtures import packet_bytes, references
from olist_support.controlled_service_package import ControlledServicePackage, prepare
from olist_support.controlled_service_reference import ControlledServiceReference, bind_accepted
from olist_support.routing_evaluation import RoutingCase
from olist_support.routing_reference import RoutingReference
from olist_support.service_h10 import eval_case, manifest_for, private_scenario
from olist_support.service_study import ServiceProtocol, summarize


def test_loader_verifies_actual_original_file_bytes_and_separate_acceptance():
    values = references()
    assert len(values) == 12
    for index in range(3):
        changed = list(packet_bytes())
        changed[index] += b" "
        with pytest.raises(ValueError, match="bytes differ"):
            bind_accepted(*changed)
    assert all(not r.source.method_accepted for r in values)  # original proposal history
    assert all(r.provenance == "accepted_constructed_development" for r in values)


def test_all_inputs_meanings_and_prefix_spans_survive_service_manifest_roundtrip():
    package = prepare(references())
    assert ControlledServicePackage.model_validate_json(package.canonical_json()) == package
    base = package.population.entries[:12]
    for source, scenario in zip(package.references, base, strict=True):
        case = eval_case(scenario)
        assert case.agent_input() == source.source.input
        assert private_scenario(case) == scenario
        assert "acceptance_sha256" not in case.agent_input().canonical_json()
        assert scenario.reference.reference.expected == source.expected
    assert "SIM 99.99" in base[3].reference.reference.text
    with pytest.raises(ValueError):
        RoutingReference(
            text=base[3].reference.reference.text,
            expected=base[3].reference.reference.expected,
            provenance="constructed_development",
        )


def test_policy_eligibility_customer_choice_and_recovery_scripts_have_distinct_denominators():
    package = prepare(references())
    entries = package.population.entries
    assert len(entries) == 18
    assert sum(s.expects_commit for s in entries) == 4
    assert sum(s.reference.recovery_required for s in entries) == 1
    assert len({s.reference.group_id for s in entries}) == 5
    assert len({s.reference.order.order_id for s in entries}) == 5
    assert not any(s.expects_commit for s in entries[:12])
    assert not entries[15].expects_commit  # separate reviewer rejects
    assert not entries[16].expects_commit  # wrong customer amount
    assert entries[17].expects_commit and entries[17].reference.recovery_required
    manifest = manifest_for(entries)
    protocol = ServiceProtocol(
        population_sha256=pin(package.population),
        manifest_sha256=sha256(manifest.canonical_json().encode()),
        candidate_sha256={"candidate": "a" * 64, "rules": "b" * 64, "always-review": "c" * 64},
        trial_ids=("trial-1", "trial-2", "trial-3"),
    )
    report = summarize(protocol, package.population, ())
    assert report["scheduled"] == report["missing"] == 162 and report["observed"] == 0
    for variant in report["variants"].values():
        assert variant["declared_connected_groups"] == 5
        assert variant["eligible_completion"]["scheduled"] == 12
    assert not report["qualification_met"] and not report["release_allowed"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("split", "holdout"),
        ("source_kind", "hybrid"),
        ("group_id", "b" * 64),
        ("language_family", "invented-independent-family"),
        ("reference_source_sha256", "b" * 64),
    ],
)
def test_controlled_service_cannot_be_relabelled_as_fresh_or_independent(field, value):
    case = prepare(references()).population.entries[0].reference
    with pytest.raises(ValueError, match="controlled service"):
        RoutingCase.model_validate_json(case.model_copy(update={field: value}).canonical_json())


def test_changed_script_fixture_or_expanded_unaccepted_amount_is_not_this_package():
    package = prepare(references())
    data = json.loads(package.canonical_json())
    data["population"]["entries"][0]["script"] = data["population"]["entries"][12]["script"]
    with pytest.raises(ValueError, match="preparation differs"):
        ControlledServicePackage.model_validate_json(json.dumps(data))
    data = json.loads(package.canonical_json())
    data["population"]["entries"][0]["reference"]["order"]["customer_city"] = "changed"
    with pytest.raises(ValueError, match="preparation differs"):
        ControlledServicePackage.model_validate_json(json.dumps(data))
    from olist_support.controlled_reference import ControlledSpec, construct

    with pytest.raises(ValueError, match="original twelve"):
        ControlledServiceReference(
            source=construct(ControlledSpec(template="refund_suffix", requested_minor=1234))
        )


def test_complete_ordered_reference_set_is_required_for_the_declared_package():
    values = references()
    for changed in (values[:-1], tuple(reversed(values)), (values[0],) * 12):
        with pytest.raises(ValueError, match="complete original ordered"):
            prepare(changed)


def test_original_stress_format_refuses_the_new_service_wrapper():
    from olist_support.routing_stress import StressDraft, StressEntry

    case = prepare(references()).population.entries[0].reference
    with pytest.raises(ValueError, match="explicitly constructed"):
        StressDraft(
            entries=(StressEntry(case=case, challenge="zero_amount", rationale="invented"),)
        )


def test_service_tasks_bind_the_selected_scenario_tenant_not_the_old_fixture_default():
    from olist_service_fixtures import composition

    scenario = prepare(references()).population.entries[17]
    _, _, schedule, _ = composition("refund", scenario=scenario)
    for task in schedule.tasks:
        scenario.check_context(task.context)
        assert task.context.tenant_id == scenario.reference.order.tenant_id
