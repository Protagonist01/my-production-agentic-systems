"""Shared admission, observed usage, bounded retries and tenant/route circuits."""

import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal, localcontext
from typing import Annotated, Protocol

from pydantic import Field

from agent_harness.contracts import (
    Budget,
    Contract,
    Count,
    FailureCode,
    ModelRequest,
    ModelResponse,
    Money,
    NonEmpty,
    RunContext,
    Usage,
)
from agent_harness.gateway import failed_response
from agent_harness.replay import ReplayMismatch, StrictReplayGateway


class Clock(Protocol):
    def now(self) -> datetime: ...
    def monotonic(self) -> float: ...
    def sleep(self, seconds: float) -> None: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)

    def monotonic(self) -> float:
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


class ExecutionPolicy(Contract):
    version: NonEmpty = "h4-control-v1"
    max_attempts: Annotated[int, Field(ge=1, le=5)] = 3
    attempt_timeout_seconds: Annotated[float, Field(gt=0, le=60)] = 30.0
    backoff_seconds: Annotated[float, Field(ge=0, le=5)] = 0.25
    max_backoff_seconds: Annotated[float, Field(ge=0, le=5)] = 2.0
    circuit_failure_threshold: Annotated[int, Field(gt=0, le=100)] = 3
    circuit_cooldown_seconds: Annotated[float, Field(gt=0, le=300)] = 5.0


class ReservationQuote(Contract):
    """Reviewed upper bounds, not estimates or observed provider charges."""

    version: NonEmpty
    max_tokens: Annotated[int, Field(gt=0)]
    max_cost: Money
    currency: NonEmpty
    evidence_ref: NonEmpty


class AdmissionPolicy(Protocol):
    def quote(self, request: ModelRequest) -> ReservationQuote: ...


class DeadlineGateway(Protocol):
    def generate(
        self, context: RunContext, request: ModelRequest, *, timeout_seconds: float
    ) -> ModelResponse: ...


class ReplayAttempts:
    """Adapt only the network-free H3 gateway; replay still requires assert_complete."""

    def __init__(self, replay: StrictReplayGateway) -> None:
        if not isinstance(replay, StrictReplayGateway):
            raise TypeError("ReplayAttempts requires StrictReplayGateway")
        self.replay = replay

    def generate(
        self, context: RunContext, request: ModelRequest, *, timeout_seconds: float
    ) -> ModelResponse:
        return self.replay.generate(context, request)


def add_money(left: Decimal, right: Decimal) -> Decimal:
    """Do not round a tiny extra reservation away at Decimal's default precision."""
    with localcontext() as context:
        context.prec = (
            max(28, len(left.as_tuple().digits), len(right.as_tuple().digits))
            + abs(left.adjusted() - right.adjusted())
            + 4
        )
        return left + right


def _total_cost(values: tuple[Usage, ...]) -> Decimal:
    total = Decimal(0)
    for value in values:
        total = add_money(total, value.cost or Decimal(0))
    return total


def combine_usage(values: tuple[Usage, ...], currency: str) -> Usage:
    def tokens(name: str) -> int | None:
        counts = [getattr(value, name) for value in values]
        return None if any(count is None for count in counts) else sum(counts)

    known_cost = all(value.cost is not None and value.cost_currency == currency for value in values)
    return Usage(
        model_calls=sum(value.model_calls for value in values),
        input_tokens=tokens("input_tokens"),
        output_tokens=tokens("output_tokens"),
        cost=_total_cost(values) if known_cost else None,
        cost_currency=currency if known_cost else None,
    )


class BudgetSnapshot(Contract):
    reserved_calls: Count
    reserved_tokens: Count
    reserved_cost: Money
    currency: NonEmpty
    frozen: bool
    observed_usage: Usage


class ControlledCall(Contract):
    context: RunContext
    occurrence: Annotated[int, Field(gt=0)]
    request_fingerprint: NonEmpty
    policy: ExecutionPolicy
    reservations: tuple[ReservationQuote, ...]
    attempt_usage: tuple[Usage, ...]
    response: ModelResponse


class AdmissionDenied(Exception):
    def __init__(self, code: FailureCode, message: str) -> None:
        self.code, self.message = code, message
        super().__init__(message)


RunKey = tuple[str, str]
RouteKey = tuple[str, str, str, str, str | None]


@dataclass
class _Run:
    budget: Budget
    deadline_text: str
    end: float
    calls: int = 0
    tokens: int = 0
    cost: Decimal = Decimal(0)
    frozen: bool = False
    usage: list[Usage] = field(default_factory=list)


@dataclass
class _Circuit:
    policy: ExecutionPolicy
    failures: int = 0
    open_until: float = 0.0
    probe_active: bool = False
    epoch: int = 0


@dataclass(frozen=True)
class _Ticket:
    run: RunKey
    route: RouteKey
    epoch: int
    quote: ReservationQuote
    end: float
    serial: int


