"""PA scope admission/readiness with invented history and actual mocked Google SDK."""

import hashlib
import json
import socket
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from agent_harness.contracts import ModelRequest
from agent_harness.gemini import GeminiTransport

from prior_auth_demo import demo_policy
from prior_auth_study_budget import Grant, Slot, historical_snapshot, initialize
from prior_auth_study_draft import prepare
from prior_auth_study_run import load_packet, parse

NOW = datetime(2026, 11, 13, 2, tzinfo=UTC)


def history(path):
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE attempts(serial INTEGER PRIMARY KEY,response_pin TEXT)")
        db.executemany("INSERT INTO attempts VALUES(?,?)", [(i, str(i)) for i in range(1, 448)])
        db.execute("CREATE TABLE routing_stops(id INTEGER PRIMARY KEY,reason TEXT)")
        db.execute("INSERT INTO routing_stops VALUES(1,'historical-stop')")
        db.execute("CREATE TABLE routing_extensions(document TEXT)")
        db.execute("INSERT INTO routing_extensions VALUES(?)", (json.dumps({"maximum": 614}),))
        return historical_snapshot(db)


def ledger(path, *, count=3):
    prior = history(path)
    grant = Grant(
        packet_sha256="a" * 64,
        historical_sha256=prior,
        project_sha256="b" * 64,
        execution_sha256="c" * 64,
        approved_at=NOW,
        expires_at=NOW + timedelta(days=7),
        slots=tuple(
            Slot(
                ordinal=i,
                phase="canary" if i <= 2 else "domain",
                case_id="case",
                trial=0,
                criterion="education",
                request_sha256="d" * 64,
            )
            for i in range(1, count + 1)
        ),
    )
    return initialize(path, grant)


def test_append_only_single_file_counts_preserve_all_original_data(tmp_path):
    path = tmp_path / "shared.sqlite"
    budget = ledger(path)
    for i in range(1, 4):
        budget.reserve(i, "d" * 64, now=NOW)
        budget.settle(i, {"mock": True}, tokens=20, canary_pass=i <= 2, stop=None)
    assert budget.summary() == {
        "maximum": 784,
        "historical_consumed": 447,
        "pa_consumed": 3,
        "total_consumed": 450,
        "pa_unsettled": 0,
        "stop": None,
        "old_history_unchanged": True,
    }
    with closing(budget.connect()) as db:
        assert db.execute("SELECT reason FROM routing_stops").fetchone()[0] == "historical-stop"
        assert db.execute("SELECT count(*) FROM attempts").fetchone()[0] == 447
        for table in ("pa_scope", "pa_reservations", "pa_settlements"):
            with pytest.raises(sqlite3.IntegrityError):
                db.execute("DELETE FROM " + table)
    with pytest.raises(ValueError):
        budget.reserve(4, "d" * 64, now=NOW)


def test_wrong_scope_expiry_order_and_crash_left_attempt_deny_before_transport(tmp_path):
    budget = ledger(tmp_path / "shared.sqlite")
    for ordinal, request, now in (
        (1, "e" * 64, NOW),
        (2, "d" * 64, NOW),
        (1, "d" * 64, NOW - timedelta(seconds=1)),
        (1, "d" * 64, NOW + timedelta(days=7)),
    ):
        with pytest.raises(ValueError):
            budget.reserve(ordinal, request, now=now)
    budget.reserve(1, "d" * 64, now=NOW)
    # Simulated parent death: no settlement. Neither repeated nor later slots run.
    for ordinal in (1, 2):
        with pytest.raises(ValueError):
            budget.reserve(ordinal, "d" * 64, now=NOW)
    assert budget.summary()["pa_unsettled"] == 1


@pytest.mark.parametrize(
    "passed,tokens,reason", [(False, 10, None), (True, None, None), (True, 10, "provider_failure")]
)
def test_failed_canary_unknown_usage_and_stop_each_block_domain(tmp_path, passed, tokens, reason):
    budget = ledger(tmp_path / "shared.sqlite")
    budget.reserve(1, "d" * 64, now=NOW)
    budget.settle(1, {"mock": True}, tokens=tokens, canary_pass=passed, stop=reason)
    if passed and tokens is not None and reason is None:
        raise AssertionError("test must represent a blocker")
    if tokens is not None and reason is None:
        budget.reserve(2, "d" * 64, now=NOW)
        budget.settle(2, {"mock": True}, tokens=10, canary_pass=True, stop=None)
    with pytest.raises(ValueError):
        budget.reserve(3 if tokens is not None and reason is None else 2, "d" * 64, now=NOW)


