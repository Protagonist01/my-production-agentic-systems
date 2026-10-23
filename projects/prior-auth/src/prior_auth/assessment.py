"""Evidence checks for a deliberately narrow national initial-CPAP policy slice."""

import math
import re
from typing import Literal

from prior_auth.contracts import (
    AssessmentResult,
    CandidateAssessment,
    CheckedClaim,
    Claim,
    CriterionId,
    NoteInput,
    Policy,
    Span,
    digest,
)
from prior_auth.redaction import segments

CRITERIA: tuple[CriterionId, ...] = (
    "adult_osa",
    "education",
    "clinical_evaluation",
    "sleep_test",
    "physician_order",
    "severity",
    "event_count",
)
TERMS = {
    "adult_osa": ("age", "adult", "apnea", "osa"),
    "education": ("education", "educated", "instruction", "caregiver"),
    "clinical_evaluation": ("evaluation", "evaluated", "exam"),
    "sleep_test": ("sleep", "psg", "polysomnography", "channels"),
    "physician_order": ("ordered", "order", "supervision", "physician"),
    "severity": ("ahi", "rdi", "sleepiness", "hypertension", "insomnia", "stroke"),
    "event_count": ("hours", "events", "ahi", "rdi"),
}


def retrieve(note: NoteInput, criterion: CriterionId) -> tuple[Span, ...]:
    """Deterministic visible-only recall stage, never evaluator-label driven."""
    matches = tuple(
        s
        for s in segments(note.text)
        if any(word in s.quote.casefold() for word in TERMS[criterion])
    )
    # Bound disclosure and request size; truncation is explicit in the caller's diagnostics.
    return matches[:12]


def _numbers(text: str, pattern: str) -> list[float]:
    values = [float(value) for value in re.findall(pattern, text, flags=re.I)]
    return values if all(math.isfinite(value) for value in values) else []


def supports(criterion: CriterionId, spans: tuple[Span, ...]) -> bool:
    """Conservative transparent support recognizer, not general medical entailment.

    An unrecognized paraphrase remains insufficient even if the model calls it met.
    The model does not get to choose thresholds, units or which policy version applies.
    """
    text = " ".join(s.quote for s in spans).casefold()
    # Fail closed on ambiguity/negation anywhere in the proposed supporting evidence.
    if re.search(
        r"\b(no|not|negative|denies|denied|without|unknown|pending|possible|"
        r"suspected|history of)\b",
        text,
    ):
        return False
    if criterion == "adult_osa":
        ages = _numbers(text, r"(?:age[: ]+|aged\s+)(\d{1,3})\b")
        adult = "adult" in text or (bool(ages) and all(18 <= n <= 120 for n in ages))
        return adult and bool(re.search(r"\bosa\b|obstructive sleep apnea", text))
    if criterion == "education":
        return (
            "cpap" in text
            and bool(re.search(r"\b(education|educated|instruction)\b", text))
            and bool(re.search(r"\b(completed|received|provided)\b", text))
            and ("prior to use" in text or "before use" in text)
        )
    if criterion == "clinical_evaluation":
        return (
            "clinical evaluation" in text
            and "completed" in text
            and ("osa" in text or "obstructive sleep apnea" in text)
        )
    if criterion == "sleep_test":
        return "positive" in text and (
            "attended polysomnography" in text
            or "attended psg" in text
            or "type ii home sleep test" in text
            or "type iii home sleep test" in text
            or (
                "type iv home sleep test" in text
                and bool(re.search(r"(?:[3-9]|\d{2,}) channels", text))
            )
        )
    if criterion == "physician_order":
        return (
            "sleep test" in text
            and "ordered" in text
            and "treating physician" in text
            and "physician supervision" in text
        )
    rates = _numbers(text, r"\b(?:ahi|rdi)\s*[:=]?\s*(\d+(?:\.\d+)?)\s*events?/(?:hour|h)\b")
    if not rates or len(set(rates)) != 1:
        return False
    rate = rates[0]
    if criterion == "severity":
        symptom = any(
            word in text
            for word in (
                "excessive daytime sleepiness",
                "impaired cognition",
                "mood disorder",
                "insomnia",
                "hypertension",
                "ischemic heart disease",
                "stroke",
            )
        )
        return rate >= 15 or (5 <= rate <= 14 and symptom)
    hours = _numbers(text, r"(\d+(?:\.\d+)?)\s*hours? of (?:recorded sleep|recording)")
    if not hours or len(set(hours)) != 1 or hours[0] <= 0:
        return False
    if hours[0] >= 2:
        return True
    counts = _numbers(text, r"(\d+)\s*total (?:recorded )?events")
    return bool(counts) and len(set(counts)) == 1 and counts[0] >= rate * 2


