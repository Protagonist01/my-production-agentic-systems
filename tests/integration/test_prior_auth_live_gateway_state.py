"""Actual SQL plus spawned invented SDK; no credential or provider export."""

import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from agent_harness.gateway import ProviderGateway
from agent_harness.isolated_transport import IsolatedTransport
from prior_auth.candidate import QuoteClaim
from test_prior_auth_demo_runtime_state import seed
from test_prior_auth_live_gateway import historical_ledger
from test_prior_auth_review import actor, policy
from test_prior_auth_review_state import app as app

from prior_auth_demo_fixtures import note, requests
from prior_auth_demo_runtime import DemoWorker, provision_scope
from prior_auth_evidence_cards import EvidenceReader
from prior_auth_live_console import context
from prior_auth_live_gateway import Grant, Ledger, LiveGateway, Slot, initialize, scope_binding


class InventedWorker:
    def generate(self, request, *, timeout_seconds):
        import httpx
        from agent_harness.gemini import GeminiTransport

        def fake_http(wire):
            assert wire.url.host == "generativelanguage.googleapis.com"
            assert wire.url.path.endswith("/models/gemini-3.5-flash-lite:generateContent")
            payload = json.loads(json.loads(wire.content)["contents"][0]["parts"][0]["text"])
            claim = QuoteClaim(
                criterion_id=payload["criterion"]["criterion_id"],
                state="met",
                quotes=(payload["full_note"],),
                rationale="Invented SDK wiring proof only",
            )
            return httpx.Response(
                200,
                json={
                    "candidates": [
                        {
                            "content": {
                                "role": "model",
                                "parts": [{"text": claim.canonical_json()}],
                            },
                            "finishReason": "STOP",
                        }
                    ],
                    "usageMetadata": {
                        "promptTokenCount": 10,
                        "candidatesTokenCount": 2,
                        "thoughtsTokenCount": 0,
                        "totalTokenCount": 12,
                    },
                    "modelVersion": request.model,
                    "responseId": "invented-local-sdk",
                },
            )

        return GeminiTransport(
            "invented-not-a-credential",
            free_tier_confirmed=True,
            http_timeout_seconds=90,
            http_transport=httpx.MockTransport(fake_http),
        ).generate(request, timeout_seconds=min(90, timeout_seconds))


def live(app, tmp_path, transport=None):
    case, value, scope, _, _, _, _ = seed(app)
    now = datetime.now(UTC)
    app[3][0] = now
    scope = scope.model_copy(
        update={
            "scope_id": "live-" + uuid.uuid4().hex,
            "mode": "fresh_candidate",
            "provider_scope_sha256": "f" * 64,
            "starts_at": now - timedelta(seconds=1),
            "expires_at": now + timedelta(hours=1),
        }
    )
    planned = requests((value,), policy())
    canary_requests = requests((note(case, policy()),), policy())[:2]
    scope = scope.model_copy(
        update={
            "request_sha256s": tuple(
                dict.fromkeys(r.fingerprint() for r in (*canary_requests, *planned))
            )
        }
    )
    path, original = historical_ledger(tmp_path)
    grant = Grant(
        approval_ref="invented-SQL-test-only",
        free_project_confirmed=True,
        project_association_sha256="b" * 64,
        historical_sha256=original,
        execution_sha256="c" * 64,
        runtime_scope_sha256=scope_binding(scope),
        starts_at=scope.starts_at,
        expires_at=scope.expires_at,
        slots=tuple(
            Slot(phase=phase, case_id=case, request_sha256=request.fingerprint())
            for phase, request in [("canary", r) for r in canary_requests]
            + [("domain", r) for r in planned]
        ),
    )
    ledger = initialize(path, grant)
    scope = scope.model_copy(update={"provider_scope_sha256": ledger.pin})
    with app[0].connect(app[1].name) as admin:
        provision_scope(admin, scope)
    gateway = LiveGateway(
        app[2],
        scope,
        ledger,
        transport or ProviderGateway(IsolatedTransport(InventedWorker())),
        execution_probe=lambda: "c" * 64,
        project_association_sha256="b" * 64,
    )
    return case, scope, ledger, gateway, canary_requests


def canaries(case, scope, gateway, planned):
    for i, request in enumerate(planned[:2]):
        response = gateway.canary(
            context(scope, case, "canary-" + str(i + 1)), request, note(case, policy()), policy()
        )
        assert response.failure is None


def test_spawned_sdk_canaries_then_sql_worker_and_restart_send_nothing(app, tmp_path):
    case, scope, ledger, gateway, planned = live(app, tmp_path)
    canaries(case, scope, gateway, planned)
    result = DemoWorker(app[2], scope, gateway, provider_validator=gateway.validate).step()
    assert result["published"] and result["sent"] == 7
    assert ledger.summary()["total_consumed"] == 624
    assert not ledger.summary()["unsettled"]
    cards = EvidenceReader(app[2]).cards(actor(case), case, expected_version=1)
    assert len(cards) == 7 and all(c.state == "met" and c.source_mapping == "mapped" for c in cards)
    assert DemoWorker(app[2], scope, gateway, provider_validator=gateway.validate).step() == {
        "claimed": False,
        "published": False,
        "sent": 0,
        "replayed": 0,
    }
    assert Ledger(ledger.path, ledger.pin).summary()["total_consumed"] == 624


def test_no_domain_export_without_committed_sql_reservation(app, tmp_path):
    case, scope, ledger, gateway, planned = live(app, tmp_path)
    canaries(case, scope, gateway, planned)
    with pytest.raises(PermissionError):
        gateway.generate(context(scope, case, "case-version-1"), planned[0])
    assert ledger.summary()["new_consumed"] == 2


def test_process_death_keeps_both_reservations_unknown_without_resend(app, tmp_path):
    case, scope, ledger, gateway, planned = live(app, tmp_path)
    canaries(case, scope, gateway, planned)

    class Death:
        calls = 0

        def generate(self, *args, **kwargs):
            self.calls += 1
            raise SystemExit()

    dead = Death()
    gateway.transport = dead
    with pytest.raises(SystemExit):
        DemoWorker(app[2], scope, gateway, provider_validator=gateway.validate).step()
    assert ledger.summary()["unsettled"] == 1
    app[3][0] += timedelta(minutes=6)
    result = DemoWorker(app[2], scope, gateway, provider_validator=gateway.validate).step()
    assert result["sent"] == 0 and result["blocked"] == 1 and dead.calls == 1
    assert ledger.summary()["new_consumed"] == 3


def test_bounded_live_attempts_renew_only_active_job_lease(app, tmp_path):
    case, scope, ledger, gateway, planned = live(app, tmp_path)
    canaries(case, scope, gateway, planned)

    class Slow:
        def generate(self, context, request, *, timeout_seconds):
            app[3][0] += timedelta(minutes=2)
            return InventedWorker().generate(request, timeout_seconds=timeout_seconds)

    gateway.transport = Slow()
    result = DemoWorker(app[2], scope, gateway, provider_validator=gateway.validate).step()
    assert result["published"] and result["sent"] == 7
    assert ledger.summary()["new_consumed"] == 9
