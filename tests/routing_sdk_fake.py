"""Small invented SDK fake; spawned workers must not import history/test suites."""

import json

import httpx


def fake_sdk(request):
    wire = json.loads(request.content)
    text = wire["contents"][0]["parts"][0]["text"]
    assert text.startswith("Invented routing")
    assert not wire.get("tools") and wire["generationConfig"]["maxOutputTokens"] == 512
    out = {"intent": "refund", "requested_minor": None}
    if "routing_version" in wire["generationConfig"]["responseJsonSchema"]["properties"]:
        out["routing_version"] = "olist-intent-routing-v2"
    return httpx.Response(
        200,
        json={
            "candidates": [
                {
                    "content": {"role": "model", "parts": [{"text": json.dumps(out)}]},
                    "finishReason": "STOP",
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 3,
                "candidatesTokenCount": 5,
                "totalTokenCount": 8,
            },
        },
    )


def sdk_child(controls, context, request, connection):
    try:
        result = controls.transport(context).generate(request)
        connection.send(result.canonical_json())
    finally:
        connection.close()
