"""Real SQL: intake receipt and legacy handoff commit together or neither does."""

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
from prior_auth.review_contracts import StateChanged, WaitRequest
from prior_auth.review_workflow import ReviewWorkflow
from psycopg import errors, sql
from test_prior_auth_review import NOW, actor, insufficient
from test_prior_auth_review_state import app as app

from prior_auth_demo import demo_request
from prior_auth_pipeline import prepare
from prior_auth_profiling import Profiler
from prior_auth_store import IntakeStore, ProfiledReviewStore, setup


def seed(app):
    server, trial, legacy, now = app
    now[0] = NOW
    with server.connect(trial.name) as admin:
        setup(admin, trial.name)
    key = "intake-" + uuid.uuid4().hex
    request = demo_request(b"AHI: 18 events/hour.", case_id=key)
    store = IntakeStore(lambda: server.connect_trial(trial), clock=lambda: now[0])
    return request, store, legacy, actor(key)


def test_atomic_initial_replay_and_rejected_supplement_leaves_case_unchanged(app):
    request, store, legacy, user = seed(app)
    raw, profiler = b"AHI: 18 events/hour.", Profiler()
    prepared = prepare(raw, request, profiler)
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(lambda _: store.accept(user, prepared, Profiler()), range(2))) == [
            1,
            1,
        ]
    before = legacy.snapshot(user, request.case.case_id)
    unrelated = request.model_copy(
        update={
            "document": request.document.model_copy(
                update={"document_id": "unrelated", "kind": "other"}
            ),
            "expected_version": 1,
        }
    )
    rejected = prepare(raw, unrelated, profiler)
    assert store.accept(user, rejected, profiler) is None
    assert legacy.snapshot(user, request.case.case_id) == before
    rebuilt = IntakeStore(store.store.connect, clock=legacy.clock)
    assert rebuilt.accept(user, prepared, profiler) == 1
    with pytest.raises(StateChanged):
        rebuilt.accept(
            user,
            prepare(
                raw,
                request.model_copy(
                    update={
                        "document": request.document.model_copy(update={"kind": "clinical_note"})
                    }
                ),
                profiler,
            ),
            profiler,
        )


def test_delivery_joins_wait_version_and_rollback(app):
    request, store, legacy, user = seed(app)
    raw, profiler = b"AHI: 18 events/hour.", Profiler()
    store.accept(user, prepare(raw, request, profiler), profiler)
    profiled = ProfiledReviewStore(legacy.connect, profiler, clock=legacy.clock)
    for _ in range(20):
        if legacy.snapshot(user, request.case.case_id)["status"] != "assessing":
            break
        assert ReviewWorkflow(profiled, lambda note, policy, keys: insufficient(note, keys)).step()[
            "claimed"
        ]
    assert profiler.report()["counts"]["publication"] >= 1
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
    supplement = request.model_copy(
        update={
            "document": request.document.model_copy(update={"document_id": "supplement"}),
            "expected_version": 1,
        }
    )
    with pytest.raises(StateChanged):
        store.accept(user, prepare(raw, supplement, profiler), profiler)
    with store.store.transaction() as c:
        assert (
            c.execute(
                "SELECT COUNT(*) AS n FROM prior_auth_intake.receipts "
                "WHERE case_id=%s AND document_id='supplement'",
                (request.case.case_id,),
            ).fetchone()["n"]
            == 0
        )
    supplement = supplement.model_copy(update={"expected_version": 2})
    assert store.accept(user, prepare(raw, supplement, profiler), profiler) == 3
    assert store.accept(user, prepare(raw, supplement, profiler), profiler) == 3
    assert legacy.snapshot(user, request.case.case_id)["version"] == 3


def test_receipt_failure_rolls_back_enrollment_and_job(app):
    request, store, legacy, user = seed(app)
    server, trial, _, _ = app
    with server.connect(trial.name) as admin:
        admin.execute(
            sql.SQL("REVOKE INSERT ON prior_auth_intake.receipts FROM {}").format(
                sql.Identifier(trial.name)
            )
        )
    try:
        with pytest.raises(errors.InsufficientPrivilege):
            store.accept(user, prepare(b"AHI: 18 events/hour.", request, Profiler()), Profiler())
        with pytest.raises(LookupError):
            legacy.snapshot(user, request.case.case_id)
        with store.store.transaction() as c:
            assert (
                c.execute(
                    "SELECT COUNT(*) AS n FROM prior_auth_app.jobs WHERE case_id=%s",
                    (request.case.case_id,),
                ).fetchone()["n"]
                == 0
            )
    finally:
        with server.connect(trial.name) as admin:
            setup(admin, trial.name)
