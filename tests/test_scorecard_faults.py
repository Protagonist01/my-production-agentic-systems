"""Scorecards preserve independently executed faults and unknown hook coverage."""

import pytest
from agent_harness.fault_contracts import digest
from agent_harness.scorecard_contracts import ReportPolicy
from agent_harness.scorecards import build_scorecard
from agent_harness.trials import BatchReport
from test_faults import inline


def test_fault_outcomes_require_separate_plan_and_keep_missing_population(tmp_path):
    loaded, schedule, row, actual = inline(tmp_path, 1)
    policy = ReportPolicy(version="report-v1", required_case_ids=(row.task.context.case_id,))
    batch = BatchReport(schedule=schedule, rows=(row,))
    with pytest.raises(ValueError, match="reviewed fault plan"):
        build_scorecard(batch, loaded, policy, reporter_revision="reporter")
    card = build_scorecard(
        batch, loaded, policy, reporter_revision="reporter", fault_plan=schedule.fault_plan
    )
    assert card.fault_outcomes.scheduled_trials == 8 and card.fault_outcomes.missing_rows == 7
    assert card.fault_outcomes.autonomous_completion.numerator == 1
    assert card.fault_plan_sha256 == digest(schedule.fault_plan)
    malformed = next(
        s for s in card.slices if s.dimension == "fault_kind" and s.label == "malformed_output"
    )
    assert malformed.summary.autonomous_completion.numerator == 1
    # Removing all hook evidence cannot turn the positive scorer metrics into a verified pass.
    row = row.model_copy(
        update={
            "report": row.report.model_copy(
                update={"report": row.report.report.model_copy(update={"fault_evidence": None})}
            )
        }
    )
    card = build_scorecard(
        BatchReport(schedule=schedule, rows=(row,)),
        loaded,
        policy,
        reporter_revision="reporter",
        fault_plan=schedule.fault_plan,
    )
    assert card.fault_outcomes.autonomous_completion.numerator == 0
    assert card.cases[0].trials[0].category == "unverified"


def test_duplicate_effect_remains_unsafe_in_scorecard(tmp_path):
    loaded, schedule, row, actual = inline(tmp_path, 5, behavior="blind_retry", deduplicate=False)
    card = build_scorecard(
        BatchReport(schedule=schedule, rows=(row,)),
        loaded,
        ReportPolicy(version="report-v1", required_case_ids=()),
        reporter_revision="reporter",
        fault_plan=schedule.fault_plan,
    )
    assert card.fault_outcomes.observed_violations.numerator == 1
    assert card.fault_outcomes.safety_uncertainty.observed_event_groups == 1
    assert card.fault_outcomes.autonomous_completion.numerator == 0
