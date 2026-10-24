"""Invented audit inputs test rejection logic, not provider or domain quality."""

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from agent_harness.evaluation_audit import main
from agent_harness.evaluation_standards import (
    Review,
    StandardCase,
    StandardProfile,
    StandardProtocol,
    StandardRow,
    StandardStudy,
    audit_study,
    text_fingerprint,
)
from agent_harness.release_contracts import pin

NOW = datetime(2026, 10, 24, tzinfo=UTC)


def sample():
    profile = StandardProfile(
        version="invented",
        agent="invented",
        required_fields=("action",),
        required_holdout_slices=("eligible", "review"),
    )
    review = Review(
        reviewer="invented-human",
        reference="invented-reference",
        reviewed_at=NOW,
        kind="human_blind",
    )
    protocol = StandardProtocol(
        version="invented-only",
        profile_sha256=pin(profile),
        dataset_sha256="1" * 64,
        scorer_sha256="2" * 64,
        baseline_sha256="3" * 64,
        frozen_at=NOW,
        trials_per_case=3,
        min_holdout_groups=2,
        min_holdout_groups_per_slice=1,
        min_correct_rate=1.0,
        min_field_correct_rates={"action": 1.0},
        min_all_repetitions_correct_rate=1.0,
        max_group_error_upper_bound=1.0,
        max_unnecessary_review_rate=0.0,
        max_missed_review_rate=0.0,
        max_unresolved_rate=0.0,
        max_p95_seconds=2.0,
        max_total_cost=Decimal(1),
        cost_currency="USD",
        max_model_calls=12,
        max_total_tokens=144,
        representative_sampling_ref="invented-sampling",
        independence_review_ref="invented-independence",
        evaluator_validation_ref="invented-scorer",
        sample_size_rationale_ref="invented-tiny-logic-test-not-production",
        baseline_review=review,
        threshold_review=review,
    )
    cases = tuple(
        StandardCase(
            case_id=f"c{i}",
            independence_keys=(f"group-{i}",),
            language_family=f"family-{i}",
            input_text=f"invented request {i}",
            split=split,
            source_kind="synthetic",
            slices=("review",) if i == 3 else ("eligible",),
            required_review=i == 3,
            eligible_for_autonomy=i != 3,
            critical=True,
            label_review=review,
        )
        for i, split in enumerate(("development", "regression", "holdout", "holdout"))
    )
    trials = ("t1", "t2", "t3")
    rows = tuple(
        StandardRow(
            case_id=c.case_id,
            trial_id=t,
            outcome="review_required" if c.required_review else "completed",
            correct=True,
            unsafe=False,
            fields={"action": True},
            baseline_correct=True,
            elapsed_seconds=1.0,
            input_tokens=10,
            output_tokens=2,
            model_calls=1,
            cost=Decimal(0),
            cost_currency="USD",
        )
        for c in cases
        for t in trials
    )
    study = StandardStudy(
        version="invented",
        protocol_sha256=pin(protocol),
        candidate_spec_sha256="4" * 64,
        candidate_evidence_sha256="5" * 64,
        started_at=NOW + timedelta(seconds=1),
        finished_at=NOW + timedelta(seconds=2),
        cases=cases,
        trial_ids=trials,
        rows=rows,
    )
    return profile, protocol, study


def audit(profile, protocol, study):
    return audit_study(profile, protocol, study, now=NOW + timedelta(seconds=3))


def test_complete_invented_design_qualifies_methodology_only():
    result = audit(*sample())
    assert result["methodology_qualified"] and not result["release_allowed"]
    assert result["metrics"]["all"]["scheduled"] == 12
    assert result["holdout_source_components"] == 2
    assert result["metrics"]["holdout"]["all_repetitions_correct_cases"] == 2
    assert result["holdout_group_error_uncertainty"]["upper"] > 0.8


@pytest.mark.parametrize("kind", ["source", "text", "language", "transitive"])
def test_leakage_is_not_hidden_by_different_ids(kind):
    p, protocol, s = sample()
    cases = list(s.cases)
    if kind == "source":
        cases[2] = cases[2].model_copy(update={"independence_keys": cases[0].independence_keys})
    elif kind == "text":
        cases[2] = cases[2].model_copy(update={"input_text": "  INVENTED\nREQUEST 0 "})
    elif kind == "language":
        cases[2] = cases[2].model_copy(update={"language_family": cases[0].language_family})
    else:
        cases[2] = cases[2].model_copy(update={"independence_keys": ("a", "shared")})
        cases[3] = cases[3].model_copy(update={"independence_keys": ("shared", "b")})
    result = audit(p, protocol, s.model_copy(update={"cases": tuple(cases)}))
    assert not result["methodology_qualified"]
    assert any("leakage" in x or "insufficient_holdout_groups" in x for x in result["blockers"])


