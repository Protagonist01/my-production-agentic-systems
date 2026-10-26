"""Real ASGI lifecycle, private output and aggregate-only telemetry boundaries."""

import json

import pytest
from fastapi.testclient import TestClient
from olist_support.console_api import create_app
from olist_support.service_telemetry import ServiceTelemetry


def application(telemetry):
    return create_app(
        None,
        None,
        origin="http://127.0.0.1:8765",
        trial_id="private-trial-canary",
        code_revision="invented",
        environment_lock="a" * 64,
        run_limit_minor=10000,
        telemetry=telemetry,
    )


def test_shutdown_flushes_complete_status_counts_without_request_content(tmp_path):
    path = tmp_path / "private-telemetry.json"
    telemetry = ServiceTelemetry(code_revision="invented", environment_lock="a" * 64, output=path)
    with TestClient(application(telemetry), base_url="http://127.0.0.1:8765") as client:
        assert path.read_bytes() == b""
        assert client.get("/health/live").status_code == 200
        assert client.get("/private-path-canary?secret=private-query-canary").status_code == 404
        assert client.post("/api/login", content=b"private-body-canary" * 2000).status_code == 413
        assert telemetry.snapshot()["active"] == 0
    raw = path.read_text()
    result = json.loads(raw)
    assert result["shutdown_finished"] and result["active"] == result["interrupted"] == 0
    assert result["started"] == result["completed"] == 3
    assert result["status_classes"] == {"1xx": 0, "2xx": 1, "3xx": 0, "4xx": 2, "5xx": 0}
    # Python3.12/Windows can observe the same coarse monotonic tick for fast requests.
    assert result["total_request_ns"] >= 0 and result["uptime_ns"] >= 0
    assert "canary" not in raw and "invented" not in raw
    telemetry.close()
    assert path.read_text() == raw
    with pytest.raises(ValueError, match="closed"):
        telemetry.begin()
    with pytest.raises(ValueError, match="single-use"):
        telemetry.open()


def test_existing_output_or_git_checkout_refuses_startup_without_overwrite(tmp_path):
    path = tmp_path / "existing"
    path.write_text("private-original-canary")
    for output in (path, tmp_path / "checkout" / "summary.json"):
        if output != path:
            output.parent.mkdir()
            (output.parent / ".git").mkdir()
        app = application(ServiceTelemetry(code_revision="x", environment_lock="x", output=output))
        with pytest.raises(RuntimeError, match="choose a new private output"):
            with TestClient(app):
                pass
    assert path.read_text() == "private-original-canary"


@pytest.mark.parametrize("elapsed", [0, 50])
def test_coarse_and_advancing_clocks_preserve_actual_duration(elapsed, monkeypatch):
    current = 100
    monkeypatch.setattr("olist_support.service_telemetry.time.monotonic_ns", lambda: current)
    telemetry = ServiceTelemetry(code_revision="invented", environment_lock="a" * 64)
    telemetry.open()
    start = telemetry.begin()
    current += elapsed
    telemetry.end(start, 200, True)
    result = telemetry.snapshot()
    assert result["total_request_ns"] == result["uptime_ns"] == elapsed
    assert result["active"] == result["interrupted"] == 0
    assert result["started"] == result["completed"] == 1
    telemetry.close()


def test_failed_send_and_private_exception_count_interrupted_without_text(tmp_path):
    import asyncio

    from olist_support.service_telemetry import CountHTTP

    path = tmp_path / "summary.json"
    telemetry = ServiceTelemetry(code_revision="x", environment_lock="x", output=path)
    telemetry.open()

    async def failing(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        raise OSError("private-exception-canary")

    async def receive():
        return {"type": "http.request", "body": b""}

    async def send(message):
        pass

    with pytest.raises(OSError):
        asyncio.run(CountHTTP(failing, telemetry)({"type": "http"}, receive, send))
    telemetry.close()
    result = json.loads(path.read_bytes())
    assert result["interrupted"] == 1 and result["completed"] == result["active"] == 0
    assert "canary" not in path.read_text()


def test_flush_failure_is_explicit_safe_and_does_not_remove_output(tmp_path, monkeypatch):
    path = tmp_path / "summary.json"
    app = application(ServiceTelemetry(code_revision="x", environment_lock="x", output=path))

    def fail(descriptor):
        raise OSError("private-storage-canary")

    monkeypatch.setattr("olist_support.service_telemetry.os.fsync", fail)
    with pytest.raises(RuntimeError, match="telemetry flush failed") as error:
        with TestClient(app):
            pass
    assert "canary" not in str(error.value) and path.exists()
    assert path.read_bytes() == b""
