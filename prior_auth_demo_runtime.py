"""Opt-in SQL-worker assessor with durable per-criterion model attempt control.

No credential loader, provider creation or implicit live scope. A trusted caller must
inject the separately authorized gateway. The shipped demo CLI uses only a fake SDK.
"""

import json
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Any, Literal, Self

from agent_harness.admission import GEMINI_TOKEN_CEILING
from agent_harness.contracts import (
    Budget,
    CandidateVersions,
    ModelGateway,
    ModelRequest,
    ModelResponse,
    RunContext,
    WireContract,
)
from agent_harness.gateway import failed_response
from prior_auth.contracts import (
    CandidateAssessment,
    Digest,
    Id,
    NoteInput,
    Policy,
    digest,
)
from prior_auth.review_contracts import StateChanged
from prior_auth.review_store import ReviewStore, contract
from psycopg import Connection, sql
from psycopg.rows import tuple_row
from psycopg.types.json import Jsonb
from pydantic import AwareDatetime, Field, model_validator

from prior_auth_complete_citations import VERSION, extract_complete
from prior_auth_profiling import Profiler


class Scope(WireContract):
    scope_id: Id
    tenant_id: Id
    case_ids: Annotated[tuple[Id, ...], Field(min_length=1, max_length=100)]
    mode: Literal["offline_fake", "fresh_candidate"]
    authorization_ref: Annotated[str, Field(min_length=1, max_length=200)]
    # A shared provider allowance is a separate prerequisite for any live delegate.
    provider_scope_sha256: Digest | None = None
    candidate: Literal["prior-auth-complete-citations-v1"] = "prior-auth-complete-citations-v1"
    code_revision: Annotated[str, Field(min_length=1, max_length=128)]
    environment_sha256: Digest
    starts_at: AwareDatetime
    expires_at: AwareDatetime
    max_attempts: Annotated[int, Field(ge=1, le=10000)]
    max_tokens: Annotated[int, Field(ge=GEMINI_TOKEN_CEILING, le=1_000_000_000)]
    request_sha256s: Annotated[tuple[Digest, ...], Field(min_length=1, max_length=10000)]

    @model_validator(mode="after")
    def valid(self) -> Self:
        if (
            self.expires_at <= self.starts_at
            or len(set(self.case_ids)) != len(self.case_ids)
            or (len(set(self.request_sha256s)) != len(self.request_sha256s))
            or (self.mode == "fresh_candidate" and self.provider_scope_sha256 is None)
        ):
            raise ValueError("bounded unique scope and live provider authority required")
        return self


def setup(admin: Connection[Any], runtime_role: str) -> None:
    ddl = Path(__file__).with_suffix(".sql").read_text(encoding="utf-8")
    with admin.transaction():
        admin.execute("SELECT pg_advisory_xact_lock(73414051)")
        admin.execute("CREATE SCHEMA IF NOT EXISTS prior_auth_demo")
        admin.execute("REVOKE ALL ON SCHEMA prior_auth_demo FROM PUBLIC")
        admin.execute(
            "CREATE TABLE IF NOT EXISTS prior_auth_demo.schema_pin("
            "version integer PRIMARY KEY,sha256 text NOT NULL)"
        )
        with admin.cursor(row_factory=tuple_row) as cursor:
            current = cursor.execute(
                "SELECT version,sha256 FROM prior_auth_demo.schema_pin"
            ).fetchall()
        if current and current != [(1, digest(ddl))]:
            raise ValueError("demo runtime schema pin differs")
        if not current:
            admin.execute(ddl)
            admin.execute("INSERT INTO prior_auth_demo.schema_pin VALUES(1,%s)", (digest(ddl),))
        admin.execute(
            sql.SQL("GRANT USAGE ON SCHEMA prior_auth_demo TO {}").format(
                sql.Identifier(runtime_role)
            )
        )
        # Scope provisioning is trusted administration only. Runtime cannot extend it.
        admin.execute(
            sql.SQL("GRANT SELECT ON prior_auth_demo.scopes TO {}").format(
                sql.Identifier(runtime_role)
            )
        )
        for table in ("attempts", "settlements"):
            admin.execute(
                sql.SQL("GRANT SELECT,INSERT ON prior_auth_demo.{} TO {}").format(
                    sql.Identifier(table), sql.Identifier(runtime_role)
                )
            )


