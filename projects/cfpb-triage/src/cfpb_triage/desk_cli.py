"""Trusted local provisioning/import/worker entrypoints; HTTP can enqueue review only."""

import argparse
import getpass
import hashlib
import json
import secrets
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from agent_harness.local_services import Workspace

from cfpb_triage.desk_auth import AuthStore, provision, setup_review
from cfpb_triage.desk_contracts import Principal
from cfpb_triage.desk_store import DeskStore
from cfpb_triage.desk_worker import failed, step
from cfpb_triage.evaluation_store import EvaluationStore, provision_participant, setup_evaluation
from cfpb_triage.scope_routing import ScopePolicy
from cfpb_triage.source_contracts import ComplaintInput
from cfpb_triage.source_io import external_path
from cfpb_triage.triage_contracts import Decision, RouterPolicy, Taxonomy


def read_external(path: Path) -> str:
    path = external_path(path)
    if path.stat().st_size > 1_000_000:
        raise ValueError("input exceeds bound")
    return path.read_text(encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--trial", required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("bootstrap")
    diagnostic = commands.add_parser("diagnostics")
    diagnostic.add_argument("--principal", type=Path, required=True)
    diagnostic.add_argument("--reference", type=Path, required=True)
    diagnostic.add_argument("--output", type=Path, required=True)
    account = commands.add_parser("account")
    account.add_argument("--principal", type=Path, required=True)
    enroll = commands.add_parser("enroll")
    for flag in ["complaint", "taxonomy", "policy"]:
        enroll.add_argument("--" + flag, type=Path, required=True)
    enroll.add_argument("--tenant", required=True)
    enroll.add_argument("--review-ref", required=True)
    enroll.add_argument("--provenance", choices=["original", "edited", "invented"], required=True)
    worker = commands.add_parser("worker")
    worker.add_argument("--live-gemini", action="store_true")
    worker.add_argument("--code-root", type=Path)
    worker.add_argument("--langfuse", action="store_true")
    serve = commands.add_parser("serve")
    serve.add_argument("--port", type=int, default=8883)
    serve.add_argument("--evaluation-v2", action="store_true")
    commands.add_parser("evaluation-bootstrap")
    participant = commands.add_parser("evaluation-participant")
    participant.add_argument("--tenant", required=True)
    participant.add_argument("--actor", required=True)
    evaluation = commands.add_parser("evaluation-enroll")
    for flag in ("complaint", "taxonomy", "policy"):
        evaluation.add_argument("--" + flag, type=Path, required=True)
    for flag in ("tenant", "family", "actor", "review-ref"):
        evaluation.add_argument("--" + flag, required=True)
    evaluation.add_argument("--arm", choices=("manual", "assisted"), required=True)
    evaluation.add_argument(
        "--measurement-basis", choices=("human_attested", "invented", "estimated"), required=True
    )
    commands.add_parser("evaluation-worker")
    work_export = commands.add_parser("evaluation-work-export")
    work_export.add_argument("--principal", type=Path, required=True)
    work_export.add_argument("--currency", required=True)
    work_export.add_argument("--output", type=Path, required=True)
    timing_export = commands.add_parser("evaluation-timing-export")
    timing_export.add_argument("--principal", type=Path, required=True)
    timing_export.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    w = Workspace(args.root.resolve())
    s = w.server()
    t = w.load_trial(args.trial)
    store = DeskStore(lambda: s.connect_trial(t))
    if args.command == "evaluation-timing-export":
        user = Principal.model_validate_json(read_external(args.principal))
        report = EvaluationStore(store.connect).export_timings(user)
        with external_path(args.output).open("x", encoding="utf-8") as file:
            json.dump(report, file, indent=2)
    elif args.command == "evaluation-work-export":
        user = Principal.model_validate_json(read_external(args.principal))
        work_rows = EvaluationStore(store.connect).export_work(user, currency=args.currency)
        output = external_path(args.output)
        with output.open("x", encoding="utf-8") as file:
            json.dump([r.model_dump(mode="json") for r in work_rows], file, indent=2)
    elif args.command == "evaluation-bootstrap":
        with s.connect(t.name) as admin:
            setup_review(admin, t.name)
            setup_evaluation(admin, t.name)
    elif args.command == "evaluation-participant":
        with s.connect(t.name) as admin:
            provision_participant(admin, args.tenant, args.actor)
    elif args.command == "evaluation-enroll":
        EvaluationStore(store.connect).enroll_evaluation(
            args.tenant,
            ComplaintInput.model_validate_json(read_external(args.complaint)),
            Taxonomy.model_validate_json(read_external(args.taxonomy)),
            ScopePolicy.model_validate_json(read_external(args.policy)),
            family=args.family,
            actor=args.actor,
            arm=args.arm,
            review_ref=args.review_ref,
            measurement_basis=args.measurement_basis,
        )
    elif args.command == "evaluation-worker":
        from cfpb_triage.evaluation_worker import step_evaluation

        print(json.dumps(step_evaluation(EvaluationStore(store.connect))))
    elif args.command == "bootstrap":
        with s.connect(t.name) as admin:
            setup_review(admin, t.name)
    elif args.command == "account":
        user = Principal.model_validate_json(read_external(args.principal))
        with s.connect(t.name) as admin:
            provision(admin, user, getpass.getpass("New account password: "))
    elif args.command == "enroll":
        store.enroll(
            args.tenant,
            ComplaintInput.model_validate_json(read_external(args.complaint)),
            Taxonomy.model_validate_json(read_external(args.taxonomy)),
            RouterPolicy.model_validate_json(read_external(args.policy)),
            review_ref=args.review_ref,
            provenance=args.provenance,
        )
    elif args.command == "worker":
        if args.langfuse and not args.live_gemini:
            raise ValueError("--langfuse requires the live worker")
        assess = failed
        if args.live_gemini:
            if args.code_root is None:
                raise ValueError("--code-root is required for live provenance/config")
            from agent_harness.admission import GEMINI_TOKEN_CEILING, GeminiFreeAdmission
            from agent_harness.controls import BoundedGateway, ExecutionPolicy, SharedControls
            from agent_harness.gateway import ProviderGateway
            from agent_harness.integration_smoke import local_environment
            from agent_harness.isolated_transport import GeminiWorker, IsolatedTransport
            from agent_harness.offline_example import example_context

            from cfpb_triage.classifier import route
            from cfpb_triage.triage_contracts import digest_text

            code = args.code_root.resolve()
            values = local_environment(
                code,
                (
                    "GEMINI_API_KEY",
                    "GEMINI_FREE_TIER_CONFIRMED",
                    "LANGFUSE_BASE_URL",
                    "LANGFUSE_PUBLIC_KEY",
                    "LANGFUSE_SECRET_KEY",
                ),
            )
            if values.get("GEMINI_FREE_TIER_CONFIRMED", "").lower() != "true":
                raise ValueError("Free project confirmation required")
            revision = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=code, text=True
            ).strip()
            if subprocess.check_output(
                ["git", "status", "--porcelain"], cwd=code, text=True
            ).strip():
                revision += "+dirty"
            lock = hashlib.sha256((code / "uv.lock").read_bytes()).hexdigest()
            transport = ProviderGateway(
                IsolatedTransport(GeminiWorker(values["GEMINI_API_KEY"], True, True))
            )
            gateway = BoundedGateway(
                transport,
                SharedControls(),
                GeminiFreeAdmission(free_tier_confirmed=True, flash_comparison=True),
                policy=ExecutionPolicy(max_attempts=1),
            )

            def live(job: dict[str, Any]) -> Decision:
                complaint = ComplaintInput.model_validate_json(json.dumps(job["complaint"]))
                taxonomy = Taxonomy.model_validate_json(json.dumps(job["taxonomy"]))
                policy = RouterPolicy.model_validate_json(json.dumps(job["policy"]))
                now = datetime.now(UTC)
                c = example_context(revision, lock)
                c = c.model_copy(
                    update={
                        "tenant_id": job["tenant_id"],
                        "case_id": job["case_id"],
                        "agent_id": "cfpb-triage-v2",
                        "run_id": "cfpb-" + job["lease_id"],
                        "trial_id": t.trial_id,
                        "business_event_id": digest_text(
                            job["tenant_id"] + ":" + job["case_id"] + ":" + str(job["version"])
                        ),
                        "mode": "fresh_candidate",
                        "clock": now,
                        "deadline": now + timedelta(seconds=90),
                        "budget": c.budget.model_copy(
                            update={"max_model_calls": 2, "max_tokens": 2 * GEMINI_TOKEN_CEILING}
                        ),
                        "versions": c.versions.model_copy(
                            update={
                                "candidate": "cfpb-triage-v2",
                                "policy": digest_text(policy.canonical_json()),
                                "data_snapshot": digest_text(complaint.narrative),
                            }
                        ),
                    }
                )
                if not args.langfuse:
                    return route(gateway, c, complaint, taxonomy, policy)
                from agent_harness.langfuse_export import LangfuseExporter
                from agent_harness.telemetry import TraceSession

                from cfpb_triage.tracing import traced_route

                trace = TraceSession(
                    LangfuseExporter(
                        values["LANGFUSE_BASE_URL"],
                        values["LANGFUSE_PUBLIC_KEY"],
                        values["LANGFUSE_SECRET_KEY"],
                    ),
                    secrets.token_bytes(32),
                )
                result = traced_route(
                    trace, gateway, c, complaint, taxonomy, policy, provenance=job["provenance"]
                )
                assert trace.health is not None
                print(trace.health.canonical_json())
                return result

            assess = live
        print(json.dumps(step(store, assess)))
    elif args.command == "diagnostics":
        from cfpb_triage.diagnostics import Profile, compare, profile

        user = Principal.model_validate_json(read_external(args.principal))
        rows = []
        for case_id in user.case_ids:
            try:
                rows.append(store.snapshot(user, case_id))
            except LookupError:
                continue
        reference = Profile.model_validate_json(read_external(args.reference))
        output = external_path(args.output)
        with output.open("x", encoding="utf-8") as file:
            json.dump(compare(reference, profile(rows)), file, indent=2)
    elif args.command == "serve":
        if not 1024 <= args.port <= 65535:
            raise ValueError("port outside allowed range")
        import uvicorn

        from cfpb_triage.desk_api import create_app

        app = create_app(
            store,
            AuthStore(lambda: s.connect_trial(t)),
            origin=f"http://127.0.0.1:{args.port}",
            trial_id=t.trial_id,
            evaluation=EvaluationStore(store.connect) if args.evaluation_v2 else None,
        )
        uvicorn.run(app, host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, PermissionError, LookupError, OSError):
        raise SystemExit(
            "CFPB command failed; verify scope, pins and private local state"
        ) from None
