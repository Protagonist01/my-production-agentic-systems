"""Invented reference-relative diagnostics; no real judge or clinical qualification."""

from datetime import UTC, datetime, timedelta

import pytest
from agent_harness.evaluator_qualification import (
    QualificationCase,
    QualificationDataset,
    QualificationObservation,
    QualificationProtocol,
    QualificationStudy,
    qualification_report,
)
from agent_harness.release_contracts import pin, sha256
from pydantic import ValidationError

NOW = datetime(2026, 10, 26, tzinfo=UTC)


def sample():
    cases = tuple(
        QualificationCase(
            case_id=f"invented-{i}",
            input_sha256=sha256(str(i).encode()),
            independence_keys=(f"source-{i}",),
            split="calibration" if i < 2 else "holdout",
            slices=("mixed",),
            expected_accept=i % 2 == 0,
            reference_sha256="a" * 64,
            reference_kind="independent_program",
            applicability_ref="invented-only-applicability",
            exposure="withheld_from_tuning",
            critical_reject=i == 3,
            invariant_failed=i == 3,
        )
        for i in range(6)
    )
    data = QualificationDataset(
        version="invented-not-a-real-reference",
        agent="invented",
        field="invented",
        frozen_at=NOW,
        cases=cases,
    )
    protocol = QualificationProtocol(
        dataset_sha256=pin(data),
        evaluator_sha256="b" * 64,
        frozen_at=NOW,
        trial_ids=("t1", "t2"),
        required_slices=("mixed",),
        min_holdout_groups=4,
        min_groups_per_slice=4,
        min_groups_per_class=2,
        min_decision_coverage=1.0,
        min_scheduled_accuracy=1.0,
        max_false_accept_rate=0.0,
        max_false_reject_rate=0.0,
        max_group_error_upper_bound=1.0,
        reference_validation_ref="invented-not-a-review",
        sample_size_ref="invented-permissive-limit-for-logic-tests",
    )
    rows = tuple(
        QualificationObservation(
            case_id=c.case_id,
            trial_id=t,
            input_sha256=c.input_sha256,
            evaluator_sha256=protocol.evaluator_sha256,
            observed_at=NOW,
            decision="accept" if c.expected_accept else "reject",
        )
        for c in cases
        for t in protocol.trial_ids
    )
    study = QualificationStudy(
        protocol_sha256=pin(protocol), started_at=NOW, finished_at=NOW, rows=rows
    )
    return data, protocol, study


def report(data, protocol, study):
    return qualification_report(data, protocol, study, now=NOW)


def change_data(data, protocol, study, cases):
    data = data.model_copy(update={"cases": cases})
    protocol = protocol.model_copy(update={"dataset_sha256": pin(data)})
    study = study.model_copy(update={"protocol_sha256": pin(protocol)})
    return data, protocol, study


def test_perfect_invented_mechanism_pass_is_never_release_or_human_review():
    data, protocol, study = sample()
    result = report(data, protocol, study)
    assert result["criteria_met"] and not result["release_allowed"]
    assert not result["human_review_supplied"] and not result["unseen_model_data_claimed"]
    metrics = result["metrics"]["holdout"]
    assert metrics["scheduled"] == 8 and metrics["groups"] == 4
    assert metrics["true_accept"] == metrics["true_reject"] == 4
    assert result["calibration"]["scheduled"] == 4


def test_missing_failed_and_abstention_stay_in_denominators():
    data, protocol, study = sample()
    rows = list(study.rows)
    rows.pop()  # Missing final reject reference.
    rows[4] = rows[4].model_copy(update={"decision": "abstain"})
    rows[5] = rows[5].model_copy(update={"decision": None, "failure_code": "invalid_response"})
    result = report(data, protocol, study.model_copy(update={"rows": tuple(rows)}))
    m = result["metrics"]["holdout"]
    assert (m["scheduled"], m["missing"], m["failed"], m["abstained"]) == (8, 1, 1, 1)
    assert m["scheduled_accuracy"] == 5 / 8
    assert m["conditional_accuracy"] == 1.0
    assert m["failed_groups"] == 2 and not result["criteria_met"]


@pytest.mark.parametrize("decision", ["abstain", "accept", "reject"])
def test_always_one_decision_cannot_hide_bad_class_performance(decision):
    data, protocol, study = sample()
    changed = study.model_copy(
        update={"rows": tuple(r.model_copy(update={"decision": decision}) for r in study.rows)}
    )
    result = report(data, protocol, changed)
    assert not result["criteria_met"]
    assert result["metrics"]["holdout"]["scheduled"] == 8


