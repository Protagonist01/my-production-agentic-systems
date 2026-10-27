"""Pinned synchronous Gemini Developer API text/JSON/function adapter."""

import base64
import json
import math
from typing import Annotated, Any, Literal
from uuid import uuid4

import httpx
from google import genai
from google.genai import errors, types
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError
from pydantic import BaseModel, ConfigDict, Field, JsonValue
from referencing import Registry
from referencing.exceptions import Unresolvable

from agent_harness.contracts import (
    ModelMessage,
    ModelPart,
    ModelRequest,
    ModelResponse,
    ToolCall,
    Usage,
)
from agent_harness.gateway import failed_response

PROVIDER = "google-gemini-developer-api"
ENDPOINT = "https://generativelanguage.googleapis.com"
MODEL = "gemini-3.5-flash-lite"


class GenerationParameters(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)
    temperature: Annotated[float, Field(ge=0, le=2)] | None = None
    top_p: Annotated[float, Field(ge=0, le=1)] | None = None
    top_k: Annotated[int, Field(gt=0)] | None = None
    max_output_tokens: Annotated[int, Field(gt=0, le=512)] = 512
    stop_sequences: list[str] | None = None
    seed: int | None = None
    thinking_level: Literal["LOW"] = "LOW"


class FlashDevelopmentParameters(GenerationParameters):
    # Only the separately opted-in Flash route permits the reviewed development limit.
    max_output_tokens: Annotated[int, Field(gt=0, le=2048)] = 512


def json_value(text: str) -> JsonValue:
    def reject_constant(value: str) -> None:
        raise ValueError("Non-finite JSON is unsupported")

    def unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON keys are unsupported")
            result[key] = value
        return result

    value: JsonValue = json.loads(
        text, parse_constant=reject_constant, object_pairs_hook=unique_pairs
    )
    json.dumps(value, allow_nan=False)
    return value


def validate_http_response(response: httpx.Response) -> None:
    """Reject malformed accounting before the SDK's permissive numeric parsing."""
    if not 200 <= response.status_code < 300:
        return
    body = json_value(response.read().decode("utf-8"))
    if not isinstance(body, dict):
        raise ValueError("Provider wire response must be an object")
    usage = body.get("usageMetadata")
    if usage is not None:
        if not isinstance(usage, dict):
            raise ValueError("Invalid usage metadata")
        for name in (
            "promptTokenCount",
            "candidatesTokenCount",
            "thoughtsTokenCount",
            "cachedContentTokenCount",
            "totalTokenCount",
        ):
            count = usage.get(name)
            if count is not None and (type(count) is not int or count < 0):
                raise ValueError("Token counts must be nonnegative integers")


def schema_validator(schema: dict[str, JsonValue]) -> Draft202012Validator:
    # References can resolve within the supplied document, never through HTTP/files.
    def check_refs(value: JsonValue) -> None:
        if isinstance(value, dict):
            if (
                "$schema" in value
                and value["$schema"] != "https://json-schema.org/draft/2020-12/schema"
            ):
                raise ValueError("Only JSON Schema 2020-12 is supported")
            for key, item in value.items():
                if key in ("$ref", "$dynamicRef") and (
                    not isinstance(item, str) or not item.startswith("#")
                ):
                    raise ValueError("External schema references are unsupported")
                check_refs(item)
        elif isinstance(value, list):
            for item in value:
                check_refs(item)

    check_refs(schema)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, registry=Registry())


def sdk_part(part: ModelPart) -> types.Part:
    call = part.tool_call
    return types.Part(
        text=part.text,
        function_call=None
        if call is None
        else types.FunctionCall(id=call.provider_call_id, name=call.name, args=call.arguments),
        thought=part.thought or None,
        thought_signature=None
        if part.thought_signature is None
        else base64.b64decode(part.thought_signature),
    )


