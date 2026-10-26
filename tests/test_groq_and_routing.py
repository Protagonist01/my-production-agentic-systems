"""Invented Groq wire, explicit provider routing, replay and isolated allowance checks."""

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx
import pytest
from agent_harness.contracts import Budget, ModelMessage, ModelRequest, ModelResponse, Usage
from agent_harness.controls import BoundedGateway, ExecutionPolicy, ReservationQuote, SharedControls
from agent_harness.gateway import failed_response
from agent_harness.groq import ENDPOINT, MODEL, PROVIDER, GroqTransport
from agent_harness.groq_smoke_budget import SmokeAllowance, SmokeLedger, SmokeTransport, initialize
from agent_harness.offline_example import example_context
from agent_harness.provider_routing import FallbackRouter, RoutePlan
from agent_harness.release_contracts import pin

SCHEMA = {
    "type": "object",
    "properties": {"answer": {"type": "integer"}},
    "required": ["answer"],
    "additionalProperties": False,
}


def request(**changes):
    return ModelRequest(
        provider=PROVIDER,
        endpoint=ENDPOINT,
        model=MODEL,
        messages=(ModelMessage(role="user", content="Invented test: return answer42."),),
        parameters={"max_completion_tokens": 1024, "temperature": 0.0, "reasoning_effort": "low"},
        output_schema=SCHEMA,
    ).model_copy(update=changes)


def context(**changes):
    now = datetime.now(UTC)
    return example_context("invented", "a" * 64).model_copy(
        update={
            "mode": "fresh_candidate",
            "agent_id": "groq-invented-smoke",
            "clock": now,
            "deadline": now + timedelta(minutes=2),
            "budget": Budget(
                max_model_calls=2, max_tokens=10000, max_cost=Decimal(0), cost_currency="USD"
            ),
            **changes,
        }
    )


def body(**changes):
    return {
        "id": "invented-response",
        "model": MODEL,
        "choices": [
            {"finish_reason": "stop", "message": {"role": "assistant", "content": '{"answer":42}'}}
        ],
        "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
        **changes,
    }


def transport(handler):
    return GroqTransport(
        "invented-private-key",
        free_tier_confirmed=True,
        http_transport=httpx.MockTransport(handler),
    )


def test_strict_wire_retains_usage_unknown_cost_and_never_exports_key_or_tools():
    seen = []

    def handler(req):
        seen.append(req)
        payload = json.loads(req.content)
        assert payload["response_format"]["json_schema"]["strict"] is True
        assert payload["stream"] is False and "tools" not in payload
        return httpx.Response(200, json=body())

    value = transport(handler).generate(request(), timeout_seconds=2.0)
    assert len(seen) == 1 and value.failure is None
    assert value.output.content == '{"answer":42}'
    assert value.usage.input_tokens == 20 and value.usage.output_tokens == 10
    assert value.usage.cost is value.usage.cost_currency is None
    assert "invented-private-key" not in value.canonical_json()


@pytest.mark.parametrize(
    "change",
    [
        {"model": "llama-3.3-70b-versatile"},
        {"endpoint": "https://elsewhere.invalid"},
        {"model_revision": "unsupported"},
        {"parameters": {"thinking_level": "LOW"}},
        {"output_schema": {"type": "object", "additionalProperties": True}},
        {
            "output_schema": {
                "type": "object",
                "properties": {"x": {"$ref": "https://private.invalid"}},
                "required": ["x"],
                "additionalProperties": False,
            }
        },
    ],
)
def test_unsupported_route_parameters_schema_refuse_before_network(change):
    def forbidden(req):
        raise AssertionError("must not dispatch")

    result = transport(forbidden).generate(request(**change))
    assert result.failure.code == "invalid_response" and result.usage.model_calls == 0


