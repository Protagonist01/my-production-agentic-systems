"""Actual mock H10 captures projected into methodology, never promoted to release."""

from dataclasses import replace
from datetime import UTC, datetime

import pytest
from agent_harness.evaluation_standards import audit_study
from agent_harness.evaluation_study import assemble_study
from agent_harness.release_contracts import pin
from test_evaluation_binding import binding as binding


def test_assembly_preserves_observed_rows_and_missing_reviews(binding):
    p, protocol, expected, loaded, baseline, candidate, required = binding
    study = assemble_study(
        p, protocol, expected.cases, loaded, baseline, candidate, required_case_ids=required
    )
    assert study.rows == expected.rows and study.cases == expected.cases
    assert study.candidate_evidence_sha256 == pin(candidate.manifest)
    audit = audit_study(p, protocol, study, now=candidate.manifest.finished_at)
    assert not audit["release_allowed"]
    assert "labels_not_independently_frozen" in audit["blockers"]


@pytest.mark.parametrize(
    "change", ["timing", "scores", "batch_pin", "split", "required_id", "baseline"]
)
def test_projection_refuses_unbound_or_unobserved_evidence(binding, change):
    p, protocol, expected, loaded, baseline, candidate, required = binding
    cases = expected.cases
    if change == "batch_pin":
        candidate = replace(
            candidate, manifest=candidate.manifest.model_copy(update={"batch_sha256": "0" * 64})
        )
    elif change == "baseline":
        baseline = replace(
            baseline,
            manifest=baseline.manifest.model_copy(
                update={
                    "candidate": baseline.manifest.candidate.model_copy(
                        update={"scorer_sha256": "0" * 64}
                    )
                }
            ),
        )
    elif change == "split":
        cases = (cases[0].model_copy(update={"split": "holdout"}),)
    elif change == "required_id":
        required = ("unknown",)
    else:
        row = candidate.batch.rows[0]
        if change == "scores":
            row = row.model_copy(
                update={
                    "report": row.report.model_copy(
                        update={"report": row.report.report.model_copy(update={"scores": ()})}
                    )
                }
            )
        else:
            row = row.model_copy(
                update={
                    "timing": row.timing.model_copy(
                        update={
                            "execution_seconds": 0.0,
                            "setup_seconds": 0.0,
                            "cleanup_seconds": 0.0,
                        }
                    )
                }
            )
        batch = candidate.batch.model_copy(update={"rows": (row, *candidate.batch.rows[1:])})
        candidate = replace(
            candidate,
            batch=batch,
            # Keep the independently sealed batch pin. An altered duration cannot
            # be made trusted by re-sealing it inside a tamper test. Real receipt
            # UTC spans can round to zero on Windows and are not a minimum timer.
            manifest=candidate.manifest,
        )
    with pytest.raises(ValueError):
        assemble_study(p, protocol, cases, loaded, baseline, candidate, required_case_ids=required)


def test_projection_rejects_paired_condition_changes_even_with_updated_baseline_seals(binding):
    p, protocol, expected, loaded, baseline, candidate, required = binding
    first = baseline.batch.schedule.tasks[0]
    altered = first.model_copy(update={"context": first.context.model_copy(update={"seed": 9876})})
    schedule = baseline.batch.schedule.model_copy(
        update={"tasks": (altered, *baseline.batch.schedule.tasks[1:])}
    )
    rows = tuple(
        row.model_copy(update={"task": altered}) if row.task.key == first.key else row
        for row in baseline.batch.rows
    )
    batch = baseline.batch.model_copy(update={"schedule": schedule, "rows": rows})
    baseline = replace(
        baseline,
        batch=batch,
        manifest=baseline.manifest.model_copy(update={"batch_sha256": pin(batch)}),
    )
    protocol = protocol.model_copy(update={"baseline_sha256": pin(baseline.manifest)})
    with pytest.raises(ValueError, match="trial conditions differ"):
        assemble_study(
            p, protocol, expected.cases, loaded, baseline, candidate, required_case_ids=required
        )


@pytest.mark.parametrize("change", ["profile", "split", "population"])
def test_olist_projection_preserves_original_partition_before_reading_evidence(
    tmp_path, monkeypatch, change
):
    from agent_harness.evaluation_standards import StandardCase, StandardProfile, StandardProtocol
    from olist_h10_fixtures import population
    from olist_support import h10_study
    from olist_support.field_evaluation import FIELDS

    label, loaded = population()
    profile = StandardProfile(
        version="invented",
        agent="olist",
        required_fields=FIELDS,
        required_holdout_slices=("eligible_refund",),
    )
    protocol = StandardProtocol(
        version="invented",
        profile_sha256=pin(profile),
        dataset_sha256=loaded.pin.sha256,
        scorer_sha256="a" * 64,
        baseline_sha256="b" * 64,
        frozen_at=datetime(2025, 1, 1, tzinfo=UTC),
        trials_per_case=3,
    )
    cases = (
        StandardCase(
            case_id=label.input.case_id,
            independence_keys=(label.group_id,),
            language_family="invented",
            input_text=label.input.request.message,
            split=label.split,
            source_kind=label.source_kind,
            slices=(),
            eligible_for_autonomy=True,
            required_review=False,
            critical=True,
        ),
    )
    if change == "profile":
        profile = profile.model_copy(update={"required_fields": ("intent",)})
    elif change == "split":
        cases = (
            cases[0].model_copy(
                update={"split": "regression" if label.split != "regression" else "development"}
            ),
        )
    else:
        cases = ()

    def forbidden(*args, **kwargs):
        raise AssertionError("invalid methodology must fail before reading observations")

    monkeypatch.setattr(h10_study, "read_olist_evidence", forbidden)
    with pytest.raises(ValueError):
        h10_study.assemble_olist_study(
            profile,
            protocol,
            cases,
            loaded,
            baseline_root=tmp_path,
            baseline_evidence_sha256="a" * 64,
            baseline_candidate_sha256="b" * 64,
            candidate_root=tmp_path,
            candidate_evidence_sha256="c" * 64,
            candidate_sha256="d" * 64,
            required_case_ids=loaded.manifest.case_ids,
        )
