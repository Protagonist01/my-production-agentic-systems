"""Actual owned worker -> SDK fake HTTP -> shared ledger -> SQL -> receipt/read-back."""

import pytest
from agent_harness.release_contracts import pin
from agent_harness.trials import TrialJournal
from olist_routing_fixtures import ROOT
from olist_support.routing_h10 import RoutingEnvironment
from olist_support.routing_provider import capture_canary, read_controlled, record_controlled
from routing_provider_fixtures import batch_for, context_for, pass_canaries, setup_scope
from routing_provider_fixtures import settled_history as settled_history
from test_olist_business import app as app


def test_real_sdk_worker_sql_and_accounting_receipts_remain_mock_and_scope_bound(
    app, tmp_path, settled_history
):
    server, parent, _ = app
    scope = setup_scope(settled_history, tmp_path / "invented-allowance.sqlite")
    _, store, _, _, requests, _, controls, *_ = scope
    for n in (1, 2):
        report = capture_canary(
            context_for(scope, n),
            requests[n],
            controls,
            tmp_path / ("canary-" + str(n)),
            source_root=ROOT,
        )
        assert report["passed"] and report["origin"] == "mock"
    for start in (3, 6):
        loaded, schedule, factory = batch_for(scope, start)
        output = tmp_path / ("mock-controlled-" + str(start))
        evidence = record_controlled(
            schedule,
            loaded,
            factory,
            RoutingEnvironment(server, parent.workspace_key, loaded),
            output,
            candidate_sha256=pin(factory.candidate),
            source_root=ROOT,
        )
        assert evidence.origin == "mock"
        verified = read_controlled(
            output,
            loaded,
            route=factory.route,
            variant=factory.variant,
            expected_origin="mock",
            control_sha256=controls.sha256,
            evidence_sha256=pin(evidence),
            candidate_sha256=pin(factory.candidate),
        )
        assert verified.batch.complete and len(verified.receipts) == 3
        for row in verified.batch.rows:
            assert not row.errors and row.report is not None
            scores = {s.metric: s.value for s in row.report.report.scores}
            assert scores["correct"] == scores["routing_safe"] == scores["duplicate_delivery"] == 1
            assert row.report.report.result.usage.input_tokens == 3
            assert row.report.report.result.usage.output_tokens == 5
            with server.connect() as admin:
                database = row.state_ref.removeprefix("olist-routing:")
                assert not admin.execute(
                    "SELECT 1 FROM pg_database WHERE datname=%s", (database,)
                ).fetchone()
                assert not admin.execute(
                    "SELECT 1 FROM pg_roles WHERE rolname=%s", (database,)
                ).fetchone()
        with pytest.raises(ValueError, match="origin"):
            read_controlled(
                output,
                loaded,
                route=factory.route,
                variant=factory.variant,
                expected_origin="provider",
                control_sha256=controls.sha256,
                evidence_sha256=pin(evidence),
                candidate_sha256=pin(factory.candidate),
            )
        with pytest.raises(ValueError, match="controls|candidate"):
            read_controlled(
                output,
                loaded,
                route=factory.route,
                variant=factory.variant,
                expected_origin="mock",
                control_sha256="a" * 64,
                evidence_sha256=pin(evidence),
                candidate_sha256=pin(factory.candidate),
            )
    assert store.summary()["consumed"] == 425 and store.summary()["unsettled"] == 0


def test_independent_scorer_stops_after_unsafe_effect_and_retains_later_missing_dispatches(
    app, tmp_path, settled_history
):
    server, parent, _ = app
    scope = setup_scope(
        settled_history, tmp_path / "invented-unsafe.sqlite", first_intent="clarify"
    )
    _, store, *_ = scope
    pass_canaries(scope)
    loaded, schedule, factory = batch_for(scope, 3)
    output = tmp_path / "mock-unsafe"
    evidence = record_controlled(
        schedule,
        loaded,
        factory,
        RoutingEnvironment(server, parent.workspace_key, loaded),
        output,
        candidate_sha256=pin(factory.candidate),
        source_root=ROOT,
    )
    assert evidence.origin == "mock"
    batch = TrialJournal(output / "journal").read(loaded)
    assert len(batch.rows) == 3
    scores = {s.metric: s.value for s in batch.rows[0].report.report.scores}
    assert scores["state_safety"] == scores["routing_safe"] == 0
    assert store.summary()["consumed"] == 420
    with store.connect() as db:
        assert db.execute("SELECT reason FROM routing_stops").fetchone() == (
            "unsafe_or_unknown_state",
        )
    with pytest.raises(ValueError):
        store.reserve(context_for(scope, 4), scope[4][4], project_sha256="a" * 64)
