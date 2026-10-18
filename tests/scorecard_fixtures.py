"""Invented typed reporting fixtures, not domain observations or fresh model evidence."""

import hashlib
from datetime import timedelta
from decimal import Decimal

from agent_harness.cases import CaseEntry, CaseManifest, LoadedManifest, ManifestPin, SnapshotSpec
from agent_harness.contracts import Failure, Usage
from agent_harness.evaluation import CaseReport, ScoreResult
from agent_harness.offline_example import FakeAgent, FakeGateway, example_case, example_context
from agent_harness.scorers import ManifestCaseReport
from agent_harness.trials import BatchReport, OutcomePolicy, TrialRow, TrialSchedule, TrialTask


def population(count=3, trials=1, mode="offline_fake", same_group=False, review_last=False):
    entries, snapshots, tasks = [], [], []
    kinds = ("synthetic", "hybrid", "original")
    for i in range(count):
        template = example_case()
        case = template.model_copy(
            update={
                "case_id": f"case-{i}",
                "snapshot_ref": f"snapshot-{i}",
                "source_kind": kinds[i % 3],
                "source_version": f"invented-source-{i}",
                "scorer_version": "invented-independent-v1",
                "risk": "required" if i == 0 else "ordinary",
                "slices": ("shared-tag",),
                "hidden_state": {"private": "HIDDEN-CANARY"},
                "expected": template.expected.model_copy(
                    update={
                        "eligible_for_autonomy": not (review_last and i == count - 1),
                        "required_review": review_last and i == count - 1,
                    }
                ),
            }
        )
        entries.append(
            CaseEntry(
                group_id="group-0" if same_group else f"group-{i}",
                split="development" if same_group or i == 0 else "holdout",
                scorer_id="invented-independent",
                case=case,
            )
        )
        snapshots.append(
            SnapshotSpec(
                reference=case.snapshot_ref,
                source_kind=case.source_kind,
                source_version=case.source_version,
            )
        )
        for j in range(trials):
            ctx = example_context("invented-code-v1", "invented-lock-v1")
            ctx = ctx.model_copy(
                update={
                    "case_id": case.case_id,
                    "trial_id": f"trial-{j}",
                    "run_id": f"run-{i}-{j}",
                    "mode": mode,
                    "seed": j,
                    "deadline": ctx.clock + timedelta(seconds=90),
                    "versions": ctx.versions.model_copy(
                        update={"data_snapshot": case.snapshot_ref}
                    ),
                }
            )
            tasks.append(
                TrialTask(
                    context=ctx,
                    eligible_for_autonomy=case.expected.eligible_for_autonomy,
                    required_review=case.expected.required_review,
                )
            )
    manifest = CaseManifest(
        manifest_id="invented-scorecards",
        version="v1",
        case_ids=tuple(e.case.case_id for e in entries),
        snapshots=tuple(snapshots),
        entries=tuple(entries),
    )
    payload = manifest.canonical_json().encode()
    pin = ManifestPin(
        manifest_id=manifest.manifest_id,
        version=manifest.version,
        sha256=hashlib.sha256(payload).hexdigest(),
    )
    loaded = LoadedManifest(payload, pin)
    schedule = TrialSchedule(
        experiment_id="invented-reporting",
        manifest=pin,
        environment_version="invented-env-v1",
        state_fixture="invented-state-v1",
        outcome_policy=OutcomePolicy(
            version="outcomes-v1",
            correctness_metric="correct",
            safety_metric="safe",
            review_metric="review",
        ),
        case_ids=manifest.case_ids,
        trial_ids=tuple(f"trial-{j}" for j in range(trials)),
        tasks=tuple(tasks),
    )
    return loaded, schedule


def batch(loaded, schedule, outcomes=None):
    outcomes = outcomes or {}
    rows = []
    for task in schedule.tasks:
        status = outcomes.get(task.key, "pass")
        if status == "missing":
            continue
        if status == "worker_error":
            rows.append(TrialRow(task=task, errors=("worker_crash",)))
            continue
        entry = loaded.entry(task.context.case_id)
        result = FakeAgent().run(
            task.context.model_copy(update={"mode": "offline_fake"}),
            entry.case.agent_input(),
            FakeGateway(),
        )
        result = result.model_copy(
            update={
                "output": "PRIVATE-OUTPUT-CANARY",
                "usage": Usage(
                    model_calls=1,
                    input_tokens=2,
                    output_tokens=3,
                    cost=Decimal("0.01"),
                    cost_currency="USD",
                ),
            }
        )
        if status == "review":
            result = result.model_copy(
                update={"outcome": "review_required", "review_ref": "private-review"}
            )
        if status == "blocked":
            result = result.model_copy(update={"outcome": "blocked"})
        values = (
            ("correct", status not in ("fail", "blocked")),
            ("safe", status not in ("unsafe", "unsafe_error")),
            ("review", status == "review"),
        )
        scores = tuple(
            ScoreResult(
                metric=name,
                scorer_version=entry.case.scorer_version,
                eligible=entry.case.expected.eligible_for_autonomy,
                value=float(value),
            )
            for name, value in values
        )
        if status in ("scorer_error", "unsafe_error"):
            scores = (
                ScoreResult(
                    metric="correct",
                    scorer_version=entry.case.scorer_version,
                    eligible=True,
                    failure=Failure(
                        stage="scorer",
                        code="scorer_error",
                        message="PRIVATE-SCORER-CANARY",
                        retryable=False,
                    ),
                ),
                *scores[1:],
            )
        report = CaseReport(
            context=task.context,
            source_kind=entry.case.source_kind,
            source_version=entry.case.source_version,
            policy_version=entry.case.policy_version,
            scorer_version=entry.case.scorer_version,
            result=result,
            scores=scores,
        )
        rows.append(
            TrialRow(
                task=task,
                report=ManifestCaseReport(
                    manifest=loaded.pin,
                    group_id=entry.group_id,
                    split=entry.split,
                    scorer_id=entry.scorer_id,
                    report=report,
                ),
                errors=("cleanup_error",) if status in ("cleanup_error", "unsafe_error") else (),
            )
        )
    return BatchReport(schedule=schedule, rows=tuple(rows))
