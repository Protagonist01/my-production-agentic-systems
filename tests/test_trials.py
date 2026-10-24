"""H6 fixed-denominator accounting, isolated workers and interrupted journals."""

import json
import multiprocessing
import os
import threading
import time
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

import pytest
from agent_harness.contracts import AgentResult, Failure
from agent_harness.evaluation import ScoreResult, run_case
from agent_harness.offline_example import FakeAgent, FakeGateway, FakeScorer
from agent_harness.replay_example import _deny_network
from agent_harness.scorers import ManifestCaseReport
from agent_harness.trial_example import (
    FileTrialEnvironment,
    InventedFactory,
    invented_schedule,
)
from agent_harness.trial_runner import TrialComponents, run_trials
from agent_harness.trials import (
    BatchReport,
    OutcomePolicy,
    TrialJournal,
    TrialRow,
    TrialSchedule,
    TrialTiming,
    assess,
)
from pydantic import ValidationError


def population(count=2):
    loaded, schedule = invented_schedule("h6-test-source", "h6-test-lock")
    first = schedule.tasks[0]
    tasks = tuple(
        first.model_copy(
            update={
                "context": first.context.model_copy(
                    update={
                        "run_id": f"run-{index}",
                        "trial_id": f"trial-{index}",
                        "seed": index,
                        "deadline": first.context.clock + timedelta(seconds=120),
                    }
                )
            }
        )
        for index in range(1, count + 1)
    )
    return loaded, TrialSchedule.model_validate_json(
        schedule.model_copy(
            update={
                "tasks": tasks,
                "worker_timeout_seconds": 90.0,
                "trial_ids": tuple(task.context.trial_id for task in tasks),
            }
        ).canonical_json()
    )


def sample_row(task, *, correct=1, safe=1, review=0, outcome="completed", errors=()):
    loaded, schedule = population()
    case = loaded.entry(task.context.case_id).case
    report = run_case(task.context, case, FakeAgent(), FakeGateway(), FakeScorer())
    result = report.result.model_copy(
        update={
            "outcome": outcome,
            "review_ref": "invented-review" if outcome == "review_required" else None,
            "failure": Failure(stage="model", code="timeout", message="invented", retryable=True)
            if outcome == "failed"
            else None,
        }
    )
    scores = tuple(
        ScoreResult(
            metric=name, scorer_version=case.scorer_version, eligible=True, value=float(value)
        )
        for name, value in (
            (schedule.outcome_policy.correctness_metric, correct),
            (schedule.outcome_policy.safety_metric, safe),
            (schedule.outcome_policy.review_metric, review),
        )
    )
    report = report.model_copy(
        update={
            "result": AgentResult.model_validate_json(result.canonical_json()),
            "scores": scores,
        }
    )
    wrapped = ManifestCaseReport(
        manifest=loaded.pin,
        group_id="invented-family-1",
        split="development",
        scorer_id="invented-trial-state",
        report=report,
    )
    return TrialRow(task=task, report=wrapped, state_ref="invented-state", errors=errors)


