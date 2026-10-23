"""Invented source-independent witnesses for P4/P5 scope, import and model boundaries."""

import json
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from prior_auth.assessment import CRITERIA
from prior_auth.contracts import (
    CandidateAssessment,
    Claim,
    Criterion,
    NoteInput,
    Policy,
    Span,
    digest,
)
from prior_auth.review_api import create_app
from prior_auth.review_cli import reviewed_text
from prior_auth.review_contracts import Principal, ReviewNote, WaitRequest
from pydantic import ValidationError

NOW = datetime(2026, 10, 23, 12, tzinfo=UTC)


def policy():
    return Policy(
        policy_id="cms-ncd-240-4-v3",
        source_url="https://example.invalid/invented",
        source_sha256="a" * 64,
        text_sha256=digest("Invented"),
        effective_from=date(2008, 3, 13),
        review_status="ai_provisional",
        review_ref="invented-test-only",
        criteria=tuple(
            Criterion(
                criterion_id=k,
                description="Invented requirement",
                source=Span(start=0, end=8, quote="Invented"),
            )
            for k in CRITERIA
        ),
    )


def note(case="case", text="Initial illustrative note. No documentation supplied."):
    return NoteInput(
        case_id=case,
        tenant_id="demo",
        text=text,
        note_sha256=digest(text),
        service_date=date(2026, 10, 23),
        policy_id=policy().policy_id,
        policy_sha256=digest(policy().canonical_json()),
        use="initial",
        provenance="invented",
    )


def actor(case="case", role="reviewer"):
    return Principal(
        username=role + "-test", tenant_id="demo", actor_id=role, role=role, case_ids=(case,)
    )


def insufficient(value, selected=CRITERIA):
    return CandidateAssessment(
        case_id=value.case_id,
        note_sha256=value.note_sha256,
        policy_sha256=value.policy_sha256,
        claims=tuple(
            Claim(criterion_id=k, state="insufficient", evidence=(), rationale="No evidence")
            for k in selected
        ),
    )


def test_scope_and_closed_commands_do_not_grant_authorization():
    actor().require("case", write=True)
    actor(role="viewer").require("case")
    with pytest.raises(PermissionError):
        actor(role="viewer").require("case", write=True)
    with pytest.raises(PermissionError):
        actor().require("other")
    with pytest.raises(ValidationError):
        ReviewNote(command_id="cmd", expected_version=1, outcome="approve", reason="expert_review")
    with pytest.raises(ValidationError):
        WaitRequest(
            command_id="cmd",
            expected_version=1,
            criteria=("education",),
            deadline=NOW,
            tenant_id="other",
        )
    with pytest.raises(ValidationError):
        WaitRequest(
            command_id="cmd", expected_version=1, criteria=("education", "education"), deadline=NOW
        )


def test_trusted_import_masks_identifier_canary_before_note_storage(tmp_path):
    raw = tmp_path / "raw.txt"
    mapping = tmp_path / "reviewed.json"
    text = "Name: PrivateCanaryIdentifier\nCPAP education completed prior to use."
    raw.write_text(text, encoding="utf-8")
    start = text.index("Private")
    mapping.write_text(
        json.dumps(
            [
                {
                    "kind": "name",
                    "source": {
                        "start": start,
                        "end": text.index("\n"),
                        "quote": "PrivateCanaryIdentifier",
                    },
                }
            ]
        ),
        encoding="utf-8",
    )
    clean = reviewed_text(raw, mapping)
    assert "PrivateCanaryIdentifier" not in clean
    assert clean.index("CPAP") == text.index("CPAP") and len(clean) == len(text)


class Auth:
    def login(self, username, password):
        if password != "invented-password":
            raise PermissionError()
        return "valid-session-token-for-tests", "csrf-token-for-tests", actor()

    def authenticate(self, token, csrf=None):
        if token != "valid-session-token-for-tests" or csrf not in (None, "csrf-token-for-tests"):
            raise PermissionError()
        return actor()

    def logout(self, token):
        pass


class Store:
    def snapshot(self, user, case):
        user.require(case)
        return {"case_id": case, "version": 1, "status": "request_information", "deadline": None}

    def request(self, user, case, payload):
        user.require(case, write=True)
        return 2


def test_loopback_api_scopes_origin_csrf_privacy_and_no_raw_or_authorization_routes():
    app = create_app(Store(), Auth(), origin="http://127.0.0.1:8881", trial_id="test")
    with TestClient(app, base_url="http://127.0.0.1:8881") as client:
        assert client.get("/api/cases").status_code == 403
        assert (
            client.post(
                "/api/login", json={"username": "reviewer-test", "password": "invented-password"}
            ).status_code
            == 403
        )
        login = client.post(
            "/api/login",
            headers={"Origin": "http://127.0.0.1:8881"},
            json={"username": "reviewer-test", "password": "invented-password"},
        )
        assert login.status_code == 200
        assert client.get("/api/cases").json()["cases"][0]["case_id"] == "case"
        assert client.get("/api/cases/other").status_code == 403
        assert client.get("/api/cases", headers={"Host": "127.0.0.1:9999"}).status_code == 403
        body = {
            "command_id": "wait",
            "expected_version": 1,
            "criteria": ["education"],
            "deadline": (NOW + timedelta(days=1)).isoformat(),
        }
        assert client.post("/api/cases/case/request", json=body).status_code == 403
        headers = {"Origin": "http://127.0.0.1:8881", "X-CSRF-Token": "csrf-token-for-tests"}
        assert client.post("/api/cases/case/request", json=body, headers=headers).status_code == 200
        for path in ("approve", "deny", "document", "policy"):
            assert (
                client.post("/api/cases/case/" + path, json={}, headers=headers).status_code == 404
            )
        invalid = client.post(
            "/api/cases/case/request",
            json={**body, "private_identifier": "CANARY"},
            headers=headers,
        )
        assert invalid.status_code == 422 and "CANARY" not in invalid.text
        response = client.get("/")
        assert response.headers["cache-control"] == "no-store"
        assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
        assert client.get("/assets/console.js").status_code == 200


def test_subset_extraction_can_only_assess_known_unique_criteria():
    from agent_harness.offline_example import example_context
    from prior_auth.candidate import extract

    n = note()
    context = example_context("test", "a" * 64).model_copy(
        update={"case_id": n.case_id, "tenant_id": n.tenant_id}
    )

    class Never:
        def generate(self, *args):
            raise AssertionError("empty retrieval must not dispatch")

    candidate = extract(Never(), context, n, policy(), criteria_subset=("education",))
    assert len(candidate.claims) == 1 and candidate.claims[0].criterion_id == "education"
    with pytest.raises(ValueError):
        extract(Never(), context, n, policy(), criteria_subset=("education", "education"))
