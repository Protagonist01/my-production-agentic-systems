"""Original-span provider composition; shared allowance, no business/meaning credit."""

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal

from agent_harness.admission import GeminiFreeAdmission
from agent_harness.cases import LoadedManifest
from agent_harness.contracts import RunContext
from agent_harness.domain_recording import (
    FIXTURE,
    DomainAgent,
    DomainScorer,
    Slot,
    StatelessEnvironment,
    verify_observations,
    verify_runtime,
)
from agent_harness.fresh_recording import FreshComponents, record_candidate
from agent_harness.provider_capture import GeminiCaptureControls
from agent_harness.release_contracts import CandidateSpec, EvidenceManifest
from agent_harness.release_evidence import VerifiedEvidence, read_evidence
from agent_harness.scorers import ScorerCompatibility, ScorerRegistry, ScorerSpec
from agent_harness.trial_runner import StateLease
from agent_harness.trials import TrialSchedule

from revenue_integrity.h10_recording import RevenueAdapter


@dataclass(frozen=True)
class RevenueProviderFactory:
    candidate: CandidateSpec
    loaded: LoadedManifest
    adapter: RevenueAdapter
    controls: GeminiCaptureControls
    root: Path
    origin: Literal["provider"] = "provider"

    def validate(self) -> None:
        verify_runtime(self.adapter, self.candidate)
        self.controls.validate()
        route = self.adapter.route
        if (
            self.origin != "provider"
            or self.candidate.execution.max_attempts != 1
            or self.candidate.provider_control_sha256 != self.controls.sha256
            or self.candidate.prompt_sha256
            != self.candidate.source_files[self.adapter.source_prefix + "extraction.py"]
            or self.candidate.recording_budget.max_cost != 0
            or self.candidate.recording_budget.cost_currency != "USD"
            or route.provider != "google-gemini-developer-api"
            or route.endpoint != "https://generativelanguage.googleapis.com"
            or route.model not in self.controls.tariff.models
            or route.tools
        ):
            raise ValueError("Revenue provider composition differs from reviewed controls/route")
        for entry in self.loaded.manifest.entries:
            self.adapter.validate_case(entry.case)
            if entry.scorer_id != self.adapter.scorer_id:
                raise ValueError("Revenue provider registry differs")

    def build(self, context: RunContext, state: StateLease) -> FreshComponents:
        self.validate()
        if context.agent_id != "revenue" or state.fixture != FIXTURE or state.access is not None:
            raise ValueError("Revenue original extraction requires its stateless scope")
        slot = Slot()
        registry = ScorerRegistry()
        registry.register(
            ScorerSpec(
                scorer_id=self.adapter.scorer_id,
                version=self.adapter.version,
                compatible=tuple(
                    ScorerCompatibility(snapshot_ref=snapshot, policy_version=policy)
                    for snapshot, policy in sorted(
                        {
                            (e.case.snapshot_ref, e.case.policy_version)
                            for e in self.loaded.manifest.entries
                        }
                    )
                ),
            ),
            DomainScorer(self.adapter, context, slot, self.root),
        )
        return FreshComponents(
            DomainAgent(self.adapter, slot),
            self.controls.transport(context),
            GeminiFreeAdmission(free_tier_confirmed=True, flash_comparison=True),
            registry,
        )


def record_provider(
    schedule: TrialSchedule,
    loaded: LoadedManifest,
    factory: RevenueProviderFactory,
    output: Path,
    *,
    candidate_sha256: str,
    source_root: Path,
) -> EvidenceManifest:
    factory.validate()
    if loaded.pin != factory.loaded.pin or schedule.fault_plan is not None:
        raise ValueError("Revenue original provider population/fault scope differs")
    return record_candidate(
        schedule,
        loaded,
        replace(factory, root=output / "observations"),
        StatelessEnvironment(),
        output,
        candidate=factory.candidate,
        candidate_sha256=candidate_sha256,
        source_root=source_root,
    )


def read_provider(
    root: Path,
    loaded: LoadedManifest,
    adapter: RevenueAdapter,
    *,
    evidence_sha256: str,
    candidate_sha256: str,
) -> VerifiedEvidence:
    verified = read_evidence(
        root, loaded, evidence_sha256=evidence_sha256, candidate_sha256=candidate_sha256
    )
    if (
        verified.manifest.origin != "provider"
        or verified.manifest.candidate.provider_control_sha256 is None
    ):
        raise ValueError("Revenue provider receipt/control evidence required")
    verify_runtime(adapter, verified.manifest.candidate)
    verify_observations(root, loaded, adapter, verified.batch)
    return verified
