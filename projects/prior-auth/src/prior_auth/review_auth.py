"""Prior-auth provisioned identities and opaque sessions; no public registration."""

import hashlib
import hmac
import json
import re
import secrets
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from importlib.resources import files
from typing import Any

from psycopg import Connection, sql
from psycopg.rows import dict_row, tuple_row
from psycopg.types.json import Jsonb

from prior_auth.review_contracts import Principal

ConnectionFactory = Callable[[], Connection[Any]]


def sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


ITERATIONS = 600_000
SESSION_SECONDS = 1800


def password_hash(password: str, salt: bytes | None = None) -> str:
    if not 15 <= len(password) <= 128:
        raise ValueError("password must contain 15 to 128 characters")
    salt = salt or secrets.token_bytes(16)
    value = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS)
    return f"pbkdf2-sha256${ITERATIONS}${salt.hex()}${value.hex()}"


def password_matches(password: str, encoded: str) -> bool:
    if not 15 <= len(password) <= 128:
        return False
    try:
        algorithm, iterations, salt, expected = encoded.split("$")
        if algorithm != "pbkdf2-sha256" or int(iterations) != ITERATIONS:
            return False
        value = password_hash(password, bytes.fromhex(salt)).rsplit("$", 1)[1]
        return hmac.compare_digest(value, expected)
    except ValueError:
        return False


def setup_review(admin: Connection[Any], runtime_role: str) -> None:
    ddl = files("prior_auth").joinpath("review.sql").read_text(encoding="utf-8")
    with admin.transaction():
        admin.execute("SELECT pg_advisory_xact_lock(73414049)")
        admin.execute("CREATE SCHEMA IF NOT EXISTS prior_auth_app")
        admin.execute("REVOKE ALL ON SCHEMA prior_auth_app FROM PUBLIC")
        admin.execute(
            "CREATE TABLE IF NOT EXISTS prior_auth_app.schema_pin("
            "version integer PRIMARY KEY,sha256 text NOT NULL)"
        )
        with admin.cursor(row_factory=tuple_row) as cursor:
            current = cursor.execute(
                "SELECT version,sha256 FROM prior_auth_app.schema_pin"
            ).fetchall()
        if current and current != [(1, sha(ddl))]:
            raise ValueError("prior-auth schema differs from immutable version1")
        if not current:
            admin.execute(ddl)
            admin.execute("INSERT INTO prior_auth_app.schema_pin VALUES(1,%s)", (sha(ddl),))
        admin.execute(
            sql.SQL("GRANT USAGE ON SCHEMA prior_auth_app TO {}").format(
                sql.Identifier(runtime_role)
            )
        )
        for table, privileges in (
            ("accounts", "SELECT"),
            ("sessions", "SELECT,INSERT,DELETE"),
            ("login_attempts", "SELECT,INSERT,UPDATE,DELETE"),
            ("cases", "SELECT,INSERT,UPDATE"),
            ("events", "SELECT,INSERT"),
            ("commands", "SELECT,INSERT"),
            ("jobs", "SELECT,INSERT,UPDATE"),
        ):
            admin.execute(
                sql.SQL("GRANT " + privileges + " ON prior_auth_app." + table + " TO {}").format(
                    sql.Identifier(runtime_role)
                )
            )


def provision(admin: Connection[Any], principal: Principal, password: str) -> None:
    principal = Principal.model_validate_json(principal.canonical_json())
    if re.fullmatch(r"[a-z0-9][a-z0-9_.-]{2,63}", principal.username) is None:
        raise ValueError("username must be 3 to 64 lowercase account characters")
    with admin.transaction():
        admin.execute(
            "INSERT INTO prior_auth_app.accounts(username,password_hash,principal) "
            "VALUES(%s,%s,%s)",
            (principal.username, password_hash(password), Jsonb(principal.model_dump(mode="json"))),
        )


