"""Real SQL demo scope/attempt fences, crash/replay, document resume and citation readback."""

import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
from agent_harness.contracts import ModelMessage
from prior_auth.contracts import digest
from prior_auth.review_contracts import StateChanged, WaitRequest
from psycopg import errors
from test_prior_auth_review import NOW, actor, policy
from test_prior_auth_review_state import app as app

from prior_auth_demo import demo_request
from prior_auth_demo_fixtures import EDUCATION, ScriptedGateway, fake_scope, note
from prior_auth_demo_runtime import DemoWorker, provision_scope, setup
from prior_auth_documents import normalize
from prior_auth_evidence_cards import EvidenceReader
from prior_auth_pipeline import prepare
from prior_auth_profiling import Profiler
from prior_auth_store import IntakeStore
from prior_auth_store import setup as setup_intake


def seed(app, *, missing=False, gateway=None):
    server, trial, store, now = app
    now[0] = NOW
    case = "demo-" + uuid.uuid4().hex
    value = note(case, policy(), missing_education=missing)
    raw = value.text.encode()
    imported = demo_request(raw, case_id=case).model_copy(update={"policy": policy()})
    # demo_request registry binds its own fixture policy; keep both pins coherent.
    imported = imported.model_copy(
        update={
            "registry": imported.registry.model_copy(
                update={
                    "entries": (
                        imported.registry.entries[0].model_copy(
                            update={"policy_sha256": value.policy_sha256}
                        ),
                    )
                }
            )
        }
    )
    with server.connect(trial.name) as admin:
        setup_intake(admin, trial.name)
        setup(admin, trial.name)
    intake = IntakeStore(store.connect, clock=store.clock)
    intake.accept(actor(case), prepare(raw, imported, Profiler()), Profiler())
    # The actual imported date differs from the standalone value; use canonical SQL.
    from prior_auth.contracts import NoteInput

    value = NoteInput.model_validate_json(json.dumps(store.snapshot(actor(case), case)["note"]))
    scope = fake_scope("scope-" + uuid.uuid4().hex, (value,), policy(), now=NOW)
    with server.connect(trial.name) as admin:
        provision_scope(admin, scope)
    gateway = gateway or ScriptedGateway()
    return case, value, scope, gateway, DemoWorker(store, scope, gateway), intake, imported


def test_complete_case_uses_seven_durable_attempts_and_two_source_types(app):
    case, _, scope, gateway, worker, _, _ = seed(app)
    store = app[2]
    assert worker.step() == {
        "claimed": True,
        "published": True,
        "sent": 7,
        "replayed": 0,
        "blocked": 0,
        "candidate": scope.candidate,
        "clinical_validation": False,
    }
    assert len(gateway.requests) == 7
    cards = EvidenceReader(store).cards(actor(case), case, expected_version=1)
    assert len(cards) == 7 and all(c.state == "met" and c.source_mapping == "mapped" for c in cards)
    assert all(c.policy_requirement.quote and c.document_citations[0].locations for c in cards)
    assert all(c.clinical_validation is False for c in cards)
    assert worker.step()["claimed"] is False


def test_crash_after_settlement_reuses_responses_and_sends_zero_on_lease_recovery(app, monkeypatch):
    case, _, scope, gateway, worker, _, _ = seed(app)
    store, now = app[2], app[3]
    original = store.finish
    monkeypatch.setattr(store, "finish", lambda *args: (_ for _ in ()).throw(SystemExit()))
    with pytest.raises(SystemExit):
        worker.step()
    assert len(gateway.requests) == 7
    now[0] = NOW + timedelta(minutes=6)
    monkeypatch.setattr(store, "finish", original)
    result = DemoWorker(store, scope, gateway).step()
    assert result["published"] and result["sent"] == 0 and result["replayed"] == 7
    assert len(gateway.requests) == 7
    assert store.snapshot(actor(case), case)["status"] == "evidence_complete_for_review"


def test_death_after_reservation_is_consumed_and_never_automatically_resent(app):
    class Death:
        calls = 0

        def generate(self, *args):
            self.calls += 1
            raise SystemExit()

    dead = Death()
    case, _, scope, _, worker, _, _ = seed(app, gateway=dead)
    with pytest.raises(SystemExit):
        worker.step()
    app[3][0] = NOW + timedelta(minutes=6)
    result = DemoWorker(app[2], scope, dead).step()
    assert result["sent"] == 0 and result["blocked"] == 1 and dead.calls == 1
    assert app[2].snapshot(actor(case), case)["status"] == "qualified_review"
    with app[2].transaction() as c:
        counts = c.execute(
            "SELECT count(*) AS n FROM prior_auth_demo.attempts WHERE scope_id=%s",
            (scope.scope_id,),
        ).fetchone()
        assert counts["n"] == 1


