"""Offline baselines and calibration; never dispatch a provider or fit holdout."""

from collections import defaultdict
from typing import Annotated

from agent_harness.contracts import WireContract
from agent_harness.scorecard_stats import binomial_bounds
from pydantic import Field

from cfpb_triage.evaluation_v2 import Observation, Reference, correct, validate_groups
from cfpb_triage.scope_routing import ScopePolicy


class OperatingLimits(WireContract):
    maximum_group_error_upper: Annotated[float, Field(gt=0, lt=1)]
    minimum_automatic_families: Annotated[int, Field(ge=1)]
    maximum_review_fraction: Annotated[float, Field(ge=0, le=1)]


def baseline(case: Reference, *, always_review: bool) -> Observation:
    # Rules deliberately use only text, never the reference fields.
    text = case.text.casefold()
    pair = None
    if "credit card" in text and "billing dispute" in text:
        pair = ("Credit card", "Billing dispute")
    hold = any(word in text for word in ("not ", "food", "today", "ignore", "secret", "maybe"))
    automatic = bool(pair and not always_review and not hold)
    # An intentionally weak lexical comparator. Relevance/risk remain separately assessed.
    return Observation(
        case_id=case.case_id,
        variant="always_review" if always_review else "rules",
        trial=1,
        action="classified" if automatic else "review_required",
        scope="in_scope" if pair and not always_review else None,
        product=pair[0] if pair and not always_review else None,
        issue=pair[1] if pair and not always_review else None,
        priority="routine" if automatic else "uncertain",
        ambiguity="clear" if automatic else "ambiguous",
        confidence=0.5 if automatic else None,
        evidence_exact=True if automatic else None,
    )


def calibrate(
    cases: tuple[Reference, ...],
    rows: tuple[Observation, ...],
    limits: OperatingLimits,
    *,
    trials: int = 1,
) -> dict[str, object]:
    validate_groups(cases)
    if not cases or any(c.split != "calibration" for c in cases):
        raise ValueError("threshold fitting requires calibration-only references")
    by_id = {c.case_id: c for c in cases}
    if len({(r.case_id, r.variant, r.trial) for r in rows}) != len(rows):
        raise ValueError("duplicate observation")
    if any(r.case_id not in by_id for r in rows) or len({r.variant for r in rows}) != 1:
        raise ValueError("one pinned comparator and known case IDs required")
    if rows[0].variant == "cheap_first":
        raise ValueError("cascade fitting requires separate per-stage observations")
    # Repeated trials never increase independent family support.
    curve = []
    feasible = []
    if not 1 <= trials <= 100 or any(r.trial > trials for r in rows):
        raise ValueError("invalid scheduled trial count")
    expected_trials = set(range(1, trials + 1))
    complete = bool(rows) and all(
        any(r.case_id == c.case_id and r.trial == t for r in rows)
        for c in cases
        for t in expected_trials
    )
    for threshold in (0.0, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 1.0, 1.01):
        admitted = [
            r
            for r in rows
            if r.failure is None
            and r.scope == "in_scope"
            and r.product is not None
            and r.evidence_exact is True
            and r.priority == "routine"
            and r.ambiguity == "clear"
            and r.confidence is not None
            and r.confidence >= threshold
            and r.scope_confidence is not None
            and r.scope_confidence >= threshold
        ]
        families: dict[str, bool] = defaultdict(bool)
        critical = any(r.unauthorized_write is True or r.disclosure is True for r in rows)
        for r in admitted:
            c = by_id[r.case_id]
            families[c.family] |= not correct(c, r)
            critical |= c.must_review or r.unauthorized_write is True or r.disclosure is True
        _, upper = binomial_bounds(sum(families.values()), len(families))
        coverage = len(admitted) / (len(cases) * len(expected_trials)) if expected_trials else 0.0
        meets = (
            complete
            and not critical
            and len(families) >= limits.minimum_automatic_families
            and upper is not None
            and upper <= limits.maximum_group_error_upper
            and 1 - coverage <= limits.maximum_review_fraction
            and all(r.unauthorized_write is False and r.disclosure is False for r in rows)
        )
        point = {
            "threshold": threshold,
            "coverage": coverage,
            "review_fraction": 1 - coverage,
            "automatic_families": len(families),
            "group_error_upper": upper,
            "critical": critical,
            "meets_constraints": meets,
        }
        curve.append(point)
        if meets:
            feasible.append(point)
    chosen = max(feasible, key=lambda p: (p["coverage"], p["threshold"])) if feasible else None
    return {
        "curve": curve,
        "selected": chosen,
        "complete": complete,
        "qualified_for_release": False,
        "uncertainty": "conditional independent-family binomial; not distribution-free",
        "reliability": reliability(cases, rows),
    }


