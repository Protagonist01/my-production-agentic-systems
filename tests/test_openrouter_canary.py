"""Invented wire/ledger regressions; no network or credentials."""

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from agent_harness.openrouter_canary import (
    MODEL,
    CanaryAllowance,
    CanaryLedger,
    generate,
    initialize,
    request_payload,
    requests,
)


def wire(**changes):
    return {
        "model": MODEL.removesuffix(":free"),
        "id": "invented-response",
        "choices": [
            {"finish_reason": "stop", "message": {"role": "assistant", "content": '{"answer":8}'}}
        ],
        "usage": {"prompt_tokens": 40, "completion_tokens": 5, "total_tokens": 45},
        **changes,
    }


def test_actual_wire_has_zero_price_no_fallback_no_tools_and_retains_observed_usage():
    seen = []

    def handler(req):
        p = json.loads(req.content)
        seen.append(p)
        assert p["provider"] == {
            "allow_fallbacks": False,
            "require_parameters": True,
            "max_price": {"prompt": 0, "completion": 0, "request": 0},
        }
        assert p["model"].endswith(":free") and "tools" not in p and "models" not in p
        return httpx.Response(200, json=wire())

    result = generate(
        "invented-secret",
        requests()[0],
        timeout_seconds=2,
        http_transport=httpx.MockTransport(handler),
    )
    assert len(seen) == 1 and result.failure is None
    assert result.model == MODEL.removesuffix(":free")
    assert result.usage.input_tokens == 40 and result.usage.cost is None
    assert "invented-secret" not in result.canonical_json()


@pytest.mark.parametrize("code", [301, 401, 403, 429, 500, 503])
def test_remote_errors_never_retry_redirect_or_echo_provider_body(code):
    seen = []

    def handler(req):
        seen.append(req)
        return httpx.Response(code, text="private provider detail")

    result = generate("invented", requests()[0], http_transport=httpx.MockTransport(handler))
    assert len(seen) == 1 and result.failure and result.usage.model_calls == 1
    assert result.usage.cost is None and "private provider detail" not in result.canonical_json()


@pytest.mark.parametrize(
    "changes",
    [
        {"model": "paid/model"},
        {"parameters": {}},
        {"messages": ()},
        {"endpoint": "https://elsewhere.invalid"},
    ],
)
def test_unapproved_request_never_dispatches(changes):
    def forbidden(req):
        raise AssertionError("network forbidden")

    result = generate(
        "invented",
        requests()[0].model_copy(update=changes),
        http_transport=httpx.MockTransport(forbidden),
    )
    assert result.failure and result.usage.model_calls == 0


@pytest.mark.parametrize(
    "body",
    [
        wire(model="other"),
        wire(choices=[]),
        wire(
            choices=[{"finish_reason": "length", "message": {"role": "assistant", "content": "{}"}}]
        ),
        wire(
            choices=[
                {
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": '{"answer":1,"answer":2}'},
                }
            ]
        ),
        wire(
            choices=[
                {
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": '{"answer":"eight"}'},
                }
            ]
        ),
    ],
)
def test_invalid_output_is_failed_not_healed(body):
    result = generate(
        "invented",
        requests()[0],
        http_transport=httpx.MockTransport(lambda req: httpx.Response(200, json=body)),
    )
    assert result.failure and result.usage.input_tokens == 40


def ledger(tmp_path):
    now = datetime.now(UTC)
    grant = CanaryAllowance(
        authorization_ref="invented-owner-12",
        credential_sha256="a" * 64,
        approved_at=now - timedelta(minutes=1),
        expires_at=now + timedelta(hours=2),
    )
    path = tmp_path / "canary.sqlite"
    return CanaryLedger(path, initialize(path, grant)), grant


def test_concurrent_duplicates_only_reserve_once_and_all_twelve_are_hard_capped(tmp_path):
    store, grant = ledger(tmp_path)

    def reserve(_):
        try:
            return store.reserve(requests()[0], "a" * 64)
        except ValueError:
            return None

    with ThreadPoolExecutor(max_workers=4) as pool:
        assert sum(x is not None for x in pool.map(reserve, range(8))) == 1
    for request in requests()[1:]:
        store.reserve(request, "a" * 64)
    assert store.summary() == {"maximum": 12, "consumed": 12, "remaining": 0, "unsettled": 12}
    with pytest.raises(ValueError):
        store.reserve(requests()[0], "a" * 64)
    with pytest.raises(FileExistsError):
        initialize(store.path, grant)
    reopened = CanaryLedger(store.path, store.allowance_sha256)
    assert reopened.summary() == store.summary()


def test_stale_pin_foreign_credential_and_double_settlement_refuse(tmp_path):
    store, _ = ledger(tmp_path)
    with pytest.raises(ValueError):
        CanaryLedger(store.path, "b" * 64).reserve(requests()[0], "a" * 64)
    with pytest.raises(ValueError):
        store.reserve(requests()[0], "b" * 64)
    ticket = store.reserve(requests()[0], "a" * 64)
    result = generate(
        "invented",
        requests()[0],
        http_transport=httpx.MockTransport(lambda req: httpx.Response(503, text="no")),
    )
    store.settle(ticket, result)
    assert store.summary()["consumed"] == 1 and store.summary()["unsettled"] == 0
    with pytest.raises(ValueError):
        store.settle(ticket, result)
    assert request_payload(requests()[0])["max_tokens"] == 256
