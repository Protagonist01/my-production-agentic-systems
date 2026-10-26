"""Operator limits are explicit and invalid/output-conflicting drills do not touch SQL."""

import pytest
from olist_support.recovery_exercise import RecoveryObjective, exercise
from pydantic import ValidationError


@pytest.mark.parametrize("seconds", [0.0, -1.0, float("nan"), float("inf"), 3601.0])
def test_recovery_objective_requires_finite_positive_bounded_limit(seconds):
    with pytest.raises(ValidationError):
        RecoveryObjective(max_restore_seconds=seconds)


def test_existing_same_or_git_output_is_refused_before_database_access(tmp_path):
    existing = tmp_path / "existing.json"
    existing.write_text("private-existing-canary")
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    (checkout / ".git").mkdir()
    for archive, report in (
        (existing, tmp_path / "report.json"),
        (tmp_path / "same.json", tmp_path / "same.json"),
        (checkout / "archive.json", tmp_path / "report.json"),
    ):
        with pytest.raises(ValueError):
            exercise(
                None,
                None,
                "unused",
                code_revision="invented",
                environment_lock="a" * 64,
                archive_path=archive,
                report_path=report,
                objective=RecoveryObjective(max_restore_seconds=60.0),
                bootstrap=lambda *_: None,
            )
    assert existing.read_text() == "private-existing-canary"