@pytest.mark.parametrize(
    "code,expected",
    [
        (301, "invalid_response"),
        (401, "permission_denied"),
        (429, "rate_limited"),
        (503, "unavailable"),
    ],
)
def test_errors_do_not_redirect_retry_or_echo_private_provider_body(code, expected):
    seen = []

    def handler(req):
        seen.append(req)
        return httpx.Response(
            code, text="private-error-canary", headers={"Location": "https://private.invalid"}
        )

    result = transport(handler).generate(request())
    assert len(seen) == 1 and result.failure.code == expected
    assert result.usage.model_calls == 1 and "canary" not in result.canonical_json()


@pytest.mark.parametrize(
    "wire",
    [
        body(choices=[]),
        body(model="wrong-model"),
        body(
            choices=[
                {
                    "finish_reason": "length",
                    "message": {"role": "assistant", "content": '{"answer":42}'},
                }
            ]
        ),
        body(
            choices=[
                {
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": '{"answer":"wrong"}'},
                }
            ]
        ),
        body(
            choices=[
                {
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": '{"answer":42,"answer":0}'},
                }
            ]
        ),
    ],
)
def test_invalid_output_retains_actual_token_counts(wire):
    result = transport(lambda req: httpx.Response(200, json=wire)).generate(request())
    assert result.failure.code == "invalid_response" and result.usage.input_tokens == 20
    assert result.usage.output_tokens == 10 and result.provider_usage["total_tokens"] == 30


@pytest.mark.parametrize(
    "counts",
    [
        None,
        {"prompt_tokens": 1},
        {"prompt_tokens": True},
        {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 4},
    ],
)
def test_missing_usage_is_unknown_and_bad_numeric_usage_is_invalid(counts):
    result = transport(lambda req: httpx.Response(200, json=body(usage=counts))).generate(request())
    assert result.usage.cost is None
    if counts is None or (
        type(counts.get("prompt_tokens")) is int and counts == {"prompt_tokens": 1}
    ):
        assert result.failure is None and result.usage.output_tokens is None
    else:
        assert result.failure.code == "invalid_response" and result.usage.model_calls == 1


class Admission:
    def quote(self, req):
        return ReservationQuote(
            version="invented",
            max_tokens=100,
            max_cost=Decimal(0),
            currency="USD",
            evidence_ref="invented",
        )


class FakeAttempt:
    def __init__(self, failure=None):
        self.failure, self.requests = failure, []

    def generate(self, ctx, req, *, timeout_seconds):
        self.requests.append(req)
        if self.failure:
            return failed_response(
                req, self.failure, "Invented outage", dispatched=True, retryable=True
            )
        return ModelResponse(
            provider=req.provider,
            model=req.model,
            output=ModelMessage(role="assistant", content='{"answer":42}'),
            usage=Usage(
                model_calls=1, input_tokens=1, output_tokens=1, cost=None, cost_currency=None
            ),
        )


def router(primary_failure="unavailable", **policy_changes):
    fallback = request()
    primary = fallback.model_copy(
        update={"provider": "invented-primary", "endpoint": "in-process", "model": "invented-v1"}
    )
    plan = RoutePlan(primary=primary, fallback=fallback)
    controls = SharedControls()
    a, b = FakeAttempt(primary_failure), FakeAttempt()
    policy = ExecutionPolicy(max_attempts=1, circuit_failure_threshold=1, **policy_changes)
    return (
        FallbackRouter(
            plan,
            BoundedGateway(a, controls, Admission(), policy=policy),
            BoundedGateway(b, controls, Admission(), policy=policy),
        ),
        plan,
        controls,
        a,
        b,
    )


def test_transient_outage_switches_provider_with_separate_receipts_and_shared_calls():
    routing, plan, controls, a, b = router()
    ctx = context()
    result = routing.execute(ctx, plan_sha256=pin(plan))
    assert result.selected_route == "fallback" and result.usage.model_calls == 2
    assert result.usage.cost is None and len(result.attempts) == 2
    assert a.requests == [plan.primary] and b.requests == [plan.fallback]
    assert [r.response.provider for r in result.attempts] == [plan.primary.provider, PROVIDER]
    assert controls.snapshot(ctx.tenant_id, ctx.run_id).reserved_calls == 2
    assert routing.results == (result,)