def reliability(cases: tuple[Reference, ...], rows: tuple[Observation, ...]) -> dict[str, object]:
    by_id = {c.case_id: c for c in cases}
    if any(r.case_id not in by_id for r in rows):
        raise ValueError("unknown reliability case")
    bins = []
    for low in range(0, 10):
        selected = [
            r
            for r in rows
            if r.confidence is not None
            and low / 10 <= r.confidence < ((low + 1) / 10 if low < 9 else 1.01)
        ]
        bins.append(
            {
                "lower": low / 10,
                "n": len(selected),
                "mean_self_confidence": sum(
                    r.confidence for r in selected if r.confidence is not None
                )
                / len(selected)
                if selected
                else None,
                "observed_composite_accuracy": sum(correct(by_id[r.case_id], r) for r in selected)
                / len(selected)
                if selected
                else None,
            }
        )
    return {
        "bins": bins,
        "missing_confidence": sum(r.confidence is None for r in rows),
        "interpretation": "self-confidence ranking diagnostic, not calibrated probability",
    }


def drift(reference: tuple[str, ...], current: tuple[str, ...]) -> dict[str, object]:
    if not reference or not current:
        return {"total_variation": None, "status": "insufficient_data"}
    labels = set(reference) | set(current)
    distance = 0.5 * sum(
        abs(reference.count(x) / len(reference) - current.count(x) / len(current)) for x in labels
    )
    return {
        "total_variation": distance,
        "reference_n": len(reference),
        "current_n": len(current),
        "status": "descriptive_only_no_automatic_threshold_change",
    }


def review_only(policy: ScopePolicy) -> ScopePolicy:
    """Rollback candidate; callers must pin its NEW hash, never mutate historical policy."""
    return policy.model_copy(
        update={"cheap_threshold": 1.01, "strong_threshold": 1.01, "scope_threshold": 1.01}
    )


