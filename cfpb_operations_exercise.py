"""Run simulated complaint operations over the protected desk and an isolated database."""

import argparse
import json
import os
import secrets
import sqlite3
from collections import Counter
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import perf_counter
from typing import Any, Literal

import psycopg
from agent_harness.local_services import Workspace
from agent_harness.postgres import Server, Trial, create_trial, drop_trial
from cfpb_triage.desk_api import create_app
from cfpb_triage.desk_auth import AuthStore, provision, setup_review
from cfpb_triage.desk_contracts import Principal
from cfpb_triage.desk_store import DeskStore
from cfpb_triage.evaluation_store import EvaluationStore, provision_participant, setup_evaluation
from cfpb_triage.scope_routing import MODELS, ScopeAttempt, ScopeDecision, ScopeOutput, ScopePolicy
from cfpb_triage.source import verify_prepared
from cfpb_triage.source_contracts import ComplaintInput
from cfpb_triage.source_io import digest_file, external_path
from cfpb_triage.triage_contracts import ExtractedPrediction, Taxonomy, digest_text
from fastapi.testclient import TestClient

from cfpb_public_feed import replay_ids

Arm = Literal["manual", "assisted"]
ORIGIN = "http://127.0.0.1:9051"


@dataclass(frozen=True)
class Scenario:
    kind: str
    text: str
    expected: ScopeOutput | None
    proposal: ScopeOutput | None = None
    outage: bool = False
    source_key: str = ""


def bank_route(text: str, *, elevated: bool) -> ScopeOutput:
    return ScopeOutput(
        scope="in_scope",
        confidence=1.0,
        quotes=(text,),
        classification=ExtractedPrediction(
            product="Exercise checking",
            issue="Unauthorized transfer",
            priority="elevated" if elevated else "routine",
            ambiguity="clear",
            confidence=1.0,
            quotes=(text,),
        ),
    )


def scenarios() -> tuple[Scenario, ...]:
    routine = "The disputed transfer was reversed. Please record the complaint."
    urgent = "An unauthorized transfer posted this morning and my account is still exposed."
    unrelated = "Could you suggest a recipe for lentil soup?"
    outage = "I disputed a transfer yesterday and need someone to review it."
    outside = ScopeOutput(scope="out_of_scope", confidence=1.0, quotes=(unrelated,))
    unknown = ScopeOutput(scope="insufficient", confidence=0.0)
    return (
        Scenario(
            "routine",
            routine,
            bank_route(routine, elevated=False),
            bank_route(routine, elevated=False),
        ),
        Scenario(
            "missed_escalation",
            urgent,
            bank_route(urgent, elevated=True),
            bank_route(urgent, elevated=False),
        ),
        Scenario("unrelated", unrelated, outside, outside),
        Scenario("missing_detail", "Please help.", unknown, unknown),
        Scenario("provider_outage", outage, bank_route(outage, elevated=False), outage=True),
        Scenario("unresolved", "I cannot describe the issue yet.", None),
    )


def archived(directory: Path, pin: str, count: int) -> tuple[Scenario, ...]:
    """Replay one development input per family without exposing categories to the desk."""
    if not 1 <= count <= 10:
        raise ValueError("archive replay supports 1 to 10 cases")
    directory = external_path(directory)
    manifest = verify_prepared(directory, pin)
    target_path = directory / "evaluator.sqlite"
    with closing(sqlite3.connect(target_path.as_uri() + "?mode=ro", uri=True)) as selection:
        keys = {
            row[0]
            for row in selection.execute(
                "SELECT min(case_id) FROM targets WHERE split='development' "
                "GROUP BY group_id ORDER BY min(case_id) LIMIT ?",
                (count,),
            )
        }
    items = []
    # Both stores are rehashed after selecting the small in-memory projection.
    agent_uri = (directory / "agent.sqlite").as_uri() + "?mode=ro"
    with closing(sqlite3.connect(agent_uri, uri=True)) as inputs:
        for key in sorted(keys):
            row = inputs.execute("SELECT narrative FROM inputs WHERE case_id=?", (key,)).fetchone()
            if row and len(row[0]) <= 20000:
                item = ComplaintInput(case_id=key, narrative=row[0])
                items.append(Scenario("archive", item.narrative, None, source_key=item.case_id))
    if (
        len(items) != count
        or any(
            digest_file(directory / name) != manifest["files"][name]["sha256"]
            for name in ("agent.sqlite", "evaluator.sqlite")
        )
        or digest_file(directory / "manifest.json") != pin
    ):
        raise ValueError("archive inputs missing or source changed")
    return tuple(items)


