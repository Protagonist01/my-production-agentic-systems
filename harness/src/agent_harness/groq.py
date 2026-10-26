"""Groq text/strict-schema HTTP adapter. No ambient key, retries, redirects or tools."""

import json
import math
from decimal import Decimal
from typing import Annotated, Any, Literal, cast

import httpx
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError
from pydantic import BaseModel, ConfigDict, Field, JsonValue
from referencing import Registry
from referencing.exceptions import Unresolvable

from agent_harness.contracts import FailureCode, ModelMessage, ModelRequest, ModelResponse, Usage
from agent_harness.controls import ReservationQuote
from agent_harness.gateway import failed_response

PROVIDER = "groq"
ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "openai/gpt-oss-120b"
MAX_RESPONSE_BYTES = 1_000_000


class GroqFreeAdmission:
    def __init__(self, *, free_tier_confirmed: bool) -> None:
        if not free_tier_confirmed:
            raise ValueError("billing-disabled Free account attestation required")

    def quote(self, request: ModelRequest) -> ReservationQuote:
        request_payload(request)
        return ReservationQuote(
            version="groq-gpt-oss-120b-free-ceiling-2026-10-26",
            max_tokens=131_072 + 65_536,
            max_cost=Decimal(0),
            currency="USD",
            evidence_ref="https://console.groq.com/docs/model/openai/gpt-oss-120b",
        )


class Parameters(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)
    max_completion_tokens: Annotated[int, Field(gt=0, le=2048)] = 1024
    temperature: Annotated[float, Field(ge=0, le=2)] = 0.0
    reasoning_effort: Literal["low"] = "low"
    seed: int | None = None


def json_value(raw: str) -> Any:
    def constant(value: str) -> None:
        raise ValueError("non-finite JSON rejected")

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    return json.loads(raw, parse_constant=constant, object_pairs_hook=pairs)


def validator(schema: dict[str, JsonValue]) -> Draft202012Validator:
    def closed(value: JsonValue) -> None:
        if isinstance(value, list):
            for child in value:
                closed(child)
        elif isinstance(value, dict):
            for key, child in value.items():
                if key in ("$ref", "$dynamicRef") and (
                    not isinstance(child, str) or not child.startswith("#")
                ):
                    raise ValueError("external schema references rejected")
                if key == "$schema" and child != "https://json-schema.org/draft/2020-12/schema":
                    raise ValueError("unsupported schema dialect")
                closed(child)
            if value.get("type") == "object":
                properties, required = value.get("properties"), value.get("required")
                if (
                    value.get("additionalProperties") is not False
                    or not isinstance(properties, dict)
                    or not isinstance(required, list)
                    or len(required) != len(properties)
                    or set(required) != set(properties)
                ):
                    raise ValueError("strict objects require all properties and no extras")

    closed(schema)
    if schema.get("type") != "object":
        raise ValueError("strict output requires an object root")
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, registry=Registry())


def request_payload(request: ModelRequest) -> dict[str, Any]:
    request = ModelRequest.model_validate_json(request.canonical_json())
    if (request.provider, request.endpoint, request.model) != (PROVIDER, ENDPOINT, MODEL):
        raise ValueError("unapproved Groq route")
    if request.model_revision is not None or request.tools or request.tool_choice is not None:
        raise ValueError("revision pinning/tools unsupported by initial Groq route")
    messages = []
    for message in request.messages:
        if message.role == "tool" or message.tool_calls or message.parts:
            raise ValueError("tool history/provider parts unsupported")
        messages.append({"role": message.role, "content": message.content})
    payload = dict(
        model=MODEL,
        messages=messages,
        stream=False,
        n=1,
        **Parameters.model_validate(request.parameters).model_dump(exclude_none=True),
    )
    if request.output_schema is not None:
        validator(request.output_schema)
        payload["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": "agent_output",
                "strict": True,
                "schema": request.output_schema,
            },
        }
    if len(json.dumps(payload).encode()) > 32_768:
        raise ValueError("Groq request exceeds reviewed local size bound")
    return payload


