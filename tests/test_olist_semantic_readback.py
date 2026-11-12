"""Unknown-reference and failure denominators cannot be improved by dropping rows."""

import hashlib
from datetime import UTC, datetime

import pytest
from agent_harness.cost_accounting import FreeTariff

from docs.evaluation.olist_semantic_candidate import SemanticOutput, request
from docs.evaluation.olist_semantic_controls import Scope, Slot, canonical, pin
from docs.evaluation.read_olist_semantic_comparison import Reference, score_rows


def fixture():
    now = datetime(2026, 11, 11, tzinfo=UTC)
    refs = tuple(
        Reference(
            case_id=f"invented-{i}",
            input_sha256=hashlib.sha256(f"text {i}".encode()).hexdigest(),
            stratum="constructed_accepted" if i < 17 else "price_role_unresolved",
            intent="refund" if i < 21 else None,
            amount_status="explicit" if i < 17 else None,
            requested_minor=2500 if i < 17 else None,
            currency="SIM" if i < 17 else None,
        )
        for i in range(24)
    )
    requests = tuple(
        [request("canary one"), request("canary two")]
        + [request(f"text {i}") for i in range(24) for _ in range(3)]
    )
    slots = tuple(
        Slot(
            ordinal=i + 1,
            phase="canary" if i < 2 else "domain",
            case_id=f"canary-{i}" if i < 2 else f"invented-{(i - 2) // 3}",
            trial_id="canary" if i < 2 else f"trial-{(i - 2) % 3 + 1}",
            request_sha256=r.fingerprint(),
        )
        for i, r in enumerate(requests)
    )
    scope = Scope(
        origin="mock",
        proposal_sha256="a" * 64,
        historical_anchor_sha256="b" * 64,
        project_sha256="c" * 64,
        allowance_sha256="d" * 64,
        tariff=FreeTariff(
            source_snapshot_sha256="e" * 64,
            project_sha256="c" * 64,
            free_project_attestation_ref="invented",
            review_ref="invented",
            reviewed_at=now,
            expires_at=now.replace(day=13),
            models=("gemini-3.5-flash-lite",),
        ),
        source_files={"invented.py": "f" * 64},
        environment_sha256="0" * 64,
        code_revision="1" * 40,
        input_packet_sha256="2" * 64,
        reference_packet_sha256=pin(canonical([r.model_dump(mode="json") for r in refs])),
        canary_expectations_sha256="3" * 64,
        approved_at=now,
        expires_at=now.replace(day=12),
        slots=slots,
    )
    return scope, requests, refs


def test_empty_capture_preserves_all_scheduled_and_unknown_fields() -> None:
    scope, requests, refs = fixture()
    result = score_rows(scope, requests, [], refs)["domain"]
    assert result["scheduled"] == result["missing"] == 72
    assert (result["intent_reference"], result["intent_unknown"]) == (63, 9)
    assert (result["amount_reference"], result["amount_unknown"]) == (51, 21)
    assert result["intent_match"] == result["amount_match"] == 0


def test_unknowns_do_not_become_free_correct_amount_labels() -> None:
    scope, requests, refs = fixture()
    output = SemanticOutput(
        intent="refund",
        amount_status="explicit",
        requested_minor=2500,
        currency="SIM",
        amount_evidence="25.00 SIM",
    )
    rows = [
        {
            "ordinal": i + 1,
            "extracted": output.model_dump(mode="json"),
            "timing": {"parent_failure": None},
        }
        for i in range(74)
    ]
    result = score_rows(scope, requests, rows, refs)["domain"]
    assert result["intent_match"] == 63 and result["amount_match"] == 51
    assert result["amount_unknown"] == 21 and result["intent_unknown"] == 9
    rows[-1]["timing"]["parent_failure"] = "invented_failure"
    assert score_rows(scope, requests, rows, refs)["domain"]["failed"] == 1
    rows.pop()
    assert score_rows(scope, requests, rows, refs)["domain"]["missing"] == 1


def test_changed_or_reordered_references_refuse() -> None:
    scope, requests, refs = fixture()
    with pytest.raises(ValueError, match="frozen reference"):
        score_rows(scope, requests, [], refs[::-1])


def test_duplicate_or_gapped_rows_refuse() -> None:
    scope, requests, refs = fixture()
    for rows in ([{"ordinal": 1}, {"ordinal": 1}], [{"ordinal": 2}]):
        with pytest.raises(ValueError, match="ordered unique"):
            score_rows(scope, requests, rows, refs)
