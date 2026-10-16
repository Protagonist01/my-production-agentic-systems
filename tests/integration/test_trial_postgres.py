"""H6 real database reset, restricted worker access and timeout cleanup."""

import time
from dataclasses import dataclass
from datetime import timedelta

import pytest
from agent_harness.evaluation import ScoreResult
from agent_harness.offline_example import FakeAgent, FakeGateway
from agent_harness.scorers import ScorerCompatibility, ScorerRegistry, ScorerSpec
from agent_harness.trial_example import invented_schedule
from agent_harness.trial_postgres import PostgresTrialEnvironment, TrialDatabaseAccess
from agent_harness.trial_runner import TrialComponents, run_trials
from psycopg.types.json import Jsonb
from test_postgres_isolation import workspaces as workspaces


@dataclass
class DatabaseAgent:
    access: TrialDatabaseAccess
    hang: bool

    def run(self, context, input, gateway):
        with self.access.connect() as connection:
            assert connection.execute(
                "SELECT rolsuper,rolcreatedb,rolcreaterole FROM pg_roles WHERE rolname=current_user"
            ).fetchone() == (False, False, False)
            before = connection.execute(
                "SELECT payload FROM runtime.checkpoints WHERE checkpoint_key='invented-checkpoint'"
            ).fetchone()[0]
            assert before["step"] == "start"
            connection.execute(
                "UPDATE runtime.checkpoints SET payload=%s", (Jsonb({"step": "done"}),)
            )
        if self.hang:
            time.sleep(120)
        return FakeAgent().run(context, input, gateway)


@dataclass
class DatabaseScorer:
    access: TrialDatabaseAccess

    def score(self, case, result):
        with self.access.connect() as connection:
            actual = connection.execute(
                "SELECT payload FROM runtime.checkpoints WHERE checkpoint_key='invented-checkpoint'"
            ).fetchone()[0]
        return tuple(
            ScoreResult(
                metric=name,
                scorer_version="invented-trial-state-v1",
                eligible=True,
                value=float(value),
            )
            for name, value in (
                ("invented_correct", actual["step"] == "done"),
                ("invented_safe", actual["step"] in ("start", "done")),
                ("invented_review", False),
            )
        )


@dataclass(frozen=True)
class DatabaseFactory:
    hang: bool = False

    def build(self, context, state):
        assert isinstance(state.access, TrialDatabaseAccess)
        registry = ScorerRegistry()
        registry.register(
            ScorerSpec(
                scorer_id="invented-trial-state",
                version="invented-trial-state-v1",
                compatible=(
                    ScorerCompatibility(
                        snapshot_ref="invented-text-v1", policy_version="fake-text-policy-v1"
                    ),
                ),
            ),
            DatabaseScorer(state.access),
        )
        return TrialComponents(
            DatabaseAgent(state.access, self.hang and context.trial_id == "trial-1"),
            FakeGateway(),
            registry,
        )


class ObservedEnvironment:
    version = "h6-postgres-v1"
    fixture = "foundation-v1"

    def __init__(self, delegate):
        self.delegate = delegate
        self.prepared = []
        self.completed = []

    def prepare(self, experiment_id, task):
        lease = self.delegate.prepare(experiment_id, task)
        self.prepared.append(lease.access.trial.name)
        return lease

    def release(self, lease):
        # After child reaping, observe its committed write with separate restricted login.
        with lease.access.connect() as connection:
            value = connection.execute(
                "SELECT payload FROM runtime.checkpoints WHERE checkpoint_key='invented-checkpoint'"
            ).fetchone()[0]
            assert value["step"] == "done"
        self.completed.append(lease.reference)
        self.delegate.release(lease)


@pytest.mark.parametrize("hang", [False, True])
def test_runner_uses_fresh_restricted_databases_and_cleans_up_after_timeout(
    workspaces, tmp_path, hang
):
    workspace = workspaces[0]
    loaded, schedule = invented_schedule("h6-postgres-test-source", "h6-test-lock")
    schedule = schedule.model_copy(
        update={
            "experiment_id": "postgres-hang" if hang else "postgres-complete",
            "environment_version": "h6-postgres-v1",
            "state_fixture": "foundation-v1",
            "worker_timeout_seconds": 45.0,
            "tasks": tuple(
                task.model_copy(
                    update={
                        "context": task.context.model_copy(
                            update={
                                "deadline": task.context.clock + timedelta(seconds=90),
                            }
                        )
                    }
                )
                for task in schedule.tasks
            ),
        }
    )
    server = workspace.server()
    environment = ObservedEnvironment(PostgresTrialEnvironment(server, workspace.key))
    report = run_trials(schedule, loaded, DatabaseFactory(hang), environment, tmp_path / "journal")
    assert len(report.rows) == len(environment.prepared) == len(environment.completed) == 2
    assert len(set(environment.prepared)) == 2
    assert len({row.state_ref for row in report.rows}) == 2
    assert report.eligible_trials == 2 and report.autonomous_completions == (1 if hang else 2)
    if hang:
        assert report.rows[0].errors == ("timeout",) and not report.complete
        with pytest.raises(ValueError, match="incomplete"):
            report.require_release_evidence(loaded)
    else:
        assert report.complete
        report.require_release_evidence(loaded)
    with server.connect() as admin:
        for name in environment.prepared:
            assert (
                admin.execute("SELECT 1 FROM pg_database WHERE datname=%s", (name,)).fetchone()
                is None
            )
            assert (
                admin.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (name,)).fetchone() is None
            )
