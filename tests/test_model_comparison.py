"""Invented model-only boundary, prior-history preservation, actual SDK and paired counts."""

import json
import sqlite3
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from agent_harness.contracts import ModelMessage
from agent_harness.gateway import failed_response
from agent_harness.model_budget import (
    MODELS,
    ModelExtension,
    ModelSlot,
    append_model_extension,
    model_canaries,
    record_model_canary,
)
from agent_harness.model_worker import ModelComparisonWorker
from agent_harness.paired_budget import (
    AvailabilityOverride,
    append_availability,
    record_canary_pass,
)
from agent_harness.provider_budget import AttemptLedger, ProviderAllowance, initialize
from agent_harness.release_contracts import pin
from revenue_integrity.model_quality import assess_model, comparison_request
from revenue_integrity.paired_quality import summarize
from test_paired_budget import activate, context_for, fixture
from test_paired_quality import sample
from test_provider_budget_accounting import response
from test_semantic_alignment import response as semantic_response
from test_semantic_alignment import value


def history(tmp_path):
    old, ctx, grant, canaries, domain = fixture(tmp_path)
    store = activate(old, grant)
    first = next(s for s in grant.slots if s.request_sha256 == pin(canaries[0]))
    timeout = failed_response(canaries[0], "timeout", "Invented", dispatched=True)
    store.settle(
        store.reserve(context_for(ctx, grant, first), canaries[0], project_sha256="a" * 64), timeout
    )
    override = AvailabilityOverride(
        authorization_ref="invented",
        paired_extension_sha256=store.paired_extension_sha256,
        failed_first_response_sha256=pin(timeout),
        failed_report_sha256="b" * 64,
        representative_request_sha256=pin(canaries[1]),
        approved_at=datetime.now(UTC),
    )
    overridepin = append_availability(store, override, timeout)
    store = AttemptLedger(
        store.path,
        store.allowance_sha256,
        store.amendment_sha256,
        store.development_extension_sha256,
        store.paired_extension_sha256,
        overridepin,
    )
    second = next(s for s in grant.slots if s.request_sha256 == pin(canaries[1]))
    good = response(canaries[1]).model_copy(
        update={
            "output": ModelMessage(
                role="assistant", content='{"decision":"accept","evidence_ids":["s0"]}'
            )
        }
    )
    store.settle(
        store.reserve(context_for(ctx, grant, second), canaries[1], project_sha256="a" * 64), good
    )
    record_canary_pass(store, canaries[1], good)
    for slot, r in domain:
        store.settle(
            store.reserve(context_for(ctx, grant, slot), r, project_sha256="a" * 64), response(r)
        )
    assert store.summary()["consumed"] == 415
    newcanaries = model_canaries()
    slots = []
    requests = []
    for r in newcanaries:
        slots.append(
            ModelSlot(
                case_id="invented-model-canary",
                model=r.model,
                request_sha256=pin(r),
                trial_id="model-canary",
                purpose="canary",
            )
        )
    for i in range(12):
        v = value(f"Invented unique {i}.")
        for m in MODELS:
            r = comparison_request(v, m)
            for t in ("model-only-trial-1", "model-only-trial-2"):
                slot = ModelSlot(
                    case_id=v.case_id + str(i),
                    model=m,
                    request_sha256=pin(r),
                    trial_id=t,
                    purpose="quality",
                )
                slots.append(slot)
                requests.append((slot, r))
    now = datetime.now(UTC)
    extension = ModelExtension(
        authorization_ref="invented-owner468",
        historical_pins=(
            store.allowance_sha256,
            store.amendment_sha256,
            store.development_extension_sha256,
            store.paired_extension_sha256,
            store.availability_override_sha256,
        ),
        run_id="invented-model-study",
        approved_at=now,
        expires_at=now + timedelta(days=5),
        slots=tuple(slots),
    )
    return store, ctx, extension, newcanaries, requests


def test_all50_slots_preserve415_history_and_deny_stale_oldbinary_duplicates_and_three_old_slots(
    tmp_path,
):
    old, ctx, ext, canaries, requests = history(tmp_path)
    with old.connect() as db:
        before = db.execute("SELECT * FROM attempts ORDER BY serial").fetchall()
        oldslots = db.execute("SELECT * FROM paired_slots ORDER BY ticket").fetchall()
    with pytest.raises(ValueError):
        append_model_extension(old, ext.model_copy(update={"slots": (ext.slots[0],) * 50}))
    newpin = append_model_extension(old, ext)
    store = AttemptLedger(old.path, *ext.historical_pins, newpin)
    with pytest.raises(ValueError, match="current external pin"):
        old.summary()

    def context(slot):
        return ctx.model_copy(
            update={
                "agent_id": "revenue",
                "run_id": ext.run_id,
                "case_id": slot.case_id,
                "trial_id": slot.trial_id,
            }
        )

    slot, r = requests[0]
    with pytest.raises(ValueError, match="both model"):
        store.reserve(context(slot), r, project_sha256="a" * 64)
    assert store.summary()["consumed"] == 415
    for r in canaries:
        slot = next(s for s in ext.slots if s.request_sha256 == pin(r))
        good = response(r).model_copy(
            update={
                "output": ModelMessage(
                    role="assistant", content='{"decision":"accept","evidence_ids":["s0"]}'
                )
            }
        )
        with pytest.raises(ValueError, match="settled"):
            record_model_canary(store, r, good)
        store.settle(store.reserve(context(slot), r, project_sha256="a" * 64), good)
        record_model_canary(store, r, good)
    for slot, r in requests:
        ticket = store.reserve(context(slot), r, project_sha256="a" * 64)
        store.settle(ticket, response(r))
    assert store.summary()["consumed"] == 465 and store.summary()["remaining"] == 3
    for slot, r in requests:
        with pytest.raises((ValueError, sqlite3.IntegrityError)):
            store.reserve(context(slot), r, project_sha256="a" * 64)
    with store.connect() as db:
        assert (
            db.execute("SELECT * FROM attempts WHERE serial<=415 ORDER BY serial").fetchall()
            == before
        )
        assert all(
            row in db.execute("SELECT * FROM paired_slots ORDER BY ticket").fetchall()
            for row in oldslots
        )
        assert db.execute("SELECT count(*) FROM model_slots").fetchone()[0] == 50
        with pytest.raises(sqlite3.IntegrityError, match="current model scope"):
            db.execute("INSERT INTO attempts VALUES(466,'old-code','c','r','now',NULL,NULL)")
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            db.execute("DELETE FROM model_extensions")