def test_historical_mutation_and_external_pin_change_fail_closed(tmp_path):
    budget = ledger(tmp_path / "shared.sqlite")
    with closing(budget.connect()) as db, db:
        db.execute("UPDATE routing_stops SET reason='tampered'")
    with pytest.raises(ValueError, match="historical"):
        budget.reserve(1, "d" * 64, now=NOW)


def test_concurrent_callers_cannot_reserve_the_same_or_next_attempt(tmp_path):
    budget = ledger(tmp_path / "shared.sqlite")

    def reserve(_):
        try:
            budget.reserve(1, "d" * 64, now=NOW)
            return True
        except ValueError:
            return False

    with ThreadPoolExecutor(max_workers=4) as pool:
        assert sum(pool.map(reserve, range(8))) == 1


def test_actual_tokens_release_only_settled_reservation_and_never_unknowns(tmp_path):
    budget = ledger(tmp_path / "shared.sqlite")
    budget.reserve(1, "d" * 64, now=NOW)
    budget.settle(1, {"mock": True}, tokens=900_000, canary_pass=True, stop=None)
    with pytest.raises(ValueError, match="budget"):
        budget.reserve(2, "d" * 64, now=NOW)


def test_actual_pinned_sdk_can_serialize_and_parse_every_prepared_request(tmp_path, monkeypatch):
    def forbidden(*args):
        raise AssertionError("mock readiness attempted a real connection")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    directory = tmp_path / "draft"
    prepare(directory)
    notes = {row["case_id"]: row for row in json.loads((directory / "inputs.json").read_text())}
    from prior_auth.contracts import NoteInput

    calls = []

    def handler(http_request):
        calls.append(http_request)
        payload = json.loads(json.loads(http_request.content)["contents"][0]["parts"][0]["text"])
        claim = {
            "schema_version": 1,
            "criterion_id": payload["criterion"]["criterion_id"],
            "state": "insufficient",
            "quotes": [],
            "rationale": "Invented SDK shape witness.",
        }
        return httpx.Response(
            200,
            json={
                "modelVersion": "gemini-3.5-flash-lite",
                "candidates": [
                    {
                        "content": {"role": "model", "parts": [{"text": json.dumps(claim)}]},
                        "finishReason": "STOP",
                    }
                ],
                "usageMetadata": {
                    "promptTokenCount": 50,
                    "candidatesTokenCount": 20,
                    "totalTokenCount": 70,
                },
            },
        )

    transport = GeminiTransport(
        "invented-key",
        free_tier_confirmed=True,
        http_transport=httpx.MockTransport(handler),
        http_timeout_seconds=90,
    )
    for row in json.loads((directory / "request-plan.json").read_text()):
        if row["request"] is not None:
            request = ModelRequest.model_validate_json(json.dumps(row["request"]))
            response = transport.generate(request, timeout_seconds=90)
            assert response.failure is None
            assert (
                parse(
                    response,
                    request,
                    NoteInput.model_validate_json(json.dumps(notes[row["case_id"]])),
                )
                is not None
            )
    assert len(calls) == 166


def test_packet_tamper_refused_without_loading_credentials(tmp_path):
    directory = tmp_path / "draft"
    prepare(directory)
    with pytest.raises(ValueError, match="owner-approved"):
        load_packet(directory)
    # The approved manifest pin cannot be supplied by an untrusted CLI argument.
    assert hashlib.sha256((directory / "manifest.json").read_bytes()).hexdigest() != "a" * 64
    assert demo_policy().review_status == "ai_provisional"


def test_actual_owned_spawn_sdk_frame_and_live_worker_http_ceiling(tmp_path, monkeypatch):
    from agent_harness.isolated_transport import IsolatedTransport
    from prior_auth_sdk_fake import Worker as FakeWorker

    from prior_auth_study_run import Worker

    directory = tmp_path / "draft"
    prepare(directory)
    row = next(r for r in json.loads((directory / "request-plan.json").read_text()) if r["request"])
    request = ModelRequest.model_validate_json(json.dumps(row["request"]))
    isolated = IsolatedTransport(FakeWorker())
    output = isolated.generate(request, timeout_seconds=30)
    assert output.failure is None and output.usage.input_tokens == 50
    assert isolated.last_timing.exit_code == 0 and not isolated.last_timing.timed_out
    seen = []

    class Transport:
        def __init__(self, key, **kwargs):
            seen.append(kwargs)

        def generate(self, request, *, timeout_seconds):
            seen.append(timeout_seconds)
            return output

    monkeypatch.setattr("agent_harness.gemini.GeminiTransport", Transport)
    assert Worker("invented").generate(request, timeout_seconds=110) == output
    assert seen == [{"free_tier_confirmed": True, "http_timeout_seconds": 90}, 90]
