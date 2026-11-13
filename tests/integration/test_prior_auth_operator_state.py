"""Actual SQL-backed auth/import/receipts/source mapping; no provider transport."""

import argparse
from datetime import timedelta

import pytest
from prior_auth.contracts import digest
from prior_auth.review_auth import AuthStore, provision
from prior_auth.review_contracts import StateChanged, WaitRequest
from prior_auth.review_workflow import ReviewWorkflow
from psycopg.types.json import Jsonb
from test_prior_auth_intake_state import seed
from test_prior_auth_review import NOW
from test_prior_auth_review_state import app as app

import prior_auth_operator as operator
from prior_auth_documents import normalize
from prior_auth_intake_readback import IntakeReader
from prior_auth_pipeline import prepare
from prior_auth_profiling import Profiler


def test_authenticated_import_replay_logout_and_private_receipt(app, tmp_path, monkeypatch):
    request, intake, legacy, user = seed(app)
    server, trial, _, _ = app
    username = "reviewer-" + request.case.case_id[-20:]
    user = user.model_copy(update={"username": username})
    password = "invented-test-password-2026"
    with server.connect(trial.name) as admin:
        provision(admin, user, password)
    auth = AuthStore(legacy.connect, clock=legacy.clock)
    request_path, source = tmp_path / "request.json", tmp_path / "source.txt"
    request_path.write_text(request.canonical_json(), encoding="utf-8")
    source.write_text("AHI: 18 events/hour.", encoding="utf-8")
    monkeypatch.setattr(operator.getpass, "getpass", lambda _: password)
    args = argparse.Namespace(
        command="import", username=username, request=request_path, source=source, native_tools=None
    )
    first = operator.authenticated(args, legacy.connect, auth, Profiler())
    assert first["recorded"] and first["resulting_version"] == 1
    assert operator.authenticated(args, legacy.connect, auth, Profiler()) == first
    with legacy.transaction() as c:
        assert c.execute("SELECT COUNT(*) AS n FROM prior_auth_app.sessions").fetchone()["n"] == 0
    receipt = IntakeReader(legacy.connect).receipt(
        user, request.case.case_id, request.document.document_id
    )
    assert receipt.resulting_version == 1 and receipt.decision.admitted
    assert "AHI" not in receipt.canonical_json() and password not in receipt.canonical_json()


def test_source_map_is_scoped_and_fenced_against_changed_note(app):
    request, intake, legacy, user = seed(app)
    profiler = Profiler()
    initial = prepare(b"AHI: 18 events/hour.", request, profiler)
    intake.accept(user, initial, profiler)
    reader = IntakeReader(legacy.connect)
    location = reader.locate(
        user,
        request.case.case_id,
        request.document.document_id,
        note_sha256=initial.note.note_sha256,
        start=0,
        end=3,
    )
    assert location.imported_version == location.current_version == 1
    assert location.regions[0].note_start == 0 and "AHI" not in location.canonical_json()
    for _ in range(20):
        if legacy.snapshot(user, request.case.case_id)["status"] != "assessing":
            break
        assert ReviewWorkflow(legacy, lambda note, policy, keys: None).step()["claimed"]
    legacy.request(
        user,
        request.case.case_id,
        WaitRequest(
            command_id="wait",
            expected_version=1,
            criteria=("education",),
            deadline=NOW + timedelta(hours=1),
        ),
    )
    raw = b"CPAP education completed prior to use."
    supplement = request.model_copy(
        update={
            "document": request.document.model_copy(update={"document_id": "supplement"}),
            "expected_version": 2,
            "source_sha256": digest(raw.decode()),
            "normalization_sha256": normalize(raw, "text").text_sha256,
        }
    )
    intake.accept(user, prepare(raw, supplement, profiler), profiler)
    current = legacy.snapshot(user, request.case.case_id)
    with pytest.raises(StateChanged):
        reader.locate(
            user,
            request.case.case_id,
            request.document.document_id,
            note_sha256=initial.note.note_sha256,
            start=0,
            end=3,
        )
    restored = reader.locate(
        user,
        request.case.case_id,
        request.document.document_id,
        note_sha256=current["note"]["note_sha256"],
        start=0,
        end=3,
    )
    assert restored.current_version == 3 and restored.imported_version == 1
    offset = len(current["note"]["text"]) - len(raw.decode())
    new = reader.locate(
        user,
        request.case.case_id,
        "supplement",
        note_sha256=current["note"]["note_sha256"],
        start=offset,
        end=offset + 4,
    )
    assert new.regions[0].note_start == offset and new.imported_version == 3
    with pytest.raises(LookupError):
        reader.receipt(
            user.model_copy(update={"tenant_id": "other"}),
            request.case.case_id,
            request.document.document_id,
        )
    server, trial, _, _ = app
    altered = initial.normalized.model_copy(update={"source_sha256": "a" * 64})
    with server.connect(trial.name) as admin:
        admin.execute(
            "UPDATE prior_auth_intake.documents SET normalized=%s "
            "WHERE tenant_id=%s AND case_id=%s AND document_id=%s",
            (
                Jsonb(altered.model_dump(mode="json")),
                user.tenant_id,
                request.case.case_id,
                request.document.document_id,
            ),
        )
    with pytest.raises(StateChanged):
        reader.locate(
            user,
            request.case.case_id,
            request.document.document_id,
            note_sha256=current["note"]["note_sha256"],
            start=0,
            end=3,
        )


def test_rejected_receipt_inspectable_without_a_case_or_source_body(app):
    request, intake, legacy, user = seed(app)
    request = request.model_copy(
        update={"document": request.document.model_copy(update={"kind": "other"})}
    )
    prepared = prepare(b"AHI: 18 events/hour.", request, Profiler())
    assert intake.accept(user, prepared, Profiler()) is None
    reader = IntakeReader(legacy.connect)
    receipt = reader.receipt(user, request.case.case_id, request.document.document_id)
    assert receipt.decision.outcome == "unrelated_document" and receipt.resulting_version is None
    with pytest.raises(LookupError):
        legacy.snapshot(user, request.case.case_id)
    with pytest.raises(LookupError):
        reader.locate(
            user,
            request.case.case_id,
            request.document.document_id,
            note_sha256="a" * 64,
            start=0,
            end=3,
        )


def test_actual_operator_worker_routes_conflicts_without_a_provider(app):
    request, intake, legacy, user = seed(app)
    raw = b"AHI: 18 events/hour. AHI: 2 events/hour."
    request = request.model_copy(
        update={
            "source_sha256": digest(raw.decode()),
            "normalization_sha256": normalize(raw, "text").text_sha256,
        }
    )
    intake.accept(user, prepare(raw, request, Profiler()), Profiler())
    for _ in range(20):
        if legacy.snapshot(user, request.case.case_id)["status"] != "assessing":
            break
        result = operator.worker(legacy.connect, Profiler(), baseline="conflict-rules-v3")
        assert result["claimed"] and result["provider_attempts"] == 0
    saved = legacy.snapshot(user, request.case.case_id)
    assert saved["status"] == "qualified_review" and saved["version"] == 1
    assert saved["job"]["state"] == "done" and not saved["result"]["clinical_validation"]
