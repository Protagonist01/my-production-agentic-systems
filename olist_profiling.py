"""Opt-in content-free stage timings; no transport, keys or provider scope is created."""

import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from math import ceil
from typing import Any, Literal, TypeVar

from agent_harness.contracts import Contract, ModelGateway, ModelRequest, ModelResponse, RunContext
from olist_support.business import ConnectionFactory
from olist_support.console_auth import AuthStore
from olist_support.console_cases import CaseStore
from olist_support.console_contracts import CaseRecord, Principal
from olist_support.routing_contracts import RoutingPlan
from olist_support.workflow import IntentDecision, RoutingGatewayPlanner, WorkflowRequest
from pydantic import Field
from starlette.types import ASGIApp, Receive, Scope, Send

Stage = Literal[
    "request",
    "authenticate",
    "login",
    "case_submit",
    "case_decide",
    "case_resume",
    "database_context",
    "planner",
    "gateway",
    "parse",
]
STAGES: tuple[Stage, ...] = (
    "request",
    "authenticate",
    "login",
    "case_submit",
    "case_decide",
    "case_resume",
    "database_context",
    "planner",
    "gateway",
    "parse",
)
T = TypeVar("T")


class Span(Contract):
    sequence: int = Field(ge=0)
    parent: int | None
    stage: Stage
    elapsed_ns: int = Field(ge=0)
    failed: bool


class Recorder:
    def __init__(self, *, limit: int = 4096, clock: Callable[[], int] = time.monotonic_ns):
        if type(limit) is not int or not 1 <= limit <= 100_000:
            raise ValueError("bounded positive timing capacity required")
        self.limit, self.clock = limit, clock
        self._lock = threading.Lock()
        self._parent: ContextVar[int | None] = ContextVar("olist_profile_parent", default=None)
        self._next = 0
        self._active = 0
        self._dropped = 0
        self._spans: list[Span] = []

    @contextmanager
    def phase(self, stage: Stage) -> Iterator[None]:
        if stage not in STAGES:
            raise ValueError("fixed stage name required")
        with self._lock:
            seq = self._next
            self._next += 1
            admitted = seq < self.limit
            self._active += 1
            if not admitted:
                self._dropped += 1
        parent = self._parent.get()
        token = self._parent.set(seq if admitted else parent)
        started = self.clock()
        failed = False
        try:
            yield
        except BaseException:
            failed = True
            raise
        finally:
            elapsed = max(0, self.clock() - started)
            self._parent.reset(token)
            with self._lock:
                self._active -= 1
                if admitted:
                    self._spans.append(
                        Span(
                            sequence=seq,
                            parent=parent,
                            stage=stage,
                            elapsed_ns=elapsed,
                            failed=failed,
                        )
                    )

    def call(self, stage: Stage, fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        with self.phase(stage):
            return fn(*args, **kwargs)

    def coverage(self, required: tuple[Stage, ...]) -> dict[str, object]:
        if (
            not required
            or len(set(required)) != len(required)
            or any(s not in STAGES for s in required)
        ):
            raise ValueError("explicit distinct required stages needed")
        with self._lock:
            spans = {s.sequence: s for s in self._spans}
            incomplete = self._active > 0 or self._dropped > 0
        roots = [s for s in spans.values() if s.stage == "request"]
        missing = []
        for root in roots:
            observed = set()
            for s in spans.values():
                current = s
                while current.sequence != root.sequence and current.parent in spans:
                    current = spans[current.parent]
                if current.sequence == root.sequence:
                    observed.add(s.stage)
            missing.append(tuple(stage for stage in required if stage not in observed))
        return {
            "required_stages": required,
            "requests": len(roots),
            "complete_requests": sum(not m for m in missing) if not incomplete else 0,
            "missing_stage_counts": {s: sum(s in m for m in missing) for s in required},
            "active_or_dropped": incomplete,
            "complete": bool(roots) and not incomplete and all(not m for m in missing),
        }

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            spans = tuple(self._spans)
            active, dropped = self._active, self._dropped
        groups = {}
        for stage in STAGES:
            selected = [s for s in spans if s.stage == stage]
            values = sorted(s.elapsed_ns for s in selected)
            groups[stage] = {
                "observations": len(values),
                "failures": sum(s.failed for s in selected),
                "percentiles_ns": {
                    str(q): values[ceil(len(values) * q) - 1] if values else None
                    for q in (0.5, 0.95, 0.99)
                },
            }
        return {
            "version": "olist-content-free-stage-profile-v1",
            "active": active,
            "dropped": dropped,
            "spans": [s.model_dump(mode="json") for s in sorted(spans, key=lambda s: s.sequence)],
            "stages": groups,
            "finalized": active == 0,
            "capacity_complete": active == 0 and dropped == 0,
            "elapsed_scope": "inclusive_monotonic_do_not_sum_nested_stages",
            "all_subprocesses_instrumented": False,
            "provider_internal_time_known": False,
            "release_allowed": False,
        }


class ProfiledGateway:
    def __init__(self, delegate: ModelGateway, recorder: Recorder):
        self.delegate, self.recorder = delegate, recorder

    def generate(self, context: RunContext, request: ModelRequest) -> ModelResponse:
        return self.recorder.call("gateway", self.delegate.generate, context, request)


class ProfiledPlanner(RoutingGatewayPlanner):
    def __init__(self, gateway: ModelGateway, route: ModelRequest, recorder: Recorder):
        self.recorder = recorder
        super().__init__(ProfiledGateway(gateway, recorder), route)

    def plan(self, context: RunContext, request: WorkflowRequest) -> IntentDecision:
        return self.recorder.call("planner", super().plan, context, request)

    def parse_plan(self, content: str) -> RoutingPlan:
        return self.recorder.call("parse", super().parse_plan, content)


class ProfiledAuth(AuthStore):
    def __init__(self, connect: ConnectionFactory, recorder: Recorder):
        self.recorder = recorder
        super().__init__(connect)

    def authenticate(self, token: str, csrf: str | None = None) -> Principal:
        return self.recorder.call("authenticate", super().authenticate, token, csrf)

    def login(self, username: str, password: str) -> tuple[str, str, Principal]:
        return self.recorder.call("login", super().login, username, password)


class ProfiledCases(CaseStore):
    def __init__(
        self,
        connect: ConnectionFactory,
        *,
        recorder: Recorder,
        planner: ProfiledPlanner | None = None,
    ):
        self.recorder = recorder
        super().__init__(connect, planner=planner)

    @contextmanager
    def connection(self) -> Iterator[Any]:
        # Inclusive context time, not isolated query/lock/commit timings.
        with self.recorder.phase("database_context"), super().connection() as connection:
            yield connection

    def submit(self, *args: Any, **kwargs: Any) -> CaseRecord:
        return self.recorder.call("case_submit", super().submit, *args, **kwargs)

    def decide(self, *args: Any, **kwargs: Any) -> CaseRecord:
        return self.recorder.call("case_decide", super().decide, *args, **kwargs)

    def resume(self, *args: Any, **kwargs: Any) -> CaseRecord:
        return self.recorder.call("case_resume", super().resume, *args, **kwargs)


class ProfiledHTTP:
    def __init__(self, app: ASGIApp, recorder: Recorder):
        self.app, self.recorder = app, recorder

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
        else:
            with self.recorder.phase("request"):
                await self.app(scope, receive, send)