def publish(
    store: EvaluationStore,
    item: ComplaintInput,
    scenario: Scenario,
    policy: ScopePolicy,
    taxonomy: Taxonomy,
) -> str | None:
    if scenario.proposal is None and not scenario.outage:
        return None
    claim = store.claim_evaluation()
    if claim is None or claim["case_id"] != item.case_id:
        raise RuntimeError("exercise worker claimed unexpected case")
    output = scenario.proposal
    prediction = (
        output.classification.locate(item, taxonomy) if output and output.classification else None
    )
    action: Literal["classified", "scope_response", "review_required"] = "review_required"
    reason: Literal["supported", "scope_response", "operational_failure", "scope_uncertain"]
    if scenario.outage:
        reason = "operational_failure"
    elif prediction:
        action, reason = "classified", "supported"
    elif output and output.scope == "out_of_scope":
        action, reason = "scope_response", "scope_response"
    else:
        reason = "scope_uncertain"
    attempt = ScopeAttempt(
        route="cheap",
        model=MODELS["cheap"],
        output=output,
        prediction=prediction,
        failure="unavailable" if scenario.outage else None,
    )
    decision = ScopeDecision(
        case_id=item.case_id,
        narrative_sha256=digest_text(item.narrative),
        taxonomy_sha256=taxonomy.digest(),
        policy_sha256=digest_text(policy.canonical_json()),
        scope=output.scope if output else None,
        action=action,
        reason=reason,
        prediction=prediction,
        attempts=(attempt,),
        timings=(),
    )
    if not store.finish_evaluation(claim, decision) or store.finish_evaluation(claim, decision):
        raise RuntimeError("publication receipt invariant failed")
    return action


def rollup(
    store: EvaluationStore,
    user: Principal,
    candidate_misses: int,
    count: int,
) -> dict[str, object]:
    rows = store.export_work(user, currency="USD")
    if len(rows) != count or any(
        row.basis != "invented" or row.correct is not None for row in rows
    ):
        raise RuntimeError("planned case inventory or work basis differs")
    accepted = [row for row in rows if row.accepted is not None]
    return {
        "scheduled": count,
        "accepted": len(accepted),
        "unresolved": count - len(accepted),
        "candidate_missed_escalations_in_authored_cases": candidate_misses,
        "scripted_initial_seconds": sum(row.initial_seconds for row in rows),
        "scripted_correction_seconds": sum(row.correction_seconds for row in rows),
        "scripted_max_seconds_to_accept": max(
            ((row.accepted - row.arrived).total_seconds() for row in accepted if row.accepted),
            default=None,
        ),
        "observed_human_savings_seconds": None,
        "observed_cost_per_correct_acceptance": None,
    }