def calibrate_cascade(
    cases: tuple[Reference, ...],
    rows: tuple[Observation, ...],
    limits: OperatingLimits,
    *,
    trials: int = 1,
    scope_threshold: float,
) -> dict[str, object]:
    """Replay a fixed cheap-first routing rule on BOTH stage observations, not final-only rows.

    Machine costs are counterfactual known sums; this is not an end-to-end timing study.
    No model is dispatched and no holdout labels fit any threshold.
    """
    validate_groups(cases)
    if (
        not cases
        or any(c.split != "calibration" for c in cases)
        or not 1 <= trials <= 100
        or not 0 <= scope_threshold <= 1.01
    ):
        raise ValueError("bounded calibration-only cascade required")
    keys = {
        (c.case_id, v, t)
        for c in cases
        for v in ("cheap_only", "strong_only")
        for t in range(1, trials + 1)
    }
    indexed = {(r.case_id, r.variant, r.trial): r for r in rows}
    if len(indexed) != len(rows) or not set(indexed) <= keys:
        raise ValueError("duplicate or unscheduled cascade stage")
    complete = len(indexed) == len(keys)
    curve = []
    feasible: list[tuple[float, int, int]] = []
    for cheap_threshold in (0.0, 0.5, 0.7, 0.8, 0.9, 0.95, 1.0, 1.01):
        for strong_threshold in (0.0, 0.5, 0.7, 0.8, 0.9, 0.95, 1.0, 1.01):
            admitted: list[tuple[Reference, Observation]] = []
            selected: list[Observation] = []
            for c in cases:
                for t in range(1, trials + 1):
                    cheap = indexed.get((c.case_id, "cheap_only", t))
                    if cheap is None:
                        continue
                    selected.append(cheap)
                    if cheap.failure:
                        continue
                    if cheap.scope == "out_of_scope":
                        if (
                            cheap.scope_confidence is not None
                            and cheap.scope_confidence >= scope_threshold
                        ):
                            admitted.append((c, cheap))
                        continue
                    if (
                        cheap.scope != "in_scope"
                        or cheap.product is None
                        or cheap.evidence_exact is not True
                        or cheap.priority != "routine"
                        or cheap.ambiguity != "clear"
                    ):
                        continue
                    if (
                        cheap.confidence is not None
                        and cheap.confidence >= cheap_threshold
                        and cheap.scope_confidence is not None
                        and cheap.scope_confidence >= scope_threshold
                    ):
                        admitted.append((c, cheap))
                        continue
                    strong = indexed.get((c.case_id, "strong_only", t))
                    if strong is None:
                        continue
                    selected.append(strong)
                    if (
                        strong.failure is None
                        and strong.scope == "in_scope"
                        and strong.product is not None
                        and strong.evidence_exact is True
                        and strong.priority == "routine"
                        and strong.ambiguity == "clear"
                        and strong.confidence is not None
                        and strong.confidence >= strong_threshold
                        and strong.scope_confidence is not None
                        and strong.scope_confidence >= scope_threshold
                    ):
                        admitted.append((c, strong))
            groups: dict[str, bool] = defaultdict(bool)
            for c, r in admitted:
                groups[c.family] |= not correct(c, r)
            _, upper = binomial_bounds(sum(groups.values()), len(groups))
            critical = any(
                c.must_review or r.unauthorized_write is True or r.disclosure is True
                for c, r in admitted
            )
            critical |= any(r.unauthorized_write is True or r.disclosure is True for r in selected)
            coverage = len(admitted) / (len(cases) * trials)
            currencies = {r.currency for r in selected if r.cost is not None}
            cost_known = all(r.cost is not None for r in selected) and len(currencies) == 1
            meets = (
                complete
                and not critical
                and len(groups) >= limits.minimum_automatic_families
                and upper is not None
                and upper <= limits.maximum_group_error_upper
                and 1 - coverage <= limits.maximum_review_fraction
                and all(r.unauthorized_write is False and r.disclosure is False for r in selected)
            )
            point = {
                "cheap_threshold": cheap_threshold,
                "strong_threshold": strong_threshold,
                "scope_threshold": scope_threshold,
                "coverage": coverage,
                "review_fraction": 1 - coverage,
                "automatic_families": len(groups),
                "group_error_upper": upper,
                "critical": critical,
                "selected_stage_requests": len(selected),
                "counterfactual_cost_sum": sum(r.cost for r in selected if r.cost is not None)
                if complete and cost_known
                else None,
                "unknown_stage_costs": sum(r.cost is None for r in selected),
                "counterfactual_cost_currency": next(iter(currencies)) if cost_known else None,
                "meets_constraints": meets,
            }
            curve.append(point)
            if meets:
                feasible.append((coverage, -len(selected), len(curve) - 1))
    chosen = curve[max(feasible)[2]] if feasible else None
    return {
        "curve": curve,
        "selected": chosen,
        "complete": complete,
        "qualified_for_release": False,
        "interpretation": "counterfactual calibration only",
    }
