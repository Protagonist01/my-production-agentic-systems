"""Explicit already-granted Gemini operations; never provisions or extends an allowance."""

import hashlib
import json
import sqlite3
import subprocess
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import psycopg
from agent_harness.contracts import Budget, CandidateVersions, RunContext
from agent_harness.gateway import ProviderGateway
from agent_harness.isolated_transport import IsolatedTransport
from agent_harness.local_services import Workspace
from prior_auth.contracts import Policy, digest
from prior_auth.review_store import ReviewStore

from prior_auth_demo_runtime import DemoWorker, Scope
from prior_auth_live_gateway import Ledger, LiveGateway, execution_pin, scope_binding
from prior_auth_operator import OperatorParser, bounded_private
from prior_auth_study_budget import pin
from prior_auth_study_run import Worker, private_configuration


def context(scope: Scope, case_id: str, trial_id: str) -> RunContext:
    return RunContext(
        run_id=scope.scope_id,
        tenant_id=scope.tenant_id,
        agent_id="prior-auth",
        case_id=case_id,
        trial_id=trial_id,
        business_event_id=digest(scope.canonical_json()),
        mode="fresh_candidate",
        clock=datetime.now(UTC),
        deadline=scope.expires_at,
        seed=0,
        budget=Budget(
            max_model_calls=scope.max_attempts,
            max_tokens=scope.max_tokens,
            max_cost=Decimal(0),
            cost_currency="USD",
        ),
        versions=CandidateVersions(
            code_revision=scope.code_revision,
            candidate=scope.candidate,
            data_snapshot=digest(scope.canonical_json()),
            policy="explicit-live-canary",
            environment_lock=scope.environment_sha256,
        ),
    )


def open_runtime(
    root: Path,
    store: ReviewStore,
    scope: Scope,
    ledger: Ledger,
    configuration: Path,
) -> LiveGateway:
    """Inspect persisted authority and actual source before loading any credential."""
    root = root.resolve(strict=True)
    if root != Path(__file__).resolve().parent:
        raise PermissionError("runtime must execute from the inspected checkout")
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True).strip():
        raise PermissionError("clean tested checkout required")
    with ledger.connect() as c:
        grant = ledger.grant(c)
    if (
        scope.mode != "fresh_candidate"
        or scope.provider_scope_sha256 != ledger.pin
        or scope_binding(scope) != grant.runtime_scope_sha256
        or execution_pin(root) != grant.execution_sha256
        or not grant.starts_at <= datetime.now(UTC) < grant.expires_at
    ):
        raise PermissionError("active exact grant/source/runtime required before credential load")
    configuration = private_configuration(configuration)
    cfg = dict(
        line.split("=", 1)
        for line in configuration.read_text().splitlines()
        if "=" in line and not line.startswith("#")
    )
    key = cfg["GEMINI_API_KEY"].strip().strip("\"'")
    if not key or cfg["GEMINI_FREE_TIER_CONFIRMED"].strip().lower() not in {"true", "1", "yes"}:
        raise PermissionError("approved Free configuration required")
    association = pin(
        {
            "configuration_reference": str(configuration),
            "credential_sha256": hashlib.sha256(key.encode()).hexdigest(),
            "meaning": (
                "operator-selected-credential-association-not-provider-verified-cloud-project"
            ),
        }
    )
    if association != grant.project_association_sha256:
        raise PermissionError("existing credential association differs")
    return LiveGateway(
        store,
        scope,
        ledger,
        ProviderGateway(IsolatedTransport(Worker(key))),
        execution_probe=lambda: execution_pin(root),
        project_association_sha256=association,
    )


def main() -> None:
    parser = OperatorParser(prog="prior_auth_live_console", description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--trial", required=True)
    parser.add_argument("--scope", required=True, type=Path)
    parser.add_argument("--ledger", required=True, type=Path)
    parser.add_argument("--grant-sha256", required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("summary")
    worker = commands.add_parser("worker")
    worker.add_argument("--configuration", required=True, type=Path)
    canary = commands.add_parser("canary")
    canary.add_argument("--configuration", required=True, type=Path)
    canary.add_argument("--policy", required=True, type=Path)
    args = parser.parse_args()
    try:
        scope = Scope.model_validate_json(bounded_private(args.scope, 2_000_000))
        ledger = Ledger(args.ledger, args.grant_sha256)
        if args.command == "summary":
            result = ledger.summary()
        else:
            workspace = Workspace(args.root.resolve())
            trial, server = workspace.load_trial(args.trial), workspace.server()

            def connect() -> psycopg.Connection[Any]:
                return server.connect_trial(trial)

            store = ReviewStore(connect)
            gateway = open_runtime(args.root, store, scope, ledger, args.configuration)
            if args.command == "worker":
                result = DemoWorker(
                    store,
                    scope,
                    gateway,
                    provider_validator=gateway.validate,
                    profiler=gateway.profiler,
                ).step()
            else:
                from prior_auth_demo_fixtures import note, requests

                policy = Policy.model_validate_json(bounded_private(args.policy, 2_000_000))
                with ledger.connect() as c:
                    grant = ledger.grant(c)
                ordinal = ledger.summary()["new_consumed"]
                if ordinal not in (0, 1):
                    raise PermissionError("no unattempted canary remains")
                slot = grant.slots[ordinal]
                value = note(slot.case_id, policy)
                planned = requests((value,), policy)
                request = next(r for r in planned[:2] if r.fingerprint() == slot.request_sha256)
                response = gateway.canary(
                    context(scope, value.case_id, "canary-" + str(ordinal + 1)),
                    request,
                    value,
                    policy,
                )
                result = {"canary": ordinal + 1, "response_failed": response.failure is not None}
            result.update(
                {
                    "provider_allowance": ledger.summary(),
                    "timing": gateway.profiler.report(),
                    "clinical_validation": False,
                }
            )
        print(json.dumps(result, sort_keys=True))
    except (ValueError, OSError, LookupError, StopIteration, psycopg.Error, sqlite3.Error) as error:
        print(json.dumps({"operation_failed": type(error).__name__, "detail": "see private state"}))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
