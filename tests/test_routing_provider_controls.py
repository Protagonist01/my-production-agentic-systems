"""Invented ledger/SDK regression tests; no private packet, real key or provider network."""

import json
import socket
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest
from agent_harness.cost_accounting import verify_accounting
from agent_harness.gateway import failed_response
from agent_harness.provider_budget import ProviderAllowance, initialize
from agent_harness.routing_budget import RoutingExtension, stop
from olist_support.routing_h10 import RoutingMockFactory
from olist_support.routing_provider import RoutingProviderFactory
from routing_provider_fixtures import (
    acknowledge_response,
    context_for,
    pass_canaries,
    sdk_child,
    setup_scope,
    success,
)
from routing_provider_fixtures import (
    settled_history as settled_history,
)


@pytest.fixture
def scope(settled_history, tmp_path):
    return setup_scope(settled_history, tmp_path / "invented-only.sqlite")


def test_146_unique_slots_keep_417_rows_and_all_51_old_slots_unavailable(scope):
    old, store, _, extension, requests, *_ = scope
    with store.connect() as db:
        before = db.execute("SELECT * FROM attempts ORDER BY serial").fetchall()
    with pytest.raises(ValueError, match="current external pin"):
        old.summary()
    with pytest.raises(ValueError):
        store.reserve(context_for(scope, 3), requests[3], project_sha256="a" * 64)
    pass_canaries(scope)
    for n in range(3, 147):
        ticket = store.reserve(context_for(scope, n), requests[n], project_sha256="a" * 64)
        store.settle(ticket, success(requests[n], extension.slots[n - 1].variant))
    summary = store.summary()
    assert summary["maximum"] == 614 and summary["consumed"] == 563 and summary["remaining"] == 51
    with pytest.raises(ValueError, match="stopped or exhausted"):
        store.reserve(context_for(scope, 146), requests[146], project_sha256="a" * 64)
    with store.connect() as db:
        assert (
            db.execute("SELECT * FROM attempts WHERE serial<=417 ORDER BY serial").fetchall()
            == before
        )
        assert db.execute(
            "SELECT min(allocation_no),max(allocation_no),count(*) FROM routing_slots"
        ).fetchone() == (469, 614, 146)
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("DELETE FROM routing_extensions")
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("DELETE FROM routing_slots")
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("INSERT INTO attempts VALUES(564,'old-binary','c','r','now',NULL,NULL)")


def test_concurrent_duplicate_reservation_consumes_once_and_unsettled_blocks_next(scope):
    _, store, _, _, requests, *_ = scope

    def attempt(_):
        try:
            return store.reserve(context_for(scope, 1), requests[1], project_sha256="a" * 64)
        except ValueError:
            return None

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(attempt, range(4)))
    assert sum(r is not None for r in results) == 1
    assert store.summary()["consumed"] == 418 and store.summary()["unsettled"] == 1
    with pytest.raises(ValueError, match="unsettled"):
        store.reserve(context_for(scope, 2), requests[2], project_sha256="a" * 64)
    # A crash leaves a durable consumed ticket; a new process/client cannot retry it.
    reopened = replace(store)
    with pytest.raises(ValueError):
        reopened.reserve(context_for(scope, 1), requests[1], project_sha256="a" * 64)


@pytest.mark.parametrize(
    "change",
    [
        "tenant_id",
        "run_id",
        "business_event_id",
        "trial_id",
        "candidate",
        "parameters",
        "text",
        "policy",
        "snapshot",
    ],
)
def test_changed_context_or_payload_refuses_before_reservation(scope, change):
    _, store, _, _, requests, *_ = scope
    context = context_for(scope, 1)
    request = requests[1]
    if change == "candidate":
        context = context.model_copy(
            update={"versions": context.versions.model_copy(update={"candidate": "wrong"})}
        )
    elif change in ("policy", "snapshot"):
        context = context.model_copy(
            update={
                "versions": context.versions.model_copy(
                    update={"policy" if change == "policy" else "data_snapshot": "wrong"}
                )
            }
        )
    elif change == "parameters":
        request = request.model_copy(
            update={"parameters": {**request.parameters, "max_output_tokens": 513}}
        )
    elif change == "text":
        request = request.model_copy(update={"messages": ()})
    else:
        context = context.model_copy(update={change: "wrong"})
    with pytest.raises(ValueError):
        store.reserve(context, request, project_sha256="a" * 64)
    assert store.summary()["consumed"] == 417


