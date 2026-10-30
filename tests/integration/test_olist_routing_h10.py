"""Actual wider H10/SQL observations and zero-call baselines with invented text only."""

import pytest
from agent_harness.release_contracts import pin
from olist_routing_fixtures import INTENTS, ROOT, composition
from olist_support.routing_evaluation import RoutingPopulation
from olist_support.routing_h10 import (
    RoutingBaselineFactory,
    RoutingEnvironment,
    read_comparator,
    read_mock,
    record_comparator,
    record_mock,
)
from olist_support.routing_study import RoutingProtocol, assemble
from test_olist_business import app as app


@pytest.mark.parametrize("intent", INTENTS)
def test_wider_routes_have_bound_observations_sql_readback_and_owned_cleanup(app, tmp_path, intent):
    server, parent, _ = app
    _, loaded, schedule, factory = composition(intent, recovery=intent == "refund")
    output = tmp_path / "wider-mock"
    evidence = record_mock(
        schedule,
        loaded,
        factory,
        RoutingEnvironment(server, parent.workspace_key, loaded),
        output,
        candidate_sha256=pin(factory.candidate),
        source_root=ROOT,
    )
    verified = read_mock(
        output,
        loaded,
        route=factory.route,
        variant="candidate",
        evidence_sha256=pin(evidence),
        candidate_sha256=pin(factory.candidate),
    )
    assert verified.batch.complete and len(verified.receipts) == 3
    assert evidence.origin == "mock"
    for row in verified.batch.rows:
        assert not row.errors and row.report is not None
        scores = {s.metric: s.value for s in row.report.report.scores}
        assert scores["correct"] == scores["routing_safe"] == scores["duplicate_delivery"] == 1
        assert row.report.report.result.usage.model_calls == 1
        if intent == "refund":
            assert scores["recovery"] == 1
        else:
            assert "recovery" not in scores
        with server.connect() as admin:
            name = row.state_ref.removeprefix("olist-routing:")
            assert not admin.execute(
                "SELECT 1 FROM pg_database WHERE datname=%s", (name,)
            ).fetchone()
            assert not admin.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (name,)).fetchone()
    observation = next((output / "observations").glob("*.json"))
    observation.write_bytes(observation.read_bytes() + b" ")
    with pytest.raises(ValueError, match="readback"):
        read_mock(
            output,
            loaded,
            route=factory.route,
            variant="candidate",
            evidence_sha256=pin(evidence),
            candidate_sha256=pin(factory.candidate),
        )


@pytest.mark.parametrize("selected", ["rules", "always-review"])
def test_deterministic_comparators_have_no_provider_receipts_and_preserve_safe_abstention(
    app, tmp_path, selected
):
    server, parent, _ = app
    _, loaded, schedule, fresh = composition("clarify", variant=selected)
    factory = RoutingBaselineFactory(fresh.candidate, fresh.route, selected, tmp_path / "unused")
    output = tmp_path / "zero-call-baseline"
    evidence = record_comparator(
        schedule,
        loaded,
        factory,
        RoutingEnvironment(server, parent.workspace_key, loaded),
        output,
        candidate_sha256=pin(factory.candidate),
        source_root=ROOT,
    )
    verified = read_comparator(
        output,
        loaded,
        route=factory.route,
        selected=selected,
        evidence_sha256=pin(evidence),
        candidate_sha256=pin(factory.candidate),
    )
    assert verified.batch.complete and not (output / "receipts").exists()
    for row in verified.batch.rows:
        assert not row.errors
        assert row.report.report.result.usage.model_calls == 0
        scores = {s.metric: s.value for s in row.report.report.scores}
        assert scores["routing_safe"] == scores["action"] == scores["observed_review"] == 1
        assert scores["intent"] == scores["correct"] == 0


def test_legacy_model_comparator_keeps_its_own_wire_and_safe_coarse_outcome(app, tmp_path):
    server, parent, _ = app
    label, loaded, schedule, factory = composition("clarify", variant="legacy")
    output = tmp_path / "legacy-mock"
    evidence = record_mock(
        schedule,
        loaded,
        factory,
        RoutingEnvironment(server, parent.workspace_key, loaded),
        output,
        candidate_sha256=pin(factory.candidate),
        source_root=ROOT,
    )
    verified = read_mock(
        output,
        loaded,
        route=factory.route,
        variant="legacy",
        evidence_sha256=pin(evidence),
        candidate_sha256=pin(factory.candidate),
    )
    assert len(verified.receipts) == 3
    for row in verified.batch.rows:
        scores = {s.metric: s.value for s in row.report.report.scores}
        assert scores["action"] == scores["routing_safe"] == 1
        assert scores["intent"] == scores["correct"] == 0
    population = RoutingPopulation(entries=(label,))
    pins = {
        v: str(i) * 64 for i, v in enumerate(("candidate", "legacy", "rules", "always-review"), 1)
    }
    pins["legacy"] = pin(factory.candidate)
    protocol = RoutingProtocol(
        population_sha256=pin(population),
        manifest_sha256=loaded.pin.sha256,
        candidate_sha256=pins,
        trial_ids=schedule.trial_ids,
    )
    summary = assemble(protocol, population, {"legacy": verified})
    assert summary["observed"] == 3 and summary["missing"] == 9
    assert summary["variants"]["legacy"]["fields"]["action"]["correct"] == 3
    assert summary["variants"]["legacy"]["fields"]["intent"]["incorrect"] == 3
    assert summary["variants"]["legacy"]["trial_latency_complete"]
    assert not summary["variants"]["legacy"]["latency_target_assessable"]