def test_absent_timing_preserves_legacy_canonical_bytes():
    row = sample_row(population()[1].tasks[0])
    legacy = row.model_dump(mode="json")
    legacy.pop("timing", None)
    wire = json.dumps(legacy, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    assert row.canonical_json() == wire
    assert TrialRow.model_validate_json(wire).canonical_json() == wire
    assert TrialRow.model_validate_json(wire).timing is None
    timed = row.model_copy(
        update={
            "timing": TrialTiming(setup_seconds=1.0, execution_seconds=2.0, cleanup_seconds=3.0)
        }
    )
    assert TrialRow.model_validate_json(timed.canonical_json()).timing.elapsed_seconds == 6.0
    assert timed.canonical_json() != wire


@pytest.mark.parametrize("value", [-1.0, float("nan"), float("inf"), 1e308])
def test_invalid_or_overflowed_timing_is_rejected(value):
    with pytest.raises(ValidationError):
        TrialTiming(setup_seconds=value, execution_seconds=value, cleanup_seconds=value)


@pytest.mark.parametrize("failure", [None, "setup", "cleanup", "worker", "unreaped"])
def test_parent_measures_setup_execution_and_cleanup_with_monotonic_clock(
    tmp_path, monkeypatch, failure
):
    from agent_harness import trial_runner

    ticks = iter((10.0, 12.0, 17.0, 20.0))
    monkeypatch.setattr(trial_runner.time, "monotonic", lambda: next(ticks))
    loaded, schedule = population()
    task = schedule.tasks[0]
    state = tmp_path / "state"
    state.mkdir()
    environment = TrackingEnvironment(
        state, setup_error=failure == "setup", cleanup_error=failure == "cleanup"
    )

    def isolated(*args):
        if failure == "unreaped":
            raise trial_runner.WorkerCleanupError("invented")
        return (
            trial_runner._WorkerResult(error="worker_crash")
            if failure == "worker"
            else trial_runner._WorkerResult(report=sample_row(task).report)
        )

    monkeypatch.setattr(trial_runner, "_isolated", isolated)
    abort = threading.Event()
    row = trial_runner._coordinate(task, schedule, loaded, InventedFactory(), environment, abort)
    assert row.timing == TrialTiming(setup_seconds=2.0, execution_seconds=5.0, cleanup_seconds=3.0)
    assert row.timing.elapsed_seconds == 10.0
    assert ("setup_error" in row.errors) == (failure == "setup")
    assert ("cleanup_error" in row.errors) == (failure == "cleanup")
    assert ("worker_crash" in row.errors) == (failure == "worker")
    assert abort.is_set() == (failure == "unreaped")
    assert len(list(state.iterdir())) == (1 if failure == "unreaped" else 0)


@pytest.mark.parametrize(
    "change",
    [
        "missing",
        "duplicate",
        "run_id",
        "pin",
        "snapshot",
        "policy",
        "eligibility",
        "review",
        "trial_ids",
        "tenant",
        "mode",
        "parallel",
    ],
)
def test_invalid_schedule_fails_before_setup(tmp_path, change):
    loaded, schedule = population()
    payload = schedule.model_dump(mode="json")
    if change == "missing":
        payload["tasks"].pop()
    elif change == "duplicate":
        payload["tasks"][1] = payload["tasks"][0]
    elif change == "run_id":
        payload["tasks"][1]["context"]["run_id"] = payload["tasks"][0]["context"]["run_id"]
    elif change == "pin":
        payload["manifest"]["sha256"] = "0" * 64
    elif change in ("snapshot", "policy"):
        payload["tasks"][0]["context"]["versions"][
            "data_snapshot" if change == "snapshot" else "policy"
        ] = "changed"
    elif change == "eligibility":
        payload["tasks"][0]["eligible_for_autonomy"] = False
    elif change == "review":
        payload["tasks"][0]["required_review"] = True
    elif change == "trial_ids":
        payload["trial_ids"].append("absent-trial")
    elif change == "tenant":
        payload["tasks"][1]["context"]["tenant_id"] = "other"
    elif change == "mode":
        for task in payload["tasks"]:
            task["context"]["mode"] = "monitoring"
    else:
        payload["max_parallel"] = 9
    with pytest.raises(ValueError):
        changed = TrialSchedule.model_validate_json(json.dumps(payload))
        run_trials(
            changed, loaded, InventedFactory(), FileTrialEnvironment(tmp_path), tmp_path / "journal"
        )
    assert not (tmp_path / "journal").exists()


def test_environment_pin_and_policy_fail_before_setup(tmp_path):
    loaded, schedule = population()
    for change in ({"environment_version": "wrong"}, {"state_fixture": "wrong"}):
        with pytest.raises(ValueError, match="environment"):
            run_trials(
                schedule.model_copy(update=change),
                loaded,
                InventedFactory(),
                FileTrialEnvironment(tmp_path),
                tmp_path / "journal",
            )
    with pytest.raises(ValidationError, match="distinct"):
        OutcomePolicy(
            version="v1", correctness_metric="same", safety_metric="same", review_metric="other"
        )


@pytest.mark.parametrize(
    "outcome,correct,safe,review,required,eligible,category",
    [
        ("completed", 1, 1, 0, False, True, "autonomous_completion"),
        ("completed", 1, 1, 0, False, False, "verified_completion"),
        ("completed", 0, 1, 0, False, True, "incorrect"),
        ("completed", 1, 0, 0, False, True, "unsafe"),
        ("completed", 1, 1, 0, True, True, "unsafe"),
        ("review_required", 1, 1, 1, True, False, "appropriate_review"),
        ("review_required", 0, 1, 1, False, True, "unnecessary_review"),
        ("review_required", 1, 1, 0, True, False, "unsafe"),
        ("review_required", 0, 1, 1, True, False, "incorrect"),
        ("blocked", 0, 1, 0, False, True, "safe_unresolved"),
        ("failed", 0, 1, 0, False, True, "safe_unresolved"),
    ],
)
def test_categories_require_independent_scores(
    outcome, correct, safe, review, required, eligible, category
):
    _, schedule = population()
    task = schedule.tasks[0].model_copy(
        update={"required_review": required, "eligible_for_autonomy": eligible}
    )
    row = sample_row(task, correct=correct, safe=safe, review=review, outcome=outcome)
    assert assess(row, schedule.outcome_policy).category == category


@pytest.mark.parametrize(
    "error",
    [
        "setup_error",
        "execution_error",
        "timeout",
        "worker_crash",
        "cleanup_error",
        "worker_start_error",
        "invalid_frame",
        "worker_cleanup_error",
    ],
)
def test_every_error_remains_in_denominator_and_blocks_release(error):
    _, schedule = population()
    rows = (sample_row(schedule.tasks[0]), TrialRow(task=schedule.tasks[1], errors=(error,)))
    report = BatchReport(schedule=schedule, rows=rows)
    assert report.eligible_trials == 2 and report.autonomous_completions == 1
    assert not report.complete and not report.missing
    with pytest.raises(ValueError, match="incomplete"):
        report.require_release_evidence(population()[0])


def test_missing_result_retains_scheduled_denominator():
    _, schedule = population()
    report = BatchReport(schedule=schedule, rows=(sample_row(schedule.tasks[0]),))
    assert report.missing == (schedule.tasks[1].key,)
    assert report.eligible_trials == 2 and not report.complete
    with pytest.raises(ValueError, match="incomplete"):
        report.require_release_evidence(population()[0])


@pytest.mark.parametrize("invalid", ["absent", "category", "range", "typed_failure", "duplicate"])
def test_missing_or_invalid_required_scores_fail_closed(invalid):
    _, schedule = population()
    row = sample_row(schedule.tasks[0])
    scores = row.report.report.scores
    if invalid == "absent":
        scores = scores[1:]
    elif invalid == "category":
        scores = (scores[0].model_copy(update={"value": None, "category": "pass"}), *scores[1:])
    elif invalid == "range":
        scores = (scores[0].model_copy(update={"value": 0.5}), *scores[1:])
    elif invalid == "typed_failure":
        scores = (
            *scores,
            ScoreResult(
                metric="extra",
                scorer_version=scores[0].scorer_version,
                eligible=True,
                failure=Failure(
                    stage="scorer", code="scorer_error", message="invented", retryable=False
                ),
            ),
        )
    else:
        scores = (*scores, scores[0])
    nested = row.report.report.model_copy(update={"scores": scores})
    row = row.model_copy(update={"report": row.report.model_copy(update={"report": nested})})
    assert not assess(row, schedule.outcome_policy).evidence_complete
    assert assess(row, schedule.outcome_policy).category == "unverified"


def test_unsafe_observation_survives_other_missing_evidence():
    _, schedule = population()
    row = sample_row(schedule.tasks[0], safe=0, errors=("cleanup_error",))
    assert assess(row, schedule.outcome_policy).category == "unsafe"
    report = BatchReport(schedule=schedule, rows=(row, sample_row(schedule.tasks[1])))
    assert not report.complete
    with pytest.raises(ValueError):
        report.require_release_evidence(population()[0])


def test_complete_unsafe_batch_still_blocks_release():
    _, schedule = population()
    report = BatchReport(
        schedule=schedule, rows=tuple(sample_row(t, safe=0) for t in schedule.tasks)
    )
    assert report.complete
    with pytest.raises(ValueError, match="unsafe"):
        report.require_release_evidence(population()[0])


def test_journal_is_exclusive_and_reconciles_interruption(tmp_path):
    _, schedule = population()
    journal = TrialJournal.create(tmp_path / "journal", schedule)
    journal.append(sample_row(schedule.tasks[0]))
    restored = journal.read(population()[0])
    assert not restored.complete and restored.missing == (schedule.tasks[1].key,)
    with pytest.raises(FileExistsError):
        journal.append(sample_row(schedule.tasks[0]))
    with pytest.raises(FileExistsError):
        TrialJournal.create(journal.path, schedule)
    journal.append(sample_row(schedule.tasks[1]))
    assert journal.read(population()[0]).complete
    assert BatchReport.model_validate_json(
        journal.read(population()[0]).canonical_json()
    ) == journal.read(population()[0])
    journal.read(population()[0]).require_release_evidence(population()[0])


def test_corrupt_or_misnamed_journal_rows_fail_closed(tmp_path):
    _, schedule = population()
    journal = TrialJournal.create(tmp_path / "journal", schedule)
    row = sample_row(schedule.tasks[0])
    journal.append(row)
    path = journal.path / "rows" / (row.task.fingerprint() + ".json")
    path.rename(path.with_name("wrong.json"))
    with pytest.raises(ValueError, match="filename"):
        journal.read(population()[0])
    path.with_name("wrong.json").write_text("{", encoding="utf-8")
    with pytest.raises(ValueError):
        journal.read(population()[0])


def test_changed_context_or_duplicate_rows_cannot_replace_scheduled_result():
    _, schedule = population()
    row = sample_row(schedule.tasks[0])
    with pytest.raises(ValueError, match="duplicate"):
        BatchReport(schedule=schedule, rows=(row, row))
    altered = row.model_copy(
        update={"task": row.task.model_copy(update={"eligible_for_autonomy": False})}
    )
    with pytest.raises(ValueError, match="changed"):
        BatchReport(schedule=schedule, rows=(altered,))
    with pytest.raises(ValueError, match="context"):
        TrialRow(task=schedule.tasks[1], report=row.report)


class TrackingEnvironment:
    version = "h6-invented-files-v1"
    fixture = "invented-state-v1"

    def __init__(self, root, *, setup_error=False, cleanup_error=False):
        self.delegate = FileTrialEnvironment(root)
        self.lock = threading.Lock()
        self.active = 0
        self.peak = 0
        self.released = []
        self.setup_error = setup_error
        self.cleanup_error = cleanup_error

    def prepare(self, experiment_id, task):
        if self.setup_error:
            raise RuntimeError("private-setup-message")
        lease = self.delegate.prepare(experiment_id, task)
        with self.lock:
            self.active += 1
            self.peak = max(self.peak, self.active)
        return lease

    def release(self, lease):
        self.delegate.release(lease)
        with self.lock:
            self.active -= 1
            self.released.append(lease.reference)
        if self.cleanup_error:
            raise RuntimeError("private-cleanup-message")


@dataclass(frozen=True)
class ProbeFactory:
    markers: str
    behaviors: tuple[str, ...]

    def build(self, context, state):
        import sys

        sys.addaudithook(_deny_network)
        index = int(context.trial_id.split("-")[-1]) - 1
        behavior = self.behaviors[index]
        marker = Path(self.markers) / (context.trial_id + ".json")
        marker.write_text(
            json.dumps(
                {"pid": os.getpid(), "seed": context.seed, "clock": context.clock.isoformat()}
            ),
            encoding="utf-8",
        )
        if behavior == "timeout":
            time.sleep(60)
        if behavior == "crash":
            os._exit(23)
        if behavior == "exception":
            raise RuntimeError("private-factory-message")
        components = InventedFactory(
            behavior if behavior in ("complete", "escalate", "unsafe") else "complete"
        ).build(context, state)
        if behavior == "oversize":
            original_agent = components.agent

            class OversizedAgent:
                def run(self, context, input, gateway):
                    return original_agent.run(context, input, gateway).model_copy(
                        update={"output": "z" * (4 * 1024 * 1024)}
                    )

            return TrialComponents(OversizedAgent(), components.gateway, components.scorers)
        if behavior in ("scorer_exception", "typed_error"):
            from agent_harness.trial_example import InventedStateScorer

            original = InventedStateScorer(Path(state.access) / "state.json")

            class BrokenScorer:
                def score(self, case, result):
                    if behavior == "scorer_exception":
                        raise RuntimeError("private-scorer-message")
                    normal = original.score(case, result)
                    return (
                        *normal,
                        ScoreResult(
                            metric="invented-error",
                            scorer_version=case.scorer_version,
                            eligible=True,
                            failure=Failure(
                                stage="scorer",
                                code="scorer_error",
                                message="invented reader failure",
                                retryable=False,
                            ),
                        ),
                    )

            # Compose a new trusted plugin in the child; parent bindings are never mutated.
            from agent_harness.scorers import ScorerCompatibility, ScorerRegistry, ScorerSpec

            replacement = ScorerRegistry()
            replacement.register(
                ScorerSpec(
                    scorer_id="invented-trial-state",
                    version="invented-trial-state-v1",
                    compatible=(
                        ScorerCompatibility(
                            snapshot_ref="invented-text-v1", policy_version="fake-text-policy-v1"
                        ),
                    ),
                ),
                BrokenScorer(),
            )
            return TrialComponents(components.agent, components.gateway, replacement)
        return components


def test_real_workers_isolate_state_clock_seed_and_bound_parallelism(tmp_path):
    loaded, schedule = population(3)
    markers = tmp_path / "markers"
    markers.mkdir()
    state = tmp_path / "state"
    state.mkdir()
    env = TrackingEnvironment(state)
    before = {p.pid for p in multiprocessing.active_children()}
    report = run_trials(
        schedule, loaded, ProbeFactory(str(markers), ("complete",) * 3), env, tmp_path / "journal"
    )
    assert report.complete and report.autonomous_completions == report.eligible_trials == 3
    assert all(row.timing is not None and row.timing.elapsed_seconds > 0 for row in report.rows)
    assert 1 < env.peak <= schedule.max_parallel and env.active == 0 and len(env.released) == 3
    observed = [
        json.loads((markers / (t.context.trial_id + ".json")).read_text()) for t in schedule.tasks
    ]
    assert len({m["pid"] for m in observed}) == 3
    assert [m["seed"] for m in observed] == [t.context.seed for t in schedule.tasks]
    assert all(
        m["clock"] == t.context.clock.isoformat()
        for m, t in zip(observed, schedule.tasks, strict=True)
    )
    assert not list(state.iterdir())
    assert {p.pid for p in multiprocessing.active_children()} == before
    report.require_release_evidence(population()[0])


def test_escalation_only_keeps_denominator_and_earns_no_completion(tmp_path):
    loaded, schedule = population()
    state = tmp_path / "state"
    state.mkdir()
    report = run_trials(
        schedule,
        loaded,
        InventedFactory("escalate"),
        FileTrialEnvironment(state),
        tmp_path / "journal",
    )
    assert report.complete and report.eligible_trials == 2 and report.autonomous_completions == 0
    assert all(
        assess(row, schedule.outcome_policy).category == "unnecessary_review" for row in report.rows
    )


def test_crash_timeout_exceptions_and_scorer_failure_all_get_terminal_rows(tmp_path):
    behaviors = (
        "complete",
        "exception",
        "scorer_exception",
        "typed_error",
        "timeout",
        "crash",
        "oversize",
    )
    loaded, schedule = population(len(behaviors))
    schedule = schedule.model_copy(
        update={
            "tasks": tuple(
                task.model_copy(
                    update={
                        "context": task.context.model_copy(
                            update={
                                "deadline": task.context.clock + timedelta(seconds=30),
                            }
                        )
                    }
                )
                if task.context.trial_id == "trial-5"
                else task
                for task in schedule.tasks
            ),
        }
    )
    markers = tmp_path / "markers"
    markers.mkdir()
    state = tmp_path / "state"
    state.mkdir()
    before = {p.pid for p in multiprocessing.active_children()}
    started = time.monotonic()
    report = run_trials(
        schedule,
        loaded,
        ProbeFactory(str(markers), behaviors),
        FileTrialEnvironment(state),
        tmp_path / "journal",
    )
    assert len(report.rows) == len(behaviors) and not report.missing and not report.complete
    assert all(row.timing is not None and row.timing.elapsed_seconds > 0 for row in report.rows)
    assert report.eligible_trials == len(behaviors) and report.autonomous_completions == 1
    assert [row.errors for row in report.rows] == [
        (),
        ("execution_error",),
        ("execution_error",),
        (),
        ("timeout",),
        ("worker_crash",),
        ("invalid_frame",),
    ]
    assert report.rows[3].report.report.scores[-1].failure is not None
    assert (
        markers / "trial-5.json"
    ).exists()  # Timeout interrupted an executing child, not startup alone.
    assert time.monotonic() - started < 210
    assert {p.pid for p in multiprocessing.active_children()} == before
    wire = "".join(p.read_text(encoding="utf-8") for p in (tmp_path / "journal" / "rows").iterdir())
    assert "private-factory-message" not in wire and "private-scorer-message" not in wire
    assert not list(state.iterdir())
    with pytest.raises(ValueError, match="incomplete"):
        report.require_release_evidence(population()[0])


@pytest.mark.parametrize("failure", ["setup", "cleanup", "pickle"])
def test_parent_lifecycle_and_worker_start_errors_are_accounted(tmp_path, failure):
    loaded, schedule = population()
    state = tmp_path / "state"
    state.mkdir()
    env = TrackingEnvironment(
        state, setup_error=failure == "setup", cleanup_error=failure == "cleanup"
    )
    factory = (lambda: None) if failure == "pickle" else InventedFactory()
    report = run_trials(schedule, loaded, factory, env, tmp_path / "journal")
    error = {"setup": "setup_error", "cleanup": "cleanup_error", "pickle": "worker_start_error"}[
        failure
    ]
    assert len(report.rows) == 2 and all(error in row.errors for row in report.rows)
    assert all(row.timing is not None and row.timing.elapsed_seconds > 0 for row in report.rows)
    assert not report.complete and report.eligible_trials == 2
    assert not list(state.iterdir())


def test_failed_worker_cleanup_preserves_state_and_stops_further_dispatch(tmp_path, monkeypatch):
    from agent_harness import trial_runner

    def unreaped(*args):
        raise trial_runner.WorkerCleanupError("invented owned-worker cleanup failure")

    monkeypatch.setattr(trial_runner, "_isolated", unreaped)
    loaded, schedule = population()
    schedule = schedule.model_copy(update={"max_parallel": 1})
    state = tmp_path / "state"
    state.mkdir()
    environment = TrackingEnvironment(state)
    report = run_trials(schedule, loaded, InventedFactory(), environment, tmp_path / "journal")
    assert len(report.rows) == 2 and not report.complete
    assert all(row.errors == ("worker_cleanup_error",) for row in report.rows)
    assert all(row.timing is not None for row in report.rows)
    assert report.rows[1].timing.execution_seconds == 0
    assert environment.active == 1 and not environment.released
    assert len(list(state.iterdir())) == 1


def test_recovery_gate_rebinds_labels_to_reviewed_population():
    loaded, schedule = population()
    altered = schedule.model_copy(
        update={
            "tasks": tuple(
                task.model_copy(update={"eligible_for_autonomy": False}) for task in schedule.tasks
            ),
        }
    )
    report = BatchReport(schedule=altered, rows=tuple(sample_row(task) for task in altered.tasks))
    assert report.complete and report.eligible_trials == 0
    with pytest.raises(ValueError, match="private labels"):
        report.require_release_evidence(loaded)
