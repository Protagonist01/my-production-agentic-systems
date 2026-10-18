"""Explicit OTLP/HTTP Langfuse transport. No ambient attributes, retries or redirects."""

import base64
import json
import math
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable

from agent_harness.telemetry import SpanRecord

TYPES = {
    "run": "chain",
    "agent": "agent",
    "node": "span",
    "model": "generation",
    "tool": "tool",
    "policy": "guardrail",
    "scorer": "evaluator",
}


def encode(spans: tuple[SpanRecord, ...]) -> bytes:
    # Optional imports keep the base harness independent of telemetry packages.
    from opentelemetry.exporter.otlp.proto.common.trace_encoder import encode_spans
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import ReadableSpan
    from opentelemetry.trace import SpanContext, Status, StatusCode, TraceFlags

    def context(trace_id: str, span_id: str) -> SpanContext:
        return SpanContext(int(trace_id, 16), int(span_id, 16), False, TraceFlags(1))

    result = []
    for span in spans:
        inputs = {
            key: span.attributes[key]
            for key in (
                "mode",
                "source_kind",
                "input_ref",
                "source_count",
                "request_ref",
                "model_ref",
                "messages",
                "tools",
                "structured",
                "operation_ref",
            )
            if key in span.attributes
        }
        outputs: dict[str, str | int | bool] = {"failed": span.failed}
        outputs.update(
            {
                key: span.attributes[key]
                for key in (
                    "outcome",
                    "output_ref",
                    "response_ref",
                    "result_ref",
                    "model_failed",
                    "model_calls",
                    "input_tokens",
                    "output_tokens",
                    "scores",
                    "scorer_failed",
                )
                if key in span.attributes
            }
        )
        attrs: dict[str, str | int | bool] = {
            "langfuse.observation.type": TYPES[span.kind],
            "langfuse.environment": "harness",
            "langfuse.observation.input": json.dumps({"redacted": True, **inputs}),
            "langfuse.observation.output": json.dumps(outputs),
        }
        attrs.update(
            {
                "langfuse.observation.metadata." + key: value
                for key, value in span.attributes.items()
            }
        )
        if span.kind == "model":
            attrs["langfuse.observation.model.name"] = "model-" + str(span.attributes["model_ref"])
            attrs["langfuse.observation.usage_details"] = json.dumps(
                {
                    key.removesuffix("_tokens"): span.attributes[key]
                    for key in ("input_tokens", "output_tokens")
                    if key in span.attributes
                }
            )
        result.append(
            ReadableSpan(
                name="harness-" + span.kind,
                context=context(span.trace_id, span.span_id),
                parent=context(span.trace_id, span.parent_id) if span.parent_id else None,
                resource=Resource({"service.name": "production-agent-harness"}),
                attributes=attrs,
                start_time=span.start_ns,
                end_time=span.end_ns,
                status=Status(
                    StatusCode.ERROR
                    if (
                        span.failed
                        or span.attributes.get("model_failed")
                        or span.attributes.get("scorer_failed")
                        or span.attributes.get("outcome") == "failed"
                    )
                    else StatusCode.OK
                ),
            )
        )
    return bytes(encode_spans(result).SerializeToString())


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: object, **kwargs: object) -> None:
        return None


def accepted(body: bytes, content_type: str) -> bool:
    """Recognize OTLP responses and the tested Langfuse 4.50 queue acknowledgement."""
    if content_type.split(";", 1)[0].strip() == "application/json":
        value = json.loads(body)
        if not isinstance(value, dict):
            return False
        if not value:
            return True
        if set(value) == {"partialSuccess"}:
            partial = value["partialSuccess"]
            return (
                isinstance(partial, dict)
                and int(partial.get("rejectedSpans", 0)) == 0
                and not partial.get("errorMessage")
            )
        # This is enqueue acceptance, never a claim of durable storage. The probe
        # separately waits for observation read-back before declaring end-to-end success.
        return (
            isinstance(value.get("id"), str)
            and bool(value["id"])
            and isinstance(value.get("name"), str)
            and bool(value["name"])
            and isinstance(value.get("data"), dict)
            and isinstance(value.get("queueQualifiedName"), str)
            and not value.get("failedReason")
        )
    from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceResponse

    reply = ExportTraceServiceResponse.FromString(body)
    return not reply.partial_success.rejected_spans and not reply.partial_success.error_message


class LangfuseExporter:
    """Synchronous bounded batch, explicit credentials and socket timeout; no global provider."""

    def __init__(
        self,
        base_url: str,
        public_key: str,
        secret_key: str,
        *,
        timeout: float = 5,
        send: Callable[[bytes], bool] | None = None,
    ) -> None:
        parsed = urllib.parse.urlsplit(base_url)
        if (
            parsed.scheme not in ("http", "https")
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.path not in ("", "/")
            or parsed.query
            or parsed.fragment
            or (
                parsed.scheme == "http" and parsed.hostname not in ("localhost", "127.0.0.1", "::1")
            )
        ):
            raise ValueError("explicit HTTPS or loopback Langfuse origin required")
        if not public_key or not secret_key or not math.isfinite(timeout) or not 0 < timeout <= 30:
            raise ValueError("credentials and bounded timeout required")
        self._url = base_url.rstrip("/") + "/api/public/otel/v1/traces"
        self._auth = "Basic " + base64.b64encode((public_key + ":" + secret_key).encode()).decode()
        self._timeout = timeout
        self._closed = False
        self._send = send or self._post
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())

    def _post(self, payload: bytes) -> bool:
        request = urllib.request.Request(
            self._url,
            data=payload,
            method="POST",
            headers={
                "Authorization": self._auth,
                "Content-Type": "application/x-protobuf",
                "x-langfuse-ingestion-version": "4",
            },
        )
        try:
            with self._opener.open(request, timeout=self._timeout) as response:
                if response.status != 200:
                    return False
                body = response.read(65537)
                if len(body) > 65536:
                    return False
                return accepted(body, response.headers.get("Content-Type", ""))
        except Exception:
            # Neither response bodies, configured endpoints nor exception messages are diagnostics.
            return False

    def export(self, spans: tuple[SpanRecord, ...]) -> bool:
        return not self._closed and self._send(encode(spans))

    def flush(self) -> bool:
        return not self._closed  # export is synchronous; no queue or background threads

    def shutdown(self) -> None:
        self._closed = True
        self._auth = ""
