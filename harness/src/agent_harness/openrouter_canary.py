"""Invented-only, explicit-free OpenRouter canary. Not a domain model adapter."""

import math
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import httpx
from jsonschema.exceptions import ValidationError
from pydantic import AwareDatetime

from agent_harness.contracts import Contract, FailureCode, ModelMessage, ModelRequest, ModelResponse
from agent_harness.gateway import failed_response
from agent_harness.groq import json_value, usage, validator
from agent_harness.provider_budget import AttemptLedger
from agent_harness.release_contracts import Sha256, pin

PROVIDER = "openrouter"
MODEL = "liquid/lfm-2.5-2.6b:free"
ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"


def requests() -> tuple[ModelRequest, ...]:
    """Fixed invented inventory, independent of any dataset, labels or user documents."""
    result = []
    for number in range(1, 13):
        result.append(
            ModelRequest(
                provider=PROVIDER,
                model=MODEL,
                endpoint=ENDPOINT,
                messages=(
                    ModelMessage(
                        role="system", content="Return only JSON containing the integer answer."
                    ),
                    ModelMessage(role="user", content=f"Invented canary: what is {number} + 7?"),
                ),
                parameters={"temperature": 0.0, "max_tokens": 256},
                output_schema={
                    "type": "object",
                    "properties": {"answer": {"type": "integer"}},
                    "required": ["answer"],
                    "additionalProperties": False,
                },
            )
        )
    return tuple(result)


def request_payload(request: ModelRequest) -> dict[str, object]:
    request = ModelRequest.model_validate_json(request.canonical_json())
    if request not in requests():
        raise ValueError("outside frozen invented canary inventory")
    assert request.output_schema is not None
    validator(request.output_schema)
    return {
        "model": MODEL,
        "messages": [{"role": m.role, "content": m.content} for m in request.messages],
        "temperature": 0.0,
        "max_tokens": 256,
        "stream": False,
        "provider": {
            "allow_fallbacks": False,
            "require_parameters": True,
            "max_price": {"prompt": 0, "completion": 0, "request": 0},
        },
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "canary", "strict": True, "schema": request.output_schema},
        },
    }


@dataclass(frozen=True)
class CanaryWorker:
    api_key: str = field(repr=False)

    def generate(self, request: ModelRequest, *, timeout_seconds: float) -> ModelResponse:
        return generate(self.api_key, request, timeout_seconds=timeout_seconds)


def generate(
    api_key: str,
    request: ModelRequest,
    *,
    timeout_seconds: float = 45.0,
    http_transport: httpx.BaseTransport | None = None,
) -> ModelResponse:
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        return failed_response(request, "timeout", "No canary time remaining", dispatched=False)
    observed = None
    counts: dict[str, int | None] = {}
    try:
        payload = request_payload(request)
    except ValueError:
        return failed_response(
            request, "invalid_response", "Canary preflight refused", dispatched=False
        )
    if not api_key:
        return failed_response(request, "permission_denied", "Canary key missing", dispatched=False)
    try:
        with httpx.Client(
            transport=http_transport,
            trust_env=False,
            follow_redirects=False,
            timeout=min(timeout_seconds, 45.0),
        ) as client:
            with client.stream(
                "POST", ENDPOINT, headers={"Authorization": "Bearer " + api_key}, json=payload
            ) as response:
                if response.status_code != 200:
                    code = response.status_code
                    failure: FailureCode = (
                        "permission_denied"
                        if code in (401, 403)
                        else "rate_limited"
                        if code == 429
                        else "timeout"
                        if code in (408, 504)
                        else "unavailable"
                        if code >= 500
                        else "invalid_response"
                    )
                    return failed_response(
                        request, failure, f"OpenRouter canary HTTP {code}", dispatched=True
                    )
                raw = bytearray()
                for chunk in response.iter_bytes(chunk_size=16384):
                    raw.extend(chunk)
                    if len(raw) > 100000:
                        raise ValueError("response too large")
        body = json_value(raw.decode("utf-8"))
        if not isinstance(body, dict) or body.get("error"):
            raise ValueError("invalid response object")
        observed, counts = usage(body)  # Shared strict token parser; monetary cost stays unknown.
        # OpenRouter's response may use the canonical model ID without the :free suffix.
        if body.get("model") not in (MODEL, MODEL.removesuffix(":free")):
            raise ValueError("unexpected model")
        choices = body.get("choices")
        if not isinstance(choices, list) or len(choices) != 1:
            raise ValueError("ambiguous choice")
        choice = choices[0]
        message = choice["message"]
        if (
            choice.get("finish_reason") != "stop"
            or message.get("role") != "assistant"
            or not isinstance(message.get("content"), str)
            or message.get("tool_calls")
            or message.get("function_call")
            or message.get("refusal")
        ):
            raise ValueError("invalid structured completion")
        assert request.output_schema is not None
        validator(request.output_schema).validate(json_value(message["content"]))
        return ModelResponse(
            provider=PROVIDER,
            model=body["model"],
            provider_request_id=body.get("id"),
            output=ModelMessage(role="assistant", content=message["content"]),
            finish_reason="stop",
            usage=observed,
            provider_usage=counts,
        )
    except httpx.TimeoutException:
        return failed_response(request, "timeout", "Canary HTTP timeout", dispatched=True)
    except httpx.HTTPError:
        return failed_response(request, "unavailable", "Canary transport failed", dispatched=True)
    except (ValueError, KeyError, TypeError, AttributeError, ValidationError):
        return failed_response(
            request, "invalid_response", "Canary response refused", dispatched=True, usage=observed
        ).model_copy(update={"provider_usage": counts})


