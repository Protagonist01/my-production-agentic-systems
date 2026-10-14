"""H1 invented-data compatibility probes; this is not the H2 production gateway."""

import argparse
import json
import os
import sys
from collections.abc import Callable
from contextlib import nullcontext
from importlib.metadata import version
from pathlib import Path
from typing import Any, Literal, TypedDict

import httpx
from google import genai
from google.genai import errors, types
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, ConfigDict
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage, ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

MODEL = "gemini-3.5-flash-lite"
ENDPOINT = "https://generativelanguage.googleapis.com"
STRUCTURED_PROMPT = 'Return only JSON with case_id="invented-h1" and answer equal to 6 * 7.'
TOOL_PROMPT = "Call lookup_order for invented-order-001. Do not invent another order."
PACKAGES = ("google-genai", "langgraph", "pydantic-ai-slim", "langfuse")


class SmokeOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    case_id: Literal["invented-h1"]
    answer: Literal[42]


class LookupArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    order_id: Literal["invented-order-001"]


def structured(client: genai.Client) -> tuple[SmokeOutput, types.GenerateContentResponse]:
    response = client.models.generate_content(
        model=MODEL,
        contents=STRUCTURED_PROMPT,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_json_schema=SmokeOutput.model_json_schema(),
            max_output_tokens=512,
            thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW),
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        ),
    )
    if not response.text:
        raise ValueError("Structured probe returned no text")
    return SmokeOutput.model_validate_json(response.text), response


def tool(client: genai.Client) -> tuple[LookupArguments, types.GenerateContentResponse]:
    response = client.models.generate_content(
        model=MODEL,
        contents=TOOL_PROMPT,
        config=types.GenerateContentConfig(
            tools=[
                types.Tool(
                    function_declarations=[
                        types.FunctionDeclaration(
                            name="lookup_order",
                            description="Read one invented order; this probe executes no tool.",
                            parameters_json_schema=LookupArguments.model_json_schema(),
                        )
                    ]
                )
            ],
            tool_config=types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(
                    mode=types.FunctionCallingConfigMode.ANY,
                    allowed_function_names=["lookup_order"],
                )
            ),
            max_output_tokens=512,
            thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW),
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        ),
    )
    calls = response.function_calls or []
    if len(calls) != 1 or calls[0].name != "lookup_order":
        raise ValueError("Tool probe requires exactly one allowed function call")
    return LookupArguments.model_validate(calls[0].args), response


def response_evidence(response: types.GenerateContentResponse) -> dict[str, Any]:
    usage = response.usage_metadata
    if usage is None or usage.prompt_token_count is None or usage.candidates_token_count is None:
        raise ValueError("Provider response omitted required token accounting")
    return {
        "reported_model_version": response.model_version,
        "response_id": response.response_id,
        "input_tokens": usage.prompt_token_count,
        "output_tokens": usage.candidates_token_count,
        "thinking_tokens": usage.thoughts_token_count,
        "cost": None,
        "billing_evidence": "user-confirmed free project; not independently exposed by response",
    }


class GraphState(TypedDict, total=False):
    output: dict[str, Any]


def framework_check(generate: Callable[[], SmokeOutput]) -> dict[str, Any]:
    """A graph node accepts a callable; Pydantic AI accepts a custom Model boundary."""
    os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

    def graph_node(state: GraphState) -> GraphState:
        return {"output": generate().model_dump()}

    graph = StateGraph(GraphState)
    graph.add_node("typed_probe", graph_node)
    graph.add_edge(START, "typed_probe")
    graph.add_edge("typed_probe", END)
    graph_output = SmokeOutput.model_validate(graph.compile().invoke({})["output"])

    def local_model(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        if len(info.output_tools) != 1:
            raise ValueError("Expected one typed Pydantic AI output tool")
        return ModelResponse(
            parts=[ToolCallPart(info.output_tools[0].name, graph_output.model_dump())]
        )

    agent = Agent(FunctionModel(local_model), output_type=SmokeOutput, retries=0)
    result = agent.run_sync("Return the invented H1 result")
    return {"langgraph": graph_output.model_dump(), "pydantic_ai": result.output.model_dump()}


def offline_check() -> dict[str, Any]:
    """Actual pinned SDK serialization/parsing over a mock HTTP transport, never live."""
    requests: list[dict[str, Any]] = []

    def respond(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        requests.append(body)
        part: dict[str, Any] = {"text": '{"case_id":"invented-h1","answer":42}'}
        if body.get("tools"):
            part = {
                "functionCall": {
                    "name": "lookup_order",
                    "args": {"order_id": "invented-order-001"},
                }
            }
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {"content": {"role": "model", "parts": [part]}, "finishReason": "STOP"}
                ],
                "modelVersion": "invented-mock-version",
                "usageMetadata": {"promptTokenCount": 12, "candidatesTokenCount": 8},
            },
        )

    with genai.Client(
        vertexai=False,
        api_key="invented-offline-key",
        http_options=types.HttpOptions(
            base_url=ENDPOINT,
            api_version="v1beta",
            timeout=30_000,
            client_args={"transport": httpx.MockTransport(respond), "trust_env": False},
            retry_options=types.HttpRetryOptions(attempts=1),
        ),
    ) as client:
        output, _ = structured(client)
        arguments, _ = tool(client)
    return {
        "mode": "offline_mock",
        "sdk_requests": len(requests),
        "structured": output.model_dump(),
        "tool_arguments": arguments.model_dump(),
        "frameworks": framework_check(lambda: output),
        "versions": {name: version(name) for name in PACKAGES},
        "provider_access_verified": False,
    }