def test_false_accept_false_reject_and_state_invariant_are_separate():
    data, protocol, study = sample()
    rows = tuple(
        r.model_copy(update={"decision": "reject" if r.decision == "accept" else "accept"})
        for r in study.rows
    )
    result = report(data, protocol, study.model_copy(update={"rows": rows}))
    m = result["metrics"]["holdout"]
    assert m["false_accept"] == m["false_reject"] == 4
    assert m["false_accept_rate"] == m["false_reject_rate"] == 1.0
    assert m["invariant_overridden"] == 2
    assert "holdout:critical_or_invariant_failure" in result["blockers"]


def test_repetitions_do_not_fix_tiny_group_uncertainty():
    data, protocol, study = sample()
    protocol = protocol.model_copy(update={"max_group_error_upper_bound": 0.05})
    study = study.model_copy(update={"protocol_sha256": pin(protocol)})
    result = report(data, protocol, study)
    assert "holdout:group_error_upper_bound" in result["blockers"]
    assert "holdout:unacceptable_group_error_upper_bound" in result["blockers"]
    assert result["metrics"]["holdout"]["groups"] == 4


def test_connected_groups_merge_transitively_before_counting():
    data, protocol, study = sample()
    cases = list(data.cases)
    cases[2] = cases[2].model_copy(update={"independence_keys": ("A", "B")})
    cases[3] = cases[3].model_copy(update={"independence_keys": ("C", "D")})
    cases[4] = cases[4].model_copy(update={"independence_keys": ("B", "C")})
    result = report(*change_data(data, protocol, study, tuple(cases)))
    assert result["metrics"]["holdout"]["groups"] == 2
    assert not result["criteria_met"]


@pytest.mark.parametrize("kind", ["declared_key", "identical_input"])
def test_calibration_holdout_leakage_refuses(kind):
    data, protocol, study = sample()
    cases = list(data.cases)
    changes = (
        {"independence_keys": cases[0].independence_keys}
        if kind == "declared_key"
        else {"input_sha256": cases[0].input_sha256}
    )
    cases[2] = cases[2].model_copy(update=changes)
    data, protocol, study = change_data(data, protocol, study, tuple(cases))
    if kind == "identical_input":
        study = study.model_copy(
            update={
                "rows": tuple(
                    r.model_copy(update={"input_sha256": cases[2].input_sha256})
                    if r.case_id == cases[2].case_id
                    else r
                    for r in study.rows
                )
            }
        )
    with pytest.raises(ValueError, match="crosses splits"):
        report(data, protocol, study)


@pytest.mark.parametrize(
    "change,blocker",
    [
        ({"reference_kind": "ai_provisional"}, "holdout_reference_basis_unqualified"),
        ({"applicability_ref": None}, "holdout_reference_basis_unqualified"),
        ({"exposure": "unknown"}, "holdout_exposure_unknown"),
    ],
)
def test_unqualified_references_and_unknown_exposure_do_not_qualify(change, blocker):
    data, protocol, study = sample()
    cases = (*data.cases[:2], data.cases[2].model_copy(update=change), *data.cases[3:])
    assert blocker in report(*change_data(data, protocol, study, cases))["blockers"]


def test_missing_required_slice_and_class_do_not_become_perfect_metrics():
    data, protocol, study = sample()
    protocol = protocol.model_copy(update={"required_slices": ("absent",)})
    result = report(data, protocol, study.model_copy(update={"protocol_sha256": pin(protocol)}))
    assert result["metrics"]["slice:absent"]["false_accept_rate"] is None
    assert "slice:absent:unacceptable_groups" in result["blockers"]
    assert not result["criteria_met"]


def test_identity_schedule_and_time_tampering_refuses():
    data, protocol, study = sample()
    for change in (
        {"input_sha256": "c" * 64},
        {"evaluator_sha256": "c" * 64},
        {"trial_id": "unscheduled"},
        {"observed_at": NOW + timedelta(seconds=1)},
    ):
        with pytest.raises(ValueError):
            report(
                data,
                protocol,
                study.model_copy(
                    update={"rows": (study.rows[0].model_copy(update=change), *study.rows[1:])}
                ),
            )
    with pytest.raises(ValueError, match="duplicate"):
        report(data, protocol, study.model_copy(update={"rows": (*study.rows, study.rows[0])}))
    with pytest.raises(ValueError, match="pin"):
        report(data, protocol, study.model_copy(update={"protocol_sha256": "c" * 64}))
    with pytest.raises(ValueError, match="time order"):
        report(data, protocol, study.model_copy(update={"started_at": NOW - timedelta(seconds=1)}))


def test_conflicting_gold_and_invariant_labels_cannot_be_forged():
    data, protocol, study = sample()
    with pytest.raises(ValidationError, match="known invariant"):
        QualificationCase.model_validate_json(
            data.cases[3].model_copy(update={"expected_accept": True}).canonical_json()
        )
    bad = data.model_copy(
        update={
            "cases": (
                data.cases[0],
                data.cases[1].model_copy(update={"input_sha256": data.cases[0].input_sha256}),
            )
        }
    )
    with pytest.raises(ValidationError, match="conflicting"):
        QualificationDataset.model_validate_json(bad.canonical_json())
    with pytest.raises(ValidationError):
        QualificationObservation.model_validate_json(
            study.rows[0].model_copy(update={"failure_code": "failed"}).canonical_json()
        )