def request_payload(
    request: ModelRequest,
    *,
    flash_comparison: bool = False,
) -> tuple[list[types.Content], types.GenerateContentConfig]:
    allowed = (MODEL, "gemini-3.8-flash") if flash_comparison else (MODEL,)
    if (request.provider, request.endpoint) != (PROVIDER, ENDPOINT) or request.model not in allowed:
        raise ValueError("Only the explicitly selected Gemini route is supported")
    parameter_contract = (
        FlashDevelopmentParameters
        if flash_comparison and request.model == "gemini-3.8-flash"
        else GenerationParameters
    )
    parameters = parameter_contract.model_validate(request.parameters).model_dump(exclude_none=True)
    level = parameters.pop("thinking_level")
    # Omitted parameters are not invented in the canonical request. SDK defaults
    # are part of this pinned adapter version; callers must pin explicit settings.
    config = types.GenerateContentConfig.model_validate(parameters)
    config.thinking_config = types.ThinkingConfig(thinking_level=types.ThinkingLevel(level))
    config.automatic_function_calling = types.AutomaticFunctionCallingConfig(disable=True)
    config.automatic_continuation = False
    config.candidate_count = 1
    tool_names = [tool.name for tool in request.tools]
    if len(set(tool_names)) != len(tool_names):
        raise ValueError("Duplicate function declarations")
    for tool in request.tools:
        schema_validator(tool.parameters)
    if request.tools:
        config.tools = [
            types.Tool(
                function_declarations=[
                    types.FunctionDeclaration(
                        name=tool.name,
                        description=tool.description,
                        parameters_json_schema=tool.parameters,
                    )
                    for tool in request.tools
                ]
            )
        ]
    choice = request.tool_choice
    if choice is not None:
        if not isinstance(choice, str) or choice not in ("auto", "none", "required", *tool_names):
            raise ValueError("Unsupported function choice")
        if not request.tools:
            raise ValueError("Function choice needs declarations")
        mode = {"auto": "AUTO", "none": "NONE", "required": "ANY"}.get(choice, "ANY")
        config.tool_config = types.ToolConfig(
            function_calling_config=types.FunctionCallingConfig(
                mode=types.FunctionCallingConfigMode(mode),
                allowed_function_names=[choice] if choice in tool_names else None,
            )
        )
    if request.output_schema is not None:
        schema_validator(request.output_schema)
        config.response_mime_type = "application/json"
        config.response_json_schema = request.output_schema
    contents: list[types.Content] = []
    instructions: list[types.Part] = []
    pending: dict[str, ToolCall] = {}
    used_ids: set[str] = set()
    for message in request.messages:
        if message.role == "system":
            if contents:
                raise ValueError("System instructions must precede conversation history")
            instructions.append(types.Part(text=message.content))
            continue
        if message.role == "developer":
            raise ValueError("Developer messages have no faithful Gemini role mapping")
        if pending and message.role != "tool":
            raise ValueError("Pending function calls require their results before another turn")
        if message.role == "tool":
            call = pending.pop(message.tool_call_id or "", None)
            if call is None or call.name != message.tool_name:
                raise ValueError("Function result is unmatched, duplicated or misnamed")
            result = json_value(message.content or "")
            if not isinstance(result, dict):
                raise ValueError("Function result must be a JSON object")
            part = types.Part(
                function_response=types.FunctionResponse(
                    id=call.provider_call_id, name=call.name, response=result
                )
            )
            if (
                contents
                and contents[-1].role == "user"
                and contents[-1].parts
                and contents[-1].parts[0].function_response
            ):
                contents[-1].parts.append(part)
            else:
                contents.append(types.Content(role="user", parts=[part]))
            continue
        parts = [sdk_part(part) for part in message.parts] if message.parts else []
        if message.tool_calls:
            if not message.parts:
                raise ValueError("Gemini function history must retain its original ordered parts")
            for call in message.tool_calls:
                if call.call_id in used_ids:
                    raise ValueError("Function call IDs must be unique within history")
                used_ids.add(call.call_id)
                pending[call.call_id] = call
        if not parts:
            parts = [types.Part(text=message.content)]
        contents.append(
            types.Content(role="model" if message.role == "assistant" else "user", parts=parts)
        )
    if not contents or pending:
        raise ValueError("Conversation needs content and complete function results")
    if instructions:
        config.system_instruction = types.Content(parts=instructions)
    return contents, config