def usage(body: dict[str, Any]) -> tuple[Usage, dict[str, int | None]]:
    raw = body.get("usage")
    if raw is not None and not isinstance(raw, dict):
        raise ValueError("invalid Groq usage")
    counts = {
        name: (raw or {}).get(name)
        for name in ("prompt_tokens", "completion_tokens", "total_tokens")
    }
    if any(v is not None and (type(v) is not int or v < 0) for v in counts.values()):
        raise ValueError("invalid token counts")
    prompt, completion, total = (counts[n] for n in counts)
    if (
        prompt is not None
        and completion is not None
        and total is not None
        and total != prompt + completion
    ):
        raise ValueError("inconsistent token totals")
    return Usage(
        model_calls=1,
        input_tokens=prompt,
        output_tokens=completion,
        cost=None,
        cost_currency=None,
    ), counts


def parse_response(request: ModelRequest, body: dict[str, Any]) -> ModelResponse:
    observed, counts = usage(body)
    try:
        choices = body.get("choices")
        if body.get("model") != request.model or not isinstance(choices, list) or len(choices) != 1:
            raise ValueError("missing/ambiguous/different-model result")
        choice = choices[0]
        if not isinstance(choice, dict) or choice.get("finish_reason") != "stop":
            raise ValueError("truncated or incomplete result")
        message = choice.get("message")
        if (
            not isinstance(message, dict)
            or message.get("role") != "assistant"
            or not isinstance(message.get("content"), str)
            or message.get("tool_calls")
            or message.get("function_call")
            or message.get("refusal")
        ):
            raise ValueError("unsupported Groq output")
        text = cast(str, message["content"])
        if request.output_schema is not None:
            validator(request.output_schema).validate(json_value(text))
        result = ModelResponse(
            provider=PROVIDER,
            model=request.model,
            provider_request_id=body.get("id"),
            output=ModelMessage(role="assistant", content=text),
            finish_reason="stop",
            usage=observed,
            provider_usage=counts,
        )
    except (ValueError, ValidationError, SchemaError, Unresolvable, TypeError):
        result = failed_response(
            request,
            "invalid_response",
            "Groq output failed local validation",
            dispatched=True,
            usage=observed,
        ).model_copy(update={"provider_usage": counts})
    return result


class GroqTransport:
    def __init__(
        self,
        api_key: str,
        *,
        free_tier_confirmed: bool,
        http_transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not api_key or not free_tier_confirmed:
            raise ValueError("explicit key and billing-disabled Free account attestation required")
        self._key, self._transport = api_key, http_transport

    def generate(self, request: ModelRequest, *, timeout_seconds: float = 30.0) -> ModelResponse:
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            return failed_response(
                request, "timeout", "No Groq attempt time remaining", dispatched=False
            )
        try:
            payload = request_payload(request)
        except (ValueError, SchemaError, TypeError, Unresolvable):
            return failed_response(
                request, "invalid_response", "Unsupported Groq request", dispatched=False
            )
        try:
            with httpx.Client(
                transport=self._transport,
                trust_env=False,
                follow_redirects=False,
                timeout=min(timeout_seconds, 60.0),
            ) as client:
                with client.stream(
                    "POST", ENDPOINT, headers={"Authorization": "Bearer " + self._key}, json=payload
                ) as response:
                    code = response.status_code
                    if code != 200:
                        failure: FailureCode = (
                            "rate_limited"
                            if code == 429
                            else (
                                "permission_denied"
                                if code in (401, 403)
                                else (
                                    "timeout"
                                    if code in (408, 504)
                                    else ("unavailable" if code >= 500 else "invalid_response")
                                )
                            )
                        )
                        return failed_response(
                            request,
                            failure,
                            "Groq HTTP request failed",
                            dispatched=True,
                            retryable=code in (408, 429, 504) or code >= 500,
                        )
                    raw = bytearray()
                    for chunk in response.iter_bytes(chunk_size=65_536):
                        raw.extend(chunk)
                        if len(raw) > MAX_RESPONSE_BYTES:
                            raise ValueError("Groq response exceeds size bound")
            body = json_value(raw.decode("utf-8"))
            if not isinstance(body, dict):
                raise ValueError("Groq response must be an object")
            return parse_response(request, body)
        except httpx.TimeoutException:
            return failed_response(
                request, "timeout", "Groq request timed out", dispatched=True, retryable=True
            )
        except httpx.HTTPError:
            return failed_response(
                request, "unavailable", "Groq transport failed", dispatched=True, retryable=True
            )
        except (ValueError, UnicodeError, TypeError):
            return failed_response(
                request, "invalid_response", "Invalid Groq wire response", dispatched=True
            )