class SharedControls:
    """Explicitly share one instance across callers. In-process, never a distributed quota."""

    def __init__(self, *, clock: Clock | None = None) -> None:
        self.clock = clock or SystemClock()
        self._lock = threading.Lock()
        self._runs: dict[RunKey, _Run] = {}
        self._circuits: dict[RouteKey, _Circuit] = {}
        self._settled: set[tuple[RunKey, int]] = set()

    def admit(
        self,
        context: RunContext,
        request: ModelRequest,
        quote: ReservationQuote,
        policy: ExecutionPolicy,
    ) -> _Ticket:
        context = RunContext.model_validate(context)
        quote = ReservationQuote.model_validate(quote)
        policy = ExecutionPolicy.model_validate(policy)
        key = context.tenant_id, context.run_id
        route = (
            context.tenant_id,
            request.provider,
            request.endpoint,
            request.model,
            request.model_revision,
        )
        with self._lock:
            now = self.clock.monotonic()
            state = self._runs.get(key)
            if state is None:
                remaining = (context.deadline - self.clock.now()).total_seconds()
                state = _Run(context.budget, context.deadline.isoformat(), now + max(0, remaining))
                self._runs[key] = state
            if (
                state.budget != context.budget
                or state.deadline_text != context.deadline.isoformat()
            ):
                raise AdmissionDenied("permission_denied", "Run budget/deadline changed")
            if state.frozen:
                raise AdmissionDenied("budget_exhausted", "Run frozen after accounting breach")
            if now >= state.end:
                raise AdmissionDenied("timeout", "Run deadline exhausted")
            circuit = self._circuits.setdefault(route, _Circuit(policy))
            if circuit.policy != policy:
                raise AdmissionDenied("permission_denied", "Shared route policy changed")
            if now < circuit.open_until or circuit.probe_active:
                raise AdmissionDenied("unavailable", "Provider circuit is open")
            if quote.currency != state.budget.cost_currency:
                raise AdmissionDenied(
                    "budget_exhausted", "Reservation currency differs from budget"
                )
            if (
                state.calls + 1 > state.budget.max_model_calls
                or state.tokens + quote.max_tokens > state.budget.max_tokens
                or add_money(state.cost, quote.max_cost) > state.budget.max_cost
            ):
                raise AdmissionDenied("budget_exhausted", "Shared reservation budget exhausted")
            # Check and reserve every dimension under the same lock, before dispatch.
            state.calls += 1
            state.tokens += quote.max_tokens
            state.cost = add_money(state.cost, quote.max_cost)
            if circuit.open_until > 0:
                circuit.probe_active = True
            return _Ticket(key, route, circuit.epoch, quote, state.end, state.calls)

    def remaining(self, ticket: _Ticket) -> float:
        return max(0.0, ticket.end - self.clock.monotonic())

    def finish(self, ticket: _Ticket, response: ModelResponse, *, fatal: bool = False) -> bool:
        """Charge remains reserved. Keep unknowns; freeze on observable bound violations."""
        with self._lock:
            identity = ticket.run, ticket.serial
            if identity in self._settled:
                raise RuntimeError("attempt already settled")
            self._settled.add(identity)
            state = self._runs[ticket.run]
            usage = response.usage
            state.usage.append(Usage.model_validate_json(usage.canonical_json()))
            known_tokens = (usage.input_tokens or 0) + (usage.output_tokens or 0)
            breach = (
                fatal
                or usage.model_calls > 1
                or known_tokens > ticket.quote.max_tokens
                or (
                    usage.cost is not None
                    and (
                        usage.cost_currency != ticket.quote.currency
                        or usage.cost > ticket.quote.max_cost
                    )
                )
            )
            state.frozen |= breach
            circuit = self._circuits[ticket.route]
            if ticket.epoch == circuit.epoch:
                transient = response.failure is not None and response.failure.code in (
                    "timeout",
                    "rate_limited",
                    "unavailable",
                )
                if transient:
                    circuit.failures += 1
                    if (
                        circuit.probe_active
                        or circuit.failures >= circuit.policy.circuit_failure_threshold
                    ):
                        circuit.open_until = (
                            self.clock.monotonic() + circuit.policy.circuit_cooldown_seconds
                        )
                        circuit.probe_active = False
                        circuit.epoch += 1
                else:
                    # A nontransient response shows reachability, even if its content is invalid.
                    circuit.failures = 0
                    circuit.open_until = 0.0
                    circuit.probe_active = False
                    circuit.epoch += 1
            return breach

    def snapshot(self, tenant_id: str, run_id: str) -> BudgetSnapshot:
        with self._lock:
            state = self._runs[(tenant_id, run_id)]
            return BudgetSnapshot(
                reserved_calls=state.calls,
                reserved_tokens=state.tokens,
                reserved_cost=state.cost,
                currency=state.budget.cost_currency,
                frozen=state.frozen,
                observed_usage=combine_usage(tuple(state.usage), state.budget.cost_currency),
            )