def provision_scope(admin: Connection[Any], scope: Scope) -> str:
    scope = Scope.model_validate_json(scope.canonical_json())
    pin = digest(scope.canonical_json())
    with admin.transaction():
        prior = admin.execute(
            "SELECT scope_sha256 FROM prior_auth_demo.scopes WHERE scope_id=%s", (scope.scope_id,)
        ).fetchone()
        if prior:
            if prior[0] != pin:
                raise StateChanged("scope identity reused")
            return pin
        admin.execute(
            "INSERT INTO prior_auth_demo.scopes VALUES(%s,%s,%s)",
            (scope.scope_id, pin, Jsonb(scope.model_dump(mode="json"))),
        )
    return pin


class DurableGateway:
    def __init__(
        self,
        store: ReviewStore,
        job: dict[str, Any],
        scope: Scope,
        delegate: ModelGateway,
        *,
        provider_validator: Callable[[Scope, ModelRequest], None] | None = None,
    ) -> None:
        self.store, self.job, self.scope, self.delegate = store, job, scope, delegate
        self.provider_validator = provider_validator
        self.sent = self.replayed = self.blocked = 0

    def generate(self, context: RunContext, request: ModelRequest) -> ModelResponse:
        request = ModelRequest.model_validate_json(request.canonical_json())
        scope, job = Scope.model_validate_json(self.scope.canonical_json()), self.job
        note, policy = contract(job["note"], NoteInput), contract(job["policy"], Policy)
        payload = json.loads(request.messages[1].content or "")
        key = payload["criterion"]["criterion_id"]
        if (
            context.mode != scope.mode
            or context.versions.candidate != scope.candidate
            or (context.tenant_id, context.case_id) != (scope.tenant_id, note.case_id)
            or (
                note.case_id not in scope.case_ids
                or note.provenance != "invented"
                or request.fingerprint() not in scope.request_sha256s
                or key not in job["criteria"]
                or payload["note_sha256"] != note.note_sha256
                or payload["full_note"] != note.text
                or payload["criterion"]
                != next(c.model_dump(mode="json") for c in policy.criteria if c.criterion_id == key)
            )
        ):
            raise PermissionError("runtime request/context outside provisioned scope")
        work = digest(
            json.dumps(
                {
                    "tenant": note.tenant_id,
                    "case": note.case_id,
                    "version": job["version"],
                    "note": note.note_sha256,
                    "policy": note.policy_sha256,
                    "criterion": key,
                    "candidate": VERSION,
                },
                sort_keys=True,
            )
        )
        with self.store.transaction() as c:
            # Case -> job lock order matches publication; serialize the scope using
            # an advisory lock because the runtime role cannot UPDATE scope rows.
            current = self.store._row(c, note.tenant_id, note.case_id)
            active = c.execute(
                "SELECT * FROM prior_auth_app.jobs WHERE tenant_id=%s AND case_id=%s "
                "AND version=%s FOR UPDATE",
                (note.tenant_id, note.case_id, job["version"]),
            ).fetchone()
            c.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,73414051))", (scope.scope_id,)
            )
            bound = c.execute(
                "SELECT scope_sha256,document FROM prior_auth_demo.scopes WHERE scope_id=%s",
                (scope.scope_id,),
            ).fetchone()
            now = self.store.now()
            if (
                not bound
                or bound["scope_sha256"] != digest(scope.canonical_json())
                or (Scope.model_validate_json(json.dumps(bound["document"])) != scope)
                or not scope.starts_at <= now < scope.expires_at
            ):
                raise PermissionError("runtime scope missing, changed or expired")
            if (
                not active
                or active["state"] != "leased"
                or active["lease_id"] != job["lease_id"]
                or active["lease_until"] <= now
                or current["version"] != job["version"]
                or current["note"] != job["note"]
                or current["policy"] != job["policy"]
            ):
                raise StateChanged("current case/job lease differs before provider admission")
            prior = c.execute(
                "SELECT a.request_sha256,s.response,s.response_sha256 "
                "FROM prior_auth_demo.attempts a "
                "LEFT JOIN prior_auth_demo.settlements s USING(scope_id,work_sha256) "
                "WHERE a.scope_id=%s AND a.work_sha256=%s",
                (scope.scope_id, work),
            ).fetchone()
            if prior:
                if prior["request_sha256"] != request.fingerprint():
                    raise StateChanged("criterion work reused with a different request")
                if prior["response"] is None:
                    self.blocked += 1
                    return failed_response(
                        request,
                        "unavailable",
                        "Prior attempt outcome unknown; review required",
                        dispatched=False,
                    )
                response = ModelResponse.model_validate_json(json.dumps(prior["response"]))
                if digest(response.canonical_json()) != prior["response_sha256"]:
                    raise StateChanged("stored provider response differs")
                self.replayed += 1
                return response
            totals = c.execute(
                "SELECT count(*) AS n,count(s.work_sha256) AS settled, "
                "COALESCE(sum(s.tokens),0) AS tokens,COALESCE(bool_or(s.stop),false) AS stopped "
                "FROM prior_auth_demo.attempts a LEFT JOIN prior_auth_demo.settlements s "
                "USING(scope_id,work_sha256) "
                "WHERE a.scope_id=%s",
                (scope.scope_id,),
            ).fetchone()
            if totals is None:
                raise StateChanged("runtime admission aggregate unavailable")
            if (
                totals["stopped"]
                or totals["n"] != totals["settled"]
                or totals["n"] >= scope.max_attempts
                or (totals["tokens"] + GEMINI_TOKEN_CEILING > scope.max_tokens)
            ):
                self.blocked += 1
                return failed_response(
                    request, "budget_exhausted", "Runtime admission blocked", dispatched=False
                )
            if scope.mode == "fresh_candidate":
                if self.provider_validator is None:
                    raise PermissionError("shared live provider authorization validator required")
                self.provider_validator(scope, request)
            c.execute(
                "INSERT INTO prior_auth_demo.attempts VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    scope.scope_id,
                    work,
                    note.tenant_id,
                    note.case_id,
                    job["version"],
                    key,
                    request.fingerprint(),
                    now,
                ),
            )
        # Reservation is committed before I/O. A process death leaves it outstanding.
        self.sent += 1
        try:
            response = ModelResponse.model_validate_json(
                self.delegate.generate(context, request).canonical_json()
            )
            if (response.provider, response.model) != (request.provider, request.model):
                raise ValueError("provider response route differs")
        except Exception:
            response = failed_response(
                request,
                "unavailable",
                "Provider result unavailable; usage unknown",
                dispatched=True,
            )
        usage = response.usage
        tokens = (
            None
            if usage.input_tokens is None or usage.output_tokens is None
            else usage.input_tokens + usage.output_tokens
        )
        stop = (
            response.failure is not None
            or tokens is None
            or tokens > GEMINI_TOKEN_CEILING
            or usage.model_calls != 1
            or (usage.cost is not None and usage.cost != 0)
        )
        with self.store.transaction() as c:
            c.execute(
                "INSERT INTO prior_auth_demo.settlements VALUES(%s,%s,%s,%s,%s,%s)",
                (
                    scope.scope_id,
                    work,
                    digest(response.canonical_json()),
                    Jsonb(response.model_dump(mode="json")),
                    tokens,
                    stop,
                ),
            )
        return response


