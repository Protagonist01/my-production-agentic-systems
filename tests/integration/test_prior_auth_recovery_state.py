"""Actual clean-target recovery preserves cases, unknown effects and private authority."""

import json
import secrets
from datetime import timedelta

import pytest
from agent_harness.postgres import Trial, create_trial, drop_trial
from prior_auth.contracts import digest
from prior_auth.review_auth import AuthStore, provision
from prior_auth.review_store import ReviewStore
from test_prior_auth_demo_runtime_state import seed
from test_prior_auth_review import NOW, actor
from test_prior_auth_review_state import app as app

from prior_auth_demo_fixtures import ScriptedGateway, note
from prior_auth_demo_runtime import DemoWorker
from prior_auth_evidence_cards import EvidenceReader
from prior_auth_pas import PasClient
from prior_auth_payer_desk import PayerCommand, PayerDesk
from prior_auth_recovery import capture, read, restore, save


def source(app, tmp_path, *, uncertain=False):
    class Death:
        def generate(self, *args):
            raise SystemExit()

    case, _, scope, _, worker, _, imported = seed(app, gateway=Death() if uncertain else None)
    if uncertain:
        with pytest.raises(SystemExit):
            worker.step()
    else:
        worker.step()
    calls = []

    def lost(method, path, value):
        calls.append(path)
        raise TimeoutError()

    journal = tmp_path / "source.sqlite"
    desk = PayerDesk(app[2], PasClient(journal, lost), (imported.case,))
    desk.exchange(
        actor(case),
        case,
        PayerCommand(expected_version=1, confirm_synthetic_exchange=True),
        inquire=False,
    )
    user = actor(case).model_copy(update={"username": "restore-" + case[-16:]})
    with app[0].connect(app[1].name) as admin:
        provision(admin, user, "invented-recovery-password-2026")
    auth = AuthStore(app[2].connect, clock=app[2].clock)
    token, csrf, _ = auth.login(user.username, "invented-recovery-password-2026")
    # The source bundle is private configuration, kept separate from live SQL.
    bundle = tmp_path / "source-bundle"
    bundle.mkdir()
    from test_prior_auth_review import policy

    files = {
        "scope.json": scope.canonical_json(),
        "request.json": imported.canonical_json(),
        "policy.json": policy().canonical_json(),
        "source.txt": note(case, policy()).text,
    }
    for name, text in files.items():
        (bundle / name).write_bytes(text.encode("utf-8"))
    manifest = {name: digest(text) for name, text in files.items()}
    (bundle / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    snapshot = capture(
        app[0],
        app[1],
        journal,
        code_revision="invented-recovery-test",
        environment_sha256="a" * 64,
        quiescent=True,
        bundle=bundle,
    )
    return case, scope, imported.case, snapshot, user, token, csrf, calls


@pytest.mark.parametrize("uncertain", [False, True])
def test_actual_restore_retains_sources_and_unknown_attempts_but_revokes_sessions(
    app, tmp_path, uncertain
):
    case, scope, binding, snapshot, user, token, csrf, calls = source(
        app, tmp_path, uncertain=uncertain
    )
    archive = tmp_path / "snapshot.json"
    pin = save(archive, snapshot)
    snapshot = read(archive, pin)
    server, original = app[:2]
    target = Trial(
        original.workspace_key, "pa-restore-" + secrets.token_hex(8), secrets.token_hex(32)
    )
    create_trial(server, target)
    try:
        journal = tmp_path / "restored.sqlite"
        report = restore(
            server,
            target,
            snapshot,
            expected_sha256=pin,
            journal=journal,
            bundle_directory=tmp_path / "restored-bundle",
        )
        assert report["restored"] and report["sessions_revoked"] >= 1

        def connect():
            return server.connect_trial(target)

        store = ReviewStore(connect, clock=lambda: NOW + timedelta(minutes=6))
        auth = AuthStore(connect, clock=lambda: NOW + timedelta(minutes=6))
        with pytest.raises(PermissionError):
            auth.authenticate(token, csrf)
        new_token, _, restored_user = auth.login(user.username, "invented-recovery-password-2026")
        assert restored_user == user
        auth.logout(new_token)
        gateway = ScriptedGateway()
        result = DemoWorker(store, scope, gateway).step()
        assert result["sent"] == 0 and not gateway.requests
        if uncertain:
            assert (
                result["blocked"] == 1
                and store.snapshot(user, case)["status"] == "qualified_review"
            )
        else:
            assert result["claimed"] is False
            cards = EvidenceReader(store).cards(user, case, expected_version=1)
            assert len(cards) == 7 and all(c.source_mapping == "mapped" for c in cards)
        desk = PayerDesk(
            store,
            PasClient(journal, lambda *args: (_ for _ in ()).throw(AssertionError("resubmitted"))),
            (binding,),
        )
        assert (
            desk.exchange(
                user,
                case,
                PayerCommand(expected_version=1, confirm_synthetic_exchange=True),
                inquire=False,
            )["submission"]["state"]
            == "unknown"
        )
        assert calls == ["Claim/$submit"]
        assert (tmp_path / "restored-bundle/source.txt").read_bytes() == (
            tmp_path / "source-bundle/source.txt"
        ).read_bytes()
        # Source sessions still exist: restore did not mutate the source.
        assert AuthStore(app[2].connect, clock=app[2].clock).authenticate(token, csrf) == user
    finally:
        drop_trial(server, target)


def test_existing_target_or_tampered_archive_cannot_be_restored(app, tmp_path):
    _, _, _, snapshot, _, _, _, _ = source(app, tmp_path)
    pin = digest(snapshot.canonical_json())
    with pytest.raises(ValueError):
        restore(
            app[0],
            app[1],
            snapshot,
            expected_sha256=pin,
            journal=tmp_path / "new.sqlite",
            bundle_directory=tmp_path / "new-bundle",
        )
    path = tmp_path / "archive.json"
    save(path, snapshot)
    with pytest.raises(FileExistsError):
        save(path, snapshot)
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError):
        read(path, pin)
