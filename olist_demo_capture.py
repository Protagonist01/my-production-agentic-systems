"""Prepare/capture/read back a finite demo study; no implicit provider authorization."""

import argparse
import json
import os
import sqlite3
import subprocess
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import monotonic

from agent_harness.contracts import ModelResponse
from agent_harness.gateway import DeadlineTransport

from olist_demo_acceptance import canonical, digest
from olist_demo_acceptance import prepare as prepare_references
from olist_demo_budget_readback import inspect
from olist_demo_evaluation import Observation, baselines, summarize
from olist_demo_study import Ledger, OwnerGrant, Scope, initialize, slots
from olist_demo_worker import SDKTransport, SDKWorker, environment_pin

ROOT = Path(__file__).resolve().parent


def source_pin(root: Path) -> str:
    names = subprocess.check_output(
        ["git", "ls-files", "--", "*.py", "*.sql", "uv.lock", "pyproject.toml"],
        cwd=root,
        text=True,
    ).splitlines()
    return digest(canonical({name: digest((root / name).read_bytes()) for name in sorted(names)}))


def verify_runtime(scope: Scope) -> None:
    import agent_harness
    import olist_support

    if (
        subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()
        or any(
            module.__file__ is None or not Path(module.__file__).resolve().is_relative_to(ROOT)
            for module in (agent_harness, olist_support)
        )
        or source_pin(ROOT) != scope.source_sha256
        or environment_pin() != scope.environment_sha256
    ):
        raise PermissionError("clean exact source/imports/environment required")


def write(path: Path, value: object) -> None:
    with path.open("xb") as stream:
        stream.write(canonical(value))
        stream.flush()
        os.fsync(stream.fileno())


