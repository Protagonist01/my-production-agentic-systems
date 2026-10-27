"""Invented schedule-bound extension, old-binary guard and canary barrier."""

import json
import sqlite3
from datetime import UTC, datetime, timedelta

import pytest
from agent_harness.contracts import ModelMessage
from agent_harness.paired_budget import (
    PairedExtension,
    PairedSlot,
    append_extension,
    canary_requests,
    record_canary_pass,
)
from agent_harness.provider_budget import (
    AttemptLedger,
    ProviderAllowance,
    extend_development,
    initialize,
)
from agent_harness.release_contracts import pin
from test_provider_budget_accounting import response
from test_remediation_development import setup_extension


def fixture(tmp_path):
    ledger, context, requests, doc = setup_extension(tmp_path)
    extpin = extend_development(ledger, doc)
    old = AttemptLedger(ledger.path, ledger.allowance_sha256, ledger.amendment_sha256, extpin)
    context = context.model_copy(update={"agent_id": "revenue", "run_id": doc.run_id})
    for index in range(21):
        r = requests[index % 12]
        ctx = context.model_copy(update={"trial_id": f"trial-{index // 12 + 1}"})
        old.settle(old.reserve(ctx, r, project_sha256="a" * 64), response(r))
    assert old.summary()["consumed"] == 341
    canaries = canary_requests()
    slots = [
        PairedSlot(
            case_id=f"invented-canary-{i}",
            request_sha256=pin(r),
            trial_id=f"canary-{i}",
            variant="canary",
        )
        for i, r in enumerate(canaries, 1)
    ]
    domain = []
    for i in range(12):
        for variant in ("baseline", "task_wording", "evidence_selection"):
            r = canaries[0].model_copy(
                update={"messages": (ModelMessage(role="user", content=f"Invented {i} {variant}"),)}
            )
            for trial in ("trial-1", "trial-2"):
                slot = PairedSlot(
                    case_id=f"case-{i}", request_sha256=pin(r), trial_id=trial, variant=variant
                )
                slots.append(slot)
                domain.append((slot, r))
    now = datetime.now(UTC)
    grant = PairedExtension(
        authorization_ref="invented-owner418",
        original_allowance_sha256=old.allowance_sha256,
        previous_amendment_sha256=old.amendment_sha256,
        previous_development_sha256=extpin,
        run_id="invented-paired",
        approved_at=now,
        expires_at=now + timedelta(days=4),
        slots=tuple(slots),
    )
    return old, context, grant, canaries, domain


def context_for(context, grant, slot):
    return context.model_copy(
        update={"run_id": grant.run_id, "case_id": slot.case_id, "trial_id": slot.trial_id}
    )


def activate(old, grant):
    p = append_extension(old, grant)
    return AttemptLedger(
        old.path, old.allowance_sha256, old.amendment_sha256, old.development_extension_sha256, p
    )


def pass_canaries(store, context, grant, canaries):
    for i, r in enumerate(canaries):
        slot = next(s for s in grant.slots if s.request_sha256 == pin(r))
        ticket = store.reserve(context_for(context, grant, slot), r, project_sha256="a" * 64)
        result = response(r).model_copy(
            update={
                "output": ModelMessage(
                    role="assistant",
                    content=json.dumps(
                        {"answer": 8} if i == 0 else {"decision": "accept", "evidence_ids": ["s0"]}
                    ),
                )
            }
        )
        store.settle(ticket, result)
        record_canary_pass(store, r, result)