def local_environment(
    root: Path,
    names: tuple[str, ...] = ("GEMINI_API_KEY", "GEMINI_FREE_TIER_CONFIRMED"),
) -> dict[str, str]:
    """Read whitelisted values as data. Never execute dotenv text or log a key."""
    values = {name: os.environ.get(name, "") for name in names}
    path = root / ".env.local"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            name, separator, value = line.partition("=")
            if separator and name.strip() in values and not values[name.strip()]:
                values[name.strip()] = value.strip().strip('"').strip("'")
    return values


def live_check(root: Path, trace_client: Any = None) -> dict[str, Any]:
    values = local_environment(root)
    if not values["GEMINI_API_KEY"] or values["GEMINI_FREE_TIER_CONFIRMED"].lower() != "true":
        raise ValueError("Set GEMINI_API_KEY and confirm a Free project in ignored .env.local")
    with genai.Client(
        vertexai=False,
        api_key=values["GEMINI_API_KEY"],
        http_options=types.HttpOptions(
            base_url=ENDPOINT,
            api_version="v1beta",
            timeout=30_000,
            retry_options=types.HttpRetryOptions(attempts=1),
        ),
    ) as client:
        print("Gemini structured probe (one request)", file=sys.stderr, flush=True)
        observation = (
            trace_client.start_as_current_observation(
                as_type="generation",
                name="gemini-structured",
                model=MODEL,
                input=STRUCTURED_PROMPT,
                model_parameters={"max_output_tokens": 512, "thinking_level": "LOW"},
                metadata={"output_schema": SmokeOutput.model_json_schema()},
            )
            if trace_client is not None
            else nullcontext(None)
        )
        with observation as generation:
            output, structured_response = structured(client)
            if generation is not None:
                evidence = response_evidence(structured_response)
                generation.update(
                    output=output.model_dump(),
                    usage_details={
                        "input": evidence["input_tokens"],
                        "output": evidence["output_tokens"],
                    },
                    metadata={
                        "mode": "live_smoke",
                        "reported_model_version": evidence["reported_model_version"],
                        "thinking_tokens": evidence["thinking_tokens"],
                        "response_id": evidence["response_id"],
                    },
                )
        print(
            "Structured response validated; Gemini tool probe (one request)",
            file=sys.stderr,
            flush=True,
        )
        observation = (
            trace_client.start_as_current_observation(
                as_type="generation",
                name="gemini-tool-proposal",
                model=MODEL,
                input=TOOL_PROMPT,
                model_parameters={"max_output_tokens": 512, "thinking_level": "LOW"},
                metadata={
                    "tool_schema": LookupArguments.model_json_schema(),
                    "allowed_function": "lookup_order",
                    "automatic_function_execution": False,
                },
            )
            if trace_client is not None
            else nullcontext(None)
        )
        with observation as generation:
            arguments, tool_response = tool(client)
            if generation is not None:
                evidence = response_evidence(tool_response)
                generation.update(
                    output=arguments.model_dump(),
                    usage_details={
                        "input": evidence["input_tokens"],
                        "output": evidence["output_tokens"],
                    },
                    metadata={
                        "mode": "live_smoke",
                        "tool_executed": False,
                        "reported_model_version": evidence["reported_model_version"],
                        "thinking_tokens": evidence["thinking_tokens"],
                        "response_id": evidence["response_id"],
                    },
                )
    return {
        "mode": "live_smoke",
        "requested_model": MODEL,
        "endpoint": ENDPOINT,
        "max_requests": 2,
        "structured": output.model_dump(),
        "tool_arguments": arguments.model_dump(),
        "structured_usage": response_evidence(structured_response),
        "tool_usage": response_evidence(tool_response),
        "versions": {name: version(name) for name in PACKAGES},
        "quality_evaluation": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["offline", "live"])
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = offline_check() if args.mode == "offline" else live_check(args.root)
        print(json.dumps(result, indent=2))
        return 0
    except errors.APIError as error:
        # Provider exception text can contain request details. Emit status only.
        print(f"Gemini smoke failed: HTTP {error.code}; no retry/fallback", file=sys.stderr)
        return 1
    except (ValueError, OSError, httpx.HTTPError):
        print("Integration smoke failed; check configuration/validated response", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
