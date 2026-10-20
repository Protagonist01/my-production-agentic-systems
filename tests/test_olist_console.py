"""Invented password/API/asset boundary checks; SQL/durability live in required DB suite."""

import pytest
from fastapi.testclient import TestClient
from olist_support.console_api import create_app
from olist_support.console_auth import password_hash, password_matches


def test_salted_passwords_are_verified_without_plaintext_or_coercion():
    secret = "invented password with enough length"
    first, second = password_hash(secret), password_hash(secret)
    assert first != second and secret not in first and password_matches(secret, first)
    assert not password_matches("invented wrong password", first)
    assert not password_matches(secret, "malformed")
    for short in ("", "too short", "x" * 129):
        with pytest.raises(ValueError):
            password_hash(short)


@pytest.mark.parametrize(
    "origin",
    [
        "http://0.0.0.0:8000",
        "https://example.com",
        "http://user@localhost:8000",
        "http://127.0.0.1:8000/path",
        "http://127.0.0.1:8000?x=y",
    ],
)
def test_only_explicit_local_origin_is_supported(origin):
    with pytest.raises(ValueError):
        create_app(
            None,
            None,
            origin=origin,
            trial_id="invented",
            code_revision="invented",
            environment_lock="invented",
            run_limit_minor=10000,
        )


def test_validation_and_body_errors_do_not_echo_passwords_or_untrusted_html():
    app = create_app(
        None,
        None,
        origin="http://127.0.0.1:8765",
        trial_id="invented",
        code_revision="invented",
        environment_lock="invented",
        run_limit_minor=10000,
    )
    client = TestClient(app, base_url="http://127.0.0.1:8765")
    canary = "private-password-canary-" * 10
    response = client.post(
        "/api/login",
        json={"username": "invented", "password": canary},
        headers={"origin": "http://127.0.0.1:8765"},
    )
    assert response.status_code == 422 and canary not in response.text
    assert client.post("/api/login", content=b"x" * 16385).status_code == 413
    page = client.get("/")
    assert (
        page.status_code == 200
        and "Support desk" in page.text
        and "no-store" in page.headers["cache-control"]
    )
    assert client.get("/assets/console.css").status_code == 200
    assert client.get("/assets/console.js").status_code == 200
    assert client.get("/assets/unknown").status_code == 404
