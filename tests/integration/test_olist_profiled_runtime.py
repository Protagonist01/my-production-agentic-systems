import json

import psycopg
import pytest
from fastapi.testclient import TestClient
from olist_support.console_auth import provision
from psycopg import sql
from test_olist_business import app as app
from test_olist_console import PASSWORD, create_case
from test_olist_console import console as console

from olist_profiled_runtime import application, connection_factory
from olist_profiling import Recorder


def test_profiled_connection_preserves_transactions_savepoints_and_commit(app):
    r = Recorder()
    connect = connection_factory(app[0], app[1], r)
    with app[0].connect(app[1].name) as admin:
        admin.execute("CREATE TABLE olist.profile_test (n integer)")
        admin.execute(
            sql.SQL("GRANT SELECT,INSERT ON olist.profile_test TO {}").format(
                sql.Identifier(app[1].name)
            )
        )
    with connect() as c:
        c.commit()
        with c.transaction():
            c.execute("INSERT INTO olist.profile_test VALUES (1)")
            with pytest.raises(ValueError), c.transaction():
                c.execute("INSERT INTO olist.profile_test VALUES (2)")
                raise ValueError("SECRET")
            assert c.execute("SELECT n FROM olist.profile_test").fetchall() == [(1,)]
        with c.cursor() as cursor:
            cursor.executemany("INSERT INTO olist.profile_test VALUES (%s)", [(3,), (4,)])
            cursor.execute("SELECT pg_sleep(0.02)")
            cursor.fetchone()
        c.rollback()
        assert c.execute("SELECT n FROM olist.profile_test").fetchmany(2) == [(1,)]
    p = r.snapshot()
    assert p["stages"]["sql_finalize"]["observations"] == 2
    assert p["stages"]["sql_rollback"]["observations"] >= 1
    assert max(s["elapsed_ns"] for s in p["spans"] if s["stage"] == "sql_execute") >= 15_000_000
    assert all(s not in json.dumps(p) for s in ("INSERT", "profile_test", "SECRET"))


def test_query_failure_is_observed_without_changing_rollback(app):
    r = Recorder()
    connect = connection_factory(app[0], app[1], r)
    with connect() as c:
        with pytest.raises(psycopg.errors.DivisionByZero), c.transaction():
            c.execute("SELECT 1/0 /* SECRET */")
        assert c.execute("SELECT 42").fetchone() == (42,)
    assert r.snapshot()["stages"]["sql_execute"]["failures"] == 1
    assert "SECRET" not in json.dumps(r.snapshot())


def test_runnable_composition_profiles_auth_sql_send_and_persists_on_shutdown(console, tmp_path):
    _, case, _, reviewer = create_case(console)
    with console[0].connect(console[1].name) as admin:
        provision(admin, reviewer, PASSWORD)
    r = Recorder()
    output = tmp_path / "runtime-profile.json"
    origin = "http://127.0.0.1:8765"
    app = application(
        console[0],
        console[1],
        r,
        origin=origin,
        revision="invented",
        lock="a" * 64,
        run_limit_minor=10000,
        output=output,
    )
    with TestClient(app, base_url=origin) as client:
        assert client.get("/api/cases/" + case.case_id).status_code == 403
        assert (
            client.post(
                "/api/login",
                json={"username": reviewer.username, "password": PASSWORD},
                headers={"origin": origin},
            ).status_code
            == 200
        )
        assert client.get("/api/cases/" + case.case_id).status_code == 200
    saved = json.loads(output.read_bytes())
    profile = saved["stage_profile"]
    assert saved["shutdown_finished"] and profile["finalized"]
    assert profile["stages"]["sql_connect"]["observations"] > 0
    assert profile["stages"]["sql_execute"]["observations"] > 0
    assert profile["stages"]["response_send"]["observations"] >= 3
    assert all(
        s not in json.dumps(saved)
        for s in (PASSWORD, reviewer.username, case.case_id, case.order_id)
    )
