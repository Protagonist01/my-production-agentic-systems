"""Proposed independent structured-fact checks. Never clinical qualification by assertion.

No candidate, support recognizer or model is imported to derive reference states.
National policy and local explanatory counts remain separate scopes.
"""

from decimal import Decimal
from typing import Annotated, Literal

from agent_harness.contracts import WireContract
from pydantic import Field

State = Literal["met", "not_met", "insufficient", "conflict"]
KEYS = (
    "adult_osa",
    "education",
    "clinical_evaluation",
    "sleep_test",
    "physician_order",
    "severity",
    "event_count",
)
METHOD_VERSION = "prior-auth-structured-reference-proposal-v1"


class Index(WireContract):
    measure: Literal["AHI", "RDI"]
    value: Annotated[Decimal, Field(ge=0, le=1000, allow_inf_nan=False)]


class Facts(WireContract):
    provenance: Literal["constructed"] = "constructed"
    adult: bool | None
    osa_documented: bool | None
    education_before_use: bool | None
    clinical_evaluation: bool | None
    positive_test: bool | None
    test_kind: Literal["PSG", "II", "III", "IV", "unknown"]
    channels: Annotated[int, Field(ge=1, le=100)] | None
    ordered_before_test: bool | None
    supervised: bool | None
    indices: Annotated[tuple[Index, ...], Field(max_length=6)]
    qualifying_symptom: bool | None
    continuous_sleep_hours: Annotated[Decimal, Field(gt=0, le=24, allow_inf_nan=False)] | None
    recorded_events: Annotated[int, Field(ge=0, le=100000)] | None


def conjunction(*values: bool | None) -> State:
    if False in values:
        return "not_met"
    return "met" if all(v is True for v in values) else "insufficient"


def reference(
    facts: Facts,
    *,
    short_study: Literal["national-unresolved", "local-30-10-proposal"] = "national-unresolved",
) -> dict[str, State]:
    if short_study not in {"national-unresolved", "local-30-10-proposal"}:
        raise ValueError("explicit short-study method required")
    facts = Facts.model_validate_json(facts.canonical_json())
    # These facts describe one constructed study, not a longitudinal patient chart.
    grouped = {
        measure: {i.value for i in facts.indices if i.measure == measure}
        for measure in ("AHI", "RDI")
    }
    conflict = any(len(values) > 1 for values in grouped.values())
    severity: State = "insufficient"
    if conflict:
        severity = "conflict"
    elif any(
        i.value >= 15 or (5 <= i.value <= 14 and facts.qualifying_symptom is True)
        for i in facts.indices
    ):
        severity = "met"
    elif facts.indices:
        uncertain = any(
            14 < i.value < 15 or (5 <= i.value <= 14 and facts.qualifying_symptom is None)
            for i in facts.indices
        )
        severity = "insufficient" if uncertain else "not_met"
    sleep: State = "insufficient"
    if facts.positive_test is False:
        sleep = "not_met"
    elif facts.positive_test is True:
        if facts.test_kind in {"PSG", "II", "III"}:
            sleep = "met"
        elif facts.test_kind == "IV" and facts.channels is not None:
            sleep = "met" if facts.channels >= 3 else "not_met"
    count: State = "insufficient"
    if facts.continuous_sleep_hours is not None:
        if facts.continuous_sleep_hours >= 2:
            count = "met"
        elif (
            short_study == "local-30-10-proposal"
            and not conflict
            and facts.recorded_events is not None
        ):
            high = any(i.value >= 15 for i in facts.indices)
            low = (
                any(5 <= i.value <= 14 for i in facts.indices) and facts.qualifying_symptom is True
            )
            if high or low:
                count = "met" if facts.recorded_events >= (30 if high else 10) else "not_met"
    return dict(
        zip(
            KEYS,
            (
                conjunction(facts.adult, facts.osa_documented),
                conjunction(facts.education_before_use),
                conjunction(facts.clinical_evaluation),
                sleep,
                conjunction(facts.ordered_before_test, facts.supervised),
                severity,
                count,
            ),
            strict=True,
        )
    )


def qualification_inventory() -> dict[str, object]:
    return {
        "version": METHOD_VERSION,
        "method_accepted": False,
        "clinical_qualified": False,
        "release_allowed": False,
        "mechanical_paths": [
            "policy/source pins",
            "numeric predicates on supplied facts",
            "exact spans",
            "privacy and durable state witnesses",
        ],
        "unresolved": [
            "natural-note fact extraction and clinical/policy meaning",
            "applicable qualified reference cases or qualified evaluator",
            "national short-study interpretation; local applicability cannot be assumed",
            "pre-output owner limits, frozen representative groups and final fresh results",
        ],
        "source_findings": [
            "AHI and RDI are distinct measures; unequal values alone are not contradiction",
            "same-measure conflicting values are a separate ambiguity check",
            "reported_rate_times_two is not adopted as a national reference label",
            "LCD minimum counts are a separate proposed local-policy method",
        ],
    }