def test_all_74_unique_slots_preserve341_rows_and_leave_three_legacy_slots_unusable(tmp_path):
    old, ctx, grant, canaries, domain = fixture(tmp_path)
    with old.connect() as db:
        before = db.execute("SELECT * FROM attempts ORDER BY serial").fetchall()
    store = activate(old, grant)
    with pytest.raises(ValueError, match="current external pin"):
        old.summary()
    slot, r = domain[0]
    with pytest.raises(ValueError, match="both invented"):
        store.reserve(context_for(ctx, grant, slot), r, project_sha256="a" * 64)
    assert store.summary()["consumed"] == 341
    pass_canaries(store, ctx, grant, canaries)
    for slot, r in domain:
        ticket = store.reserve(context_for(ctx, grant, slot), r, project_sha256="a" * 64)
        store.settle(ticket, response(r))
    assert store.summary() == {
        "allowance_sha256": old.allowance_sha256,
        "maximum": 418,
        "consumed": 415,
        "remaining": 3,
        "unsettled": 0,
    }
    for slot, r in domain:
        with pytest.raises((ValueError, sqlite3.IntegrityError)):
            store.reserve(context_for(ctx, grant, slot), r, project_sha256="a" * 64)
    with store.connect() as db:
        assert (
            db.execute("SELECT * FROM attempts WHERE serial<=341 ORDER BY serial").fetchall()
            == before
        )
        assert db.execute("SELECT count(*) FROM development_slots").fetchone()[0] == 21
        assert db.execute("SELECT count(*) FROM paired_slots").fetchone()[0] == 74
        # Simulate an older executable that does not know the new extension.
        with pytest.raises(sqlite3.IntegrityError, match="current paired scope"):
            db.execute(
                "INSERT INTO attempts VALUES(416,'old-binary','other','other','now',NULL,NULL)"
            )
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            db.execute("DELETE FROM paired_extensions")


def test_wrong_scope_and_failed_or_unsettled_canaries_never_unlock_domain(tmp_path):
    old, ctx, grant, canaries, domain = fixture(tmp_path)
    store = activate(old, grant)
    r = canaries[0]
    slot = next(s for s in grant.slots if s.request_sha256 == pin(r))
    for changes in (
        {"agent_id": "olist"},
        {"run_id": "other"},
        {"case_id": "other"},
        {"trial_id": "other"},
    ):
        with pytest.raises(ValueError):
            store.reserve(
                context_for(ctx, grant, slot).model_copy(update=changes), r, project_sha256="a" * 64
            )
    good = response(r).model_copy(
        update={"output": ModelMessage(role="assistant", content='{"answer":8}')}
    )
    with pytest.raises(ValueError, match="settled"):
        record_canary_pass(store, r, good)
    ticket = store.reserve(context_for(ctx, grant, slot), r, project_sha256="a" * 64)
    with pytest.raises(ValueError, match="settled"):
        record_canary_pass(store, r, good)
    store.settle(ticket, good)
    record_canary_pass(store, r, good)
    wrong = response(canaries[1]).model_copy(
        update={"output": ModelMessage(role="assistant", content='{"answer":8}')}
    )
    with pytest.raises(ValueError, match="incorrect"):
        record_canary_pass(store, canaries[1], wrong)
    ds, dr = domain[0]
    with pytest.raises(ValueError, match="both invented"):
        store.reserve(context_for(ctx, grant, ds), dr, project_sha256="a" * 64)


def test_malformed_or_unsettled_extension_refuses_before_any_history_change(tmp_path):
    old, ctx, grant, canaries, _ = fixture(tmp_path)
    for altered in (
        grant.model_copy(update={"previous_development_sha256": "f" * 64}),
        grant.model_copy(update={"slots": (grant.slots[0],) * 74}),
    ):
        with pytest.raises(ValueError):
            append_extension(old, altered)
    assert old.summary()["maximum"] == 344
    with old.connect() as db:
        db.execute("INSERT INTO attempts VALUES(342,'invented-unsettled','c','r','now',NULL,NULL)")
    with pytest.raises(ValueError, match="settled341"):
        append_extension(old, grant)
    assert old.summary()["unsettled"] == 1


def test_new_418_allowance_cannot_be_initialized_as_a_fresh_pool(tmp_path):
    now = datetime.now(UTC)
    g = ProviderAllowance(
        allowance_id="invented",
        authorization_ref="invented",
        project_sha256="a" * 64,
        max_attempts=418,
        models=("gemini-3.5-flash-lite",),
        approved_at=now,
        expires_at=now + timedelta(days=1),
    )
    with pytest.raises(ValueError):
        initialize(tmp_path / "fresh.sqlite", g)
    assert not (tmp_path / "fresh.sqlite").exists()