def test_scope_budget_exhaustion_never_dispatches_extra_criterion(app):
    case, value, _, gateway, _, _, _ = seed(app)
    scope = fake_scope("budget-" + uuid.uuid4().hex, (value,), policy(), now=NOW).model_copy(
        update={"max_attempts": 1}
    )
    with app[0].connect(app[1].name) as admin:
        provision_scope(admin, scope)
    result = DemoWorker(app[2], scope, gateway).step()
    assert result["sent"] == 1 and result["blocked"] == 1 and len(gateway.requests) == 1
    assert app[2].snapshot(actor(case), case)["status"] == "qualified_review"


def test_concurrent_workers_do_not_duplicate_a_current_job(app):
    case, _, _, gateway, worker, _, _ = seed(app)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: worker.step(), range(2)))
    assert sum(r["claimed"] for r in results) == 1 and len(gateway.requests) == 7
    assert app[2].snapshot(actor(case), case)["status"] == "evidence_complete_for_review"


def test_runtime_role_cannot_extend_scope_delete_attempts_or_rewrite_responses(app):
    _, _, scope, _, worker, _, _ = seed(app)
    worker.step()
    for statement in (
        "DELETE FROM prior_auth_demo.attempts WHERE scope_id=%s",
        "DELETE FROM prior_auth_demo.settlements WHERE scope_id=%s",
        "UPDATE prior_auth_demo.scopes SET scope_sha256='altered' WHERE scope_id=%s",
    ):
        with pytest.raises(errors.InsufficientPrivilege), app[2].transaction() as c:
            c.execute(statement, (scope.scope_id,))


def test_supplement_reassesses_only_education_and_binds_both_document_sources(app):
    case, _, _, _, worker, intake, imported = seed(app, missing=True)
    store = app[2]
    user = actor(case)
    assert worker.step()["sent"] == 6
    before = store.snapshot(user, case)
    assert (
        next(c for c in before["result"]["claims"] if c["criterion_id"] == "education")["state"]
        == "insufficient"
    )
    store.request(
        user,
        case,
        WaitRequest(
            command_id="wait",
            expected_version=1,
            criteria=("education",),
            deadline=NOW + timedelta(hours=1),
        ),
    )
    raw = EDUCATION.encode()
    supplement = imported.model_copy(
        update={
            "document": imported.document.model_copy(update={"document_id": "education"}),
            "expected_version": 2,
            "source_sha256": digest(EDUCATION),
            "normalization_sha256": normalize(raw, "text").text_sha256,
        }
    )
    intake.accept(user, prepare(raw, supplement, Profiler()), Profiler())
    from prior_auth.contracts import NoteInput

    current = NoteInput.model_validate_json(json.dumps(store.snapshot(user, case)["note"]))
    scope = fake_scope("resume-" + uuid.uuid4().hex, (current,), policy(), now=NOW)
    with app[0].connect(app[1].name) as admin:
        provision_scope(admin, scope)

    # On resume a real candidate should select the education sentence, not the note
    # separator, which is not part of either imported source document.
    class EducationOnly(ScriptedGateway):
        def generate(self, ctx, request):
            result = super().generate(ctx, request)
            value = json.loads(result.output.content)
            value["quotes"] = [EDUCATION]
            return result.model_copy(
                update={"output": ModelMessage(role="assistant", content=json.dumps(value))}
            )

    result = DemoWorker(store, scope, EducationOnly()).step()
    assert result["sent"] == 1 and result["published"]
    cards = EvidenceReader(store).cards(user, case, expected_version=3)
    education = next(c for c in cards if c.criterion == "education")
    assert education.state == "met" and education.source_mapping == "mapped"
    assert education.document_citations[0].locations[0].document_id == "education"
    with pytest.raises(StateChanged):
        EvidenceReader(store).cards(user, case, expected_version=1)


def test_wrong_viewer_scope_or_tampered_result_cannot_return_evidence_cards(app):
    case, _, _, _, worker, _, _ = seed(app)
    worker.step()
    with pytest.raises(PermissionError):
        EvidenceReader(app[2]).cards(actor("other"), case, expected_version=1)
    with app[0].connect(app[1].name) as admin:
        admin.execute(
            "UPDATE prior_auth_app.cases SET result='{}'::jsonb WHERE case_id=%s", (case,)
        )
    with pytest.raises(StateChanged):
        EvidenceReader(app[2]).cards(actor(case), case, expected_version=1)
