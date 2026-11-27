import json
from datetime import UTC, datetime, timedelta

import httpx
import psycopg
import pytest
from pydantic import SecretStr
from test_olist_workflow import context

import olist_nemotron
from olist_nemotron import DEMO_REQUESTS, MODEL, HostedGateway, request


def unavailable_connection():
    raise psycopg.OperationalError("invented database outage")


def test_unapproved_text_and_missing_ledger_never_dispatch(monkeypatch):
    gateway = HostedGateway(unavailable_connection, SecretStr("invented"))
    wire = request(DEMO_REQUESTS[0])
    with pytest.raises(ValueError, match="built-in"):
        request("a visitor's private message")
    now = datetime.now(UTC)
    run = context().model_copy(update={"clock": now, "deadline": now + timedelta(seconds=30)})
    monkeypatch.setattr(gateway, "_complete", lambda *args: pytest.fail("provider dispatch"))
    assert gateway.generate(run, wire).failure.code == "unavailable"
    altered = wire.model_copy(update={"model": "a-different-route"})
    assert gateway.generate(run, altered).failure.code == "permission_denied"


@pytest.mark.parametrize("cost,accepted", [(0, True), (0.01, False), (None, False)])
def test_route_and_cost_are_enforced(monkeypatch, cost, accepted):
    real_client = httpx.Client

    def exchange(req):
        assert str(req.url) == "https://openrouter.ai/api/v1/chat/completions"
        body = json.loads(req.content)
        assert body["model"] == MODEL
        assert body["messages"][-1]["content"] == DEMO_REQUESTS[0]
        assert body["provider"] == {
            "only": ["nvidia"],
            "allow_fallbacks": False,
            "require_parameters": True,
            "max_price": {"prompt": 0, "completion": 0, "request": 0},
        }
        assert body["reasoning"] == {"enabled": False}
        assert body["response_format"]["json_schema"]["strict"] is True
        return httpx.Response(
            200,
            json={
                "model": MODEL,
                "provider": "Nvidia",
                "choices": [{"finish_reason": "stop", "message": {"content": "{}"}}],
                "usage": {"prompt_tokens": 22, "completion_tokens": 3, "cost": cost},
            },
        )

    monkeypatch.setattr(
        olist_nemotron.httpx,
        "Client",
        lambda **opts: real_client(transport=httpx.MockTransport(exchange), **opts),
    )
    gateway = HostedGateway(unavailable_connection, SecretStr("invented"))
    result = gateway._complete(request(DEMO_REQUESTS[0]), 1.0)
    assert (result.failure is None) is accepted
    assert result.usage.model_calls == 1
