"""Parent-owned SIM fixture lifecycle; no administrator credentials in worker leases."""

import secrets
from dataclasses import dataclass, field

from agent_harness.cases import LoadedManifest
from agent_harness.postgres import Server, Trial, create_trial, drop_trial
from agent_harness.trial_postgres import TrialDatabaseAccess
from agent_harness.trial_runner import StateLease
from agent_harness.trials import TrialTask

from olist_support.business import enroll, setup
from olist_support.business_contracts import CallerGrant
from olist_support.h10_manifest import private_case
from olist_support.release import StateSnapshot, collect_state
from olist_support.workflow_postgres import setup_checkpoints

ENVIRONMENT_VERSION = "olist-h10-postgres-v1"
FIXTURE = "olist-h10-sim-enrollment-v1"


def grant_for(tenant_id: str, order_id: str) -> CallerGrant:
    return CallerGrant(
        tenant_id=tenant_id,
        actor_id="olist-h10-evaluation",
        order_ids=(order_id,),
        capabilities=("read", "refund"),
    )


@dataclass(frozen=True)
class OlistAccess:
    database: TrialDatabaseAccess = field(repr=False)
    order_id: str
    grant: CallerGrant
    before: StateSnapshot
    recovery_required: bool
    run_limit_minor: int = 10000


@dataclass(frozen=True)
class OlistEnvironment:
    server: Server = field(repr=False)
    workspace_key: str
    loaded: LoadedManifest = field(repr=False)
    version: str = ENVIRONMENT_VERSION
    fixture: str = FIXTURE

    def prepare(self, experiment_id: str, task: TrialTask) -> StateLease:
        entry = self.loaded.entry(task.context.case_id)
        case, recovery = private_case(entry.case)
        view = case.input.order
        if (
            task.context.tenant_id != view.tenant_id
            or task.context.agent_id != "olist"
            or (task.eligible_for_autonomy, task.required_review)
            != (entry.case.expected.eligible_for_autonomy, entry.case.expected.required_review)
        ):
            raise ValueError("Olist fixture task differs from reviewed identity/labels")
        trial = Trial(
            self.workspace_key,
            "olist-h10:" + experiment_id + ":" + task.fingerprint(),
            secrets.token_hex(32),
        )
        create_trial(self.server, trial)
        try:
            with self.server.connect(trial.name) as admin:
                setup(admin, trial.name)
                setup_checkpoints(admin, trial.name)
                enroll(admin, view, case.input.confirmation)
            with self.server.connect(trial.name) as admin:
                before = collect_state(admin)
        except Exception:
            # Failed cleanup remains an owned, visible operator-recovery task.
            drop_trial(self.server, trial)
            raise
        access = OlistAccess(
            database=TrialDatabaseAccess(self.server.port, trial),
            order_id=view.order_id,
            grant=grant_for(view.tenant_id, view.order_id),
            before=before,
            recovery_required=recovery,
        )
        return StateLease("olist-h10:" + trial.name, FIXTURE, access)

    def release(self, lease: StateLease) -> None:
        access = lease.access
        if not isinstance(access, OlistAccess):
            raise TypeError("Olist restricted fixture access required")
        database = access.database
        if (
            lease.fixture != FIXTURE
            or lease.reference != "olist-h10:" + database.trial.name
            or database.port != self.server.port
            or database.trial.workspace_key != self.workspace_key
        ):
            raise ValueError("Olist trial belongs to another environment")
        drop_trial(self.server, database.trial)