@pytest.mark.parametrize(
    "failure", ["timeout", "rate_limited", "wrong_output", "unknown_usage", "over_limit"]
)
def test_first_failed_canary_stops_and_never_unlocks_domain(scope, failure):
    _, store, _, _, requests, *_ = scope
    r = requests[1]
    result = success(r)
    if failure in ("timeout", "rate_limited"):
        result = failed_response(r, failure, "Invented", dispatched=True)
    elif failure == "wrong_output":
        result = result.model_copy(
            update={"output": result.output.model_copy(update={"content": '{"intent":"status"}'})}
        )
    elif failure == "unknown_usage":
        result = result.model_copy(
            update={"usage": result.usage.model_copy(update={"output_tokens": None})}
        )
    else:
        result = result.model_copy(
            update={"usage": result.usage.model_copy(update={"input_tokens": 2_000_000})}
        )
    store.settle(store.reserve(context_for(scope, 1), r, project_sha256="a" * 64), result)
    assert store.summary()["consumed"] == 418
    with pytest.raises(ValueError, match="stopped"):
        store.reserve(context_for(scope, 2), requests[2], project_sha256="a" * 64)


def test_three_transient_domain_errors_stop_across_reopened_clients_and_safety_stop_persists(scope):
    _, store, _, _, requests, *_ = scope
    pass_canaries(scope)
    for n in (3, 4, 5):
        store = replace(store)
        result = failed_response(requests[n], "timeout", "Invented", dispatched=True)
        result = result.model_copy(update={"usage": success(requests[n]).usage})
        store.settle(
            store.reserve(context_for(scope, n), requests[n], project_sha256="a" * 64), result
        )
    with pytest.raises(ValueError, match="stopped"):
        store.reserve(context_for(scope, 6), requests[6], project_sha256="a" * 64)
    with store.connect() as db:
        assert db.execute("SELECT reason FROM routing_stops").fetchone() == (
            "consecutive_provider_failures",
        )
    stop(store, "unsafe_or_unknown_state")
    with store.connect() as db:
        assert db.execute("SELECT count(*) FROM routing_stops").fetchone()[0] == 1


def test_actual_sdk_accounting_is_scope_bound_with_network_denied_and_mock_origin(
    scope, monkeypatch
):
    _, store, _, ext, requests, specs, controls, _, route = scope

    def deny(*args, **kwargs):
        raise AssertionError("network forbidden in invented SDK test")

    monkeypatch.setattr(socket, "create_connection", deny)
    monkeypatch.setattr(socket, "getaddrinfo", deny)
    monkeypatch.setattr(socket.socket, "connect", deny)
    assert controls.origin == "mock"
    factory = RoutingProviderFactory(
        specs["candidate"], route, "candidate", controls, __import__("pathlib").Path("unused")
    )
    factory.validate()
    for n in (1, 2):
        context = context_for(scope, n)
        result = controls.transport(context).generate(requests[n])
        acknowledge_response(scope, n, result, context)
        assert result.failure is None and result.accounting is not None
        verify_accounting(requests[n], result, expected_control_sha256=controls.sha256)
        with pytest.raises(ValueError, match="controls"):
            verify_accounting(requests[n], result, expected_control_sha256="a" * 64)
    assert store.summary()["consumed"] == 419 and store.summary()["unsettled"] == 0
    with pytest.raises(ValueError):
        RoutingMockFactory(
            specs["candidate"], route, None, None, "candidate", __import__("pathlib").Path("unused")
        ).validate()
    assert replace(controls, test_http=None).origin == "provider"
    assert controls.sha256 == replace(controls, test_http=None).sha256
    with pytest.raises(ValueError, match="origin"):
        replace(controls, test_http=None).validate()


