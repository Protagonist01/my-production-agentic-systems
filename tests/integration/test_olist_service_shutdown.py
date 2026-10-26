"""A real listening server drains an in-flight SQL effect and flushes private counters."""

import json
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import httpx
import uvicorn
from fastapi.testclient import TestClient
from olist_support.console_api import create_app
from olist_support.console_auth import AuthStore, provision
from olist_support.console_cases import CaseStore
from olist_support.service_telemetry import ServiceTelemetry
from test_olist_business import app as app
from test_olist_console import PASSWORD, create_case, decide, observed
from test_olist_console import console as console


def test_real_server_drains_commit_flushes_and_reconstructs_duplicate(console, tmp_path):
    store, case, _, reviewer = create_case(console)
    _, pending, _, pending_reviewer = create_case(console)
    approved = decide(store, case, reviewer)
    with console[0].connect(console[1].name) as admin:
        provision(admin, reviewer, PASSWORD)
    reached, release = threading.Event(), threading.Event()
    original = store.resume

    def paused(*args, **kwargs):
        def after(stage):
            if stage == "after_commit":
                reached.set()
                if not release.wait(10):
                    raise TimeoutError("owned shutdown probe exceeded bound")

        return original(*args, **kwargs, fault=after)

    store.resume = paused
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    origin = f"http://127.0.0.1:{port}"
    output = tmp_path / "server-shutdown.json"
    application = create_app(
        store,
        AuthStore(store.connect),
        origin=origin,
        trial_id=console[1].name,
        code_revision="invented-shutdown",
        environment_lock="a" * 64,
        run_limit_minor=10000,
        telemetry=ServiceTelemetry(
            code_revision="invented-shutdown", environment_lock="a" * 64, output=output
        ),
    )
    server = uvicorn.Server(
        uvicorn.Config(
            application,
            host="127.0.0.1",
            port=port,
            proxy_headers=False,
            access_log=False,
            log_level="critical",
            timeout_graceful_shutdown=5,
        )
    )
    thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 10
        while not server.started and thread.is_alive() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert server.started
        with httpx.Client(base_url=origin, timeout=15) as client:
            assert client.get("/health/ready").status_code == 200
            signed = client.post(
                "/api/login",
                json={
                    "username": reviewer.username,
                    "password": PASSWORD,
                },
                headers={"origin": origin},
            )
            assert signed.status_code == 200
            headers = {
                "origin": origin,
                "x-csrf-token": client.cookies[signed.json()["csrf_cookie"]],
            }
            with ThreadPoolExecutor(max_workers=1) as pool:
                response = pool.submit(
                    client.post,
                    f"/api/cases/{case.case_id}/resume",
                    json={"action_digest": approved.action_digest},
                    headers=headers,
                )
                assert reached.wait(5)
                server.should_exit = True
                # Normal Uvicorn shutdown waits for this admitted request, not just SQL commit.
                time.sleep(0.2)
                assert thread.is_alive() and output.read_bytes() == b""
                assert observed(console, case) == ((5000, 1), (1, 5000), 1)
                release.set()
                completed = response.result(timeout=10)
                assert completed.status_code == 200
                original_receipt = completed.json()["result"]["receipt"]
            thread.join(timeout=10)
            assert not thread.is_alive()
            raw = output.read_text()
            metrics = json.loads(raw)
            assert metrics["shutdown_finished"] and metrics["started"] == metrics["completed"] == 3
            assert metrics["interrupted"] == metrics["active"] == 0
            assert metrics["status_classes"]["2xx"] == 3
            for canary in (
                PASSWORD,
                case.case_id,
                case.order_id,
                reviewer.username,
                *client.cookies.values(),
            ):
                assert canary not in raw
        rebuilt = CaseStore(store.connect)
        recovered = rebuilt.resume(
            reviewer, case.case_id, approved.action_digest, run_limit_minor=10000
        )
        assert recovered.result.receipt.model_dump(mode="json") == original_receipt
        assert rebuilt.detail(pending_reviewer, pending.case_id)[0].status == "review_required"
        assert observed(console, case) == ((5000, 1), (1, 5000), 1)
        # A second application lifespan can read the same durable result.
        restarted = create_app(
            rebuilt,
            AuthStore(store.connect),
            origin=origin,
            trial_id=console[1].name,
            code_revision="invented-shutdown",
            environment_lock="a" * 64,
            run_limit_minor=10000,
        )
        with TestClient(restarted, base_url=origin) as reader:
            reader.cookies.update(dict(client.cookies))
            assert reader.get(f"/api/cases/{case.case_id}").json()["case"]["status"] == "committed"
    finally:
        release.set()
        server.should_exit = True
        thread.join(timeout=12)
        listener.close()
