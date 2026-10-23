"""Postgres owns canonical versions, waits, receipts and recoverable assessment jobs."""

import json
import secrets
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

from agent_harness.contracts import Contract
from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from prior_auth.assessment import CRITERIA, TERMS, assess
from prior_auth.contracts import CandidateAssessment, NoteInput, Policy, digest
from prior_auth.review_contracts import (
    Principal,
    RedactedDelivery,
    ReviewNote,
    StateChanged,
    WaitRequest,
)

ConnectionFactory = Callable[[], Connection[Any]]


def contract[T: Contract](value: Any, cls: type[T]) -> T:
    return cls.model_validate_json(json.dumps(value))


class ReviewStore:
    def __init__(
        self, connect: ConnectionFactory, *, clock: Callable[[], datetime] | None = None
    ) -> None:
        self.connect = connect
        self.clock = clock or (lambda: datetime.now(UTC))

    def now(self) -> datetime:
        value = self.clock()
        if value.utcoffset() is None:
            raise ValueError("aware clock required")
        return value

    @contextmanager
    def transaction(self) -> Iterator[Connection[Any]]:
        with self.connect() as connection:
            connection.row_factory = dict_row
            connection.execute("SET statement_timeout = 5000")
            connection.execute("SET lock_timeout = 2000")
            yield connection

    def _row(self, c: Connection[Any], tenant: str, case: str) -> dict[str, Any]:
        row = c.execute(
            "SELECT * FROM prior_auth_app.cases WHERE tenant_id=%s AND case_id=%s FOR UPDATE",
            (tenant, case),
        ).fetchone()
        if row is None:
            raise LookupError("case unavailable")
        return dict(row)

    def _event(
        self,
        c: Connection[Any],
        row: dict[str, Any],
        key: str,
        kind: str,
        actor: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        # Metadata callers supply fixed states/counts/criterion IDs only. Notes,
        # model rationales, credentials and raw document bodies never enter events.
        c.execute(
            "INSERT INTO prior_auth_app.events VALUES(%s,%s,%s,%s,%s,%s,%s,%s) "
            "ON CONFLICT DO NOTHING",
            (
                row["tenant_id"],
                row["case_id"],
                row["version"],
                key,
                kind,
                actor,
                Jsonb(metadata or {}),
                self.now(),
            ),
        )

    def _job(self, c: Connection[Any], row: dict[str, Any], criteria: tuple[str, ...]) -> None:
        c.execute(
            "UPDATE prior_auth_app.jobs SET state='obsolete' WHERE tenant_id=%s "
            "AND case_id=%s AND state IN ('pending','leased')",
            (row["tenant_id"], row["case_id"]),
        )
        c.execute(
            "INSERT INTO prior_auth_app.jobs(tenant_id,case_id,version,criteria,state) "
            "VALUES(%s,%s,%s,%s,'pending')",
            (row["tenant_id"], row["case_id"], row["version"], Jsonb(list(criteria))),
        )

    def enroll(self, note: NoteInput, policy: Policy, *, review_ref: str) -> None:
        note = NoteInput.model_validate_json(note.canonical_json())
        policy = Policy.model_validate_json(policy.canonical_json())
        if (
            not review_ref
            or len(review_ref) > 96
            or note.policy_sha256 != digest(policy.canonical_json())
        ):
            raise ValueError("reviewed redaction and matching policy pin required")
        with self.transaction() as c:
            c.execute(
                "INSERT INTO prior_auth_app.cases(tenant_id,case_id,version,note,policy,status) "
                "VALUES(%s,%s,1,%s,%s,'assessing')",
                (
                    note.tenant_id,
                    note.case_id,
                    Jsonb(note.model_dump(mode="json")),
                    Jsonb(policy.model_dump(mode="json")),
                ),
            )
            row = self._row(c, note.tenant_id, note.case_id)
            self._job(c, row, CRITERIA)
            self._event(c, row, "enrolled", "case_enrolled", "trusted_import")

    def snapshot(self, user: Principal, case_id: str) -> dict[str, Any]:
        user.require(case_id)
        with self.transaction() as c:
            row = self._row(c, user.tenant_id, case_id)
            events = c.execute(
                "SELECT version,kind,actor_id,metadata,created_at FROM prior_auth_app.events "
                "WHERE tenant_id=%s AND case_id=%s ORDER BY created_at,event_key",
                (user.tenant_id, case_id),
            ).fetchall()
            job = c.execute(
                "SELECT state,attempts,criteria FROM prior_auth_app.jobs "
                "WHERE tenant_id=%s AND case_id=%s AND version=%s",
                (user.tenant_id, case_id, row["version"]),
            ).fetchone()
        row["events"] = [dict(e, created_at=e["created_at"].isoformat()) for e in events]
        row["job"] = dict(job) if job else None
        row["deadline"] = row["deadline"].isoformat() if row["deadline"] else None
        row["can_review"] = user.role == "reviewer"
        return row

    def _receipt(
        self, c: Connection[Any], row: dict[str, Any], command: str, payload: str
    ) -> int | None:
        receipt = c.execute(
            "SELECT payload_sha,resulting_version FROM prior_auth_app.commands "
            "WHERE tenant_id=%s AND case_id=%s AND command_id=%s",
            (row["tenant_id"], row["case_id"], command),
        ).fetchone()
        if receipt:
            if receipt["payload_sha"] != digest(payload):
                raise StateChanged("command identity reused with different payload")
            return int(receipt["resulting_version"])
        return None

    def _save_receipt(
        self, c: Connection[Any], row: dict[str, Any], command: str, payload: str
    ) -> None:
        c.execute(
            "INSERT INTO prior_auth_app.commands VALUES(%s,%s,%s,%s,%s)",
            (row["tenant_id"], row["case_id"], command, digest(payload), row["version"]),
        )

    def request(self, user: Principal, case_id: str, request: WaitRequest) -> int:
        user.require(case_id, write=True)
        request = WaitRequest.model_validate_json(request.canonical_json())
        payload = user.actor_id + ":wait:" + request.canonical_json()
        with self.transaction() as c:
            row = self._row(c, user.tenant_id, case_id)
            prior = self._receipt(c, row, request.command_id, payload)
            if prior is not None:
                return prior
            if row["version"] != request.expected_version or row["status"] == "assessing":
                raise StateChanged("case changed or assessment pending")
            if not self.now() < request.deadline <= self.now() + timedelta(days=90):
                raise ValueError("deadline must be future and within 90 days")
            c.execute(
                "UPDATE prior_auth_app.cases SET status='waiting',wait_criteria=%s,deadline=%s, "
                "version=version+1 WHERE tenant_id=%s AND case_id=%s",
                (Jsonb(list(request.criteria)), request.deadline, user.tenant_id, case_id),
            )
            row["version"] += 1
            self._save_receipt(c, row, request.command_id, payload)
            self._event(
                c,
                row,
                "wait:" + request.command_id,
                "documents_requested",
                user.actor_id,
                {"criteria": list(request.criteria), "deadline": request.deadline.isoformat()},
            )
            return int(row["version"])

    def review(self, user: Principal, case_id: str, note: ReviewNote) -> int:
        user.require(case_id, write=True)
        note = ReviewNote.model_validate_json(note.canonical_json())
        payload = user.actor_id + ":review:" + note.canonical_json()
        with self.transaction() as c:
            row = self._row(c, user.tenant_id, case_id)
            prior = self._receipt(c, row, note.command_id, payload)
            if prior is not None:
                return prior
            if row["version"] != note.expected_version or row["status"] == "assessing":
                raise StateChanged("case changed or assessment pending")
            c.execute(
                "UPDATE prior_auth_app.cases SET status=%s,version=version+1,deadline=NULL, "
                "wait_criteria='[]' WHERE tenant_id=%s AND case_id=%s",
                (note.outcome, user.tenant_id, case_id),
            )
            row["version"] += 1
            self._save_receipt(c, row, note.command_id, payload)
            self._event(
                c,
                row,
                "review:" + note.command_id,
                "review_routed",
                user.actor_id,
                {"outcome": note.outcome, "reason": note.reason},
            )
            return int(row["version"])

    def deliver(self, user: Principal, case_id: str, delivery: RedactedDelivery) -> int:
        """Trusted import only: HTTP never exposes this redaction attestation surface."""
        user.require(case_id, write=True)
        delivery = RedactedDelivery.model_validate_json(delivery.canonical_json())
        payload = user.actor_id + ":document:" + delivery.canonical_json()
        with self.transaction() as c:
            row = self._row(c, user.tenant_id, case_id)
            prior = self._receipt(c, row, delivery.delivery_id, payload)
            if prior is not None:
                return prior
            if (
                row["version"] != delivery.expected_version
                or row["status"] != "waiting"
                or row["deadline"] <= self.now()
            ):
                raise StateChanged("delivery requires a current unexpired document wait")
            previous = contract(row["note"], NoteInput)
            text = previous.text + "\n\n--- Reviewed supplemental evidence ---\n" + delivery.text
            if len(text) > 100000:
                raise ValueError("combined redacted note exceeds limit")
            updated = NoteInput.model_validate_json(
                previous.model_copy(
                    update={
                        "text": text,
                        "note_sha256": digest(text),
                        "provenance": (
                            "invented"
                            if previous.provenance == "invented"
                            else "edited_illustrative"
                        ),
                    }
                ).canonical_json()
            )
            keys = tuple(
                key
                for key in CRITERIA
                if key in row["wait_criteria"]
                or any(term in delivery.text.casefold() for term in TERMS[key])
            )
            # Absence of recognized terms is not proof of no semantic change.
            if not keys:
                keys = CRITERIA
            old = contract(row["candidate"], CandidateAssessment) if row["candidate"] else None
            retained = (
                tuple(claim for claim in old.claims if claim.criterion_id not in keys)
                if old
                else ()
            )
            base = CandidateAssessment(
                case_id=case_id,
                note_sha256=updated.note_sha256,
                policy_sha256=updated.policy_sha256,
                claims=retained,
            )
            c.execute(
                "UPDATE prior_auth_app.cases SET version=version+1,note=%s,candidate=%s, "
                "result=NULL,status='assessing',deadline=NULL,wait_criteria='[]' "
                "WHERE tenant_id=%s AND case_id=%s",
                (
                    Jsonb(updated.model_dump(mode="json")),
                    Jsonb(base.model_dump(mode="json")),
                    user.tenant_id,
                    case_id,
                ),
            )
            row["version"] += 1
            self._job(c, row, keys)
            self._save_receipt(c, row, delivery.delivery_id, payload)
            self._event(
                c,
                row,
                "document:" + delivery.delivery_id,
                "document_received",
                user.actor_id,
                {"criteria": list(keys)},
            )
            return int(row["version"])

    def replace_policy(self, user: Principal, case_id: str, policy: Policy, *, version: int) -> int:
        user.require(case_id, write=True)
        policy = Policy.model_validate_json(policy.canonical_json())
        with self.transaction() as c:
            row = self._row(c, user.tenant_id, case_id)
            if row["version"] != version:
                raise StateChanged("case changed")
            pin = digest(policy.canonical_json())
            if row["note"]["policy_sha256"] == pin:
                return int(row["version"])
            note = contract(row["note"], NoteInput).model_copy(update={"policy_sha256": pin})
            c.execute(
                "UPDATE prior_auth_app.cases SET version=version+1,policy=%s,note=%s, "
                "candidate=NULL,result=NULL,status='assessing',deadline=NULL,wait_criteria='[]' "
                "WHERE tenant_id=%s AND case_id=%s",
                (
                    Jsonb(policy.model_dump(mode="json")),
                    Jsonb(note.model_dump(mode="json")),
                    user.tenant_id,
                    case_id,
                ),
            )
            row["version"] += 1
            self._job(c, row, CRITERIA)
            self._event(c, row, "policy:" + str(row["version"]), "policy_changed", user.actor_id)
            return int(row["version"])

    def expire(self) -> int:
        with self.transaction() as c:
            rows = c.execute(
                "SELECT * FROM prior_auth_app.cases WHERE status='waiting' AND deadline<=%s "
                "FOR UPDATE SKIP LOCKED LIMIT 100",
                (self.now(),),
            ).fetchall()
            for value in rows:
                row = dict(value)
                c.execute(
                    "UPDATE prior_auth_app.cases SET status='qualified_review',version=version+1 "
                    "WHERE tenant_id=%s AND case_id=%s",
                    (row["tenant_id"], row["case_id"]),
                )
                row["version"] += 1
                self._event(
                    c, row, "timeout:" + str(row["version"]), "document_wait_expired", "worker"
                )
            return len(rows)

    def claim(self) -> dict[str, Any] | None:
        with self.transaction() as c:
            job = c.execute(
                "SELECT * FROM prior_auth_app.jobs WHERE state='pending' OR "
                "(state='leased' AND lease_until<=%s) ORDER BY tenant_id,case_id,version "
                "FOR UPDATE SKIP LOCKED LIMIT 1",
                (self.now(),),
            ).fetchone()
            if job is None:
                return None
            value = dict(job)
            lease = secrets.token_hex(24)
            c.execute(
                "UPDATE prior_auth_app.jobs SET state='leased',lease_id=%s,lease_until=%s, "
                "attempts=attempts+1 WHERE tenant_id=%s AND case_id=%s AND version=%s",
                (
                    lease,
                    self.now() + timedelta(minutes=5),
                    value["tenant_id"],
                    value["case_id"],
                    value["version"],
                ),
            )
            # No case lock here: lock order would oppose document/policy writes.
            row = c.execute(
                "SELECT note,policy,candidate FROM prior_auth_app.cases "
                "WHERE tenant_id=%s AND case_id=%s AND version=%s",
                (value["tenant_id"], value["case_id"], value["version"]),
            ).fetchone()
            if row is None:
                c.execute(
                    "UPDATE prior_auth_app.jobs SET state='obsolete' WHERE tenant_id=%s "
                    "AND case_id=%s AND version=%s",
                    (value["tenant_id"], value["case_id"], value["version"]),
                )
                return None
            return dict(value, lease_id=lease, **dict(row))

    def finish(self, job: dict[str, Any], candidate: CandidateAssessment | None) -> bool:
        note = contract(job["note"], NoteInput)
        policy = contract(job["policy"], Policy)
        result = assess(note, policy, candidate)
        with self.transaction() as c:
            row = self._row(c, job["tenant_id"], job["case_id"])
            current = c.execute(
                "SELECT * FROM prior_auth_app.jobs WHERE tenant_id=%s AND case_id=%s "
                "AND version=%s FOR UPDATE",
                (job["tenant_id"], job["case_id"], job["version"]),
            ).fetchone()
            if (
                not current
                or row["version"] != job["version"]
                or current["state"] != "leased"
                or current["lease_id"] != job["lease_id"]
                or current["lease_until"] <= self.now()
            ):
                return False
            c.execute(
                "UPDATE prior_auth_app.cases SET candidate=%s,result=%s,status=%s "
                "WHERE tenant_id=%s AND case_id=%s",
                (
                    Jsonb(candidate.model_dump(mode="json")) if candidate else None,
                    Jsonb(result.model_dump(mode="json")),
                    result.disposition,
                    job["tenant_id"],
                    job["case_id"],
                ),
            )
            c.execute(
                "UPDATE prior_auth_app.jobs SET state='done' WHERE tenant_id=%s "
                "AND case_id=%s AND version=%s",
                (job["tenant_id"], job["case_id"], job["version"]),
            )
            self._event(
                c,
                row,
                "assessment:" + str(job["version"]),
                "assessment_completed",
                "worker",
                {
                    "disposition": result.disposition,
                    "assessment_failure": result.assessment_failure,
                },
            )
            return True
