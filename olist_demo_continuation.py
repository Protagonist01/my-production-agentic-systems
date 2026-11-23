"""Explicitly authorized next-slot continuation; never reset a stopped study or retry a slot.

Preparation and readback are read-only. Execution needs a separately pinned owner grant.
The parent scope/stop and every failed response stay unchanged in the original ledger.
"""

import argparse
import json
import sqlite3
import time
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Literal, Self

from agent_harness.admission import GEMINI_TOKEN_CEILING
from agent_harness.contracts import ModelResponse, WireContract
from agent_harness.gateway import DeadlineTransport
from pydantic import AwareDatetime, Field, model_validator

from olist_demo_acceptance import canonical, digest
from olist_demo_capture import ROOT, source_pin, verify_runtime, write
from olist_demo_evaluation import Observation, baselines, summarize
from olist_demo_study import TABLES, Ledger, OwnerGrant, Pin, Scope
from olist_demo_worker import SDKTransport, SDKWorker, environment_pin


class ContinuationScope(WireContract):
    version: Literal["olist-demo-next-slot-continuation-v1"] = (
        "olist-demo-next-slot-continuation-v1"
    )
    parent_scope_sha256: Pin
    parent_prefix_sha256: Pin
    parent_attempts: Annotated[int, Field(ge=3, le=145)]
    source_sha256: Pin
    environment_sha256: Pin
    starts_at: AwareDatetime
    expires_at: AwareDatetime
    max_accounted_tokens: Literal[10000000] = 10000000
    max_http_failures: Literal[7] = 7
    consecutive_http_stop: Literal[3] = 3
    cooldown_seconds: Literal[60] = 60

    @model_validator(mode="after")
    def window(self) -> Self:
        if self.starts_at >= self.expires_at:
            raise ValueError("unexpired original window required")
        return self


def http_server_failure(response: ModelResponse) -> bool:
    """Recognize only the inspected SDK's sanitized HTTP >=500 branch, excluding 504.

    Exact status/body were not retained by that SDK version; do not invent a 503.
    Network, worker, timeout, permission and quota failures do not enter this branch.
    """
    failure = response.failure
    return bool(
        failure
        and failure.code == "unavailable"
        and failure.message == "Gemini HTTP request failed"
        and failure.retryable
        and response.usage.model_calls == 1
    )


def prefix_pin(db: sqlite3.Connection, count: int) -> str:
    """Bind original DDL, parent authority/stop and every original captured byte."""
    from olist_demo_budget_readback import historical_hash

    schema = [
        row
        for row in db.execute("SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name")
        if row[2] in TABLES
    ]
    return digest(
        canonical(
            {
                "historical": historical_hash(db, TABLES),
                "demo_schema": schema,
                "scope": db.execute("SELECT * FROM olist_demo_scope ORDER BY id").fetchall(),
                "stop": db.execute("SELECT * FROM olist_demo_stop ORDER BY id").fetchall(),
                "attempts": db.execute(
                    "SELECT * FROM olist_demo_attempts WHERE ordinal<=? ORDER BY ordinal", (count,)
                ).fetchall(),
                "results": db.execute(
                    "SELECT * FROM olist_demo_results WHERE ordinal<=? ORDER BY ordinal", (count,)
                ).fetchall(),
            }
        )
    )


def responses(db: sqlite3.Connection) -> list[tuple[int, ModelResponse]]:
    return [
        (ordinal, ModelResponse.model_validate_json(raw))
        for ordinal, raw in db.execute(
            "SELECT ordinal,response FROM olist_demo_results ORDER BY ordinal"
        )
    ]


def accounted_tokens(rows: list[tuple[int, ModelResponse]]) -> int:
    """An unknown row reserves the full reviewed route ceiling, never zero tokens."""
    return sum(
        GEMINI_TOKEN_CEILING
        if r.usage.input_tokens is None or r.usage.output_tokens is None
        else r.usage.input_tokens + r.usage.output_tokens
        for _, r in rows
    )


