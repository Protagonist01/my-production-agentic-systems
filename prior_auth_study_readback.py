"""Independent read-only custody and development scoring. No provider or credentials."""

import argparse
import json
import math
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any, cast

from agent_harness.contracts import ModelRequest, ModelResponse
from agent_harness.offline_example import example_context
from prior_auth.candidate import QuoteClaim
from prior_auth.source_io import external

from prior_auth_study_budget import Ledger, pin
from prior_auth_study_run import decisions, load_packet


def ratio(correct: int, observed: int, scheduled: int) -> dict[str, object]:
    return {
        "correct": correct,
        "observed": observed,
        "scheduled": scheduled,
        "missing": scheduled - observed,
        "observed_agreement": correct / observed if observed else None,
    }


def readback(packet: Path, capture: Path, ledger_path: Path, scope_pin: str) -> dict[str, object]:
    packet, capture, ledger_path = external(packet), external(capture), external(ledger_path)
    notes, policy, schedule = load_packet(packet)
    scope = (capture / "scope.sha256").read_text(encoding="ascii").strip()
    if scope != scope_pin:
        raise ValueError("independent external scope pin differs")
    execution = json.loads((capture / "execution.json").read_bytes())
    with closing(sqlite3.connect(ledger_path.as_uri() + "?mode=ro", uri=True)) as db:
        db.execute("PRAGMA query_only=ON")
        grant = Ledger(ledger_path, scope_pin).grant(db)
        from prior_auth_study_budget import Grant

        if Grant.model_validate_json((capture / "grant.json").read_bytes()) != grant or (
            pin(execution) != grant.execution_sha256 or execution["schedule"] != schedule
        ):
            raise ValueError("execution/grant artifacts differ from shared ledger")
        reservations = db.execute(
            "SELECT ordinal,request_pin FROM pa_reservations ORDER BY ordinal"
        ).fetchall()
        settlements = db.execute(
            "SELECT ordinal,tokens,canary_pass,document_pin,document "
            "FROM pa_settlements ORDER BY ordinal"
        ).fetchall()
        stops = db.execute("SELECT reason FROM pa_stops").fetchall()
    if len(reservations) != len(settlements) or [r[0] for r in reservations] != list(
        range(1, len(reservations) + 1)
    ):
        raise ValueError("outstanding/nonconsecutive study records")
    observations = []
    for reservation, settled in zip(reservations, settlements, strict=True):
        ordinal, request_pin = reservation
        row = json.loads(settled[4])
        expected = schedule[ordinal - 1]
        artifact = json.loads((capture / f"attempt-{ordinal:03}.json").read_bytes())
        if (
            row != artifact
            or pin(row) != settled[3]
            or row["ordinal"] != ordinal
            or (request_pin != expected["request_sha256"] or row["request_sha256"] != request_pin)
            or any(row[key] != expected[key] for key in ("phase", "case_id", "trial", "criterion"))
        ):
            raise ValueError("settled observation/slot/artifact differs")
        response = ModelResponse.model_validate_json(json.dumps(row["response"]))
        request = ModelRequest.model_validate_json(json.dumps(expected["request"]))
        if (response.provider, response.model) != (request.provider, request.model):
            raise ValueError("response route differs")
        parsed = None
        if (
            response.failure is None
            and response.output is not None
            and not response.output.tool_calls
        ):
            try:
                from agent_harness.cases import _unique_object

                json.loads(response.output.content or "", object_pairs_hook=_unique_object)
                value = QuoteClaim.model_validate_json(response.output.content or "")
                text = notes[row["case_id"]].text
                occurrences = [
                    sum(text.startswith(quote, at) for at in range(len(text)))
                    for quote in value.quotes
                ]
                if (
                    value.criterion_id != expected["criterion"]
                    or (value.state == "met" and not value.quotes)
                    or any(not 1 <= count <= 4 for count in occurrences)
                ):
                    raise ValueError("invalid exact evidence")
                parsed = value.model_dump(mode="json")
            except ValueError:
                pass
        if row["parsed"] != parsed:
            raise ValueError("stored parse differs from raw response")
        tokens = (
            None
            if response.usage.input_tokens is None or response.usage.output_tokens is None
            else (response.usage.input_tokens + response.usage.output_tokens)
        )
        if tokens != settled[1] or bool(settled[2]) != row["canary_pass"]:
            raise ValueError("settlement usage/canary differs")
        canary_pass = (
            row["phase"] == "canary"
            and parsed is not None
            and parsed["state"] == "met"
            and bool(parsed["quotes"])
            and tokens is not None
        )
        if row["canary_pass"] != canary_pass:
            raise ValueError("raw canary validation differs")
        observations.append(row)
    references = {
        r["case_id"]: r["states"]
        for r in json.loads((packet / "proposed-references.json").read_bytes())
    }
    domain = [r for r in observations if r["phase"] == "domain"]
    if domain and sum(bool(r["canary_pass"]) for r in observations) != 2:
        raise ValueError("domain work without two passing canaries")
    parsed_rows = [r for r in domain if r["parsed"] is not None]
    correct = sum(
        r["parsed"]["state"] == references[r["case_id"]][r["criterion"]] for r in parsed_rows
    )
    checked = cast(
        list[dict[str, Any]],
        decisions(
            notes,
            policy,
            schedule,
            observations,
            example_context("readback-only", "readback-only").model_copy(
                update={"tenant_id": "demo", "agent_id": "prior-auth"}
            ),
        ),
    )
    if checked != json.loads((capture / "checked-decisions.json").read_bytes()):
        raise ValueError("checked decisions differ from frozen response reconstruction")
    present = [r for r in checked if r["checked_result"] is not None]
    checked_correct = sum(
        claim["state"] == references[row["case_id"]][claim["criterion_id"]]
        for row in present
        if not row["checked_result"]["assessment_failure"]
        for claim in row["checked_result"]["claims"]
    )
    baseline = []
    for name in ("rules", "always-review"):
        rows = [
            r
            for r in json.loads((packet / "baseline-observations.json").read_bytes())
            if r["baseline"] == name
        ]
        claims = [(r["case_id"], c) for r in rows for c in r["result"]["claims"]]
        matches = sum(c["state"] == references[case][c["criterion_id"]] for case, c in claims)
        baseline.append(
            {"name": name, "proposed_state_agreement": ratio(matches, len(claims), 168)}
        )
    times = sorted(r["elapsed_seconds"] for r in observations)
    if any(type(t) not in (int, float) or not math.isfinite(t) or t < 0 for t in times):
        raise ValueError("invalid attempt timing")
    return {
        "version": "prior-auth-development-readback-v1",
        "reader_version": "readback-tenant-context-v2",
        "custody_verified": True,
        "old_history_unchanged": True,
        "historical_consumed": 447,
        "pa_consumed": len(reservations),
        "total_consumed": 447 + len(reservations),
        "lifetime_ceiling": 784,
        "pa_limit": 170,
        "scheduled_requests": len(schedule),
        "missing_requests": len(schedule) - len(observations),
        "canaries_passed": sum(bool(r["canary_pass"]) for r in observations),
        "stop": stops[0][0] if stops else None,
        "invented_cases": len(notes),
        "model_proposed_state_agreement": ratio(correct, len(domain), 166),
        "parsed_domain_states": len(parsed_rows),
        "checked_proposed_state_agreement": ratio(checked_correct, len(present) * 7, 168),
        "baselines": baseline,
        "disposition_reference_agreement": None,
        "attempt_p95_seconds": times[math.ceil(len(times) * 0.95) - 1] if times else None,
        "reference_status": "accepted constructed development only; not clinical gold",
        "clinical_qualified": False,
        "release_allowed": False,
        "independent_patient_families": None,
        "provider_billing_cost": None,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("packet", "capture", "ledger"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--scope-sha256", required=True)
    args = parser.parse_args()
    try:
        print(
            json.dumps(
                readback(args.packet, args.capture, args.ledger, args.scope_sha256), sort_keys=True
            )
        )
    except Exception as error:
        print("PA readback refused: " + type(error).__name__)
        raise SystemExit(1) from None
