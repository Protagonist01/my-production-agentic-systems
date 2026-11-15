"""Canonical SQL, authenticated API and durable reference-payer desk witnesses."""

import hashlib
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from prior_auth.review_auth import AuthStore, provision
from prior_auth.review_contracts import ReviewNote, StateChanged, WaitRequest
from psycopg import errors
from test_prior_auth_demo_runtime_state import seed
from test_prior_auth_release_readiness import payer_response
from test_prior_auth_review import NOW, actor, policy
from test_prior_auth_review_state import app as app

from prior_auth_demo_console import plan
from prior_auth_demo_fixtures import ScriptedGateway
from prior_auth_demo_runtime import DemoWorker, provision_scope, setup
from prior_auth_demo_web import demo_app
from prior_auth_operator import import_document
from prior_auth_pas import Loopback, PasClient, encoded, object_from
from prior_auth_payer_desk import PayerCommand, PayerDesk
from prior_auth_pipeline import prepare
from prior_auth_profiling import Profiler
from prior_auth_store import IntakeStore
from prior_auth_store import setup as setup_intake

COMMAND = PayerCommand(expected_version=1, confirm_synthetic_exchange=True)


def configured(app, tmp_path, *, transport=None):
    case, _, _, _, worker, _, imported = seed(app)
    worker.step()
    calls, resources = [], {}

    def scripted(method, path, payload):
        calls.append((method, path))
        if path == "Claim/$submit":
            response, claim = payer_response(payload)
            resources["Claim/server-claim"] = claim
            resources["response"] = response
            return encoded(response)
        if path == "Claim/$inquire":
            return encoded(
                {
                    "resourceType": "Parameters",
                    "parameter": [{"name": "responseBundle", "resource": resources["response"]}],
                }
            )
        return encoded(resources[path])

    client = PasClient(tmp_path / "payer.sqlite", transport or scripted)
    return case, PayerDesk(app[2], client, (imported.case,)), calls


def test_sql_case_submission_is_idempotent_concurrently_and_inquiry_is_separate(app, tmp_path):
    case, desk, calls = configured(app, tmp_path)
    assert desk.status(actor(case), case, 1)["submission"] is None
    assert not calls
    with ThreadPoolExecutor(max_workers=2) as pool:
        rows = list(
            pool.map(lambda _: desk.exchange(actor(case), case, COMMAND, inquire=False), range(2))
        )
    assert all(r["submission"]["state"] == "received" for r in rows)
    assert calls.count(("POST", "Claim/$submit")) == 1
    rebuilt = PayerDesk(app[2], desk.client, tuple(desk.bindings.values()))
    result = rebuilt.exchange(actor(case), case, COMMAND, inquire=True)
    assert result["inquiry"]["review_codes"] == ["A3"]
    assert rebuilt.status(actor(case), case, 1) == result
    assert calls.count(("POST", "Claim/$submit")) == 1
    assert result["clinical_validation"] is False and result["note_exported"] is False


def test_stale_viewer_foreign_tenant_and_changed_binding_fail_before_network(app, tmp_path):
    case, desk, calls = configured(app, tmp_path)
    denied = [
        actor(case, role="viewer"),
        actor("other"),
        actor(case).model_copy(update={"tenant_id": "other"}),
    ]
    for user in denied:
        with pytest.raises(PermissionError):
            desk.exchange(user, case, COMMAND, inquire=False)
    with pytest.raises(StateChanged):
        desk.exchange(
            actor(case), case, COMMAND.model_copy(update={"expected_version": 2}), inquire=False
        )
    original = desk.bindings[("demo", case)]
    desk.bindings[("demo", case)] = original.model_copy(update={"payer_id": "demo-different"})
    with pytest.raises(StateChanged):
        desk.exchange(actor(case), case, COMMAND, inquire=False)
    assert not calls


