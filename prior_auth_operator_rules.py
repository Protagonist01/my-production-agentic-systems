"""Development-only conservative variant. Preserve the original rules and captures."""

import re
from decimal import Decimal

from prior_auth.assessment import CRITERIA
from prior_auth.contracts import CandidateAssessment, CriterionId, NoteInput, Policy, digest

from prior_auth_scorecards import rules

VERSION = "prior-auth-conflict-rules-v3"
RATE = re.compile(r"\b(?:ahi|rdi)\s*[:=]?\s*(\d+(?:\.\d+)?)\s*events?/(?:hour|h)\b", re.I)


def conflict_rules(
    note: NoteInput, policy: Policy, keys: tuple[CriterionId, ...] = CRITERIA
) -> CandidateAssessment | None:
    note = NoteInput.model_validate_json(note.canonical_json())
    policy = Policy.model_validate_json(policy.canonical_json())
    if not keys or len(set(keys)) != len(keys) or set(keys) - set(CRITERIA):
        raise ValueError("unique known criteria required")
    if note.provenance != "invented" or note.policy_sha256 != digest(policy.canonical_json()):
        # This variant is not qualified for published/clinical notes or different policies.
        return None
    if len({Decimal(value) for value in RATE.findall(note.text)}) > 1:
        # Distinct visible hourly rates need review; no inference about which is correct.
        return None
    proposed = rules(note, policy)
    return proposed.model_copy(
        update={"claims": tuple(c for c in proposed.claims if c.criterion_id in keys)}
    )
