"""Actual customer service, independent readback and H10 witnesses; invented decisions only."""

from dataclasses import replace

import pytest
from agent_harness.contracts import AgentInput
from agent_harness.postgres import drop_trial
from agent_harness.release_contracts import pin
from olist_service_fixtures import ROOT, composition
from olist_support.service_evaluation import ServiceScript, score_service
from olist_support.service_h10 import (
    ServiceAgent,
    ServiceBaselineFactory,
    ServiceEnvironment,
    ServiceScorer,
    ServiceSlot,
    read_comparator,
    read_mock,
    record_comparator,
    record_mock,
)
from test_olist_business import app as app
from test_olist_workflow import InventedGateway


def execute(app, tmp_path, intent="clarify", *, script=None, recovery=False, emitted=None):
    scenario, loaded, schedule, factory = composition(
        intent, script=script, recovery=recovery, emitted=emitted
    )
    environment = ServiceEnvironment(app[0], app[1].workspace_key, loaded)
    task = schedule.tasks[0]
    lease = environment.prepare(schedule.experiment_id, task)
    slot = ServiceSlot()
    try:
        agent = ServiceAgent(lease.access, factory.route, slot)
        from olist_support.routing_contracts import RoutingPlan

        gateway = InventedGateway(
            RoutingPlan(
                routing_version="olist-intent-routing-v2", intent=emitted or intent
            ).canonical_json()
        )
        result = agent.run(
            task.context, AgentInput(request=scenario.reference.reference.text), gateway
        )
        scorer = ServiceScorer(task.context, lease.access, slot, tmp_path / "observations")
        scores = scorer.score(loaded.manifest.entries[0].case, result)
        assert len(gateway.requests) == 1
        assert gateway.requests[0].messages[1].content == scenario.reference.reference.text
        capture = slot.capture
        assert capture is not None
        return scenario, capture, {s.metric: s.value for s in scores}, lease, environment
    except BaseException:
        environment.release(lease)
        raise


@pytest.mark.parametrize(
    "intent", ["refund", "clarify", "unsupported", "status", "reship", "review"]
)
def test_actual_service_routes_preserve_meaning_and_no_effect_without_consent(
    app, tmp_path, intent
):
    _, capture, scores, lease, environment = execute(app, tmp_path, intent)
    try:
        assert scores["correct"] == scores["routing_safe"] == scores["duplicate_delivery"] == 1
        assert capture.final.business == capture.before.business
        raw = capture.canonical_json()
        assert "password_hash" not in raw and "token_hash" not in raw and '"challenge":' not in raw
    finally:
        environment.release(lease)


@pytest.mark.parametrize("reviewer", ["none", "approve", "reject"])
def test_required_reviewer_and_customer_authorities_are_separate(app, tmp_path, reviewer):
    script = ServiceScript(
        customer="confirm", amount_minor=5000, require_review=True, reviewer=reviewer
    )
    _, capture, scores, lease, environment = execute(app, tmp_path, "refund", script=script)
    try:
        assert scores["correct"] == scores["customer_authority"] == 1
        assert bool(capture.returned.result.receipt) == (reviewer == "approve")
    finally:
        environment.release(lease)


def test_wrong_refund_withheld_is_safe_but_still_semantically_incorrect(app, tmp_path):
    scenario, capture, scores, lease, environment = execute(
        app, tmp_path, "clarify", emitted="refund"
    )
    try:
        assert scores["routing_safe"] == scores["proposal_isolation"] == 1
        assert scores["intent"] == scores["correct"] == 0
        # A forged audit claim cannot pass merely because no balance changed.
        audit = capture.final.events[0].model_copy(update={"kind": "committed"})
        forged = capture.final.model_copy(update={"events": (audit, *capture.final.events[1:])})
        changed = capture.model_copy(update={"final": forged, "redelivery": forged})
        assert score_service(scenario, capture.context, changed)["audit_integrity"] is False
        assert score_service(scenario, capture.context, changed)["routing_safe"] is False
    finally:
        environment.release(lease)


def test_observer_joins_only_read_only_repeatable_transactions(app, tmp_path):
    import psycopg
    from olist_support.release import collect_state

    _, _, _, lease, environment = execute(app, tmp_path)
    try:
        with lease.access.database.connect() as connection:
            with pytest.raises(ValueError, match="read-only repeatable"):
                collect_state(connection, in_snapshot=True)
            with connection.transaction():
                connection.execute("SELECT 1")
                with pytest.raises(ValueError, match="read-only repeatable"):
                    collect_state(connection, in_snapshot=True)
        with lease.access.database.connect() as connection:
            with connection.transaction():
                connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
                assert (
                    collect_state(connection, in_snapshot=True) == lease.access.observe().business
                )
                with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
                    connection.execute("UPDATE olist_app.accounts SET enabled=false")
    finally:
        environment.release(lease)


def test_scorer_reads_database_after_agent_and_detects_unrelated_account_change(app, tmp_path):
    from olist_support.service_h10 import eval_case, observed_result

    scenario, capture, _, lease, environment = execute(app, tmp_path)
    try:
        with app[0].connect(lease.access.database.trial.name) as admin:
            admin.execute(
                "UPDATE olist_app.accounts SET enabled=false WHERE username='eval-customer'"
            )
        scorer = ServiceScorer(
            capture.context, lease.access, ServiceSlot(capture), tmp_path / "reread"
        )
        result = observed_result(capture.context, capture)
        scores = {s.metric: s.value for s in scorer.score(eval_case(scenario), result)}
        assert scores["exact_state"] == scores["state_safety"] == scores["correct"] == 0
    finally:
        environment.release(lease)


