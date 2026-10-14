"""H1 boundaries; actual SDK on mock transport, no provider key or live request."""

import asyncio
import socket
from types import SimpleNamespace

import pytest
from agent_harness.integration_smoke import (
    LookupArguments,
    SmokeOutput,
    live_check,
    local_environment,
    offline_check,
    response_evidence,
    tool,
)
from agent_harness.trace_probe import trace_check, validate_readback
from google.genai import types
from pydantic import ValidationError


def test_sdk_and_framework_probe_cannot_use_network(monkeypatch):
    def refuse(*args, **kwargs):
        pytest.fail("Offline H1 probe attempted network access")

    # Windows builds asyncio's wake-up socketpair over loopback. Create that owned
    # IPC pair before blocking all probe connections, then close it after the guard.
    with asyncio.Runner() as runner:
        runner.get_loop()
        with monkeypatch.context() as guard:
            guard.setattr(socket.socket, "connect", refuse)
            result = offline_check()
    assert result["sdk_requests"] == 2
    assert result["structured"] == {"case_id": "invented-h1", "answer": 42}
    assert result["frameworks"]["pydantic_ai"] == result["structured"]
    assert result["provider_access_verified"] is False


@pytest.mark.parametrize(
    "payload",
    [
        {"case_id": "invented-h1", "answer": 43},
        {"case_id": "invented-h1", "answer": "42"},
        {"case_id": "invented-h1", "answer": 42, "secret": "unexpected"},
    ],
)
def test_structured_wrong_value_coercion_and_extra_fields_fail(payload):
    with pytest.raises(ValidationError):
        SmokeOutput.model_validate(payload)


@pytest.mark.parametrize(
    "calls",
    [
        [],
        [types.FunctionCall(name="refund", args={"order_id": "invented-order-001"})],
        [types.FunctionCall(name="lookup_order", args={"order_id": "other-order"})],
        [types.FunctionCall(name="lookup_order", args={"order_id": "invented-order-001"})] * 2,
    ],
)
def test_missing_unauthorized_wrong_order_or_multiple_tool_calls_fail(calls):
    client = SimpleNamespace(
        models=SimpleNamespace(
            generate_content=lambda **kwargs: SimpleNamespace(function_calls=calls)
        )
    )
    with pytest.raises(ValueError):
        tool(client)


def test_unknown_usage_is_not_claimed_as_known():
    with pytest.raises(ValueError):
        response_evidence(types.GenerateContentResponse())


def test_missing_key_or_free_confirmation_refuses_before_client(tmp_path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_FREE_TIER_CONFIRMED", raising=False)
    (tmp_path / ".env.local").write_text(
        "GEMINI_API_KEY=invented-key\nGEMINI_FREE_TIER_CONFIRMED=false\n"
    )
    with pytest.raises(ValueError, match="Free project"):
        live_check(tmp_path)
    assert LookupArguments(order_id="invented-order-001").order_id == "invented-order-001"


def test_local_configuration_text_is_data_not_code(tmp_path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_FREE_TIER_CONFIRMED", raising=False)
    (tmp_path / ".env.local").write_text("GEMINI_API_KEY=$(invented-command)\nUNRELATED=ignored\n")
    assert local_environment(tmp_path) == {
        "GEMINI_API_KEY": "$(invented-command)",
        "GEMINI_FREE_TIER_CONFIRMED": "",
    }


def trace_rows():
    return {
        "status": 200,
        "body": {
            "data": [
                {
                    "id": "root",
                    "name": "h1-provider-smoke",
                    "traceId": "invented-trace",
                    "type": "SPAN",
                },
                *[
                    {
                        "id": name,
                        "name": name,
                        "traceId": "invented-trace",
                        "parentObservationId": "root",
                        "type": "GENERATION",
                        "model": "gemini-3.5-flash-lite",
                        "usageDetails": {"input": 12, "output": 8},
                        "input": "invented input",
                        "output": "invented output",
                    }
                    for name in ("gemini-structured", "gemini-tool-proposal")
                ],
            ]
        },
    }


def test_complete_correlated_trace_readback_passes():
    assert validate_readback(trace_rows(), "invented-trace")["readback_verified"] is True


@pytest.mark.parametrize(
    "change", ["missing", "wrong_parent", "unknown_usage", "wrong_model", "failed_response"]
)
def test_incomplete_or_uncorrelated_trace_readback_fails(change):
    payload = trace_rows()
    rows = payload["body"]["data"]
    if change == "missing":
        rows.pop()
    elif change == "wrong_parent":
        rows[1]["parentObservationId"] = "other-root"
    elif change == "unknown_usage":
        rows[1]["usageDetails"] = {}
    elif change == "wrong_model":
        rows[1]["model"] = "other-model"
    else:
        payload["status"] = 503
    with pytest.raises(ValueError):
        validate_readback(payload, "invented-trace")


@pytest.mark.parametrize(
    "host", ["https://cloud.langfuse.com", "http://localhost:3000/?key=bad", ""]
)
def test_trace_probe_refuses_missing_or_nonlocal_configuration(tmp_path, monkeypatch, host):
    for name in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_BASE_URL"):
        monkeypatch.delenv(name, raising=False)
    (tmp_path / ".env.local").write_text(
        "LANGFUSE_PUBLIC_KEY=invented\nLANGFUSE_SECRET_KEY=invented\nLANGFUSE_BASE_URL=" + host
    )
    with pytest.raises(ValueError, match="dedicated local"):
        trace_check(tmp_path)
