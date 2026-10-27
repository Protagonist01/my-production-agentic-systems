"""Invented accounting, races and crash reservations; no provider calls."""

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from agent_harness.baseline_recording import zero_usage
from agent_harness.contracts import ModelMessage, ModelRequest, ModelResponse
from agent_harness.cost_accounting import AccountedTransport, FreeTariff, derive, verify_accounting
from agent_harness.offline_example import example_context
from agent_harness.provider_budget import (
    AttemptLedger,
    BudgetedTransport,
    ProviderAllowance,
    initialize,
)
from agent_harness.release_contracts import pin


def inputs(tmp_path, maximum=180, models=("gemini-3.5-flash-lite",)):
    now = datetime.now(UTC)
    allowance = ProviderAllowance(
        allowance_id="invented-shared",
        authorization_ref="invented-human-authorization",
        project_sha256="a" * 64,
        max_attempts=maximum,
        models=models,
        approved_at=now - timedelta(minutes=1),
        expires_at=now + timedelta(days=1),
    )
    path = tmp_path / "allowance.sqlite"
    ledger = AttemptLedger(path, initialize(path, allowance))
    context = example_context("invented", "b" * 64).model_copy(
        update={
            "agent_id": "olist",
            "mode": "fresh_candidate",
            "clock": now,
            "deadline": now + timedelta(minutes=5),
        }
    )
    request = ModelRequest(
        provider="google-gemini-developer-api",
        endpoint="https://generativelanguage.googleapis.com",
        model="gemini-3.5-flash-lite",
        messages=(ModelMessage(role="user", content="Invented only"),),
        parameters={},
    )
    return ledger, context, request


def tariff():
    now = datetime.now(UTC)
    return FreeTariff(
        source_snapshot_sha256="c" * 64,
        project_sha256="a" * 64,
        free_project_attestation_ref="invented-billing-disabled-attestation",
        review_ref="invented-pricing-review",
        reviewed_at=now - timedelta(minutes=1),
        expires_at=now + timedelta(days=1),
        models=("gemini-3.5-flash-lite",),
    )


def response(request):
    return ModelResponse(
        provider=request.provider,
        model=request.model,
        output=ModelMessage(role="assistant", content="Invented"),
        usage=zero_usage("USD").model_copy(
            update={
                "model_calls": 1,
                "input_tokens": 4,
                "output_tokens": 2,
                "cost": None,
                "cost_currency": None,
            }
        ),
        provider_usage={"prompt_tokens": 4, "candidate_tokens": 2, "total_tokens": 6},
    )


def test_shared_180_allowance_is_atomic_across_agents_reopens_and_never_refunds(tmp_path):
    ledger, context, request = inputs(tmp_path)

    def reserve(i):
        try:
            return ledger.reserve(
                context.model_copy(update={"agent_id": ("olist", "cfpb", "revenue")[i % 3]}),
                request,
                project_sha256="a" * 64,
            )
        except ValueError:
            return None
        except sqlite3.OperationalError as error:
            # A bounded writer wait may deny availability; never hide other SQL faults.
            if error.sqlite_errorcode not in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED):
                raise
            return None

    with ThreadPoolExecutor(max_workers=8) as pool:
        tickets = list(pool.map(reserve, range(200)))
    received = {t for t in tickets if t}
    assert 0 < len(received) <= 180
    reopened = AttemptLedger(ledger.path, ledger.allowance_sha256)
    assert reopened.summary()["consumed"] == len(received)
    remaining = reopened.summary()["remaining"]
    assert type(remaining) is int
    # Safe denials under contention need not fill the allowance; finish after writers exit.
    for _ in range(remaining):
        received.add(reopened.reserve(context, request, project_sha256="a" * 64))
    assert len(received) == 180
    assert reopened.summary()["remaining"] == 0 and reopened.summary()["unsettled"] == 180
    reopened.settle(next(iter(received)), response(request))
    assert reopened.summary()["remaining"] == 0 and reopened.summary()["unsettled"] == 179
    with pytest.raises(ValueError):
        reopened.settle(next(iter(received)), response(request))
    with pytest.raises(FileExistsError):
        initialize(
            ledger.path,
            ProviderAllowance(
                allowance_id="reset",
                authorization_ref="reset",
                project_sha256="a" * 64,
                models=("gemini-3.5-flash-lite",),
                approved_at=datetime.now(UTC),
                expires_at=datetime.now(UTC) + timedelta(days=1),
            ),
        )


