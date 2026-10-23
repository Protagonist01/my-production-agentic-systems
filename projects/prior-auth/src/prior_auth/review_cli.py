"""Trusted redacted import/provisioning, one bounded worker step and loopback reviewer desk."""

import argparse
import getpass
import hashlib
import json
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import psycopg
from agent_harness.local_services import Workspace

from prior_auth.contracts import NoteInput, Policy, Redaction
from prior_auth.redaction import redact
from prior_auth.review_auth import AuthStore, provision, setup_review
from prior_auth.review_contracts import Principal, RedactedDelivery
from prior_auth.review_store import ReviewStore


def live_assessor(root: Path) -> Any:
    from agent_harness.admission import GEMINI_TOKEN_CEILING, GeminiFreeAdmission
    from agent_harness.controls import BoundedGateway, ExecutionPolicy, SharedControls
    from agent_harness.gateway import ProviderGateway
    from agent_harness.integration_smoke import local_environment
    from agent_harness.isolated_transport import GeminiWorker, IsolatedTransport
    from agent_harness.offline_example import example_context

    from prior_auth.candidate import PROMPT_VERSION, extract

    values = local_environment(root)
    confirmed = values["GEMINI_FREE_TIER_CONFIRMED"].lower() == "true"
    if not values["GEMINI_API_KEY"] or not confirmed:
        raise ValueError("configured billing-disabled Free Gemini project required")
    gateway = BoundedGateway(
        ProviderGateway(IsolatedTransport(GeminiWorker(values["GEMINI_API_KEY"], confirmed))),
        SharedControls(),
        GeminiFreeAdmission(free_tier_confirmed=confirmed),
        policy=ExecutionPolicy(max_attempts=1),
    )
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True).strip():
        revision += "+dirty"
    lock = hashlib.sha256((root / "uv.lock").read_bytes()).hexdigest()

    def evaluate(note: Any, policy: Any, keys: Any) -> Any:
        now = datetime.now(UTC)
        context = example_context(revision, lock)
        context = context.model_copy(
            update=dict(
                tenant_id=note.tenant_id,
                case_id=note.case_id,
                run_id="prior-review-" + uuid4().hex,
                mode="fresh_candidate",
                clock=now,
                deadline=now + timedelta(seconds=240),
                budget=context.budget.model_copy(
                    update=dict(
                        max_model_calls=len(keys), max_tokens=len(keys) * GEMINI_TOKEN_CEILING
                    )
                ),
                versions=context.versions.model_copy(
                    update=dict(
                        candidate=PROMPT_VERSION,
                        data_snapshot=note.note_sha256,
                        policy=note.policy_sha256,
                    )
                ),
            )
        )
        return extract(gateway, context, note, policy, criteria_subset=keys)

    return evaluate


def reviewed_text(raw: Path, mapping: Path) -> str:
    """No implicit identifier detector: a human-reviewed exact span mapping is required."""
    from prior_auth.source_io import external

    text = external(raw).read_text(encoding="utf-8")
    if len(text) > 100000:
        raise ValueError("raw input exceeds note limit")
    rows = json.loads(external(mapping).read_bytes())
    spans = tuple(Redaction.model_validate_json(json.dumps(row)) for row in rows)
    return redact(text, spans)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--trial", required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("bootstrap")
    account = commands.add_parser("account")
    account.add_argument("--principal", type=Path, required=True)
    enroll = commands.add_parser("enroll")
    enroll.add_argument("--note", type=Path, required=True)
    enroll.add_argument("--policy", type=Path, required=True)
    enroll.add_argument("--review-ref", required=True)
    for name in ("document", "policy"):
        cmd = commands.add_parser(name)
        cmd.add_argument("--username", required=True)
        cmd.add_argument("--case", required=True)
        cmd.add_argument("--version", type=int, required=True)
        if name == "document":
            cmd.add_argument("--raw", type=Path, required=True)
            cmd.add_argument("--redactions", type=Path, required=True)
            cmd.add_argument("--review-ref", required=True)
            cmd.add_argument("--delivery-id", required=True)
        else:
            cmd.add_argument("--input", type=Path, required=True)
    worker = commands.add_parser("worker")
    worker.add_argument("--live-gemini", action="store_true")
    serve = commands.add_parser("serve")
    serve.add_argument("--port", type=int, default=8881)
    args = parser.parse_args()
    try:
        root = args.root.resolve()
        workspace = Workspace(root)
        if args.command == "bootstrap":
            workspace.up()
            trial = (
                workspace.load_trial(args.trial)
                if workspace.trial_path(args.trial).exists()
                else workspace.create(args.trial)
            )
            with workspace.server().connect(trial.name) as admin:
                setup_review(admin, trial.name)
            print('{"review_store":"ready"}')
            return
        trial, server = workspace.load_trial(args.trial), workspace.server()

        def connect() -> psycopg.Connection[Any]:
            return server.connect_trial(trial)

        store, auth = ReviewStore(connect), AuthStore(connect)
        if args.command == "account":
            user = Principal.model_validate_json(args.principal.read_bytes())
            password = getpass.getpass("New reviewer password (15-128 characters): ")
            if password != getpass.getpass("Repeat password: "):
                raise ValueError("password confirmation differs")
            with server.connect(trial.name) as admin:
                provision(admin, user, password)
            print('{"account":"provisioned"}')
        elif args.command == "enroll":
            from prior_auth.source_io import external

            note = NoteInput.model_validate_json(external(args.note).read_bytes())
            policy = Policy.model_validate_json(external(args.policy).read_bytes())
            store.enroll(note, policy, review_ref=args.review_ref)
            print('{"case":"enrolled","status":"assessing"}')
        elif args.command in ("document", "policy"):
            token, csrf, user = auth.login(args.username, getpass.getpass("Reviewer password: "))
            try:
                if args.command == "document":
                    text = reviewed_text(args.raw, args.redactions)
                    version = store.deliver(
                        user,
                        args.case,
                        RedactedDelivery(
                            delivery_id=args.delivery_id,
                            expected_version=args.version,
                            text=text,
                            review_ref=args.review_ref,
                        ),
                    )
                else:
                    from prior_auth.source_io import external

                    policy = Policy.model_validate_json(external(args.input).read_bytes())
                    version = store.replace_policy(user, args.case, policy, version=args.version)
                print(json.dumps({"recorded_version": version}))
            finally:
                auth.logout(token)
        elif args.command == "worker":
            from prior_auth.review_workflow import ReviewWorkflow

            # Omitted opt-in is explicit qualified-review routing, not fake extraction.
            assessor = live_assessor(root) if args.live_gemini else lambda note, policy, keys: None
            print(json.dumps(ReviewWorkflow(store, assessor).step()))
        else:
            import uvicorn

            from prior_auth.review_api import create_app

            if not 1024 <= args.port <= 65535:
                raise ValueError("unprivileged loopback port required")
            uvicorn.run(
                create_app(
                    store, auth, origin=f"http://127.0.0.1:{args.port}", trial_id=trial.name
                ),
                host="127.0.0.1",
                port=args.port,
                access_log=False,
            )
    except (ValueError, OSError, LookupError, PermissionError, psycopg.Error) as error:
        parser.error(
            type(error).__name__ + "; inspect private configuration and current case state"
        )


if __name__ == "__main__":
    main()
