"""Private fixed-denominator C5 reports; no provider calls or release approval."""

import json
from collections import Counter
from typing import Literal

from agent_harness.contracts import Contract, NonEmpty
from agent_harness.evaluation_population import ratio, validate_matrix
from agent_harness.evaluation_standards import Review
from agent_harness.release_contracts import pin

from cfpb_triage.source_contracts import ComplaintInput, Digest, Split
from cfpb_triage.triage_contracts import Decision, Prediction, RouterPolicy, Taxonomy, digest_text


class ReferenceCase(Contract):
    complaint: ComplaintInput
    group_id: Digest
    split: Split
    source_kind: Literal["original", "hybrid", "synthetic"]
    product: NonEmpty
    issue: NonEmpty
    priority: Literal["routine", "elevated", "uncertain"]
    ambiguity: Literal["clear", "ambiguous"]
    label_review: Review | None = None
    masking_review_ref: NonEmpty | None = None


class EvaluationPlan(Contract):
    version: Literal["cfpb-release-report-v1"] = "cfpb-release-report-v1"
    source_manifest_sha256: Digest
    taxonomy: Taxonomy
    policy: RouterPolicy
    cases: tuple[ReferenceCase, ...]
    trial_ids: tuple[NonEmpty, ...]


class Observation(Contract):
    case_id: Digest
    trial_id: NonEmpty
    decision: Decision | None = None


def _admitted(prediction: Prediction | None, threshold: float) -> bool:
    return bool(
        prediction
        and prediction.product is not None
        and prediction.priority == "routine"
        and prediction.ambiguity == "clear"
        and prediction.confidence >= threshold
    )


def _valid(case: ReferenceCase, decision: Decision, plan: EvaluationPlan) -> bool:
    """Independent route/path oracle; does not call production route or eligible."""
    if not decision.attempts:
        return False
    prediction = None
    accepted = risk = False
    for index, attempt in enumerate(decision.attempts):
        expected_route = "strong" if decision.mode == "always_strong" or index else "cheap"
        if attempt.route != expected_route or (index and decision.mode == "always_strong"):
            return False
        if attempt.failure:
            if attempt.prediction is not None or index != len(decision.attempts) - 1:
                return False
            break
        prediction = attempt.prediction
        if prediction is None:
            return False
        try:
            prediction.check(case.complaint, plan.taxonomy)
        except ValueError:
            return False
        risk |= prediction.priority != "routine" or prediction.ambiguity != "clear"
        threshold = (
            plan.policy.cheap_threshold
            if attempt.route == "cheap"
            else plan.policy.strong_threshold
        )
        accepted = _admitted(prediction, threshold) and not risk
        if (accepted or risk) and index != len(decision.attempts) - 1:
            return False
    failed = any(a.failure is not None for a in decision.attempts)
    if (
        not failed
        and not accepted
        and not risk
        and decision.mode == "cheap_first"
        and len(decision.attempts) != 2
    ):
        return False
    reason = (
        "supported_route"
        if accepted
        else "model_failure"
        if failed
        else "uncertain_or_high_priority"
        if risk
        else "below_threshold"
    )
    return (
        decision.prediction == prediction
        and decision.reason == reason
        and decision.outcome == ("classified" if accepted else "review_required")
    )


def _classification(expected: list[str], predicted: list[str | None]) -> dict[str, object]:
    classes = sorted(set(expected) | {p for p in predicted if p is not None})
    scores = {}
    for name in classes:
        support = expected.count(name)
        emitted = predicted.count(name)
        tp = sum(a == b == name for a, b in zip(expected, predicted, strict=True))
        scores[name] = {
            "support": support,
            "predicted": emitted,
            "true_positive": tp,
            "f1": 2 * tp / (support + emitted) if support + emitted else 0.0,
        }
    return {
        "macro_f1": sum(float(s["f1"]) for s in scores.values()) / len(scores) if scores else None,
        "classes": scores,
        "scheduled": len(expected),
    }


