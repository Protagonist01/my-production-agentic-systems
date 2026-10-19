"""Frozen deterministic baselines; provisional risk and consumer references stay distinct."""

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from cfpb_triage.review import (
    Ambiguity,
    BlindItem,
    Review,
    Risk,
    Selection,
    load_json,
    review_summary,
    validate_reviews,
)
from cfpb_triage.source import read_inputs, read_targets, verify_prepared

RULES_VERSION = "cfpb-keyword-baselines-v1"
# Deliberately broad literals, fixed before the first baseline execution. These do
# not handle negation, legal quotation, temporal context or actual consumer harm.
RISK_WORDS = (
    "foreclos",
    "evict",
    "identity theft",
    "stolen",
    "unauthorized",
    "fraud",
    "locked out",
    "cannot access",
    "can't access",
    "rent",
    "food",
)
PRODUCT_RULES = (
    ("mortgage", r"\bmortgage\b|\bforeclos"),
    ("student", r"\bstudent loan\b|\bnelnet\b|\bmohela\b"),
    ("vehicle", r"\bauto loan\b|\bvehicle loan\b|\bcar loan\b"),
    ("prepaid", r"\bprepaid\b"),
    ("card", r"\bcredit card\b"),
    ("management", r"\bcredit repair\b|\bdebt management\b"),
    ("collection", r"\bdebt collect|\bcollection agency\b"),
    ("transfer", r"\bwire transfer\b|\bcrypto|\bmoney transfer\b"),
    ("payday", r"\bpayday\b|\btitle loan\b|\bpersonal loan\b"),
    ("checking", r"\bchecking account\b|\bsavings account\b|\bdebit card\b"),
)
PRODUCT_NAMES = {
    "mortgage": "Mortgage",
    "student": "Student loan",
    "vehicle": "Vehicle loan or lease",
    "prepaid": "Prepaid card",
    "card": "Credit card",
    "management": "Debt or credit management",
    "collection": "Debt collection",
    "transfer": "Money transfer, virtual currency, or money service",
    "payday": "Payday loan, title loan, personal loan, or advance loan",
    "checking": "Checking or savings account",
}
DEFAULT_PRODUCT = "Credit reporting or other personal consumer reports"


def majority(counts: Counter[str]) -> str:
    if not counts:
        raise ValueError("no development labels to fit majority")
    # Lexical tie-break is fixed and independent of regression/holdout targets.
    return min(counts, key=lambda x: (-counts[x], x))


def risk_rules(narrative: str) -> tuple[Risk, Ambiguity]:
    text = narrative.casefold()
    if len(text.strip()) < 80:
        return "uncertain", "ambiguous"
    if any(word in text for word in RISK_WORDS):
        return "elevated", "clear"
    return "routine", "clear"


def product_rules(narrative: str) -> str:
    text = narrative.casefold()
    for key, pattern in PRODUCT_RULES:
        if re.search(pattern, text):
            return PRODUCT_NAMES[key]
    return DEFAULT_PRODUCT


class ClassificationCounts:
    def __init__(self) -> None:
        self.confusion: Counter[tuple[str, str]] = Counter()

    def add(self, expected: str, predicted: str) -> None:
        self.confusion[expected, predicted] += 1

    def report(self) -> dict[str, Any]:
        actual: Counter[str] = Counter()
        predicted: Counter[str] = Counter()
        correct: Counter[str] = Counter()
        for (truth, guess), count in self.confusion.items():
            actual[truth] += count
            predicted[guess] += count
            if truth == guess:
                correct[truth] += count
        n = sum(actual.values())
        slices = []
        f1_values: list[float] = []
        # Union includes predicted-only classes; undefined class precision/recall
        # is null, while the declared macro F1 convention assigns zero F1.
        for label in sorted(set(actual) | set(predicted)):
            tp, support, called = correct[label], actual[label], predicted[label]
            f1 = 2 * tp / (support + called) if support + called else 0.0
            f1_values.append(f1)
            slices.append(
                {
                    "label": label,
                    "support": support,
                    "predicted": called,
                    "correct": tp,
                    "recall": tp / support if support else None,
                    "precision": tp / called if called else None,
                    "f1": f1,
                }
            )
        return {
            "denominator": n,
            "correct": sum(correct.values()),
            "accuracy": sum(correct.values()) / n if n else None,
            "macro_f1": sum(f1_values) / len(f1_values) if f1_values else None,
            "macro_class_policy": "union-of-reference-and-predicted-classes-zero-f1",
            "classes": slices,
        }


