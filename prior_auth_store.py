"""Atomically persist an intake receipt and legacy assessment handoff in one database.

Only trusted local imports call this API. Browser uploads are intentionally not wired
to it: import assertions need their own authenticated source before that expansion.
"""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from prior_auth.contracts import CandidateAssessment, digest
from prior_auth.review_contracts import Principal, RedactedDelivery, StateChanged
from prior_auth.review_store import ConnectionFactory, ReviewStore
from psycopg import Connection, sql
from psycopg.rows import tuple_row
from psycopg.types.json import Jsonb

from prior_auth_pipeline import PreparedImport
from prior_auth_profiling import Profiler


def setup(connection: Connection[Any], runtime_role: str) -> None:
    ddl = Path(__file__).with_suffix(".sql").read_text(encoding="utf-8")
    with connection.transaction():
        connection.execute("SELECT pg_advisory_xact_lock(73414050)")
        connection.execute("CREATE SCHEMA IF NOT EXISTS prior_auth_intake")
        connection.execute("REVOKE ALL ON SCHEMA prior_auth_intake FROM PUBLIC")
        connection.execute(
            "CREATE TABLE IF NOT EXISTS prior_auth_intake.schema_pin ("
            "version integer PRIMARY KEY, sha256 text NOT NULL)"
        )
        with connection.cursor(row_factory=tuple_row) as cursor:
            current = cursor.execute(
                "SELECT version,sha256 FROM prior_auth_intake.schema_pin"
            ).fetchall()
        if current and current != [(1, digest(ddl))]:
            raise ValueError("intake schema differs from immutable version1")
        if not current:
            connection.execute(ddl)
            connection.execute(
                "INSERT INTO prior_auth_intake.schema_pin VALUES(1,%s)", (digest(ddl),)
            )
        connection.execute(
            sql.SQL("GRANT USAGE ON SCHEMA prior_auth_intake TO {}").format(
                sql.Identifier(runtime_role)
            )
        )
        for table in ("receipts", "bindings", "documents"):
            connection.execute(
                sql.SQL("GRANT SELECT,INSERT ON prior_auth_intake.{} TO {}").format(
                    sql.Identifier(table), sql.Identifier(runtime_role)
                )
            )


class JoinedReviewStore(ReviewStore):
    """Join caller's outer transaction: never commit the handoff separately."""

    def __init__(self, connection: Connection[Any], clock: Callable[[], datetime]) -> None:
        super().__init__(lambda: connection, clock=clock)
        self.connection = connection

    @contextmanager
    def transaction(self) -> Iterator[Connection[Any]]:
        yield self.connection


class IntakeStore:
    def __init__(
        self, connect: ConnectionFactory, *, clock: Callable[[], datetime] | None = None
    ) -> None:
        self.store = ReviewStore(connect, clock=clock)

    def accept(self, user: Principal, prepared: PreparedImport, profiler: Profiler) -> int | None:
        prepared = PreparedImport.model_validate_json(prepared.canonical_json())
        user.require(prepared.case.case_id, write=True)
        case, binding = prepared.case, prepared.binding
        if (user.tenant_id, case.case_id) != (case.tenant_id, binding.case_id):
            raise PermissionError("intake scope differs")
        if (
            binding.tenant_id != case.tenant_id or binding.subject_key != case.subject_key
        ) and prepared.note:
            raise PermissionError("intake document binding differs")
        with profiler.span("persistence"), self.store.transaction() as c:
            # Serialize even initial enrollment before a legacy case row exists.
            c.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (case.tenant_id + ":" + case.case_id,),
            )
            prior = c.execute(
                "SELECT prepared_sha256,resulting_version FROM prior_auth_intake.receipts "
                "WHERE tenant_id=%s AND case_id=%s AND document_id=%s",
                (case.tenant_id, case.case_id, binding.document_id),
            ).fetchone()
            if prior:
                if prior["prepared_sha256"] != digest(prepared.canonical_json()):
                    raise StateChanged("document identity reused with different import")
                value = prior["resulting_version"]
                return int(value) if value is not None else None
            version = None
            if prepared.note is not None:
                pin = digest(case.canonical_json())
                current = c.execute(
                    "SELECT binding_sha256 FROM prior_auth_intake.bindings "
                    "WHERE tenant_id=%s AND case_id=%s",
                    (case.tenant_id, case.case_id),
                ).fetchone()
                joined = JoinedReviewStore(c, self.store.clock)
                if prepared.expected_version is None:
                    if current:
                        raise StateChanged("case already imported")
                    joined.enroll(
                        prepared.note,
                        prepared.policy,
                        review_ref=binding.redaction_review_ref or "",
                    )
                    c.execute(
                        "INSERT INTO prior_auth_intake.bindings VALUES(%s,%s,%s)",
                        (case.tenant_id, case.case_id, pin),
                    )
                    version = 1
                else:
                    if not current or current["binding_sha256"] != pin:
                        raise StateChanged("case identity or policy scope changed")
                    # Prevent a registry or policy replacement from accepting evidence for
                    # a different legacy policy. The legacy lock/version checks still apply.
                    row = joined._row(c, case.tenant_id, case.case_id)
                    if row["note"]["policy_sha256"] != prepared.note.policy_sha256:
                        raise StateChanged("case policy changed")
                    version = joined.deliver(
                        user,
                        case.case_id,
                        RedactedDelivery(
                            delivery_id=binding.document_id,
                            expected_version=prepared.expected_version,
                            text=prepared.note.text,
                            review_ref=binding.redaction_review_ref or "",
                        ),
                    )
            c.execute(
                "INSERT INTO prior_auth_intake.receipts VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    case.tenant_id,
                    case.case_id,
                    binding.document_id,
                    prepared.request_sha256,
                    digest(prepared.canonical_json()),
                    prepared.source_sha256,
                    Jsonb(prepared.decision.model_dump(mode="json")),
                    version,
                    datetime.now(UTC),
                ),
            )
            if prepared.normalized is not None:
                joined = JoinedReviewStore(c, self.store.clock)
                saved = joined._row(c, case.tenant_id, case.case_id)
                note_text = str(saved["note"]["text"])
                if not note_text.endswith(prepared.normalized.text):
                    raise StateChanged("stored document location differs")
                c.execute(
                    "INSERT INTO prior_auth_intake.documents VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        case.tenant_id,
                        case.case_id,
                        binding.document_id,
                        Jsonb(prepared.normalized.model_dump(mode="json")),
                        digest(binding.canonical_json()),
                        version,
                        len(note_text) - len(prepared.normalized.text),
                        saved["note"]["note_sha256"],
                    ),
                )
            return version


class ProfiledReviewStore(ReviewStore):
    """Worker-compatible aggregate transaction/claim/publication timings.

    Publication includes the legacy checker and SQL; no false claim that every
    lock or internal statement is measured separately.
    """

    def __init__(
        self,
        connect: ConnectionFactory,
        profiler: Profiler,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        super().__init__(connect, clock=clock)
        self.profiler = profiler

    @contextmanager
    def transaction(self) -> Iterator[Connection[Any]]:
        with self.profiler.span("persistence"), super().transaction() as connection:
            yield connection

    def claim(self) -> dict[str, Any] | None:
        with self.profiler.span("claim"):
            return super().claim()

    def expire(self) -> int:
        with self.profiler.span("expiry"):
            return super().expire()

    def finish(self, job: dict[str, Any], candidate: CandidateAssessment | None) -> bool:
        with self.profiler.span("publication"):
            return super().finish(job, candidate)
