"""Invented study binding and shared-budget amendment; zero provider calls."""

import sqlite3
from datetime import UTC, datetime, timedelta

import pytest
from agent_harness.provider_budget import AllowanceAmendment, AttemptLedger, amend
from agent_harness.release_contracts import pin, sha256
from agent_harness.scorecard_stats import binomial_bounds
from revenue_integrity.confidence_study import ConfidenceCohort, prepare_confidence
from test_prospective_semantics import exposure, samples
from test_provider_budget_accounting import inputs, response


def prepared(cases=None):
    return prepare_confidence(
        samples(340) if cases is None else cases,
        (exposure(),),
        source_manifest_sha256="a" * 64,
        evaluator_source_sha256="b" * 64,
        frozen_at=datetime(2026, 10, 27, tzinfo=UTC),
    )


def test_minimum_target_is_per_class_not_repeat_count():
    assert binomial_bounds(0, 71)[1] > 0.05
    assert binomial_bounds(0, 72)[1] < 0.05
    assert binomial_bounds(1, 72)[1] > 0.05
    result = prepared()
    assert len(result.cases) == 148 and len(result.schedule) == 296
    assert sum(c.split == "holdout" for c in result.dataset.cases) == 144
    assert len({c.target.family_id for c in result.cases}) == 148
    assert not result.release_allowed


@pytest.mark.parametrize("kind", ["schedule", "family", "context", "reference", "split"])
def test_frozen_study_refuses_substitution(kind):
    data = prepared().model_dump(mode="json")
    if kind == "schedule":
        data["schedule"][0]["request_sha256"] = "f" * 64
    if kind == "family":
        data["cases"][0]["target"]["family_id"] = data["cases"][1]["target"]["family_id"]
    if kind == "context":
        data["cases"][0]["input"]["context"] = data["cases"][1]["input"]["context"]
    if kind == "reference":
        data["dataset"]["cases"][0]["reference_sha256"] = "f" * 64
    if kind == "split":
        data["dataset"]["cases"][0]["split"] = "holdout"
    with pytest.raises(ValueError):
        ConfidenceCohort.model_validate(data)


def test_no_resampling_or_group_inflation_when_source_is_too_small():
    with pytest.raises(ValueError, match="insufficient"):
        prepared(samples(100))
    source = samples(340)
    repeated = tuple(
        c.model_copy(
            update={
                "target": c.target.model_copy(update={"family_id": sha256(str(i % 100).encode())})
            }
        )
        for i, c in enumerate(source)
    )
    with pytest.raises(ValueError, match="insufficient"):
        prepared(repeated)


def amendment(ledger, used):
    now = datetime.now(UTC)
    return AllowanceAmendment(
        previous_allowance_sha256=ledger.allowance_sha256,
        authorization_ref="invented-owner-320-authorization",
        approved_at=now,
        expires_at=now + timedelta(days=2),
        consumed_before=used,
    )


def test_amendment_preserves_history_stale_clients_deny_and_exact_cap_survives_reopen(tmp_path):
    ledger, context, request = inputs(tmp_path, maximum=2)
    for _ in range(2):
        ticket = ledger.reserve(context, request, project_sha256="a" * 64)
        ledger.settle(ticket, response(request))
    with ledger.connect() as db:
        before = db.execute("SELECT * FROM attempts").fetchall()
        grant = db.execute("SELECT * FROM authorization").fetchall()
    document = amendment(ledger, 2)
    newpin = amend(ledger.path, ledger.allowance_sha256, document)
    assert newpin == pin(document)
    with pytest.raises(ValueError, match="current external pin"):
        ledger.summary()
    updated = AttemptLedger(ledger.path, ledger.allowance_sha256, newpin)
    assert updated.summary()["remaining"] == 318
    for _ in range(318):
        ticket = updated.reserve(context, request, project_sha256="a" * 64)
        updated.settle(ticket, response(request))
    with pytest.raises(ValueError, match="exhausted"):
        updated.reserve(context, request, project_sha256="a" * 64)
    with updated.connect() as db:
        assert db.execute("SELECT * FROM authorization").fetchall() == grant
        assert db.execute("SELECT * FROM attempts WHERE serial<=2").fetchall() == before
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("DELETE FROM amendments")
    assert AttemptLedger(ledger.path, ledger.allowance_sha256, newpin).summary()["consumed"] == 320


def test_amendment_rejects_wrong_count_unsettled_and_missing_pin(tmp_path):
    ledger, context, request = inputs(tmp_path)
    with pytest.raises(ValueError):
        amend(ledger.path, ledger.allowance_sha256, amendment(ledger, 1))
    assert ledger.summary()["consumed"] == 0
    with pytest.raises(ValueError):
        AttemptLedger(ledger.path, ledger.allowance_sha256, "f" * 64).summary()
    ledger.reserve(context, request, project_sha256="a" * 64)
    with pytest.raises(ValueError):
        amend(ledger.path, ledger.allowance_sha256, amendment(ledger, 1))
    assert ledger.summary()["unsettled"] == 1
