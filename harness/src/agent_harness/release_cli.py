"""Explicit pinned recording, comparison and release commands; no baseline promotion."""

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from agent_harness.cases import ManifestPin, load_manifest
from agent_harness.fault_contracts import FaultPlan
from agent_harness.fresh_example import RecordingConfig, UppercaseFactory
from agent_harness.fresh_recording import record_candidate
from agent_harness.release_contracts import (
    BaselineApproval,
    CandidateSpec,
    ReleasePolicy,
    pin,
    verify_sources,
)
from agent_harness.release_evidence import compare_evidence, read_evidence, release_candidate
from agent_harness.trial_example import FileTrialEnvironment
from agent_harness.trials import TrialSchedule, _write_exclusive


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("eval-record", "eval-compare", "eval-release"))
    for name in ("manifest", "manifest-pin", "candidate-spec", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--candidate-spec-sha256", required=True)
    for name in (
        "schedule",
        "composition",
        "source-root",
        "candidate-evidence",
        "baseline-evidence",
        "release-policy",
        "baseline-approval",
        "fault-plan",
    ):
        parser.add_argument("--" + name, type=Path)
    for name in (
        "candidate-evidence-sha256",
        "baseline-evidence-sha256",
        "baseline-spec-sha256",
        "release-policy-sha256",
        "baseline-approval-sha256",
    ):
        parser.add_argument("--" + name)
    args = parser.parse_args(argv)
    required: tuple[str, ...] = (
        ("schedule", "composition", "source_root")
        if args.command == "eval-record"
        else (
            "candidate_evidence",
            "baseline_evidence",
            "release_policy",
            "candidate_evidence_sha256",
            "baseline_evidence_sha256",
            "baseline_spec_sha256",
            "release_policy_sha256",
        )
    )
    if args.command == "eval-release":
        required += ("baseline_approval", "baseline_approval_sha256")
    if any(getattr(args, name) is None for name in required):
        parser.error("missing explicit inputs for " + args.command)
    if args.command == "eval-record" and any(
        getattr(args, name) is not None
        for name in (
            "candidate_evidence",
            "baseline_evidence",
            "baseline_approval",
            "release_policy",
            "candidate_evidence_sha256",
            "baseline_evidence_sha256",
            "baseline_spec_sha256",
            "release_policy_sha256",
            "baseline_approval_sha256",
        )
    ):
        parser.error("recording cannot read previous response evidence or approve a baseline")
    if args.command != "eval-record" and any(
        getattr(args, name) is not None
        for name in (
            "schedule",
            "composition",
        )
    ):
        parser.error("comparison/release cannot dispatch provider recording")
    try:
        loaded = load_manifest(
            args.manifest, ManifestPin.model_validate_json(args.manifest_pin.read_bytes())
        )
        spec = CandidateSpec.model_validate_json(args.candidate_spec.read_bytes())
        if pin(spec) != args.candidate_spec_sha256:
            raise ValueError("candidate differs from external pin")
        plan = (
            FaultPlan.model_validate_json(args.fault_plan.read_bytes()) if args.fault_plan else None
        )
        if args.command == "eval-record":
            config = RecordingConfig.model_validate_json(args.composition.read_bytes())
            factory = UppercaseFactory(spec, config)
            factory.validate()
            factory.verify_runtime_sources(args.source_root)
            schedule = TrialSchedule.model_validate_json(args.schedule.read_bytes())
            if schedule.fault_plan != plan:
                raise ValueError("schedule differs from reviewed fault plan")
            # State root is separate and new; output remains exclusively owned by recorder.
            state_root = args.output.with_name(args.output.name + "-state")
            state_root.mkdir(mode=0o700)
            evidence = record_candidate(
                schedule,
                loaded,
                factory,
                FileTrialEnvironment(state_root),
                args.output,
                candidate=spec,
                candidate_sha256=args.candidate_spec_sha256,
                source_root=args.source_root,
            )
            read_evidence(
                args.output,
                loaded,
                evidence_sha256=pin(evidence),
                candidate_sha256=args.candidate_spec_sha256,
                fault_plan=plan,
            )
            print(
                json.dumps(
                    {
                        "evidence_sha256": pin(evidence),
                        "origin": evidence.origin,
                        "release_decision": "not_performed",
                    }
                )
            )
            return 0
        if args.source_root is not None:
            verify_sources(args.source_root, spec)
        policy = ReleasePolicy.model_validate_json(args.release_policy.read_bytes())
        if pin(policy) != args.release_policy_sha256:
            raise ValueError("release policy differs from reviewed pin")
        candidate = read_evidence(
            args.candidate_evidence,
            loaded,
            evidence_sha256=args.candidate_evidence_sha256,
            candidate_sha256=args.candidate_spec_sha256,
            fault_plan=plan,
        )
        baseline = read_evidence(
            args.baseline_evidence,
            loaded,
            evidence_sha256=args.baseline_evidence_sha256,
            candidate_sha256=args.baseline_spec_sha256,
            fault_plan=plan,
        )
        if args.command == "eval-compare":
            result = json.dumps(
                {
                    "regressed_cases": compare_evidence(
                        baseline, candidate, loaded, policy, fault_plan=plan
                    ),
                    "candidate_sha256": pin(candidate.manifest),
                    "baseline_sha256": pin(baseline.manifest),
                    "baseline_approval": "not_established",
                    "release_decision": "not_performed",
                },
                sort_keys=True,
            )
            allowed = True
        else:
            approval = BaselineApproval.model_validate_json(args.baseline_approval.read_bytes())
            decision = release_candidate(
                baseline,
                candidate,
                loaded,
                policy,
                approval,
                approval_sha256=args.baseline_approval_sha256,
                policy_sha256=args.release_policy_sha256,
                expected_candidate_sha256=args.candidate_spec_sha256,
                now=datetime.now(UTC),
                fault_plan=plan,
            )
            result, allowed = decision.canonical_json(), decision.allowed
        args.output.mkdir(mode=0o700)
        _write_exclusive(args.output / "result.json", result)
        print(
            "Private result written; "
            + (
                "comparison only"
                if args.command == "eval-compare"
                else "release allowed"
                if allowed
                else "release blocked"
            )
        )
        return 0 if allowed else 1
    except (ValueError, OSError) as error:
        print(f"{args.command} failed ({type(error).__name__}); release blocked", file=sys.stderr)
        return 1


if __name__ == "__main__":
    # Reading evidence never needs network. Recording only dispatches its explicit composition.
    if len(sys.argv) > 1 and sys.argv[1] != "eval-record":
        from agent_harness.replay_example import _deny_network

        sys.addaudithook(_deny_network)
    raise SystemExit(main())
