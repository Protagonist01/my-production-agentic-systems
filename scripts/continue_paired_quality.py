"""Explicit owner-approved continuation of untouched slots; never rerun this operator."""

import argparse
import json
import sqlite3
import subprocess
import time
import traceback
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
from agent_harness.admission import GeminiFreeAdmission
from agent_harness.contracts import ModelRequest, ModelResponse, RunContext
from agent_harness.controls import BoundedGateway, SharedControls
from agent_harness.gateway import ProviderGateway
from agent_harness.gemini import GeminiTransport, request_payload
from agent_harness.isolated_transport import IsolatedTransport
from agent_harness.paired_budget import (
    AvailabilityOverride,
    append_availability,
    canary_requests,
    record_canary_pass,
)
from agent_harness.paired_worker import PairedExecutionPolicy, PairedWorker
from agent_harness.provider_budget import AttemptLedger, BudgetedTransport
from agent_harness.release_contracts import pin, sha256
from revenue_integrity.paired_quality import assess, summarize
from revenue_integrity.release_evaluation import ExtractionCase
from run_paired_quality import FACTORIES, canonical, write


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("proposal", "capture", "continuation", "budget-root", "configuration"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    root = Path.cwd()
    assert not args.continuation.exists()
    if not args.preflight_only:
        assert not subprocess.check_output(["git", "status", "--porcelain"], text=True).strip()
    cap = args.capture
    oldplan = json.loads((cap / "plan.json").read_bytes())
    schedule = json.loads((cap / "schedule.json").read_bytes())
    assert sha256(canonical(schedule)) == oldplan["schedule_sha256"]
    first = json.loads((cap / "rows/01.json").read_bytes())
    failed = ModelResponse.model_validate_json(json.dumps(first["response"]))
    oldreport = json.loads((cap / "report.json").read_bytes())
    assert oldreport["stop_reason"] == "canary_failed" and oldreport["observed"] == 0
    assert (
        failed.failure
        and failed.failure.code == "timeout"
        and len(list((cap / "rows").glob("*.json"))) == 1
    )
    private = json.loads((args.proposal / "evaluator-only-cases.json").read_bytes())
    cases = {
        r["ordinal"]: ExtractionCase.model_validate_json(json.dumps(r["case"])) for r in private
    }
    bycase = {c.input.case_id: c for c in cases.values()}
    assert (
        sha256((args.proposal / "evaluator-only-cases.json").read_bytes())
        == oldplan["evaluator_cases_sha256"]
    )
    assert (
        sha256((args.proposal / "model-only-requests.json").read_bytes())
        == oldplan["model_inputs_sha256"]
    )
    remaining = schedule[1:]
    assert len(remaining) == 73
    for index, row in enumerate(remaining):
        request = ModelRequest.model_validate_json(json.dumps(row["request"]))
        if index == 0:
            assert request == canary_requests()[1]
        else:
            assert request == FACTORIES[row["slot"]["variant"]](
                bycase[row["slot"]["case_id"]].input
            )
        contents, config = request_payload(request)
        config.model_dump_json(exclude_none=True)
        for content in contents:
            content.model_dump_json(exclude_none=True)
    # Exercise actual SDK long-window wire and representative schema without network.
    seen = []

    def handler(req):
        seen.append(req)
        assert req.extensions["timeout"]["read"] == 90.0
        assert json.loads(req.content)["generationConfig"]["maxOutputTokens"] == 512
        return httpx.Response(
            200,
            json={
                "modelVersion": "gemini-3.5-flash-lite",
                "candidates": [
                    {
                        "finishReason": "STOP",
                        "content": {
                            "role": "model",
                            "parts": [{"text": '{"decision":"accept","evidence_ids":["s0"]}'}],
                        },
                    }
                ],
                "usageMetadata": {
                    "promptTokenCount": 10,
                    "candidatesTokenCount": 4,
                    "totalTokenCount": 14,
                },
            },
        )

    proof = GeminiTransport(
        "invented",
        free_tier_confirmed=True,
        http_timeout_seconds=90,
        http_transport=httpx.MockTransport(handler),
    ).generate(canary_requests()[1], timeout_seconds=110)
    assert len(seen) == 1 and proof.failure is None and proof.usage.input_tokens == 10
    policy = PairedExecutionPolicy()

    class NeverDispatch:
        def generate(self, *args, **kwargs):
            raise AssertionError("preflight must not dispatch")

    bounded = BoundedGateway(
        NeverDispatch(),
        SharedControls(),
        GeminiFreeAdmission(free_tier_confirmed=True),
        policy=policy,
    )
    assert bounded.policy.attempt_timeout_seconds == 110 and bounded.policy.max_attempts == 1
    if args.preflight_only:
        print(
            json.dumps(
                {
                    "untouched_scheduled_requests_verified": 73,
                    "distinct_requests_preflighted": 37,
                    "actual_sdk_fake_wire": 1,
                    "http_timeout": 90,
                    "parent_timeout": 110,
                    "provider_calls": 0,
                    "ledger_mutations": 0,
                }
            )
        )
        return
    cfg = dict(
        line.split("=", 1)
        for line in args.configuration.read_text().splitlines()
        if "=" in line and not line.startswith("#")
    )
    key = cfg["GEMINI_API_KEY"].strip().strip(chr(34) + chr(39))
    assert cfg["GEMINI_FREE_TIER_CONFIRMED"].strip().lower() in ("true", "1", "yes")
    scope = sha256(
        canonical(
            {
                "configuration_reference": str(args.configuration),
                "credential_sha256": sha256(key.encode()),
                "meaning": (
                    "operator-selected-credential-association-not-provider-verified-cloud-project"
                ),
            }
        )
    )
    b = args.budget_root
    external = json.loads((b / "external-pin.json").read_bytes())
    old = AttemptLedger(
        b / "attempts.sqlite",
        external["allowance_sha256"],
        external["amendment_sha256"],
        external["development_extension_sha256"],
        external["paired_extension_sha256"],
        external.get("availability_override_sha256"),
    )
    assert old.summary()["consumed"] == 342 and old.summary()["unsettled"] == 0
    with old.connect() as db:
        assert old.authorization(db).project_sha256 == scope
        before_rows = db.execute("SELECT * FROM attempts ORDER BY serial").fetchall()
        backup = b / "pre-availability-dispatch-recovery-only.sqlite"
        assert not backup.exists()
        with sqlite3.connect(backup) as destination:
            db.backup(destination)
    args.continuation.mkdir(exist_ok=False)
    (args.continuation / "rows").mkdir()
    now = datetime.now(UTC)
    if old.availability_override_sha256 is not None:
        override = AvailabilityOverride.model_validate_json(
            (b / "availability-continuation.json").read_bytes()
        )
        assert pin(override) == old.availability_override_sha256
        assert override.failed_first_response_sha256 == pin(failed)
        assert override.failed_report_sha256 == sha256((cap / "report.json").read_bytes())
        with old.connect() as db:
            assert db.execute("SELECT count(*) FROM paired_slots").fetchone()[0] == 1
            assert db.execute("SELECT count(*) FROM paired_canary_passes").fetchone()[0] == 0
    else:
        override = AvailabilityOverride(
            authorization_ref="owner-2026-10-27-explicit-bounded90HTTP110parent-unused-representativecanary;original72qualitycalls-only-if-pass;no-retry-or-quality-gate-change",
            paired_extension_sha256=old.paired_extension_sha256,
            failed_first_response_sha256=pin(failed),
            failed_report_sha256=sha256((cap / "report.json").read_bytes()),
            representative_request_sha256=pin(canary_requests()[1]),
            approved_at=now,
        )
    files = [
        p
        for folder in (
            root / "harness/src/agent_harness",
            root / "projects/revenue-integrity/src/revenue_integrity",
        )
        for p in folder.glob("*.py")
    ]
    files += [Path(__file__).resolve(), root / "scripts/run_paired_quality.py", root / "uv.lock"]
    inventory = {str(p.relative_to(root)): sha256(p.read_bytes()) for p in files}
    previous = {
        str(p): sha256(p.read_bytes())
        for folder in (cap, args.proposal)
        for p in folder.rglob("*")
        if p.is_file()
    }
    write(args.continuation / "previous-artifact-pins.json", previous)
    write(args.continuation / "previous-attempts.json", before_rows)
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    for row in remaining:
        context = RunContext.model_validate_json(json.dumps(row["context"]))
        context = context.model_copy(
            update={
                "clock": now,
                "deadline": now + timedelta(hours=4),
                "versions": context.versions.model_copy(update={"code_revision": revision}),
            }
        )
        row["context"] = context.model_dump(mode="json")
    plan = {
        "version": "paired-quality-continuation-v1",
        "source_revision": revision,
        "original_plan_sha256": sha256((cap / "plan.json").read_bytes()),
        "failed_first_report_sha256": sha256((cap / "report.json").read_bytes()),
        "override_sha256": pin(override),
        "remaining_schedule_sha256": sha256(canonical(remaining)),
        "source_inventory_sha256": sha256(canonical(inventory)),
        "maximum_additional_attempts": 73,
        "shared_cap": 418,
        "consumed_before": 342,
        "first_timeout_preserved": True,
        "http_timeout_seconds": 90,
        "parent_timeout_seconds": 110,
        "same_model_requests_trials": True,
        "stop": (
            "representative failure;domain auth/quota/budget denial "
            "or3consecutive timeout/unavailable"
        ),
        "retries": 0,
        "paid_fallback": False,
        "release_allowed": False,
    }
    for name, value in [
        ("plan.json", plan),
        ("schedule.json", remaining),
        ("source-inventory.json", inventory),
        ("override.json", override.model_dump(mode="json")),
    ]:
        write(args.continuation / name, value)
    if old.availability_override_sha256 is None:
        write(b / "availability-continuation.json", override.model_dump(mode="json"))
        newpin = append_availability(old, override, failed)
        assert newpin == pin(override)
        updated = external | {"availability_override_sha256": newpin}
        tmp = b / "external-pin-availability.tmp"
        write(tmp, updated)
        tmp.replace(b / "external-pin.json")
    else:
        newpin = old.availability_override_sha256
    ledger = AttemptLedger(
        old.path,
        old.allowance_sha256,
        old.amendment_sha256,
        old.development_extension_sha256,
        old.paired_extension_sha256,
        newpin,
    )
    outcomes = []
    stop = None
    consecutive = 0
    controls = SharedControls()
    representative = None
    for index, row in enumerate(remaining):
        assert all(sha256((root / name).read_bytes()) == v for name, v in inventory.items())
        context = RunContext.model_validate_json(json.dumps(row["context"]))
        request = ModelRequest.model_validate_json(json.dumps(row["request"]))
        slot = row["slot"]
        isolated = IsolatedTransport(PairedWorker(key, True))
        provider = ProviderGateway(BudgetedTransport(isolated, ledger, context, scope))
        bounded = BoundedGateway(
            provider,
            controls,
            GeminiFreeAdmission(free_tier_confirmed=True),
            policy=PairedExecutionPolicy(),
        )
        start = time.monotonic()
        response = bounded.generate(context, request)
        elapsed = time.monotonic() - start
        result = None
        parsed = None
        if index == 0:
            passed = False
            try:
                record_canary_pass(ledger, request, response)
                passed = True
            except ValueError:
                stop = "representative_canary_failed"
            representative = {
                "passed": passed,
                "failure": response.failure.code if response.failure else None,
                "elapsed_seconds": elapsed,
            }
        else:
            result, parsed = assess(
                bycase[slot["case_id"]].input,
                request,
                response,
                slot["variant"],
                slot["trial_id"],
                elapsed,
            )
            outcomes.append(result)
            code = response.failure.code if response.failure else None
            consecutive = consecutive + 1 if code in ("timeout", "unavailable") else 0
            if (
                code in ("permission_denied", "budget_exhausted", "rate_limited")
                or consecutive >= 3
            ):
                stop = "operational_stop"
        payload = {
            "context": row["context"],
            "request": row["request"],
            "response": response.model_dump(mode="json"),
            "outcome": result.model_dump(mode="json") if result else None,
            "parsed": parsed,
            "timing": isolated.last_timing.model_dump(mode="json")
            if isolated.last_timing
            else None,
            "controlled_calls": [r.model_dump(mode="json") for r in bounded.calls],
            "exchanges": [r.model_dump(mode="json") for r in provider.exchanges],
        }
        write(args.continuation / "rows" / f"{index + 2:02}.json", payload)
        print(
            json.dumps(
                {
                    "scheduled_row": index + 2,
                    "variant": slot["variant"],
                    "decision": result.decision if result else None,
                    "failure": response.failure.code
                    if response.failure
                    else (result.failure if result else None),
                    "elapsed_seconds": round(elapsed, 2),
                    "consumed": ledger.summary()["consumed"],
                }
            ),
            flush=True,
        )
        if stop:
            break
        if index < 72:
            time.sleep(6)
    expected = {c.input.case_id: not c.target.impossible for c in cases.values()}
    control_ids = frozenset(
        cases[r["ordinal"]].input.case_id
        for r in private
        if r["role"] == "previously_correct_control"
    )
    report = summarize(expected, control_ids, tuple(outcomes)) | {
        "representative_canary": representative,
        "first_canary_failed": True,
        "stop_reason": stop,
        "budget": ledger.summary(),
        "new_reserved_attempts_including_first_timeout": ledger.summary()["consumed"] - 341,
        "continuation_plan_sha256": sha256(canonical(plan)),
        "operating_plan_amended_with_owner_approval": True,
    }
    with ledger.connect() as db:
        assert (
            db.execute("SELECT * FROM attempts WHERE serial<=342 ORDER BY serial").fetchall()
            == before_rows
        )
    assert all(sha256(Path(p).read_bytes()) == v for p, v in previous.items())
    write(args.continuation / "report.json", report)
    print(
        json.dumps(
            {
                "complete": True,
                "observed_domain": len(outcomes),
                "stop_reason": stop,
                "budget": ledger.summary(),
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        frame = traceback.extract_tb(error.__traceback__)[-1]
        print(
            json.dumps(
                {
                    "failed": type(error).__name__,
                    "function": frame.name,
                    "line": frame.lineno,
                    "no_automatic_retry": True,
                }
            ),
            flush=True,
        )
        raise SystemExit(1) from None
