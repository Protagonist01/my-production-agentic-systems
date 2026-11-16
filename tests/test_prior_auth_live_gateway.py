"""Invented same-file ledger, exact slots, shared stop and Gemini-only admission."""

import json
import sqlite3
from datetime import UTC, datetime, timedelta

import pytest
from agent_harness.contracts import ModelMessage, ModelResponse, Usage
from test_prior_auth_review import policy

from prior_auth_demo_fixtures import note, requests
from prior_auth_demo_runtime import Scope
from prior_auth_live_gateway import (
    Grant,
    LiveGateway,
    Slot,
    history,
    initialize,
    scope_binding,
)


def historical_ledger(tmp_path):
    path = tmp_path / "existing.sqlite"
    with sqlite3.connect(path) as c:
        c.execute("CREATE TABLE attempts(id INTEGER PRIMARY KEY,response_pin TEXT)")
        c.executemany("INSERT INTO attempts VALUES(?,?)", [(i, "historical") for i in range(447)])
        c.execute("CREATE TABLE pa_reservations(id INTEGER PRIMARY KEY)")
        c.execute("CREATE TABLE pa_settlements(id INTEGER PRIMARY KEY)")
        for table in ("pa_reservations", "pa_settlements"):
            c.executemany("INSERT INTO " + table + " VALUES(?)", [(i,) for i in range(168)])
        c.execute("CREATE TABLE pa_stops(id INTEGER PRIMARY KEY)")
        c.execute("CREATE TABLE authorization(document TEXT)")
        c.execute(
            "INSERT INTO authorization VALUES(?)", (json.dumps({"project_sha256": "b" * 64}),)
        )
        original = history(c)
    return path, original


def setup(tmp_path):
    path, original = historical_ledger(tmp_path)
    now = datetime.now(UTC)
    n = note("demo-live", policy())
    request = requests((n,), policy())[0]
    scope = Scope(
        scope_id="live-test",
        tenant_id="demo",
        case_ids=("demo-live",),
        mode="fresh_candidate",
        provider_scope_sha256="f" * 64,
        authorization_ref="invented-only-test",
        code_revision="test",
        environment_sha256="a" * 64,
        starts_at=now - timedelta(seconds=1),
        expires_at=now + timedelta(hours=1),
        max_attempts=3,
        max_tokens=2000000,
        request_sha256s=(request.fingerprint(),),
    )
    grant = Grant(
        approval_ref="invented-test-not-live-authorization",
        free_project_confirmed=True,
        project_association_sha256="b" * 64,
        historical_sha256=original,
        execution_sha256="c" * 64,
        runtime_scope_sha256=scope_binding(scope),
        starts_at=scope.starts_at,
        expires_at=scope.expires_at,
        slots=tuple(
            Slot(phase=phase, case_id=n.case_id, request_sha256=request.fingerprint())
            for phase in ("canary", "canary", "domain")
        ),
    )
    ledger = initialize(path, grant)
    scope = scope.model_copy(update={"provider_scope_sha256": ledger.pin})
    response = ModelResponse(
        provider=request.provider,
        model=request.model,
        output=ModelMessage(role="assistant", content="invented"),
        usage=Usage(model_calls=1, input_tokens=10, output_tokens=2, cost=None, cost_currency=None),
    )
    return path, ledger, scope, request, response, original


def test_exact_order_two_canaries_and_prior_history_are_preserved(tmp_path):
    path, ledger, scope, request, response, original = setup(tmp_path)
    with pytest.raises(PermissionError):
        ledger.reserve("demo-live", request, phase="domain", now=datetime.now(UTC))
    for i in (1, 2):
        assert ledger.reserve("demo-live", request, phase="canary", now=datetime.now(UTC)) == i
        with pytest.raises(PermissionError):
            ledger.reserve("demo-live", request, phase="canary", now=datetime.now(UTC))
        ledger.settle(i, response, canary_pass=True)
    assert ledger.reserve("demo-live", request, phase="domain", now=datetime.now(UTC)) == 3
    ledger.settle(3, response, canary_pass=False)
    assert ledger.summary() == {
        "historical_consumed": 615,
        "new_consumed": 3,
        "total_consumed": 618,
        "lifetime_ceiling": 952,
        "unsettled": 0,
        "stopped": False,
        "old_history_unchanged": True,
        "old_bound_slots_preserved": 169,
        "known_token_subtotal": 36,
        "unknown_token_settlements": 0,
        "known_subtotals_are_not_complete_cost": True,
    }
    with sqlite3.connect(path) as c:
        assert history(c) == original
        with pytest.raises(sqlite3.IntegrityError):
            c.execute("DELETE FROM pa_live_attempts")
    with pytest.raises(PermissionError):
        ledger.reserve("demo-live", request, phase="domain", now=datetime.now(UTC))


