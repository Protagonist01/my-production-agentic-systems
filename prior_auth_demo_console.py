"""Reproducible synthetic demo setup/worker/desk. Scripted gateway only; no provider calls."""

import getpass
import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg
from agent_harness.local_services import Workspace
from prior_auth.contracts import NoteInput, Policy, digest
from prior_auth.review_auth import AuthStore, provision, setup_review
from prior_auth.review_contracts import Principal
from prior_auth.review_store import ReviewStore
from prior_auth.source_io import external

from prior_auth_demo import demo_request
from prior_auth_demo_fixtures import EDUCATION, ScriptedGateway, fake_scope, note
from prior_auth_demo_runtime import DemoWorker, Scope, provision_scope, setup
from prior_auth_demo_web import demo_app
from prior_auth_documents import normalize
from prior_auth_operator import OperatorParser, bounded_private
from prior_auth_pas import Loopback, PasClient
from prior_auth_payer_desk import PayerDesk
from prior_auth_pipeline import ImportRequest, prepare
from prior_auth_profiling import Profiler
from prior_auth_store import IntakeStore
from prior_auth_store import setup as setup_intake
from prior_auth_study_draft import verified_policy


def plan(
    policy: Policy, *, now: datetime, scenario: str
) -> tuple[ImportRequest, Scope, dict[str, str]]:
    if scenario not in {"complete", "education-wait"}:
        raise ValueError("declared demo scenario required")
    value = note(
        "demo-complete" if scenario == "complete" else "demo-education-wait",
        policy,
        missing_education=scenario == "education-wait",
    )
    request = demo_request(value.text.encode(), case_id=value.case_id)
    request = request.model_copy(
        update={
            "policy": policy,
            "registry": request.registry.model_copy(
                update={
                    "entries": (
                        request.registry.entries[0].model_copy(
                            update={"policy_sha256": value.policy_sha256}
                        ),
                    )
                }
            ),
        }
    )
    prepared = prepare(value.text.encode(), request, Profiler())
    assert prepared.note is not None
    notes: tuple[NoteInput, ...] = (prepared.note,)
    files = {
        "request.json": request.canonical_json(),
        "policy.json": policy.canonical_json(),
        "source.txt": value.text,
    }
    if scenario == "education-wait":
        text = prepared.note.text + "\n\n--- Reviewed supplemental evidence ---\n" + EDUCATION
        resumed = NoteInput.model_validate_json(
            prepared.note.model_copy(
                update={
                    "text": text,
                    "note_sha256": digest(text),
                }
            ).canonical_json()
        )
        notes += (resumed,)
        supplement = ImportRequest.model_validate_json(
            request.model_copy(
                update={
                    "document": request.document.model_copy(
                        update={
                            "document_id": "demo-education",
                            "kind": "education_record",
                        }
                    ),
                    "expected_version": 2,
                    "source_sha256": digest(EDUCATION),
                    "normalization_sha256": normalize(EDUCATION.encode(), "text").text_sha256,
                }
            ).canonical_json()
        )
        files.update(
            {"supplement.txt": EDUCATION, "supplement-request.json": supplement.canonical_json()}
        )
    scope = fake_scope("demo-citations-" + scenario, notes, policy, now=now)
    files["scope.json"] = scope.canonical_json()
    return request, scope, files