def test_new_614_pool_cannot_be_initialized_and_frozen_shape_rejects_interleaving(scope, tmp_path):
    _, store, _, ext, *_ = scope
    with store.connect() as db:
        raw = db.execute("SELECT document FROM authorization").fetchone()[0]
    initial = ProviderAllowance.model_validate_json(raw).model_copy(update={"max_attempts": 614})
    with pytest.raises(ValueError):
        initialize(tmp_path / "forbidden.sqlite", initial)
    assert not (tmp_path / "forbidden.sqlite").exists()
    data = json.loads(ext.canonical_json())
    data["slots"][3]["variant"] = "legacy"
    with pytest.raises(ValueError):
        RoutingExtension.model_validate_json(json.dumps(data))


def test_actual_owned_child_canary_sdk_uses_same_durable_ledger_and_fake_http(scope):
    import multiprocessing

    from agent_harness.contracts import ModelResponse
    from agent_harness.process_control import OwnedProcess

    _, store, _, _, requests, _, controls, *_ = scope
    ctx = multiprocessing.get_context("spawn")
    for n in (1, 2):
        read, write = ctx.Pipe(duplex=False)
        context = context_for(scope, n)
        child = OwnedProcess(
            ctx.Process(target=sdk_child, args=(controls, context, requests[n], write))
        )
        child.start()
        write.close()
        try:
            assert read.poll(60), "owned fake-SDK child did not return within test bound"
            response = ModelResponse.model_validate_json(read.recv())
            acknowledge_response(scope, n, response, context)
            child.join(10)
            assert child.exitcode == 0 and response.failure is None
            verify_accounting(requests[n], response, expected_control_sha256=controls.sha256)
        finally:
            if child.is_alive():
                child.terminate()
                child.join(5)
            assert not child.is_alive()
            child.close()
            read.close()
    assert store.summary()["consumed"] == 419 and store.summary()["unsettled"] == 0
    with store.connect() as db:
        rows = db.execute(
            "SELECT response_pin,document FROM routing_settlements ORDER BY ordinal"
        ).fetchall()
    from agent_harness.release_contracts import pin

    assert all(pin(ModelResponse.model_validate_json(body)) == p for p, body in rows)


def test_controlled_summary_retains_all288_missing_and_rejects_reference_substitution(scope):
    from agent_harness.release_contracts import pin
    from olist_support.controlled_study import ControlledStudyProtocol, assemble_controlled

    _, _, _, ext, _, specs, controls, pop, _ = scope
    pins = {v: pin(c) for v, c in specs.items()}
    pins.update({"rules": "a" * 64, "always-review": "b" * 64})
    protocol = ControlledStudyProtocol(
        extension=ext,
        tariff_sha256=controls.tariff_sha256,
        project_sha256=controls.project_sha256,
        candidate_sha256=pins,
        expected_origin="mock",
    )
    assert protocol.control_sha256 == controls.sha256
    result = assemble_controlled(protocol, pop, {})
    assert result["scheduled"] == result["missing"] == 288 and result["observed"] == 0
    assert result["recordings_scheduled"] == 96 and result["recordings_observed"] == 0
    assert not result["release_allowed"] and not result["semantic_gold_validated"]
    modified = pop.model_copy(update={"entries": pop.entries[1:]})
    with pytest.raises(ValueError, match="population"):
        assemble_controlled(protocol, modified, {})


