"""F4 fresh database/role lifecycle; only restricted access crosses into trial workers."""

import secrets
from dataclasses import dataclass, field
from typing import Any

import psycopg
from psycopg import Connection

from agent_harness.postgres import FIXTURE_ID, Server, Trial, create_trial, drop_trial
from agent_harness.trial_runner import StateLease
from agent_harness.trials import TrialTask


@dataclass(frozen=True)
class TrialDatabaseAccess:
    port: int
    trial: Trial = field(repr=False)

    def connect(self) -> Connection[tuple[Any, ...]]:
        return psycopg.connect(
            host="127.0.0.1",
            port=self.port,
            user=self.trial.name,
            password=self.trial.password,
            dbname=self.trial.name,
            connect_timeout=5,
        )


@dataclass(frozen=True)
class PostgresTrialEnvironment:
    server: Server = field(repr=False)
    workspace_key: str
    version: str = "h6-postgres-v1"
    fixture: str = FIXTURE_ID

    def prepare(self, experiment_id: str, task: TrialTask) -> StateLease:
        # A new database resets all controlled state. Never reset an existing identity.
        identity = "h6:" + experiment_id + ":" + task.fingerprint()
        trial = Trial(self.workspace_key, identity, secrets.token_hex(32))
        create_trial(self.server, trial)
        return StateLease(
            reference="postgres-trial:" + trial.name,
            fixture=FIXTURE_ID,
            access=TrialDatabaseAccess(self.server.port, trial),
        )

    def release(self, lease: StateLease) -> None:
        if not isinstance(lease.access, TrialDatabaseAccess):
            raise TypeError("expected restricted trial database access")
        if (
            lease.access.port != self.server.port
            or lease.access.trial.workspace_key != self.workspace_key
        ):
            raise ValueError("trial belongs to another environment")
        drop_trial(self.server, lease.access.trial)
