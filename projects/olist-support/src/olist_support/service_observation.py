"""Read-only, single-snapshot observation of the customer-confirmed SIM service.

Private evaluator artifacts contain source text but never password/session/challenge tokens.
An observation proves the database contents read, not source-label quality or provider origin.
"""

import json
from datetime import datetime
from typing import Any, Literal

from agent_harness.contracts import Contract
from psycopg import Connection
from psycopg.rows import tuple_row

from olist_support.console_contracts import CaseRecord, Principal
from olist_support.customer_intent import Authority
from olist_support.release import StateSnapshot, collect_state


class AccountState(Contract):
    principal: Principal
    enabled: bool


class CaseState(Contract):
    tenant_id: str
    case_id: str
    request_sha256: str
    actor_id: str
    order_id: str
    version: int
    status: str
    document: CaseRecord


class AuthorityState(Contract):
    tenant_id: str
    case_id: str
    state: Literal["pending", "confirmed", "consumed"]
    document: Authority


class AuditState(Contract):
    event_id: str
    tenant_id: str
    case_id: str
    actor_id: str
    kind: str
    at: datetime
    detail: dict[str, Any]


class ServiceSnapshot(Contract):
    business: StateSnapshot
    accounts: tuple[AccountState, ...]
    cases: tuple[CaseState, ...]
    authorities: tuple[AuthorityState, ...]
    events: tuple[AuditState, ...]


def collect_service_state(connection: Connection[Any]) -> ServiceSnapshot:
    """Own one idle evaluator connection and one repeatable-read, read-only transaction.

    All tenants are observed, including effects outside the candidate's order scope.
    Explicit columns exclude authentication material even from private evidence files.
    """
    with connection.transaction(), connection.cursor(row_factory=tuple_row) as cursor:
        cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        business = collect_state(connection, in_snapshot=True)
        accounts = tuple(
            AccountState(principal=Principal.model_validate_json(json.dumps(p)), enabled=enabled)
            for p, enabled in cursor.execute(
                "SELECT principal,enabled FROM olist_app.accounts ORDER BY username"
            ).fetchall()
        )
        cases = tuple(
            CaseState(
                tenant_id=t,
                case_id=c,
                request_sha256=h,
                actor_id=a,
                order_id=o,
                version=v,
                status=s,
                document=CaseRecord.model_validate_json(json.dumps(d)),
            )
            for t, c, h, a, o, v, s, d in cursor.execute(
                "SELECT tenant_id,case_id,request_hash,actor_id,order_id,version,status,document "
                "FROM olist_app.cases ORDER BY tenant_id,case_id"
            ).fetchall()
        )
        authorities = tuple(
            AuthorityState(
                tenant_id=t,
                case_id=c,
                state=s,
                document=Authority.model_validate_json(json.dumps(d)),
            )
            for t, c, s, d in cursor.execute(
                "SELECT tenant_id,case_id,state,document FROM olist_intent.challenges "
                "ORDER BY tenant_id,case_id"
            ).fetchall()
        )
        events = tuple(
            AuditState(event_id=e, tenant_id=t, case_id=c, actor_id=a, kind=k, at=at, detail=d)
            for e, t, c, a, k, at, d in cursor.execute(
                "SELECT event_id,tenant_id,case_id,actor_id,kind,at,detail "
                "FROM olist_app.events ORDER BY at,event_id"
            ).fetchall()
        )
    return ServiceSnapshot(
        business=business, accounts=accounts, cases=cases, authorities=authorities, events=events
    )