def test_unknown_submission_is_never_reposted_and_inquiry_failure_stays_explicit(app, tmp_path):
    calls = []

    def lost(method, path, payload):
        calls.append(path)
        raise TimeoutError("private-body-must-not-persist")

    case, desk, _ = configured(app, tmp_path, transport=lost)
    first = desk.exchange(actor(case), case, COMMAND, inquire=False)
    assert first["submission"]["state"] == "unknown"
    assert desk.exchange(actor(case), case, COMMAND, inquire=False) == first
    result = desk.exchange(actor(case), case, COMMAND, inquire=True)
    assert result["submission"] == first["submission"]
    assert result["inquiry"]["state"] == "unavailable"
    assert calls == ["Claim/$submit", "Claim/$inquire"]
    assert "private-body" not in desk.client.journal.read_bytes().decode(errors="ignore")


def test_inquiry_requires_existing_explicit_submission(app, tmp_path):
    case, desk, calls = configured(app, tmp_path)
    with pytest.raises(StateChanged):
        desk.exchange(actor(case), case, COMMAND, inquire=True)
    assert not calls


def test_uncertain_older_packet_blocks_a_new_revision(app, tmp_path):
    calls = []

    def lost(method, path, payload):
        calls.append(path)
        raise TimeoutError()

    case, desk, _ = configured(app, tmp_path, transport=lost)
    desk.exchange(actor(case), case, COMMAND, inquire=False)
    assert (
        app[2].request(
            actor(case),
            case,
            WaitRequest(
                command_id="new-revision",
                expected_version=1,
                criteria=("education",),
                deadline=NOW + timedelta(hours=1),
            ),
        )
        == 2
    )
    assert desk.status(actor(case), case, 2)["blocked_prior_unknown"]
    with pytest.raises(StateChanged):
        desk.exchange(
            actor(case), case, COMMAND.model_copy(update={"expected_version": 2}), inquire=False
        )
    assert calls == ["Claim/$submit"]


def test_crash_after_packet_index_does_not_allow_a_blind_first_post(app, tmp_path, monkeypatch):
    case, desk, calls = configured(app, tmp_path)
    monkeypatch.setattr(desk.client, "submit", lambda *a, **k: (_ for _ in ()).throw(SystemExit()))
    with pytest.raises(SystemExit):
        desk.exchange(actor(case), case, COMMAND, inquire=False)
    assert desk.status(actor(case), case, 1)["blocked_prior_unknown"]
    with pytest.raises(StateChanged):
        desk.exchange(actor(case), case, COMMAND, inquire=False)
    assert not calls


def test_canonical_case_stays_locked_during_submission(app, tmp_path):
    case, desk, calls = configured(app, tmp_path)
    original = desk.client.transport
    observed = []

    def checked(method, path, payload):
        if path == "Claim/$submit":
            with pytest.raises(errors.LockNotAvailable), app[0].connect(app[1].name) as admin:
                admin.execute(
                    "SELECT version FROM prior_auth_app.cases WHERE tenant_id='demo' "
                    "AND case_id=%s FOR UPDATE NOWAIT",
                    (case,),
                )
            observed.append("locked")
        return original(method, path, payload)

    desk.client.transport = checked
    assert (
        desk.exchange(actor(case), case, COMMAND, inquire=False)["submission"]["state"]
        == "received"
    )
    assert observed == ["locked"] and calls.count(("POST", "Claim/$submit")) == 1


def api_client(app, case, desk):
    principal = actor(case).model_copy(update={"username": "payer-" + case[-16:]})
    with app[0].connect(app[1].name) as admin:
        provision(admin, principal, "invented-payer-password-2026")
    client = TestClient(
        demo_app(
            app[2],
            AuthStore(app[2].connect, clock=app[2].clock),
            origin="http://127.0.0.1:8766",
            trial_id=app[1].name,
            payer_desk=desk,
        ),
        base_url="http://127.0.0.1:8766",
    )
    return client, principal