class CanaryAllowance(Contract):
    version: Literal["openrouter-invented-free-canary-v1"] = "openrouter-invented-free-canary-v1"
    authorization_ref: str
    credential_sha256: Sha256
    approved_at: AwareDatetime
    expires_at: AwareDatetime
    maximum: Literal[12] = 12


def initialize(path: Path, grant: CanaryAllowance) -> str:
    """Exclusive new canary only; never open or modify a Groq/Gemini allowance."""
    grant = CanaryAllowance.model_validate_json(grant.canonical_json())
    if grant.expires_at <= grant.approved_at or not grant.authorization_ref:
        raise ValueError("invalid canary authorization interval/reference")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(descriptor)
    with sqlite3.connect(path) as db:
        db.executescript("""
        CREATE TABLE authorization(pin TEXT PRIMARY KEY, document TEXT NOT NULL);
        CREATE TABLE attempts(serial INTEGER PRIMARY KEY, ticket TEXT NOT NULL UNIQUE,
          context_pin TEXT NOT NULL, request_pin TEXT NOT NULL, reserved_at TEXT NOT NULL,
          response_pin TEXT, settled_at TEXT);
        CREATE TRIGGER no_delete BEFORE DELETE ON attempts
          BEGIN SELECT RAISE(ABORT,'append only'); END;
        CREATE TRIGGER no_rebind BEFORE UPDATE ON attempts
          WHEN NEW.serial!=OLD.serial OR NEW.ticket!=OLD.ticket OR NEW.context_pin!=OLD.context_pin
            OR NEW.request_pin!=OLD.request_pin OR NEW.reserved_at!=OLD.reserved_at
            OR OLD.response_pin IS NOT NULL
          BEGIN SELECT RAISE(ABORT,'immutable reservation'); END;
        """)
        db.execute("INSERT INTO authorization VALUES(?,?)", (pin(grant), grant.canonical_json()))
    return pin(grant)


@dataclass(frozen=True)
class CanaryLedger:
    path: Path
    allowance_sha256: str

    def base(self) -> AttemptLedger:
        return AttemptLedger(self.path, self.allowance_sha256)

    def authorization(self, db: sqlite3.Connection) -> CanaryAllowance:
        rows = db.execute("SELECT pin,document FROM authorization").fetchall()
        if len(rows) != 1 or rows[0][0] != self.allowance_sha256:
            raise ValueError("canary authorization pin differs")
        grant = CanaryAllowance.model_validate_json(rows[0][1])
        if pin(grant) != self.allowance_sha256:
            raise ValueError("canary authorization document differs")
        return grant

    def reserve(self, request: ModelRequest, credential_sha256: str) -> str:
        request_payload(request)
        with self.base().connect() as db:
            db.execute("BEGIN IMMEDIATE")
            grant = self.authorization(db)
            if (
                credential_sha256 != grant.credential_sha256
                or not grant.approved_at <= datetime.now(UTC) < grant.expires_at
                or db.execute("SELECT count(*) FROM attempts").fetchone()[0] >= grant.maximum
                or db.execute(
                    "SELECT 1 FROM attempts WHERE request_pin=?", (pin(request),)
                ).fetchone()
            ):
                raise ValueError("canary cap, duplicate, credential or interval denied")
            ticket = pin(request)
            db.execute(
                "INSERT INTO attempts(ticket,context_pin,request_pin,reserved_at) VALUES(?,?,?,?)",
                (ticket, pin(grant), pin(request), datetime.now(UTC).isoformat()),
            )
        return ticket

    def settle(self, ticket: str, response: ModelResponse) -> None:
        response = ModelResponse.model_validate_json(response.canonical_json())
        if response.provider != PROVIDER or response.model not in (
            MODEL,
            MODEL.removesuffix(":free"),
        ):
            raise ValueError("foreign canary response")
        with self.base().connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self.authorization(db)
            changed = db.execute(
                "UPDATE attempts SET response_pin=?,settled_at=? "
                "WHERE ticket=? AND response_pin IS NULL",
                (pin(response), datetime.now(UTC).isoformat(), ticket),
            )
            if changed.rowcount != 1:
                raise ValueError("canary already settled or missing")

    def summary(self) -> dict[str, int]:
        with self.base().connect() as db:
            grant = self.authorization(db)
            used, unsettled = db.execute(
                "SELECT count(*),sum(response_pin IS NULL) FROM attempts"
            ).fetchone()
        return {
            "maximum": grant.maximum,
            "consumed": used,
            "remaining": grant.maximum - used,
            "unsettled": unsettled or 0,
        }