class BoundedGateway:
    """Current caller → shared reservation → explicitly deadline-aware attempt gateway."""

    def __init__(
        self,
        attempts: DeadlineGateway,
        controls: SharedControls,
        admission: AdmissionPolicy,
        *,
        policy: ExecutionPolicy | None = None,
    ) -> None:
        self._attempts, self.controls, self._admission = attempts, controls, admission
        self.policy = ExecutionPolicy.model_validate_json(
            ExecutionPolicy.model_validate(policy or ExecutionPolicy()).canonical_json()
        )
        self._lock = threading.Lock()
        self._counts: dict[tuple[str, ...], int] = {}
        self._calls: list[str] = []

    @property
    def calls(self) -> tuple[ControlledCall, ...]:
        with self._lock:
            return tuple(ControlledCall.model_validate_json(row) for row in self._calls)

    def generate(self, context: RunContext, request: ModelRequest) -> ModelResponse:
        context = RunContext.model_validate_json(
            RunContext.model_validate(context).canonical_json()
        )
        request = ModelRequest.model_validate_json(
            ModelRequest.model_validate(request).canonical_json()
        )
        observed: list[Usage] = []
        reservations: list[ReservationQuote] = []
        response = failed_response(
            request, "permission_denied", "Unsupported controlled mode", dispatched=False
        )
        replay = isinstance(self._attempts, ReplayAttempts)
        if (context.mode == "strict_replay" and replay) or (
            context.mode in ("fresh_candidate", "monitoring") and not replay
        ):
            response = self._execute(context, request, observed, reservations)
        response = ModelResponse.model_validate_json(
            response.model_copy(
                update={
                    "usage": combine_usage(tuple(observed), context.budget.cost_currency),
                }
            ).canonical_json()
        )
        scope = (
            context.run_id,
            context.tenant_id,
            context.agent_id,
            context.case_id,
            context.trial_id,
        )
        with self._lock:
            occurrence = self._counts.get(scope, 0) + 1
            self._counts[scope] = occurrence
            self._calls.append(
                ControlledCall(
                    context=context,
                    occurrence=occurrence,
                    request_fingerprint=request.fingerprint(),
                    policy=self.policy,
                    reservations=tuple(reservations),
                    attempt_usage=tuple(observed),
                    response=response,
                ).canonical_json()
            )
        return response

    def _execute(
        self,
        context: RunContext,
        request: ModelRequest,
        observed: list[Usage],
        reservations: list[ReservationQuote],
    ) -> ModelResponse:
        for index in range(self.policy.max_attempts):
            try:
                quote = ReservationQuote.model_validate_json(
                    ReservationQuote.model_validate(self._admission.quote(request)).canonical_json()
                )
            except ValueError:
                return failed_response(
                    request, "budget_exhausted", "No reviewed admission ceiling", dispatched=False
                )
            try:
                ticket = self.controls.admit(context, request, quote, self.policy)
            except AdmissionDenied as error:
                return failed_response(request, error.code, error.message, dispatched=False)
            reservations.append(quote)
            remaining = self.controls.remaining(ticket)
            fatal = False
            try:
                if remaining <= 0:
                    response = failed_response(
                        request,
                        "timeout",
                        "Run deadline exhausted before attempt",
                        dispatched=False,
                    )
                else:
                    response = ModelResponse.model_validate(
                        self._attempts.generate(
                            context,
                            request,
                            timeout_seconds=min(remaining, self.policy.attempt_timeout_seconds),
                        )
                    )
                    response = ModelResponse.model_validate_json(response.canonical_json())
                    if (response.provider, response.model) != (request.provider, request.model):
                        raise ValueError("attempt response route differs")
            except ReplayMismatch:
                self.controls.finish(
                    ticket,
                    failed_response(request, "unavailable", "Replay mismatch", dispatched=True),
                    fatal=True,
                )
                raise
            except Exception:
                # Keep reservation on unexpected failures; detailed exception handling is H6.
                fatal = True
                response = failed_response(
                    request,
                    "unavailable",
                    "Attempt failed unexpectedly; run frozen",
                    dispatched=True,
                )
            observed.append(response.usage)
            breach = self.controls.finish(ticket, response, fatal=fatal)
            if breach:
                return failed_response(
                    request,
                    "budget_exhausted",
                    "Admission ceiling breached; run frozen",
                    dispatched=False,
                )
            if self.controls.remaining(ticket) <= 0:
                return failed_response(
                    request, "timeout", "Run deadline exhausted", dispatched=False
                )
            if (
                response.failure is None
                or not response.failure.retryable
                or response.failure.code not in ("timeout", "rate_limited", "unavailable")
                or index + 1 == self.policy.max_attempts
            ):
                return response
            delay = min(self.policy.backoff_seconds * (2**index), self.policy.max_backoff_seconds)
            remaining = self.controls.remaining(ticket)
            if delay >= remaining:
                self.controls.clock.sleep(remaining)
                return failed_response(
                    request, "timeout", "Run deadline exhausted during backoff", dispatched=False
                )
            self.controls.clock.sleep(delay)
        raise AssertionError("validated attempt bound must be positive")
