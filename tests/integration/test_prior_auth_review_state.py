"""Real Postgres version races, durable waits, recovery and scoped reviewer sessions."""

import json
import shutil
import subprocess
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path

import psycopg
import pytest
from agent_harness.local_services import Workspace
from agent_harness.postgres import drop_trial
from prior_auth.review_auth import AuthStore, provision, setup_review
from prior_auth.review_contracts import RedactedDelivery, ReviewNote, StateChanged, WaitRequest
from prior_auth.review_store import ReviewStore
from prior_auth.review_workflow import ReviewWorkflow
from test_prior_auth_review import NOW, actor, insufficient, note, policy

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    root = tmp_path_factory.mktemp("prior-auth-review-workspace")
    shutil.copyfile(ROOT / "compose.yaml", root / "compose.yaml")
    workspace = Workspace(root)
    workspace.config(initialize=True)
    workspace.up()
    server, trial = workspace.server(), workspace.create("prior-auth-p4-p5-acceptance")
    now = [NOW]
    try:
        with server.connect(trial.name) as admin:
            setup_review(admin, trial.name)
        yield (
            server,
            trial,
            ReviewStore(lambda: server.connect_trial(trial), clock=lambda: now[0]),
            now,
        )
    finally:
        drop_trial(server, trial)
        workspace.down(destroy=True)


def seed(app):
    server, trial, store, now = app
    now[0] = NOW
    key = "case-" + uuid.uuid4().hex
    store.enroll(note(key), policy(), review_ref="reviewed-invented")
    return key, actor(key)


def finish(store):
    return ReviewWorkflow(store, lambda note, policy, keys: insufficient(note, keys)).step()


def test_document_receipt_restart_and_only_affected_criteria(app):
    server, trial, store, now = app
    key, user = seed(app)
    assert finish(store)["published"]
    request = WaitRequest(
        command_id="wait",
        expected_version=1,
        criteria=("education",),
        deadline=NOW + timedelta(hours=1),
    )
    assert store.request(user, key, request) == 2
    assert store.request(user, key, request) == 2
    delivery = RedactedDelivery(
        delivery_id="doc",
        expected_version=2,
        text="CPAP education completed prior to use.",
        review_ref="explicit-reviewed-map",
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(lambda _: store.deliver(user, key, delivery), range(2))) == [3, 3]
    rebuilt = ReviewStore(lambda: server.connect_trial(trial), clock=lambda: now[0])
    row = rebuilt.snapshot(user, key)
    assert row["result"] is None and row["job"]["criteria"] == ["education"]
    seen = []

    def assessor(note, policy, keys):
        seen.append(keys)
        return insufficient(note, keys)

    assert ReviewWorkflow(rebuilt, assessor).step()["published"]
    assert seen == [("education",)]
    assert len(rebuilt.snapshot(user, key)["result"]["claims"]) == 7
    assert rebuilt.deliver(user, key, delivery) == 3
    assert not finish(rebuilt)["claimed"]
    with pytest.raises(StateChanged):
        rebuilt.deliver(user, key, delivery.model_copy(update={"text": "different"}))
    events = rebuilt.snapshot(user, key)["events"]
    assert sum(e["kind"] == "document_received" for e in events) == 1
    assert sum(e["kind"] == "assessment_completed" for e in events) == 2


def test_timeout_is_durable_and_late_delivery_requires_new_wait(app):
    server, trial, store, now = app
    key, user = seed(app)
    finish(store)
    request = WaitRequest(
        command_id="wait",
        expected_version=1,
        criteria=("education",),
        deadline=NOW + timedelta(minutes=1),
    )
    store.request(user, key, request)
    now[0] += timedelta(minutes=2)
    assert store.expire() == 1 and store.expire() == 0
    row = store.snapshot(user, key)
    assert row["status"] == "qualified_review" and row["version"] == 3
    with pytest.raises(StateChanged):
        store.deliver(
            user,
            key,
            RedactedDelivery(
                delivery_id="late", expected_version=3, text="New text", review_ref="reviewed"
            ),
        )
    renewed = request.model_copy(
        update={
            "command_id": "wait-again",
            "expected_version": 3,
            "deadline": now[0] + timedelta(hours=1),
        }
    )
    assert store.request(user, key, renewed) == 4
    assert (
        sum(e["kind"] == "document_wait_expired" for e in store.snapshot(user, key)["events"]) == 1
    )


