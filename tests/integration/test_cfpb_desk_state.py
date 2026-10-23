"""Actual Postgres receipts, lease/restart boundaries, sessions and enqueue-only scope."""

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
from cfpb_triage.desk_auth import AuthStore, provision, setup_review
from cfpb_triage.desk_contracts import QueueCommand, StateChanged
from cfpb_triage.desk_store import DeskStore
from cfpb_triage.desk_worker import failed, step
from cfpb_triage.triage_contracts import digest_text
from test_cfpb_classifier import complaint, policy, prediction, taxonomy
from test_cfpb_desk import NOW, actor

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    root = tmp_path_factory.mktemp("cfpb-desk-workspace")
    shutil.copyfile(ROOT / "compose.yaml", root / "compose.yaml")
    workspace = Workspace(root)
    workspace.config(initialize=True)
    workspace.up()
    server, trial = workspace.server(), workspace.create("cfpb-c3-c4-acceptance")
    now = [NOW]
    try:
        with server.connect(trial.name) as admin:
            setup_review(admin, trial.name)
        yield (
            server,
            trial,
            DeskStore(lambda: server.connect_trial(trial), clock=lambda: now[0]),
            now,
            root,
        )
    finally:
        drop_trial(server, trial)
        workspace.down(destroy=True)


def seed(app):
    server, trial, store, now, root = app
    now[0] = NOW
    item = complaint().model_copy(update={"case_id": digest_text(uuid.uuid4().hex)})
    store.enroll(
        "demo",
        item,
        taxonomy(),
        policy(),
        review_ref="invented-reviewed-mask",
        provenance="invented",
    )
    return item.case_id, actor(item.case_id)


def test_concurrent_enqueue_receipts_reconstruction_and_stale_commands(app):
    server, trial, store, now, root = app
    case, user = seed(app)
    command = QueueCommand(command_id="review", expected_version=1, reason="expert_review")
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(lambda _: store.enqueue(user, case, command), range(2))) == [2, 2]
    rebuilt = DeskStore(lambda: server.connect_trial(trial), clock=lambda: now[0])
    row = rebuilt.snapshot(user, case)
    assert (
        row["status"] == "review_queued"
        and sum(e["kind"] == "review_enqueued" for e in row["events"]) == 1
    )
    with pytest.raises(StateChanged):
        store.enqueue(user, case, command.model_copy(update={"reason": "uncertainty"}))
    with pytest.raises(StateChanged):
        store.enqueue(user, case, command.model_copy(update={"command_id": "new"}))


def test_lease_expiration_and_review_override_refuse_stale_publication(app):
    server, trial, store, now, root = app
    case, user = seed(app)
    old = store.claim()
    assert old
    now[0] += timedelta(minutes=6)
    current = store.claim()
    assert current
    assert not store.finish(old, failed(old))
    assert store.finish(current, failed(current))
    assert not store.finish(current, failed(current))
    assert (
        sum(e["kind"] == "classification_recorded" for e in store.snapshot(user, case)["events"])
        == 1
    )
    case, user = seed(app)
    job = store.claim()
    assert job
    store.enqueue(
        user, case, QueueCommand(command_id="review", expected_version=1, reason="high_priority")
    )
    assert not store.finish(job, failed(job))


def test_runtime_permissions_account_disable_and_tenant_scope(app):
    server, trial, store, now, root = app
    case, user = seed(app)
    with pytest.raises(PermissionError):
        store.enqueue(
            actor(case, role="viewer"),
            case,
            QueueCommand(command_id="x", expected_version=1, reason="expert_review"),
        )
    with pytest.raises(LookupError):
        store.snapshot(actor(case, tenant="other"), case)
    with server.connect(trial.name) as admin:
        provision(admin, user, "invented-cfpb-desk-password")
    auth = AuthStore(lambda: server.connect_trial(trial), clock=lambda: now[0])
    token, csrf, _ = auth.login(user.username, "invented-cfpb-desk-password")
    assert auth.authenticate(token, csrf) == user
    with pytest.raises(PermissionError):
        auth.authenticate(token, "wrong")
    with server.connect(trial.name) as admin:
        admin.execute(
            "UPDATE cfpb_app.accounts SET enabled=false WHERE username=%s", (user.username,)
        )
    with pytest.raises(PermissionError):
        auth.authenticate(token, csrf)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with server.connect_trial(trial) as c:
            c.execute("DELETE FROM cfpb_app.events")
    job = store.claim()
    assert job
    assert store.finish(job, failed(job))


def test_claimed_attempts_are_bounded_and_forged_classification_is_rejected(app):
    server, trial, store, now, root = app
    case, user = seed(app)
    job = store.claim()
    assert job
    forged = failed(job).model_copy(update={"outcome": "classified", "prediction": prediction()})
    with pytest.raises(ValueError, match="completed attempt"):
        store.finish(job, forged)
    for _ in range(2):
        now[0] += timedelta(minutes=6)
        assert store.claim()
    now[0] += timedelta(minutes=6)
    calls = []
    assert step(store, lambda j: calls.append(j)) == {"claimed": True, "published": True}
    assert calls == [] and store.snapshot(user, case)["job"]["attempts"] == 4


def test_actual_process_exit_after_claim_can_be_reclaimed(app):
    server, trial, store, now, root = app
    case, user = seed(app)
    code = """import os,sys
sys.path.insert(0,'tests')
from pathlib import Path
from agent_harness.local_services import Workspace
from cfpb_triage.desk_store import DeskStore
from test_cfpb_desk import NOW
w=Workspace(Path(sys.argv[1]));s=w.server();t=w.load_trial('cfpb-c3-c4-acceptance')
assert DeskStore(lambda:s.connect_trial(t),clock=lambda:NOW).claim()
os._exit(19)
"""
    completed = subprocess.run(
        [sys.executable, "-c", code, str(root)],
        cwd=ROOT,
        timeout=60,
        check=False,
        capture_output=True,
    )
    assert completed.returncode == 19
    now[0] += timedelta(minutes=6)
    job = store.claim()
    assert job and job["attempts"] == 2
    assert store.finish(job, failed(job))
    assert store.snapshot(user, case)["status"] == "review_required"
