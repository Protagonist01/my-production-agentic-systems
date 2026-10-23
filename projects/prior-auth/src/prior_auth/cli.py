"""Private-source evidence assessment and explicit bounded fresh Gemini evaluation."""

import argparse
import hashlib
import json
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from prior_auth.assessment import CRITERIA, assess, retrieve
from prior_auth.candidate import PROMPT_VERSION, extract
from prior_auth.contracts import NoteInput, Policy
from prior_auth.evaluation import EvaluationCase, score, validate_cohort
from prior_auth.source_io import canonical, external


def pinned(path: Path, expected: str) -> bytes:
    data = external(path).read_bytes()
    if len(data) > 5_000_000 or hashlib.sha256(data).hexdigest() != expected:
        raise ValueError("private input byte pin differs or input exceeds limit")
    return data


def run(args: argparse.Namespace) -> dict[str, object]:
    # Live SDK imports are explicit and optional. Importing the base package or
    # source verifiers never loads a provider client or reads credentials.
    from agent_harness.admission import GEMINI_TOKEN_CEILING, GeminiFreeAdmission
    from agent_harness.controls import BoundedGateway, ExecutionPolicy, SharedControls
    from agent_harness.gateway import ProviderGateway
    from agent_harness.integration_smoke import local_environment
    from agent_harness.isolated_transport import GeminiWorker, IsolatedTransport
    from agent_harness.offline_example import example_context

    root = args.root.resolve()
    policy = Policy.model_validate_json(pinned(args.policy, args.policy_sha256))
    cases = tuple(
        EvaluationCase.model_validate_json(json.dumps(value))
        for value in json.loads(pinned(args.cases, args.cases_sha256))
    )
    validate_cohort(cases)
    selected = tuple(c for c in cases if c.split == args.split)
    if not selected or len(selected) > 12 or len({c.input.tenant_id for c in selected}) != 1:
        raise ValueError("one tenant and one to twelve selected cases required")
    output = external(args.output)
    if output.exists():
        raise ValueError("evaluation output already exists; never overwrite evidence")
    output.mkdir(parents=True)
    values = local_environment(root)
    confirmed = values["GEMINI_FREE_TIER_CONFIRMED"].lower() == "true"
    if not values["GEMINI_API_KEY"] or not confirmed:
        raise ValueError("configure GEMINI_API_KEY and billing-disabled Free confirmation")
    policy_execution = ExecutionPolicy(max_attempts=1)
    attempts = ProviderGateway(IsolatedTransport(GeminiWorker(values["GEMINI_API_KEY"], confirmed)))
    controls = SharedControls()
    gateway = BoundedGateway(
        attempts,
        controls,
        GeminiFreeAdmission(free_tier_confirmed=confirmed),
        policy=policy_execution,
    )
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    dirty = subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True)
    if dirty.strip():
        revision += "+dirty"
    lock = hashlib.sha256((root / "uv.lock").read_bytes()).hexdigest()
    now, run_id = datetime.now(UTC), "prior-auth-" + uuid4().hex
    maximum = len(selected) * 7
    context = example_context(revision, lock)
    context = context.model_copy(
        update=dict(
            tenant_id=selected[0].input.tenant_id,
            run_id=run_id,
            mode="fresh_candidate",
            clock=now,
            deadline=now + timedelta(seconds=args.deadline_seconds),
            budget=context.budget.model_copy(
                update=dict(max_model_calls=maximum, max_tokens=maximum * GEMINI_TOKEN_CEILING)
            ),
            versions=context.versions.model_copy(
                update=dict(
                    candidate=PROMPT_VERSION,
                    data_snapshot=args.cases_sha256,
                    policy=args.policy_sha256,
                )
            ),
        )
    )
    scored = []
    slices: dict[str, dict[str, int]] = {}
    terminal_errors: dict[str, int] = {}
    for case in selected:
        # Detach and revalidate only public input. No expected values enter extract.
        note = NoteInput.model_validate_json(case.input.canonical_json())
        diagnostics: list[dict[str, str]] = []
        candidate = extract(
            gateway,
            context.model_copy(update=dict(case_id=note.case_id)),
            note,
            policy,
            diagnostics=diagnostics,
        )
        for error in diagnostics:
            key = error["phase"] + ":" + error["code"]
            terminal_errors[key] = terminal_errors.get(key, 0) + 1
        result = assess(note, policy, candidate)
        row = score(case, result if candidate is not None else None)
        row["model_completed"] = int(candidate is not None)
        scored.append(row)
        group = slices.setdefault(
            note.provenance, {"cases": 0, "correct": 0, "candidate_completed": 0}
        )
        group["cases"] += 1
        group["correct"] += int(row["correct"])
        group["candidate_completed"] += int(candidate is not None)
        (output / ("case-" + note.case_id + ".json")).write_bytes(
            canonical(
                dict(
                    candidate=candidate.model_dump(mode="json") if candidate else None,
                    result=result.model_dump(mode="json"),
                    score=row,
                    diagnostics=diagnostics,
                    retrieval={
                        key: {"candidate_spans": len(retrieve(note, key))} for key in CRITERIA
                    },
                )
            )
        )
    (output / "exchanges.json").write_bytes(
        canonical([x.model_dump(mode="json") for x in attempts.exchanges])
    )
    summary: dict[str, object] = dict(
        mode="fresh_candidate",
        split=args.split,
        source_sha256=args.cases_sha256,
        policy_sha256=args.policy_sha256,
        code_revision=revision,
        environment_lock=lock,
        candidate=PROMPT_VERSION,
        model="gemini-3.5-flash-lite",
        run_id=run_id,
        cases=len(scored),
        correct=sum(int(r["correct"]) for r in scored),
        model_completed=sum(int(r["model_completed"]) for r in scored),
        incorrect_evidence_complete=sum(int(r["incorrect_evidence_complete"]) for r in scored),
        proposed_evidence_complete=sum(int(r["proposed_evidence_complete"]) for r in scored),
        unsupported_met=sum(int(r["unsupported_met"]) for r in scored),
        criterion_correct=sum(int(r["criterion_correct"]) for r in scored),
        criterion_denominator=sum(int(r["criterion_denominator"]) for r in scored),
        by_provenance=slices,
        terminal_errors=terminal_errors,
        requests=len(attempts.exchanges),
        max_calls=maximum,
        failures=[x.response.failure.code for x in attempts.exchanges if x.response.failure],
        label_status="ai_provisional",
        clinical_validation=False,
        release_approval=False,
    )
    (output / "summary.json").write_bytes(canonical(summary))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--policy-sha256", required=True)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--cases-sha256", required=True)
    parser.add_argument("--split", choices=("development", "holdout"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--deadline-seconds", type=int, default=600, choices=range(30, 1801))
    args = parser.parse_args()
    try:
        print(json.dumps(run(args), sort_keys=True))
    except (ValueError, OSError, ImportError, subprocess.SubprocessError) as error:
        parser.error(type(error).__name__ + "; inspect private configuration and source pins")


if __name__ == "__main__":
    main()