def pilot_report(
    items: tuple[BlindItem, ...],
    selections: tuple[Selection, ...],
    reviews: tuple[Review, ...],
    *,
    reviewer_id: str,
) -> dict[str, Any]:
    validate_reviews(items, reviews)
    lookup = {s.case_id: s for s in selections}
    if len(lookup) != len(selections) or set(lookup) != {x.case_id for x in items}:
        raise ValueError("selection and blind case population differ")
    groups: dict[str, str] = {}
    for s in selections:
        if groups.setdefault(s.group_id, s.split) != s.split:
            raise ValueError("review group crosses splits")
    chosen = {r.case_id: r for r in reviews if r.reviewer_id == reviewer_id}
    if len(chosen) != len(items):
        raise ValueError("requested reviewer does not cover every case")
    development = [r for cid, r in chosen.items() if lookup[cid].split == "development"]
    risk_majority = majority(Counter(r.risk for r in development))
    ambiguity_majority = majority(Counter(r.ambiguity for r in development))
    result: dict[str, Any] = {
        "mode": "offline_deterministic",
        "rules_version": RULES_VERSION,
        "label_status": "AI/human provisional reviewer judgments; not adjudicated truth",
        "review": review_summary(items, reviews),
        "fit_split": "development",
        "fit_cases": len(development),
        "majority_risk": risk_majority,
        "majority_ambiguity": ambiguity_majority,
        "outbound_provider_calls": 0,
        "splits": {},
    }
    for split in ("development", "regression", "holdout"):
        split_items = [x for x in items if lookup[x.case_id].split == split]
        baselines = {}
        for name in ("majority", "rules"):
            risk, ambiguity = ClassificationCounts(), ClassificationCounts()
            reviews_called = elevated_support = elevated_captured = 0
            for x in split_items:
                predicted = (
                    (risk_majority, ambiguity_majority)
                    if name == "majority"
                    else risk_rules(x.narrative)
                )
                target = chosen[x.case_id]
                risk.add(target.risk, predicted[0])
                ambiguity.add(target.ambiguity, predicted[1])
                route_review = (
                    predicted[0] in ("elevated", "uncertain") or predicted[1] == "ambiguous"
                )
                reviews_called += route_review
                if target.risk == "elevated":
                    elevated_support += 1
                    elevated_captured += route_review
            baselines[name] = {
                "risk": risk.report(),
                "ambiguity": ambiguity.report(),
                "review_count": reviews_called,
                "review_denominator": len(split_items),
                "review_fraction": reviews_called / len(split_items) if split_items else None,
                "provisional_elevated_support": elevated_support,
                "provisional_elevated_routed_to_review": elevated_captured,
                "provisional_elevated_review_recall": elevated_captured / elevated_support
                if elevated_support
                else None,
            }
        result["splits"][split] = baselines
    return result


def pinned_pilot(
    packet: Path,
    packet_pin: str,
    selection: Path,
    selection_pin: str,
    review_path: Path,
    review_pin: str,
    *,
    reviewer_id: str,
) -> dict[str, Any]:
    items = tuple(BlindItem.model_validate(x) for x in load_json(packet, packet_pin))
    metadata = load_json(selection, selection_pin)
    if metadata["packet_sha256"] != packet_pin:
        raise ValueError("selection is bound to a different blind packet")
    selections = tuple(Selection.model_validate(x) for x in metadata["cases"])
    reviews = tuple(
        Review.model_validate_json(json.dumps(x)) for x in load_json(review_path, review_pin)
    )
    if any(r.guideline != metadata["guideline"] for r in reviews):
        raise ValueError("review guideline differs from selection")
    if metadata.get("guideline_sha256") is not None and any(
        r.guideline_sha256 != metadata["guideline_sha256"] for r in reviews
    ):
        raise ValueError("review guideline bytes differ from selection")
    result = pilot_report(items, selections, reviews, reviewer_id=reviewer_id)
    result["pins"] = {
        "packet": packet_pin,
        "selection": selection_pin,
        "reviews": review_pin,
        "source_manifest": metadata["source_manifest_sha256"],
        "guideline": reviews[0].guideline_sha256,
    }
    return result


def consumer_report(prepared: Path, manifest_pin: str) -> dict[str, Any]:
    """Complete-cohort reference agreement; labels remain consumer selections."""
    manifest = verify_prepared(prepared, manifest_pin)
    products: Counter[str] = Counter()
    per_product: dict[str, Counter[str]] = defaultdict(Counter)
    for t in read_targets(prepared / "evaluator.sqlite"):
        if t.split == "development":
            products[t.product] += 1
            per_product[t.product][t.issue] += 1
    issues = {p: majority(counts) for p, counts in per_product.items()}
    overall_product = majority(products)
    overall = (overall_product, issues[overall_product])
    counts = {
        (split, name, task): ClassificationCounts()
        for split in ("development", "regression", "holdout")
        for name in ("majority", "rules")
        for task in ("product", "product_issue")
    }
    input_rows = read_inputs(prepared / "agent.sqlite")
    target_rows = read_targets(prepared / "evaluator.sqlite")
    for item, target in zip(input_rows, target_rows, strict=True):
        if item.case_id != target.case_id:
            raise ValueError("source input/target inventory differs")
        # Only narrative enters the fixed predictor. Hidden targets affect counters only.
        predicted = product_rules(item.narrative)
        pair = (predicted, issues[predicted]) if predicted in issues else tuple(overall)
        for name, guess in (("majority", tuple(overall)), ("rules", pair)):
            counts[target.split, name, "product"].add(target.product, guess[0])
            counts[target.split, name, "product_issue"].add(
                target.product + "\n" + target.issue, guess[0] + "\n" + guess[1]
            )
    verify_prepared(prepared, manifest_pin)
    return {
        "mode": "offline_deterministic",
        "rules_version": RULES_VERSION,
        "source_manifest_sha256": manifest_pin,
        "prepared_rows": manifest["prepared"]["prepared_rows"],
        "target_status": "consumer-selected references, not independently reviewed truth",
        "fit_split": "development",
        "fit_rows": sum(products.values()),
        "majority_product_issue": overall,
        "outbound_provider_calls": 0,
        "splits": {
            split: {
                name: {
                    task: counts[split, name, task].report()
                    for task in ("product", "product_issue")
                }
                for name in ("majority", "rules")
            }
            for split in ("development", "regression", "holdout")
        },
    }
