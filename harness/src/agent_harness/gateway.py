"""One dispatch boundary with detached per-occurrence evidence; persistence is H3."""

import threading
from typing import Annotated, Protocol

from pydantic import Field

from agent_harness.contracts import (
    Contract,
    Failure,
    FailureCode,
    ModelRequest,
    ModelResponse,
    RunContext,
    Usage,
)


def failed_response(
    request: ModelRequest,
    code: FailureCode,
    message: str,
    *,
    dispatched: bool,
    retryable: bool = False,
    usage: Usage | None = None,
) -> ModelResponse:
    return ModelResponse(
        provider=request.provider,
        model=request.model,
        model_revision=request.model_revision,
        usage=usage
        or Usage(
            model_calls=int(dispatched),
            input_tokens=None,
            output_tokens=None,
            cost=None,
            cost_currency=None,
        ),
        failure=Failure(stage="model", code=code, message=message, retryable=retryable),
    )


class ModelTransport(Protocol):
    def generate(self, request: ModelRequest) -> ModelResponse: ...


class ModelExchange(Contract):
    context: RunContext
    occurrence: Annotated[int, Field(gt=0)]
    request: ModelRequest
    response: ModelResponse

    def identity(self) -> tuple[str, str, str, str, str, int, str]:
        scope = self.context
        return (
            scope.run_id,
            scope.tenant_id,
            scope.agent_id,
            scope.case_id,
            scope.trial_id,
            self.occurrence,
            self.request.fingerprint(),
        )


class ProviderGateway:
    """No cache/retry/fallback. A new instance starts new in-memory occurrence state."""

    def __init__(self, transport: ModelTransport) -> None:
        self._transport = transport
        self._lock = threading.Lock()
        self._counts: dict[tuple[str, ...], int] = {}
        self._records: list[str] = []

    @property
    def exchanges(self) -> tuple[ModelExchange, ...]:
        with self._lock:
            return tuple(ModelExchange.model_validate_json(value) for value in self._records)

    def generate(self, context: RunContext, request: ModelRequest) -> ModelResponse:
        # Frozen models contain mutable nested dictionaries: wire round trips detach them.
        context = RunContext.model_validate_json(
            RunContext.model_validate(context).canonical_json()
        )
        request = ModelRequest.model_validate_json(
            ModelRequest.model_validate(request).canonical_json()
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
        if context.mode not in ("fresh_candidate", "monitoring"):
            response = failed_response(
                request,
                "permission_denied",
                "Live gateway refuses fake/replay mode",
                dispatched=False,
            )
        else:
            transport_request = ModelRequest.model_validate_json(request.canonical_json())
            try:
                returned = ModelResponse.model_validate(self._transport.generate(transport_request))
                response = ModelResponse.model_validate_json(returned.canonical_json())
            except ValueError:
                response = failed_response(
                    request,
                    "invalid_response",
                    "Transport returned an invalid model contract",
                    dispatched=True,
                )
            if (
                response.provider != request.provider
                or response.model != request.model
                or (
                    request.model_revision is not None
                    and response.model_revision != request.model_revision
                )
            ):
                invalid = failed_response(
                    request,
                    "invalid_response",
                    "Transport response route/revision does not match request",
                    dispatched=True,
                    usage=response.usage,
                )
                response = invalid.model_copy(
                    update={
                        "model_revision": response.model_revision,
                        "provider_request_id": response.provider_request_id,
                        "provider_usage": response.provider_usage,
                    }
                )
        exchange = ModelExchange(
            context=context, occurrence=occurrence, request=request, response=response
        )
        with self._lock:
            self._records.append(exchange.model_dump_json())
        return ModelResponse.model_validate_json(response.model_dump_json())
