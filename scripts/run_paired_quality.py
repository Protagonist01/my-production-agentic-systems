"""One frozen owner-approved paired development capture; no resume, retries or fallback."""

import argparse
import json
import sqlite3
import subprocess
import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import httpx
from agent_harness.admission import GEMINI_TOKEN_CEILING, GeminiFreeAdmission
from agent_harness.cases import _unique_object
from agent_harness.contracts import Budget, CandidateVersions, ModelRequest, RunContext
from agent_harness.controls import BoundedGateway, ExecutionPolicy, SharedControls
from agent_harness.gateway import ProviderGateway
from agent_harness.gemini import GeminiTransport, request_payload
from agent_harness.isolated_transport import GeminiWorker, IsolatedTransport
from agent_harness.paired_budget import (
    PairedExtension,
    PairedSlot,
    append_extension,
    canary_requests,
    record_canary_pass,
)
from agent_harness.provider_budget import AttemptLedger, BudgetedTransport
from agent_harness.release_contracts import pin, sha256
from revenue_integrity.confidence_study import ConfidenceCohort
from revenue_integrity.evidence_selection import (
    Selection,
    copy_selection,
    interpretation_request,
    selection_request,
)
from revenue_integrity.paired_quality import QualityOutcome, summarize
from revenue_integrity.release_evaluation import ExtractionCase
from revenue_integrity.semantic_alignment import parse_aligned_judgment
from revenue_integrity.semantic_pilot import SemanticJudgment, model_request

