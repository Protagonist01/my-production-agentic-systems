"""Scheduled-denominator demo readback; no provider execution or qualification claim."""

import math
from collections import Counter
from typing import Annotated, Literal

from agent_harness.contracts import Contract, ModelResponse
from pydantic import Field, model_validator

from docs.evaluation.olist_semantic_candidate import parse, request
from olist_demo_acceptance import cases
from olist_routing_baseline import VERSION as BASELINE_VERSION
from olist_routing_baseline import interpret


def baselines() -> dict[str, object]:
    """Execute fixed input-only comparators before live capture; no tuned thresholds."""
    result: dict[str, object] = {}
    for variant in ("always-review", BASELINE_VERSION):
        rows = []
        correct = 0
        for case in cases():
            if variant == "always-review":
                intent, amount = "review", None
            else:
                proposed = interpret(case.text).plan
                intent, amount = proposed.intent, proposed.requested_minor
            joint = intent in case.acceptable_intents and (
                not case.amount_reference_known or amount == case.requested_minor
            )
            correct += int(joint)
            rows.append(
                {
                    "case_id": case.case_id,
                    "intent": intent,
                    "requested_minor": amount,
                    "joint_correct": joint,
                }
            )
        result[variant] = {
            "cases": 48,
            "joint_correct": correct,
            "agreement": correct / 48,
            "model_calls": 0,
            "model_cost": "0",
            "rows": rows,
            "deterministic_one_pass": True,
            "independent_language_gold": False,
        }
    return result


class Observation(Contract):
    origin: Literal["mock", "provider"] = "mock"
    case_id: str
    trial: Literal[1, 2, 3]
    request_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    response: ModelResponse
    elapsed_ms: Annotated[float, Field(ge=0, allow_inf_nan=False)]

    @model_validator(mode="after")
    def bounded(self) -> "Observation":
        calls = self.response.usage.model_calls
        if calls > 1 or (calls == 0 and self.response.failure is None):
            raise ValueError("one attempt or a preserved pre-dispatch failure required")
        return self


def schedule() -> tuple[tuple[str, int, str], ...]:
    """Interleave cases by trial; repeated cases are still dependent observations."""
    return tuple(
        (case.case_id, trial, request(case.text).fingerprint())
        for trial in (1, 2, 3)
        for case in cases()
    )


def summarize(observations: tuple[Observation, ...]) -> dict[str, object]:
    origins = {row.origin for row in observations}
    if len(origins) > 1:
        raise ValueError("mock/provider observations must remain separate")
    expected = {(c.case_id, trial): c for c in cases() for trial in (1, 2, 3)}
    by_key: dict[tuple[str, int], Observation] = {}
    for row in observations:
        observed_key = row.case_id, row.trial
        if observed_key not in expected or observed_key in by_key:
            raise ValueError("unknown or duplicate scheduled occurrence")
        wire = request(expected[observed_key].text)
        if (
            row.request_sha256 != wire.fingerprint()
            or row.response.provider != wire.provider
            or row.response.model != wire.model
        ):
            raise ValueError("captured request/route differs from the declared candidate")
        by_key[observed_key] = row
    counters: Counter[str] = Counter()
    buckets: dict[str, Counter[str]] = {}
    predictions: dict[str, list[str | None]] = {}
    durations = []
    known_cost = []
    currencies = set()
    for key, case in expected.items():
        bucket = buckets.setdefault(case.bucket, Counter())
        bucket["scheduled"] += 1
        counters["scheduled"] += 1
        counters["known_amount_scheduled"] += int(case.amount_reference_known)
        counters["explicit_amount_scheduled"] += int(case.requested_minor is not None)
        prediction = None
        captured = by_key.get(key)
        if captured is None:
            counters["missing"] += 1
        else:
            counters["attempted"] += 1
            durations.append(captured.elapsed_ms)
            usage = captured.response.usage
            counters["unknown_token_usage"] += int(
                usage.input_tokens is None or usage.output_tokens is None
            )
            counters["known_input_tokens"] += usage.input_tokens or 0
            counters["known_output_tokens"] += usage.output_tokens or 0
            if usage.cost is None:
                counters["unknown_cost"] += 1
            else:
                known_cost.append(usage.cost)
                currencies.add(usage.cost_currency)
            try:
                output = captured.response.output
                if captured.response.failure is not None or output is None:
                    category = (
                        "invalid_output"
                        if (
                            captured.response.failure is not None
                            and captured.response.failure.code == "invalid_response"
                        )
                        else "provider_failure"
                    )
                    counters[category] += 1
                elif output.tool_calls or output.content is None:
                    counters["invalid_output"] += 1
                else:
                    value = parse(case.text, output.content)
                    prediction = value.canonical_json()
                    counters["parsed"] += 1
                    intent_ok = value.intent in case.acceptable_intents
                    if case.requested_minor is not None:
                        amount_ok = (
                            value.requested_minor == case.requested_minor
                            and value.amount_status == "explicit"
                            and value.currency == "SIM"
                        )
                    else:
                        expected_status = (
                            "no_explicit_amount"
                            if case.acceptable_intents == ("refund",)
                            else "not_applicable"
                        )
                        amount_ok = (
                            value.requested_minor is None and value.amount_status == expected_status
                        )
                    counters["intent_correct"] += int(intent_ok)
                    counters["known_amount_correct"] += int(
                        case.amount_reference_known and amount_ok
                    )
                    counters["explicit_amount_correct"] += int(
                        case.requested_minor is not None and amount_ok
                    )
                    joint = intent_ok and (not case.amount_reference_known or amount_ok)
                    counters["joint_correct"] += int(joint)
                    bucket["joint_correct"] += int(joint)
                    counters["abstained"] += int(value.intent in ("review", "clarify"))
                    counters["false_refund_route"] += int(
                        value.intent == "refund" and "refund" not in case.acceptable_intents
                    )
            except ValueError:
                counters["invalid_output"] += 1
        predictions.setdefault(case.case_id, []).append(prediction)
    durations.sort()
    complete = len(by_key) == 144
    agreement = counters["joint_correct"] / 144
    return {
        "reference_basis": "authored_exposed_demo_contract",
        "observation_origin": next(iter(origins)) if origins else "none",
        "counts": dict(counters),
        "buckets": {name: dict(value) for name, value in buckets.items()},
        "scheduled_joint_agreement": agreement,
        "known_amount_accuracy": counters["known_amount_correct"]
        / counters["known_amount_scheduled"],
        "explicit_amount_accuracy": counters["explicit_amount_correct"]
        / counters["explicit_amount_scheduled"],
        "all_trials_consistent_cases": sum(
            None not in values and len(set(values)) == 1 for values in predictions.values()
        ),
        "latency_p95_ms_attempted": durations[math.ceil(0.95 * len(durations)) - 1]
        if durations
        else None,
        "known_cost_sum": str(sum(known_cost)) if known_cost and len(currencies) == 1 else None,
        "known_cost_currency": next(iter(currencies)) if len(currencies) == 1 else None,
        "cost_complete": complete and counters["unknown_cost"] == 0 and len(currencies) == 1,
        "all_scheduled_domain_observations_present": complete,
        "computed_suite_target_met": complete and agreement >= 0.95,
        "proposed_demo_language_target_met": complete
        and agreement >= 0.95
        and origins == {"provider"},
        "guardrail_effects_verified": False,
        "canaries_verified": False,
        "hosted_recovery_verified": False,
        "demo_release_accepted": False,
        "independent_language_gold": False,
        "population_confidence_established": False,
    }
