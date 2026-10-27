"""One owner-approved model-only capture. No resume,retry,fallback or allowance reset."""

import argparse
import json
import sqlite3
import subprocess
import time
import traceback
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import httpx
from agent_harness.admission import GEMINI_TOKEN_CEILING, GeminiFreeAdmission
from agent_harness.contracts import (
    Budget,
    CandidateVersions,
    ModelRequest,
    ModelResponse,
    RunContext,
)
from agent_harness.controls import BoundedGateway, PairedExecutionPolicy, SharedControls
from agent_harness.gateway import ProviderGateway
from agent_harness.gemini import GeminiTransport, request_payload
from agent_harness.isolated_transport import IsolatedTransport
from agent_harness.model_budget import (
    MODELS,
    ModelExtension,
    ModelSlot,
    append_model_extension,
    model_canaries,
    record_model_canary,
)
from agent_harness.model_worker import ModelComparisonWorker
from agent_harness.provider_budget import AttemptLedger, BudgetedTransport
from agent_harness.release_contracts import pin, sha256
from revenue_integrity.model_quality import assess_model, comparison_request
from revenue_integrity.paired_quality import summarize
from revenue_integrity.release_evaluation import ExtractionCase
from run_paired_quality import canonical, write


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("proposal", "capture", "budget-root", "configuration"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    root = Path.cwd()
    assert not args.capture.exists()
    if not args.preflight_only:
        assert not subprocess.check_output(["git", "status", "--porcelain"], text=True).strip()
    prop = args.proposal
    proposal = json.loads((prop / "proposal.json").read_bytes())
    private = json.loads((prop / "evaluator-only-cases.json").read_bytes())
    prior = prop.parent / "paired-quality-proposal-2026-10-27-v1/evaluator-only-cases.json"
    assert sha256(prior.read_bytes()) == proposal["previous_evaluator_cases_sha256"]
    assert json.loads(prior.read_bytes()) == private
    cases = {
        r["ordinal"]: ExtractionCase.model_validate_json(json.dumps(r["case"])) for r in private
    }
    bycase = {c.input.case_id: c for c in cases.values()}
    assert (
        len(cases) == len({c.target.family_id for c in cases.values()}) == 12
        and sum(not c.target.impossible for c in cases.values()) == 6
    )
    models = json.loads((prop / "model-only-requests.json").read_bytes())
    byrequest = {}
    for row in models:
        request = ModelRequest.model_validate_json(json.dumps(row["request"]))
        assert request == comparison_request(cases[row["ordinal"]].input, row["model"])
        byrequest[(row["ordinal"], row["model"])] = request
    assert len(byrequest) == 24 and len({pin(r) for r in byrequest.values()}) == 24
    scheduled = json.loads((prop / "schedule.json").read_bytes())
    assert len(scheduled) == 48
    assert {(r["ordinal"], r["model"], r["trial_id"]) for r in scheduled} == {
        (i, m, t) for i in cases for m in MODELS for t in ("trial-1", "trial-2")
    }
    assert all(r["request_sha256"] == pin(byrequest[(r["ordinal"], r["model"])]) for r in scheduled)
    canaries = model_canaries()
    assert json.loads((prop / "invented-canaries.json").read_bytes()) == [
        r.model_dump(mode="json") for r in canaries
    ]
    for request in (*canaries, *byrequest.values()):
        contents, config = request_payload(request, flash_comparison=True)
        assert config.max_output_tokens == 512
        config.model_dump_json(exclude_none=True)
        for content in contents:
            content.model_dump_json(exclude_none=True)
    # Actual pinned SDK serialization and 90secondtimeout for both routes,zero external traffic.
    wire = []
    for request in canaries:

        def handler(req, model=request.model):
            wire.append(req)
            assert req.extensions["timeout"]["read"] == 90.0
            assert json.loads(req.content)["generationConfig"]["maxOutputTokens"] == 512
            return httpx.Response(
                200,
                json={
                    "modelVersion": model,
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
            flash_comparison=True,
            http_timeout_seconds=90,
            http_transport=httpx.MockTransport(handler),
        ).generate(request, timeout_seconds=110)
        assert proof.failure is None and proof.usage.input_tokens == 10
    assert len(wire) == 2

    # Actual shared admission/control-record roundtrip,not just policy construction.
    class FakeAttempt:
        def generate(self, context, request, *, timeout_seconds):
            assert 60 < timeout_seconds <= 110
            return ModelResponse.model_validate_json(
                proof.model_copy(update={"model": request.model}).canonical_json()
            )

    from agent_harness.offline_example import example_context

    now = datetime.now(UTC)
    ctx = example_context("invented", "a" * 64).model_copy(
        update={
            "mode": "fresh_candidate",
            "clock": now,
            "deadline": now + timedelta(minutes=4),
            "budget": Budget(
                max_model_calls=1,
                max_tokens=GEMINI_TOKEN_CEILING,
                max_cost=Decimal(0),
                cost_currency="USD",
            ),
        }
    )
    gateway = BoundedGateway(
        FakeAttempt(),
        SharedControls(),
        GeminiFreeAdmission(free_tier_confirmed=True, flash_comparison=True),
        policy=PairedExecutionPolicy(),
    )
    assert (
        gateway.generate(ctx, canaries[1]).failure is None
        and gateway.calls[0].policy.attempt_timeout_seconds == 110
    )
    if args.preflight_only:
        print(
            json.dumps(
                {
                    "actual_sdk_requests_preflighted": 26,
                    "constructed_sdk_wire_exchanges": 2,
                    "shared_gateway_roundtrip": True,
                    "provider_calls": 0,
                    "ledger_changes": 0,
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
    assert "model_extension_sha256" not in external
    parents = tuple(
        external[k]
        for k in (
            "allowance_sha256",
            "amendment_sha256",
            "development_extension_sha256",
            "paired_extension_sha256",
            "availability_override_sha256",
        )
    )
    ledger = AttemptLedger(b / "attempts.sqlite", *parents)
    before = ledger.summary()
    assert (before["maximum"], before["consumed"], before["unsettled"]) == (418, 415, 0)
    args.capture.mkdir(exist_ok=False)
    (args.capture / "rows").mkdir()
    with ledger.connect() as db:
        grant = ledger.authorization(db)
        assert grant.project_sha256 == scope
        tables = [
            r[0]
            for r in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        ]
        history = {t: db.execute("SELECT * FROM " + t + " ORDER BY 1").fetchall() for t in tables}
        backup = b / "pre-model-468-recovery-only.sqlite"
        assert not backup.exists()
        with sqlite3.connect(backup) as dest:
            db.backup(dest)
    write(args.capture / "previous-tables.json", history)
    previous = {
        str(p): sha256(p.read_bytes())
        for folder in (
            prop,
            prop.parent / "paired-quality-capture-2026-10-27-v1",
            prop.parent / "paired-quality-continuation-2026-10-27-v1",
            prop.parent / "paired-quality-continuation-2026-10-27-v2",
        )
        for p in folder.rglob("*")
        if p.is_file()
    }
    write(args.capture / "previous-artifact-pins.json", previous)
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
    slots = [
        ModelSlot(
            case_id=sha256(("model-only-invented-" + r.model).encode()),
            request_sha256=pin(r),
            model=r.model,
            trial_id="model-canary",
            purpose="canary",
        )
        for r in canaries
    ]
    slots += [
        ModelSlot(
            case_id=cases[r["ordinal"]].input.case_id,
            request_sha256=r["request_sha256"],
            model=r["model"],
            trial_id="model-only-" + r["trial_id"],
            purpose="quality",
        )
        for r in scheduled
    ]
    now = datetime.now(UTC)
    run_id = "revenue-model-only-development-v1"
    extension = ModelExtension(
        authorization_ref="owner-2026-10-27-explicit468total;2modelrepresentativecanaries+48modelonlyquality;bothcanariesmustpass;failurescount;no-retry-paidfallback-release",
        historical_pins=parents,
        run_id=run_id,
        approved_at=now,
        expires_at=max(now + timedelta(days=3), grant.expires_at),
        slots=tuple(slots),
    )
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    versions = CandidateVersions(
        code_revision=revision,
        candidate="model-only-baseline-v1",
        data_snapshot=proposal["previous_evaluator_cases_sha256"],
        policy="exposed-model-development-not-qualification",
        environment_lock=inventory["uv.lock"],
    )
    budget = Budget(
        max_model_calls=50,
        max_tokens=50 * GEMINI_TOKEN_CEILING,
        max_cost=Decimal(0),
        cost_currency="USD",
    )
    complete = []
    for slot in slots:
        request = next(r for r in (*canaries, *byrequest.values()) if pin(r) == slot.request_sha256)
        context = RunContext(
            run_id=run_id,
            tenant_id="local-authorized-cuad-evaluation",
            agent_id="revenue",
            case_id=slot.case_id,
            trial_id=slot.trial_id,
            business_event_id=sha256((slot.case_id + slot.model + slot.trial_id).encode()),
            mode="fresh_candidate",
            clock=now,
            deadline=now + timedelta(hours=4),
            seed=27,
            budget=budget,
            versions=versions,
        )
        complete.append(
            {
                "slot": slot.model_dump(mode="json"),
                "context": context.model_dump(mode="json"),
                "request": request.model_dump(mode="json"),
            }
        )
    plan = {
        "version": "model-only-capture-v1",
        "source_revision": revision,
        "source_inventory_sha256": sha256(canonical(inventory)),
        "schedule_sha256": sha256(canonical(complete)),
        "proposal_sha256": sha256((prop / "proposal.json").read_bytes()),
        "model_requests_sha256": sha256((prop / "model-only-requests.json").read_bytes()),
        "evaluator_cases_sha256": sha256((prop / "evaluator-only-cases.json").read_bytes()),
        "model_extension_sha256": pin(extension),
        "starting_consumed": 415,
        "maximum_new_attempts": 50,
        "shared_cap": 468,
        "model_only_difference": True,
        "canaries": "both_routes_pass_before_domain",
        "http_timeout_seconds": 90,
        "parent_timeout_seconds": 110,
        "output_tokens": 512,
        "minimum_spacing_seconds": 6,
        "stop": "firstcanaryfailure;domainauthquotabudgetdenialor3consecutivetimeoutunavailable",
        "retries": 0,
        "paid_fallback": False,
        "release_allowed": False,
    }
    for name, value in [
        ("plan.json", plan),
        ("schedule.json", complete),
        ("source-inventory.json", inventory),
        ("extension.json", extension.model_dump(mode="json")),
    ]:
        write(args.capture / name, value)
    write(b / "model-extension-468.json", extension.model_dump(mode="json"))
    extensionpin = append_model_extension(ledger, extension)
    assert extensionpin == pin(extension)
    updated = external | {"model_extension_sha256": extensionpin, "maximum": 468}
    tmp = b / "external-pin-model.tmp"
    write(tmp, updated)
    tmp.replace(b / "external-pin.json")
    ledger = AttemptLedger(ledger.path, *parents, extensionpin)
    assert ledger.summary()["maximum"] == 468
    controls = SharedControls()
    outcomes = []
    canaryresults = []
    consecutive = 0
    stop = None
    for index, row in enumerate(complete):
        assert all(sha256((root / name).read_bytes()) == v for name, v in inventory.items())
        context = RunContext.model_validate_json(json.dumps(row["context"]))
        request = ModelRequest.model_validate_json(json.dumps(row["request"]))
        slot = slots[index]
        isolated = IsolatedTransport(ModelComparisonWorker(key, True))
        provider = ProviderGateway(BudgetedTransport(isolated, ledger, context, scope))
        bounded = BoundedGateway(
            provider,
            controls,
            GeminiFreeAdmission(free_tier_confirmed=True, flash_comparison=True),
            policy=PairedExecutionPolicy(),
        )
        start = time.monotonic()
        response = bounded.generate(context, request)
        elapsed = time.monotonic() - start
        outcome = None
        parsed = None
        if slot.purpose == "canary":
            passed = False
            try:
                record_model_canary(ledger, request, response)
                passed = True
            except ValueError:
                stop = "model_canary_failed"
            canaryresults.append(
                {
                    "model": slot.model,
                    "passed": passed,
                    "failure": response.failure.code if response.failure else None,
                    "elapsed_seconds": elapsed,
                }
            )
        else:
            trial = "trial-1" if slot.trial_id.endswith("1") else "trial-2"
            outcome, parsed = assess_model(
                bycase[slot.case_id].input, request, response, trial, elapsed
            )
            outcomes.append(outcome)
            code = response.failure.code if response.failure else None
            consecutive = consecutive + 1 if code in ("timeout", "unavailable") else 0
            if (
                code in ("permission_denied", "rate_limited", "budget_exhausted")
                or consecutive >= 3
            ):
                stop = "operational_stop"
        raw = {
            "context": row["context"],
            "request": row["request"],
            "response": response.model_dump(mode="json"),
            "outcome": outcome.model_dump(mode="json") if outcome else None,
            "parsed": parsed,
            "timing": isolated.last_timing.model_dump(mode="json")
            if isolated.last_timing
            else None,
            "controlled_calls": [c.model_dump(mode="json") for c in bounded.calls],
            "exchanges": [e.model_dump(mode="json") for e in provider.exchanges],
        }
        write(args.capture / "rows" / f"{index + 1:02}.json", raw)
        print(
            json.dumps(
                {
                    "scheduled_row": index + 1,
                    "purpose": slot.purpose,
                    "model": slot.model,
                    "decision": outcome.decision if outcome else None,
                    "failure": response.failure.code
                    if response.failure
                    else (outcome.failure if outcome else None),
                    "elapsed_seconds": round(elapsed, 2),
                    "consumed": ledger.summary()["consumed"],
                }
            ),
            flush=True,
        )
        if stop:
            break
        if index < 49:
            time.sleep(6)
    expected = {c.input.case_id: not c.target.impossible for c in cases.values()}
    controlids = frozenset(
        cases[r["ordinal"]].input.case_id
        for r in private
        if r["role"] == "previously_correct_control"
    )
    report = summarize(expected, controlids, tuple(outcomes), comparison="models") | {
        "canaries": canaryresults,
        "stop_reason": stop,
        "model_labels": {"baseline": MODELS[0], "challenger": MODELS[1]},
        "budget": ledger.summary(),
        "new_reserved_attempts": ledger.summary()["consumed"] - 415,
        "plan_sha256": sha256(canonical(plan)),
    }
    with ledger.connect() as db:
        for table, rows in history.items():
            current = db.execute("SELECT * FROM " + table + " ORDER BY 1").fetchall()
            if table in ("attempts", "paired_slots"):
                assert all(row in current for row in rows)
            else:
                assert current == rows
    assert all(sha256(Path(name).read_bytes()) == v for name, v in previous.items())
    write(args.capture / "report.json", report)
    print(
        json.dumps(
            {
                "complete": True,
                "domain_observed": len(outcomes),
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
