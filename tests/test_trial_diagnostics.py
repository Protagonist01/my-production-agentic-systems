"""Private cause classification never stores arbitrary exception strings or SQL details."""

import json
import threading

import psycopg
import pytest
from agent_harness import trial_runner
from agent_harness.trial_example import InventedFactory
from agent_harness.trial_runner import StateLease, WorkerCleanupError, _exception_diagnostic
from agent_harness.trials import TrialDiagnostic, TrialRow
from pydantic import ValidationError
from test_trials import population, sample_row

SECRET = "invented-private-password-and-customer-source-text"


@pytest.mark.parametrize(
    "error,category,state",
    [
        (psycopg.errors.UniqueViolation(SECRET), "database", "23505"),
        (psycopg.OperationalError(SECRET), "database", None),
        (TimeoutError(SECRET), "timeout", None),
        (ConnectionError(SECRET), "connection", None),
        (PermissionError(SECRET), "permission", None),
        (OSError(SECRET), "os", None),
        (ValueError(SECRET), "validation", None),
        (RuntimeError(SECRET), "runtime", None),
        (Exception(SECRET), "other", None),
    ],
)
def test_fixed_categories_and_known_database_code_omit_exception_text(error, category, state):
    diagnostic = _exception_diagnostic("setup_error", error)
    assert diagnostic.exception_category == category and diagnostic.sqlstate == state
    assert SECRET not in diagnostic.canonical_json()


def test_unknown_database_code_and_throwing_stringifier_cannot_export_text():
    class PrivateDatabaseError(psycopg.Error):
        sqlstate = SECRET

        def __str__(self):
            raise AssertionError("must never stringify an exception")

    row = _exception_diagnostic("setup_error", PrivateDatabaseError())
    assert row.exception_category == "database" and row.sqlstate is None
    assert SECRET not in row.canonical_json()


class Environment:
    def __init__(self, failure=None):
        self.failure = failure
        self.prepared = self.released = 0

    def prepare(self, experiment_id, task):
        self.prepared += 1
        if self.failure == "setup":
            raise psycopg.errors.DiskFull(SECRET)
        return StateLease("invented-state", "invented-fixture", object())

    def release(self, lease):
        self.released += 1
        if self.failure == "cleanup":
            raise PermissionError(SECRET)


@pytest.mark.parametrize("failure", ["setup", "execution", "cleanup", "unreaped"])
def test_actual_parent_paths_keep_error_code_and_mask_cause(monkeypatch, failure):
    loaded, schedule = population()
    environment, abort = Environment(failure), threading.Event()
    environment_fixture = "invented-fixture"
    schedule = schedule.model_copy(update={"state_fixture": environment_fixture})

    def isolated(*args):
        if failure == "execution":
            raise ValueError(SECRET)
        if failure == "unreaped":
            raise WorkerCleanupError(SECRET)
        return trial_runner._WorkerResult(report=sample_row(schedule.tasks[0]).report)

    monkeypatch.setattr(trial_runner, "_isolated", isolated)
    row = trial_runner._coordinate(
        schedule.tasks[0], schedule, loaded, InventedFactory(), environment, abort
    )
    expected = {
        "setup": ("setup_error", "database", "53100"),
        "execution": ("execution_error", "validation", None),
        "cleanup": ("cleanup_error", "permission", None),
        "unreaped": ("worker_cleanup_error", "runtime", None),
    }[failure]
    assert row.errors == (expected[0],)
    assert len(row.diagnostics) == 1
    d = row.diagnostics[0]
    assert (d.code, d.exception_category, d.sqlstate) == expected
    assert d.origin == "exception" and SECRET not in row.canonical_json()
    assert TrialRow.model_validate_json(row.canonical_json()) == row
    assert environment.released == (0 if failure in ("setup", "unreaped") else 1)
    assert abort.is_set() == (failure == "unreaped")


def test_aborted_trial_is_distinct_from_a_physical_worker_cleanup_failure(monkeypatch):
    loaded, schedule = population()
    environment, abort = Environment(), threading.Event()
    abort.set()
    row = trial_runner._coordinate(
        schedule.tasks[0], schedule, loaded, InventedFactory(), environment, abort
    )
    assert environment.prepared == environment.released == 0
    assert row.errors == ("worker_cleanup_error",) and row.report is None
    assert row.diagnostics == (
        TrialDiagnostic(code="worker_cleanup_error", origin="prior_trial_abort"),
    )


def test_identity_mismatch_has_no_invented_exception(monkeypatch):
    loaded, schedule = population()
    environment = Environment()
    schedule = schedule.model_copy(update={"state_fixture": "invented-fixture"})
    report = sample_row(schedule.tasks[0]).report
    report = report.model_copy(
        update={"manifest": report.manifest.model_copy(update={"version": "other"})}
    )
    monkeypatch.setattr(
        trial_runner, "_isolated", lambda *args: trial_runner._WorkerResult(report=report)
    )
    row = trial_runner._coordinate(
        schedule.tasks[0], schedule, loaded, InventedFactory(), environment, threading.Event()
    )
    assert row.report is None and row.errors == ("invalid_frame",)
    assert row.diagnostics == (TrialDiagnostic(code="invalid_frame", origin="identity_mismatch"),)
    assert environment.released == 1


def test_abort_after_setup_still_releases_the_prepared_lease(monkeypatch):
    loaded, schedule = population()
    schedule = schedule.model_copy(update={"state_fixture": "invented-fixture"})
    abort = threading.Event()

    class AbortingEnvironment(Environment):
        def prepare(self, experiment_id, task):
            lease = super().prepare(experiment_id, task)
            abort.set()
            return lease

    def forbidden(*args):
        raise AssertionError("aborted work must not enter a worker")

    monkeypatch.setattr(trial_runner, "_isolated", forbidden)
    environment = AbortingEnvironment()
    row = trial_runner._coordinate(
        schedule.tasks[0], schedule, loaded, InventedFactory(), environment, abort
    )
    assert environment.prepared == environment.released == 1
    assert row.errors == ("worker_cleanup_error",)
    assert row.diagnostics[0].origin == "prior_trial_abort"


def test_legacy_row_without_diagnostics_preserves_exact_canonical_bytes():
    row = sample_row(population()[1].tasks[0])
    legacy = row.model_dump(mode="json")
    legacy.pop("diagnostics", None)
    raw = json.dumps(legacy, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    assert "diagnostics" not in row.canonical_json()
    assert TrialRow.model_validate_json(raw).canonical_json() == raw


@pytest.mark.parametrize(
    "change",
    [
        {"exception_category": None},
        {"exception_category": "private-driver-name"},
        {"sqlstate": SECRET},
        {"exception_category": "runtime", "sqlstate": "23505"},
        {"origin": "prior_trial_abort"},
        {"origin": "identity_mismatch", "exception_category": None},
    ],
)
def test_malformed_diagnostics_are_rejected(change):
    values = dict(code="setup_error", origin="exception", exception_category="database")
    with pytest.raises(ValidationError):
        TrialDiagnostic.model_validate(dict(values, **change))


def test_diagnostic_cannot_attach_to_a_successful_row():
    row = sample_row(population()[1].tasks[0])
    bad = row.model_copy(
        update={"diagnostics": (_exception_diagnostic("setup_error", ValueError(SECRET)),)}
    )
    with pytest.raises(ValidationError, match="actual row error"):
        TrialRow.model_validate_json(bad.canonical_json())
