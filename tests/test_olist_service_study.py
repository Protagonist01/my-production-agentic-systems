"""Complete denominators and honest uncertainty/cost for invented service observations."""

from decimal import Decimal

import pytest
from agent_harness.contracts import Usage
from agent_harness.release_contracts import pin, sha256
from olist_routing_fixtures import label_for
from olist_support.service_evaluation import ServiceScenario, ServiceScript
from olist_support.service_h10 import manifest_for
from olist_support.service_study import (
    FIELDS,
    ServicePopulation,
    ServiceProtocol,
    ServiceRow,
    summarize,
)


def preparation(*, recovery=False, variants=False):
    label = label_for("refund", recovery=recovery)
    confirm = ServiceScenario(
        reference=label, script=ServiceScript(customer="confirm", amount_minor=5000)
    )
    entries = (
        (confirm, ServiceScenario(reference=label, script=ServiceScript()))
        if variants
        else (confirm,)
    )
    population = ServicePopulation(entries=entries)
    manifest = manifest_for(entries)
    protocol = ServiceProtocol(
        population_sha256=pin(population),
        manifest_sha256=sha256(manifest.canonical_json().encode()),
        candidate_sha256={"candidate": "a" * 64, "rules": "b" * 64, "always-review": "c" * 64},
        trial_ids=("trial-1", "trial-2", "trial-3"),
    )
    return population, protocol


def row(population, trial="trial-1", *, unresolved=False, usage=None, recovery=False):
    values = dict.fromkeys(FIELDS, True)
    values["observed_review"] = False
    if recovery:
        values["recovery"] = True
    if unresolved:
        values["correct"] = False
    return ServiceRow(
        variant="candidate",
        case_id=population.entries[0].case_id,
        trial_id=trial,
        fields=values,
        unresolved=unresolved,
        elapsed_seconds=2.0,
        usage=usage,
    )


def test_absent_variants_and_trials_remain_in_every_denominator():
    population, protocol = preparation()
    report = summarize(protocol, population, (row(population),))
    assert report["scheduled"] == 9 and report["observed"] == 1 and report["missing"] == 8
    candidate = report["variants"]["candidate"]
    assert candidate["joint_intent_amount"] == {
        "passed": 1,
        "failed": 0,
        "unknown_or_missing": 2,
        "scheduled": 3,
        "pass_fraction": 1 / 3,
    }
    assert candidate["all_repetition_case_passes"] == 0
    assert candidate["timing"]["unknown_or_missing"] == 2
    assert candidate["timing"]["api_latency_target_assessable"] is False
    assert report["variants"]["rules"]["fields"]["correct"]["unknown_or_missing"] == 3
    assert not report["qualification_met"] and not report["release_allowed"]


def test_same_source_with_different_customer_script_is_one_connected_group():
    population, protocol = preparation(variants=True)
    report = summarize(protocol, population, ())
    for variant in report["variants"].values():
        assert variant["declared_connected_groups"] == 1
        assert variant["cases_scheduled"] == 2
        assert variant["unknown_groups"] == 1
        assert variant["conditional_group_error_bounds"]["upper"] == 1


def test_failed_attempt_fallback_cannot_receive_semantic_or_completion_credit():
    population, protocol = preparation()
    report = summarize(protocol, population, (row(population, unresolved=True),))
    variant = report["variants"]["candidate"]
    assert variant["joint_intent_amount"]["passed"] == 0
    assert variant["eligible_completion"]["passed"] == 0
    assert variant["fields"]["customer_authority"]["passed"] == 1
    assert variant["unresolved"] == 1


def test_unknown_cost_is_not_zero_and_reported_free_is_not_billing_proof():
    population, protocol = preparation()
    unknown = Usage(
        model_calls=1, input_tokens=None, output_tokens=3, cost=None, cost_currency=None
    )
    zero = Usage(
        model_calls=1, input_tokens=2, output_tokens=3, cost=Decimal(0), cost_currency="USD"
    )
    report = summarize(
        protocol,
        population,
        (
            row(population, usage=unknown),
            row(population, "trial-2", usage=zero),
        ),
    )
    usage = report["variants"]["candidate"]["usage"]
    assert usage["reported_model_calls"] == 2 and usage["missing_rows"] == 1
    assert usage["known_input_tokens"] == 2 and usage["input_tokens_unknown_or_missing"] == 2
    assert usage["known_reported_costs"] == {"USD": "0"}
    assert usage["cost_unknown_or_missing"] == 2 and not usage["billing_cost_verified"]


def test_duplicate_foreign_rows_omitted_recovery_and_wrong_pins_refuse():
    population, protocol = preparation(recovery=True)
    complete = row(population, recovery=True)
    with pytest.raises(ValueError, match="duplicate"):
        summarize(protocol, population, (complete, complete))
    with pytest.raises(ValueError, match="recovery"):
        summarize(protocol, population, (row(population),))
    with pytest.raises(ValueError, match="unscheduled"):
        summarize(protocol, population, (complete.model_copy(update={"trial_id": "foreign"}),))
    with pytest.raises(ValueError, match="protocol"):
        summarize(protocol.model_copy(update={"population_sha256": "f" * 64}), population, ())


def test_partial_repeats_never_inflate_all_repetition_success():
    population, protocol = preparation()
    report = summarize(protocol, population, tuple(row(population, t) for t in protocol.trial_ids))
    candidate = report["variants"]["candidate"]
    assert candidate["all_repetition_case_passes"] == 1
    assert candidate["declared_connected_groups"] == 1
    assert candidate["conditional_group_error_bounds"]["upper"] > 0.9
