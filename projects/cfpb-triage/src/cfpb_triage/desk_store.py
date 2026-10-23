"""Durable, scoped complaint review and version-bound classification publication."""

import json
import secrets
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from cfpb_triage.desk_contracts import Principal, QueueCommand, StateChanged
from cfpb_triage.source_contracts import ComplaintInput
from cfpb_triage.triage_contracts import Decision, RouterPolicy, Taxonomy, digest_text


class DeskStore:
    def __init__(
        self, connect: Callable[[], Connection[Any]], *, clock: Callable[[], datetime] | None = None
    ) -> None:
        self.connect = connect
        self.clock = clock or (lambda: datetime.now(UTC))

    @contextmanager
    def transaction(self) -> Iterator[Connection[Any]]:
        with self.connect() as c:
            c.row_factory = dict_row
            c.execute("SET statement_timeout=5000")
            c.execute("SET lock_timeout=2000")
            yield c

    def _row(self, c: Connection[Any], tenant: str, case: str) -> dict[str, Any]:
        row = c.execute(
            "SELECT * FROM cfpb_app.cases WHERE tenant_id=%s AND case_id=%s FOR UPDATE",
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
        c.execute(
            "INSERT INTO cfpb_app.events VALUES(%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
            (
                row["tenant_id"],
                row["case_id"],
                row["version"],
                key,
                kind,
                actor,
                Jsonb(metadata or {}),
                self.clock(),
            ),
        )

    def enroll(
        self,
        tenant: str,
        complaint: ComplaintInput,
        taxonomy: Taxonomy,
        policy: RouterPolicy,
        *,
        review_ref: str,
        provenance: Literal["original", "edited", "invented"],
    ) -> None:
        # Trusted reviewed/masked import only; no raw-input HTTP route exists.
        Principal(
            username="trusted-import",
            tenant_id=tenant,
            actor_id="import",
            role="reviewer",
            case_ids=(complaint.case_id,),
        )
        if not review_ref or len(review_ref) > 96 or len(complaint.narrative) > 20000:
            raise ValueError("bounded reviewed import required")
        if policy.taxonomy_sha256 != taxonomy.digest():
            raise ValueError("taxonomy pin mismatch")
        with self.transaction() as c:
            c.execute(
                "INSERT INTO cfpb_app.cases VALUES(%s,%s,1,%s,%s,%s,%s,%s,NULL,'queued')",
                (
                    tenant,
                    complaint.case_id,
                    Jsonb(complaint.model_dump(mode="json")),
                    review_ref,
                    provenance,
                    Jsonb(taxonomy.model_dump(mode="json")),
                    Jsonb(policy.model_dump(mode="json")),
                ),
            )
            c.execute(
                "INSERT INTO cfpb_app.jobs(tenant_id,case_id,version,state) "
                "VALUES(%s,%s,1,'pending')",
                (tenant, complaint.case_id),
            )
            self._event(
                c,
                {"tenant_id": tenant, "case_id": complaint.case_id, "version": 1},
                "enrolled",
                "case_enrolled",
                "trusted-import",
            )

    def snapshot(self, user: Principal, case: str) -> dict[str, Any]:
        user.require(case)
        with self.transaction() as c:
            row = self._row(c, user.tenant_id, case)
            events = c.execute(
                "SELECT version,kind,actor_id,metadata,created_at FROM cfpb_app.events WHERE"
                " tenant_id=%s AND case_id=%s ORDER BY created_at,event_key",
                (user.tenant_id, case),
            ).fetchall()
            job = c.execute(
                "SELECT state,attempts FROM cfpb_app.jobs WHERE tenant_id=%s AND case_id=%s "
                "AND version=%s",
                (user.tenant_id, case, row["version"]),
            ).fetchone()
            for event in events:
                event["created_at"] = event["created_at"].isoformat()
            return {**row, "events": events, "job": job, "can_review": user.role == "reviewer"}

    def enqueue(self, user: Principal, case: str, command: QueueCommand) -> int:
        user.require(case, write=True)
        pin = digest_text(command.canonical_json())
        with self.transaction() as c:
            row = self._row(c, user.tenant_id, case)
            old = c.execute(
                "SELECT payload_sha,resulting_version FROM cfpb_app.commands WHERE "
                "tenant_id=%s AND case_id=%s AND command_id=%s",
                (user.tenant_id, case, command.command_id),
            ).fetchone()
            if old:
                if old["payload_sha"] != pin:
                    raise StateChanged("command rebound")
                return int(old["resulting_version"])
            if row["version"] != command.expected_version:
                raise StateChanged("refresh case version")
            row["version"] += 1
            c.execute(
                "UPDATE cfpb_app.cases SET version=%s,status='review_queued' WHERE "
                "tenant_id=%s AND case_id=%s",
                (row["version"], user.tenant_id, case),
            )
            c.execute(
                "UPDATE cfpb_app.jobs SET state='obsolete' WHERE tenant_id=%s AND case_id=%s"
                " AND state IN ('pending','leased')",
                (user.tenant_id, case),
            )
            c.execute(
                "INSERT INTO cfpb_app.commands VALUES(%s,%s,%s,%s,%s)",
                (user.tenant_id, case, command.command_id, pin, row["version"]),
            )
            self._event(
                c,
                row,
                "review:" + command.command_id,
                "review_enqueued",
                user.actor_id,
                {"reason": command.reason},
            )
            return int(row["version"])

    def claim(self) -> dict[str, Any] | None:
        with self.transaction() as c:
            job = c.execute(
                "SELECT * FROM cfpb_app.jobs WHERE state='pending' OR (state='leased' AND "
                "lease_until<=%s) ORDER BY tenant_id,case_id FOR UPDATE SKIP LOCKED LIMIT 1",
                (self.clock(),),
            ).fetchone()
            if job is None:
                return None
            lease = secrets.token_hex(16)
            c.execute(
                "UPDATE cfpb_app.jobs SET "
                "state='leased',lease_id=%s,lease_until=%s,attempts=attempts+1 WHERE "
                "tenant_id=%s AND case_id=%s AND version=%s",
                (
                    lease,
                    self.clock() + timedelta(minutes=5),
                    job["tenant_id"],
                    job["case_id"],
                    job["version"],
                ),
            )
            # Do not lock the case while holding the job: writers lock case first.
            row = c.execute(
                "SELECT * FROM cfpb_app.cases WHERE tenant_id=%s AND case_id=%s",
                (job["tenant_id"], job["case_id"]),
            ).fetchone()
            if row is None or row["version"] != job["version"]:
                c.execute(
                    "UPDATE cfpb_app.jobs SET state='obsolete' WHERE tenant_id=%s AND case_id=%s"
                    " AND version=%s",
                    (job["tenant_id"], job["case_id"], job["version"]),
                )
                return None
            return {**row, "lease_id": lease, "attempts": job["attempts"] + 1}

    def finish(self, job: dict[str, Any], decision: Decision) -> bool:
        complaint = ComplaintInput.model_validate_json(json.dumps(job["complaint"]))
        taxonomy = Taxonomy.model_validate_json(json.dumps(job["taxonomy"]))
        policy = RouterPolicy.model_validate_json(json.dumps(job["policy"]))
        if (
            decision.case_id != complaint.case_id
            or decision.narrative_sha256 != digest_text(complaint.narrative)
            or decision.taxonomy_sha256 != taxonomy.digest()
            or decision.policy_sha256 != digest_text(policy.canonical_json())
        ):
            raise ValueError("publication pin mismatch")
        for attempt in decision.attempts:
            if attempt.prediction:
                attempt.prediction.check(complaint, taxonomy)
        if decision.prediction:
            decision.prediction.check(complaint, taxonomy)
        if decision.outcome == "classified":
            from cfpb_triage.classifier import eligible

            if not decision.attempts:
                raise ValueError("classified result needs a completed attempt")
            last = decision.attempts[-1]
            threshold = policy.cheap_threshold if last.route == "cheap" else policy.strong_threshold
            if (
                last.failure
                or last.prediction != decision.prediction
                or not eligible(last.prediction, threshold)
                or any(
                    a.failure
                    or (
                        a.prediction
                        and (
                            a.prediction.priority != "routine" or a.prediction.ambiguity != "clear"
                        )
                    )
                    for a in decision.attempts
                )
            ):
                raise ValueError("classified result violates current routing policy")
        with self.transaction() as c:
            row = self._row(c, job["tenant_id"], job["case_id"])
            lease = c.execute(
                "SELECT * FROM cfpb_app.jobs WHERE tenant_id=%s AND case_id=%s AND "
                "version=%s FOR UPDATE",
                (job["tenant_id"], job["case_id"], job["version"]),
            ).fetchone()
            if (
                row["version"] != job["version"]
                or not lease
                or lease["state"] != "leased"
                or lease["lease_id"] != job["lease_id"]
                or lease["lease_until"] <= self.clock()
            ):
                return False
            c.execute(
                "UPDATE cfpb_app.cases SET result=%s,status=%s WHERE tenant_id=%s AND case_id=%s",
                (
                    Jsonb(decision.model_dump(mode="json")),
                    decision.outcome,
                    job["tenant_id"],
                    job["case_id"],
                ),
            )
            c.execute(
                "UPDATE cfpb_app.jobs SET state='done' WHERE tenant_id=%s AND case_id=%s AND"
                " version=%s",
                (job["tenant_id"], job["case_id"], job["version"]),
            )
            self._event(
                c,
                row,
                "classification:" + str(job["version"]),
                "classification_recorded",
                "worker",
                {
                    "outcome": decision.outcome,
                    "reason": decision.reason,
                    "attempts": len(decision.attempts),
                },
            )
            return True


class ReviewTool:
    """Trusted caller binds identity and case; untrusted text grants no capability."""

    def __init__(self, store: DeskStore, user: Principal, case_id: str) -> None:
        user.require(case_id, write=True)
        self.store, self.user, self.case_id = store, user, case_id

    def enqueue(self, command: QueueCommand) -> int:
        return self.store.enqueue(self.user, self.case_id, command)