def test_policy_change_obsoletes_in_flight_job_and_all_prior_findings(app):
    server, trial, store, now = app
    key, user = seed(app)
    stale = store.claim()
    assert stale
    changed = policy().model_copy(update={"review_ref": "new-reviewed-pin"})
    assert store.replace_policy(user, key, changed, version=1) == 2
    assert not store.finish(stale, insufficient(note(key)))
    row = store.snapshot(user, key)
    assert row["candidate"] is None and row["result"] is None
    assert set(row["job"]["criteria"]) == {c.criterion_id for c in policy().criteria}
    assert finish(store)["published"]
    assert store.snapshot(user, key)["note"]["policy_sha256"] != note(key).policy_sha256


def test_hard_process_exit_reclaims_lease_without_duplicate_result(app):
    server, trial, store, now = app
    key, user = seed(app)
    script = """import json,os,psycopg
from prior_auth.review_store import ReviewStore
value=json.loads(__import__('sys').stdin.read())
store=ReviewStore(lambda:psycopg.connect(**value))
assert store.claim() is not None
os._exit(19)
"""
    data = {
        "host": "127.0.0.1",
        "port": server.port,
        "dbname": trial.name,
        "user": trial.name,
        "password": trial.password,
    }
    result = subprocess.run(
        [sys.executable, "-c", script], input=json.dumps(data), text=True, capture_output=True
    )
    assert result.returncode == 19
    # Child uses real wall time; make test clock definitely later than its lease.
    from datetime import UTC, datetime

    now[0] = datetime.now(UTC) + timedelta(minutes=6)
    assert finish(store)["published"]
    row = store.snapshot(user, key)
    assert row["job"]["attempts"] == 2
    assert sum(e["kind"] == "assessment_completed" for e in row["events"]) == 1
    assert not finish(store)["claimed"]


def test_worker_lease_replacement_refuses_old_result_and_attempts_are_bounded(app):
    server, trial, store, now = app
    key, user = seed(app)
    old = store.claim()
    for _ in range(2):
        now[0] += timedelta(minutes=6)
        newer = store.claim()
        assert newer and not store.finish(old, insufficient(note(key)))
        old = newer
    now[0] += timedelta(minutes=6)

    def must_not_call(*args):
        raise AssertionError("exhausted job cannot call provider")

    assert ReviewWorkflow(store, must_not_call).step()["published"]
    row = store.snapshot(user, key)
    assert row["status"] == "qualified_review" and row["result"]["assessment_failure"]


def test_tenant_roles_sessions_exact_review_and_runtime_privileges(app):
    server, trial, store, now = app
    key, user = seed(app)
    finish(store)
    with pytest.raises(LookupError):
        store.snapshot(user.model_copy(update={"tenant_id": "other"}), key)
    viewer = user.model_copy(update={"role": "viewer"})
    review = ReviewNote(
        command_id="review", expected_version=1, outcome="qualified_review", reason="expert_review"
    )
    with pytest.raises(PermissionError):
        store.review(viewer, key, review)
    assert store.review(user, key, review) == 2 and store.review(user, key, review) == 2
    with pytest.raises(StateChanged):
        store.review(user, key, review.model_copy(update={"command_id": "other"}))
    with server.connect(trial.name) as admin:
        provision(admin, user, "invented-reviewer-password")
    auth = AuthStore(lambda: server.connect_trial(trial), clock=lambda: now[0])
    token, csrf, principal = auth.login(user.username, "invented-reviewer-password")
    assert auth.authenticate(token, csrf) == user
    with pytest.raises(PermissionError):
        auth.authenticate(token, "wrong-csrf")
    auth.logout(token)
    with pytest.raises(PermissionError):
        auth.authenticate(token, csrf)
    with server.connect_trial(trial) as runtime:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            runtime.execute("DELETE FROM prior_auth_app.events")


def test_model_sees_only_reviewed_input_and_events_never_capture_identifier(app, tmp_path):
    from prior_auth.contracts import digest
    from prior_auth.review_cli import reviewed_text

    server, trial, store, now = app
    key = "privacy-" + uuid.uuid4().hex
    raw = "Name: SecretIdentifierCanary\nEducation not documented."
    path = tmp_path / "raw.txt"
    mapping = tmp_path / "map.json"
    path.write_text(raw, encoding="utf-8")
    mapping.write_text(
        json.dumps(
            [{"kind": "name", "source": {"start": 6, "end": 28, "quote": "SecretIdentifierCanary"}}]
        ),
        encoding="utf-8",
    )
    text = reviewed_text(path, mapping)
    value = note(key).model_copy(update={"text": text, "note_sha256": digest(text)})
    store.enroll(value, policy(), review_ref="reviewed-canary")
    seen = []

    def assessor(n, p, keys):
        seen.append(n.canonical_json())
        return insufficient(n, keys)

    assert ReviewWorkflow(store, assessor).step()["published"]
    events = json.dumps(store.snapshot(actor(key), key)["events"])
    assert seen and "SecretIdentifierCanary" not in "".join(seen) + events
