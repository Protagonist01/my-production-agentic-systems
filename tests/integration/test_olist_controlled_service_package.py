"""Real SQL service on accepted constructed texts; invented gateway decisions only."""

from dataclasses import replace

import pytest
from olist_controlled_service_fixtures import references
from olist_service_fixtures import ROOT, MockServiceRoute, composition
from olist_support.controlled_service_package import prepare
from olist_support.routing_contracts import RoutingPlan
from olist_support.service_h10 import (
    ServiceAgent,
    ServiceEnvironment,
    ServiceScorer,
    ServiceSlot,
    eval_case,
)
from test_olist_business import app as app
from test_olist_workflow import InventedGateway


@pytest.mark.parametrize(
    "index,wrong,committed,correct",
    [
        (12, False, True, True),  # exact cap, independently scripted customer confirmation
        (3, False, False, True),  # prefix currency preserved; partial refund requires review
        (4, True, False, False),  # payment confused with requested refund, consent withheld
        (8, True, False, False),  # clarification confused with refund, consent withheld
        (17, False, True, True),  # committed response loss, reconstructed service reads receipt
    ],
)
def test_original_texts_cross_real_service_scoring_and_authority_boundaries(
    app, tmp_path, index, wrong, committed, correct
):
    scenario = prepare(references()).population.entries[index]
    expected = scenario.reference.reference.expected
    emitted = (
        RoutingPlan(
            routing_version="olist-intent-routing-v2", intent="refund", requested_minor=10000
        )
        if wrong
        else expected
    )
    _, loaded, schedule, factory = composition(expected.intent, scenario=scenario)
    environment = ServiceEnvironment(app[0], app[1].workspace_key, loaded)
    task = schedule.tasks[0]
    lease = environment.prepare(schedule.experiment_id, task)
    slot = ServiceSlot()
    gateway = InventedGateway(emitted.canonical_json())
    try:
        result = ServiceAgent(lease.access, factory.route, slot).run(
            task.context,
            eval_case(scenario).agent_input(),
            gateway,
        )
        scores = {
            s.metric: s.value
            for s in ServiceScorer(
                task.context,
                lease.access,
                slot,
                tmp_path / "observations",
            ).score(loaded.manifest.entries[0].case, result)
        }
        capture = slot.capture
        assert capture is not None and len(gateway.requests) == 1
        assert gateway.requests[0].messages[1].content == scenario.reference.reference.text
        assert scores["correct"] == int(correct)
        assert (
            scores["routing_safe"]
            == scores["customer_authority"]
            == scores["duplicate_delivery"]
            == 1
        )
        assert capture.proposed.business == capture.before.business
        assert bool(capture.returned.result.receipt) == committed
        if wrong:
            assert capture.final.business == capture.before.business
            assert scores["intent" if index == 8 else "amount"] == 0
        if committed:
            assert capture.returned.result.receipt.amount_minor == 10000
        if index == 17:
            assert scores["recovery"] == 1
            assert capture.interrupted == capture.final == capture.redelivery
        assert lease.access.observe() == capture.redelivery
    finally:
        environment.release(lease)


def test_controlled_reference_survives_h10_three_trial_recording_and_strict_readback(app, tmp_path):
    from agent_harness.release_contracts import pin
    from olist_support.service_h10 import read_mock, record_mock

    scenario = prepare(references()).population.entries[17]
    _, loaded, schedule, factory = composition("refund", scenario=scenario)
    factory = replace(factory, transport=MockServiceRoute("refund", 10000))
    output = tmp_path / "controlled-service-mock"
    evidence = record_mock(
        schedule,
        loaded,
        factory,
        ServiceEnvironment(app[0], app[1].workspace_key, loaded),
        output,
        candidate_sha256=pin(factory.candidate),
        source_root=ROOT,
    )
    verified = read_mock(
        output,
        loaded,
        route=factory.route,
        evidence_sha256=pin(evidence),
        candidate_sha256=pin(factory.candidate),
    )
    assert verified.batch.complete and len(verified.receipts) == 3
    for row in verified.batch.rows:
        scores = {s.metric: s.value for s in row.report.report.scores}
        assert scores["correct"] == scores["recovery"] == scores["duplicate_delivery"] == 1
        with app[0].connect() as admin:
            name = row.state_ref.split(":", 1)[1]
            assert not admin.execute(
                "SELECT 1 FROM pg_database WHERE datname=%s", (name,)
            ).fetchone()
            assert not admin.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (name,)).fetchone()