def response_usage(response: types.GenerateContentResponse) -> tuple[Usage, dict[str, int | None]]:
    usage = response.usage_metadata
    counts = {
        "prompt_tokens": None if usage is None else usage.prompt_token_count,
        "candidate_tokens": None if usage is None else usage.candidates_token_count,
        "thinking_tokens": None if usage is None else usage.thoughts_token_count,
        "cached_input_tokens": None if usage is None else usage.cached_content_token_count,
        "total_tokens": None if usage is None else usage.total_token_count,
    }
    if any(
        value is not None and (type(value) is not int or value < 0) for value in counts.values()
    ):
        raise ValueError("Invalid provider usage")
    visible, thinking = counts["candidate_tokens"], counts["thinking_tokens"]
    output = None if visible is None or thinking is None else visible + thinking
    # The provider total includes prompt, tool-use prompt, thoughts and candidates.
    # Equality leaves no residual tokens; absent thoughts alone must never imply zero.
    if (
        output is None
        and visible is not None
        and counts["prompt_tokens"] is not None
        and counts["total_tokens"] == counts["prompt_tokens"] + visible
    ):
        output = visible
    return Usage(
        model_calls=1,
        input_tokens=counts["prompt_tokens"],
        output_tokens=output,
        cost=None,
        cost_currency=None,
    ), counts


def parse_response(request: ModelRequest, response: types.GenerateContentResponse) -> ModelResponse:
    usage, counts = response_usage(response)
    candidates = response.candidates or []
    if len(candidates) != 1 or candidates[0].finish_reason != types.FinishReason.STOP:
        return failed_response(
            request,
            "invalid_response",
            "Missing, blocked, truncated or ambiguous candidate",
            dispatched=True,
            usage=usage,
        )
    candidate = candidates[0]
    if (
        candidate.content is None
        or candidate.content.role != "model"
        or not candidate.content.parts
    ):
        raise ValueError("Missing model content")
    retained: list[ModelPart] = []
    schemas = {tool.name: tool.parameters for tool in request.tools}
    for index, part in enumerate(candidate.content.parts):
        fields = part.model_dump(exclude_none=True)
        if set(fields) - {"text", "function_call", "thought", "thought_signature"}:
            raise ValueError("Unsupported output modality")
        call = part.function_call
        public_call = None
        if call is not None:
            if call.partial_args is not None or call.will_continue is not None:
                raise ValueError("Streaming/continuing function calls are unsupported")
            if call.name not in schemas or call.args is None:
                raise ValueError("Undeclared function or missing arguments")
            if request.tool_choice == "none" or (
                request.tool_choice in schemas and call.name != request.tool_choice
            ):
                raise ValueError("Function proposal violates requested choice")
            schema_validator(schemas[call.name]).validate(call.args)
            public_call = ToolCall(
                call_id=call.id or f"gemini-{uuid4().hex}-{index}",
                provider_call_id=call.id,
                name=call.name,
                arguments=call.args,
            )
        retained.append(
            ModelPart(
                text=part.text,
                tool_call=public_call,
                thought=bool(part.thought),
                thought_signature=None
                if part.thought_signature is None
                else base64.b64encode(part.thought_signature).decode("ascii"),
            )
        )
    texts = [part.text for part in retained if part.text is not None and not part.thought]
    calls = tuple(part.tool_call for part in retained if part.tool_call is not None)
    if len({call.call_id for call in calls}) != len(calls):
        raise ValueError("Duplicate function call IDs")
    text = "".join(texts) if texts else None
    if request.tool_choice in ("required", *schemas) and not calls:
        raise ValueError("Required function proposal missing")
    if request.output_schema is not None and not calls:
        schema_validator(request.output_schema).validate(json_value(text or ""))
    return ModelResponse(
        provider=request.provider,
        model=request.model,
        model_revision=response.model_version,
        provider_request_id=response.response_id,
        finish_reason="STOP",
        output=ModelMessage(
            role="assistant", content=text, tool_calls=calls, parts=tuple(retained)
        ),
        usage=usage,
        provider_usage=counts,
    )


