"""Explicit two-provider execution: separate requests, receipts and per-route controls."""

import threading
from typing import Literal, Self, cast

from pydantic import model_validator

from agent_harness.contracts import Contract, ModelRequest, ModelResponse, RunContext, Usage
from agent_harness.controls import BoundedGateway, combine_usage
from agent_harness.release_contracts import Sha256, pin


class RoutePlan(Contract):
    version: Literal["two-provider-fallback-v1"] = "two-provider-fallback-v1"
    primary: ModelRequest
    fallback: ModelRequest

    @model_validator(mode="after")
    def same_task(self) -> Self:
        a, b = self.primary, self.fallback
        if a.provider == b.provider or (a.messages, a.tools, a.tool_choice, a.output_schema) != (
            b.messages,
            b.tools,
            b.tool_choice,
            b.output_schema,
        ):
            raise ValueError("different providers must receive the same explicit task/schema")
        return self


class RouteAttempt(Contract):
    route: Literal["primary", "fallback"]
    request: ModelRequest
    response: ModelResponse


class RouteResult(Contract):
    plan_sha256: Sha256
    context_sha256: Sha256
    attempts: tuple[RouteAttempt, ...]
    selected_route: Literal["primary", "fallback"] | None
    usage: Usage


class FallbackRouter:
    """Not a ModelGateway alias: callers must handle the explicit multi-request result."""

    def __init__(self, plan: RoutePlan, primary: BoundedGateway, fallback: BoundedGateway) -> None:
        if (
            primary.controls is not fallback.controls
            or primary.policy.max_attempts != 1
            or fallback.policy.max_attempts != 1
        ):
            raise ValueError("both routes require shared run controls and one attempt each")
        self._plan = RoutePlan.model_validate_json(plan.canonical_json())
        self._primary, self._fallback = primary, fallback
        self._lock = threading.Lock()
        self._results: list[str] = []

    @property
    def results(self) -> tuple[RouteResult, ...]:
        with self._lock:
            return tuple(RouteResult.model_validate_json(raw) for raw in self._results)

    def execute(self, context: RunContext, *, plan_sha256: str) -> RouteResult:
        context = RunContext.model_validate_json(context.canonical_json())
        if plan_sha256 != pin(self._plan) or context.mode not in (
            "fresh_candidate",
            "monitoring",
            "strict_replay",
        ):
            raise ValueError("routing requires the externally frozen plan and controlled mode")
        attempts: list[RouteAttempt] = []
        selected: Literal["primary", "fallback"] | None = None
        for name, request, gateway in (
            ("primary", self._plan.primary, self._primary),
            ("fallback", self._plan.fallback, self._fallback),
        ):
            response = gateway.generate(context, request)
            route = cast(Literal["primary", "fallback"], name)
            attempts.append(RouteAttempt(route=route, request=request, response=response))
            if response.failure is None:
                selected = route
                break
            if response.failure.code not in ("timeout", "unavailable", "rate_limited"):
                break
        result = RouteResult(
            plan_sha256=pin(self._plan),
            context_sha256=pin(context),
            attempts=tuple(attempts),
            selected_route=selected,
            usage=combine_usage(
                tuple(a.response.usage for a in attempts), context.budget.cost_currency
            ),
        )
        with self._lock:
            self._results.append(result.canonical_json())
        return result
