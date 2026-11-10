"""Local operator-console profiling, with real psycopg semantics and no model transport."""

import argparse
import hashlib
import json
import os
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Self

import psycopg
import uvicorn
from agent_harness.local_services import Workspace
from agent_harness.postgres import Server, Trial
from olist_support.console_api import create_app
from olist_support.policy_cases import external
from olist_support.service_health import ServiceNotReady, require_ready
from olist_support.service_telemetry import ServiceTelemetry
from psycopg import Transaction
from starlette.types import ASGIApp

from olist_diagnostics import development_plan, summarize
from olist_profiling import ProfiledAuth, ProfiledCases, ProfiledHTTP, Recorder, Stage


def prepare_evaluation(output: Path) -> dict[str, str]:
    """Expose authored development proposals; no source export, calls or label acceptance."""
    from agent_harness.release_contracts import pin

    output = external(output)
    output.mkdir(mode=0o700)  # refuse existing directory; preserve earlier attempts
    plan = development_plan()
    documents = {
        "inputs.json": [
            {"case_id": c.case_id, "group": c.group, "text": c.reference.text} for c in plan.cases
        ],
        "references.json": [c.model_dump(mode="json") for c in plan.cases],
        "plan.json": plan.model_dump(mode="json"),
        "empty-report.json": summarize(plan, ()),
        "review.json": [
            {
                "case_id": c.case_id,
                "decision": "unreviewed",
                "correction": None,
                "independent_evidence": None,
            }
            for c in plan.cases
        ],
        "scope.json": {
            "plan_sha256": pin(plan),
            "purpose": "exposed_authored_development",
            "provider_calls_authorized": False,
            "qualification_accepted": False,
            "proposed_max_new_attempts": 74,
            "proposed_canaries": 2,
            "proposed_candidate_calls": 72,
            "baseline_calls": 0,
            "proposal_only": True,
            "release_allowed": False,
        },
    }
    hashes = {}
    for name, document in documents.items():
        raw = (json.dumps(document, sort_keys=True, indent=2) + "\n").encode()
        descriptor = os.open(output / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as file:
            file.write(raw)
            file.flush()
            os.fsync(file.fileno())
        hashes[name] = hashlib.sha256(raw).hexdigest()
    descriptor = os.open(output / "manifest.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as file:
        file.write(
            (json.dumps({"files": hashes, "complete": True}, sort_keys=True) + "\n").encode()
        )
        file.flush()
        os.fsync(file.fileno())
    return hashes


class ProfiledCursor(psycopg.Cursor[Any]):
    def measured(self, stage: Stage, fn: Any, *args: Any, **kwargs: Any) -> Any:
        recorder = getattr(self.connection, "recorder", None)
        return recorder.call(stage, fn, *args, **kwargs) if recorder else fn(*args, **kwargs)

    def execute(self, *args: Any, **kwargs: Any) -> Self:
        self.measured("sql_execute", super().execute, *args, **kwargs)
        return self

    def executemany(self, *args: Any, **kwargs: Any) -> None:
        self.measured("sql_execute", super().executemany, *args, **kwargs)

    def fetchone(self) -> Any:
        return self.measured("sql_fetch", super().fetchone)

    def fetchmany(self, size: int = 0) -> list[Any]:
        result: list[Any] = self.measured("sql_fetch", super().fetchmany, size)
        return result

    def fetchall(self) -> list[Any]:
        result: list[Any] = self.measured("sql_fetch", super().fetchall)
        return result


class Finalize:
    def __init__(self, manager: Any, recorder: Recorder | None):
        self.manager, self.recorder = manager, recorder

    def __enter__(self) -> Transaction:
        value: Transaction = self.manager.__enter__()
        return value

    def __exit__(self, typ: Any, value: Any, traceback: Any) -> Any:
        if self.recorder:
            return self.recorder.call("sql_finalize", self.manager.__exit__, typ, value, traceback)
        return self.manager.__exit__(typ, value, traceback)


class ProfiledConnection(psycopg.Connection[Any]):
    recorder: Recorder | None = None

    def commit(self) -> None:
        if self.recorder:
            self.recorder.call("sql_commit", super().commit)
        else:
            super().commit()

    def rollback(self) -> None:
        if self.recorder:
            self.recorder.call("sql_rollback", super().rollback)
        else:
            super().rollback()

    @contextmanager
    def transaction(
        self, savepoint_name: str | None = None, force_rollback: bool = False
    ) -> Iterator[Transaction]:
        manager = Finalize(super().transaction(savepoint_name, force_rollback), self.recorder)
        if self.recorder:
            with self.recorder.phase("sql_transaction"), manager as transaction:
                yield transaction
        else:
            with manager as transaction:
                yield transaction


def connection_factory(server: Server, trial: Trial, recorder: Recorder) -> Any:
    def connect() -> ProfiledConnection:
        with recorder.phase("sql_connect"):
            connection = ProfiledConnection.connect(
                host="127.0.0.1",
                port=server.port,
                user=trial.name,
                password=trial.password,
                dbname=trial.name,
                connect_timeout=5,
                cursor_factory=ProfiledCursor,
            )
            connection.recorder = recorder
            return connection

    return connect


class ProfileTelemetry(ServiceTelemetry):
    def __init__(self, recorder: Recorder, **kwargs: Any):
        self.recorder = recorder
        super().__init__(**kwargs)

    def snapshot(self) -> dict[str, object]:
        result = super().snapshot()
        result["stage_profile"] = self.recorder.snapshot()
        result["profile_scope"] = "operator_console_no_model_transport"
        return result


def application(
    server: Server,
    trial: Trial,
    recorder: Recorder,
    *,
    origin: str,
    revision: str,
    lock: str,
    run_limit_minor: int,
    output: Path,
) -> ASGIApp:
    connect = connection_factory(server, trial, recorder)
    with recorder.phase("startup"):
        require_ready(connect)
        app = create_app(
            ProfiledCases(connect, recorder=recorder),
            ProfiledAuth(connect, recorder),
            origin=origin,
            trial_id=trial.name,
            code_revision=revision,
            environment_lock=lock,
            run_limit_minor=run_limit_minor,
            telemetry=ProfileTelemetry(
                recorder, code_revision=revision, environment_lock=lock, output=output
            ),
        )
    return ProfiledHTTP(app, recorder)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare-evaluation", type=Path)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--trial")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--run-limit-minor", type=int)
    parser.add_argument("--profile-output", type=Path)
    parser.add_argument("--span-limit", type=int, default=4096)
    args = parser.parse_args()
    if args.prepare_evaluation:
        if any(
            x is not None
            for x in (args.root, args.trial, args.run_limit_minor, args.profile_output)
        ):
            parser.error("preparation and serving arguments must be separate")
        try:
            print(json.dumps(prepare_evaluation(args.prepare_evaluation)))
        except (ValueError, OSError) as error:
            parser.error("preparation refused: " + type(error).__name__)
        return
    if any(x is None for x in (args.root, args.trial, args.run_limit_minor, args.profile_output)):
        parser.error("serving requires root, trial, run limit and private profile output")
    if not 1024 <= args.port <= 65535:
        parser.error("explicit unprivileged loopback port required")
    try:
        root = args.root.resolve()
        workspace = Workspace(root)
        revision = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True
        ).strip()
        if subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True).strip():
            revision += "+dirty"
        lock = hashlib.sha256((root / "uv.lock").read_bytes()).hexdigest()
        app = application(
            workspace.server(),
            workspace.load_trial(args.trial),
            Recorder(limit=args.span_limit),
            origin=f"http://127.0.0.1:{args.port}",
            revision=revision,
            lock=lock,
            run_limit_minor=args.run_limit_minor,
            output=args.profile_output,
        )
        uvicorn.run(
            app,
            host="127.0.0.1",
            port=args.port,
            proxy_headers=False,
            access_log=False,
            limit_concurrency=16,
            timeout_keep_alive=5,
            timeout_graceful_shutdown=30,
            log_level="warning",
        )
    except (
        ServiceNotReady,
        ValueError,
        OSError,
        psycopg.Error,
        subprocess.SubprocessError,
    ) as error:
        parser.error("profiled console refused: " + type(error).__name__)


if __name__ == "__main__":
    main()