def test_model_only_projection_and_raw_assessment_do_not_relax_quotes_or_rewrite_response():
    v = value()
    baseline = comparison_request(v, MODELS[0])
    challenger = comparison_request(v, MODELS[1])
    assert challenger.model_copy(update={"model": baseline.model}) == baseline
    raw = semantic_response().model_copy(update={"model": MODELS[1]})
    before = raw.canonical_json()
    result, proof = assess_model(v, challenger, raw, "trial-2", 1.0)
    assert (
        result.variant == "challenger"
        and result.decision == "accept"
        and proof["semantic_support"] == "not_assessed"
    )
    assert raw.canonical_json() == before
    for quotes in (("not in source",), ("Payment", "Payment is due.")):
        out, _ = assess_model(
            v,
            challenger,
            semantic_response(quotes=quotes).model_copy(update={"model": MODELS[1]}),
            "trial-1",
            1.0,
        )
        assert out.decision is None and out.failure and out.raw_decision == "accept"
    with pytest.raises(ValueError):
        assess_model(v, challenger.model_copy(update={"parameters": {}}), raw, "trial-1", 1.0)


def test_two_model_report_has48_denominator_and_no_phantom_third_variant():
    labels, controls, rows = sample()
    selected = tuple(
        r.model_copy(update={"variant": "challenger"}) if r.variant == "task_wording" else r
        for r in rows
        if r.variant != "evidence_selection"
    )
    report = summarize(labels, controls, selected, comparison="models")
    assert (
        report["scheduled"] == report["observed"] == 48
        and report["all_scheduled_reference_correct"]
    )
    assert set(report["metrics"]) == {"baseline", "challenger"} and not report["qualification_met"]
    assert summarize(labels, controls, selected[:-1], comparison="models")["missing"] == 1
    with pytest.raises(ValueError):
        summarize(labels, controls, selected)


def test_actual_model_worker_sdk_flag_longwindow512_and_no_implicit_output_increase(monkeypatch):
    import agent_harness.gemini as adapter

    seen = []
    original = adapter.GeminiTransport

    def handler(req):
        seen.append(req)
        body = json.loads(req.content)
        assert req.extensions["timeout"]["read"] == 90.0
        assert body["generationConfig"]["maxOutputTokens"] == 512
        return httpx.Response(
            200,
            json={
                "modelVersion": MODELS[1],
                "candidates": [
                    {
                        "finishReason": "STOP",
                        "content": {
                            "role": "model",
                            "parts": [{"text": '{"decision":"accept","evidence_ids":["s0"]}'}],
                        },
                    }
                ],
                "usageMetadata": {
                    "promptTokenCount": 10,
                    "candidatesTokenCount": 4,
                    "totalTokenCount": 14,
                },
            },
        )

    def selected(key, **kwargs):
        assert kwargs["flash_comparison"] and kwargs["http_timeout_seconds"] == 90
        return original(key, http_transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(adapter, "GeminiTransport", selected)
    response = ModelComparisonWorker("invented-key", True).generate(
        model_canaries()[1], timeout_seconds=110
    )
    assert response.failure is None and response.usage.input_tokens == 10 and len(seen) == 1
    bad = model_canaries()[1].model_copy(
        update={
            "parameters": {"temperature": 0.0, "max_output_tokens": 2048, "thinking_level": "LOW"}
        }
    )
    result = ModelComparisonWorker("invented-key", True).generate(bad, timeout_seconds=110)
    assert result.failure and result.usage.model_calls == 0 and len(seen) == 1


def test_fresh468_pool_is_refused_without_file_creation(tmp_path):
    now = datetime.now(UTC)
    grant = ProviderAllowance(
        allowance_id="invented",
        authorization_ref="invented",
        project_sha256="a" * 64,
        max_attempts=468,
        models=MODELS,
        approved_at=now,
        expires_at=now + timedelta(days=1),
    )
    with pytest.raises(ValueError):
        initialize(tmp_path / "new.sqlite", grant)
    assert not (tmp_path / "new.sqlite").exists()
