"""Opt-in Revenue console/SQL adapters; source APIs and authorization stay unchanged."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, Self

import psycopg
from psycopg import Transaction
from revenue_integrity.console_api import create_app
from revenue_integrity.console_auth import AuthStore
from revenue_integrity.console_contracts import Principal, Submission
from revenue_integrity.console_service import ConsoleService, Operations
from revenue_integrity.operation_contracts import (
    ChangeCommand,
    Proposal,
    Receipt,
    RevenueGrant,
    RevenueRecord,
)
from revenue_integrity.operations import ConnectionFactory
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from revenue_profiling import Recorder


class ProfiledCursor(psycopg.Cursor[Any]):
    def measured(self, stage: str, fn: Any, *args: Any, **kwargs: Any) -> Any:
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
    def __init__(self, connect: ConnectionFactory, recorder: Recorder):
        self.recorder = recorder
        super().__init__(connect)

    def authenticate(self, token: str, csrf: str | None = None) -> Principal:
        return self.recorder.call("authenticate", super().authenticate, token, csrf)

    def login(self, username: str, password: str) -> tuple[str, str, Principal]:
        return self.recorder.call("login", super().login, username, password)


class ProfiledService(ConsoleService):
    def __init__(self, store: Operations, recorder: Recorder):
        self.recorder = recorder
        super().__init__(store)

    def workbench(self, principal: Principal) -> dict[str, object]:
        # Includes retrieval and arithmetic; not isolated query or reconciliation time.
        return self.recorder.call("retrieval", super().workbench, principal)

    def propose(self, principal: Principal, payload: Submission) -> Proposal:
        return self.recorder.call("proposal", super().propose, principal, payload)

    def review(
        self, principal: Principal, operation_id: str, *, approve: bool, digest: str
    ) -> Proposal:
        return self.recorder.call(
            "review", super().review, principal, operation_id, approve=approve, digest=digest
        )


class ProfiledOperations:
    """Delegate every authorized operation unchanged, including API paths outside service."""

    def __init__(self, delegate: Operations, recorder: Recorder):
        self.delegate, self.recorder = delegate, recorder

    def snapshot(
        self, grant: RevenueGrant
    ) -> tuple[tuple[RevenueRecord, ...], tuple[Proposal, ...], tuple[Receipt, ...]]:
        return self.recorder.call("retrieval", self.delegate.snapshot, grant)

    def records(self, grant: RevenueGrant) -> tuple[RevenueRecord, ...]:
        return self.recorder.call("document_load", self.delegate.records, grant)

    def proposals(self, grant: RevenueGrant) -> tuple[Proposal, ...]:
        return self.recorder.call("retrieval", self.delegate.proposals, grant)

    def ledger(self, grant: RevenueGrant) -> tuple[Receipt, ...]:
        return self.recorder.call("retrieval", self.delegate.ledger, grant)

    def propose(
        self, grant: RevenueGrant, command: ChangeCommand, *, ttl_seconds: int = 86400
    ) -> Proposal:
        return self.recorder.call(
            "proposal", self.delegate.propose, grant, command, ttl_seconds=ttl_seconds
        )

    def review(self, grant: RevenueGrant, operation_id: str, *, approve: bool) -> Proposal:
        return self.recorder.call(
            "review", self.delegate.review, grant, operation_id, approve=approve
        )

    def apply(self, grant: RevenueGrant, operation_id: str, *, run_id: str) -> Receipt:
        return self.recorder.call("apply", self.delegate.apply, grant, operation_id, run_id=run_id)

    def trim(self, grant: RevenueGrant, command: ChangeCommand, *, run_id: str) -> Receipt:
        return self.recorder.call("apply", self.delegate.trim, grant, command, run_id=run_id)

    def sweep(self, grant: RevenueGrant) -> tuple[Proposal, ...]:
        return self.recorder.call("review", self.delegate.sweep, grant)


class ProfiledHTTP:
    def __init__(self, app: ASGIApp, recorder: Recorder):
        self.app, self.recorder = app, recorder

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        with self.recorder.phase("request"):

            async def timed_send(message: Message) -> None:
                with self.recorder.phase("response_send"):
                    await send(message)

            await self.app(scope, receive, timed_send)


def application(
    store: Operations, connect: ConnectionFactory, recorder: Recorder, *, origin: str, trial_id: str
) -> ASGIApp:
    """Explicit opt-in console composition. Caller supplies scoped store and database."""
    with recorder.phase("startup"):
        app = create_app(
            ProfiledService(ProfiledOperations(store, recorder), recorder),
            ProfiledAuth(connect, recorder),
            origin=origin,
            trial_id=trial_id,
        )
    return ProfiledHTTP(app, recorder)