def prepare(output: Path, ledger: Path, *, now: datetime) -> dict[str, object]:
    report = inspect(ledger)
    if any(report["unsettled_by_namespace"].values()):
        raise PermissionError("unsettled historical attempt blocks preparation")
    prepare_references(output)
    with closing(sqlite3.connect(ledger.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        project = json.loads(db.execute("SELECT document FROM authorization").fetchone()[0])[
            "project_sha256"
        ]
    scope = Scope(
        origin="provider",
        ledger_reference=str(ledger.resolve(strict=True)),
        historical_sha256=report["historical_snapshot_sha256"],
        historical_consumed=report["total_consumed"],
        retained_bound_slots=report["retained_bound_slots"],
        lifetime_ceiling=report["proposed_required_ceiling"],
        source_sha256=source_pin(ROOT),
        environment_sha256=environment_pin(),
        reference_sha256=digest((output / "references.json").read_bytes()),
        project_sha256=project,
        starts_at=now,
        expires_at=now + timedelta(days=7),
        schedule=slots(),
    )
    verify_runtime(scope)
    (output / "scope.json").write_text(scope.canonical_json(), encoding="utf-8")
    write(output / "budget-readback.json", report)
    write(output / "baselines.json", baselines())
    result = {
        "scope_sha256": digest(scope.canonical_json().encode()),
        "reference_sha256": scope.reference_sha256,
        "attempts_proposed": 146,
        "proposed_ceiling": scope.lifetime_ceiling,
        "provider_calls_authorized": 0,
        "expires_at": scope.expires_at.isoformat(),
        "source_sha256": scope.source_sha256,
        "environment_sha256": scope.environment_sha256,
        "baselines_sha256": digest((output / "baselines.json").read_bytes()),
    }
    write(output / "proposal.json", result)
    return result


def capture(
    ledger: Ledger, transport: DeadlineTransport, *, origin: str, verify: bool = True
) -> dict[str, object]:
    with closing(ledger.connect()) as db:
        scope = ledger.scope(db)
    if origin != scope.origin:
        raise PermissionError("transport origin differs from frozen scope")
    if origin == "provider" and (
        not isinstance(transport, SDKTransport)
        or transport.worker.origin != "provider"
        or transport.worker.project_sha256 != scope.project_sha256
    ):
        raise PermissionError("provider capture requires the inspected real SDK worker")
    if verify:
        verify_runtime(scope)
    elif origin != "mock":
        raise PermissionError("provider execution cannot skip readiness binding")
    for ordinal, slot in enumerate(scope.schedule, 1):
        if verify:
            verify_runtime(scope)
        start = monotonic()
        ledger.reserve(ordinal, slot.request, now=datetime.now(UTC), origin=origin)
        # Admission is committed before any process/SDK I/O. A killed parent leaves
        # an outstanding reservation; restart cannot silently resend it.
        response = transport.generate(slot.request, timeout_seconds=scope.parent_seconds)
        phase = transport.last_timing if isinstance(transport, SDKTransport) else None
        ledger.settle(
            ordinal,
            response,
            (monotonic() - start) * 1000,
            phase.canonical_json() if phase is not None else None,
        )
        with closing(ledger.connect()) as db:
            if db.execute("SELECT 1 FROM olist_demo_stop").fetchone():
                break
    return readback(ledger)


def readback(ledger: Ledger) -> dict[str, object]:
    with closing(ledger.connect()) as db:
        scope = ledger.scope(db)
        rows = db.execute(
            "SELECT ordinal,response,elapsed_ms FROM olist_demo_results ORDER BY ordinal"
        ).fetchall()
        count = db.execute("SELECT count(*) FROM olist_demo_attempts").fetchone()[0]
        stopped = bool(db.execute("SELECT 1 FROM olist_demo_stop").fetchone())
        canary_count = db.execute(
            "SELECT count(*) FROM olist_demo_results WHERE ordinal<=2 AND canary_pass=1"
        ).fetchone()[0]
        timing_rows = db.execute(
            "SELECT ordinal,process_timing FROM olist_demo_results ORDER BY ordinal"
        ).fetchall()
    if scope.origin == "provider" and source_pin(ROOT) != scope.source_sha256:
        raise PermissionError("exact study source required for provider readback")
    observations = tuple(
        Observation(
            origin=scope.origin,
            case_id=scope.schedule[ordinal - 1].case_id,
            trial=scope.schedule[ordinal - 1].trial,
            request_sha256=scope.schedule[ordinal - 1].request.fingerprint(),
            response=ModelResponse.model_validate_json(response),
            elapsed_ms=elapsed,
        )
        for ordinal, response, elapsed in rows
        if ordinal > 2
    )
    return {
        "origin": scope.origin,
        "scheduled_attempts": 146,
        "reserved_attempts": count,
        "settled_attempts": len(rows),
        "missing_attempts": 146 - count,
        "unsettled_attempts": count - len(rows),
        "stopped": stopped,
        "both_canaries_passed": canary_count == 2,
        "process_timings": [
            {"ordinal": i, "phases": json.loads(value) if value else None}
            for i, value in timing_rows
        ],
        "actual_provider_attempts": count if scope.origin == "provider" else 0,
        "model_quality_observed": scope.origin == "provider" and bool(observations),
        "domain": summarize(observations),
        "baselines": baselines(),
        "prior_history_unchanged": True,
        "scope_sha256": ledger.pin,
        "demo_release_accepted": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", type=Path)
    mode.add_argument("--capture", type=Path, help="exact prepared scope JSON")
    mode.add_argument("--readback", help="externally retained scope hash")
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--owner-grant", type=Path)
    parser.add_argument("--owner-grant-pin")
    parser.add_argument("--configuration", type=Path)
    args = parser.parse_args()
    if args.prepare:
        result = prepare(args.prepare, args.ledger, now=datetime.now(UTC))
    elif args.readback:
        result = readback(Ledger(args.ledger, args.readback))
    else:
        if not args.owner_grant or not args.owner_grant_pin or not args.configuration:
            parser.error("capture needs the separate owner grant/pin and private configuration")
        scope = Scope.model_validate_json(args.capture.read_bytes())
        if scope.origin != "provider":
            parser.error("this CLI captures provider origin only")
        verify_runtime(scope)
        grant = OwnerGrant.model_validate_json(args.owner_grant.read_bytes())
        ledger = initialize(args.ledger, scope, grant, trusted_grant_sha256=args.owner_grant_pin)
        # Only now read an already authorized private key; never echo its contents.
        from prior_auth_study_run import private_configuration

        config_path = private_configuration(args.configuration)
        values = dict(
            line.split("=", 1)
            for line in config_path.read_text().splitlines()
            if "=" in line and not line.startswith("#")
        )
        key = values["GEMINI_API_KEY"].strip().strip("\"'")
        if not key or values.get("GEMINI_FREE_TIER_CONFIRMED", "").strip().lower() not in {
            "true",
            "1",
            "yes",
        }:
            raise PermissionError("configured Free confirmation required")
        # This configured-project association is the same established private path
        # binding used by the earlier scopes; it is not a claim of billing telemetry.
        from prior_auth_study_budget import pin as association_pin

        association = association_pin(
            {
                "configuration_reference": str(config_path),
                "credential_sha256": digest(key.encode()),
                "meaning": (
                    "operator-selected-credential-association-not-provider-verified-cloud-project"
                ),
            }
        )
        if association != scope.project_sha256:
            raise PermissionError("existing project association differs")
        result = capture(ledger, SDKTransport(SDKWorker(key, association)), origin="provider")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