def test_api_requires_session_csrf_origin_confirmation_and_only_canonical_fields(app, tmp_path):
    case, desk, calls = configured(app, tmp_path)
    client, principal = api_client(app, case, desk)
    url = "/api/cases/" + case + "/payer/submit"
    with client:
        assert client.post(url, json=COMMAND.model_dump()).status_code == 403
        assert (
            client.post(
                "/api/login",
                headers={"origin": "http://127.0.0.1:8766"},
                json={"username": principal.username, "password": "invented-payer-password-2026"},
            ).status_code
            == 200
        )
        suffix = hashlib.sha256(app[1].name.encode()).hexdigest()[:12]
        headers = {
            "origin": "http://127.0.0.1:8766",
            "x-csrf-token": client.cookies["prior_auth_csrf_" + suffix],
        }
        assert client.post(url, json=COMMAND.model_dump()).status_code == 403
        assert (
            client.post(
                url,
                headers={**headers, "origin": "http://foreign.invalid"},
                json=COMMAND.model_dump(),
            ).status_code
            == 403
        )
        assert client.post(url, headers=headers, json={"expected_version": 1}).status_code == 422
        assert (
            client.post(
                url,
                headers=headers,
                json={**COMMAND.model_dump(), "payer_endpoint": "http://foreign.invalid"},
            ).status_code
            == 422
        )
        assert not calls
        sent = client.post(url, headers=headers, json=COMMAND.model_dump())
        assert sent.status_code == 200 and sent.json()["submission"]["state"] == "received"
        assert client.get("/api/cases/" + case).json()["payer"] == sent.json()
        assert client.post(url, headers=headers, json=COMMAND.model_dump()).json() == sent.json()
        assert calls.count(("POST", "Claim/$submit")) == 1


@pytest.mark.skipif(
    not os.environ.get("PRIOR_AUTH_REFERENCE_PAYER_URL"),
    reason="owned reference process not configured",
)
def test_actual_reference_payer_through_authenticated_sql_desk(app, tmp_path):
    transport = Loopback(os.environ["PRIOR_AUTH_REFERENCE_PAYER_URL"], timeout=10)
    calls = []
    matches = []

    def observed(method, path, payload):
        calls.append((method, path))
        raw = transport(method, path, payload)
        if path == "Claim/$inquire":
            matches.append(len(object_from(raw).get("parameter", [])))
        return raw

    case, desk, _ = configured(app, tmp_path, transport=observed)
    client, principal = api_client(app, case, desk)
    with client:
        assert (
            client.post(
                "/api/login",
                headers={"origin": "http://127.0.0.1:8766"},
                json={"username": principal.username, "password": "invented-payer-password-2026"},
            ).status_code
            == 200
        )
        suffix = hashlib.sha256(app[1].name.encode()).hexdigest()[:12]
        headers = {
            "origin": "http://127.0.0.1:8766",
            "x-csrf-token": client.cookies["prior_auth_csrf_" + suffix],
        }
        url = "/api/cases/" + case + "/payer/"
        sent = client.post(url + "submit", headers=headers, json=COMMAND.model_dump())
        assert sent.status_code == 200 and sent.json()["submission"]["state"] == "received"
        assert sent.json()["submission"]["review_codes"] == ["A3"]
        assert (
            client.post(url + "submit", headers=headers, json=COMMAND.model_dump()).json()
            == sent.json()
        )
        inquiry = client.post(url + "inquire", headers=headers, json=COMMAND.model_dump())
        assert inquiry.status_code == 200 and inquiry.json()["inquiry"].get("review_codes") == [
            "A3"
        ], {"inquiry_matches": matches}
        assert calls.count(("POST", "Claim/$submit")) == 1
        assert calls.count(("POST", "Claim/$inquire")) == 1
        # Same patient, coverage and service, but a new explicit packet. The trace
        # must disambiguate inquiry without accepting a first/ambiguous match.
        assert (
            app[2].review(
                actor(case),
                case,
                ReviewNote(
                    command_id="second-packet",
                    expected_version=1,
                    outcome="qualified_review",
                    reason="expert_review",
                ),
            )
            == 2
        )
        second = {"expected_version": 2, "confirm_synthetic_exchange": True}
        assert (
            client.post(url + "submit", headers=headers, json=second).json()["submission"]["state"]
            == "received"
        )
        response = client.post(url + "inquire", headers=headers, json=second)
        assert response.status_code == 200 and response.json()["inquiry"].get("review_codes") == [
            "A3"
        ], {"inquiry_matches": matches}
        assert matches == [1, 1]
        assert calls.count(("POST", "Claim/$submit")) == 2


