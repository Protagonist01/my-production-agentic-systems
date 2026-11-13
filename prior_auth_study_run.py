"""Owner-approved PA constructed development run; no resume/retry or clinical release."""

import argparse
import hashlib
import json
import platform
import sqlite3
import subprocess
import sys
import time
from contextlib import closing
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from agent_harness.contracts import (
    Budget,
    CandidateVersions,
    ModelRequest,
    ModelResponse,
    RunContext,
)
from agent_harness.gateway import ProviderGateway
from agent_harness.isolated_transport import IsolatedTransport
from prior_auth.assessment import assess
from prior_auth.candidate import QuoteClaim, extract
from prior_auth.contracts import NoteInput, Policy, digest
from prior_auth.source import matching_spans
from prior_auth.source_io import external

from prior_auth_study_budget import Grant, Slot, historical_snapshot, initialize, pin

PACKET = "119a2297ce220a5063e28755e99e58d93f591ced672a54d3930264bb890f1824"
APPROVED = datetime(2026, 11, 13, 1, 5, 34, tzinfo=UTC)
# Conservatively earlier than seven days after the observed approval.
EXPIRES = datetime(2026, 11, 20, tzinfo=UTC)


def write(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as output:
        output.write(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")
        output.flush()


def load_packet(directory: Path) -> tuple[dict[str, NoteInput], Policy, list[dict[str, Any]]]:
    directory = external(directory)
    manifest_raw = (directory / "manifest.json").read_bytes()
    if hashlib.sha256(manifest_raw).hexdigest() != PACKET:
        raise ValueError("owner-approved v2 packet pin differs")
    manifest = json.loads(manifest_raw)
    root = Path(__file__).resolve().parent
    for name, expected in manifest["artifacts"].items():
        if (
            Path(name).name != name
            or hashlib.sha256((directory / name).read_bytes()).hexdigest() != expected
        ):
            raise ValueError("approved packet artifact differs")
    for name, expected in manifest["code"].items():
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != expected:
            raise ValueError("approved request-builder code/lock differs")
    if manifest["environment"] != {"python": sys.version, "platform": platform.platform()}:
        raise ValueError("approved request-preparation environment differs")
    proposal = json.loads((directory / "proposal.json").read_bytes())
    if not proposal["policy_artifact_ready"] or proposal["attempts_max"] != 170:
        raise ValueError("CMS policy/fixed attempt proposal required")
    notes = {
        n.case_id: n
        for n in (
            NoteInput.model_validate_json(json.dumps(row))
            for row in json.loads((directory / "inputs.json").read_bytes())
        )
    }
    if len(notes) != 12 or any(n.provenance != "invented" for n in notes.values()):
        raise ValueError("approved invented population differs")
    policy = Policy.model_validate_json((directory / "policy.json").read_bytes())
    rows = json.loads((directory / "request-plan.json").read_bytes())
    scheduled = [row for row in rows if row["retrieval_has_request"]]
    if len(rows) != 168 or len(scheduled) != 166:
        raise ValueError("approved retrieval schedule differs")
    # Two representative canaries reuse only the already approved invented input
    # and exact request bytes; they do not introduce new export content.
    canaries = [dict(scheduled[i], phase="canary") for i in (0, 1)]
    schedule = canaries + [dict(row, phase="domain") for row in scheduled]
    return notes, policy, schedule


def inventory(root: Path) -> dict[str, str]:
    # Include all executable workspace source, not only the candidate request builder.
    names = subprocess.check_output(
        ["git", "ls-files", "--", "*.py", "uv.lock", "pyproject.toml"], cwd=root, text=True
    ).splitlines()
    for name in ("prior_auth_study_budget.py", "prior_auth_study_run.py"):
        if name not in names:
            names.append(name)
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in sorted(names)}


@dataclass(frozen=True)
class Worker:
    api_key: str = field(repr=False)

    def generate(self, request: ModelRequest, *, timeout_seconds: float) -> ModelResponse:
        from agent_harness.gemini import GeminiTransport

        return GeminiTransport(
            self.api_key, free_tier_confirmed=True, http_timeout_seconds=90
        ).generate(request, timeout_seconds=min(90, timeout_seconds))


def parse(response: ModelResponse, request: ModelRequest, note: NoteInput) -> QuoteClaim | None:
    if response.failure is not None or response.output is None or response.output.tool_calls:
        return None
    try:
        from agent_harness.cases import _unique_object

        json.loads(response.output.content or "", object_pairs_hook=_unique_object)
        claim = QuoteClaim.model_validate_json(response.output.content or "")
        expected = json.loads(request.messages[1].content or "")["criterion"]["criterion_id"]
        if claim.criterion_id != expected or (claim.state == "met" and not claim.quotes):
            return None
        for quote in claim.quotes:
            matching_spans(note.text, quote)
        return claim
    except (ValueError, KeyError, TypeError):
        return None


class Captured:
    def __init__(self, responses: dict[str, ModelResponse]) -> None:
        self.responses = responses

    def generate(self, context: RunContext, request: ModelRequest) -> ModelResponse:
        return self.responses[request.fingerprint()]


def decisions(
    notes: dict[str, NoteInput],
    policy: Policy,
    schedule: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    context: RunContext,
) -> list[dict[str, object]]:
    result = []
    for note in notes.values():
        for trial in range(2):
            expected = [
                i + 1
                for i, row in enumerate(schedule)
                if row["phase"] == "domain"
                and row["case_id"] == note.case_id
                and row["trial"] == trial
            ]
            available = {r["ordinal"]: r for r in rows if r["ordinal"] in expected}
            output = None
            if len(available) == len(expected):
                replay = Captured(
                    {
                        r["request_sha256"]: ModelResponse.model_validate_json(
                            json.dumps(r["response"])
                        )
                        for r in available.values()
                    }
                )
                local = context.model_copy(update={"case_id": note.case_id, "trial_id": str(trial)})
                candidate = extract(replay, local, note, policy)
                output = assess(note, policy, candidate).model_dump(mode="json")
            result.append(
                {
                    "case_id": note.case_id,
                    "trial": trial,
                    "scheduled_requests": len(expected),
                    "observed_requests": len(available),
                    "checked_result": output,
                    "clinical_validation": False,
                }
            )
    return result


def run(packet: Path, capture: Path, ledger_path: Path, configuration: Path) -> dict[str, object]:
    root = Path(__file__).resolve().parent
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True).strip():
        raise ValueError("clean tested checkout required")
    notes, policy, schedule = load_packet(packet)
    capture = external(capture)
    if capture.exists():
        raise ValueError("new capture required; no implicit resume")
    now = datetime.now(UTC)
    if not APPROVED <= now < EXPIRES:
        raise ValueError("owner scope expired/not active")
    source = inventory(root)
    execution = {
        "code": source,
        "environment": {"python": sys.version, "platform": platform.platform()},
        "packet_sha256": PACKET,
        "schedule": schedule,
        "http_seconds": 90,
        "parent_seconds": 110,
        "run_seconds": 18000,
        "total_tokens": 2000000,
        "attempts_max": 170,
        "no_retry": True,
        "paid_fallback": False,
    }
    # Credentials are loaded only after exact packet/source/environment preflight.
    configuration = external(configuration)
    cfg = dict(
        line.split("=", 1)
        for line in configuration.read_text().splitlines()
        if "=" in line and not line.startswith("#")
    )
    key = cfg["GEMINI_API_KEY"].strip().strip("\"'")
    if not key or cfg["GEMINI_FREE_TIER_CONFIRMED"].strip().lower() not in {"true", "1", "yes"}:
        raise ValueError("approved Free configuration required")
    association = pin(
        {
            "configuration_reference": str(configuration),
            "credential_sha256": hashlib.sha256(key.encode()).hexdigest(),
            "meaning": (
                "operator-selected-credential-association-not-provider-verified-cloud-project"
            ),
        }
    )
    ledger_path = external(ledger_path)
    with sqlite3.connect(ledger_path.as_uri() + "?mode=ro", uri=True) as db:
        history = historical_snapshot(db)
        old = json.loads(db.execute("SELECT document FROM authorization").fetchone()[0])
        if old["project_sha256"] != association:
            raise ValueError("configured credential association differs from shared ledger")
    slots = tuple(
        Slot(
            ordinal=i + 1,
            phase=row["phase"],
            case_id=row["case_id"],
            trial=row["trial"],
            criterion=row["criterion"],
            request_sha256=row["request_sha256"],
        )
        for i, row in enumerate(schedule)
    )
    grant = Grant(
        packet_sha256=PACKET,
        historical_sha256=history,
        project_sha256=association,
        execution_sha256=pin(execution),
        approved_at=APPROVED,
        expires_at=EXPIRES,
        slots=slots,
    )
    capture.mkdir(mode=0o700, parents=True)
    write(capture / "execution.json", execution)
    write(capture / "grant.json", grant.model_dump(mode="json"))
    # Local recovery copy only; never use a historical copy as a reset allowance.
    with closing(sqlite3.connect(ledger_path.as_uri() + "?mode=ro", uri=True)) as db:
        with closing(sqlite3.connect(capture / "historical-recovery-only.sqlite")) as backup:
            db.backup(backup)
    ledger = initialize(ledger_path, grant)
    (capture / "scope.sha256").write_text(ledger.scope_pin + "\n", encoding="ascii")
    write(
        ledger_path.parent / "prior-auth-784-external-pin.json",
        {
            "scope_sha256": ledger.scope_pin,
            "capture": str(capture),
            "maximum": 784,
            "meaning": "PA extension in same ledger; old external marker and stopped scope unchanged",
        },
    )
    print(
        json.dumps(
            {
                "phase": "grant_committed",
                "scope_sha256": ledger.scope_pin,
                "lifetime_maximum": 784,
                "historical_consumed": 447,
            }
        ),
        flush=True,
    )
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    context = RunContext(
        run_id="prior-auth-development-2026-11-13-v1",
        tenant_id="demo",
        agent_id="prior-auth",
        case_id="placeholder",
        trial_id="0",
        business_event_id=PACKET,
        mode="fresh_candidate",
        clock=now,
        deadline=min(now + timedelta(seconds=18000), EXPIRES),
        seed=13,
        budget=Budget(
            max_model_calls=170, max_tokens=2000000, max_cost=Decimal(0), cost_currency="USD"
        ),
        versions=CandidateVersions(
            code_revision=revision,
            candidate="legacy-criterion-v3",
            data_snapshot=PACKET,
            policy=digest(policy.canonical_json()),
            environment_lock=source["uv.lock"],
        ),
    )
    rows: list[dict[str, Any]] = []
    run_end = time.monotonic() + 18000
    for ordinal, row in enumerate(schedule, 1):
        if (
            inventory(root) != source
            or datetime.now(UTC) >= context.deadline
            or time.monotonic() >= run_end
        ):
            ledger.stop("execution_changed_or_expired")
            break
        request = ModelRequest.model_validate_json(json.dumps(row["request"]))
        if request.fingerprint() != row["request_sha256"]:
            raise ValueError("frozen request differs")
        try:
            ledger.reserve(ordinal, request.fingerprint(), now=datetime.now(UTC))
        except ValueError:
            ledger.stop("admission_denied")
            break
        current = context.model_copy(
            update={"case_id": row["case_id"], "trial_id": str(row["trial"])}
        )
        isolated = IsolatedTransport(Worker(key))
        started = time.monotonic()
        response = ProviderGateway(isolated).generate(
            current,
            request,
            timeout_seconds=min(
                110, (context.deadline - datetime.now(UTC)).total_seconds(), run_end - started
            ),
        )
        elapsed = time.monotonic() - started
        claim = parse(response, request, notes[row["case_id"]])
        usage = response.usage
        tokens = (
            None
            if usage.input_tokens is None or usage.output_tokens is None
            else usage.input_tokens + usage.output_tokens
        )
        passed = (
            row["phase"] == "canary"
            and tokens is not None
            and claim is not None
            and claim.state == "met"
            and bool(claim.quotes)
        )
        stop = (
            "canary_failed"
            if row["phase"] == "canary" and not passed
            else (
                "provider_failure"
                if response.failure is not None
                else "usage_unknown"
                if tokens is None
                else None
            )
        )
        observation = {
            "ordinal": ordinal,
            "phase": row["phase"],
            "case_id": row["case_id"],
            "trial": row["trial"],
            "criterion": row["criterion"],
            "request_sha256": request.fingerprint(),
            "response": response.model_dump(mode="json"),
            "parsed": claim.model_dump(mode="json") if claim else None,
            "elapsed_seconds": elapsed,
            "process_timing": isolated.last_timing.model_dump(mode="json")
            if isolated.last_timing
            else None,
            "canary_pass": passed,
            "stop": stop,
        }
        ledger.settle(ordinal, observation, tokens=tokens, canary_pass=passed, stop=stop)
        write(capture / f"attempt-{ordinal:03}.json", observation)
        rows.append(observation)
        print(
            json.dumps(
                {
                    "ordinal": ordinal,
                    "phase": row["phase"],
                    "failure": response.failure.code if response.failure else None,
                    "parsed": claim is not None,
                    "stop": stop,
                }
            ),
            flush=True,
        )
        if ledger.summary()["stop"] is not None:
            break
        if ordinal < len(schedule):
            time.sleep(6)
    outputs = decisions(notes, policy, schedule, rows, context)
    write(capture / "checked-decisions.json", outputs)
    report = {
        "version": "prior-auth-development-actual-v1",
        "packet_sha256": PACKET,
        "scope_sha256": ledger.scope_pin,
        "ledger": ledger.summary(),
        "scheduled_requests": len(schedule),
        "observed_requests": len(rows),
        "missing_requests": len(schedule) - len(rows),
        "scheduled_case_trials": 24,
        "complete_case_trials": sum(r["checked_result"] is not None for r in outputs),
        "clinical_qualified": False,
        "release_allowed": False,
        "cost_basis": "owner-confirmed Free; provider billing remains unverified",
    }
    write(capture / "report.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("packet", "capture", "ledger", "configuration"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    try:
        run(args.packet, args.capture, args.ledger, args.configuration)
    except Exception as error:
        print("PA study refused: " + type(error).__name__, file=sys.stderr)
        raise SystemExit(1) from None
