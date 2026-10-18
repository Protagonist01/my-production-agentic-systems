"""Invented offline fixtures. Relabelled DTOs test logic, never actual provider evidence."""

import inspect
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from agent_harness.contracts import Budget, ModelMessage, ModelRequest
from agent_harness.controls import ExecutionPolicy
from agent_harness.fresh_example import RecordingConfig, UppercaseFactory, UppercaseScorer
from agent_harness.fresh_recording import record_candidate
from agent_harness.release_contracts import (
    BaselineApproval,
    CandidateSpec,
    ReleasePolicy,
    pin,
    sha256,
)
from agent_harness.release_evidence import read_evidence
from agent_harness.scorecard_contracts import ReportPolicy
from agent_harness.trial_example import FileTrialEnvironment, invented_schedule
from agent_harness.trials import TrialSchedule


def inputs(tmp_path, label="candidate"):
    source = tmp_path / "source"
    source.mkdir(exist_ok=True)
    (source / "agent.py").write_text("# invented reviewed source\n", encoding="utf-8")
    config = RecordingConfig(
        composition="invented-uppercase-mock",
        prompt="Uppercase the supplied invented text.",
        request=ModelRequest(
            provider="mock",
            endpoint="in-process",
            model="invented-uppercase",
            messages=(ModelMessage(role="user", content="template"),),
            parameters={"temperature": 0},
        ),
    )
    spec = CandidateSpec(
        candidate=label,
        code_revision="invented-source-" + label,
        environment_lock="invented-lock-v1",
        source_files={"agent.py": sha256((source / "agent.py").read_bytes())},
        prompt_sha256=sha256(config.prompt.encode()),
        model_config_sha256=pin(config.request),
        tools_sha256=sha256(b"no-tools"),
        policy_sha256=sha256(b"fake-text-policy-v1"),
        scorer_sha256=sha256(inspect.getsource(UppercaseScorer).encode()),
        environment_sha256=sha256(b"h6-invented-files-v1:invented-state-v1"),
        execution=ExecutionPolicy(max_attempts=1, attempt_timeout_seconds=5.0),
        recording_budget=Budget(
            max_model_calls=3, max_tokens=300, max_cost=Decimal(0), cost_currency="USD"
        ),
    )
    loaded, old = invented_schedule(spec.code_revision, spec.environment_lock)
    now = datetime.now(UTC)
    tasks = tuple(
        old.tasks[0].model_copy(
            update={
                "context": old.tasks[0].context.model_copy(
                    update={
                        "run_id": label + "-" + uuid4().hex,
                        "trial_id": "trial-" + str(i),
                        "seed": i,
                        "mode": "fresh_candidate",
                        "clock": now,
                        "deadline": now + timedelta(seconds=90),
                        "versions": old.tasks[0].context.versions.model_copy(
                            update={
                                "candidate": spec.candidate,
                            }
                        ),
                    }
                )
            }
        )
        for i in (1, 2, 3)
    )
    schedule = TrialSchedule.model_validate(
        old.model_copy(
            update={
                "tasks": tasks,
                "trial_ids": ("trial-1", "trial-2", "trial-3"),
                "max_parallel": 1,
            }
        )
    )
    return loaded, schedule, spec, config, source


def capture(tmp_path, label="candidate"):
    loaded, schedule, spec, config, source = inputs(tmp_path, label)
    state = tmp_path / (label + "-state")
    state.mkdir()
    output = tmp_path / label
    manifest = record_candidate(
        schedule,
        loaded,
        UppercaseFactory(spec, config),
        FileTrialEnvironment(state),
        output,
        candidate=spec,
        candidate_sha256=pin(spec),
        source_root=source,
    )
    evidence = read_evidence(
        output, loaded, evidence_sha256=pin(manifest), candidate_sha256=pin(spec)
    )
    return loaded, evidence, output


def logical_pair(tmp_path):
    loaded, old, _ = capture(tmp_path, "baseline")
    _, new, _ = capture(tmp_path, "candidate")
    # Artificial provider-labelled objects test gate branches offline. They are never persisted
    # as real provider evidence, published as a release, or presented as quality observations.
    before = old.manifest.finished_at
    after = new.manifest.started_at
    approved = before + (after - before) / 2
    old = replace(old, manifest=old.manifest.model_copy(update={"origin": "provider"}))
    new = replace(new, manifest=new.manifest.model_copy(update={"origin": "provider"}))
    policy = ReleasePolicy(
        version="invented-test-policy",
        max_age_seconds=3600,
        min_autonomous_completion=1.0,
        max_review_rate=0.0,
        report=ReportPolicy(
            version="invented-test-report",
            required_case_ids=loaded.manifest.case_ids,
            repeated_case_ids=loaded.manifest.case_ids,
        ),
    )
    approval = BaselineApproval(
        version="invented-test-approval",
        baseline_sha256=pin(old.manifest),
        release_policy_sha256=pin(policy),
        reviewer="invented-reviewer",
        review_ref="invented-offline-logic-test-only",
        approved_at=approved,
        expires_at=after + timedelta(hours=1),
    )
    return loaded, old, new, policy, approval
