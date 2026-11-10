"""Real database work receipts, blinded arms, actual denied attacks and stale leases."""

import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import psycopg
import pytest
from cfpb_triage.desk_api import create_app
from cfpb_triage.desk_auth import AuthStore, provision
from cfpb_triage.desk_contracts import StateChanged
from cfpb_triage.evaluation_store import (
    EvaluationStore,
    WorkCommand,
    provision_participant,
    setup_evaluation,
)
from cfpb_triage.scope_routing import ScopeAttempt, ScopeDecision, ScopeOutput
from cfpb_triage.triage_contracts import digest_text
from fastapi.testclient import TestClient
from test_cfpb_classifier import complaint, taxonomy
from test_cfpb_desk import NOW, actor
from test_cfpb_desk_state import app as app
from test_cfpb_evaluation_v2 import policy_v2, wire


@pytest.fixture(scope="module")
def evaluation(app):
    server, trial, _, now, _ = app
    with server.connect(trial.name) as admin:
        setup_evaluation(admin, trial.name)
        provision_participant(admin, "demo", "reviewer")
    store = EvaluationStore(lambda: server.connect_trial(trial), clock=lambda: now[0])
    return store


def seed(app, evaluation, arm="manual"):
    now = app[3]
    now[0] = NOW
    item = complaint().model_copy(update={"case_id": digest_text(uuid.uuid4().hex)})
    evaluation.enroll_evaluation(
        "demo",
        item,
        taxonomy(),
        policy_v2(),
        family=uuid.uuid4().hex,
        actor="reviewer",
        arm=arm,
        review_ref="invented-reviewed",
    )
    return item, actor(item.case_id)


def test_manual_has_no_job_no_candidate_and_no_legacy_record(app, evaluation):
    item, user = seed(app, evaluation)
    assert evaluation.evaluation_snapshot(user, item.case_id)["result"] is None
    with evaluation.transaction() as c:
        assert (
            c.execute("SELECT * FROM cfpb_eval.jobs WHERE case_id=%s", (item.case_id,)).fetchone()
            is None
        )
    with pytest.raises(LookupError):
        app[2].snapshot(user, item.case_id)
    with pytest.raises(PermissionError):
        evaluation.evaluation_snapshot(user.model_copy(update={"actor_id": "other"}), item.case_id)


def test_real_concurrent_receipt_pause_correction_and_final_acceptance(app, evaluation):
    item, user = seed(app, evaluation)
    start = WorkCommand(command_id="start", expected_version=1, operation="start")
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(lambda _: evaluation.work(user, item.case_id, start), range(2))) == [
            2,
            2,
        ]
    app[3][0] += timedelta(seconds=30)
    final = ScopeOutput.model_validate_json(json.dumps(wire()))
    correction = WorkCommand(
        command_id="correct",
        expected_version=2,
        operation="correct",
        active_seconds=20.0,
        final=final,
    )
    assert evaluation.work(user, item.case_id, correction) == 3
    with pytest.raises(StateChanged):
        evaluation.work(user, item.case_id, correction.model_copy(update={"active_seconds": 25.0}))
    assert (
        evaluation.work(
            user,
            item.case_id,
            WorkCommand(command_id="resume", expected_version=3, operation="start"),
        )
        == 4
    )
    app[3][0] += timedelta(seconds=10)
    accept = WorkCommand(
        command_id="accept", expected_version=4, operation="accept", active_seconds=5.0, final=final
    )
    assert evaluation.work(user, item.case_id, accept) == 5
    rebuilt = EvaluationStore(evaluation.connect, clock=evaluation.clock)
    row = rebuilt.evaluation_snapshot(user, item.case_id)
    assert row["active_seconds"] == 25 and row["accepted_at"] and row["result"] is None
    assert rebuilt.work(user, item.case_id, accept) == 5
    with evaluation.transaction() as c:
        assert (
            c.execute(
                "SELECT count(*) AS n FROM cfpb_eval.events WHERE case_id=%s", (item.case_id,)
            ).fetchone()["n"]
            == 4
        )


def decision(claim):
    return ScopeDecision(
        case_id=claim["case_id"],
        narrative_sha256=digest_text(complaint().narrative),
        taxonomy_sha256=taxonomy().digest(),
        policy_sha256=digest_text(policy_v2().canonical_json()),
        scope=None,
        action="review_required",
        reason="operational_failure",
        prediction=None,
        attempts=(ScopeAttempt(route="cheap", model="invented", failure="unavailable"),),
        timings=(),
    )


def test_expired_lease_duplicate_and_version_fences(app, evaluation):
    item, user = seed(app, evaluation, arm="assisted")
    old = evaluation.claim_evaluation()
    assert old
    app[3][0] += timedelta(minutes=6)
    claim = evaluation.claim_evaluation()
    assert claim and claim["attempts"] == 2
    assert not evaluation.finish_evaluation(old, decision(old))
    assert evaluation.finish_evaluation(claim, decision(claim))
    assert not evaluation.finish_evaluation(claim, decision(claim))
    assert evaluation.evaluation_snapshot(user, item.case_id)["version"] == 2