def test_real_writer_lock_denies_dispatch_and_does_not_consume(tmp_path, monkeypatch):
    ledger, context, request = inputs(tmp_path, maximum=1)
    connect = AttemptLedger.connect

    def short_wait(self):
        db = connect(self)
        db.execute("PRAGMA busy_timeout=1")
        return db

    class Counting:
        calls = 0

        def generate(self, request, *, timeout_seconds=30):
            self.calls += 1
            return response(request)

    monkeypatch.setattr(AttemptLedger, "connect", short_wait)
    delegate = Counting()
    transport = BudgetedTransport(delegate, ledger, context, "a" * 64)
    locker = sqlite3.connect(ledger.path)
    try:
        locker.execute("BEGIN IMMEDIATE")
        denied = transport.generate(request)
        assert denied.failure.code == "budget_exhausted" and denied.usage.model_calls == 0
        assert delegate.calls == 0
    finally:
        locker.rollback()
        locker.close()
    assert ledger.summary()["consumed"] == 0
    assert transport.generate(request).failure is None
    assert ledger.summary()["consumed"] == 1 and ledger.summary()["unsettled"] == 0
    assert transport.generate(request).failure.code == "budget_exhausted"
    assert delegate.calls == 1


@pytest.mark.parametrize(
    "change", ["project", "provider", "endpoint", "model", "mode", "agent", "expired", "pin"]
)
def test_wrong_scope_denies_before_reservation(tmp_path, change):
    ledger, ctx, req = inputs(tmp_path)
    project = "a" * 64
    if change == "project":
        project = "d" * 64
    elif change == "mode":
        ctx = ctx.model_copy(update={"mode": "offline_fake"})
    elif change == "agent":
        ctx = ctx.model_copy(update={"agent_id": "prior-auth"})
    elif change == "expired":
        ctx = ctx.model_copy(update={"deadline": datetime.now(UTC) - timedelta(seconds=1)})
    elif change == "pin":
        ledger = AttemptLedger(ledger.path, "e" * 64)
    else:
        req = req.model_copy(update={change: "wrong"})
    with pytest.raises(ValueError):
        ledger.reserve(ctx, req, project_sha256=project)


class Throwing:
    def generate(self, request, *, timeout_seconds=30):
        raise RuntimeError("invented interrupted dispatch")


def test_interrupted_transport_keeps_consumed_unknown_reservation(tmp_path):
    ledger, ctx, req = inputs(tmp_path, 1)
    transport = BudgetedTransport(Throwing(), ledger, ctx, "a" * 64)
    with pytest.raises(RuntimeError):
        transport.generate(req)
    assert ledger.summary()["consumed"] == ledger.summary()["unsettled"] == 1
    denied = transport.generate(req)
    assert denied.failure.code == "budget_exhausted" and denied.usage.model_calls == 0