def halt_reason(rows: list[tuple[int, ModelResponse]], scope: ContinuationScope) -> str | None:
    http_count = consecutive = 0
    for ordinal, response in rows:
        usage = response.usage
        if usage.model_calls != 1 or (usage.cost is not None and usage.cost != 0):
            return "unexpected_call_or_nonzero_cost"
        if http_server_failure(response):
            http_count += 1
            consecutive += 1
            if http_count > scope.max_http_failures or consecutive >= scope.consecutive_http_stop:
                return "http_failure_circuit"
            continue
        consecutive = 0
        if usage.input_tokens is None or usage.output_tokens is None:
            return "unknown_usage_outside_http_server_failure"
        if usage.input_tokens + usage.output_tokens > GEMINI_TOKEN_CEILING:
            return "reported_usage_exceeds_reviewed_ceiling"
        if response.failure and not (ordinal > 2 and response.failure.code == "invalid_response"):
            return "noncontinuable_provider_failure"
    if accounted_tokens(rows) + GEMINI_TOKEN_CEILING > scope.max_accounted_tokens:
        return "conservative_token_limit"
    return None


class Continuation:
    def __init__(
        self,
        path: Path,
        scope: ContinuationScope,
        grant: OwnerGrant | None = None,
        *,
        trusted_grant_sha256: str | None = None,
    ) -> None:
        self.scope = ContinuationScope.model_validate_json(scope.canonical_json())
        self.pin = digest(self.scope.canonical_json().encode())
        self.ledger = Ledger(path, self.scope.parent_scope_sha256)
        if grant is not None:
            grant = OwnerGrant.model_validate_json(grant.canonical_json())
        with closing(self.ledger.connect()) as db:
            parent = self.check(db)
        if parent.origin == "provider" and (
            grant is None
            or digest(grant.canonical_json().encode()) != trusted_grant_sha256
            or grant.scope_sha256 != self.pin
        ):
            raise PermissionError("new exact owner grant/current Free confirmation required")
        if parent.origin == "mock" and (grant is not None or trusted_grant_sha256 is not None):
            raise PermissionError("mock continuation cannot carry provider authority")

    def check(self, db: sqlite3.Connection) -> Scope:
        return self.validate_parent(db, self.ledger, self.scope)

    @staticmethod
    def validate_parent(db: sqlite3.Connection, ledger: Ledger, scope: ContinuationScope) -> Scope:
        parent = ledger.scope(db)
        if (
            scope.environment_sha256 != parent.environment_sha256
            or scope.expires_at != parent.expires_at
            or scope.starts_at < parent.starts_at
            or prefix_pin(db, scope.parent_attempts) != scope.parent_prefix_sha256
            or db.execute("SELECT count(*) FROM olist_demo_stop").fetchone()[0] != 1
            or db.execute(
                "SELECT count(*) FROM olist_demo_results WHERE ordinal<=2 AND canary_pass=1"
            ).fetchone()[0]
            != 2
        ):
            raise PermissionError(
                "parent history, canaries, environment or original expiry differs"
            )
        attempts = db.execute(
            "SELECT ordinal,request_sha256 FROM olist_demo_attempts ORDER BY ordinal"
        ).fetchall()
        if (
            not scope.parent_attempts <= len(attempts) <= 146
            or [i for i, _ in attempts] != list(range(1, len(attempts) + 1))
            or any(pin != parent.schedule[i - 1].request.fingerprint() for i, pin in attempts)
        ):
            raise PermissionError("exact contiguous original request schedule required")
        rows = responses(db)
        if (
            [i for i, _ in rows] != list(range(1, len(rows) + 1))
            or not scope.parent_attempts <= len(rows) <= len(attempts)
            or not http_server_failure(rows[scope.parent_attempts - 1][1])
            or any(
                response.provider != parent.schedule[i - 1].request.provider
                or response.model != parent.schedule[i - 1].request.model
                for i, response in rows
            )
        ):
            raise PermissionError(
                "complete preserved parent prefix and exact response route required"
            )
        return parent

    def verify_runtime(self) -> None:
        with closing(self.ledger.connect()) as db:
            parent = self.check(db)
        # This temporary view checks the new grant's source. Never store/change the parent scope.
        verify_runtime(parent.model_copy(update={"source_sha256": self.scope.source_sha256}))

    def reserve(self, ordinal: int, *, now: datetime) -> None:
        with closing(self.ledger.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            parent = self.check(db)
            count = db.execute("SELECT count(*) FROM olist_demo_attempts").fetchone()[0]
            rows = responses(db)
            if (
                not self.scope.starts_at <= now < self.scope.expires_at
                or count != len(rows)
                or ordinal != count + 1
                or not self.scope.parent_attempts < ordinal <= 146
                or halt_reason(rows, self.scope)
            ):
                raise PermissionError("expired, outstanding, exhausted, stopped or out-of-order")
            db.execute(
                "INSERT INTO olist_demo_attempts VALUES(?,?,?)",
                (ordinal, parent.schedule[ordinal - 1].request.fingerprint(), now.isoformat()),
            )

    def readback(self) -> dict[str, object]:
        with closing(self.ledger.connect()) as db:
            parent = self.check(db)
            raw = db.execute(
                "SELECT ordinal,response,elapsed_ms,process_timing FROM olist_demo_results "
                "ORDER BY ordinal"
            ).fetchall()
            reserved = db.execute("SELECT count(*) FROM olist_demo_attempts").fetchone()[0]
            rows = responses(db)
        if parent.origin == "provider" and source_pin(ROOT) != self.scope.source_sha256:
            raise PermissionError("exact continuation source required for provider readback")
        observations = tuple(
            Observation(
                origin=parent.origin,
                case_id=parent.schedule[i - 1].case_id,
                trial=parent.schedule[i - 1].trial,
                request_sha256=parent.schedule[i - 1].request.fingerprint(),
                response=ModelResponse.model_validate_json(value),
                elapsed_ms=elapsed,
            )
            for i, value, elapsed, _ in raw
            if i > 2
        )
        return {
            "origin": parent.origin,
            "scheduled_attempts": 146,
            "reserved_attempts": reserved,
            "settled_attempts": len(raw),
            "missing_attempts": 146 - reserved,
            "unsettled_attempts": reserved - len(raw),
            "parent_stop_preserved": True,
            "parent_scope_sha256": self.scope.parent_scope_sha256,
            "continuation_scope_sha256": self.pin,
            "continuation_halt_reason": halt_reason(rows, self.scope),
            "both_canaries_passed": True,
            "conservatively_accounted_tokens": accounted_tokens(rows),
            "unknown_usage_reservation_per_row": GEMINI_TOKEN_CEILING,
            "observed_usage_unknown_rows": sum(
                r.usage.input_tokens is None or r.usage.output_tokens is None for _, r in rows
            ),
            "process_timings": [
                {"ordinal": i, "phases": json.loads(timing) if timing else None}
                for i, _, _, timing in raw
            ],
            "actual_provider_attempts": reserved if parent.origin == "provider" else 0,
            "model_quality_observed": parent.origin == "provider" and bool(observations),
            "domain": summarize(observations),
            "baselines": baselines(),
            "demo_release_accepted": False,
        }

    def capture(self, transport: DeadlineTransport, *, pause: bool = True) -> dict[str, object]:
        with closing(self.ledger.connect()) as db:
            parent = self.check(db)
            rows = responses(db)
            count = db.execute("SELECT count(*) FROM olist_demo_attempts").fetchone()[0]
        if parent.origin == "provider" and (
            not pause
            or not isinstance(transport, SDKTransport)
            or transport.worker.origin != "provider"
            or transport.worker.project_sha256 != parent.project_sha256
        ):
            raise PermissionError("real SDK, same project and required cooldown only")
        if isinstance(transport, SDKTransport) and transport.worker.origin != parent.origin:
            raise PermissionError("mock/provider transport origin differs")
        if parent.origin == "provider":
            self.verify_runtime()
        for ordinal in range(count + 1, 147):
            if halt_reason(rows, self.scope):
                break
            if rows and http_server_failure(rows[-1][1]) and pause:
                time.sleep(self.scope.cooldown_seconds)
            if parent.origin == "provider":
                self.verify_runtime()
            start = time.monotonic()
            self.reserve(ordinal, now=datetime.now(UTC))
            response = transport.generate(
                parent.schedule[ordinal - 1].request, timeout_seconds=parent.parent_seconds
            )
            phase = transport.last_timing if isinstance(transport, SDKTransport) else None
            self.ledger.settle(
                ordinal,
                response,
                (time.monotonic() - start) * 1000,
                phase.canonical_json() if phase else None,
            )
            rows.append((ordinal, response))
        return self.readback()


def prepare(
    output: Path, ledger_path: Path, parent_pin: str, *, now: datetime
) -> dict[str, object]:
    if any((p / ".git").exists() for p in (output.resolve(), *output.resolve().parents)):
        raise ValueError("private continuation packet must stay outside Git")
    ledger = Ledger(ledger_path, parent_pin)
    with closing(ledger.connect()) as db:
        parent = ledger.scope(db)
        count = db.execute("SELECT count(*) FROM olist_demo_attempts").fetchone()[0]
        rows = responses(db)
        if count != len(rows):
            raise PermissionError("outstanding attempt cannot be retried or continued")
        scope = ContinuationScope(
            parent_scope_sha256=parent_pin,
            parent_prefix_sha256=prefix_pin(db, count),
            parent_attempts=count,
            source_sha256=source_pin(ROOT),
            environment_sha256=environment_pin(),
            starts_at=now,
            expires_at=parent.expires_at,
        )
        # Preparation inspects eligibility; it never installs execution authority.
        Continuation.validate_parent(db, ledger, scope)
        if halt_reason(rows, scope):
            raise PermissionError("parent failure is not eligible for the proposed continuation")
    if parent.origin == "provider":
        verify_runtime(parent.model_copy(update={"source_sha256": scope.source_sha256}))
    output.mkdir(exist_ok=False)
    write(output / "scope.json", scope.model_dump(mode="json"))
    result = {
        "scope_sha256": digest(scope.canonical_json().encode()),
        "parent_scope_sha256": parent_pin,
        "parent_consumed": count,
        "remaining_original_slots": 146 - count,
        "ceiling_unchanged": parent.lifetime_ceiling,
        "retained_unchanged": parent.retained_bound_slots,
        "expires_at_unchanged": parent.expires_at.isoformat(),
        "max_accounted_tokens_proposed": scope.max_accounted_tokens,
        "provider_calls_authorized": 0,
    }
    write(output / "proposal.json", result)
    return result


def private_worker(configuration: Path, parent: Scope) -> SDKWorker:
    from prior_auth_study_budget import pin
    from prior_auth_study_run import private_configuration

    path = private_configuration(configuration)
    values = dict(
        line.split("=", 1)
        for line in path.read_text().splitlines()
        if "=" in line and not line.startswith("#")
    )
    key = values["GEMINI_API_KEY"].strip().strip("\"'")
    if not key or values.get("GEMINI_FREE_TIER_CONFIRMED", "").strip().lower() not in {
        "true",
        "1",
        "yes",
    }:
        raise PermissionError("configured Free confirmation required")
    association = pin(
        {
            "configuration_reference": str(path),
            "credential_sha256": digest(key.encode()),
            "meaning": (
                "operator-selected-credential-association-not-provider-verified-cloud-project"
            ),
        }
    )
    if association != parent.project_sha256:
        raise PermissionError("same authorized project association required")
    return SDKWorker(key, association)


def main() -> None:
    cli = argparse.ArgumentParser(description=__doc__)
    mode = cli.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", type=Path)
    mode.add_argument("--capture", type=Path)
    mode.add_argument("--readback", type=Path)
    cli.add_argument("--ledger", type=Path, required=True)
    cli.add_argument("--parent-pin")
    cli.add_argument("--owner-grant", type=Path)
    cli.add_argument("--owner-grant-pin")
    cli.add_argument("--configuration", type=Path)
    args = cli.parse_args()
    if args.prepare:
        if not args.parent_pin:
            cli.error("preparation requires externally retained parent pin")
        result = prepare(args.prepare, args.ledger, args.parent_pin, now=datetime.now(UTC))
    else:
        if not args.owner_grant or not args.owner_grant_pin:
            cli.error("continuation needs the new separately pinned owner grant")
        scope = ContinuationScope.model_validate_json((args.capture or args.readback).read_bytes())
        grant = OwnerGrant.model_validate_json(args.owner_grant.read_bytes())
        continuation = Continuation(
            args.ledger, scope, grant, trusted_grant_sha256=args.owner_grant_pin
        )
        if args.capture:
            if not args.configuration:
                cli.error("capture requires private configuration")
            continuation.verify_runtime()
            with closing(continuation.ledger.connect()) as db:
                parent = continuation.check(db)
            result = continuation.capture(SDKTransport(private_worker(args.configuration, parent)))
        else:
            result = continuation.readback()
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