class GeminiTransport:
    _key: str
    _http_transport: httpx.BaseTransport | None
    _flash_comparison: bool
    _http_timeout_seconds: Literal[30, 90]

    def __init__(
        self,
        api_key: str,
        *,
        free_tier_confirmed: bool,
        http_transport: httpx.BaseTransport | None = None,
        flash_comparison: bool = False,
        http_timeout_seconds: Literal[30, 90] = 30,
    ) -> None:
        if not api_key or not free_tier_confirmed:
            raise ValueError("A key and explicit Free-project attestation are required")
        if type(http_timeout_seconds) is not int or http_timeout_seconds not in (30, 90):
            raise ValueError("unsupported HTTP timeout ceiling")
        self._key = api_key
        self._http_transport = http_transport
        self._flash_comparison = flash_comparison
        self._http_timeout_seconds = http_timeout_seconds

    def generate(self, request: ModelRequest, *, timeout_seconds: float = 30.0) -> ModelResponse:
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            return failed_response(
                request, "timeout", "No Gemini attempt time remaining", dispatched=False
            )
        try:
            if (
                self._http_timeout_seconds == 90
                and request.model != MODEL
                and (
                    not self._flash_comparison
                    or request.model != "gemini-3.8-flash"
                    or request.parameters
                    != {"temperature": 0.0, "max_output_tokens": 512, "thinking_level": "LOW"}
                )
            ):
                raise ValueError("long Flash window requires explicit model-only512 settings")
            contents, config = request_payload(request, flash_comparison=self._flash_comparison)
        except (ValueError, SchemaError, Unresolvable):
            return failed_response(
                request,
                "invalid_response",
                "Unsupported or invalid Gemini request",
                dispatched=False,
            )
        try:
            arguments: dict[str, Any] = {
                "trust_env": False,
                "follow_redirects": False,
                "event_hooks": {"response": [validate_http_response]},
            }
            if self._http_transport is not None:
                arguments["transport"] = self._http_transport
            with genai.Client(
                enterprise=False,
                vertexai=False,
                api_key=self._key,
                http_options=types.HttpOptions(
                    base_url=ENDPOINT,
                    api_version="v1beta",
                    timeout=max(
                        1, min(self._http_timeout_seconds * 1000, int(timeout_seconds * 1000))
                    ),
                    retry_options=types.HttpRetryOptions(attempts=1),
                    client_args=arguments,
                ),
            ) as client:
                response = client.models.generate_content(
                    model=request.model, contents=contents, config=config
                )
        except errors.APIError as error:
            if error.code == 429:
                return failed_response(
                    request, "rate_limited", "Gemini HTTP 429", dispatched=True, retryable=True
                )
            if error.code in (401, 403):
                return failed_response(
                    request,
                    "permission_denied",
                    "Gemini authentication/permission failure",
                    dispatched=True,
                )
            if error.code in (408, 504):
                return failed_response(
                    request, "timeout", "Gemini request timed out", dispatched=True, retryable=True
                )
            return failed_response(
                request,
                "unavailable" if error.code and error.code >= 500 else "invalid_response",
                "Gemini HTTP request failed",
                dispatched=True,
                retryable=bool(error.code and error.code >= 500),
            )
        except httpx.TimeoutException:
            return failed_response(
                request, "timeout", "Gemini request timed out", dispatched=True, retryable=True
            )
        except httpx.HTTPError:
            return failed_response(
                request, "unavailable", "Gemini transport failed", dispatched=True, retryable=True
            )
        except ValueError:
            return failed_response(
                request,
                "invalid_response",
                "Gemini returned an invalid wire response",
                dispatched=True,
            )
        try:
            result = parse_response(request, response)
        except (ValueError, ValidationError, SchemaError, Unresolvable):
            try:
                usage, counts = response_usage(response)
            except ValueError:
                usage, counts = None, {}
            result = failed_response(
                request,
                "invalid_response",
                "Gemini returned unsupported or invalid content",
                dispatched=True,
                usage=usage,
            )
            result = result.model_copy(update={"provider_usage": counts})
        # Retain safe provider evidence on invalid content as well as successful output.
        return result.model_copy(
            update={
                "model_revision": response.model_version,
                "provider_request_id": response.response_id,
            }
        )