class DemoWorker:
    def __init__(
        self,
        store: ReviewStore,
        scope: Scope,
        gateway: ModelGateway,
        *,
        provider_validator: Callable[[Scope, ModelRequest], None] | None = None,
        profiler: Profiler | None = None,
    ) -> None:
        self.store, self.scope, self.gateway = store, scope, gateway
        self.provider_validator, self.profiler = provider_validator, profiler or Profiler()

    def step(self) -> dict[str, object]:
        scope = Scope.model_validate_json(self.scope.canonical_json())
        if not scope.starts_at <= self.store.now() < scope.expires_at:
            raise PermissionError("demo runtime scope expired/not active")
        if scope.mode == "fresh_candidate" and self.provider_validator is None:
            raise PermissionError("no live provider authority installed")
        # Only claim allowed tenant/cases. A generic global claim could consume work
        # belonging to another scope and publish an accidental review result.
        with self.store.transaction() as c:
            ready = c.execute(
                "SELECT * FROM prior_auth_app.jobs WHERE tenant_id=%s AND case_id=ANY(%s) "
                "AND (state='pending' OR (state='leased' AND lease_until<=%s)) "
                "ORDER BY case_id,version FOR UPDATE SKIP LOCKED LIMIT 1",
                (scope.tenant_id, list(scope.case_ids), self.store.now()),
            ).fetchone()
            if not ready:
                return {"claimed": False, "published": False, "sent": 0, "replayed": 0}
            import secrets
            from datetime import timedelta

            lease = secrets.token_hex(24)
            c.execute(
                "UPDATE prior_auth_app.jobs SET state='leased',lease_id=%s,lease_until=%s,"
                "attempts=attempts+1 "
                "WHERE tenant_id=%s AND case_id=%s AND version=%s",
                (
                    lease,
                    self.store.now() + timedelta(minutes=5),
                    ready["tenant_id"],
                    ready["case_id"],
                    ready["version"],
                ),
            )
            row = c.execute(
                "SELECT note,policy,candidate FROM prior_auth_app.cases "
                "WHERE tenant_id=%s AND case_id=%s AND version=%s",
                (ready["tenant_id"], ready["case_id"], ready["version"]),
            ).fetchone()
            if row is None:
                c.execute(
                    "UPDATE prior_auth_app.jobs SET state='obsolete' "
                    "WHERE tenant_id=%s AND case_id=%s AND version=%s",
                    (ready["tenant_id"], ready["case_id"], ready["version"]),
                )
                return {"claimed": False, "published": False, "sent": 0, "replayed": 0}
            job = dict(ready, lease_id=lease, **dict(row))
        note, policy = contract(job["note"], NoteInput), contract(job["policy"], Policy)
        context = RunContext(
            run_id=scope.scope_id,
            tenant_id=scope.tenant_id,
            agent_id="prior-auth",
            case_id=note.case_id,
            trial_id="case-version-" + str(job["version"]),
            business_event_id=digest(note.canonical_json()),
            mode=scope.mode,
            clock=self.store.now(),
            deadline=scope.expires_at,
            seed=0,
            budget=Budget(
                max_model_calls=scope.max_attempts,
                max_tokens=scope.max_tokens,
                max_cost=Decimal(0),
                cost_currency="USD",
            ),
            versions=CandidateVersions(
                code_revision=scope.code_revision,
                candidate=VERSION,
                data_snapshot=note.note_sha256,
                policy=note.policy_sha256,
                environment_lock=scope.environment_sha256,
            ),
        )
        durable = DurableGateway(
            self.store, job, scope, self.gateway, provider_validator=self.provider_validator
        )
        with self.profiler.span("assessment"):
            proposed = extract_complete(durable, context, note, policy, tuple(job["criteria"]))
        candidate: CandidateAssessment | None = None
        if proposed is not None:
            retained = contract(job["candidate"], CandidateAssessment) if job["candidate"] else None
            kept = (
                tuple(c for c in retained.claims if c.criterion_id not in job["criteria"])
                if retained
                else ()
            )
            candidate = proposed.model_copy(update={"claims": kept + proposed.claims})
        published = self.store.finish(job, candidate)
        return {
            "claimed": True,
            "published": published,
            "sent": durable.sent,
            "replayed": durable.replayed,
            "blocked": durable.blocked,
            "candidate": VERSION,
            "clinical_validation": False,
        }