@pytest.mark.skipif(
    not os.environ.get("PRIOR_AUTH_REFERENCE_PAYER_URL"),
    reason="owned reference process not configured",
)
def test_actual_reference_payer_after_document_wait_and_resume(app, tmp_path):
    imported, scope, files = plan(policy(), now=NOW, scenario="education-wait")
    case = imported.case.case_id
    app[3][0] = NOW
    with app[0].connect(app[1].name) as admin:
        setup_intake(admin, app[1].name)
        setup(admin, app[1].name)
        provision_scope(admin, scope)
    for name, value in files.items():
        (tmp_path / name).write_text(value, encoding="utf-8")
    user, store = actor(case), app[2]
    IntakeStore(store.connect, clock=store.clock).accept(
        user, prepare(files["source.txt"].encode(), imported, Profiler()), Profiler()
    )
    worker = DemoWorker(store, scope, ScriptedGateway())
    assert worker.step()["sent"] == 6
    desk = PayerDesk(
        store,
        PasClient(
            tmp_path / "payer.sqlite",
            Loopback(os.environ["PRIOR_AUTH_REFERENCE_PAYER_URL"], timeout=10),
        ),
        (imported.case,),
    )
    client, principal = api_client(app, case, desk)
    with client:
        assert (
            client.post(
                "/api/login",
                headers={"origin": "http://127.0.0.1:8766"},
                json={"username": principal.username, "password": "invented-payer-password-2026"},
            ).status_code
            == 200
        )
        suffix = hashlib.sha256(app[1].name.encode()).hexdigest()[:12]
        headers = {
            "origin": "http://127.0.0.1:8766",
            "x-csrf-token": client.cookies["prior_auth_csrf_" + suffix],
        }
        url = "/api/cases/" + case
        before = client.get(url).json()
        assert (
            next(c for c in before["evidence_cards"] if c["criterion"] == "education")["state"]
            == "insufficient"
        )
        wait = client.post(
            url + "/request",
            headers=headers,
            json={
                "command_id": "demo-wait",
                "expected_version": 1,
                "criteria": ["education"],
                "deadline": (NOW + timedelta(hours=1)).isoformat(),
            },
        )
        assert wait.status_code == 200 and wait.json()["version"] == 2
        result = import_document(
            principal,
            IntakeStore(store.connect, clock=store.clock),
            tmp_path / "supplement-request.json",
            tmp_path / "supplement.txt",
            Profiler(),
        )
        assert result["resulting_version"] == 3
        assert worker.step()["sent"] == 1
        current = client.get(url).json()
        assert len(current["evidence_cards"]) == 7
        assert all(
            c["state"] == "met" and c["source_mapping"] == "mapped"
            for c in current["evidence_cards"]
        )
        education = next(c for c in current["evidence_cards"] if c["criterion"] == "education")
        assert education["document_citations"][0]["locations"][0]["document_id"] == "demo-education"
        assert (
            client.post(
                url + "/payer/submit", headers=headers, json=COMMAND.model_dump()
            ).status_code
            == 409
        )
        command = {"expected_version": 3, "confirm_synthetic_exchange": True}
        assert (
            client.post(url + "/payer/submit", headers=headers, json=command).json()["submission"][
                "state"
            ]
            == "received"
        )
        assert client.post(url + "/payer/inquire", headers=headers, json=command).json()["inquiry"][
            "review_codes"
        ] == ["A3"]
        assert not DemoWorker(store, scope, ScriptedGateway()).step()["claimed"]