FACTORIES = {
    "baseline": lambda v: model_request(v, max_context_chars=50000),
    "task_wording": interpretation_request,
    "evidence_selection": selection_request,
}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def write(path, value):
    with path.open("xb") as stream:
        stream.write(canonical(value))
        stream.flush()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--proposal", type=Path, required=True)
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--budget-root", type=Path, required=True)
    parser.add_argument("--configuration", type=Path, required=True)
    args = parser.parse_args()
    root = Path.cwd()
    assert not args.capture.exists()
    if not args.preflight_only:
        assert not subprocess.check_output(["git", "status", "--porcelain"], text=True).strip()
    prepared = args.proposal
    proposal = json.loads((prepared / "proposal.json").read_bytes())
    private = json.loads((prepared / "evaluator-only-cases.json").read_bytes())
    models = json.loads((prepared / "model-only-requests.json").read_bytes())
    schedule = json.loads((prepared / "schedule.json").read_bytes())
    source = ConfidenceCohort.model_validate_json(
        (prepared.parent / "confidence-target-study-2026-10-27-v1/cohort.json").read_bytes()
    )
    assert pin(source) == proposal["source_cohort_sha256"]
    source_cases = {c.input.case_id: c for c in source.cases}
    cases = {
        r["ordinal"]: ExtractionCase.model_validate_json(json.dumps(r["case"])) for r in private
    }
    assert len(cases) == 12 and len({c.target.family_id for c in cases.values()}) == 12
    assert sum(not c.target.impossible for c in cases.values()) == 6
    assert all(source_cases[c.input.case_id] == c for c in cases.values())
    byrequest = {}
    for row in models:
        case = cases[row["ordinal"]]
        expected = FACTORIES[row["variant"]](case.input)
        request = ModelRequest.model_validate_json(json.dumps(row["request"]))
        assert request == expected
        byrequest[(row["ordinal"], row["variant"])] = request
    assert len(byrequest) == 36 and len({pin(r) for r in byrequest.values()}) == 36
    assert (
        len(schedule) == 72
        and len({(r["ordinal"], r["variant"], r["trial_id"]) for r in schedule}) == 72
    )
    for row in schedule:
        assert pin(byrequest[(row["ordinal"], row["variant"])]) == row["request_sha256"]
    canaries = canary_requests()
    worker = GeminiWorker("invented-preflight-key", free_tier_confirmed=True)
    assert not worker.flash_comparison
    for request in (*canaries, *byrequest.values()):
        contents, config = request_payload(request, flash_comparison=worker.flash_comparison)
        assert contents and config.max_output_tokens == 512
        config.model_dump_json(exclude_none=True)
        for content in contents:
            content.model_dump_json(exclude_none=True)
    # Real pinned SDK, constructed HTTP, actual second-canary schema: no credentials/network.
    seen = []

    def mocked(req):
        seen.append(req)
        body = json.loads(req.content)
        assert body["generationConfig"]["maxOutputTokens"] == 512
        return httpx.Response(
            200,
            json={
                "modelVersion": canaries[1].model,
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
        "invented-preflight-key",
        free_tier_confirmed=True,
        http_transport=httpx.MockTransport(mocked),
    ).generate(canaries[1])
    assert len(seen) == 1 and proof.failure is None and proof.usage.input_tokens == 10
    if args.preflight_only:
        print(
            json.dumps(
                {
                    "actual_requests_preflighted": 38,
                    "sdk_fake_wire_exchanges": 1,
                    "provider_calls": 0,
                    "ledger_mutations": 0,
                }
            ),
            flush=True,
        )
        return
    config_path = args.configuration
    cfg = dict(
        line.split("=", 1)
        for line in config_path.read_text().splitlines()
        if "=" in line and not line.startswith("#")
    )
    key = cfg["GEMINI_API_KEY"].strip().strip("\"'")
    assert cfg["GEMINI_FREE_TIER_CONFIRMED"].strip().lower() in ("true", "1", "yes")
    scope = sha256(
        canonical(
            {
                "configuration_reference": str(config_path),
                "credential_sha256": sha256(key.encode()),
                "meaning": (
                    "operator-selected-credential-association-not-provider-verified-cloud-project"
                ),
            }
        )
    )
    b = args.budget_root
    external = json.loads((b / "external-pin.json").read_bytes())
    assert "paired_extension_sha256" not in external
    old = AttemptLedger(
        b / "attempts.sqlite",
        external["allowance_sha256"],
        external["amendment_sha256"],
        external["development_extension_sha256"],
    )
    before = old.summary()
    assert (before["consumed"], before["maximum"], before["unsettled"]) == (341, 344, 0)
    args.capture.mkdir(exist_ok=False)
    (args.capture / "rows").mkdir()
    tables = (
        "authorization",
        "amendments",
        "development_extensions",
        "development_slots",
        "attempts",
    )
    with old.connect() as db:
        previous = {t: db.execute("SELECT * FROM " + t + " ORDER BY 1").fetchall() for t in tables}
        grant = old.authorization(db)
        assert grant.project_sha256 == scope
        backup = b / "pre-paired-418-recovery-only.sqlite"
        assert not backup.exists()
        with sqlite3.connect(backup) as destination:
            db.backup(destination)
    write(args.capture / "previous-tables.json", previous)
    source_files = [str(p) for p in (root / "harness/src/agent_harness").glob("*.py")]
    source_files += [
        str(p) for p in (root / "projects/revenue-integrity/src/revenue_integrity").glob("*.py")
    ]
    source_files += [str(Path(__file__).resolve()), str(root / "uv.lock")]
    inventory = {str(Path(f).relative_to(root)): sha256(Path(f).read_bytes()) for f in source_files}
    previous_files = {
        str(p): sha256(p.read_bytes())
        for folder in (
            prepared.parent / "confidence-target-study-2026-10-27-v1",
            prepared.parent / "remediation-development-capture-2026-10-27-v1",
            prepared.parent / "semantic-answerability-pilot-2026-10-27-v1",
        )
        for p in folder.rglob("*")
        if p.is_file()
    }
    write(args.capture / "previous-artifact-pins.json", previous_files)
    now = datetime.now(UTC)
    run_id = "revenue-paired-quality-development-v1"
    slots = [
        PairedSlot(
            case_id=sha256(f"paired-invented-canary-{i}".encode()),
            request_sha256=pin(r),
            trial_id=f"canary-{i}",
            variant="canary",
        )
        for i, r in enumerate(canaries, 1)
    ]
    slots += [
        PairedSlot(
            case_id=cases[r["ordinal"]].input.case_id,
            request_sha256=r["request_sha256"],
            trial_id=r["trial_id"],
            variant=r["variant"],
        )
        for r in schedule
    ]
    extension = PairedExtension(
        authorization_ref="owner-2026-10-27-explicit418-total;2invented-canaries+72paired-exposed-CUAD;failures-count;no-retry-fallback-release",
        original_allowance_sha256=old.allowance_sha256,
        previous_amendment_sha256=old.amendment_sha256,
        previous_development_sha256=old.development_extension_sha256,
        run_id=run_id,
        approved_at=now,
        expires_at=max(now + timedelta(days=3), grant.expires_at),
        slots=tuple(slots),
    )
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    versions = CandidateVersions(
        code_revision=revision,
        candidate="paired-quality-v1",
        data_snapshot=pin(source),
        policy="exposed-variant-comparison-not-qualification",
        environment_lock=inventory["uv.lock"],
    )
    budget = Budget(
        max_model_calls=74,
        max_tokens=74 * GEMINI_TOKEN_CEILING,
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
            business_event_id=sha256((slot.case_id + slot.variant + slot.trial_id).encode()),
            mode="fresh_candidate",
            clock=now,
            deadline=now + timedelta(hours=2),
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
    protocol = {
        "version": "paired-quality-development-plan-v1",
        "source_revision": revision,
        "starting_consumed": 341,
        "maximum_new_attempts": 74,
        "shared_maximum": 418,
        "proposal_sha256": sha256((prepared / "proposal.json").read_bytes()),
        "model_inputs_sha256": sha256((prepared / "model-only-requests.json").read_bytes()),
        "evaluator_cases_sha256": sha256((prepared / "evaluator-only-cases.json").read_bytes()),
        "schedule_sha256": sha256(canonical(complete)),
        "source_inventory_sha256": sha256(canonical(inventory)),
        "extension_sha256": pin(extension),
        "canary_gate": "both matching settled strict outputs must pass;else no domain",
        "domain_stop": (
            "first auth/quota/budget denial or three consecutive timeout/unavailable failures"
        ),
        "attempt_timeout_seconds": 55.0,
        "http_timeout_ceiling_seconds": 30,
        "minimum_spacing_seconds": 6,
        "retries": 0,
        "paid_fallback": False,
        "release_allowed": False,
    }
    for name, value in [
        ("plan.json", protocol),
        ("schedule.json", complete),
        ("source-inventory.json", inventory),
        ("extension.json", extension.model_dump(mode="json")),
    ]:
        write(args.capture / name, value)
    write(b / "paired-extension-418.json", extension.model_dump(mode="json"))
    extension_pin = append_extension(old, extension)
    assert extension_pin == pin(extension)
    updated = external | {"paired_extension_sha256": extension_pin, "maximum": 418}
    temporary = b / "external-pin-418.tmp"
    write(temporary, updated)
    temporary.replace(b / "external-pin.json")
    ledger = AttemptLedger(
        old.path,
        old.allowance_sha256,
        old.amendment_sha256,
        old.development_extension_sha256,
        extension_pin,
    )
    controls = SharedControls()
    policy = ExecutionPolicy(max_attempts=1, attempt_timeout_seconds=55.0, backoff_seconds=0.0)
    outcomes = []
    canary_results = []
    consecutive = 0
    stop = None
    bycase = {c.input.case_id: c for c in cases.values()}
    for index, row in enumerate(complete):
        assert all(
            sha256((root / name).read_bytes()) == digest for name, digest in inventory.items()
        )
        context = RunContext.model_validate_json(json.dumps(row["context"]))
        request = ModelRequest.model_validate_json(json.dumps(row["request"]))
        slot = slots[index]
        isolated = IsolatedTransport(GeminiWorker(key, free_tier_confirmed=True))
        provider = ProviderGateway(BudgetedTransport(isolated, ledger, context, scope))
        bounded = BoundedGateway(
            provider, controls, GeminiFreeAdmission(free_tier_confirmed=True), policy=policy
        )
        start = time.monotonic()
        response = bounded.generate(context, request)
        elapsed = time.monotonic() - start
        result = None
        parsed = None
        raw = None
        if slot.variant == "canary":
            passed = False
            try:
                record_canary_pass(ledger, request, response)
                passed = True
            except ValueError:
                stop = "canary_failed"
            canary_results.append(
                {
                    "ordinal": index + 1,
                    "passed": passed,
                    "failure": response.failure.code if response.failure else None,
                }
            )
        else:
            case = bycase[slot.case_id]
            decision = None
            evidence = False
            failure = response.failure.code if response.failure else None
            if response.output and response.output.content:
                try:
                    json.loads(response.output.content, object_pairs_hook=_unique_object)
                    contract = (
                        Selection if slot.variant == "evidence_selection" else SemanticJudgment
                    )
                    raw = contract.model_validate_json(response.output.content).decision
                except ValueError:
                    pass
            try:
                assert request == FACTORIES[slot.variant](case.input)
                parsed = (
                    copy_selection(case.input, request, response)
                    if slot.variant == "evidence_selection"
                    else parse_aligned_judgment(case.input, response, max_context_chars=50000)
                )
                decision = (
                    parsed.selection.decision
                    if slot.variant == "evidence_selection"
                    else parsed.judgment.decision
                )
                evidence = True
            except ValueError:
                failure = failure or "invalid_evidence_or_judgment"
            result = QualityOutcome(
                case_id=slot.case_id,
                variant=slot.variant,
                trial_id=slot.trial_id,
                decision=decision,
                raw_decision=raw,
                evidence_valid=evidence,
                failure=failure,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                cost_known=response.usage.cost is not None,
                elapsed_seconds=elapsed,
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
            "parsed": parsed.model_dump(mode="json") if parsed else None,
            "timing": isolated.last_timing.model_dump(mode="json")
            if isolated.last_timing
            else None,
            "controlled_calls": [c.model_dump(mode="json") for c in bounded.calls],
            "exchanges": [e.model_dump(mode="json") for e in provider.exchanges],
        }
        write(args.capture / "rows" / f"{index + 1:02}.json", payload)
        print(
            json.dumps(
                {
                    "scheduled_row": index + 1,
                    "variant": slot.variant,
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
        if index < 73:
            time.sleep(6)
    expected = {c.input.case_id: not c.target.impossible for c in cases.values()}
    control_ids = frozenset(
        cases[r["ordinal"]].input.case_id
        for r in private
        if r["role"] == "previously_correct_control"
    )
    report = summarize(expected, control_ids, tuple(outcomes)) | {
        "canaries": canary_results,
        "stop_reason": stop,
        "budget": ledger.summary(),
        "new_reserved_attempts": ledger.summary()["consumed"] - 341,
        "plan_sha256": sha256(canonical(protocol)),
    }
    with ledger.connect() as db:
        for table, rows in previous.items():
            clause = " WHERE serial<=341" if table == "attempts" else ""
            assert db.execute("SELECT * FROM " + table + clause + " ORDER BY 1").fetchall() == rows
    assert all(sha256(Path(name).read_bytes()) == digest for name, digest in previous_files.items())
    write(args.capture / "report.json", report)
    print(
        json.dumps(
            {
                "complete": True,
                "domain_observed": len(outcomes),
                "stop_reason": stop,
                "new_reserved_attempts": report["new_reserved_attempts"],
                "budget": ledger.summary(),
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        import traceback

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
