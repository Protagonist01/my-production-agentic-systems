"""Opt-in local Supply runtime. Delegates canonical policy; never exports content."""

import argparse
import json
import os
import secrets
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Self

import psycopg
import uvicorn
from agent_harness.local_services import Workspace
from psycopg import Transaction
from starlette.types import ASGIApp, Message, Receive, Scope, Send
from supply_chain.action_contracts import Action, Grant, Shipment
from supply_chain.console_api import create_app
from supply_chain.console_auth import AuthStore
from supply_chain.console_contracts import (
    Confirmation,
    Decision,
    IncidentContext,
    Notice,
    Principal,
    Selection,
)
from supply_chain.console_service import ConsoleService
from supply_chain.events import EventHandlers, build_functions
from supply_chain.notices import NoticeStore
from supply_chain.operations import ConnectionFactory, OperationStore
from supply_chain.simulator import allocate
from supply_chain.workflow import Planner, SupplyWorkflow

from supply_profiling import Recorder


class ProfiledCursor(psycopg.Cursor[Any]):
    def measured(self, stage: str, fn: Any, *args: Any, **kwargs: Any) -> Any:
        recorder = getattr(self.connection, "recorder", None)
        return recorder.call(stage, fn, *args, **kwargs) if recorder else fn(*args, **kwargs)

    def execute(self, *args: Any, **kwargs: Any) -> Self:
        query = args[0] if args else kwargs.get("query")
        # Fixed metadata only; never render composed SQL or retain query/parameters.
        locking = isinstance(query, str) and "FOR UPDATE" in query.upper()
        self.measured(
            "sql_lock_statement" if locking else "sql_execute", super().execute, *args, **kwargs
        )
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
        manager = super().transaction(savepoint_name, force_rollback)
        recorder = self.recorder
        if recorder is None:
            with manager as tx:
                yield tx
            return
        with recorder.phase("sql_transaction"):
            tx = manager.__enter__()
            try:
                yield tx
            except BaseException as error:
                with recorder.phase("sql_finalize"):
                    suppressed = manager.__exit__(type(error), error, error.__traceback__)
                if not suppressed:
                    raise
            else:
                with recorder.phase("sql_finalize"):
                    manager.__exit__(None, None, None)


def connection_factory(recorder: Recorder, **kwargs: Any) -> ConnectionFactory:
    """Trusted server connection arguments; never store DSN, SQL, credentials or rows."""
    if "cursor_factory" in kwargs or "connection_factory" in kwargs:
        raise ValueError("profiled connection owns its cursor factory")

    def connect() -> ProfiledConnection:
        with recorder.phase("sql_connect"):
            connection = ProfiledConnection.connect(cursor_factory=ProfiledCursor, **kwargs)
            connection.recorder = recorder
            return connection

    return connect


class ProfiledAuth(AuthStore):
    def __init__(self, connect: ConnectionFactory, recorder: Recorder, **kwargs: Any):
        self.recorder = recorder
        super().__init__(connect, **kwargs)

    def authenticate(self, token: str, csrf: str | None = None) -> Principal:
        return self.recorder.call("authenticate", super().authenticate, token, csrf)

    def login(self, username: str, password: str) -> tuple[str, str, Principal]:
        return self.recorder.call("login", super().login, username, password)


class ProfiledStore(OperationStore):
    def __init__(self, connect: ConnectionFactory, recorder: Recorder, **kwargs: Any):
        self.recorder = recorder
        super().__init__(connect, **kwargs)

    @contextmanager
    def _connection(self) -> Iterator[psycopg.Connection[Any]]:
        with self.recorder.phase("database_context"), super()._connection() as connection:
            yield connection

    def portfolio(self, grant: Grant, event: str) -> tuple[dict[str, Any], tuple[Shipment, ...]]:
        return self.recorder.call("shipment_read", super().portfolio, grant, event)


class ProfiledNotices(NoticeStore):
    def __init__(self, connect: ConnectionFactory, recorder: Recorder):
        self.recorder = recorder
        super().__init__(connect)

    def context(self, principal: Principal, event: str) -> IncidentContext | None:
        return self.recorder.call("alert_read", super().context, principal, event)

    def append(self, notice: Notice) -> None:
        # Includes persistence; body construction is part of the containing board span.
        self.recorder.call("notice_build", super().append, notice)

    def list(self, principal: Principal, event: str) -> tuple[Notice, ...]:
        return self.recorder.call("notice_list", super().list, principal, event)

    def acknowledge(self, principal: Principal, notice_id: str) -> None:
        self.recorder.call("notice_read", super().acknowledge, principal, notice_id)


class ProfiledWorkflow(SupplyWorkflow):
    def __init__(self, store: OperationStore, recorder: Recorder, planner: Planner = allocate):
        self.recorder = recorder

        def timed(
            shipments: tuple[Shipment, ...], budget_minor: int, *, now: datetime
        ) -> dict[str, Action]:
            return recorder.call("planning", planner, shipments, budget_minor, now=now)

        super().__init__(store, timed)


