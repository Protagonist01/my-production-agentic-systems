"""Authenticated local invented-document import, receipt/location inspection and worker.

No provider switch, credential loader or public upload endpoint. Use existing reviewer
account provisioning; passwords are read interactively, never through command arguments.
"""

import argparse
import getpass
import json
from pathlib import Path
from typing import Annotated, Any, Literal

import psycopg
from agent_harness.contracts import WireContract
from agent_harness.local_services import Workspace
from prior_auth.review_auth import AuthStore, setup_review
from prior_auth.review_contracts import Principal
from prior_auth.review_store import ConnectionFactory
from prior_auth.review_workflow import ReviewWorkflow
from prior_auth.source_io import external
from pydantic import Field

from prior_auth_demo import demo_request
from prior_auth_documents import MAX_BYTES, NativeTools
from prior_auth_intake_readback import IntakeReader
from prior_auth_operator_rules import VERSION, conflict_rules
from prior_auth_pipeline import ImportRequest, prepare
from prior_auth_profiling import Profiler
from prior_auth_store import IntakeStore, ProfiledReviewStore, setup


class ToolsConfig(WireContract):
    version: Literal["prior-auth-native-tools-v1"] = "prior-auth-native-tools-v1"
    pdfinfo: Path
    pdftotext: Path
    pdftoppm: Path
    tesseract: Path
    timeout_seconds: Annotated[int, Field(ge=1, le=60)] = 30

    def tools(self) -> NativeTools:
        paths = (self.pdfinfo, self.pdftotext, self.pdftoppm, self.tesseract)
        if not all(path.is_absolute() and path.is_file() for path in paths):
            raise ValueError("trusted absolute native executables required")
        return NativeTools(*paths, timeout_seconds=self.timeout_seconds)


def bounded_private(path: Path, limit: int) -> bytes:
    with external(path).open("rb") as source:
        raw = source.read(limit + 1)
    if not raw or len(raw) > limit:
        raise ValueError("private input size refused")
    return raw


def import_document(
    user: Principal,
    store: IntakeStore,
    request_path: Path,
    source: Path,
    profiler: Profiler,
    tools_path: Path | None = None,
) -> dict[str, object]:
    request = ImportRequest.model_validate_json(bounded_private(request_path, 2_000_000))
    user.require(request.case.case_id, write=True)
    if user.tenant_id != request.case.tenant_id:
        raise PermissionError("import tenant differs")
    # Scope is checked before opening the document or starting a native parser.
    tools = (
        ToolsConfig.model_validate_json(bounded_private(tools_path, 64_000)).tools()
        if tools_path
        else None
    )
    raw = bounded_private(source, MAX_BYTES)
    prepared = prepare(raw, request, profiler, tools)
    version = store.accept(user, prepared, profiler)
    return {
        "recorded": True,
        "intake": prepared.decision.outcome,
        "resulting_version": version,
        "provider_attempts": 0,
    }


def draft_demo(directory: Path) -> dict[str, object]:
    directory = external(directory)
    directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    raw = b"AHI: 18 events/hour. Study duration: 2 hours."
    request = demo_request(raw)
    principal = Principal(
        username="demo-reviewer",
        tenant_id="demo",
        actor_id="demo-operator",
        role="reviewer",
        case_ids=(request.case.case_id,),
    )
    # A fresh directory/exclusive files prevent quietly replacing a reviewed request.
    for name, content in (
        ("source.txt", raw),
        ("request.json", request.canonical_json().encode()),
        ("principal.json", principal.canonical_json().encode()),
    ):
        with (directory / name).open("xb") as output:
            output.write(content)
    return {
        "draft": "invented-demo",
        "files": 3,
        "clinical_validation": False,
        "provider_attempts": 0,
    }


def worker(connect: ConnectionFactory, profiler: Profiler, *, baseline: str) -> dict[str, object]:
    if baseline not in {"always-review", "conflict-rules-v3"}:
        raise ValueError("known offline baseline required")
    assessor = (
        conflict_rules if baseline == "conflict-rules-v3" else lambda note, policy, keys: None
    )
    result = ReviewWorkflow(ProfiledReviewStore(connect, profiler), assessor).step()
    return {
        **result,
        "baseline": VERSION if baseline == "conflict-rules-v3" else "always-review",
        "provider_attempts": 0,
        "clinical_validation": False,
    }


def authenticated(
    args: argparse.Namespace, connect: ConnectionFactory, auth: AuthStore, profiler: Profiler
) -> dict[str, object]:
    token, _csrf, user = auth.login(args.username, getpass.getpass("Reviewer password: "))
    try:
        if args.command == "import":
            return import_document(
                user, IntakeStore(connect), args.request, args.source, profiler, args.native_tools
            )
        reader = IntakeReader(connect)
        if args.command == "receipt":
            return reader.receipt(user, args.case, args.document).model_dump(mode="json")
        return reader.locate(
            user,
            args.case,
            args.document,
            note_sha256=args.note_sha,
            start=args.start,
            end=args.end,
        ).model_dump(mode="json")
    finally:
        auth.logout(token)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--trial", required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("bootstrap")
    draft = commands.add_parser("draft-demo")
    draft.add_argument("--directory", type=Path, required=True)
    ingest = commands.add_parser("import")
    ingest.add_argument("--username", required=True)
    ingest.add_argument("--request", type=Path, required=True)
    ingest.add_argument("--source", type=Path, required=True)
    ingest.add_argument("--native-tools", type=Path)
    for name in ("receipt", "locate"):
        cmd = commands.add_parser(name)
        cmd.add_argument("--username", required=True)
        cmd.add_argument("--case", required=True)
        cmd.add_argument("--document", required=True)
        if name == "locate":
            cmd.add_argument("--note-sha", required=True)
            cmd.add_argument("--start", type=int, required=True)
            cmd.add_argument("--end", type=int, required=True)
    process = commands.add_parser("worker")
    process.add_argument(
        "--baseline", choices=("always-review", "conflict-rules-v3"), default="always-review"
    )
    args = parser.parse_args()
    try:
        if args.command == "draft-demo":
            result = draft_demo(args.directory)
        else:
            workspace = Workspace(args.root.resolve())
            if args.command == "bootstrap":
                workspace.up()
                trial = (
                    workspace.load_trial(args.trial)
                    if workspace.trial_path(args.trial).exists()
                    else workspace.create(args.trial)
                )
                with workspace.server().connect(trial.name) as admin:
                    setup_review(admin, trial.name)
                    setup(admin, trial.name)
                result = {"review_store": "ready", "intake_store": "ready", "provider_attempts": 0}
            else:
                trial, server = workspace.load_trial(args.trial), workspace.server()

                def connect() -> psycopg.Connection[Any]:
                    return server.connect_trial(trial)

                profiler = Profiler()
                with profiler.span("total"):
                    result = (
                        worker(connect, profiler, baseline=args.baseline)
                        if args.command == "worker"
                        else authenticated(args, connect, AuthStore(connect), profiler)
                    )
                result = {**result, "timing": profiler.report()}
        print(json.dumps(result, sort_keys=True))
    except (ValueError, OSError, LookupError, PermissionError, psycopg.Error) as error:
        parser.error(
            type(error).__name__ + "; inspect private inputs and current case/receipt state"
        )


if __name__ == "__main__":
    main()
