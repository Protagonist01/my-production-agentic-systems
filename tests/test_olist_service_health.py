"""Health error projection never echoes DB errors, keys or source records."""

import psycopg
import pytest
from fastapi.testclient import TestClient
from olist_support.console_api import create_app
from olist_support.service_health import ServiceNotReady, readiness, require_ready


def unavailable():
    raise psycopg.OperationalError("PRIVATE credential canary")


def test_liveness_does_not_need_database_and_unconfigured_readiness_is_503():
    app = create_app(
        None,
        None,
        origin="http://127.0.0.1:8765",
        trial_id="invented",
        code_revision="invented",
        environment_lock="a" * 64,
        run_limit_minor=10000,
    )
    client = TestClient(app, base_url="http://127.0.0.1:8765")
    assert client.get("/health/live").json() == {"live": True, "business_unit": "SIM"}
    assert client.get("/health/ready").status_code == 503
    assert "no-store" in client.get("/health/ready").headers["cache-control"]


def test_database_failure_is_safe_and_startup_action_is_specific():
    result = readiness(unavailable)
    assert result["reason"] == "database_unavailable" and "PRIVATE" not in str(result)
    with pytest.raises(ServiceNotReady, match="check_private_database_configuration"):
        require_ready(unavailable)


@pytest.mark.parametrize(
    "error,expected",
    [
        (psycopg.errors.UndefinedTable, "schema_missing"),
        (psycopg.errors.InsufficientPrivilege, "schema_access_denied"),
    ],
)
def test_readiness_classifies_schema_failures_without_exposing_error_payload(error, expected):
    def broken():
        raise error("PRIVATE schema payload")

    result = readiness(broken)
    assert result["reason"] == expected and "PRIVATE" not in str(result)