def test_unknown_usage_or_failed_canary_stops_without_retry(tmp_path):
    _, ledger, scope, request, response, _ = setup(tmp_path)
    assert ledger.reserve("demo-live", request, phase="canary", now=datetime.now(UTC)) == 1
    unknown = response.model_copy(
        update={
            "usage": Usage(
                model_calls=1, input_tokens=None, output_tokens=None, cost=None, cost_currency=None
            )
        }
    )
    ledger.settle(1, unknown, canary_pass=True)
    assert ledger.summary()["stopped"]
    with pytest.raises(PermissionError):
        ledger.reserve("demo-live", request, phase="canary", now=datetime.now(UTC))


def test_existing_new_tables_cannot_reset_and_changed_history_blocks(tmp_path):
    path, ledger, scope, request, response, _ = setup(tmp_path)
    with ledger.connect() as c:
        grant = ledger.grant(c)
    with pytest.raises(sqlite3.OperationalError):
        initialize(path, grant)
    with sqlite3.connect(path) as c:
        c.execute("UPDATE attempts SET response_pin=? WHERE id=0", ("changed",))
    with pytest.raises(ValueError):
        ledger.summary()


def test_runtime_scope_binding_has_no_reciprocal_hash_cycle_and_checks_execution(tmp_path):
    _, ledger, scope, request, response, _ = setup(tmp_path)

    class Transport:
        calls = 0

        def generate(self, *args, **kwargs):
            self.calls += 1
            return response

    transport = Transport()

    class Store:
        pass

    gateway = LiveGateway(
        Store(),
        scope,
        ledger,
        transport,
        execution_probe=lambda: "c" * 64,
        project_association_sha256="b" * 64,
    )
    gateway.validate(scope, request)
    with pytest.raises(PermissionError):
        gateway.validate(scope.model_copy(update={"max_attempts": 4}), request)
    gateway.execution_probe = lambda: "d" * 64
    with pytest.raises(PermissionError):
        gateway.validate(scope, request)
    assert not transport.calls


def test_canary_requires_actual_support_not_just_valid_json_or_exact_quote(tmp_path):
    from prior_auth.candidate import QuoteClaim

    from prior_auth_live_gateway import supported_canary

    _, _, _, request, response, _ = setup(tmp_path)
    value = note("demo-live", policy())
    for quote, expected in ((value.text, True), ("CPAP education completed prior to use.", False)):
        claim = QuoteClaim(
            criterion_id="adult_osa", state="met", quotes=(quote,), rationale="Invented canary"
        )
        current = response.model_copy(
            update={"output": ModelMessage(role="assistant", content=claim.canonical_json())}
        )
        assert supported_canary(current, request, value) is expected


def test_consumed_reservation_survives_restart_without_settlement_or_retry(tmp_path):
    from prior_auth_live_gateway import Ledger

    path, ledger, scope, request, response, _ = setup(tmp_path)
    ledger.reserve("demo-live", request, phase="canary", now=datetime.now(UTC))
    rebuilt = Ledger(path, ledger.pin)
    assert rebuilt.summary()["unsettled"] == 1
    with pytest.raises(PermissionError):
        rebuilt.reserve("demo-live", request, phase="canary", now=datetime.now(UTC))


def test_failed_canary_stops_even_with_known_usage(tmp_path):
    _, ledger, scope, request, response, _ = setup(tmp_path)
    ledger.reserve("demo-live", request, phase="canary", now=datetime.now(UTC))
    ledger.settle(1, response, canary_pass=False)
    assert ledger.summary()["stopped"]
    with pytest.raises(PermissionError):
        ledger.reserve("demo-live", request, phase="canary", now=datetime.now(UTC))


def test_factory_denies_scope_before_reading_configuration(tmp_path, monkeypatch):
    import prior_auth_live_console as console

    _, ledger, scope, request, response, _ = setup(tmp_path)
    monkeypatch.setattr(console.subprocess, "check_output", lambda *args, **kwargs: "")
    monkeypatch.setattr(console, "execution_pin", lambda root: "c" * 64)
    monkeypatch.setattr(
        console,
        "private_configuration",
        lambda path: (_ for _ in ()).throw(AssertionError("configuration accessed")),
    )
    with pytest.raises(PermissionError):
        console.open_runtime(
            console.Path(console.__file__).resolve().parent,
            None,
            scope.model_copy(update={"max_attempts": 4}),
            ledger,
            tmp_path / "absent",
        )


def test_live_demo_proposal_separates_canary_initial_and_supplement_requests():
    from prior_auth_live_draft import packet

    value = packet(policy(), now=datetime.now(UTC))
    rows = value["requests"]
    assert len(rows) == 9
    assert [row["slot"]["phase"] for row in rows] == ["canary"] * 2 + ["domain"] * 7
    payloads = [json.loads(row["request"]["messages"][1]["content"]) for row in rows]
    assert all("CPAP education completed" in p["full_note"] for p in payloads[:2])
    assert all("CPAP education completed" not in p["full_note"] for p in payloads[2:8])
    assert payloads[-1]["criterion"]["criterion_id"] == "education"
    assert "CPAP education completed" in payloads[-1]["full_note"]
    assert value["scope"].max_attempts == 7
    assert "scope.json" not in value["files"]
