"""Development-only threshold fitting; complete denominators, no held-out refitting."""

from typing import Literal

from agent_harness.contracts import Contract

from cfpb_triage.classifier import eligible
from cfpb_triage.source_contracts import Digest
from cfpb_triage.triage_contracts import Attempt, RouterPolicy, Taxonomy, digest_text


class EvaluatedCase(Contract):
    case_id: Digest
    group_id: Digest
    split: Literal["development", "regression", "holdout"]
    reference_product: str
    reference_issue: str
    provisional_priority: Literal["routine", "elevated", "uncertain"]
    provisional_ambiguity: Literal["clear", "ambiguous"]
    cheap: Attempt
    strong: Attempt


class Metrics(Contract):
    cases: int
    classified: int
    review_required: int
    incorrect_classified: int
    coverage: float
    review_fraction: float
    selective_error: float | None
    elevated_cases: int
    elevated_routed_review: int
    elevated_review_recall: float | None
    priority_evaluable: int
    priority_agreement: float | None
    failed_cases: int
    model_calls: int
    observed_input_tokens: int
    observed_output_tokens: int
    usage_unknown_attempts: int


def correct(row: EvaluatedCase, attempt: Attempt) -> bool:
    p = attempt.prediction
    return bool(
        p
        and p.product == row.reference_product
        and p.issue == row.reference_issue
        and p.priority == row.provisional_priority
        and p.ambiguity == row.provisional_ambiguity
    )


def validate_cases(rows: tuple[EvaluatedCase, ...]) -> None:
    if not rows or len({r.case_id for r in rows}) != len(rows):
        raise ValueError("nonempty unique case population required")
    groups: dict[str, str] = {}
    for row in rows:
        if row.group_id in groups and groups[row.group_id] != row.split:
            raise ValueError("group crosses partitions")
        groups[row.group_id] = row.split
        if row.cheap.route != "cheap" or row.strong.route != "strong":
            raise ValueError("route observations rebound")


def fit_threshold(
    rows: tuple[EvaluatedCase, ...], which: Literal["cheap", "strong"], max_error: float
) -> float:
    feasible = []
    for threshold in (0.0, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 1.0, 1.01):
        admitted = [
            r
            for r in rows
            if eligible(getattr(r, which).prediction, threshold) and not getattr(r, which).failure
        ]
        wrong = sum(not correct(r, getattr(r, which)) for r in admitted)
        if not admitted or wrong / len(admitted) <= max_error:
            feasible.append((-len(admitted), wrong, -threshold, threshold))
    return min(feasible)[3]


def fit(
    rows: tuple[EvaluatedCase, ...],
    taxonomy: Taxonomy,
    *,
    max_error: float = 0.0,
    target_review_fraction: float = 0.5,
) -> RouterPolicy:
    validate_cases(rows)
    if any(r.split != "development" for r in rows):
        raise ValueError("calibration accepts development cases only")
    if not 0 <= max_error <= 1 or not 0 <= target_review_fraction <= 1:
        raise ValueError("bounded calibration objectives required")
    canonical = "\n".join(r.canonical_json() for r in sorted(rows, key=lambda r: r.case_id))
    return RouterPolicy(
        taxonomy_sha256=taxonomy.digest(),
        cheap_threshold=fit_threshold(rows, "cheap", max_error),
        strong_threshold=fit_threshold(rows, "strong", max_error),
        fit_manifest_sha256=digest_text(canonical),
        fit_cases=len(rows),
        max_development_auto_error=max_error,
        target_review_fraction=target_review_fraction,
    )


def measure(
    rows: tuple[EvaluatedCase, ...],
    policy: RouterPolicy,
    mode: Literal["cheap_first", "always_strong"],
) -> Metrics:
    validate_cases(rows)
    classified = wrong = elevated = elevated_review = failed = agreement = evaluable = 0
    calls = input_tokens = output_tokens = unknown = 0
    for row in rows:
        chosen = row.strong
        attempts = [row.strong]
        risk_seen = False
        if mode == "cheap_first":
            chosen = row.cheap
            attempts = [chosen]
            p = chosen.prediction
            risk_seen = bool(p and (p.priority != "routine" or p.ambiguity != "clear"))
            if not chosen.failure and not risk_seen and not eligible(p, policy.cheap_threshold):
                chosen = row.strong
                attempts.append(chosen)
        threshold = policy.cheap_threshold if chosen.route == "cheap" else policy.strong_threshold
        admitted = not chosen.failure and not risk_seen and eligible(chosen.prediction, threshold)
        classified += admitted
        wrong += bool(admitted and not correct(row, chosen))
        if row.provisional_priority == "elevated":
            elevated += 1
            elevated_review += not admitted
        if row.provisional_priority != "uncertain":
            evaluable += 1
            agreement += bool(
                chosen.prediction and chosen.prediction.priority == row.provisional_priority
            )
        failed += any(a.failure is not None for a in attempts)
        for attempt in attempts:
            u = attempt.usage
            if u is not None:
                calls += u.model_calls
                input_tokens += u.input_tokens or 0
                output_tokens += u.output_tokens or 0
            unknown += u is None or u.input_tokens is None or u.output_tokens is None
    n = len(rows)
    return Metrics(
        cases=n,
        classified=classified,
        review_required=n - classified,
        incorrect_classified=wrong,
        coverage=classified / n,
        review_fraction=(n - classified) / n,
        selective_error=wrong / classified if classified else None,
        elevated_cases=elevated,
        elevated_routed_review=elevated_review,
        elevated_review_recall=elevated_review / elevated if elevated else None,
        priority_evaluable=evaluable,
        priority_agreement=agreement / evaluable if evaluable else None,
        failed_cases=failed,
        model_calls=calls,
        observed_input_tokens=input_tokens,
        observed_output_tokens=output_tokens,
        usage_unknown_attempts=unknown,
    )