@pytest.mark.parametrize("kind", ["ai_provisional", "human_retrospective", "future", "qualified"])
def test_label_acceptance_after_output_cannot_become_blind_gold(kind):
    p, protocol, s = sample()
    case = s.cases[2]
    review = case.label_review
    if kind == "qualified":
        p = p.model_copy(update={"qualified_label_review_required": True})
        protocol = protocol.model_copy(update={"profile_sha256": pin(p)})
        s = s.model_copy(update={"protocol_sha256": pin(protocol)})
    elif kind == "future":
        review = review.model_copy(update={"reviewed_at": s.finished_at})
    else:
        review = review.model_copy(update={"kind": kind})
    cases = (*s.cases[:2], case.model_copy(update={"label_review": review}), s.cases[3])
    result = audit(p, protocol, s.model_copy(update={"cases": cases}))
    assert "labels_not_independently_frozen" in result["blockers"]


@pytest.mark.parametrize(
    "change,blocker",
    [
        ({"rows": ()}, "incomplete_results"),
        ({"trial_ids": ("t1",)}, "invalid"),
        ({"finished_at": NOW + timedelta(days=1)}, "protocol_or_capture_time_order"),
    ],
)
def test_missing_or_changed_schedule_never_disappears(change, blocker):
    p, protocol, s = sample()
    if blocker == "invalid":
        with pytest.raises(ValueError, match="unexpected"):
            audit(p, protocol, s.model_copy(update=change))
    else:
        result = audit(p, protocol, s.model_copy(update=change))
        assert blocker in result["blockers"]


@pytest.mark.parametrize(
    "change,blocker",
    [
        ({"correct": False, "unsafe": True}, "unsafe_effect"),
        ({"correct": False, "outcome": "unresolved"}, "incomplete_results"),
        ({"correct": False, "fields": {"action": False}}, "previously_passing_trial_regressed"),
        ({"fields": {}}, "incomplete_results"),
        ({"cost": None, "cost_currency": None}, "cost_unknown_or_currency_mismatch"),
        ({"input_tokens": None}, "token_usage_unknown"),
        ({"elapsed_seconds": None}, "latency_unknown"),
        ({"baseline_correct": None}, "paired_baseline_incomplete"),
    ],
)
def test_one_bad_trial_is_not_hidden_by_eleven_passes(change, blocker):
    p, protocol, s = sample()
    rows = (*s.rows[:6], s.rows[6].model_copy(update=change), *s.rows[7:])
    result = audit(p, protocol, s.model_copy(update={"rows": rows}))
    assert not result["methodology_qualified"] and blocker in result["blockers"]


def test_review_errors_have_separate_denominators_and_missing_rows_stay_scheduled():
    p, protocol, s = sample()
    rows = list(s.rows)
    rows[6] = rows[6].model_copy(update={"correct": False, "outcome": "review_required"})
    rows[9] = rows[9].model_copy(update={"correct": False, "outcome": "completed"})
    rows.pop(10)
    result = audit(p, protocol, s.model_copy(update={"rows": tuple(rows)}))
    held = result["metrics"]["holdout"]
    assert held["scheduled"] == 6 and held["missing"] == 1
    assert held["unnecessary_review_rate"] == held["missed_review_rate"] == 1 / 3
    assert held["field_denominator"] == 6 and held["field_correct"]["action"] == 5


def test_unset_limits_and_tiny_sample_uncertainty_fail_closed():
    p, protocol, s = sample()
    protocol = protocol.model_copy(
        update={"max_group_error_upper_bound": 0.05, "max_p95_seconds": None}
    )
    result = audit(p, protocol, s.model_copy(update={"protocol_sha256": pin(protocol)}))
    assert "holdout_group_error_uncertainty_above_limit" in result["blockers"]
    assert "protocol_requirement_unset:max_p95_seconds" in result["blockers"]


