"""A methodology audit cannot substitute outcomes for sealed H10 results."""

from dataclasses import replace

import pytest
from agent_harness.evaluation_binding import verify_binding
from agent_harness.evaluation_standards import (
    StandardCase,
    StandardProfile,
    StandardProtocol,
    StandardRow,
    StandardStudy,
)
from agent_harness.release_contracts import pin
from agent_harness.trials import TrialTiming
from release_fixtures import logical_pair


@pytest.fixture(scope="module")
def binding(tmp_path_factory):
    loaded, baseline, candidate, policy, _ = logical_pair(tmp_path_factory.mktemp("audit-binding"))
    entry = loaded.manifest.entries[0]
    profile = StandardProfile(
        agent=candidate.batch.schedule.tasks[0].context.agent_id,
        version="invented",
        required_fields=("invented_correct",),
        required_holdout_slices=("invented",),
    )
    protocol = StandardProtocol(
        version="invented",
        profile_sha256=pin(profile),
        dataset_sha256=loaded.pin.sha256,
        scorer_sha256=candidate.manifest.candidate.scorer_sha256,
        baseline_sha256=pin(baseline.manifest),
        frozen_at=baseline.manifest.started_at,
        trials_per_case=3,
    )
    case = StandardCase(
        case_id=entry.case.case_id,
        independence_keys=(entry.group_id,),
        language_family="invented",
        input_text=entry.case.input.request,
        split=entry.split,
        source_kind=entry.case.source_kind,
        slices=("invented",),
        required_review=entry.case.expected.required_review,
        eligible_for_autonomy=entry.case.expected.eligible_for_autonomy,
        critical=True,
    )
    rows = []
    for row in candidate.batch.rows:
        usage = row.report.report.result.usage
        rows.append(
            StandardRow(
                case_id=row.task.context.case_id,
                trial_id=row.task.context.trial_id,
                outcome="completed",
                correct=True,
                unsafe=False,
                fields={"invented_correct": True},
                baseline_correct=True,
                elapsed_seconds=row.timing.elapsed_seconds,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                model_calls=usage.model_calls,
                cost=usage.cost,
                cost_currency=usage.cost_currency,
            )
        )
    study = StandardStudy(
        version="invented",
        protocol_sha256=pin(protocol),
        candidate_spec_sha256=pin(candidate.manifest.candidate),
        candidate_evidence_sha256=pin(candidate.manifest),
        started_at=candidate.manifest.started_at,
        finished_at=candidate.manifest.finished_at,
        cases=(case,),
        trial_ids=candidate.batch.schedule.trial_ids,
        rows=tuple(rows),
    )
    return profile, protocol, study, loaded, baseline, candidate, policy.report.required_case_ids


def test_binding_checks_actual_scores_not_qualification_status(binding):
    # This one-case toy binds, but cannot qualify methodology: no independent labels,
    # split coverage, sampling or thresholds. Binding is not qualification.
    verify_binding(*binding)


@pytest.mark.parametrize("declared", [None, 0.0, 5.9, 6.0, 100.0])
def test_latency_requires_exact_sealed_parent_measurement(binding, declared):
    p, protocol, study, loaded, baseline, candidate, required = binding
    batch = candidate.batch.model_copy(
        update={
            "rows": tuple(
                row.model_copy(
                    update={
                        "timing": TrialTiming(
                            setup_seconds=1.0, execution_seconds=2.0, cleanup_seconds=3.0
                        )
                    }
                )
                for row in candidate.batch.rows
            )
        }
    )
    candidate = replace(
        candidate,
        batch=batch,
        manifest=candidate.manifest.model_copy(update={"batch_sha256": pin(batch)}),
    )
    study = study.model_copy(
        update={
            "candidate_evidence_sha256": pin(candidate.manifest),
            "rows": tuple(
                row.model_copy(update={"elapsed_seconds": declared}) for row in study.rows
            ),
        }
    )
    if declared == 6.0:
        verify_binding(p, protocol, study, loaded, baseline, candidate, required)
    else:
        with pytest.raises(ValueError, match="sealed parent measurement"):
            verify_binding(p, protocol, study, loaded, baseline, candidate, required)


def test_historical_rows_cannot_gain_claimed_latency(binding):
    p, protocol, study, loaded, baseline, candidate, required = binding
    batch = candidate.batch.model_copy(
        update={
            "rows": tuple(row.model_copy(update={"timing": None}) for row in candidate.batch.rows)
        }
    )
    candidate = replace(
        candidate,
        batch=batch,
        manifest=candidate.manifest.model_copy(update={"batch_sha256": pin(batch)}),
    )
    study = study.model_copy(
        update={
            "candidate_evidence_sha256": pin(candidate.manifest),
            "rows": tuple(row.model_copy(update={"elapsed_seconds": None}) for row in study.rows),
        }
    )
    verify_binding(p, protocol, study, loaded, baseline, candidate, required)
    study = study.model_copy(
        update={
            "rows": tuple(row.model_copy(update={"elapsed_seconds": 100.0}) for row in study.rows)
        }
    )
    with pytest.raises(ValueError, match="sealed parent measurement"):
        verify_binding(p, protocol, study, loaded, baseline, candidate, required)


@pytest.mark.parametrize(
    "change",
    [
        "candidate",
        "dataset",
        "agent",
        "group",
        "input",
        "critical",
        "outcome",
        "field",
        "usage",
        "rows",
    ],
)
def test_unrelated_or_forged_studies_are_rejected(binding, change):
    p, protocol, s, loaded, baseline, candidate, required = binding
    if change == "candidate":
        s = s.model_copy(update={"candidate_evidence_sha256": "0" * 64})
    elif change == "dataset":
        protocol = protocol.model_copy(update={"dataset_sha256": "0" * 64})
    elif change == "agent":
        p = p.model_copy(update={"agent": "other-agent"})
    elif change in ("group", "input", "critical"):
        updates = (
            {"independence_keys": ("unrelated",)}
            if change == "group"
            else {"input_text": "changed"}
            if change == "input"
            else {"critical": False}
        )
        s = s.model_copy(update={"cases": (s.cases[0].model_copy(update=updates),)})
    elif change == "rows":
        s = s.model_copy(update={"rows": s.rows[1:]})
    else:
        updates = (
            {"correct": False}
            if change == "outcome"
            else {"fields": {"invented_correct": False}, "correct": False}
            if change == "field"
            else {"input_tokens": 123456}
        )
        s = s.model_copy(update={"rows": (s.rows[0].model_copy(update=updates), *s.rows[1:])})
    with pytest.raises(ValueError):
        verify_binding(p, protocol, s, loaded, baseline, candidate, required)
