"""Invented readback/scopes isolate mapping logic; SQL integration tests verify actual IO."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from agent_harness.baseline_recording import BaselineManifest, VerifiedBaseline, zero_usage
from agent_harness.contracts import AgentResult, Failure
from agent_harness.evaluation import CaseReport, ScoreResult
from agent_harness.release_contracts import pin, sha256
from agent_harness.scorers import ManifestCaseReport
from agent_harness.trials import BatchReport, TrialRow
from olist_service_fixtures import composition
from olist_support.evidence_methods import MethodScope

import service_method_readback as reader

NOW = datetime(2026, 11, 6, 12, tzinfo=UTC)


def setup(monkeypatch, *, values=(True, True, True), recovery=False):
    _, loaded, schedule, factory = composition(
        "refund" if recovery else "clarify", variant="rules", recovery=recovery
    )
    rows = []
    for task, value in zip(schedule.tasks, values, strict=True):
        case = loaded.entry(task.context.case_id).case
        scores = tuple(
            ScoreResult(
                metric=field,
                scorer_version=case.scorer_version,
                eligible=True,
                value=float(value) if value is not None else None,
                failure=Failure(
                    stage="scorer", code="scorer_error", message="invented unknown", retryable=False
                )
                if value is None
                else None,
            )
            for field in (*reader.PARTS, *(("recovery",) if recovery else ()))
        )
        report = CaseReport(
            context=task.context,
            source_kind=case.source_kind,
            source_version=case.source_version,
            policy_version=case.policy_version,
            scorer_version=case.scorer_version,
            result=AgentResult(
                run_id=task.context.run_id,
                case_id=task.context.case_id,
                trial_id=task.context.trial_id,
                decision="review",
                outcome="review_required",
                usage=zero_usage("USD"),
                review_ref="invented-review",
            ),
            scores=scores,
        )
        wrapped = ManifestCaseReport(
            manifest=loaded.pin,
            group_id=loaded.manifest.entries[0].group_id,
            split="development",
            scorer_id=loaded.manifest.entries[0].scorer_id,
            report=report,
        )
        rows.append(TrialRow(task=task, report=wrapped))
    batch = BatchReport(schedule=schedule, rows=tuple(rows))
    manifest = BaselineManifest(
        execution_id="invented-unit-only",
        algorithm="olist-confirmed-service-rules-v1",
        candidate=factory.candidate,
        started_at=NOW - timedelta(minutes=20),
        finished_at=NOW - timedelta(minutes=10),
        batch_sha256=pin(batch),
    )
    verified = VerifiedBaseline(manifest, batch)
    calls = []

    def pinned_read(root, actual, **kwargs):
        assert root == Path("invented-private-capture") and actual is loaded
        assert kwargs == dict(
            route=factory.route,
            selected="rules",
            evidence_sha256=pin(manifest),
            candidate_sha256=pin(factory.candidate),
        )
        calls.append(True)
        return verified

    monkeypatch.setattr(reader, "read_comparator", pinned_read)
    kwargs = dict(
        root=Path("invented-private-capture"),
        loaded=loaded,
        route=factory.route,
        selected="rules",
        evidence_sha256=pin(manifest),
        candidate_sha256=pin(factory.candidate),
        checked_at=NOW,
    )
    return kwargs, calls, verified


def scopes_for(report):
    case = report.cases[0]
    return tuple(
        MethodScope(
            field=field,
            part=part,
            method=method,
            input_sha256=case.input_sha256,
            reference_sha256=case.reference_sha256,
            source_sha256=report.manifest_sha256,
            evaluator_sha256=report.evaluator_sha256,
            slices=case.slices,
            permitted_use="development",
            authority_reference="invented-test-only-no-real-grant",
            granted_at=report.started_at - timedelta(seconds=1),
            expires_at=NOW + timedelta(hours=1),
        )
        for field, (part, method) in reader.PARTS.items()
    )


@pytest.mark.parametrize(
    "values,expected",
    [
        ((True, True, True), "supported"),
        ((True, None, True), "unresolved"),
        ((True, False, True), "contradicted"),
        ((False, None, True), "contradicted"),
    ],
)
def test_all_repetitions_are_bound_and_failure_dominates_unknown(monkeypatch, values, expected):
    kwargs, calls, _ = setup(monkeypatch, values=values)
    result = reader.read_method_evidence(**kwargs)
    assert calls == [True]
    assert len(result.readback.facts) == 3
    assert all(f.values == values and f.disposition == expected for f in result.readback.facts)
    assert all(len(f.row_sha256) == 3 for f in result.readback.facts)
    assert not result.claims and not result.verified_claim_pins
    assert not result.readback.release_allowed
    assert not result.readback.semantic_reference_authenticated


def test_actual_input_reference_and_group_projection_are_bound(monkeypatch):
    kwargs, _, _ = setup(monkeypatch)
    result = reader.read_method_evidence(**kwargs)
    case = result.readback.cases[0]
    original = kwargs["loaded"].manifest.entries[0].case
    assert case.input_sha256 == sha256(original.input.request.encode())
    assert case.slices == original.slices and case.split == "development"
    assert any(k.startswith("normalized_text:") for k in case.source_keys)
    assert any(k.startswith("order:") for k in case.source_keys)


def test_scope_can_be_frozen_before_capture_without_its_outcome_hash(monkeypatch):
    from olist_support.service_h10 import private_scenario

    kwargs, calls, verified = setup(monkeypatch)
    loaded = kwargs["loaded"]
    case = loaded.manifest.entries[0].case
    evaluator = sha256(
        Path(reader.__file__).read_bytes() + verified.manifest.candidate.scorer_sha256.encode()
    )
    scope = MethodScope(
        field="exact_state",
        part="authoritative_state",
        method="state_observation",
        input_sha256=sha256(case.input.request.encode()),
        reference_sha256=pin(private_scenario(case)),
        source_sha256=loaded.pin.sha256,
        evaluator_sha256=evaluator,
        slices=case.slices,
        permitted_use="development",
        authority_reference="invented-prospective-test-grant",
        granted_at=NOW - timedelta(hours=1),
        expires_at=NOW + timedelta(hours=1),
    )
    assert not calls and scope.source_sha256 != pin(verified.manifest)
    result = reader.read_method_evidence(
        **kwargs, scopes=(scope,), trusted_scope_pins=frozenset((pin(scope),))
    )
    assert calls == [True] and len(result.claims) == 1
    assert result.claims[0].source_sha256 == loaded.pin.sha256
    impossible = scope.model_copy(update={"source_sha256": pin(verified.manifest)})
    with pytest.raises(ValueError, match="scope differs"):
        reader.read_method_evidence(
            **kwargs, scopes=(impossible,), trusted_scope_pins=frozenset((pin(impossible),))
        )


@pytest.mark.parametrize(
    "values,expected", [((True, False, True), "contradicted"), ((True, None, True), "unresolved")]
)
def test_only_separately_trusted_scopes_produce_claims_and_recheck_artifacts(
    monkeypatch, values, expected
):
    kwargs, calls, _ = setup(monkeypatch, values=values)
    first = reader.read_method_evidence(**kwargs)
    scopes = scopes_for(first.readback)
    with pytest.raises(ValueError, match="separately trusted"):
        reader.read_method_evidence(**kwargs, scopes=scopes)
    result = reader.read_method_evidence(
        **kwargs, scopes=scopes, trusted_scope_pins=frozenset(pin(s) for s in scopes)
    )
    assert calls == [True, True, True]
    assert len(result.claims) == len(result.verified_claim_pins) == 3
    assert all(c.disposition == expected for c in result.claims)
    changed = result.claims[0].model_copy(update={"disposition": "supported"})
    assert pin(changed) not in result.verified_claim_pins


@pytest.mark.parametrize(
    "change",
    [
        {"permitted_use": "qualification"},
        {"input_sha256": "f" * 64},
        {"reference_sha256": "f" * 64},
        {"source_sha256": "f" * 64},
        {"evaluator_sha256": "f" * 64},
        {"slices": ("invented-other",)},
        {"granted_at": NOW - timedelta(minutes=15)},
        {"expires_at": NOW},
        {"field": "intent", "part": "meaning", "method": "validated_construction"},
        {"field": "recovery", "part": "declared_fault", "method": "fault_observation"},
    ],
)
def test_even_trusted_scope_cannot_expand_the_verified_part_or_time(monkeypatch, change):
    kwargs, _, _ = setup(monkeypatch)
    first = reader.read_method_evidence(**kwargs)
    scope = scopes_for(first.readback)[0].model_copy(update=change)
    with pytest.raises(ValueError):
        reader.read_method_evidence(
            **kwargs, scopes=(scope,), trusted_scope_pins=frozenset((pin(scope),))
        )


def test_duplicate_scope_refuses_and_evidence_hash_changes_with_any_repetition(monkeypatch):
    kwargs, _, _ = setup(monkeypatch)
    report = reader.read_method_evidence(**kwargs).readback
    scopes = scopes_for(report)
    with pytest.raises(ValueError, match="duplicate"):
        reader.read_method_evidence(
            **kwargs,
            scopes=(scopes[0], scopes[0]),
            trusted_scope_pins=frozenset((pin(scopes[0]),)),
        )
    first = reader.read_method_evidence(
        **kwargs, scopes=scopes, trusted_scope_pins=frozenset(pin(s) for s in scopes)
    )
    changed = report.facts[0].model_copy(
        update={"row_sha256": ("f" * 64, *report.facts[0].row_sha256[1:])}
    )
    assert pin(changed) != pin(report.facts[0])
    assert all(c.evidence_sha256 for c in first.claims)
    assert all(c.disposition == "supported" for c in first.claims)


def test_objective_admissions_leave_semantic_and_qualification_requirements_unmet(monkeypatch):
    from agent_harness.evaluation_standards import StandardProfile
    from olist_support.evidence_methods import audit_methods
    from test_olist_evidence_methods import ACCEPTANCE_PIN, RAW, ROOT

    kwargs, _, _ = setup(monkeypatch)
    report = reader.read_method_evidence(**kwargs).readback
    scopes = scopes_for(report)
    trusted = frozenset(pin(s) for s in scopes)
    result = reader.read_method_evidence(**kwargs, scopes=scopes, trusted_scope_pins=trusted)
    audit = audit_methods(
        StandardProfile.model_validate_json(
            (ROOT / "docs/evaluation/profiles/olist.json").read_bytes()
        ),
        report.cases,
        result.claims,
        scopes,
        acceptance_raw=RAW,
        expected_acceptance_sha256=ACCEPTANCE_PIN,
        trusted_scope_pins=trusted,
        verified_claim_pins=result.verified_claim_pins,
        qualifications={},
        now=NOW,
    )
    assert audit["required_claims"] == 10 and audit["admitted_supported_claims"] == 0
    assert any("intent:meaning" in b for b in audit["blockers"])
    assert any("amount:requested_meaning" in b for b in audit["blockers"])
    assert not audit["method_coverage_met"] and not audit["qualification_allowed"]
    assert not audit["release_allowed"]


def test_declared_response_loss_is_visible_without_admitting_process_crash_claim(monkeypatch):
    kwargs, _, _ = setup(monkeypatch, recovery=True)
    result = reader.read_method_evidence(**kwargs)
    assert len(result.readback.facts) == 4 and result.readback.facts[-1].field == "recovery"
    assert result.readback.recovery_scope == "response_loss_only_not_process_death"
    assert all("crash_restart" not in c.slices for c in result.readback.cases)
    assert not result.claims


@pytest.mark.parametrize("kind", ["naive", "future_capture"])
def test_clock_rejection_does_not_invent_observation_times(monkeypatch, kind):
    kwargs, calls, _ = setup(monkeypatch)
    kwargs["checked_at"] = NOW.replace(tzinfo=None) if kind == "naive" else NOW - timedelta(days=1)
    with pytest.raises(ValueError):
        reader.read_method_evidence(**kwargs)
    assert len(calls) == (0 if kind == "naive" else 1)


def test_reader_failure_produces_no_trusted_result(monkeypatch):
    kwargs, _, _ = setup(monkeypatch)

    def corrupt(*args, **kwargs):
        raise ValueError("invented pin or observation mismatch")

    monkeypatch.setattr(reader, "read_comparator", corrupt)
    with pytest.raises(ValueError, match="mismatch"):
        reader.read_method_evidence(**kwargs)
