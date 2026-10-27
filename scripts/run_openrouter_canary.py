"""Owner-authorized maximum-12 invented Free canary, once, stop on first failure.

Private directory must not exist. Never resume/retry from this command. Never log keys.
"""

import argparse
import json
import subprocess
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
from agent_harness.contracts import ModelResponse
from agent_harness.isolated_transport import IsolatedTransport
from agent_harness.openrouter_canary import (
    MODEL,
    CanaryAllowance,
    CanaryLedger,
    CanaryWorker,
    generate,
    initialize,
    request_payload,
    requests,
)
from agent_harness.release_contracts import pin, sha256


def save(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-root", type=Path, required=True)
    parser.add_argument("--key-file", type=Path, required=True)
    args = parser.parse_args()
    args.private_root.mkdir(parents=True, exist_ok=False)
    values = dict(
        line.split("=", 1) for line in args.key_file.read_text().splitlines() if "=" in line
    )
    key = values["OPENROUTER_API_KEY"]
    assert values["OPENROUTER_FREE_CONFIRMED"] == "true" and key
    inventory = requests()
    assert len(inventory) == len({pin(r) for r in inventory}) == 12
    for request in inventory:
        request_payload(request)
        constructed = {
            "model": MODEL.removesuffix(":free"),
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": '{"answer":8}'},
                }
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }
        proof = generate(
            "invented-key",
            request,
            http_transport=httpx.MockTransport(
                lambda req, body=constructed: httpx.Response(200, json=body)
            ),
        )
        assert proof.failure is None and proof.usage.input_tokens == 1
    now = datetime.now(UTC)
    grant = CanaryAllowance(
        authorization_ref="owner-2026-10-27-openrouter-12-invented-free-canary",
        credential_sha256=sha256(key.encode()),
        approved_at=now,
        expires_at=now + timedelta(hours=2),
    )
    files = [
        "harness/src/agent_harness/" + s + ".py"
        for s in (
            "openrouter_canary",
            "groq",
            "provider_budget",
            "isolated_transport",
            "process_control",
            "contracts",
            "release_contracts",
            "gateway",
        )
    ]
    files += ["scripts/run_openrouter_canary.py", "uv.lock"]
    source = {f: sha256(Path(f).read_bytes()) for f in files}
    save(args.private_root / "source-inventory.json", source)
    save(args.private_root / "requests.json", [r.model_dump(mode="json") for r in inventory])
    save(args.private_root / "allowance.json", grant.model_dump(mode="json"))
    plan = {
        "version": "openrouter-invented-canary-plan-v1",
        "maximum": 12,
        "authorization_sha256": pin(grant),
        "requests_sha256s": [pin(r) for r in inventory],
        "source_inventory_sha256": sha256(
            (args.private_root / "source-inventory.json").read_bytes()
        ),
        "code_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "source_inventory_authoritative": True,
        "parent_deadline_seconds": 55,
        "http_inactivity_timeout_seconds": 45,
        "retries": 0,
        "paid_fallback": False,
        "stop_on_first_failure": True,
        "data_scope": "invented arithmetic only",
    }
    save(args.private_root / "plan.json", plan)
    ledger = CanaryLedger(
        args.private_root / "attempts.sqlite",
        initialize(args.private_root / "attempts.sqlite", grant),
    )
    save(args.private_root / "external-pin.json", {"allowance_sha256": ledger.allowance_sha256})
    worker = IsolatedTransport(CanaryWorker(key))
    outcomes = []
    for number, request in enumerate(inventory, 1):
        ticket = ledger.reserve(request, grant.credential_sha256)
        result = worker.generate(request, timeout_seconds=55.0)
        ledger.settle(ticket, result)
        correct = (
            result.failure is None
            and result.output is not None
            and json.loads(result.output.content)["answer"] == number + 7
        )
        row = {
            "ordinal": number,
            "request_sha256": pin(request),
            "ticket": ticket,
            "response": result.model_dump(mode="json"),
            "correct": correct,
            "timing": worker.last_timing.model_dump(mode="json") if worker.last_timing else None,
        }
        save(args.private_root / f"row-{number:02}.json", row)
        outcomes.append(row)
        print(
            json.dumps(
                {
                    "ordinal": number,
                    "correct": correct,
                    "failure": result.failure.code if result.failure else None,
                    "budget": ledger.summary(),
                }
            ),
            flush=True,
        )
        if not correct:
            break
        if number < 12:
            time.sleep(4)  # At most 15 dispatches/minute; never retry a failed request.
    with ledger.base().connect() as db:
        reservations = db.execute(
            "SELECT request_pin,response_pin FROM attempts ORDER BY serial"
        ).fetchall()
    assert reservations == [
        (r["request_sha256"], pin(ModelResponse.model_validate_json(json.dumps(r["response"]))))
        for r in outcomes
    ]
    assert all(sha256(Path(f).read_bytes()) == digest for f, digest in source.items())
    report = {
        "version": "openrouter-invented-canary-result-v1",
        "model_requested": MODEL,
        "observed": len(outcomes),
        "correct": sum(r["correct"] for r in outcomes),
        "failures": [
            r["response"]["failure"]["code"] for r in outcomes if r["response"]["failure"]
        ],
        "budget": ledger.summary(),
        "all_twelve_passed": len(outcomes) == 12 and all(r["correct"] for r in outcomes),
        "input_tokens_known": sum(r["response"]["usage"]["input_tokens"] or 0 for r in outcomes),
        "output_tokens_known": sum(r["response"]["usage"]["output_tokens"] or 0 for r in outcomes),
        "unknown_token_rows": sum(
            r["response"]["usage"]["input_tokens"] is None
            or r["response"]["usage"]["output_tokens"] is None
            for r in outcomes
        ),
        "unknown_cost_rows": sum(r["response"]["usage"]["cost"] is None for r in outcomes),
        "source_inventory_verified": True,
        "ledger_rows_verified": True,
        "domain_data_exported": False,
        "release_allowed": False,
        "limits": [
            "Invented arithmetic transport canary, not contract quality or calibration.",
            "Explicit free route and zero price ceilings; billing independently unverified.",
            "One selected model; no domain use, retries, paid route or fallback authorized.",
        ],
    }
    save(args.private_root / "report.json", report)


if __name__ == "__main__":
    main()
