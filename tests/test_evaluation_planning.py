"""Invented schedules/evidence verify boundaries, not authentic grants or domain quality."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from agent_harness.evaluation_plan_cli import main
from agent_harness.evaluation_planning import (
    AgentEvidencePlan,
    AllowanceSnapshot,
    AllowanceSnapshots,
    AssessmentProposal,
    AttemptLine,
    AttemptPlan,
    EvidenceMatrix,
    EvidenceSpan,
    forecast_attempts,
    validate_matrix,
)
from agent_harness.evaluation_standards import Review, StandardProfile
from agent_harness.release_contracts import sha256
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]


def line(**changes):
    values = dict(
        line_id="invented-line",
        provider="invented-provider",
        agent="invented-agent",
        purpose="candidate",
        cases=3,
        trials=2,
        calls_per_trial=2,
        orderings=2,
        extra_attempts_per_call=1,
    )
    values.update(changes)
    return AttemptLine(**values)


def snapshot(**changes):
    values = dict(
        provider="invented-provider",
        ledger_reference="invented-not-a-grant",
        observed_at=datetime(2026, 10, 26, tzinfo=UTC),
        maximum=60,
        consumed=12,
        agents=("invented-agent",),
        purposes=("candidate",),
    )
    values.update(changes)
    return AllowanceSnapshot(**values)


def test_forecast_counts_every_dimension_but_never_allows_dispatch():
    plan = AttemptPlan(lines=(line(),))
    before = plan.canonical_json()
    result = forecast_attempts(plan, (snapshot(),))
    assert result.maximum_by_provider == {"invented-provider": 48}
    assert result.maximum_by_agent == {"invented-agent": 48}
    assert result.remaining_before == {"invented-provider": 48}
    assert result.fits_declared_snapshots and not result.blockers
    assert result.dispatch_allowed is False and result.release_allowed is False
    assert plan.canonical_json() == before


@pytest.mark.parametrize(
    "changes,blocker",
    [
        ({"purpose": "judge"}, "scope_not_in_snapshot"),
        ({"agent": "other-agent"}, "scope_not_in_snapshot"),
        ({"provider": "other-provider"}, "missing_allowance"),
        ({"trials": 3}, "attempt_cap_exceeded"),
    ],
)
def test_scope_and_cap_never_expand_from_an_offline_plan(changes, blocker):
    result = forecast_attempts(AttemptPlan(lines=(line(**changes),)), (snapshot(),))
    assert any(blocker in b for b in result.blockers)
    assert not result.fits_declared_snapshots and not result.dispatch_allowed


def test_shared_allowance_is_not_per_agent_and_missing_provider_stays_blocked():
    plan = AttemptPlan(lines=(line(), line(line_id="second", agent="second-agent")))
    result = forecast_attempts(plan, (snapshot(agents=("invented-agent", "second-agent")),))
    assert result.maximum_by_provider == {"invented-provider": 96}
    assert "invented-provider:attempt_cap_exceeded" in result.blockers
    assert forecast_attempts(plan, ()).blockers


def test_duplicate_snapshots_and_lines_refuse_instead_of_multiplying_allowance():
    with pytest.raises(ValueError, match="authoritative"):
        forecast_attempts(AttemptPlan(lines=(line(),)), (snapshot(), snapshot()))
    with pytest.raises(ValueError, match="duplicate schedule"):
        forecast_attempts(AttemptPlan(lines=(line(), line())), (snapshot(),))
    forged = line().model_copy(update={"cases": True})
    with pytest.raises(ValidationError):
        forecast_attempts(AttemptPlan(lines=(forged,)), (snapshot(),))


def test_exact_unicode_span_binding_does_not_assert_semantic_support():
    source = "é: invented policy"
    span = EvidenceSpan(source_sha256=sha256(source.encode()), start=3, end=11, text="invented")
    assert span.verify(source)
    assert not span.verify(source + "!")
    assert not span.model_copy(update={"start": 2}).verify(source)
    assert not span.model_copy(update={"end": 999}).verify(source)


def test_assessments_cannot_forge_a_human_review_or_enable_release():
    source = "invented"
    source_pin = sha256(source.encode())
    values = dict(
        agent="invented-agent",
        field="invented-field",
        input_sha256="1" * 64,
        evaluator_sha256="2" * 64,
        source_sha256s=(source_pin,),
        method="model_assessment",
        judgment="supported",
        spans=(EvidenceSpan(source_sha256=source_pin, start=0, end=8, text=source),),
        explanation="Invented diagnostic, not verified meaning.",
    )
    assessment = AssessmentProposal(**values)
    assert assessment.status == "diagnostic_only" and not assessment.release_allowed
    with pytest.raises(ValidationError):
        Review.model_validate_json(assessment.canonical_json())
    for change in ({"release_allowed": True}, {"status": "qualified"}, {"spans": ()}):
        with pytest.raises(ValidationError):
            AssessmentProposal(**(values | change))
    with pytest.raises(ValidationError, match="outside declared"):
        AssessmentProposal(**(values | {"source_sha256s": ("3" * 64,)}))
    assert AssessmentProposal(**(values | {"judgment": "unresolved", "spans": ()}))


def test_tracked_matrix_covers_every_current_field_and_slice():
    matrix = EvidenceMatrix.model_validate_json(
        (ROOT / "docs/evaluation/evidence-paths-v1.json").read_text(encoding="utf-8")
    )
    profiles = tuple(
        StandardProfile.model_validate_json(p.read_text(encoding="utf-8"))
        for p in sorted((ROOT / "docs/evaluation/profiles").glob("*.json"))
    )
    assert validate_matrix(matrix, profiles) == 43
    assert all(r.acceptance == "pending" for a in matrix.agents for r in a.requirements)
    raw = json.loads(matrix.canonical_json())
    raw["agents"][0]["requirements"].pop()
    with pytest.raises(ValueError, match="fields differ"):
        validate_matrix(EvidenceMatrix.model_validate_json(json.dumps(raw)), profiles)
    agent = matrix.agents[0]
    for change in (
        {"profile_sha256": "f" * 64},
        {"required_slices": ("wrong-slice",)},
    ):
        with pytest.raises(ValueError):
            validate_matrix(
                matrix.model_copy(update={"agents": (agent.model_copy(update=change),)}), profiles
            )
    with pytest.raises(ValueError, match="duplicate agent"):
        validate_matrix(matrix.model_copy(update={"agents": (*matrix.agents, agent)}), profiles)
    with pytest.raises(ValidationError):
        AgentEvidencePlan.model_validate_json(
            agent.model_copy(
                update={"requirements": (*agent.requirements, agent.requirements[0])}
            ).canonical_json()
        )


def test_cli_pins_duplicate_keys_and_caps_are_not_bypassed(tmp_path, capsys):
    from agent_harness.release_contracts import pin

    plan = AttemptPlan(lines=(line(),))
    snapshots = AllowanceSnapshots(snapshots=(snapshot(),))
    plan_file, snapshots_file = tmp_path / "plan.json", tmp_path / "snapshots.json"
    plan_file.write_text(plan.canonical_json(), encoding="utf-8")
    snapshots_file.write_text(snapshots.canonical_json(), encoding="utf-8")
    args = [
        "forecast",
        "--plan",
        str(plan_file),
        "--plan-sha256",
        pin(plan),
        "--snapshots",
        str(snapshots_file),
        "--snapshots-sha256",
        pin(snapshots),
    ]
    assert main(args) == 0
    assert json.loads(capsys.readouterr().out)["dispatch_allowed"] is False
    plan_file.write_text(plan.canonical_json().replace('"cases":3', '"cases":4'), encoding="utf-8")
    assert main(args) == 1
    assert "cases" not in capsys.readouterr().err
    plan_file.write_text('{"lines":[],"lines":[]}', encoding="utf-8")
    assert main(args) == 1
    caps = AllowanceSnapshots(snapshots=(snapshot(consumed=13),))
    snapshots_file.write_text(caps.canonical_json(), encoding="utf-8")
    plan_file.write_text(plan.canonical_json(), encoding="utf-8")
    args[-1] = pin(caps)
    assert main(args) == 1
    output = json.loads(capsys.readouterr().out)
    assert not output["fits_declared_snapshots"]


def test_matrix_cli_checks_external_pin(tmp_path, capsys):
    from agent_harness.release_contracts import pin

    path = ROOT / "docs/evaluation/evidence-paths-v1.json"
    matrix = EvidenceMatrix.model_validate_json(path.read_text(encoding="utf-8"))
    args = [
        "matrix",
        "--matrix",
        str(path),
        "--matrix-sha256",
        pin(matrix),
        "--profiles",
        str(ROOT / "docs/evaluation/profiles"),
    ]
    assert main(args) == 0
    assert json.loads(capsys.readouterr().out) == {"pending_fields": 43, "release_allowed": False}
    args[4] = "0" * 64
    assert main(args) == 1