def initialize(
    root: Path,
    trial_id: str,
    directory: Path,
    policy_directory: Path,
    *,
    scenario: str = "complete",
) -> dict[str, object]:
    directory = external(directory)
    if directory.exists():
        raise ValueError("exclusive new demo directory required")
    policy = verified_policy(policy_directory)
    workspace = Workspace(root.resolve())
    if workspace.trial_path(trial_id).exists():
        raise ValueError("new isolated trial required; existing accounts/state are not replaced")
    workspace.up()
    trial = workspace.create(trial_id)
    server = workspace.server()

    def connect() -> psycopg.Connection[Any]:
        return server.connect_trial(trial)

    now = datetime.now(UTC)
    request, scope, files = plan(policy, now=now, scenario=scenario)
    prepared = prepare(files["source.txt"].encode(), request, Profiler())
    assert prepared.note is not None
    value = prepared.note
    principal = Principal(
        username="demo-reviewer",
        tenant_id="demo",
        actor_id="demo-operator",
        role="reviewer",
        case_ids=(value.case_id,),
    )
    password = getpass.getpass("New demo reviewer password (15–128 characters): ")
    with server.connect(trial.name) as admin:
        setup_review(admin, trial.name)
        setup_intake(admin, trial.name)
        setup(admin, trial.name)
        provision(admin, principal, password)
        provision_scope(admin, scope)
    directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    for name, content in files.items():
        with (directory / name).open("x", encoding="utf-8", newline="\n") as output:
            output.write(content)
    IntakeStore(connect).accept(principal, prepared, Profiler())
    manifest = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in directory.iterdir()}
    (directory / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return {
        "initialized": True,
        "case": value.case_id,
        "scenario": scenario,
        "mode": "scripted-synthetic",
        "provider_calls": 0,
        "clinical_validation": False,
        "next": "run worker, then serve and sign in",
    }


def main() -> None:
    parser = OperatorParser(prog="prior_auth_demo_console", description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--trial", required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("initialize")
    init.add_argument("--directory", required=True, type=Path)
    init.add_argument("--policy-directory", required=True, type=Path)
    init.add_argument("--scenario", choices=("complete", "education-wait"), default="complete")
    worker = commands.add_parser("worker")
    worker.add_argument("--scope", required=True, type=Path)
    serve = commands.add_parser("serve")
    serve.add_argument("--port", type=int, default=8766)
    serve.add_argument("--payer-endpoint")
    serve.add_argument("--payer-journal", type=Path)
    serve.add_argument("--binding-file", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "initialize":
            result = initialize(
                args.root, args.trial, args.directory, args.policy_directory, scenario=args.scenario
            )
        else:
            workspace = Workspace(args.root.resolve())
            trial, server = workspace.load_trial(args.trial), workspace.server()

            def connect() -> psycopg.Connection[Any]:
                return server.connect_trial(trial)

            if args.command == "worker":
                scope = Scope.model_validate_json(bounded_private(args.scope, 2_000_000))
                if scope.mode != "offline_fake":
                    raise PermissionError("this CLI cannot activate a provider scope")
                result = DemoWorker(ReviewStore(connect), scope, ScriptedGateway()).step()
                result.update({"mode": "scripted-synthetic", "provider_calls": 0})
            else:
                if not 1024 <= args.port <= 65535:
                    raise ValueError("unprivileged loopback port required")
                import uvicorn

                payer = None
                options = (args.payer_endpoint, args.payer_journal, args.binding_file)
                if any(v is not None for v in options):
                    if not all(v is not None for v in options):
                        raise ValueError(
                            "payer endpoint, private journal and binding file required together"
                        )
                    imported = ImportRequest.model_validate_json(
                        bounded_private(args.binding_file, 2_000_000)
                    )
                    payer = PayerDesk(
                        ReviewStore(connect),
                        PasClient(args.payer_journal, Loopback(args.payer_endpoint)),
                        (imported.case,),
                    )

                uvicorn.run(
                    demo_app(
                        ReviewStore(connect),
                        AuthStore(connect),
                        origin=f"http://127.0.0.1:{args.port}",
                        trial_id=trial.name,
                        payer_desk=payer,
                    ),
                    host="127.0.0.1",
                    port=args.port,
                    access_log=False,
                    log_level="warning",
                )
                return
        print(json.dumps(result, sort_keys=True))
    except (
        ValueError,
        OSError,
        LookupError,
        PermissionError,
        psycopg.Error,
        sqlite3.Error,
    ) as error:
        parser.exit(
            2, type(error).__name__ + "; inspect private demo configuration and current state\n"
        )


if __name__ == "__main__":
    main()