def test_schema_rejects_duplicate_rows_and_unsafe_success():
    p, protocol, s = sample()
    with pytest.raises(ValueError, match="duplicate"):
        audit(p, protocol, s.model_copy(update={"rows": (*s.rows, s.rows[0])}))
    with pytest.raises(ValueError, match="unsafe"):
        StandardRow.model_validate(s.rows[0].model_copy(update={"unsafe": True}))
    with pytest.raises(ValueError, match="pin"):
        audit(p, protocol, s.model_copy(update={"protocol_sha256": "0" * 64}))


def test_cli_requires_external_pins_and_never_overwrites(tmp_path, capsys):
    p, protocol, s = sample()
    args = []
    for name, value in (("profile", p), ("protocol", protocol), ("study", s)):
        path = tmp_path / (name + ".json")
        path.write_text(value.canonical_json(), encoding="utf-8")
        args += ["--" + name, str(path), "--" + name + "-sha256", pin(value)]
    output = tmp_path / "audit.json"
    assert main([*args, "--output", str(output)]) == 0
    assert not json.loads(output.read_bytes())["release_allowed"]
    assert "invented request" not in output.read_text()
    before = output.read_bytes()
    assert main([*args, "--output", str(output)]) == 1
    assert output.read_bytes() == before
    args[args.index("--study-sha256") + 1] = "0" * 64
    assert main([*args, "--output", str(tmp_path / "bad.json")]) == 1
    assert not (tmp_path / "bad.json").exists()


def test_all_five_agent_profiles_are_strict_and_have_distinct_measures():
    folder = Path(__file__).resolve().parents[1] / "docs/evaluation/profiles"
    profiles = [StandardProfile.model_validate_json(p.read_bytes()) for p in folder.glob("*.json")]
    assert {p.agent for p in profiles} == {"olist", "cfpb", "revenue", "prior-auth", "supply"}
    assert len({p.required_fields for p in profiles}) == 5
    assert next(p for p in profiles if p.agent == "prior-auth").qualified_label_review_required
    assert next(p for p in profiles if p.agent == "supply").claim_scope == "simulation"
    assert text_fingerprint("Ａ  request\n") == text_fingerprint("a request")


def test_inventory_preserves_historical_evidence_and_acceptance_scope():
    from agent_harness.release_contracts import sha256

    root = Path(__file__).resolve().parents[1]
    inventory = json.loads((root / "docs/evaluation/readiness.json").read_bytes())
    assert not inventory["release_allowed"]
    for agent, record in inventory["agents"].items():
        profile = StandardProfile.model_validate_json((root / record["profile"]).read_bytes())
        assert profile.agent == agent and pin(profile) == record["profile_canonical_sha256"]
        for name, digest in record["historical_evidence_lf_sha256"].items():
            assert sha256((root / name).read_bytes().replace(b"\r\n", b"\n")) == digest
        assert not record["release_allowed"]
    acceptance = inventory["retrospective_label_acceptance"]
    assert acceptance["case_count"] == 12 and not acceptance["blind_annotation_established"]
    assert not acceptance["baseline_approval"] and not acceptance["threshold_approval"]


@pytest.mark.parametrize(
    "field,change,blocker",
    [
        ("max_model_calls", 1, "model_call_limit_not_met"),
        ("max_total_tokens", 1, "token_limit_not_met"),
        ("max_total_cost", Decimal(0), "cost_limit_not_met"),
        ("max_p95_seconds", 0.1, "holdout_limit_not_met:p95_seconds"),
        ("min_holdout_groups_per_slice", 2, "insufficient_holdout_slice_groups:review"),
    ],
)
def test_explicit_budget_latency_and_slice_limits_are_enforced(field, change, blocker):
    p, protocol, s = sample()
    protocol = protocol.model_copy(update={field: change})
    rows = s.rows
    if field == "max_total_cost":
        rows = (
            rows[0].model_copy(update={"cost": Decimal("0.000000000000000000000000000001")}),
            *rows[1:],
        )
    result = audit(
        p, protocol, s.model_copy(update={"protocol_sha256": pin(protocol), "rows": rows})
    )
    assert blocker in result["blockers"]


def test_mismatched_currency_has_no_fabricated_total_and_unknown_calls_fail():
    p, protocol, s = sample()
    rows = (
        s.rows[0].model_copy(
            update={"cost": Decimal(2), "cost_currency": "SIM", "model_calls": None}
        ),
        *s.rows[1:],
    )
    result = audit(p, protocol, s.model_copy(update={"rows": rows}))
    assert result["observed_total_cost"] is None
    assert result["known_cost_by_currency"]["SIM"] == "2"
    assert "model_call_usage_unknown" in result["blockers"]


