"""Explicit two-request, invented-data gateway acceptance probe; never run in CI."""

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict

from agent_harness.admission import GEMINI_TOKEN_CEILING, GeminiFreeAdmission
from agent_harness.contracts import ModelMessage, ModelRequest, ToolSchema
from agent_harness.controls import BoundedGateway, ExecutionPolicy, SharedControls
from agent_harness.gateway import ProviderGateway
from agent_harness.gemini import ENDPOINT, MODEL, PROVIDER
from agent_harness.integration_smoke import LookupArguments, local_environment
from agent_harness.isolated_transport import GeminiWorker, IsolatedTransport
from agent_harness.offline_example import example_context


class GatewayAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    case_id: Literal["invented-h2"]
    answer: Literal[42]


def live_probe(root: Path, code_revision: str) -> dict[str, Any]:
    values = local_environment(root)
    confirmed = values["GEMINI_FREE_TIER_CONFIRMED"].lower() == "true"
    admission = GeminiFreeAdmission(free_tier_confirmed=confirmed)
    attempts = ProviderGateway(IsolatedTransport(GeminiWorker(values["GEMINI_API_KEY"], confirmed)))
    controls = SharedControls()
    gateway = BoundedGateway(attempts, controls, admission, policy=ExecutionPolicy(max_attempts=1))
    now = datetime.now(UTC)
    context = example_context(
        code_revision, hashlib.sha256((root / "uv.lock").read_bytes()).hexdigest()
    )
    context = context.model_copy(
        update={
            "mode": "fresh_candidate",
            "run_id": "h4-smoke-" + uuid4().hex,
            "case_id": "invented-h2",
            "clock": now,
            "deadline": now + timedelta(seconds=90),
            "budget": context.budget.model_copy(
                update={"max_model_calls": 2, "max_tokens": 2 * GEMINI_TOKEN_CEILING}
            ),
            "versions": context.versions.model_copy(
                update={"candidate": "h4-controlled-compatibility-probe"}
            ),
        }
    )
    declaration = ToolSchema(
        name="lookup_order",
        description="Read one invented order",
        parameters=LookupArguments.model_json_schema(),
    )
    request = ModelRequest(
        provider=PROVIDER,
        endpoint=ENDPOINT,
        model=MODEL,
        messages=(
            ModelMessage(
                role="user",
                content=(
                    "Call lookup_order for invented-order-001. After its result, "
                    'return JSON with case_id="invented-h2" and the returned answer.'
                ),
            ),
        ),
        parameters={"temperature": 0, "max_output_tokens": 512, "thinking_level": "LOW"},
        tools=(declaration,),
        tool_choice="lookup_order",
    )
    print("H4 controlled gateway function proposal (one request)", file=sys.stderr, flush=True)
    proposal = gateway.generate(context, request)
    if (
        proposal.failure is not None
        or proposal.output is None
        or len(proposal.output.tool_calls) != 1
    ):
        code = "invalid_response" if proposal.failure is None else proposal.failure.code
        raise ValueError("H4 proposal failed: " + code)
    call = proposal.output.tool_calls[0]
    LookupArguments.model_validate(call.arguments)
    followup = request.model_copy(
        update={
            "messages": (
                *request.messages,
                proposal.output,
                ModelMessage(
                    role="tool",
                    tool_call_id=call.call_id,
                    tool_name=call.name,
                    content='{"answer":42}',
                ),
            ),
            "tool_choice": "none",
            "output_schema": GatewayAnswer.model_json_schema(),
        }
    )
    print(
        "H4 controlled gateway tool-result/JSON continuation (one request)",
        file=sys.stderr,
        flush=True,
    )
    response = gateway.generate(context, followup)
    if response.failure is not None or response.output is None:
        code = "invalid_response" if response.failure is None else response.failure.code
        raise ValueError("H4 continuation failed: " + code)
    answer = GatewayAnswer.model_validate_json(response.output.content or "")
    return {
        "mode": "live_gateway_compatibility",
        "run_id": context.run_id,
        "code_revision": code_revision,
        "lock_sha256": context.versions.environment_lock,
        "model": MODEL,
        "result": answer.model_dump(),
        "requests": len(attempts.exchanges),
        "occurrences": [exchange.occurrence for exchange in attempts.exchanges],
        "fingerprints": [exchange.request.fingerprint() for exchange in attempts.exchanges],
        "execution_policy": gateway.policy.model_dump(mode="json"),
        "budget_accounting": controls.snapshot(context.tenant_id, context.run_id).model_dump(
            mode="json"
        ),
        "opaque_signatures_preserved": sum(
            part.thought_signature is not None for part in proposal.output.parts
        ),
        "responses": [
            {
                "request_id": exchange.response.provider_request_id,
                "model_revision": exchange.response.model_revision,
                "usage": exchange.response.usage.model_dump(mode="json"),
                "provider_usage": exchange.response.provider_usage,
            }
            for exchange in attempts.exchanges
        ],
        "quality_evaluation": False,
        "durable_recording": False,
        "billing_evidence": "User-confirmed Free project; monetary cost not independently known",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--code-revision", required=True)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(live_probe(args.root, args.code_revision), indent=2))
        return 0
    except ValueError as error:
        # Only our fixed failure labels; raw validation/provider text can contain input.
        message = str(error)
        allowed = {
            "invalid_response",
            "permission_denied",
            "timeout",
            "rate_limited",
            "unavailable",
            "budget_exhausted",
        }
        label = message.rsplit(": ", 1)[-1]
        print(
            "H4 controlled gateway probe failed: "
            + (label if label in allowed else "configuration/validation"),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
