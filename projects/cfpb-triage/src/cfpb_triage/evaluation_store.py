"""Additive v2 evaluation desk: isolated manual arms, append-only work receipts, leases."""

import json
import secrets
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import timedelta
from importlib.resources import files
from typing import Annotated, Any, Literal, LiteralString

from agent_harness.contracts import WireContract
from psycopg import Connection, Cursor, sql
from psycopg.rows import dict_row, tuple_row
from psycopg.types.json import Jsonb
from pydantic import Field

from cfpb_triage.desk_auth import sha
from cfpb_triage.desk_contracts import Principal, StateChanged
from cfpb_triage.desk_store import DeskStore
from cfpb_triage.economics import WorkSample
from cfpb_triage.measurement import Timing, measured, timing_report
from cfpb_triage.scope_routing import MODELS, ScopeDecision, ScopeOutput, ScopePolicy, unique_quote
from cfpb_triage.source_contracts import ComplaintInput
from cfpb_triage.triage_contracts import Id, Taxonomy


def setup_evaluation(admin: Connection[Any], runtime_role: str) -> None:
    """Trusted migration only; old v1 schema and privilege meanings are unchanged."""
    ddl = files("cfpb_triage").joinpath("evaluation.sql").read_text(encoding="utf-8")
    with admin.transaction():
        admin.execute("SELECT pg_advisory_xact_lock(73414037)")
        admin.execute("CREATE SCHEMA IF NOT EXISTS cfpb_eval")
        admin.execute("REVOKE ALL ON SCHEMA cfpb_eval FROM PUBLIC")
        admin.execute(
            "CREATE TABLE IF NOT EXISTS cfpb_eval.schema_pin("
            "version integer PRIMARY KEY,sha256 text NOT NULL)"
        )
        with admin.cursor(row_factory=tuple_row) as cursor:
            current = cursor.execute("SELECT version,sha256 FROM cfpb_eval.schema_pin").fetchall()
        if current and current != [(2, sha(ddl))]:
            raise ValueError("evaluation schema pin mismatch")
        if not current:
            admin.execute(ddl)
            admin.execute("INSERT INTO cfpb_eval.schema_pin VALUES(2,%s)", (sha(ddl),))
        admin.execute(
            sql.SQL("GRANT USAGE ON SCHEMA cfpb_eval TO {}").format(sql.Identifier(runtime_role))
        )
        for table, privileges in (
            ("participants", "SELECT"),
            ("cases", "SELECT,INSERT,UPDATE"),
            ("jobs", "SELECT,INSERT,UPDATE"),
            ("events", "SELECT,INSERT"),
        ):
            admin.execute(
                sql.SQL("GRANT " + privileges + " ON cfpb_eval." + table + " TO {}").format(
                    sql.Identifier(runtime_role)
                )
            )


def provision_participant(admin: Connection[Any], tenant: str, actor: str) -> None:
    # Additional consent/capability. A legacy reviewer is not automatically a study participant.
    Principal(
        username="trusted-import", tenant_id=tenant, actor_id=actor, role="reviewer", case_ids=()
    )
    admin.execute(
        "INSERT INTO cfpb_eval.participants VALUES(%s,%s) ON CONFLICT DO NOTHING", (tenant, actor)
    )


class WorkCommand(WireContract):
    schema_version: Literal[2] = 2
    command_id: Id
    expected_version: Annotated[int, Field(ge=1)]
    operation: Literal["start", "pause", "correct", "accept", "visible"]
    active_seconds: Annotated[float, Field(ge=0, le=14400)] = 0.0
    final: ScopeOutput | None = None
    work_kind: Literal["review", "correction", "oversight"] = "review"


def _query(
    c: Connection[Any], query: LiteralString, params: Sequence[Any] | None = None
) -> Cursor[Any]:
    with measured("database_read" if query.lstrip().startswith("SELECT") else "database_write"):
        return c.execute(query, params)


