"""One real spawned fake SDK check plus orchestration binding checks; no provider calls."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from agent_harness.cost_accounting import FreeTariff
from agent_harness.isolated_transport import IsolatedTransport

from docs.evaluation.olist_semantic_candidate import SemanticOutput, parse, request
from docs.evaluation.olist_semantic_controls import Scope, Slot, canonical, pin
from docs.evaluation.run_olist_semantic_comparison import SDKWorker, capture


def test_actual_spawn_sdk_schema_parser_and_no_network() -> None:
    text = "refund $25"
    expected = SemanticOutput(
        intent="refund",
        amount_status="explicit",
        requested_minor=2500,
        currency="dollar_unspecified",
        amount_evidence="$25",
    )
    req = request(text)
    worker = SDKWorker("invented-key", "b" * 64, {req.fingerprint(): expected.canonical_json()})
    transport = IsolatedTransport(worker)
    result = transport.generate(req, timeout_seconds=30)
    assert result.failure is None
    assert result.output is not None and result.output.content is not None
    assert parse(text, result.output.content) == expected
    assert result.usage.input_tokens == 100 and result.usage.output_tokens == 50
    assert result.usage.cost is None
    assert worker.origin == "mock"
    assert transport.last_timing is not None and transport.last_timing.exit_code == 0


def invented_scope() -> tuple[Scope, tuple, tuple]:
    now = datetime.now(UTC)
    cases = [
        {"case_id": f"invented-{i}", "input": {"text": f"help with invented order {i}"}}
        for i in range(24)
    ]
    texts = ["refund $25", "Where is my order?"] + [
        x["input"]["text"] for x in cases for _ in range(3)
    ]
    requests = tuple(request(t) for t in texts)
    expected = (
        SemanticOutput(
            intent="refund",
            amount_status="explicit",
            requested_minor=2500,
            currency="dollar_unspecified",
            amount_evidence="$25",
        ),
        SemanticOutput(
            intent="status",
            amount_status="not_applicable",
            requested_minor=None,
            currency="unspecified",
            amount_evidence=None,
        ),
    )
    slots = tuple(
        Slot(
            ordinal=i + 1,
            phase="canary" if i < 2 else "domain",
            case_id=f"canary-{i}" if i < 2 else cases[(i - 2) // 3]["case_id"],
            trial_id="canary" if i < 2 else f"trial-{(i - 2) % 3 + 1}",
            request_sha256=req.fingerprint(),
        )
        for i, req in enumerate(requests)
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
            expires_at=now + timedelta(days=2),
            models=("gemini-3.5-flash-lite",),
        ),
        source_files={"invented.py": "f" * 64},
        environment_sha256="0" * 64,
        code_revision="1" * 40,
        input_packet_sha256=pin(canonical(cases)),
        reference_packet_sha256="9" * 64,
        canary_expectations_sha256=pin(canonical([x.model_dump(mode="json") for x in expected])),
        approved_at=now,
        expires_at=now + timedelta(days=1),
        slots=slots,
    )
    return scope, requests, expected


@pytest.mark.parametrize(
    "change", ["input_packet", "canary", "worker_origin", "project", "scope_pin"]
)
def test_preflight_failure_never_opens_a_ledger(tmp_path: Path, change: str) -> None:
    scope, requests, expected = invented_scope()
    worker = SDKWorker("invented", scope.project_sha256, {r.fingerprint(): "{}" for r in requests})
    if change == "input_packet":
        scope = scope.model_copy(update={"input_packet_sha256": "9" * 64})
    elif change == "canary":
        expected = expected[::-1]
    elif change == "worker_origin":
        worker = SDKWorker("invented", scope.project_sha256)
    elif change == "project":
        worker = SDKWorker("invented", "8" * 64, {})
    digest = pin(scope.canonical_json()) if change != "scope_pin" else "7" * 64
    with pytest.raises(ValueError):
        capture(
            Path.cwd(),
            tmp_path / "must-not-exist.sqlite",
            scope,
            digest,
            requests,
            expected,
            worker,
            tmp_path / "out",
        )
    assert not (tmp_path / "must-not-exist.sqlite").exists()
    assert not (tmp_path / "out").exists()