def test_settled_canary_without_matching_receipt_never_unlocks_next(scope):
    _, store, _, _, requests, *_ = scope
    context = context_for(scope, 1)
    response = success(requests[1])
    store.settle(store.reserve(context, requests[1], project_sha256="a" * 64), response)
    with pytest.raises(ValueError, match="canary gate"):
        store.reserve(context_for(scope, 2), requests[2], project_sha256="a" * 64)
    wrong = context.model_copy(update={"run_id": "foreign"})
    with pytest.raises(ValueError, match="matching settled"):
        acknowledge_response(scope, 1, response, wrong)
    acknowledge_response(scope, 1, response, context)
    store.reserve(context_for(scope, 2), requests[2], project_sha256="a" * 64)
    assert store.summary()["consumed"] == 419 and store.summary()["unsettled"] == 1


@pytest.mark.parametrize(
    "output,good",
    [
        ('{"intent":"refund","routing_version":"olist-intent-routing-v2"}', True),
        (
            '{"intent":"refund","requested_minor":null,"routing_version":"olist-intent-routing-v2","schema_version":true}',
            False,
        ),
    ],
)
def test_canary_uses_runtime_optional_defaults_but_never_boolean_schema_version(
    scope, output, good
):
    _, store, _, _, requests, *_ = scope
    context = context_for(scope, 1)
    response = success(requests[1])
    response = response.model_copy(
        update={"output": response.output.model_copy(update={"content": output})}
    )
    store.settle(store.reserve(context, requests[1], project_sha256="a" * 64), response)
    with store.connect() as db:
        assert db.execute("SELECT canary_pass FROM routing_settlements").fetchone()[0] == int(good)


def test_live_factory_refuses_unpinned_source_before_database_or_output(settled_history, tmp_path):
    from agent_harness.release_contracts import pin
    from olist_routing_fixtures import ROOT
    from olist_support.routing_h10 import RoutingEnvironment
    from olist_support.routing_provider import record_controlled
    from routing_provider_fixtures import batch_for

    prepared = setup_scope(
        settled_history, tmp_path / "invented-live-refusal.sqlite", origin="provider"
    )
    loaded, schedule, factory = batch_for(prepared, 3)
    output = tmp_path / "must-not-start"
    with pytest.raises(ValueError, match="clean final candidate source"):
        record_controlled(
            schedule,
            loaded,
            factory,
            RoutingEnvironment(None, "invented", loaded),
            output,
            candidate_sha256=pin(factory.candidate),
            source_root=ROOT,
        )
    assert not output.exists() and prepared[1].summary()["consumed"] == 417


def test_parent_timeout_blocks_next_slot_even_after_first_domain_response_settled(scope, tmp_path):
    from agent_harness.trials import TrialRow
    from olist_support.routing_provider import RoutingParentFence
    from routing_provider_fixtures import batch_for

    _, store, _, _, requests, _, controls, *_ = scope
    pass_canaries(scope)
    loaded, schedule, _ = batch_for(scope, 3)
    response = controls.transport(schedule.tasks[0].context).generate(requests[3])
    assert response.failure is None
    assert store.summary()["consumed"] == 420 and store.summary()["unsettled"] == 0
    # Counterfactual invented copy proves settlement alone permits the next SDK slot.
    copied = tmp_path / "invented-unfenced-copy.sqlite"
    with store.connect() as src, sqlite3.connect(copied) as dst:
        src.backup(dst)
    unfenced = replace(store, path=copied)
    unfenced.reserve(schedule.tasks[1].context, requests[4], project_sha256="a" * 64)
    assert unfenced.summary()["consumed"] == 421

    fence = RoutingParentFence(store, loaded, schedule, tmp_path / "missing-observation")
    fence(TrialRow(task=schedule.tasks[0], errors=("timeout",)))
    assert fence.halted
    with pytest.raises(ValueError, match="stopped"):
        replace(store).reserve(schedule.tasks[1].context, requests[4], project_sha256="a" * 64)
    assert store.summary()["consumed"] == 420 and store.summary()["unsettled"] == 0
    with store.connect() as db:
        assert db.execute("SELECT reason FROM routing_stops").fetchone() == (
            "unsafe_or_unknown_state",
        )
