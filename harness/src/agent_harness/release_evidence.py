"""Read exact pinned artifacts and fail closed before evaluating release policy."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from agent_harness.cases import LoadedManifest
from agent_harness.controls import combine_usage
from agent_harness.fault_contracts import FaultPlan
from agent_harness.fresh_recording import validate_fresh
from agent_harness.release_contracts import (
    AttemptReceipt,
    BaselineApproval,
    EvidenceManifest,
    ReleaseDecision,
    ReleasePolicy,
    pin,
    sha256,
)
from agent_harness.scorecards import build_scorecard
from agent_harness.trials import BatchReport, TrialJournal, validate_schedule


@dataclass(frozen=True)
class VerifiedEvidence:
    manifest: EvidenceManifest
    batch: BatchReport
    receipts: tuple[AttemptReceipt, ...]


def read_evidence(
    root: Path,
    loaded: LoadedManifest,
    *,
    evidence_sha256: str,
    candidate_sha256: str,
    fault_plan: FaultPlan | None = None,
) -> VerifiedEvidence:
    manifest = EvidenceManifest.model_validate_json((root / "evidence.json").read_bytes())
    if pin(manifest) != evidence_sha256 or pin(manifest.candidate) != candidate_sha256:
        raise ValueError("evidence or candidate differs from external pin")
    if manifest.finished_at < manifest.started_at:
        raise ValueError("invalid capture interval")
    batch = TrialJournal(root / "journal").read(loaded, fault_plan=fault_plan)
    validate_schedule(batch.schedule, loaded)
    validate_fresh(batch.schedule, manifest.candidate)
    if pin(batch) != manifest.batch_sha256:
        raise ValueError("journal changed after recording")
    receipts = []
    names = set()
    nonces = set()
    directory = root / "receipts"
    contexts = {pin(t.context): t.context for t in batch.schedule.tasks}
    for scope, context in contexts.items():
        values = []
        for path in (directory / scope).glob("*.json"):
            if path.is_symlink():
                raise ValueError("receipt symlinks are not accepted")
            name = path.relative_to(directory).as_posix()
            names.add(name)
            payload = path.read_bytes()
            if manifest.receipts.get(name) != sha256(payload):
                raise ValueError("receipt differs from sealed digest")
            receipt = AttemptReceipt.model_validate_json(payload)
            exchange = receipt.exchange
            if (
                receipt.execution_id != manifest.execution_id
                or receipt.nonce in nonces
                or exchange.context != context
                or path.name != f"{exchange.occurrence}.json"
                or not manifest.started_at
                <= receipt.started_at
                <= receipt.finished_at
                <= manifest.finished_at
            ):
                raise ValueError("receipt has incompatible identity, nonce or interval")
            nonces.add(receipt.nonce)
            values.append(receipt)
        values.sort(key=lambda r: r.exchange.occurrence)
        if not values or [r.exchange.occurrence for r in values] != list(range(1, len(values) + 1)):
            raise ValueError("every scheduled fresh trial requires contiguous dispatch receipts")
        if any(r.exchange.response.usage.model_calls != 1 for r in values):
            raise ValueError("non-dispatched response cannot prove fresh recording")
        usage = combine_usage(
            tuple(r.exchange.response.usage for r in values), context.budget.cost_currency
        )
        if (
            usage.input_tokens is None
            or usage.output_tokens is None
            or usage.cost is None
            or usage.cost_currency != context.budget.cost_currency
        ):
            raise ValueError("fresh usage evidence is incomplete")
        row = next((r for r in batch.rows if r.task.context == context), None)
        if row is None or row.report is None or row.report.report.result.usage != usage:
            raise ValueError("reported usage differs from observed fresh attempts")
        if (
            usage.model_calls > context.budget.max_model_calls
            or (usage.input_tokens or 0) + (usage.output_tokens or 0) > context.budget.max_tokens
            or (usage.cost is not None and usage.cost > context.budget.max_cost)
        ):
            raise ValueError("observed usage exceeds reviewed partition")
        receipts.extend(values)
    actual = {p.relative_to(directory).as_posix() for p in directory.rglob("*") if p.is_file()}
    if names != set(manifest.receipts) or actual != names:
        raise ValueError("missing or unexpected receipts")
    return VerifiedEvidence(manifest, batch, tuple(receipts))


def compare_evidence(
    baseline: VerifiedEvidence,
    candidate: VerifiedEvidence,
    loaded: LoadedManifest,
    policy: ReleasePolicy,
    *,
    fault_plan: FaultPlan | None = None,
) -> tuple[str, ...]:
    """Case/trial regressions; wall-clock capture times may differ between fresh runs."""
    a, b = baseline.batch.schedule, candidate.batch.schedule
    left, right = baseline.manifest.candidate, candidate.manifest.candidate
    if (
        a.manifest,
        a.environment_version,
        a.state_fixture,
        a.outcome_policy,
        a.fault_plan,
        left.scorer_sha256,
        left.policy_sha256,
        left.environment_sha256,
        left.environment_lock,
    ) != (
        b.manifest,
        b.environment_version,
        b.state_fixture,
        b.outcome_policy,
        b.fault_plan,
        right.scorer_sha256,
        right.policy_sha256,
        right.environment_sha256,
        right.environment_lock,
    ):
        raise ValueError("baseline population, evaluator, policy or environment is incompatible")
    before = {t.key: t for t in a.tasks}
    after = {t.key: t for t in b.tasks}
    if before.keys() != after.keys():
        raise ValueError("baseline and candidate trial populations differ")
    for key, task in before.items():
        x, y = task.context, after[key].context
        if (
            x.seed,
            x.budget,
            x.tenant_id,
            x.agent_id,
            x.business_event_id,
            x.deadline - x.clock,
        ) != (
            y.seed,
            y.budget,
            y.tenant_id,
            y.agent_id,
            y.business_event_id,
            y.deadline - y.clock,
        ):
            raise ValueError("baseline and candidate trial conditions differ")
    cards = [
        build_scorecard(
            v.batch,
            loaded,
            policy.report,
            reporter_revision="h10-release-v1",
            fault_plan=fault_plan,
        )
        for v in (baseline, candidate)
    ]
    regressions = []
    for old, new in zip(cards[0].cases, cards[1].cases, strict=True):
        prior = {f.trial_id: f for f in old.trials}
        if any(prior[f.trial_id].passed and not f.passed for f in new.trials):
            regressions.append(new.case_id)
    return tuple(regressions)


def release_candidate(
    baseline: VerifiedEvidence,
    candidate: VerifiedEvidence,
    loaded: LoadedManifest,
    policy: ReleasePolicy,
    approval: BaselineApproval,
    *,
    approval_sha256: str,
    policy_sha256: str,
    expected_candidate_sha256: str,
    now: datetime,
    fault_plan: FaultPlan | None = None,
) -> ReleaseDecision:
    if now.tzinfo is None:
        raise ValueError("release clock must be timezone aware")
    if pin(approval) != approval_sha256 or pin(policy) != policy_sha256:
        raise ValueError("approval or policy differs from separately reviewed pin")
    if pin(candidate.manifest.candidate) != expected_candidate_sha256:
        raise ValueError("candidate behavior changed; new whole-population evidence required")
    if approval.baseline_sha256 != pin(baseline.manifest) or (
        approval.release_policy_sha256 != pin(policy)
    ):
        raise ValueError("approval does not bind this baseline and release policy")
    regressions = compare_evidence(baseline, candidate, loaded, policy, fault_plan=fault_plan)
    blockers = []
    if not approval.approved_at <= now < approval.expires_at:
        blockers.append("baseline_approval_expired_or_future")
    if approval.approved_at < baseline.manifest.finished_at:
        blockers.append("baseline_approved_before_evidence")
    if candidate.manifest.started_at < approval.approved_at:
        blockers.append("candidate_recorded_before_baseline_approval")
    baseline_runs = {t.context.run_id for t in baseline.batch.schedule.tasks}
    candidate_runs = {t.context.run_id for t in candidate.batch.schedule.tasks}
    if (
        baseline.manifest.execution_id == candidate.manifest.execution_id
        or baseline_runs & candidate_runs
        or {r.nonce for r in baseline.receipts} & {r.nonce for r in candidate.receipts}
    ):
        blockers.append("candidate_reuses_baseline_execution")
    for label, evidence in (("baseline", baseline), ("candidate", candidate)):
        manifest = evidence.manifest
        if manifest.origin != "provider":
            blockers.append(label + "_mock_evidence")
        age = (now - manifest.started_at).total_seconds()
        if age < 0 or age > policy.max_age_seconds or manifest.finished_at > now:
            blockers.append(label + "_evidence_expired_or_future")
        try:
            evidence.batch.require_release_evidence(loaded, fault_plan=fault_plan)
        except ValueError:
            blockers.append(label + "_incomplete_or_unsafe")
    if regressions:
        blockers.append("previously_passing_case_regressed")
    card = build_scorecard(
        candidate.batch,
        loaded,
        policy.report,
        reporter_revision="h10-release-v1",
        fault_plan=fault_plan,
    )
    if any(c.required_case and not all(f.passed for f in c.trials) for c in card.cases):
        blockers.append("required_case_failed")
    completion = card.overall.autonomous_completion.value
    review = card.overall.observed_review.value
    if completion is None or completion < policy.min_autonomous_completion:
        blockers.append("autonomous_completion_below_floor")
    if review is None or review > policy.max_review_rate:
        blockers.append("review_burden_above_ceiling")
    if not policy.report.required_case_ids:
        blockers.append("no_reviewed_required_cases")
    return ReleaseDecision(
        candidate_sha256=pin(candidate.manifest),
        baseline_sha256=pin(baseline.manifest),
        candidate_spec_sha256=expected_candidate_sha256,
        approval_sha256=pin(approval),
        policy_sha256=pin(policy),
        checked_at=now,
        allowed=not blockers,
        blockers=tuple(blockers),
        regressed_cases=regressions,
    )