class ProfiledService(ConsoleService):
    def __init__(self, store: OperationStore, notices: NoticeStore, recorder: Recorder):
        self.recorder = recorder
        super().__init__(store, notices)

    def board(self, principal: Principal, event: str) -> dict[str, Any]:
        with self.recorder.incident(principal.tenant_id, event):
            return self.recorder.call("board", super().board, principal, event)

    def assess(self, principal: Principal, event: str) -> dict[str, Any]:
        with self.recorder.phase("assessment", operation="assessment"):
            if principal.role != "operator":
                raise PermissionError("operator required")
            with self.recorder.phase("scope_check"):
                grant = principal.grant(event)
            with self.recorder.incident(principal.tenant_id, event):
                ProfiledWorkflow(self.store, self.recorder).run(
                    grant, event, "console-" + secrets.token_hex(12)
                )
                return self.board(principal, event)

    def review(self, principal: Principal, value: Decision) -> dict[str, Any]:
        with self.recorder.phase("review", operation="review"):
            return super().review(principal, value)

    def apply(self, principal: Principal, value: Selection) -> dict[str, Any]:
        with self.recorder.phase("apply", operation="apply"):
            return super().apply(principal, value)

    def confirm(self, principal: Principal, value: Confirmation) -> dict[str, Any]:
        with self.recorder.phase("confirm", operation="confirm"):
            return super().confirm(principal, value)


class ProfiledHTTP:
    def __init__(self, app: ASGIApp, recorder: Recorder):
        self.app, self.recorder = app, recorder

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        with self.recorder.phase("request") as finish:

            async def timed_send(message: Message) -> None:
                if message["type"] == "http.response.start":
                    finish.http_status = message["status"]
                with self.recorder.phase("response_send"):
                    await send(message)

            await self.app(scope, receive, timed_send)


def application(
    connect: ConnectionFactory, recorder: Recorder, *, origin: str, trial_id: str, clock: Any = None
) -> ASGIApp:
    with recorder.phase("startup"):
        app = create_app(
            ProfiledService(
                ProfiledStore(connect, recorder, clock=clock),
                ProfiledNotices(connect, recorder),
                recorder,
            ),
            ProfiledAuth(connect, recorder),
            origin=origin,
            trial_id=trial_id,
        )
    return ProfiledHTTP(app, recorder)


class ProfiledStep:
    """SDK step proxy. Durable replay time is NOT elapsed business waiting time."""

    def __init__(self, delegate: Any, recorder: Recorder):
        self.delegate, self.recorder = delegate, recorder

    async def run(self, *args: Any, **kwargs: Any) -> Any:
        return await self.recorder.wait("event_step", lambda: self.delegate.run(*args, **kwargs))

    async def send_event(self, *args: Any, **kwargs: Any) -> Any:
        return await self.recorder.wait(
            "event_send", lambda: self.delegate.send_event(*args, **kwargs)
        )

    async def wait_for_event(self, key: str, **kwargs: Any) -> Any:
        stages = {
            "supply/shipment.reviewed": "approval_wait",
            "supply/shipment.confirmed": "confirmation_wait",
        }
        stage = stages.get(kwargs.get("event", ""))
        if stage is None:
            raise ValueError("unknown Supply wait stage")
        with self.recorder.phase(stage):
            return await self.delegate.wait_for_event(key, **kwargs)


class ProfiledContext:
    def __init__(self, delegate: Any, recorder: Recorder):
        self.delegate, self.step = delegate, ProfiledStep(delegate.step, recorder)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.delegate, name)


def profiled_functions(client: Any, handlers: EventHandlers, recorder: Recorder) -> Any:
    class Client:
        def create_function(self, **kwargs: Any) -> Any:
            decorate = client.create_function(**kwargs)

            def measured(fn: Any) -> Any:
                async def invoke(ctx: Any) -> Any:
                    with recorder.phase("event", operation="event"):
                        return await fn(ProfiledContext(ctx, recorder))

                return decorate(invoke)

            return measured

    return build_functions(Client(), handlers)  # type: ignore[arg-type]


def private_output(path: Path) -> Path:
    resolved = path.resolve()
    if resolved.exists() or any((p / ".git").exists() for p in resolved.parents):
        raise ValueError("new output outside every Git checkout required")
    if not resolved.parent.is_dir():
        raise ValueError("existing private parent directory required")
    return resolved


def persist(recorder: Recorder, path: Path) -> None:
    output = private_output(path)
    # Exclusive creation, no overwriting prior evidence, no raw runtime objects serialized.
    with output.open("x", encoding="utf-8") as stream:
        json.dump(recorder.snapshot(), stream, sort_keys=True)
        stream.flush()
        os.fsync(stream.fileno())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--trial", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8877)
    parser.add_argument("--span-limit", type=int, default=4096)
    args = parser.parse_args()
    try:
        if not 1024 <= args.port <= 65535:
            raise ValueError("unprivileged loopback port required")
        output = private_output(args.output)
        workspace = Workspace(args.root.resolve())
        trial, server = workspace.load_trial(args.trial), workspace.server()
        recorder = Recorder(limit=args.span_limit)
        connect = connection_factory(
            recorder,
            host="127.0.0.1",
            port=server.port,
            user=trial.name,
            password=trial.password,
            dbname=trial.name,
            connect_timeout=5,
        )
        try:
            uvicorn.run(
                application(
                    connect, recorder, origin=f"http://127.0.0.1:{args.port}", trial_id=trial.name
                ),
                host="127.0.0.1",
                port=args.port,
                proxy_headers=False,
                access_log=False,
                limit_concurrency=16,
                timeout_keep_alive=5,
                timeout_graceful_shutdown=30,
                log_level="warning",
            )
        finally:
            persist(recorder, output)
    except (ValueError, OSError, psycopg.Error) as error:
        parser.error("Supply profiling refused: " + type(error).__name__)


if __name__ == "__main__":
    main()
