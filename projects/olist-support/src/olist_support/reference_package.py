"""Audit pinned reference artifacts without executing a candidate or certifying language."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Annotated

from agent_harness.contracts import Contract, NonEmpty
from pydantic import Field, TypeAdapter

from olist_support.evaluation_oracle import OracleFacts, OracleRequest, evaluate_policy
from olist_support.policy_cases import Digest, PolicyCases


class CaseMetadata(Contract):
    case_id: Digest
    language_family: NonEmpty
    slices: Annotated[tuple[NonEmpty, ...], Field(min_length=1)]
    recovery_required: bool
    recovery_kind: NonEmpty | None


def pinned(path: Path, expected: str) -> bytes:
    """Check the exact file, not a reserialized approximation of its content."""
    if path.is_symlink():
        raise ValueError("reference artifact must not be a symlink")
    payload = path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != expected:
        raise ValueError("reference artifact differs from its external pin")
    return payload


def audit(
    cases_payload: bytes,
    metadata_payload: bytes,
    *,
    required_holdout_slices: frozenset[str],
) -> dict[str, object]:
    """Safe aggregate diagnostic only; expectations and intent remain evaluator inputs.

    Policy agreement is conditional on the supplied structured intent/amount/facts.
    Neither the runtime policy nor any model is called. Text meaning, reason wording,
    state execution, semantic family independence and recovery remain unassessed.
    """
    if not required_holdout_slices or any(not s.strip() for s in required_holdout_slices):
        raise ValueError("explicit nonempty holdout requirements required")
    cases = PolicyCases.model_validate_json(cases_payload)
    metadata = TypeAdapter(tuple[CaseMetadata, ...]).validate_json(metadata_payload)
    ids = {entry.input.case_id for entry in cases.entries}
    if len(metadata) != len(ids) or {m.case_id for m in metadata} != ids:
        raise ValueError("metadata must cover every case exactly once")
    by_id = {m.case_id: m for m in metadata}
    families: dict[str, str] = {}
    source_groups: dict[str, set[str]] = {}
    holdout_slices: set[str] = set()
    issues: Counter[str] = Counter()
    agreement = errors = recovery = 0
    for entry in cases.entries:
        m = by_id[entry.input.case_id]
        if families.setdefault(m.language_family, entry.split) != entry.split:
            raise ValueError("declared language family crosses splits")
        if len(m.slices) != len(set(m.slices)):
            raise ValueError("duplicate slice declaration")
        if m.recovery_required != (m.recovery_kind is not None):
            raise ValueError("recovery requirement and kind disagree")
        source_groups.setdefault(entry.split, set()).add(entry.group_id)
        if entry.split == "holdout":
            holdout_slices.update(m.slices)
        recovery += m.recovery_required
        if entry.input.order.source_manifest_sha256 != cases.source_manifest_sha256:
            raise ValueError("case source manifest differs from packet manifest")
        confirmation = entry.input.confirmation
        facts = (
            None
            if confirmation is None
            else OracleFacts.model_validate(confirmation.model_dump(exclude={"provenance"}))
        )
        request = OracleRequest(
            intent=entry.input.request.intent,
            requested_minor=entry.input.request.requested_minor,
        )
        try:
            decision = evaluate_policy(entry.input.order, request, facts)
        except (ValueError, PermissionError):
            errors += 1
            continue
        matched = (decision.action, decision.amount_minor) == (
            entry.expected.action,
            entry.expected.amount_minor,
        )
        agreement += matched
        if not matched:
            issues["action_or_amount_disagreement"] += 1
    missing = sorted(required_holdout_slices - holdout_slices)
    return {
        "version": "olist-reference-package-audit-v1",
        "evaluator_sha256": hashlib.sha256(cases_payload).hexdigest(),
        "metadata_sha256": hashlib.sha256(metadata_payload).hexdigest(),
        "cases": len(cases.entries),
        "source_groups": len({e.group_id for e in cases.entries}),
        "source_groups_by_split": {s: len(g) for s, g in sorted(source_groups.items())},
        "declared_language_families": len(families),
        "label_provenance": dict(sorted(Counter(e.reviewer_kind for e in cases.entries).items())),
        "structured_action_amount_agreement": agreement,
        "oracle_errors": errors,
        "disagreements": dict(issues),
        "declared_holdout_slices": sorted(holdout_slices),
        "missing_declared_holdout_slices": missing,
        "declared_recovery_cases": recovery,
        "structural_checks_passed": errors == 0 and not issues and not missing,
        "semantic_labels_validated": False,
        "reason_labels_validated": False,
        "family_independence_validated": False,
        "recovery_executed": False,
        "fresh_candidate_evaluated": False,
        "provider_calls": 0,
        "release_allowed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--cases-sha256", required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--metadata-sha256", required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--profile-sha256", required=True)
    args = parser.parse_args()
    profile = json.loads(pinned(args.profile, args.profile_sha256))
    if profile["agent"] != "olist":
        raise ValueError("Olist profile required")
    required = TypeAdapter(tuple[NonEmpty, ...]).validate_python(profile["required_holdout_slices"])
    report = audit(
        pinned(args.cases, args.cases_sha256),
        pinned(args.metadata, args.metadata_sha256),
        required_holdout_slices=frozenset(required),
    )
    report["profile_sha256"] = args.profile_sha256
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["structural_checks_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
