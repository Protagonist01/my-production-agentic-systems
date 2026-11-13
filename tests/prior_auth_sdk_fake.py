"""Importable invented SDK worker for actual spawn/readiness; no provider connection."""

import json

import httpx
from agent_harness.gemini import GeminiTransport


def response(request):
    payload = json.loads(json.loads(request.content)["contents"][0]["parts"][0]["text"])
    claim = {
        "schema_version": 1,
        "criterion_id": payload["criterion"]["criterion_id"],
        "state": "met",
        "quotes": [payload["full_note"].splitlines()[0]],
        "rationale": "Invented readiness response, not a clinical assessment.",
    }
    return httpx.Response(
        200,
        json={
            "modelVersion": "gemini-3.5-flash-lite",
            "candidates": [
                {
                    "content": {"role": "model", "parts": [{"text": json.dumps(claim)}]},
                    "finishReason": "STOP",
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 50,
                "candidatesTokenCount": 20,
                "totalTokenCount": 70,
            },
        },
    )


class Worker:
    def generate(self, request, *, timeout_seconds):
        return GeminiTransport(
            "invented-key",
            free_tier_confirmed=True,
            http_transport=httpx.MockTransport(response),
            http_timeout_seconds=90,
        ).generate(request, timeout_seconds=min(90, timeout_seconds))
