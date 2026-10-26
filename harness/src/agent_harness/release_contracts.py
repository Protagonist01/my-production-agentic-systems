"""Private fresh-evidence contracts; approval is an externally reviewed input."""

import hashlib
from pathlib import Path, PurePosixPath
from typing import Annotated, Literal, Self

from pydantic import AwareDatetime, Field, model_validator

from agent_harness.contracts import Budget, Contract, NonEmpty, WireContract
from agent_harness.controls import ExecutionPolicy
from agent_harness.gateway import ModelExchange
from agent_harness.scorecard_contracts import ReportPolicy

Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Rate = Annotated[float, Field(ge=0, le=1)]


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def pin(value: WireContract) -> str:
    return sha256(value.canonical_json().encode())


class CandidateSpec(Contract):
    candidate: NonEmpty
    code_revision: NonEmpty
    environment_lock: NonEmpty
    # Explicit reviewed inventories. Whole-population invalidation, no slice reuse.
    source_files: dict[NonEmpty, Sha256]
    prompt_sha256: Sha256
    model_config_sha256: Sha256
    tools_sha256: Sha256
    policy_sha256: Sha256
    scorer_sha256: Sha256
    environment_sha256: Sha256
    execution: ExecutionPolicy
    recording_budget: Budget
    provider_control_sha256: Sha256 | None = Field(default=None, exclude_if=lambda v: v is None)

    @model_validator(mode="after")
    def paths(self) -> Self:
        if not self.source_files:
            raise ValueError("reviewed source inventory is required")
        for name in self.source_files:
            path = PurePosixPath(name)
            if path.is_absolute() or ".." in path.parts or "\\" in name or ":" in name:
                raise ValueError("source paths must be relative portable paths")
        return self


def verify_sources(root: Path, spec: CandidateSpec) -> None:
    for name, expected in spec.source_files.items():
        path = (root / name).resolve()
        if not path.is_relative_to(root.resolve()) or sha256(path.read_bytes()) != expected:
            raise ValueError("candidate source differs from reviewed inventory")


class AttemptReceipt(Contract):
    execution_id: NonEmpty
    nonce: NonEmpty
    started_at: AwareDatetime
    finished_at: AwareDatetime
    exchange: ModelExchange

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if self.finished_at < self.started_at:
            raise ValueError("receipt time order")
        return self


class EvidenceManifest(Contract):
    execution_id: NonEmpty
    origin: Literal["provider", "mock"]
    candidate: CandidateSpec
    started_at: AwareDatetime
    finished_at: AwareDatetime
    batch_sha256: Sha256
    # Fixed task-fingerprint/occurrence names, independently pinned by this manifest.
    receipts: dict[NonEmpty, Sha256]


class ReleasePolicy(Contract):
    version: NonEmpty
    report: ReportPolicy
    max_age_seconds: Annotated[int, Field(gt=0)]
    min_autonomous_completion: Rate
    max_review_rate: Rate


class BaselineApproval(Contract):
    version: NonEmpty
    baseline_sha256: Sha256
    release_policy_sha256: Sha256
    reviewer: NonEmpty
    review_ref: NonEmpty
    approved_at: AwareDatetime
    expires_at: AwareDatetime

    @model_validator(mode="after")
    def interval(self) -> Self:
        if self.expires_at <= self.approved_at:
            raise ValueError("approval must expire after approval")
        return self


class DeterministicBaselineApproval(BaselineApproval):
    approval_kind: Literal["executed-deterministic-baseline-v1"] = (
        "executed-deterministic-baseline-v1"
    )
    algorithm: NonEmpty
    dataset_sha256: Sha256
    baseline_spec_sha256: Sha256


class ReleaseDecision(Contract):
    candidate_sha256: Sha256
    baseline_sha256: Sha256
    candidate_spec_sha256: Sha256
    approval_sha256: Sha256
    policy_sha256: Sha256
    checked_at: AwareDatetime
    allowed: bool
    blockers: tuple[NonEmpty, ...]
    regressed_cases: tuple[NonEmpty, ...]
    evaluation_audit_sha256: Sha256 | None = None
    decision_kind: Literal["evidence_gate_only"] = "evidence_gate_only"
