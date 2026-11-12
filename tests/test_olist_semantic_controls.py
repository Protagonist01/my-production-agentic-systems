"""Invented histories only. Never connect to the owner's live allowance."""

import sqlite3
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from agent_harness.contracts import ModelMessage, ModelResponse, Usage
from agent_harness.cost_accounting import FreeTariff

from docs.evaluation.olist_semantic_controls import (
    Scope,
    Slot,
    connect,
    historical_anchor,
    install,
    observe,
    reserve,
)

NOW = datetime(2026, 11, 11, tzinfo=UTC)


def fixture(tmp_path: Path) -> tuple[Path, Scope]:
    path = tmp_path / "invented.sqlite"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE attempts(id INTEGER PRIMARY KEY,response_pin TEXT)")
        db.executemany("INSERT INTO attempts VALUES(?,?)", [(i, "invented") for i in range(447)])
        db.execute("CREATE TABLE routing_stops(reason TEXT)")
        db.execute("INSERT INTO routing_stops VALUES('original invented stop')")
        anchor = historical_anchor(db)
    slots = [
        Slot(
            ordinal=i + 1,
            phase="canary",
            case_id=f"invented-canary-{i}",
            trial_id="canary",
            request_sha256=str(i + 1) * 64,
        )
        for i in range(2)
    ]
    for case in range(24):
        for trial in range(3):
            slots.append(
                Slot(
                    ordinal=len(slots) + 1,
                    phase="domain",
                    case_id=f"invented-{case}",
                    trial_id=f"trial-{trial + 1}",
                    request_sha256=f"{case + 50:064x}",
                )
            )
    return path, Scope(
        origin="mock",
        proposal_sha256="a" * 64,
        historical_anchor_sha256=anchor,
        project_sha256="b" * 64,
        allowance_sha256="6" * 64,
        tariff=FreeTariff(
            source_snapshot_sha256="7" * 64,
            project_sha256="b" * 64,
            free_project_attestation_ref="invented",
            review_ref="invented",
            reviewed_at=NOW,
            expires_at=NOW + timedelta(days=1),
            models=("gemini-3.5-flash-lite",),
        ),
        source_files={"invented.py": "c" * 64},
        environment_sha256="d" * 64,
        code_revision="e" * 40,
        input_packet_sha256="f" * 64,
        reference_packet_sha256="9" * 64,
        canary_expectations_sha256="8" * 64,
        approved_at=NOW,
        expires_at=NOW + timedelta(days=1),
        slots=tuple(slots),
    )


def response() -> ModelResponse:
    return ModelResponse(
        provider="google-gemini-developer-api",
        model="gemini-3.5-flash-lite",
        output=ModelMessage(role="assistant", content="invented"),
        usage=Usage(
            model_calls=1, input_tokens=10, output_tokens=2, cost=Decimal(0), cost_currency="USD"
        ),
    )


def test_two_canaries_parent_fence_and_single_use_cap_preserve_history(tmp_path: Path) -> None:
    path, scope = fixture(tmp_path)
    expected = install(path, scope, None)
    for slot in scope.slots:
        reserve(path, expected, slot, now=NOW, origin="mock")
        with pytest.raises(ValueError, match="unobserved"):
            reserve(path, expected, slot, now=NOW, origin="mock")
        observe(path, expected, slot, response(), {}, continue_allowed=True, now=NOW, origin="mock")
    with pytest.raises(ValueError):
        reserve(path, expected, scope.slots[-1], now=NOW, origin="mock")
    with connect(path) as db:
        assert historical_anchor(db) == scope.historical_anchor_sha256
        assert db.execute("SELECT count(*) FROM attempts").fetchone()[0] == 447
        assert db.execute("SELECT count(*) FROM routing_stops").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM olist_semantic_attempts").fetchone()[0] == 74
        assert 447 + 74 + scope.preserved_other_slots == 614


def test_stopped_canary_refuses_remaining_calls(tmp_path: Path) -> None:
    path, scope = fixture(tmp_path)
    expected = install(path, scope, None)
    reserve(path, expected, scope.slots[0], now=NOW, origin="mock")
    observe(
        path,
        expected,
        scope.slots[0],
        response(),
        {},
        continue_allowed=False,
        now=NOW,
        origin="mock",
    )
    with pytest.raises(ValueError, match="stopped"):
        reserve(path, expected, scope.slots[1], now=NOW, origin="mock")


def test_missing_live_ledger_is_never_recreated(tmp_path: Path) -> None:
    with pytest.raises(sqlite3.OperationalError):
        connect(tmp_path / "missing.sqlite")
    assert not (tmp_path / "missing.sqlite").exists()


@pytest.mark.parametrize(
    "change",
    ["provider_origin", "expired", "wrong_request", "skip_canary", "changed_history", "wrong_pin"],
)
def test_dispatch_binding_failures_do_not_consume(tmp_path: Path, change: str) -> None:
    path, scope = fixture(tmp_path)
    expected = install(path, scope, None)
    slot, now, origin = scope.slots[0], NOW, "mock"
    if change == "provider_origin":
        origin = "provider"
    elif change == "expired":
        now = scope.expires_at
    elif change == "wrong_request":
        slot = slot.model_copy(update={"request_sha256": "a" * 64})
    elif change == "skip_canary":
        slot = scope.slots[2]
    elif change == "changed_history":
        with connect(path) as db:
            db.execute("INSERT INTO routing_stops VALUES('unexpected change')")
    elif change == "wrong_pin":
        expected = "0" * 64
    with pytest.raises(ValueError):
        reserve(path, expected, slot, now=now, origin=origin)
    with connect(path) as db:
        assert db.execute("SELECT count(*) FROM olist_semantic_attempts").fetchone()[0] == 0


def test_provider_install_requires_separately_trusted_owner_grant(tmp_path: Path) -> None:
    path, scope = fixture(tmp_path)
    scope = Scope.model_validate_json(
        scope.model_copy(update={"origin": "provider"}).canonical_json()
    )
    with pytest.raises(ValueError, match="owner grant"):
        install(path, scope, None)


def test_no_reset_or_mutation_of_published_semantic_evidence(tmp_path: Path) -> None:
    path, scope = fixture(tmp_path)
    expected = install(path, scope, None)
    reserve(path, expected, scope.slots[0], now=NOW, origin="mock")
    with pytest.raises(ValueError, match="already exists"):
        install(path, scope, None)
    with connect(path) as db, pytest.raises(sqlite3.IntegrityError, match="immutable"):
        db.execute("DELETE FROM olist_semantic_attempts")


def test_response_requires_consumption_and_matching_provider(tmp_path: Path) -> None:
    path, scope = fixture(tmp_path)
    expected = install(path, scope, None)
    with pytest.raises(ValueError, match="consumed"):
        observe(
            path,
            expected,
            scope.slots[0],
            response(),
            {},
            continue_allowed=True,
            now=NOW,
            origin="mock",
        )
    reserve(path, expected, scope.slots[0], now=NOW, origin="mock")
    bad = response().model_copy(update={"model": "different-model"})
    with pytest.raises(ValueError, match="provider/model"):
        observe(
            path, expected, scope.slots[0], bad, {}, continue_allowed=True, now=NOW, origin="mock"
        )