def test_simulation_requires_sensitivity_and_qualified_review_can_pass():
    p, protocol, s = sample()
    p = p.model_copy(update={"claim_scope": "simulation", "qualified_label_review_required": True})
    protocol = protocol.model_copy(update={"profile_sha256": pin(p)})
    cases = tuple(
        c.model_copy(
            update={"label_review": c.label_review.model_copy(update={"kind": "qualified_blind"})}
        )
        for c in s.cases
    )
    s = s.model_copy(update={"protocol_sha256": pin(protocol), "cases": cases})
    result = audit(p, protocol, s)
    assert result["blockers"] == ["simulation_sensitivity_not_reviewed"]
    protocol = protocol.model_copy(
        update={"simulation_sensitivity_ref": "invented-reviewed-sensitivity"}
    )
    assert audit(p, protocol, s.model_copy(update={"protocol_sha256": pin(protocol)}))[
        "methodology_qualified"
    ]


def test_correct_flag_cannot_override_expected_review_disposition():
    p, protocol, s = sample()
    rows = (*s.rows[:9], s.rows[9].model_copy(update={"outcome": "completed"}), *s.rows[10:])
    result = audit(p, protocol, s.model_copy(update={"rows": rows}))
    assert not result["methodology_qualified"]
    assert result["metrics"]["holdout"]["correct"] == 5


def test_non_autonomous_completion_does_not_inflate_eligible_denominator():
    p, protocol, s = sample()
    cases = (s.cases[0].model_copy(update={"eligible_for_autonomy": False}), *s.cases[1:])
    result = audit(p, protocol, s.model_copy(update={"cases": cases}))
    assert result["metrics"]["all"]["eligible"] == 6
    assert result["metrics"]["all"]["other_completion"] == 3
    assert result["metrics"]["all"]["required_review"] == 3


def test_duplicate_json_keys_do_not_survive_canonical_pin_comparison(tmp_path):
    p, protocol, s = sample()
    args = []
    for name, value in (("profile", p), ("protocol", protocol), ("study", s)):
        path = tmp_path / (name + ".json")
        content = value.canonical_json()
        if name == "profile":
            content = content.replace("{", '{"version":"hidden-first-value",', 1)
        path.write_text(content, encoding="utf-8")
        args += ["--" + name, str(path), "--" + name + "-sha256", pin(value)]
    output = tmp_path / "duplicate-audit.json"
    assert main([*args, "--output", str(output)]) == 1
    assert not output.exists()


def test_average_cannot_hide_a_failing_required_slice():
    p, protocol, s = sample()
    protocol = protocol.model_copy(
        update={"min_correct_rate": 0.8, "min_all_repetitions_correct_rate": 0.0}
    )
    cases = tuple(c.model_copy(update={"critical": False}) for c in s.cases)
    rows = (
        *s.rows[:9],
        s.rows[9].model_copy(update={"correct": False, "baseline_correct": False}),
        *s.rows[10:],
    )
    result = audit(
        p,
        protocol,
        s.model_copy(update={"protocol_sha256": pin(protocol), "cases": cases, "rows": rows}),
    )
    assert result["metrics"]["holdout"]["correct_rate"] > 0.8
    assert "holdout_limit_not_met:correct_rate" not in result["blockers"]
    assert "holdout_slice_limit_not_met:review:correct_rate" in result["blockers"]


def test_assistive_profile_does_not_require_autonomous_clinical_actions():
    p, protocol, s = sample()
    p = p.model_copy(
        update={"requires_eligible_cases": False, "required_holdout_slices": ("review",)}
    )
    protocol = protocol.model_copy(
        update={"profile_sha256": pin(p), "max_unnecessary_review_rate": None}
    )
    cases = tuple(
        c.model_copy(
            update={"eligible_for_autonomy": False, "required_review": True, "slices": ("review",)}
        )
        for c in s.cases
    )
    rows = tuple(r.model_copy(update={"outcome": "review_required"}) for r in s.rows)
    result = audit(
        p,
        protocol,
        s.model_copy(update={"protocol_sha256": pin(protocol), "cases": cases, "rows": rows}),
    )
    assert result["methodology_qualified"] and not result["release_allowed"]
    assert result["metrics"]["holdout"]["unnecessary_review_rate"] is None
    assert result["metrics"]["holdout"]["eligible"] == 0
