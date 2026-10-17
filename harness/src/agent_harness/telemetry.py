"""One bounded, private-by-construction trace per evaluation, without global SDK state."""

import hashlib
import hmac
import json
import secrets
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal, Protocol, TypeVar

from agent_harness.contracts import (
    ModelGateway,
    ModelRequest,
    ModelResponse,
    RunContext,
    WireContract,
)
from agent_harness.telemetry_contracts import TraceHealth

if TYPE_CHECKING:
    from agent_harness.evaluation import EvalCase

Kind = Literal["run", "agent", "node", "model", "tool", "policy", "scorer"]
T = TypeVar("T")


@dataclass(frozen=True)
class SpanRecord:
    trace_id: str
    span_id: str
    parent_id: str | None
    kind: Kind
    start_ns: int
    end_ns: int
    failed: bool
    # Only the module's fixed projections populate these fields.
    attributes: dict[str, str | int | bool] = field(repr=False)


class TraceExporter(Protocol):
    def export(self, spans: tuple[SpanRecord, ...]) -> bool: ...
    def flush(self) -> bool: ...
    def shutdown(self) -> None: ...


class TraceSession:
    """Single evaluation owner. Explicit node/tool/policy hooks never capture arguments."""

    def __init__(self, exporter: TraceExporter, key: bytes, *, max_spans: int = 256) -> None:
        if len(key) < 32 or not 2 <= max_spans <= 4096:
            raise ValueError("telemetry requires a private 32-byte key and bounded capacity")
        self._exporter = exporter
        self._key = key
        self._max = max_spans
        self.trace_id = secrets.token_hex(16)
        self._parent: ContextVar[str | None] = ContextVar("trace_parent", default=None)
        self._lock = threading.RLock()
        self._spans: list[SpanRecord] = []
        self._started = False
        self._closed = False
        self._active = 0
        self._admitted = 0
        self._dropped = 0
        self._root_id: str | None = None
        self.health: TraceHealth | None = None

    def reference(self, domain: str, value: str) -> str:
        """Domain separation prevents linking unrelated identity classes; key never exports."""
        return hmac.new(self._key, (domain + "\0" + value).encode(), hashlib.sha256).hexdigest()

    def begin(self, context: RunContext, case: "EvalCase") -> dict[str, str | int | bool]:
        with self._lock:
            if self._started or self._closed:
                raise ValueError("trace session is single-use")
            self._started = True
        attrs: dict[str, str | int | bool] = {"mode": context.mode, "source_kind": case.source_kind}
        for name in ("run_id", "tenant_id", "agent_id", "case_id", "trial_id", "business_event_id"):
            attrs[name] = self.reference(name, getattr(context, name))
        for name in ("code_revision", "candidate", "data_snapshot", "policy", "environment_lock"):
            attrs["version_" + name] = self.reference(
                "version_" + name, getattr(context.versions, name)
            )
        for name in ("source_version", "scorer_version", "snapshot_ref"):
            attrs[name] = self.reference(name, getattr(case, name))
        attrs["input_ref"] = self.reference("input", case.input.canonical_json())
        attrs["source_refs"] = json.dumps(
            [self.reference("source", item.reference) for item in case.input.observations[:64]]
        )
        attrs["source_count"] = len(case.input.observations)
        return attrs

    @contextmanager
    def _span(
        self, kind: Kind, attrs: dict[str, str | int | bool]
    ) -> Iterator[dict[str, str | int | bool]]:
        with self._lock:
            if not self._started or self._closed:
                raise ValueError("trace session is not active")
            admitted = self._admitted < self._max
            if admitted:
                self._admitted += 1
            else:
                self._dropped += 1
            self._active += 1
        span_id = secrets.token_hex(8)
        with self._lock:
            parent = self._parent.get() or self._root_id
            if kind == "run":
                self._root_id = span_id
        token = self._parent.set(span_id if admitted else parent)
        start = time.time_ns()
        failed = False
        try:
            yield attrs
        except BaseException:
            failed = True
            raise
        finally:
            self._parent.reset(token)
            with self._lock:
                if admitted:
                    self._spans.append(
                        SpanRecord(
                            self.trace_id,
                            span_id,
                            parent,
                            kind,
                            start,
                            max(start, time.time_ns()),
                            failed,
                            dict(attrs),
                        )
                    )
                self._active -= 1

    def invoke(
        self, kind: Literal["node", "tool", "policy"], name: str, call: Callable[[], T]
    ) -> T:
        # Runtime validation matters even when callers ignore Literal type annotations.
        if kind not in ("node", "tool", "policy"):
            raise ValueError("unsupported observation kind")
        with self._span(kind, {"operation_ref": self.reference("operation", name)}) as attrs:
            result = call()
            if isinstance(result, str):
                attrs["result_ref"] = self.reference("result", result)
            elif isinstance(result, WireContract):
                attrs["result_ref"] = self.reference("result", result.canonical_json())
            return result

    def finish(self) -> TraceHealth:
        """All three lifecycle steps run even after failures; never emit exception text."""
        with self._lock:
            if self.health is not None:
                return self.health
            if self._active:
                raise ValueError("cannot finish active trace")
            self._closed = True
            export: Literal["accepted", "failed", "empty"] = "empty"
            flush: Literal["ok", "failed"] = "failed"
            cleanup: Literal["ok", "failed"] = "failed"
            try:
                if self._spans:
                    export = (
                        "accepted"
                        if self._exporter.export(tuple(self._spans)) is True
                        else "failed"
                    )
            except Exception:
                export = "failed"
            try:
                flush = "ok" if self._exporter.flush() is True else "failed"
            except Exception:
                pass
            try:
                self._exporter.shutdown()
                cleanup = "ok"
            except Exception:
                pass
            self.health = TraceHealth(
                trace_id=self.trace_id,
                spans=len(self._spans),
                dropped=self._dropped,
                export=export,
                flush=flush,
                cleanup=cleanup,
            )
            return self.health


class TracedGateway:
    def __init__(self, trace: TraceSession, delegate: ModelGateway) -> None:
        self._trace = trace
        self._delegate = delegate

    def generate(self, context: RunContext, request: ModelRequest) -> ModelResponse:
        trace = self._trace
        attrs: dict[str, str | int | bool] = {
            "model_ref": trace.reference("model", request.model),
            "provider_ref": trace.reference("provider", request.provider),
            "request_ref": trace.reference("request", request.canonical_json()),
            "messages": len(request.messages),
            "tools": len(request.tools),
            "structured": request.output_schema is not None,
        }
        with trace._span("model", attrs):
            response = ModelResponse.model_validate_json(
                self._delegate.generate(context, request).canonical_json()
            )
            attrs["response_ref"] = trace.reference("response", response.canonical_json())
            attrs["model_failed"] = response.failure is not None
            attrs["model_calls"] = response.usage.model_calls
            for name in ("input_tokens", "output_tokens"):
                value = getattr(response.usage, name)
                if value is not None:
                    attrs[name] = value
            return response