def test_worker_cannot_publish_after_human_acceptance(app, evaluation):
    item, user = seed(app, evaluation, arm="assisted")
    claim = evaluation.claim_evaluation()
    assert claim
    evaluation.work(
        user, item.case_id, WorkCommand(command_id="start", expected_version=1, operation="start")
    )
    app[3][0] += timedelta(seconds=1)
    evaluation.work(
        user,
        item.case_id,
        WorkCommand(
            command_id="accept",
            expected_version=2,
            operation="accept",
            final=ScopeOutput.model_validate_json(json.dumps(wire())),
        ),
    )
    assert not evaluation.finish_evaluation(claim, decision(claim))


def test_append_only_events_and_capability_provisioning_are_database_enforced(app, evaluation):
    with pytest.raises(psycopg.errors.InsufficientPrivilege), evaluation.transaction() as c:
        c.execute("DELETE FROM cfpb_eval.events")
    with pytest.raises(psycopg.errors.InsufficientPrivilege), evaluation.transaction() as c:
        c.execute("INSERT INTO cfpb_eval.participants VALUES('demo','injected')")


def test_actual_http_attacks_cannot_mutate_or_read_other_case(app, evaluation):
    item, user = seed(app, evaluation)
    server, trial, legacy, now, _ = app
    user = user.model_copy(update={"username": "eval-" + uuid.uuid4().hex[:12]})
    with server.connect(trial.name) as admin:
        provision(admin, user, "invented-test-password")
    origin = "http://127.0.0.1:9051"
    api = create_app(
        legacy,
        AuthStore(evaluation.connect, clock=lambda: now[0]),
        origin=origin,
        trial_id=trial.name,
        evaluation=evaluation,
    )
    client = TestClient(api, base_url=origin)
    path = "/api/v2/evaluation/" + item.case_id
    assert client.get(path).status_code == 403
    login = client.post(
        "/api/login",
        json={"username": user.username, "password": "invented-test-password"},
        headers={"origin": origin},
    )
    assert login.status_code == 200
    csrf = next(v for k, v in client.cookies.items() if "csrf" in k)
    payload = {"command_id": "attack", "expected_version": 1, "operation": "start"}
    assert client.post(path + "/work", json=payload).status_code == 403
    headers = {"origin": origin, "x-csrf-token": csrf}
    assert (
        client.post(path + "/work", json={**payload, "refund": True}, headers=headers).status_code
        == 422
    )
    assert (
        client.post(
            path + "/work", json={**payload, "operation": "delete"}, headers=headers
        ).status_code
        == 422
    )
    assert client.get("/api/v2/evaluation/other").status_code == 403
    assert client.get(path).json()["result"] is None
    assert client.get("/evaluation").status_code == 200
    assert "innerHTML" not in client.get("/evaluation.js").text
    assert evaluation.evaluation_snapshot(user, item.case_id)["version"] == 1
    with evaluation.transaction() as c:
        assert (
            c.execute(
                "SELECT count(*) AS n FROM cfpb_eval.events WHERE case_id=%s "
                "AND kind<>'api_timing'",
                (item.case_id,),
            ).fetchone()["n"]
            == 0
        )


def test_durable_work_export_does_not_invent_correctness_or_cost(app, evaluation):
    item, user = seed(app, evaluation)
    evaluation.work(
        user,
        item.case_id,
        WorkCommand(
            command_id="start", expected_version=1, operation="start", work_kind="correction"
        ),
    )
    app[3][0] += timedelta(seconds=15)
    evaluation.work(
        user,
        item.case_id,
        WorkCommand(command_id="pause", expected_version=2, operation="pause", active_seconds=10.0),
    )
    exported = evaluation.export_work(user, currency="USD")
    assert exported[0].correction_seconds == 10 and exported[0].initial_seconds == 0
    assert exported[0].correct is None and exported[0].recurring_machine_cost is None
    assert exported[0].accepted is None
    assert exported[0].basis == "invented"


def test_expired_worker_claim_never_redispatches_and_records_actual_timings(app, evaluation):
    from cfpb_triage.evaluation_worker import step_evaluation

    item, _ = seed(app, evaluation, arm="assisted")
    assert evaluation.claim_evaluation()
    app[3][0] += timedelta(minutes=6)

    def forbidden(_):
        raise AssertionError("expired attempt was redispatched")

    assert step_evaluation(evaluation, forbidden) == {"claimed": True, "published": True}
    with evaluation.transaction() as c:
        row = c.execute(
            "SELECT metadata FROM cfpb_eval.events WHERE case_id=%s AND kind='api_timing'",
            (item.case_id,),
        ).fetchone()
        assert {t["stage"] for t in row["metadata"]["timings"]} >= {
            "claim",
            "publication",
            "commit",
        }