def test_calibration_is_separate_and_cannot_be_omitted():
    data, protocol, study = sample()
    study = study.model_copy(update={"rows": study.rows[4:]})
    result = report(data, protocol, study)
    assert result["metrics"]["holdout"]["scheduled_accuracy"] == 1.0
    assert "calibration_incomplete_or_one_class" in result["blockers"]


def test_class_specific_abstention_cannot_hide_behind_global_coverage():
    data, protocol, study = sample()
    protocol = protocol.model_copy(
        update={"min_decision_coverage": 0.4, "min_scheduled_accuracy": 0.4}
    )
    rejected = {c.case_id for c in data.cases if c.split == "holdout" and not c.expected_accept}
    study = study.model_copy(
        update={
            "protocol_sha256": pin(protocol),
            "rows": tuple(
                r.model_copy(update={"decision": "abstain"}) if r.case_id in rejected else r
                for r in study.rows
            ),
        }
    )
    result = report(data, protocol, study)
    assert result["metrics"]["holdout"]["decision_coverage"] == 0.5
    assert "holdout:decision_coverage" not in result["blockers"]
    assert "holdout:unacceptable_decision_coverage" in result["blockers"]


def test_cli_verifies_pins_and_never_overwrites_reports(tmp_path, capsys):
    import json

    from agent_harness.evaluator_qualification_cli import main

    data, protocol, study = sample()
    args = []
    for name, obj in (("dataset", data), ("protocol", protocol), ("study", study)):
        path = tmp_path / (name + ".json")
        path.write_text(obj.canonical_json(), encoding="utf-8")
        args += ["--" + name, str(path), "--" + name + "-sha256", pin(obj)]
    output = tmp_path / "report.json"
    args += ["--output", str(output)]
    assert main(args) == 0
    original = output.read_bytes()
    result = json.loads(original)
    assert not result["release_allowed"] and not result["human_review_supplied"]
    assert main(args) == 1 and output.read_bytes() == original
    args[3] = "0" * 64
    assert main(args) == 1
    assert "invented-" not in capsys.readouterr().err


def test_cli_retains_failed_criteria_and_rejects_duplicate_json_keys(tmp_path):
    import json

    from agent_harness.evaluator_qualification_cli import main

    data, protocol, study = sample()
    study = study.model_copy(update={"rows": ()})
    args = []
    for name, obj in (("dataset", data), ("protocol", protocol), ("study", study)):
        path = tmp_path / (name + ".json")
        path.write_text(obj.canonical_json(), encoding="utf-8")
        args += ["--" + name, str(path), "--" + name + "-sha256", pin(obj)]
    output = tmp_path / "failed.json"
    args += ["--output", str(output)]
    assert main(args) == 1
    result = json.loads(output.read_bytes())
    assert not result["criteria_met"] and result["metrics"]["holdout"]["missing"] == 8
    original = (tmp_path / "dataset.json").read_text()
    (tmp_path / "dataset.json").write_text('{"version":"duplicate",' + original[1:])
    assert main(args) == 1


def test_critical_failure_cannot_be_waived_by_loose_numeric_limits():
    data, protocol, study = sample()
    protocol = protocol.model_copy(
        update={
            "min_scheduled_accuracy": 0.0,
            "min_decision_coverage": 0.0,
            "max_false_accept_rate": 1.0,
            "max_false_reject_rate": 1.0,
        }
    )
    study = study.model_copy(
        update={
            "protocol_sha256": pin(protocol),
            "rows": tuple(
                r.model_copy(update={"decision": "accept"}) if r.case_id == "invented-3" else r
                for r in study.rows
            ),
        }
    )
    result = report(data, protocol, study)
    assert not result["criteria_met"]
    assert set(result["blockers"]) == {
        "holdout:critical_or_invariant_failure",
        "slice:mixed:critical_or_invariant_failure",
    }


def test_calibration_ai_labels_remain_unqualified_even_with_perfect_decisions():
    data, protocol, study = sample()
    cases = (data.cases[0].model_copy(update={"reference_kind": "ai_provisional"}), *data.cases[1:])
    result = report(*change_data(data, protocol, study, cases))
    assert "calibration_reference_basis_unqualified" in result["blockers"]


def test_public_reference_exposure_is_disclosed_without_claiming_unseen_model_data():
    data, protocol, study = sample()
    cases = tuple(c.model_copy(update={"exposure": "public_reference"}) for c in data.cases)
    result = report(*change_data(data, protocol, study, cases))
    assert result["criteria_met"] and not result["unseen_model_data_claimed"]
    assert result["reference_exposure_counts"] == {"public_reference": 4}
