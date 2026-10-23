"""Distribution diagnostics; heuristic language signals are not verified language labels."""

import re
from collections import Counter
from typing import Any

from agent_harness.contracts import Contract


class Profile(Contract):
    cases: int
    categories: dict[str, int]
    lengths: dict[str, int]
    languages: dict[str, int]
    masking: dict[str, int]
    models: dict[str, int]
    providers: dict[str, int]


def profile(rows: list[dict[str, Any]]) -> Profile:
    categories: Counter[str] = Counter()
    lengths: Counter[str] = Counter()
    languages: Counter[str] = Counter()
    masking: Counter[str] = Counter()
    models: Counter[str] = Counter()
    providers: Counter[str] = Counter()
    for row in rows:
        text = row["complaint"]["narrative"]
        result = row.get("result") or {}
        prediction = result.get("prediction") or {}
        categories[prediction.get("product") or "unresolved"] += 1
        lengths["short" if len(text) < 500 else "medium" if len(text) < 2500 else "long"] += 1
        # Explicitly diagnostic marker mix: no demographic/language truth claim.
        folded = " " + text.casefold() + " "
        spanish = sum(
            folded.count(word) for word in (" el ", " la ", " que ", " mi ", " cuenta ", " banco ")
        )
        english = sum(
            folded.count(word) for word in (" the ", " my ", " account ", " bank ", " and ")
        )
        languages[
            "spanish_markers"
            if spanish >= 3 and spanish > english
            else "english_markers"
            if english >= 3
            else "unknown"
        ] += 1
        masked = sum(len(m.group()) for m in re.finditer(r"X{2,}|\[MASKED\]", text))
        masking[
            "none" if masked == 0 else "dense" if masked / max(1, len(text)) >= 0.1 else "present"
        ] += 1
        for attempt in result.get("attempts", []):
            models[attempt["model"]] += 1
            providers[
                "google-gemini-developer-api" if attempt["model"].startswith("gemini-") else "other"
            ] += 1
    return Profile(
        cases=len(rows),
        categories=dict(categories),
        lengths=dict(lengths),
        languages=dict(languages),
        masking=dict(masking),
        models=dict(models),
        providers=dict(providers),
    )


def compare(reference: Profile, current: Profile, *, threshold: float = 0.2) -> dict[str, Any]:
    if not 0 < threshold <= 1:
        raise ValueError("diagnostic threshold must be in (0,1]")
    result: dict[str, Any] = {
        "reference_cases": reference.cases,
        "current_cases": current.cases,
        "threshold": threshold,
        "language_method": "heuristic_markers_not_language_validation",
        "accuracy_claim": False,
        "dimensions": {},
    }
    for key in ("categories", "lengths", "languages", "masking", "models", "providers"):
        a: dict[str, int] = getattr(reference, key)
        b: dict[str, int] = getattr(current, key)
        total_a, total_b = sum(a.values()), sum(b.values())
        distance = (
            None
            if not total_a or not total_b
            else sum(abs(a.get(k, 0) / total_a - b.get(k, 0) / total_b) for k in set(a) | set(b))
            / 2
        )
        result["dimensions"][key] = {
            "total_variation": distance,
            "alert": distance is not None and distance >= threshold,
            "reference": a,
            "current": b,
            "insufficient_data": distance is None,
        }
    return result