def check_claim(note: NoteInput, claim: Claim) -> CheckedClaim:
    try:
        for span in claim.evidence:
            span.require(note.text)
            if "█" in span.quote:
                raise ValueError("redacted content is not supporting evidence")
    except ValueError:
        return CheckedClaim(
            criterion_id=claim.criterion_id,
            state="insufficient",
            evidence=(),
            reason="citation_integrity_failed",
        )
    negatives = {
        "adult_osa": r"\b(?:osa|obstructive sleep apnea) (?:is )?(?:absent|ruled out)\b",
        "education": r"\bcpap education (?:was )?not (?:completed|provided|received)\b",
        "clinical_evaluation": r"\bclinical evaluation (?:was )?not completed\b",
        "sleep_test": r"\bsleep test (?:was )?not performed\b",
        "physician_order": r"\bsleep test (?:was )?not ordered\b",
    }
    negative = negatives.get(claim.criterion_id)
    cited = " ".join(s.quote for s in claim.evidence)
    # Scan the entire visible note so selecting only a positive span cannot hide
    # a separately documented contradiction in this supported grammar.
    positive = supports(claim.criterion_id, claim.evidence)
    if positive:
        for span in claim.evidence:
            # A quote beginning inside a negative sentence must not remove its
            # qualifier. Bound context to the same line/sentence, not other visits.
            boundary = max(
                note.text.rfind("\n", 0, span.start),
                note.text.rfind(". ", 0, span.start),
                note.text.rfind(";", 0, span.start),
            )
            prefix = note.text[boundary + 1 : span.start]
            if re.search(r"\b(no|not|negative|denies|without|suspected|possible)\b", prefix, re.I):
                return CheckedClaim(
                    criterion_id=claim.criterion_id,
                    state="insufficient",
                    evidence=claim.evidence,
                    reason="omitted_negative_context",
                )
    if positive and claim.criterion_id in ("severity", "event_count"):
        visible_rates = _numbers(
            note.text,
            r"\b(?:ahi|rdi)\s*[:=]?\s*(\d+(?:\.\d+)?)\s*events?/(?:hour|h)\b",
        )
        if len(set(visible_rates)) > 1:
            return CheckedClaim(
                criterion_id=claim.criterion_id,
                state="conflict",
                evidence=claim.evidence,
                reason="conflicting_visible_rates",
            )
    if positive and negative and re.search(negative, note.text, re.I):
        return CheckedClaim(
            criterion_id=claim.criterion_id,
            state="conflict",
            evidence=claim.evidence,
            reason="contradictory_visible_evidence",
        )
    if claim.state == "not_met" and negative and re.search(negative, cited, re.I):
        return CheckedClaim(
            criterion_id=claim.criterion_id,
            state="not_met",
            evidence=claim.evidence,
            reason="recognized_explicit_negative",
        )
    if claim.state == "conflict":
        return CheckedClaim(
            criterion_id=claim.criterion_id,
            state="conflict",
            evidence=claim.evidence,
            reason="candidate_conflict_requires_review",
        )
    if claim.state == "met" and claim.evidence and positive:
        return CheckedClaim(
            criterion_id=claim.criterion_id,
            state="met",
            evidence=claim.evidence,
            reason="recognized_policy_support",
        )
    # A model's unsupported assertion never becomes a verified negative or positive finding.
    return CheckedClaim(
        criterion_id=claim.criterion_id,
        state="insufficient",
        evidence=claim.evidence,
        reason="missing_or_unrecognized_support",
    )


def assess(
    note: NoteInput, policy: Policy, candidate: CandidateAssessment | None
) -> AssessmentResult:
    note = NoteInput.model_validate_json(note.canonical_json())
    policy = Policy.model_validate_json(policy.canonical_json())
    retrieval_failed = (
        note.policy_id != policy.policy_id
        or note.policy_sha256 != digest(policy.canonical_json())
        or note.service_date < policy.effective_from
        or (policy.effective_until is not None and note.service_date >= policy.effective_until)
        or note.use != "initial"
    )
    bad_candidate = candidate is None
    values: dict[CriterionId, Claim] = {}
    if candidate is not None:
        candidate = CandidateAssessment.model_validate_json(candidate.canonical_json())
        bad_candidate = (
            candidate.case_id != note.case_id
            or candidate.note_sha256 != note.note_sha256
            or candidate.policy_sha256 != note.policy_sha256
            or len({c.criterion_id for c in candidate.claims}) != len(candidate.claims)
        )
        values = {c.criterion_id: c for c in candidate.claims}
    checked = tuple(
        check_claim(note, values[key])
        if not retrieval_failed and not bad_candidate and key in values
        else CheckedClaim(
            criterion_id=key, state="insufficient", evidence=(), reason="missing_or_invalid_input"
        )
        for key in CRITERIA
    )
    disposition: Literal[
        "evidence_complete_for_review", "request_information", "qualified_review"
    ] = (
        "qualified_review"
        if retrieval_failed or bad_candidate or any(c.state == "conflict" for c in checked)
        else (
            "evidence_complete_for_review"
            if all(c.state == "met" for c in checked)
            else "request_information"
        )
    )
    return AssessmentResult(
        case_id=note.case_id,
        note_sha256=note.note_sha256,
        policy_sha256=note.policy_sha256,
        claims=checked,
        disposition=disposition,
        retrieval_failure=retrieval_failed,
        assessment_failure=bad_candidate,
    )
