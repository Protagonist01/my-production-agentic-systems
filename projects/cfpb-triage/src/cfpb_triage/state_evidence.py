"""Independent scoped review-command SQL evidence; no privacy or model-quality credit."""

import json
from typing import Any, Literal

from agent_harness.contracts import Contract, NonEmpty
from agent_harness.release_contracts import pin, sha256
from psycopg import Connection
from pydantic import JsonValue

from cfpb_triage.desk_contracts import Principal, QueueCommand


class QueueState(Contract):
    tenant_id: NonEmpty
    case_id: NonEmpty
    version: int
    status: str
    source_sha256: str
    jobs: tuple[dict[str, JsonValue], ...]
    events: tuple[dict[str, JsonValue], ...]
    commands: tuple[dict[str, JsonValue], ...]


class QueueEvidence(Contract):
    version: Literal["cfpb-review-command-state-v1"] = "cfpb-review-command-state-v1"
    before: QueueState
    after: QueueState
    restarted: QueueState
    duplicate: QueueState


def collect_queue(connection: Connection[Any], tenant: str, case: str) -> QueueState:
    """Read only one explicit case; no sessions, credentials or source text are exported."""
    with connection.transaction():
        connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        row = connection.execute(
            "SELECT version,status,complaint,review_ref,provenance,taxonomy,policy,result "
            "FROM cfpb_app.cases WHERE tenant_id=%s AND case_id=%s",
            (tenant, case),
        ).fetchone()
        if row is None:
            raise ValueError("review evidence case missing")
        jobs = connection.execute(
            "SELECT version,state,attempts,lease_id,lease_until FROM cfpb_app.jobs "
            "WHERE tenant_id=%s AND case_id=%s ORDER BY version",
            (tenant, case),
        ).fetchall()
        events = connection.execute(
            "SELECT event_key,version,kind,actor_id,metadata FROM cfpb_app.events "
            "WHERE tenant_id=%s AND case_id=%s ORDER BY event_key",
            (tenant, case),
        ).fetchall()
        commands = connection.execute(
            "SELECT command_id,payload_sha,resulting_version FROM cfpb_app.commands "
            "WHERE tenant_id=%s AND case_id=%s ORDER BY command_id",
            (tenant, case),
        ).fetchall()
    return QueueState(
        tenant_id=tenant,
        case_id=case,
        version=row[0],
        status=row[1],
        source_sha256=sha256(json.dumps(row[2:], sort_keys=True, separators=(",", ":")).encode()),
        jobs=tuple(
            dict(
                version=v, state=s, attempts=a, lease_id=i, lease_until=t.isoformat() if t else None
            )
            for v, s, a, i, t in jobs
        ),
        events=tuple(
            dict(event_key=k, version=v, kind=s, actor_id=a, metadata=m) for k, v, s, a, m in events
        ),
        commands=tuple(
            dict(command_id=k, payload_sha=p, resulting_version=v) for k, p, v in commands
        ),
    )


def assess_queue(
    evidence: QueueEvidence, user: Principal, case: str, command: QueueCommand
) -> dict[str, object]:
    evidence = QueueEvidence.model_validate_json(evidence.canonical_json())
    user = Principal.model_validate_json(user.canonical_json())
    command = QueueCommand.model_validate_json(command.canonical_json())
    user.require(case, write=True)
    before = evidence.before
    if (before.tenant_id, before.case_id, before.version) != (
        user.tenant_id,
        case,
        command.expected_version,
    ):
        raise ValueError("review evidence expectation scope differs")
    # One explicit enqueue, no background worker. Preserve source/result pin and all prior rows.
    if any(c["command_id"] == command.command_id for c in before.commands):
        raise ValueError("review command must be new in the before-state")
    event_key = "review:" + command.command_id
    if any(e["event_key"] == event_key for e in before.events):
        raise ValueError("review event already exists in the before-state")
    expected = before.model_copy(
        update={
            "version": before.version + 1,
            "status": "review_queued",
            "jobs": tuple(
                {**j, "state": "obsolete"} if j["state"] in ("pending", "leased") else j
                for j in before.jobs
            ),
            "commands": tuple(
                sorted(
                    (
                        *before.commands,
                        dict(
                            command_id=command.command_id,
                            payload_sha=pin(command),
                            resulting_version=before.version + 1,
                        ),
                    ),
                    key=lambda c: str(c["command_id"]),
                )
            ),
            "events": tuple(
                sorted(
                    (
                        *before.events,
                        dict(
                            event_key=event_key,
                            version=before.version + 1,
                            kind="review_enqueued",
                            actor_id=user.actor_id,
                            metadata={"reason": command.reason},
                        ),
                    ),
                    key=lambda e: str(e["event_key"]),
                )
            ),
        }
    )
    exact = evidence.after == evidence.restarted == evidence.duplicate == expected
    return dict(
        version=evidence.version,
        evidence_sha256=pin(evidence),
        review_command_durable=exact,
        exact_scoped_delta=exact,
        mechanism_only=True,
        provider_calls=0,
        release_allowed=False,
        limitations="One scoped enqueue without concurrent worker; no privacy, "
        "classifier quality, complete tenant state or full fault-matrix claim.",
    )
