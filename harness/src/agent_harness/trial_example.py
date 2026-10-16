"""Invented offline file-state trials; no domain quality or provider experiment."""

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from agent_harness.cases import CaseEntry, CaseManifest, LoadedManifest, ManifestPin, SnapshotSpec
from agent_harness.contracts import AgentInput, AgentResult, ModelGateway, RunContext
from agent_harness.evaluation import EvalCase, ScoreResult
from agent_harness.offline_example import FakeAgent, FakeGateway, example_case, example_context
from agent_harness.scorers import ScorerCompatibility, ScorerRegistry, ScorerSpec
from agent_harness.trial_runner import StateLease, TrialComponents, run_trials
from agent_harness.trials import OutcomePolicy, TrialSchedule, TrialTask


@dataclass(frozen=True)
class FileTrialEnvironment:
    root: Path
    version: str = "h6-invented-files-v1"
    fixture: str = "invented-state-v1"

    def prepare(self, experiment_id: str, task: TrialTask) -> StateLease:
        # Root belongs exclusively to this example execution. Existing paths fail.
        directory = self.root / task.fingerprint()
        directory.mkdir(mode=0o700)
        (directory / "state.json").write_text('{"status":"start"}', encoding="utf-8")
        return StateLease("invented-file:" + task.fingerprint(), self.fixture, str(directory))

    def release(self, lease: StateLease) -> None:
        if not isinstance(lease.access, str):
            raise TypeError("expected invented file access")
        directory = Path(lease.access)
        if directory.parent.resolve() != self.root.resolve():
            raise ValueError("state belongs to another example")
        (directory / "state.json").unlink()
        directory.rmdir()  # Unexpected files preserve a visible cleanup failure.


@dataclass
class InventedAgent:
    path: Path
    behavior: str = "complete"

    def run(self, context: RunContext, input: AgentInput, gateway: ModelGateway) -> AgentResult:
        observed = json.loads(self.path.read_text(encoding="utf-8"))
        if observed != {"status": "start"}:
            raise ValueError("trial state was not reset")
        result = FakeAgent().run(context, input, gateway)
        state = {"status": "done", "safe": True, "review": False}
        if self.behavior == "escalate":
            state = {"status": "review", "safe": True, "review": True}
            result = result.model_copy(
                update={"outcome": "review_required", "review_ref": "invented-review"}
            )
        elif self.behavior == "unsafe":
            state["safe"] = False
        self.path.write_text(json.dumps(state), encoding="utf-8")
        return result


@dataclass
class InventedStateScorer:
    path: Path

    def score(self, case: EvalCase, result: AgentResult) -> tuple[ScoreResult, ...]:
        actual = json.loads(self.path.read_text(encoding="utf-8"))
        values = (
            ("invented_correct", actual["status"] == "done"),
            ("invented_safe", actual["safe"] is True),
            ("invented_review", actual["review"] is True),
        )
        return tuple(
            ScoreResult(
                metric=name,
                scorer_version="invented-trial-state-v1",
                eligible=True,
                value=float(value),
            )
            for name, value in values
        )


@dataclass(frozen=True)
class InventedFactory:
    behavior: str = "complete"

    def build(self, context: RunContext, state: StateLease) -> TrialComponents:
        if not isinstance(state.access, str):
            raise TypeError("expected invented file access")
        path = Path(state.access) / "state.json"
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
            InventedStateScorer(path),
        )
        return TrialComponents(InventedAgent(path, self.behavior), FakeGateway(), registry)


def invented_schedule(code_revision: str, lock_hash: str) -> tuple[LoadedManifest, TrialSchedule]:
    case = example_case().model_copy(update={"scorer_version": "invented-trial-state-v1"})
    manifest = CaseManifest(
        manifest_id="invented-trials",
        version="v1",
        case_ids=(case.case_id,),
        snapshots=(
            SnapshotSpec(
                reference=case.snapshot_ref,
                source_kind="synthetic",
                source_version=case.source_version,
            ),
        ),
        entries=(
            CaseEntry(
                group_id="invented-family-1",
                split="development",
                scorer_id="invented-trial-state",
                case=case,
            ),
        ),
    )
    # Author our own invented fixture here; production callers supply a separately reviewed pin.
    payload = manifest.canonical_json().encode()
    pin = ManifestPin(
        manifest_id=manifest.manifest_id,
        version=manifest.version,
        sha256=hashlib.sha256(payload).hexdigest(),
    )
    tasks = tuple(
        TrialTask(
            context=example_context(code_revision, lock_hash).model_copy(
                update={
                    "run_id": "invented-run-" + str(index),
                    "trial_id": "trial-" + str(index),
                    "seed": index,
                }
            ),
            eligible_for_autonomy=True,
            required_review=False,
        )
        for index in (1, 2)
    )
    return LoadedManifest(payload, pin), TrialSchedule(
        experiment_id="invented-experiment-v1",
        case_ids=manifest.case_ids,
        manifest=pin,
        environment_version="h6-invented-files-v1",
        state_fixture="invented-state-v1",
        outcome_policy=OutcomePolicy(
            version="invented-outcomes-v1",
            correctness_metric="invented_correct",
            safety_metric="invented_safe",
            review_metric="invented_review",
        ),
        trial_ids=("trial-1", "trial-2"),
        tasks=tasks,
        max_parallel=2,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path, help="New private output directory")
    parser.add_argument("--code-revision", required=True)
    parser.add_argument("--lockfile", required=True, type=Path)
    args = parser.parse_args()
    loaded, schedule = invented_schedule(
        args.code_revision, hashlib.sha256(args.lockfile.read_bytes()).hexdigest()
    )
    args.root.mkdir(mode=0o700)
    state_root = args.root / "state"
    state_root.mkdir(mode=0o700)
    report = run_trials(
        schedule, loaded, InventedFactory(), FileTrialEnvironment(state_root), args.root / "journal"
    )
    report.require_release_evidence(loaded)
    print(
        json.dumps(
            {
                "check": "invented-isolated-trials",
                "mode": "offline_fake",
                "scheduled_trials": len(schedule.tasks),
                "terminal_rows": len(report.rows),
                "eligible_trials": report.eligible_trials,
                "autonomous_completions": report.autonomous_completions,
                "complete": report.complete,
                "provider_calls": 0,
                "quality_evaluation": False,
            }
        )
    )


if __name__ == "__main__":
    main()
