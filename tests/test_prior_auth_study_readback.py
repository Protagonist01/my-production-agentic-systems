"""Separate reader catches artifact/scope corruption and keeps unobserved scores unknown."""

import json

import pytest
from agent_harness.contracts import ModelMessage, ModelRequest, ModelResponse, Usage
from agent_harness.offline_example import example_context
from prior_auth.contracts import NoteInput
from test_prior_auth_study_scope import NOW, history

import prior_auth_study_readback as reader
from prior_auth_demo import demo_policy
from prior_auth_study_budget import Grant, Slot, initialize, pin
from prior_auth_study_draft import prepare
from prior_auth_study_run import decisions, parse, write


def fixture(tmp_path, monkeypatch):
    packet, capture, database = (
        tmp_path / "packet",
        tmp_path / "capture",
        tmp_path / "shared.sqlite",
    )
    prepare(packet)
    capture.mkdir()
    notes = {
        row["case_id"]: NoteInput.model_validate_json(json.dumps(row))
        for row in json.loads((packet / "inputs.json").read_text())
    }
    rows = [r for r in json.loads((packet / "request-plan.json").read_text()) if r["request"]]
    schedule = [dict(r, phase="canary") for r in rows[:2]] + [dict(r, phase="domain") for r in rows]
    execution = {"schedule": schedule}
    grant = Grant(
        packet_sha256="a" * 64,
        historical_sha256=history(database),
        project_sha256="b" * 64,
        execution_sha256=pin(execution),
        approved_at=NOW,
        expires_at=NOW.replace(day=20),
        slots=tuple(
            Slot(
                ordinal=i + 1,
                phase=r["phase"],
                case_id=r["case_id"],
                trial=r["trial"],
                criterion=r["criterion"],
                request_sha256=r["request_sha256"],
            )
            for i, r in enumerate(schedule)
        ),
    )
    ledger = initialize(database, grant)
    write(capture / "grant.json", grant.model_dump(mode="json"))
    write(capture / "execution.json", execution)
    (capture / "scope.sha256").write_text(ledger.scope_pin)
    write(
        capture / "checked-decisions.json",
        decisions(
            notes, demo_policy(), schedule, [], example_context("readback-only", "readback-only")
        ),
    )
    monkeypatch.setattr(reader, "load_packet", lambda _: (notes, demo_policy(), schedule))
    return packet, capture, database, ledger, notes, schedule


def test_missing_model_observations_are_unknown_not_zero_accuracy(tmp_path, monkeypatch):
    packet, capture, database, ledger, _, _ = fixture(tmp_path, monkeypatch)
    result = reader.readback(packet, capture, database, ledger.scope_pin)
    assert result["model_proposed_state_agreement"] == {
        "correct": 0,
        "observed": 0,
        "scheduled": 166,
        "missing": 166,
        "observed_agreement": None,
    }
    assert result["checked_proposed_state_agreement"]["observed_agreement"] is None
    assert result["custody_verified"] and not result["clinical_qualified"]
    assert result["total_consumed"] == 447
    with pytest.raises(ValueError):
        reader.readback(packet, capture, database, "f" * 64)


def test_raw_response_reconstruction_and_tampered_artifact_refusal(tmp_path, monkeypatch):
    packet, capture, database, ledger, notes, schedule = fixture(tmp_path, monkeypatch)
    first = schedule[0]
    request = ModelRequest.model_validate_json(json.dumps(first["request"]))
    note = notes[first["case_id"]]
    response = ModelResponse(
        provider=request.provider,
        model=request.model,
        output=ModelMessage(
            role="assistant",
            content=json.dumps(
                {
                    "criterion_id": first["criterion"],
                    "state": "met",
                    "quotes": [note.text.splitlines()[0]],
                    "rationale": "Invented transport witness.",
                }
            ),
        ),
        usage=Usage(
            model_calls=1, input_tokens=50, output_tokens=20, cost=None, cost_currency=None
        ),
    )
    value = parse(response, request, note)
    row = {
        "ordinal": 1,
        "phase": "canary",
        "case_id": first["case_id"],
        "trial": first["trial"],
        "criterion": first["criterion"],
        "request_sha256": request.fingerprint(),
        "response": response.model_dump(mode="json"),
        "parsed": value.model_dump(mode="json"),
        "canary_pass": True,
        "elapsed_seconds": 1.0,
    }
    ledger.reserve(1, request.fingerprint(), now=NOW)
    ledger.settle(1, row, tokens=70, canary_pass=True, stop=None)
    write(capture / "attempt-001.json", row)
    result = reader.readback(packet, capture, database, ledger.scope_pin)
    assert result["canaries_passed"] == 1 and result["total_consumed"] == 448
    assert result["model_proposed_state_agreement"]["observed"] == 0
    row["parsed"] = None
    (capture / "attempt-001.json").write_text(json.dumps(row))
    with pytest.raises(ValueError, match="artifact"):
        reader.readback(packet, capture, database, ledger.scope_pin)


def test_completed_case_reconstruction_requires_the_approved_tenant_context(tmp_path, monkeypatch):
    packet, capture, database, ledger, notes, schedule = fixture(tmp_path, monkeypatch)
    observed = []
    for ordinal, first in enumerate(schedule[:9], 1):
        request = ModelRequest.model_validate_json(json.dumps(first["request"]))
        note = notes[first["case_id"]]
        response = ModelResponse(
            provider=request.provider,
            model=request.model,
            output=ModelMessage(
                role="assistant",
                content=json.dumps(
                    {
                        "criterion_id": first["criterion"],
                        "state": "met",
                        "quotes": [note.text.splitlines()[0]],
                        "rationale": "Invented scope witness.",
                    }
                ),
            ),
            usage=Usage(
                model_calls=1, input_tokens=50, output_tokens=20, cost=None, cost_currency=None
            ),
        )
        parsed = parse(response, request, note)
        row = {
            "ordinal": ordinal,
            "phase": first["phase"],
            "case_id": first["case_id"],
            "trial": first["trial"],
            "criterion": first["criterion"],
            "request_sha256": request.fingerprint(),
            "response": response.model_dump(mode="json"),
            "parsed": parsed.model_dump(mode="json"),
            "canary_pass": ordinal <= 2,
            "elapsed_seconds": 1.0,
        }
        ledger.reserve(ordinal, request.fingerprint(), now=NOW)
        ledger.settle(ordinal, row, tokens=70, canary_pass=ordinal <= 2, stop=None)
        write(capture / f"attempt-{ordinal:03}.json", row)
        observed.append(row)
    with pytest.raises(PermissionError):
        decisions(
            notes,
            demo_policy(),
            schedule,
            observed,
            example_context("readback-only", "readback-only"),
        )
    correct = decisions(
        notes,
        demo_policy(),
        schedule,
        observed,
        example_context("readback-only", "readback-only").model_copy(update={"tenant_id": "demo"}),
    )
    (capture / "checked-decisions.json").write_text(json.dumps(correct))
    result = reader.readback(packet, capture, database, ledger.scope_pin)
    assert result["checked_proposed_state_agreement"]["observed"] == 7
    assert result["model_proposed_state_agreement"]["observed"] == 7
    assert not result["clinical_qualified"]
