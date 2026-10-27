"""Explicit continuation preserves failed probe and permits only the unused schema canary."""

import json
import sqlite3
from datetime import UTC, datetime

import httpx
import pytest
from agent_harness.contracts import ModelMessage
from agent_harness.gateway import failed_response
from agent_harness.gemini import GeminiTransport
from agent_harness.paired_budget import (
    AvailabilityOverride,
    append_availability,
    record_canary_pass,
)
from agent_harness.paired_worker import PairedWorker
from agent_harness.provider_budget import AttemptLedger
from agent_harness.release_contracts import pin
from test_paired_budget import activate, context_for, fixture
from test_provider_budget_accounting import response


def test_override_keeps_failed_first_probe_and_requires_matching_second_receipt(tmp_path):
    old, ctx, grant, canaries, domain = fixture(tmp_path)
    store = activate(old, grant)
    first = next(s for s in grant.slots if s.request_sha256 == pin(canaries[0]))
    timeout = failed_response(canaries[0], "timeout", "Invented first failure", dispatched=True)
    store.settle(
        store.reserve(context_for(ctx, grant, first), canaries[0], project_sha256="a" * 64), timeout
    )
    policy = AvailabilityOverride(
        authorization_ref="invented-explicit-continuation",
        paired_extension_sha256=store.paired_extension_sha256,
        failed_first_response_sha256=pin(timeout),
        failed_report_sha256="b" * 64,
        representative_request_sha256=pin(canaries[1]),
        approved_at=datetime.now(UTC),
    )
    with pytest.raises(ValueError):
        append_availability(
            store, policy.model_copy(update={"failed_first_response_sha256": "f" * 64}), timeout
        )
    newpin = append_availability(store, policy, timeout)
    updated = AttemptLedger(
        store.path,
        store.allowance_sha256,
        store.amendment_sha256,
        store.development_extension_sha256,
        store.paired_extension_sha256,
        newpin,
    )
    with pytest.raises(ValueError, match="current external pin"):
        store.summary()
    ds, dr = domain[0]
    with pytest.raises(ValueError, match="must pass"):
        updated.reserve(context_for(ctx, grant, ds), dr, project_sha256="a" * 64)
    second = next(s for s in grant.slots if s.request_sha256 == pin(canaries[1]))
    good = response(canaries[1]).model_copy(
        update={
            "output": ModelMessage(
                role="assistant", content='{"decision":"accept","evidence_ids":["s0"]}'
            )
        }
    )
    ticket = updated.reserve(context_for(ctx, grant, second), canaries[1], project_sha256="a" * 64)
    updated.settle(ticket, good)
    record_canary_pass(updated, canaries[1], good)
    updated.reserve(context_for(ctx, grant, ds), dr, project_sha256="a" * 64)
    with pytest.raises((ValueError, sqlite3.IntegrityError)):
        updated.reserve(context_for(ctx, grant, first), canaries[0], project_sha256="a" * 64)
    with updated.connect() as db:
        assert db.execute("SELECT response_pin FROM attempts WHERE serial=342").fetchone() == (
            pin(timeout),
        )
        assert db.execute("SELECT count(*) FROM paired_canary_passes").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM development_slots").fetchone()[0] == 21
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            db.execute("DELETE FROM paired_availability")
    assert updated.summary()["maximum"] == 418 and updated.summary()["consumed"] == 344


def test_actual_sdk_long_window_is_explicit_and_legacy_default_is_still30():
    from agent_harness.paired_budget import canary_requests

    timeouts = []

    def handler(req):
        timeouts.append(req.extensions["timeout"]["read"])
        assert json.loads(req.content)["generationConfig"]["maxOutputTokens"] == 512
        return httpx.Response(
            200,
            json={
                "modelVersion": "gemini-3.5-flash-lite",
                "candidates": [
                    {
                        "finishReason": "STOP",
                        "content": {"role": "model", "parts": [{"text": '{"answer":8}'}]},
                    }
                ],
                "usageMetadata": {
                    "promptTokenCount": 10,
                    "candidatesTokenCount": 4,
                    "totalTokenCount": 14,
                },
            },
        )

    for options in ({}, {"http_timeout_seconds": 90}):
        r = GeminiTransport(
            "invented",
            free_tier_confirmed=True,
            http_transport=httpx.MockTransport(handler),
            **options,
        ).generate(canary_requests()[0], timeout_seconds=110)
        assert r.failure is None
    assert timeouts == [30.0, 90.0]
    with pytest.raises(ValueError):
        GeminiTransport("invented", free_tier_confirmed=True, http_timeout_seconds=91)
    r = GeminiTransport(
        "invented",
        free_tier_confirmed=True,
        flash_comparison=True,
        http_timeout_seconds=90,
        http_transport=httpx.MockTransport(handler),
    ).generate(canary_requests()[0].model_copy(update={"model": "gemini-3.8-flash"}))
    assert r.failure and r.usage.model_calls == 0 and timeouts == [30.0, 90.0]
    assert "invented-private" not in repr(PairedWorker("invented-private", True))


def test_actual_gateway_and_controlled_call_roundtrip_preserve_explicit110_policy():
    from datetime import timedelta

    from agent_harness.admission import GeminiFreeAdmission
    from agent_harness.controls import BoundedGateway, ExecutionPolicy, SharedControls
    from agent_harness.offline_example import example_context
    from agent_harness.paired_budget import canary_requests
    from agent_harness.paired_worker import PairedExecutionPolicy

    class FakeAttempt:
        def generate(self, context, request, *, timeout_seconds):
            assert 60 < timeout_seconds <= 110
            return response(request)

    context = example_context("invented", "a" * 64)
    context = context.model_copy(
        update={
            "mode": "fresh_candidate",
            "clock": datetime.now(UTC),
            "deadline": datetime.now(UTC) + timedelta(minutes=4),
            "budget": context.budget.model_copy(update={"max_tokens": 2000000}),
        }
    )
    gateway = BoundedGateway(
        FakeAttempt(),
        SharedControls(),
        GeminiFreeAdmission(free_tier_confirmed=True),
        policy=PairedExecutionPolicy(),
    )
    result = gateway.generate(context, canary_requests()[0])
    assert result.failure is None and gateway.calls[0].policy.attempt_timeout_seconds == 110
    assert gateway.calls[0].policy.max_attempts == 1
    with pytest.raises(ValueError):
        ExecutionPolicy(attempt_timeout_seconds=110)