class AuthStore:
    def __init__(
        self, connect: ConnectionFactory, *, clock: Callable[[], datetime] | None = None
    ) -> None:
        self.connect = connect
        self.clock = clock or (lambda: datetime.now(UTC))
        self._dummy = password_hash(secrets.token_urlsafe(32))

    def login(self, username: str, password: str) -> tuple[str, str, Principal]:
        if len(username) > 64 or len(password) > 128:
            raise PermissionError("sign-in failed")
        now = self.clock()
        valid = False
        principal = None
        with self.connect() as connection:
            connection.row_factory = dict_row
            connection.execute("SET statement_timeout = 5000")
            connection.execute("SET lock_timeout = 2000")
            # Bound expensive hashes and the number of unknown-account counters.
            # Global admission serializes only local sign-in, not case processing.
            global_key = sha("prior-auth-global-login-v1")
            connection.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (global_key,)
            )
            connection.execute(
                "DELETE FROM prior_auth_app.login_attempts WHERE window_start < %s",
                (now - timedelta(minutes=5),),
            )
            global_row = connection.execute(
                "SELECT failures FROM prior_auth_app.login_attempts WHERE username_hash=%s",
                (global_key,),
            ).fetchone()
            if global_row and global_row["failures"] >= 100:
                raise PermissionError("sign-in failed")
            connection.execute(
                "INSERT INTO prior_auth_app.login_attempts VALUES(%s,%s,1) "
                "ON CONFLICT(username_hash) DO UPDATE "
                "SET failures=prior_auth_app.login_attempts.failures+1",
                (global_key, now),
            )
            key = sha("account:" + username)
            connection.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (key,))
            row = connection.execute(
                "SELECT * FROM prior_auth_app.login_attempts WHERE username_hash=%s", (key,)
            ).fetchone()
            if row and now - row["window_start"] < timedelta(minutes=5) and row["failures"] >= 5:
                raise PermissionError("sign-in failed")
            account = connection.execute(
                "SELECT * FROM prior_auth_app.accounts WHERE username=%s", (username,)
            ).fetchone()
            matched = password_matches(
                password, account["password_hash"] if account else self._dummy
            )
            if account and account["enabled"] and matched:
                principal = Principal.model_validate_json(json.dumps(account["principal"]))
                connection.execute(
                    "DELETE FROM prior_auth_app.login_attempts WHERE username_hash=%s", (key,)
                )
                valid = True
            else:
                connection.execute(
                    (
                        "INSERT INTO prior_auth_app.login_attempts VALUES(%s,%s,1) ON "
                        "CONFLICT(username_hash) DO UPDATE SET failures=CASE WHEN "
                        "prior_auth_app.login_attempts.window_start < %s THEN 1 ELSE "
                        "prior_auth_app.login_attempts.failures+1 END,window_start=CASE WHEN"
                        " prior_auth_app.login_attempts.window_start < %s THEN %s ELSE "
                        "prior_auth_app.login_attempts.window_start END"
                    ),
                    (key, now, now - timedelta(minutes=5), now - timedelta(minutes=5), now),
                )
            if valid:
                token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
                connection.execute(
                    "DELETE FROM prior_auth_app.sessions WHERE expires_at<=%s", (now,)
                )
                connection.execute(
                    "INSERT INTO prior_auth_app.sessions VALUES(%s,%s,%s,%s)",
                    (sha(token), username, sha(csrf), now + timedelta(seconds=SESSION_SECONDS)),
                )
        # Failure is raised after the transaction commits its throttle counter.
        if not valid or principal is None:
            raise PermissionError("sign-in failed")
        return token, csrf, principal

    def authenticate(self, token: str, csrf: str | None = None) -> Principal:
        if not 20 <= len(token) <= 128 or (csrf is not None and not 20 <= len(csrf) <= 128):
            raise PermissionError("sign-in required")
        with self.connect() as connection:
            connection.row_factory = dict_row
            row = connection.execute(
                (
                    "SELECT s.csrf_hash,a.principal FROM prior_auth_app.sessions s JOIN "
                    "prior_auth_app.accounts a USING(username) WHERE s.token_hash=%s AND "
                    "s.expires_at>%s AND a.enabled"
                ),
                (sha(token), self.clock()),
            ).fetchone()
        if row is None or (
            csrf is not None and not hmac.compare_digest(row["csrf_hash"], sha(csrf))
        ):
            raise PermissionError("sign-in or request verification failed")
        return Principal.model_validate_json(json.dumps(row["principal"]))

    def logout(self, token: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "DELETE FROM prior_auth_app.sessions WHERE token_hash=%s", (sha(token),)
            )