@pytest.mark.parametrize("failure", ["permission_denied", "invalid_response", "budget_exhausted"])
def test_auth_schema_policy_failures_stop_without_fallback(failure):
    routing, plan, _, _, b = router(failure)
    result = routing.execute(context(), plan_sha256=pin(plan))
    assert result.selected_route is None and len(result.attempts) == 1 and not b.requests


def test_run_cap_cannot_be_bypassed_by_provider_change():
    routing, plan, _, _, b = router()
    ctx = context()
    ctx = ctx.model_copy(update={"budget": ctx.budget.model_copy(update={"max_model_calls": 1})})
    result = routing.execute(ctx, plan_sha256=pin(plan))
    assert (
        result.selected_route is None
        and result.attempts[-1].response.failure.code == "budget_exhausted"
    )
    assert result.usage.model_calls == 1 and not b.requests
    with pytest.raises(ValueError):
        routing.execute(context(), plan_sha256="0" * 64)


def test_provider_circuit_isolated_from_fallback_and_other_tenants():
    routing, plan, _, primary, fallback = router()
    first = context()
    routing.execute(first, plan_sha256=pin(plan))
    second = first.model_copy(update={"run_id": "invented-second-run"})
    result = routing.execute(second, plan_sha256=pin(plan))
    assert result.selected_route == "fallback" and result.usage.model_calls == 1
    assert len(primary.requests) == 1 and len(fallback.requests) == 2
    other = first.model_copy(update={"run_id": "invented-third-run", "tenant_id": "other-tenant"})
    routing.execute(other, plan_sha256=pin(plan))
    assert len(primary.requests) == 2


def test_strict_replay_consumes_both_provider_requests_and_mismatch_never_falls_back():
    from agent_harness.controls import ReplayAttempts
    from agent_harness.gateway import ModelExchange
    from agent_harness.recording import Recording, RecordingProvenance
    from agent_harness.replay import ReplayBinding, ReplayMismatch, StrictReplayGateway

    _, plan, _, a, b = router()
    captured = context(mode="offline_fake")
    recording = Recording(
        provenance=RecordingProvenance(
            source_kind="synthetic",
            source_version="invented",
            snapshot_ref=captured.versions.data_snapshot,
            policy_version=captured.versions.policy,
            scorer_version="invented",
            content_policy="invented-only",
            content_review_ref="invented-test-fixture",
        ),
        exchanges=(
            ModelExchange(
                context=captured,
                occurrence=1,
                request=plan.primary,
                response=a.generate(captured, plan.primary, timeout_seconds=1),
            ),
            ModelExchange(
                context=captured,
                occurrence=2,
                request=plan.fallback,
                response=b.generate(captured, plan.fallback, timeout_seconds=1),
            ),
        ),
    )
    current = captured.model_copy(update={"mode": "strict_replay", "run_id": "replay-current"})

    def replay_router(actual_plan):
        replay = StrictReplayGateway(
            recording, bindings=(ReplayBinding(recorded=captured, current=current),)
        )
        attempts, controls = ReplayAttempts(replay), SharedControls()
        policy = ExecutionPolicy(max_attempts=1)
        return FallbackRouter(
            actual_plan,
            BoundedGateway(attempts, controls, Admission(), policy=policy),
            BoundedGateway(attempts, controls, Admission(), policy=policy),
        ), replay

    routing, replay = replay_router(plan)
    assert routing.execute(current, plan_sha256=pin(plan)).selected_route == "fallback"
    replay.assert_complete()
    messages = (ModelMessage(role="user", content="Changed invented prompt."),)
    changed = RoutePlan(
        primary=plan.primary.model_copy(update={"messages": messages}),
        fallback=plan.fallback.model_copy(update={"messages": messages}),
    )
    routing, replay = replay_router(changed)
    with pytest.raises(ReplayMismatch):
        routing.execute(current, plan_sha256=pin(changed))
    assert not routing.results


