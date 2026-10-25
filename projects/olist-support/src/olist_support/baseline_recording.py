"""Actual zero-call rules/always-review SIM workflows, distinct from fresh candidates."""

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal

from agent_harness.baseline_recording import (
    BaselineManifest,
    DenyModels,
    VerifiedBaseline,
    read_baseline,
    record_baseline,
    zero_usage,
)
from agent_harness.cases import LoadedManifest
from agent_harness.contracts import ModelGateway, ModelRequest, RunContext
from agent_harness.release_contracts import CandidateSpec, sha256
from agent_harness.scorers import ScorerCompatibility, ScorerRegistry, ScorerSpec
from agent_harness.trial_runner import StateLease, TrialComponents, TrialEnvironment
from agent_harness.trials import TrialSchedule

from olist_support.fresh_release import RulesPlanner
from olist_support.h10_config import fingerprints, verify_runtime
from olist_support.h10_environment import FIXTURE, OlistAccess
from olist_support.h10_evidence import verify_observations
from olist_support.h10_manifest import SCORER_ID, SCORER_VERSION
from olist_support.h10_runtime import ObservationSlot, OlistAgent, OlistScorer
from olist_support.policy import POLICY_VERSION
from olist_support.workflow import IntentDecision, IntentPlan, Planner, WorkflowRequest

Algorithm = Literal["rules", "always-review"]


@dataclass(frozen=True)
class DeterministicPlanner:
    algorithm: Algorithm

    def plan(self, context: RunContext, request: WorkflowRequest) -> IntentDecision:
        plan = (
            RulesPlanner().plan(context, request).plan
            if self.algorithm == "rules"
            else IntentPlan(intent="review")
        )
        return IntentDecision(
            plan=plan,
            usage=zero_usage(context.budget.cost_currency),
            execution_run_id=context.run_id,
        )


@dataclass(frozen=True)
class BaselineAgent(OlistAgent):
    algorithm: Algorithm

    def planner(self, gateway: ModelGateway) -> Planner:
        return DeterministicPlanner(self.algorithm)


def validate(candidate: CandidateSpec, route: ModelRequest, algorithm: str) -> None:
    verify_runtime(candidate)
    expected = fingerprints(route, candidate.source_files)
    expected["prompt_sha256"] = sha256(algorithm.encode())
    if any(getattr(candidate, k) != v for k, v in expected.items()):
        raise ValueError("Olist baseline algorithm/behavior differs from composition")


@dataclass(frozen=True)
class OlistBaselineFactory:
    candidate: CandidateSpec
    route: ModelRequest
    selected: Algorithm
    root: Path

    @property
    def algorithm(self) -> str:
        return "olist-" + self.selected + "-deterministic-v1"

    def validate(self) -> None:
        if self.selected not in ("rules", "always-review"):
            raise ValueError("unknown Olist deterministic algorithm")
        validate(self.candidate, self.route, self.algorithm)

    def build(self, context: RunContext, state: StateLease) -> TrialComponents:
        if (
            not isinstance(state.access, OlistAccess)
            or state.fixture != FIXTURE
            or context.agent_id != "olist"
            or context.tenant_id != state.access.grant.tenant_id
            or context.versions.policy != POLICY_VERSION
        ):
            raise ValueError("Olist baseline state/scope differs")
        slot = ObservationSlot()
        registry = ScorerRegistry()
        registry.register(
            ScorerSpec(
                scorer_id=SCORER_ID,
                version=SCORER_VERSION,
                compatible=(
                    ScorerCompatibility(
                        snapshot_ref=context.versions.data_snapshot, policy_version=POLICY_VERSION
                    ),
                ),
            ),
            OlistScorer(context, state.access, slot, self.root),
        )
        return TrialComponents(
            BaselineAgent(state.access, self.route, slot, self.selected), DenyModels(), registry
        )


def record_olist_baseline(
    schedule: TrialSchedule,
    loaded: LoadedManifest,
    factory: OlistBaselineFactory,
    environment: TrialEnvironment,
    output: Path,
    *,
    candidate_sha256: str,
    source_root: Path,
) -> BaselineManifest:
    return record_baseline(
        schedule,
        loaded,
        replace(factory, root=output / "observations"),
        environment,
        output,
        candidate_sha256=candidate_sha256,
        source_root=source_root,
    )


def read_olist_baseline(
    root: Path,
    loaded: LoadedManifest,
    *,
    route: ModelRequest,
    evidence_sha256: str,
    candidate_sha256: str,
) -> VerifiedBaseline:
    verified = read_baseline(
        root, loaded, evidence_sha256=evidence_sha256, candidate_sha256=candidate_sha256
    )
    if verified.manifest.algorithm not in (
        "olist-rules-deterministic-v1",
        "olist-always-review-deterministic-v1",
    ):
        raise ValueError("unknown Olist baseline algorithm")
    validate(verified.manifest.candidate, route, verified.manifest.algorithm)
    verify_observations(root, loaded, verified.batch)
    return verified
