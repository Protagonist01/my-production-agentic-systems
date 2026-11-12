"""Real SQL commit/rollback and authorization through the opt-in timing adapters."""

import json

import psycopg
import pytest
from revenue_integrity.operations import OperationStore
from test_revenue_operations import app as app
from test_revenue_operations import seed

from revenue_profiled_runtime import ProfiledOperations, connection_factory
from revenue_profiling import Recorder


def test_profiled_sql_preserves_approved_effect_and_replay_with_rollback(app):
    server, trial, _ = app
    recorder = Recorder(limit=10000)
    connect = connection_factory(
        recorder,
        host="127.0.0.1",
        port=server.port,
        user=trial.name,
        password=trial.password,
        dbname=trial.name,
        connect_timeout=5,
    )
    store = ProfiledOperations(OperationStore(connect), recorder)
    _, operator, reviewer, command, _ = seed((server, trial, store))
    store.propose(operator, command)
    with pytest.raises(PermissionError):
        store.review(operator, command.business_operation_id, approve=True)
    store.review(reviewer, command.business_operation_id, approve=True)
    receipt = store.apply(operator, command.business_operation_id, run_id="profiled")
    assert store.apply(operator, command.business_operation_id, run_id="duplicate") == receipt
    with connect() as connection:
        connection.autocommit = True
        with pytest.raises(psycopg.errors.UndefinedTable):
            with connection.transaction():
                connection.execute("SELECT * FROM missing_profile_canary_table")
        assert connection.execute("SELECT 41+1").fetchone()[0] == 42
        connection.commit()
        connection.rollback()
    report = recorder.snapshot()
    for stage in (
        "sql_connect",
        "sql_execute",
        "sql_fetch",
        "sql_commit",
        "sql_rollback",
        "sql_finalize",
        "proposal",
        "review",
        "apply",
    ):
        assert report["stages"][stage]["observations"] > 0
    assert report["stages"]["sql_execute"]["outcomes"]["error"] > 0
    assert report["complete"]
    assert "missing_profile_canary_table" not in json.dumps(report)
    assert trial.password not in json.dumps(report)
