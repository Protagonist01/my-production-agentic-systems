"""Presentation-only composition preserves existing protected API/session handlers."""

import pytest
from fastapi.testclient import TestClient
from test_prior_auth_review import actor

from prior_auth_demo_web import demo_app


class Store:
    connect = None
    clock = None


class Auth:
    def authenticate(self, token, csrf=None):
        if token != "invented-valid-token":
            raise PermissionError("denied")
        return actor("demo-case")


def test_public_presentation_is_explicit_demo_and_private_api_stays_authenticated():
    app = demo_app(Store(), Auth(), origin="http://127.0.0.1:8766", trial_id="invented-demo")
    with TestClient(app, base_url="http://127.0.0.1:8766") as client:
        html = client.get("/")
        assert html.status_code == 200 and "Synthetic portfolio demo" in html.text
        assert "No insurer approval" in html.text and html.headers["cache-control"] == "no-store"
        js = client.get("/assets/console.js")
        assert js.status_code == 200 and "renderOriginalEvidenceDesk" in js.text
        assert "Scripted workflow demonstration" in js.text
        assert "innerHTML" not in js.text
        assert client.get("/api/cases/demo-case").status_code == 403
        assert client.post("/api/cases/demo-case/review", json={}).status_code == 403
        assert client.get("/assets/anything-else").status_code == 404


def test_nonloopback_origin_is_not_enabled_by_demo_composition():
    with pytest.raises(ValueError):
        demo_app(Store(), Auth(), origin="https://public.invalid", trial_id="demo")