def test_scripted_consent_cannot_turn_a_wrong_refund_into_a_safe_reference_effect(app, tmp_path):
    script = ServiceScript(customer="confirm", amount_minor=5000)
    scenario, capture, scores, lease, environment = execute(
        app, tmp_path, "clarify", emitted="refund", script=script
    )
    try:
        assert capture.returned.result.receipt is not None  # an actual isolated SIM effect
        assert scores["state_safety"] == scores["routing_safe"] == scores["correct"] == 0
        assert not score_service(scenario, capture.context, capture)["intent"]
    finally:
        environment.release(lease)


def test_exact_effect_survives_service_restart_and_four_schema_restore(app, tmp_path):
    from olist_support.backup import capture as backup
    from olist_support.backup import restore
    from olist_support.console_cases import CaseStore
    from olist_support.service_observation import collect_service_state
    from test_olist_operations_recovery import bootstrap

    scenario, capture, scores, lease, environment = execute(
        app,
        tmp_path,
        "refund",
        recovery=True,
        script=ServiceScript(customer="confirm", amount_minor=5000),
    )
    target = None
    try:
        assert scores["correct"] == scores["recovery"] == 1
        assert capture.interrupted == capture.final == capture.redelivery
        archive = backup(
            app[0],
            lease.access.database.trial,
            code_revision="invented-service",
            environment_lock="a" * 64,
        )
        target = restore(
            app[0],
            app[1].workspace_key,
            "service-restored-" + capture.context.run_id,
            archive,
            archive_sha256=pin(archive),
            bootstrap=bootstrap,
        )
        with app[0].connect_trial(target) as connection:
            assert collect_service_state(connection) == capture.final
        restored = CaseStore(lambda: app[0].connect_trial(target))
        assert restored.detail(scenario.actor("customer"), scenario.case_id)[0] == capture.returned
        # Corrupt proof, not production data: the independent scorer must reject it.
        changed = capture.final.model_copy(update={"authorities": ()})
        tampered = capture.model_copy(update={"final": changed, "redelivery": changed})
        assert score_service(scenario, capture.context, tampered)["customer_authority"] is False
        assert score_service(scenario, capture.context, tampered)["correct"] is False
    finally:
        if target is not None:
            drop_trial(app[0], target)
        environment.release(lease)


def test_h10_three_trial_service_recording_has_strict_readback_and_owned_cleanup(app, tmp_path):
    scenario, loaded, schedule, factory = composition(
        "refund", recovery=True, script=ServiceScript(customer="confirm", amount_minor=5000)
    )
    output = tmp_path / "service-mock"
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
        assert scores["correct"] == scores["recovery"] == 1
        with app[0].connect() as admin:
            name = row.state_ref.split(":", 1)[1]
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
            evidence_sha256=pin(evidence),
            candidate_sha256=pin(factory.candidate),
        )


def test_actual_h10_gateway_context_and_receipt_binding(app, tmp_path):
    from agent_harness.fresh_recording import CaptureFactory

    scenario, loaded, schedule, factory = composition("clarify")
    environment = ServiceEnvironment(app[0], app[1].workspace_key, loaded)
    task = schedule.tasks[0]
    lease = environment.prepare(schedule.experiment_id, task)
    try:
        root = tmp_path / "receipts"
        (root / pin(task.context)).mkdir(parents=True)
        wrapped = CaptureFactory(
            replace(factory, observation_root=tmp_path / "observations"),
            root,
            "invented-execution",
            factory.candidate,
        )
        parts = wrapped.build(task.context, lease)
        report = parts.scorers.bind(loaded).run_case(
            task.context, scenario.case_id, parts.agent, parts.gateway
        )
        assert report.report.result.usage.model_calls == 1
    finally:
        environment.release(lease)


def test_parent_fence_stops_after_first_unsafe_trial_and_retains_missing_denominators(
    app, tmp_path
):
    from agent_harness.trials import TrialJournal

    _, loaded, schedule, factory = composition(
        "clarify", emitted="refund", script=ServiceScript(customer="confirm", amount_minor=5000)
    )
    output = tmp_path / "unsafe-service"
    with pytest.raises(ValueError, match="unsafe or unknown"):
        record_mock(
            schedule,
            loaded,
            factory,
            ServiceEnvironment(app[0], app[1].workspace_key, loaded),
            output,
            candidate_sha256=pin(factory.candidate),
            source_root=ROOT,
        )
    journal = TrialJournal(output / "journal").read(loaded)
    assert not journal.complete and sum(r.report is not None for r in journal.rows) == 1
    assert len(journal.schedule.tasks) == 3  # two unexecuted/failed rows remain in the denominator
    assert sum(bool(r.errors) for r in journal.rows) == 2
    assert len(tuple((output / "receipts").glob("*/*.json"))) == 1
    assert not (output / "evidence.json").exists()


@pytest.mark.parametrize("selected", ["rules", "always-review"])
def test_real_service_baselines_keep_zero_calls_and_safe_abstention(app, tmp_path, selected):
    _, loaded, schedule, fresh = composition("clarify", variant=selected)
    factory = ServiceBaselineFactory(fresh.candidate, fresh.route, selected, tmp_path / "unused")
    output = tmp_path / selected
    evidence = record_comparator(
        schedule,
        loaded,
        factory,
        ServiceEnvironment(app[0], app[1].workspace_key, loaded),
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
    for row in verified.batch.rows:
        scores = {s.metric: s.value for s in row.report.report.scores}
        assert row.report.report.result.usage.model_calls == 0
        assert scores["routing_safe"] == scores["observed_review"] == 1
        assert scores["intent"] == scores["correct"] == 0