def evaluate(plan: EvaluationPlan, observations: tuple[Observation, ...]) -> dict[str, object]:
    plan = EvaluationPlan.model_validate_json(plan.canonical_json())
    observations = tuple(Observation.model_validate_json(o.canonical_json()) for o in observations)
    ids = tuple(c.complaint.case_id for c in plan.cases)
    validate_matrix(ids, plan.trial_ids, tuple((o.case_id, o.trial_id) for o in observations))
    if (
        plan.taxonomy.source_manifest != plan.source_manifest_sha256
        or plan.policy.taxonomy_sha256 != plan.taxonomy.digest()
    ):
        raise ValueError("CFPB taxonomy/policy/source binding differs")
    groups: dict[str, set[str]] = {}
    for case in plan.cases:
        groups.setdefault(case.group_id, set()).add(case.split)
    if any(len(splits) != 1 for splits in groups.values()):
        raise ValueError("CFPB source group crosses splits")
    lookup = {(o.case_id, o.trial_id): o for o in observations}
    for case in plan.cases:
        for trial in plan.trial_ids:
            o = lookup.get((case.complaint.case_id, trial))
            d = o.decision if o else None
            if d and (
                d.case_id != case.complaint.case_id
                or d.narrative_sha256 != digest_text(case.complaint.narrative)
                or d.taxonomy_sha256 != plan.taxonomy.digest()
                or d.policy_sha256 != pin(plan.policy)
            ):
                raise ValueError("CFPB decision belongs to different input/policy")

    def measure(cases: tuple[ReferenceCase, ...]) -> dict[str, object]:
        counts: Counter[str] = Counter()
        products, product_predictions, pairs, pair_predictions = [], [], [], []
        for case in cases:
            for trial in plan.trial_ids:
                counts["scheduled"] += 1
                required = case.priority != "routine" or case.ambiguity != "clear"
                counts["required_review"] += required
                counts["eligible"] += not required
                counts["elevated"] += case.priority == "elevated"
                o = lookup.get((case.complaint.case_id, trial))
                d = o.decision if o else None
                valid = bool(d and _valid(case, d, plan))
                failed = bool(d and any(a.failure for a in d.attempts))
                counts["missing"] += d is None
                counts["invalid"] += d is not None and not valid
                counts["failed"] += failed
                resolved = valid and not failed
                counts["unresolved"] += not resolved
                p = d.prediction if d and resolved else None
                counts["priority_correct"] += bool(p and p.priority == case.priority)
                counts["ambiguity_correct"] += bool(p and p.ambiguity == case.ambiguity)
                classified = bool(d and resolved and d.outcome == "classified")
                reviewed = bool(d and resolved and d.outcome == "review_required")
                counts["classified"] += classified
                claimed = bool(d and d.outcome == "classified")
                counts["claimed_classified"] += claimed
                counts["reviewed"] += reviewed
                # Invalid path claims cannot conceal a high-risk auto classification.
                counts["missed_review"] += required and claimed
                counts["unnecessary_review"] += not required and reviewed
                counts["elevated_reviewed"] += case.priority == "elevated" and reviewed
                counts["incorrect_classified"] += claimed and not (
                    classified
                    and p
                    and (p.product, p.issue, p.priority, p.ambiguity)
                    == (case.product, case.issue, case.priority, case.ambiguity)
                )
                products.append(case.product)
                product_predictions.append(p.product if p else None)
                pairs.append(json.dumps((case.product, case.issue), ensure_ascii=False))
                pair_predictions.append(
                    json.dumps((p.product, p.issue), ensure_ascii=False)
                    if p and p.product and p.issue
                    else None
                )
        n = counts["scheduled"]
        return {
            "cases": len(cases),
            "source_groups": len({c.group_id for c in cases}),
            **{
                k: counts[k]
                for k in (
                    "scheduled",
                    "classified",
                    "claimed_classified",
                    "reviewed",
                    "required_review",
                    "eligible",
                    "missing",
                    "invalid",
                    "failed",
                    "unresolved",
                    "incorrect_classified",
                    "missed_review",
                    "unnecessary_review",
                    "elevated",
                    "elevated_reviewed",
                    "priority_correct",
                    "ambiguity_correct",
                )
            },
            "review_fraction": ratio(counts["reviewed"], n),
            "missed_review_rate": ratio(counts["missed_review"], counts["required_review"]),
            "unnecessary_review_rate": ratio(counts["unnecessary_review"], counts["eligible"]),
            "elevated_review_recall": ratio(counts["elevated_reviewed"], counts["elevated"]),
            "selective_error": ratio(counts["incorrect_classified"], counts["claimed_classified"]),
            "product": _classification(products, product_predictions),
            "product_issue_pair": _classification(pairs, pair_predictions),
        }

    return {
        "version": plan.version,
        "plan_sha256": pin(plan),
        "release_allowed": False,
        "all": measure(plan.cases),
        "splits": {
            s: measure(tuple(c for c in plan.cases if c.split == s))
            for s in ("development", "regression", "holdout")
        },
        "source_kinds": {
            s: measure(tuple(c for c in plan.cases if c.source_kind == s))
            for s in ("original", "hybrid", "synthetic")
        },
        "unreviewed_labels": sum(
            c.label_review is None or c.label_review.kind != "qualified_blind" for c in plan.cases
        ),
        "missing_masking_reviews": sum(c.masking_review_ref is None for c in plan.cases),
        "limitations": (
            "Reference-relative metrics, not verified harm or population accuracy. "
            "Missing/failed/invalid trials remain unresolved; failure review is not "
            "successful risk routing. Privacy, durable review, H10 fresh evidence, "
            "qualified review, uncertainty and release audit remain separate gates."
        ),
    }