class EvaluationStore(DeskStore):
    @contextmanager
    def transaction(self) -> Iterator[Connection[Any]]:
        with self.connect() as c:
            c.row_factory = dict_row
            _query(c, "SET statement_timeout=5000")
            _query(c, "SET lock_timeout=2000")
            yield c
            with measured("commit"):
                c.commit()

    def record_profile(
        self, user: Principal, case: str, rows: tuple[Timing, ...], *, worker: bool = False
    ) -> None:
        """Post-response durable timing receipt. Its own write is outside response latency."""
        with self.transaction() as c:
            row = self._case(c, user.tenant_id, case)
            self._allow(c, user, row)
            timings = [
                Timing.model_validate_json(t.canonical_json()).model_dump(mode="json") for t in rows
            ]
            _query(
                c,
                "INSERT INTO cfpb_eval.events VALUES(%s,%s,%s,%s,%s,%s,'api_timing',%s,%s)",
                (
                    user.tenant_id,
                    case,
                    "timing-" + secrets.token_hex(16),
                    "worker" if worker else user.actor_id,
                    sha("timing-v2"),
                    row["version"],
                    self.clock(),
                    Jsonb({"timings": timings}),
                ),
            )

    def _case(self, c: Connection[Any], tenant: str, case: str) -> dict[str, Any]:
        row = _query(
            c,
            "SELECT * FROM cfpb_eval.cases WHERE tenant_id=%s AND case_id=%s FOR UPDATE",
            (tenant, case),
        ).fetchone()
        if row is None:
            raise LookupError("evaluation case unavailable")
        return dict(row)

    def enroll_evaluation(
        self,
        tenant: str,
        complaint: ComplaintInput,
        taxonomy: Taxonomy,
        policy: ScopePolicy,
        *,
        family: str,
        actor: str,
        arm: Literal["manual", "assisted"],
        review_ref: str,
        measurement_basis: Literal["human_attested", "invented", "estimated"] = "invented",
    ) -> None:
        Principal(
            username="trusted-import",
            tenant_id=tenant,
            actor_id=actor,
            role="reviewer",
            case_ids=(complaint.case_id,),
        )
        if (
            not family
            or len(family) > 96
            or not review_ref
            or len(review_ref) > 96
            or len(complaint.narrative) > 20000
            or policy.taxonomy_sha256 != taxonomy.digest()
            or arm not in ("manual", "assisted")
            or measurement_basis not in ("human_attested", "invented", "estimated")
        ):
            raise ValueError("bounded, reviewed and pinned import required")
        with self.transaction() as c:
            _query(
                c,
                "INSERT INTO cfpb_eval.cases(tenant_id,case_id,family,actor_id,arm,complaint,"
                "taxonomy,policy,review_ref,measurement_basis,created_at) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    tenant,
                    complaint.case_id,
                    family,
                    actor,
                    arm,
                    Jsonb(complaint.model_dump(mode="json")),
                    Jsonb(taxonomy.model_dump(mode="json")),
                    Jsonb(policy.model_dump(mode="json")),
                    review_ref,
                    measurement_basis,
                    self.clock(),
                ),
            )
            if arm == "assisted":
                _query(
                    c,
                    "INSERT INTO cfpb_eval.jobs(tenant_id,case_id,version,state) "
                    "VALUES(%s,%s,1,'pending')",
                    (tenant, complaint.case_id),
                )

    def _allow(self, c: Connection[Any], user: Principal, row: dict[str, Any]) -> None:
        user.require(row["case_id"], write=True)
        if (
            row["actor_id"] != user.actor_id
            or _query(
                c,
                "SELECT 1 FROM cfpb_eval.participants WHERE tenant_id=%s AND actor_id=%s",
                (user.tenant_id, user.actor_id),
            ).fetchone()
            is None
        ):
            raise PermissionError("assigned study participant required")

    def evaluation_snapshot(self, user: Principal, case: str) -> dict[str, Any]:
        user.require(case)
        with self.transaction() as c:
            row = self._case(c, user.tenant_id, case)
            self._allow(c, user, row)
            # Never return a candidate to the blinded manual arm, even after acceptance.
            return {
                "case_id": case,
                "version": row["version"],
                "arm": row["arm"],
                "measurement_basis": row["measurement_basis"],
                "work_kind": row["work_kind"],
                "complaint": row["complaint"],
                "taxonomy": row["taxonomy"],
                "result": row["result"] if row["arm"] == "assisted" else None,
                "final_result": row["final_result"],
                "accepted_at": (row["accepted_at"].isoformat() if row["accepted_at"] else None),
                "active_seconds": row["active_seconds"],
                "work_started": row["work_started"].isoformat() if row["work_started"] else None,
            }

    def work(self, user: Principal, case: str, command: WorkCommand) -> int:
        command = WorkCommand.model_validate_json(command.canonical_json())
        user.require(case, write=True)
        with self.transaction() as c:
            row = self._case(c, user.tenant_id, case)
            self._allow(c, user, row)
            old = _query(
                c,
                "SELECT * FROM cfpb_eval.events WHERE tenant_id=%s AND case_id=%s "
                "AND command_id=%s",
                (user.tenant_id, case, command.command_id),
            ).fetchone()
            fingerprint = sha(command.canonical_json())
            if old:
                if old["payload_sha256"] != fingerprint or old["actor_id"] != user.actor_id:
                    raise StateChanged("command receipt differs")
                return int(old["version"])
            if row["version"] != command.expected_version or row["accepted_at"]:
                raise StateChanged("case changed or accepted")
            now = self.clock()
            started = row["work_started"]
            work_kind = row["work_kind"]
            if command.operation in ("start", "visible"):
                if command.active_seconds or command.final is not None:
                    raise ValueError("start/visible cannot carry a work result")
                if command.operation == "start":
                    if started:
                        raise StateChanged("work already active")
                    started = now
                    work_kind = command.work_kind
            else:
                if (
                    not started
                    or not 0 <= command.active_seconds <= (now - started).total_seconds()
                ):
                    raise ValueError("active time must fit open server interval")
                started = None
                if command.operation in ("correct", "accept"):
                    if command.final is None:
                        raise ValueError("explicit final triage required")
                    complaint = ComplaintInput.model_validate_json(json.dumps(row["complaint"]))
                    taxonomy = Taxonomy.model_validate_json(json.dumps(row["taxonomy"]))
                    if command.final.classification:
                        command.final.classification.locate(complaint, taxonomy)
                    for quote in command.final.quotes:
                        if not unique_quote(complaint.narrative, quote):
                            raise ValueError("final scope evidence mismatch")
                elif command.final is not None:
                    raise ValueError("pause cannot finalize")
            version = int(row["version"]) + (0 if command.operation == "visible" else 1)
            final = command.final.model_dump(mode="json") if command.final else row["final_result"]
            _query(
                c,
                "UPDATE cfpb_eval.cases SET version=%s,work_started=%s,work_kind=%s,active_seconds="
                "active_seconds+%s,final_result=%s,accepted_at=%s WHERE tenant_id=%s "
                "AND case_id=%s",
                (
                    version,
                    started,
                    work_kind if started else None,
                    command.active_seconds,
                    Jsonb(final),
                    now if command.operation == "accept" else None,
                    user.tenant_id,
                    case,
                ),
            )
            _query(
                c,
                "INSERT INTO cfpb_eval.events VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    user.tenant_id,
                    case,
                    command.command_id,
                    user.actor_id,
                    fingerprint,
                    version,
                    command.operation,
                    now,
                    Jsonb(
                        {
                            "active_seconds": command.active_seconds,
                            "work_kind": work_kind,
                            "measurement": "human_attestation_not_presence_proof",
                        }
                    ),
                ),
            )
            return version

    def claim_evaluation(self) -> dict[str, Any] | None:
        with self.transaction() as c:
            now = self.clock()
            job = _query(
                c,
                "SELECT j.* FROM cfpb_eval.jobs j JOIN cfpb_eval.cases c "
                "USING(tenant_id,case_id) WHERE c.accepted_at IS NULL "
                "AND c.final_result IS NULL AND "
                "(j.state='pending' OR (j.state='leased' AND j.lease_until<=%s)) "
                "ORDER BY j.case_id FOR UPDATE OF c SKIP LOCKED LIMIT 1",
                (now,),
            ).fetchone()
            if job is None:
                return None
            lease = secrets.token_hex(16)
            _query(
                c,
                "UPDATE cfpb_eval.jobs SET state='leased',lease=%s,lease_until=%s,"
                "attempts=attempts+1 WHERE tenant_id=%s AND case_id=%s AND version=%s",
                (
                    lease,
                    now + timedelta(minutes=5),
                    job["tenant_id"],
                    job["case_id"],
                    job["version"],
                ),
            )
            row = self._case(c, job["tenant_id"], job["case_id"])
            _query(
                c,
                "INSERT INTO cfpb_eval.events VALUES(%s,%s,%s,'worker',%s,%s,'claim',%s,%s)",
                (
                    row["tenant_id"],
                    row["case_id"],
                    "claim-" + lease,
                    sha("claim-v2"),
                    row["version"],
                    now,
                    Jsonb(
                        {
                            "queue_wait_seconds": (now - row["created_at"]).total_seconds()
                            if job["attempts"] == 0 and now >= row["created_at"]
                            else None,
                            "age_at_reclaim_seconds": (now - row["created_at"]).total_seconds()
                            if job["attempts"] > 0 and now >= row["created_at"]
                            else None,
                            "clock_regressed": now < row["created_at"],
                            "clock_basis": "server_wall_since_receipt_not_monotonic_cross_process",
                        }
                    ),
                ),
            )
            return {
                **row,
                "job_version": job["version"],
                "lease": lease,
                "attempts": job["attempts"] + 1,
            }

    def finish_evaluation(self, claim: dict[str, Any], decision: ScopeDecision) -> bool:
        decision = ScopeDecision.model_validate_json(decision.canonical_json())
        with self.transaction() as c:
            row = self._case(c, claim["tenant_id"], claim["case_id"])
            job = _query(
                c,
                "SELECT * FROM cfpb_eval.jobs WHERE tenant_id=%s AND case_id=%s "
                "AND version=%s FOR UPDATE",
                (claim["tenant_id"], claim["case_id"], claim["job_version"]),
            ).fetchone()
            if (
                not job
                or job["state"] != "leased"
                or job["lease"] != claim["lease"]
                or job["lease_until"] <= self.clock()
                or row["accepted_at"]
                or row["final_result"] is not None
                or row["version"] != claim["version"]
                or row["arm"] != "assisted"
            ):
                return False
            complaint = ComplaintInput.model_validate_json(json.dumps(row["complaint"]))
            taxonomy = Taxonomy.model_validate_json(json.dumps(row["taxonomy"]))
            policy = ScopePolicy.model_validate_json(json.dumps(row["policy"]))
            if (
                decision.case_id != row["case_id"]
                or decision.narrative_sha256 != sha(complaint.narrative)
                or decision.taxonomy_sha256 != taxonomy.digest()
                or decision.policy_sha256 != sha(policy.canonical_json())
            ):
                raise ValueError("publication bindings differ")
            if decision.prediction:
                decision.prediction.check(complaint, taxonomy)
            last = decision.attempts[-1]
            routes = tuple(a.route for a in decision.attempts)
            if routes not in (("cheap",), ("strong",), ("cheap", "strong")):
                raise ValueError("invalid attempt order")
            if (
                policy.mode == "cheap_only"
                and routes != ("cheap",)
                or policy.mode == "strong_only"
                and routes != ("strong",)
                or policy.mode == "cheap_first"
                and routes[0] != "cheap"
            ):
                raise ValueError("attempts differ from pinned comparator")
            for a in decision.attempts:
                if a.failure is None and a.model != MODELS[a.route]:
                    raise ValueError("attempt model differs from pinned comparator")
                if a.output:
                    expected = (
                        a.output.classification.locate(complaint, taxonomy)
                        if a.output.classification
                        else None
                    )
                    if a.prediction != expected or a.failure:
                        raise ValueError("attempt output differs from checked prediction")
                    if any(not unique_quote(complaint.narrative, q) for q in a.output.quotes):
                        raise ValueError("scope quote mismatch")
            if len(decision.attempts) > 1:
                first = decision.attempts[0]
                if (
                    first.failure
                    or not first.output
                    or first.output.scope != "in_scope"
                    or not first.prediction
                    or first.prediction.priority != "routine"
                    or first.prediction.ambiguity != "clear"
                ):
                    raise ValueError("escalation after failure, risk or scope stop")
            if decision.scope != (last.output.scope if last.output else None):
                raise ValueError("scope differs from final attempt")
            if decision.action == "classified":
                threshold = (
                    policy.cheap_threshold if last.route == "cheap" else policy.strong_threshold
                )
                if (
                    not last.output
                    or not decision.prediction
                    or decision.scope != "in_scope"
                    or decision.prediction != last.prediction
                    or decision.prediction.priority != "routine"
                    or decision.prediction.ambiguity != "clear"
                    or decision.prediction.product is None
                    or decision.prediction.confidence < threshold
                    or last.output.confidence < policy.scope_threshold
                    or any(
                        a.failure
                        or not a.prediction
                        or a.prediction.priority != "routine"
                        or a.prediction.ambiguity != "clear"
                        for a in decision.attempts
                    )
                ):
                    raise ValueError("invalid automatic publication")
            elif decision.action == "scope_response":
                if (
                    not last.output
                    or decision.scope != "out_of_scope"
                    or len(decision.attempts) != 1
                    or last.output.confidence < policy.scope_threshold
                    or any(a.failure for a in decision.attempts)
                ):
                    raise ValueError("invalid scope response")
            _query(
                c,
                "UPDATE cfpb_eval.cases SET result=%s,version=version+1 WHERE tenant_id=%s "
                "AND case_id=%s",
                (Jsonb(decision.model_dump(mode="json")), row["tenant_id"], row["case_id"]),
            )
            _query(
                c,
                "UPDATE cfpb_eval.jobs SET state='done' WHERE tenant_id=%s AND case_id=%s "
                "AND version=%s",
                (row["tenant_id"], row["case_id"], claim["job_version"]),
            )
            _query(
                c,
                "INSERT INTO cfpb_eval.events VALUES(%s,%s,%s,'worker',%s,%s,'publication',%s,%s)",
                (
                    row["tenant_id"],
                    row["case_id"],
                    "publish-" + claim["lease"],
                    sha(decision.canonical_json()),
                    row["version"] + 1,
                    self.clock(),
                    Jsonb({"timings": [t.model_dump(mode="json") for t in decision.timings]}),
                ),
            )
            return True

    def export_work(self, user: Principal, *, currency: str) -> tuple[WorkSample, ...]:
        """Scoped private projection; acceptance is not independent correctness/cost evidence."""
        result = []
        for case in user.case_ids:
            with self.transaction() as c:
                try:
                    row = self._case(c, user.tenant_id, case)
                except LookupError:
                    continue
                self._allow(c, user, row)
                totals = {"review": 0.0, "correction": 0.0, "oversight": 0.0}
                events = _query(
                    c,
                    "SELECT metadata FROM cfpb_eval.events WHERE tenant_id=%s "
                    "AND case_id=%s AND kind IN ('pause','correct','accept')",
                    (user.tenant_id, case),
                ).fetchall()
                for event in events:
                    meta = event["metadata"]
                    totals[meta["work_kind"]] += meta["active_seconds"]
                result.append(
                    WorkSample(
                        case_id=case,
                        family=row["family"],
                        actor=user.actor_id,
                        arm=row["arm"],
                        basis=row["measurement_basis"],
                        arrived=row["created_at"],
                        accepted=row["accepted_at"],
                        initial_seconds=totals["review"],
                        correction_seconds=totals["correction"],
                        oversight_seconds=totals["oversight"],
                        correct=None,
                        currency=currency,
                    )
                )
        return tuple(result)

    def export_timings(self, user: Principal) -> dict[str, object]:
        runs = []
        cases_present = 0
        for case in user.case_ids:
            with self.transaction() as c:
                try:
                    row = self._case(c, user.tenant_id, case)
                except LookupError:
                    continue
                self._allow(c, user, row)
                events = _query(
                    c,
                    "SELECT metadata FROM cfpb_eval.events WHERE tenant_id=%s "
                    "AND case_id=%s AND kind='api_timing'",
                    (user.tenant_id, case),
                ).fetchall()
                cases_present += bool(events)
                for event in events:
                    runs.append(
                        tuple(
                            Timing.model_validate_json(json.dumps(t))
                            for t in event["metadata"]["timings"]
                        )
                    )
        return {
            "case_scope": len(user.case_ids),
            "cases_with_timing_receipts": cases_present,
            "profile": timing_report(runs),
            "telemetry_write_overhead": "excluded",
            "source": "post-commit timing receipts only; pre-commit copies not added",
        }