def test_derived_cost_retains_raw_unknown_and_raw_provider_tokens(tmp_path):
    _, _, req = inputs(tmp_path)
    policy = tariff()
    raw = response(req)
    assert "accounting" not in raw.model_dump(mode="json")
    result = derive(req, raw, policy, pin(policy), "a" * 64, now=datetime.now(UTC))
    verify_accounting(req, result)
    assert raw.usage.cost is None and result.usage.cost == Decimal(0)
    assert result.accounting["raw_usage"]["cost"] is None
    assert result.provider_usage == raw.provider_usage
    assert "not-provider-billing" in result.accounting["basis"]
    with pytest.raises(ValueError):
        verify_accounting(
            req,
            result.model_copy(
                update={"usage": result.usage.model_copy(update={"output_tokens": 999})}
            ),
        )
    unknown = raw.model_copy(update={"usage": raw.usage.model_copy(update={"output_tokens": None})})
    assert (
        derive(req, unknown, policy, pin(policy), "a" * 64, now=datetime.now(UTC)).usage.cost
        is None
    )


@pytest.mark.parametrize("change", ["project", "pin", "expired", "tools"])
def test_tariff_denies_mismatched_or_unreviewed_cost_policy_before_transport(tmp_path, change):
    _, _, req = inputs(tmp_path)
    p = tariff()
    project = "a" * 64
    digest = pin(p)
    if change == "project":
        project = "b" * 64
    elif change == "pin":
        digest = "d" * 64
    elif change == "expired":
        p = p.model_copy(update={"expires_at": datetime.now(UTC) - timedelta(seconds=1)})
        digest = pin(p)
    else:
        from agent_harness.contracts import ToolSchema

        req = req.model_copy(
            update={"tools": (ToolSchema(name="invented", description="invented", parameters={}),)}
        )
    with pytest.raises(ValueError):
        AccountedTransport(Throwing(), p, digest, project).generate(req)


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf")])
def test_invalid_timeout_does_not_dispatch_or_consume(tmp_path, timeout):
    ledger, context, request = inputs(tmp_path)
    with pytest.raises(ValueError, match="timeout"):
        BudgetedTransport(Throwing(), ledger, context, "a" * 64).generate(
            request, timeout_seconds=timeout
        )
    assert ledger.summary()["consumed"] == 0


def test_capture_controls_bind_cost_allowance_and_project_without_exposing_key(
    tmp_path, monkeypatch
):
    from agent_harness.provider_capture import GeminiCaptureControls

    ledger, context, request = inputs(tmp_path, maximum=2)
    policy = tariff()
    controls = GeminiCaptureControls("invented-placeholder", ledger, policy, pin(policy), "a" * 64)
    assert "invented-placeholder" not in repr(controls)

    class InventedTransport:
        def __init__(self, *args, **kwargs):
            pass

        def generate(self, request, *, timeout_seconds):
            return response(request)

    monkeypatch.setattr("agent_harness.gemini.GeminiTransport", InventedTransport)
    transport = controls.transport(context)
    saved = transport.generate(request)
    verify_accounting(request, saved, expected_control_sha256=controls.sha256)
    assert ledger.summary()["consumed"] == 1 and ledger.summary()["unsettled"] == 0
    assert saved.accounting["raw_usage"]["cost"] is None
    with pytest.raises(ValueError, match="reviewed provider controls"):
        verify_accounting(request, saved, expected_control_sha256="e" * 64)


def test_allowance_cli_status_and_reset_refusal_preserve_consumed_attempt(
    tmp_path, monkeypatch, capsys
):
    import json

    from agent_harness.provider_budget import main

    ledger, context, request = inputs(tmp_path)
    with ledger.connect() as db:
        allowance = ledger.authorization(db)
    source = tmp_path / "invented-allowance.json"
    source.write_text(allowance.canonical_json(), encoding="utf-8")
    ledger.reserve(context, request, project_sha256="a" * 64)
    common = ["--ledger", str(ledger.path), "--allowance-sha256", ledger.allowance_sha256]
    monkeypatch.setattr("sys.argv", ["budget", "status", *common])
    assert main() == 0
    assert json.loads(capsys.readouterr().out)["consumed"] == 1
    monkeypatch.setattr("sys.argv", ["budget", "initialize", *common, "--allowance", str(source)])
    assert main() == 2
    assert ledger.summary()["consumed"] == 1
    assert "refused" in capsys.readouterr().err