def test_separate_smoke_allowance_consumes_failed_and_unsettled_attempts(tmp_path):
    ctx = context()
    req = request()
    now = datetime.now(UTC)
    allowance = SmokeAllowance(
        authorization_ref="invented-user-approval",
        free_account_attestation_ref="invented",
        credential_sha256="a" * 64,
        request_sha256=(req.fingerprint(),),
        max_attempts=2,
        approved_at=now - timedelta(seconds=1),
        expires_at=now + timedelta(minutes=2),
    )
    path = tmp_path / "groq.sqlite"
    ledger = SmokeLedger(path, initialize(path, allowance))
    ticket = ledger.reserve(ctx, req, "a" * 64)

    def reserve(_):
        try:
            return ledger.reserve(ctx, req, "a" * 64)
        except ValueError:
            return None

    with ThreadPoolExecutor(max_workers=4) as pool:
        assert sum(x is not None for x in pool.map(reserve, range(4))) == 1
    assert ledger.summary() == {"maximum": 2, "consumed": 2, "remaining": 0, "unsettled": 2}
    failure = failed_response(req, "unavailable", "invented", dispatched=True)
    ledger.settle(ticket, failure)
    assert ledger.summary()["unsettled"] == 1
    with pytest.raises(ValueError):
        ledger.settle(ticket, failure)
    with pytest.raises(FileExistsError):
        initialize(path, allowance)

    def forbidden(req):
        raise AssertionError("budget must stop dispatch")

    guarded = SmokeTransport(transport(forbidden), ledger, ctx, "a" * 64)
    assert guarded.generate(req).failure.code == "budget_exhausted"


def test_smoke_scope_cannot_dispatch_changed_text_key_agent_or_expired_grant(tmp_path):
    ctx, req = context(), request()
    now = datetime.now(UTC)
    grant = SmokeAllowance(
        authorization_ref="invented",
        free_account_attestation_ref="invented",
        credential_sha256="a" * 64,
        request_sha256=(req.fingerprint(),),
        max_attempts=1,
        approved_at=now - timedelta(seconds=2),
        expires_at=now + timedelta(minutes=1),
    )
    path = tmp_path / "limited.sqlite"
    ledger = SmokeLedger(path, initialize(path, grant))
    for actual_context, actual_request, key in (
        (ctx.model_copy(update={"agent_id": "olist"}), req, "a" * 64),
        (
            ctx,
            req.model_copy(
                update={"messages": (ModelMessage(role="user", content="Different invented text"),)}
            ),
            "a" * 64,
        ),
        (ctx, req, "b" * 64),
    ):
        with pytest.raises(ValueError):
            ledger.reserve(actual_context, actual_request, key)
    assert ledger.summary()["consumed"] == 0
    expired = grant.model_copy(update={"expires_at": now - timedelta(seconds=1)})
    expired_path = tmp_path / "expired.sqlite"
    old = SmokeLedger(expired_path, initialize(expired_path, expired))
    with pytest.raises(ValueError):
        old.reserve(ctx, req, "a" * 64)
    assert old.summary()["consumed"] == 0


def test_smoke_delegate_exception_keeps_consumed_attempt(tmp_path):
    ctx, req = context(), request()
    now = datetime.now(UTC)
    grant = SmokeAllowance(
        authorization_ref="invented",
        free_account_attestation_ref="invented",
        credential_sha256="a" * 64,
        request_sha256=(req.fingerprint(),),
        max_attempts=1,
        approved_at=now - timedelta(seconds=1),
        expires_at=now + timedelta(minutes=1),
    )
    path = tmp_path / "throw.sqlite"
    ledger = SmokeLedger(path, initialize(path, grant))

    class Broken:
        def generate(self, req, *, timeout_seconds):
            raise RuntimeError("private-throw-canary")

    with pytest.raises(RuntimeError):
        SmokeTransport(Broken(), ledger, ctx, "a" * 64).generate(req)
    assert ledger.summary() == {"maximum": 1, "consumed": 1, "remaining": 0, "unsettled": 1}