def run_exercise(
    server: Server,
    workspace_key: str,
    archive_cases: tuple[Scenario, ...] = (),
    public_ids: tuple[str, ...] = (),
) -> dict[str, object]:
    """Create and tear down an owned trial. Archived cases are deliberately unadjudicated."""
    items = (
        scenarios()
        + archive_cases
        + tuple(
            Scenario(
                "public_metadata",
                "This intake sample contains receipt metadata only.",
                None,
                source_key=identity,
            )
            for identity in public_ids
        )
    )
    if len(items) > 26 or len(set(public_ids)) != len(public_ids):
        raise ValueError("bounded unique replay inputs required")
    trial = Trial(workspace_key, "cfpb-exercise-" + secrets.token_hex(8), secrets.token_hex(32))
    create_trial(server, trial)
    started = perf_counter()
    now = datetime.now(UTC)

    def clock() -> datetime:
        return now

    def advance(seconds: int) -> None:
        nonlocal now
        now += timedelta(seconds=seconds)

    def connect() -> psycopg.Connection[tuple[Any, ...]]:
        return server.connect_trial(trial)

    taxonomy = Taxonomy(
        version="scripted-operations-v1",
        source_manifest=digest_text("invented taxonomy"),
        pairs={"Exercise checking": ("Unauthorized transfer",)},
    )
    policy = ScopePolicy(
        taxonomy_sha256=taxonomy.digest(),
        reference_sha256=digest_text("scripted-workflow-v1"),
        mode="cheap_only",
        cheap_threshold=0.99,
        scope_threshold=0.99,
    )
    try:
        with server.connect(trial.name) as admin:
            setup_review(admin, trial.name)
            setup_evaluation(admin, trial.name)
        report: dict[str, object] = {}
        counts: Counter[str] = Counter()
        arms: tuple[Arm, ...] = ("manual", "assisted")
        for arm in arms:
            complaints = [
                ComplaintInput(
                    case_id=digest_text(f"{arm}:{index}:{s.source_key}"),
                    narrative=s.text,
                )
                for index, s in enumerate(items)
            ]
            user = Principal(
                username=f"scripted-{arm}",
                actor_id=f"scripted-{arm}",
                tenant_id="operations",
                role="reviewer",
                case_ids=tuple(c.case_id for c in complaints),
            )
            password = secrets.token_hex(24)
            with server.connect(trial.name) as admin:
                provision_participant(admin, user.tenant_id, user.actor_id)
                provision(admin, user, password)
            store = EvaluationStore(connect, clock=clock)
            api = create_app(
                DeskStore(connect, clock=clock),
                AuthStore(connect, clock=clock),
                origin=ORIGIN,
                trial_id=trial.name,
                evaluation=store,
            )
            candidate_misses = 0
            with TestClient(api, base_url=ORIGIN) as client:
                collection = "/api/v2/evaluation"
                if client.get(collection).status_code != 403:
                    raise RuntimeError("signed-out access must be refused")
                login = client.post(
                    "/api/login",
                    headers={"origin": ORIGIN},
                    json={"username": user.username, "password": password},
                )
                if login.status_code != 200:
                    raise RuntimeError("scripted desk login failed")
                headers = {
                    "origin": ORIGIN,
                    "x-csrf-token": next(
                        value for name, value in client.cookies.items() if "csrf" in name
                    ),
                }
                # Burst arrivals accrue queue wait while preceding work is in progress.
                actions = {}
                for index, (item, scenario) in enumerate(zip(complaints, items, strict=True)):
                    store.enroll_evaluation(
                        user.tenant_id,
                        item,
                        taxonomy,
                        policy,
                        family=f"exercise-{index}",
                        actor=user.actor_id,
                        arm=arm,
                        review_ref={
                            "archive": "published-archive-private-replay",
                            "public_metadata": "public-metadata-only",
                        }.get(scenario.kind, "authored-operations-scenario"),
                        measurement_basis="invented",
                    )
                    # Unresolved and archived cases are enrolled last and left in the queue.
                    if arm == "assisted":
                        actions[item.case_id] = publish(store, item, scenario, policy, taxonomy)
                for item, scenario in zip(complaints, items, strict=True):
                    path = f"{collection}/{item.case_id}"
                    row = client.get(path)
                    if row.status_code != 200:
                        raise RuntimeError("assigned case unavailable")
                    snapshot = row.json()
                    if arm == "manual" and snapshot["result"] is not None:
                        raise RuntimeError("manual arm was not blinded")
                    if scenario.expected is None:
                        counts[f"{arm}_{scenario.kind}_awaiting_review"] += 1
                        continue
                    action = actions.get(item.case_id)
                    if action and snapshot["result"]["action"] != action:
                        raise RuntimeError("desk response differs from worker receipt")
                    if scenario.outage and arm == "assisted" and action != "review_required":
                        raise RuntimeError("simulated provider outage must reach review")

                    version = snapshot["version"]

                    def send(
                        operation: str,
                        *,
                        work_path: str = path + "/work",
                        auth_headers: dict[str, str] = headers,
                        **fields: object,
                    ) -> None:
                        nonlocal version
                        response = client.post(
                            work_path,
                            headers=auth_headers,
                            json={
                                "command_id": f"step-{version}",
                                "expected_version": version,
                                "operation": operation,
                                **fields,
                            },
                        )
                        if response.status_code != 200:
                            raise RuntimeError(f"review work command refused: {operation}")
                        version = int(response.json()["version"])

                    send("start")
                    review_seconds = 20 if action in ("classified", "scope_response") else 40
                    correction = arm == "assisted" and scenario.kind == "missed_escalation"
                    if correction:
                        if action != "classified":
                            raise RuntimeError("missed escalation fixture did not reach the desk")
                        candidate_misses += 1
                        advance(20)
                        send("pause", active_seconds=20)
                        send("start", work_kind="correction")
                        advance(35)
                    else:
                        advance(review_seconds)
                    accepted = {
                        "command_id": f"step-{version}",
                        "expected_version": version,
                        "operation": "accept",
                        "active_seconds": 35 if correction else review_seconds,
                        "final": scenario.expected.model_dump(mode="json"),
                    }
                    first = client.post(path + "/work", json=accepted, headers=headers)
                    duplicate = client.post(path + "/work", json=accepted, headers=headers)
                    if first.status_code != 200 or duplicate.json() != first.json():
                        raise RuntimeError("review command was not idempotent")
                    actual = client.get(path).json()
                    if not actual["accepted_at"] or actual["final_result"] != accepted["final"]:
                        raise RuntimeError("final decision did not persist")
            report[arm] = rollup(
                EvaluationStore(connect, clock=clock), user, candidate_misses, len(items)
            )
        return {
            "purpose": "scripted_operating_exercise",
            "archive_cases_per_arm": len(archive_cases),
            "public_metadata_cases_per_arm": len(public_ids),
            "authored_cases_per_arm": len(scenarios()),
            "review_queue": dict(counts),
            "arms": report,
            "measured_machine_wall_seconds": round(perf_counter() - started, 3),
            "provider_calls": 0,
            "qualification": False,
        }
    finally:
        drop_trial(server, trial)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--archive-sha256")
    parser.add_argument("--archive-count", type=int, default=3)
    parser.add_argument("--journal", type=Path)
    parser.add_argument("--public-count", type=int, default=3)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if (args.archive is None) != (args.archive_sha256 is None):
        parser.error("archive and external manifest pin must be supplied together")
    try:
        report = external_path(args.report)
        if args.report.is_symlink() or report.exists():
            raise ValueError("new private report path required")
        inputs = (
            archived(args.archive, args.archive_sha256, args.archive_count) if args.archive else ()
        )
        workspace = Workspace(args.workspace.resolve())
        identities = replay_ids(args.journal, args.public_count) if args.journal else ()
        result = run_exercise(workspace.server(), workspace.key, inputs, identities)
        result["archive_manifest_sha256"] = args.archive_sha256
        raw = json.dumps(result, indent=2, sort_keys=True) + "\n"
        fd = os.open(report, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(raw)
        print(raw)
        return 0
    except (
        ValueError,
        OSError,
        LookupError,
        RuntimeError,
        TypeError,
        psycopg.Error,
        sqlite3.Error,
    ):
        print('{"error":"cfpb_operations_exercise_failed"}')
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
