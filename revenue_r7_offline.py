"""Evaluate existing Revenue evidence without provider or billing writes."""

import argparse
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from agent_harness.release_contracts import sha256
from revenue_integrity.billing_worlds import cases, validate_cases
from revenue_integrity.extraction import abstain
from revenue_integrity.reconcile import Reconciliation, reconcile
from revenue_integrity.release_evaluation import (
    BillingObservation,
    BillingPlan,
    ExtractionCase,
    ExtractionObservation,
    ExtractionPlan,
    billing_report,
    extraction_report,
)
from revenue_integrity.source_contracts import ExtractionInput, PublishedTarget

CUAD_PIN = "b852424ab854c30bd730ccc90a799907e02d3875a3066d203aed36f842f78540"
WORLDS_PIN = "97d4193e8339af5164dedc284b6b45d53fce4cb936e809ba76769adc4d104730"
TRIAL = "offline-1"
CATEGORIES = ("Minimum Commitment", "Price Restrictions", "Revenue/Profit Sharing")
REVIEW_REASONS = {
    "missing_seats": "missing_seats_or_price",
    "missing_price": "missing_seats_or_price",
    "missing_uplift_anchor": "incomplete_explicit_uplift",
    "conflicting_terms": "conflicting_terms",
    "same_date_amendments": "conflicting_same_date_amendments",
    "midmonth_amendment": "partial_month_event",
    "fractional_minor_uplift": "fractional_minor_uplift",
    "negative_after_credit": "credit_exceeds_monthly_charge",
    "same_date_price_and_uplift": "price_amendment_uplift_order_unknown",
}


def read_exclusions(root: Path) -> tuple[set[str], set[str], dict[str, str]]:
    study = root / "confidence-target-study-2026-10-27-v1"
    prospective = root / "prospective-semantic-cohort-2026-10-27-v2"
    paths = (
        *(study / f"exposure-{number}.json" for number in range(1, 5)),
        study / "cohort.json",
        prospective / "cohort.json",
        root / "semantic-answerability-pilot-2026-10-27-v1/prepared-pilot.json",
    )
    raw = [path.read_bytes() for path in paths]
    payloads = [json.loads(value) for value in raw]
    pins = [sha256(value) for value in raw]
    confidence = json.loads((study / "preparation.json").read_bytes())
    proposal = json.loads((prospective / "report.json").read_bytes())
    if (
        pins[4] != confidence["cohort_sha256"]
        or pins[5] != proposal["cohort_sha256"]
        or sorted(pins[:4]) != sorted(payloads[4]["exposure_inventory_sha256s"])
        or any(p["source_manifest_sha256"] != CUAD_PIN for p in payloads)
    ):
        raise ValueError("CUAD exposure or cohort pin mismatch")
    exposure = [row for artifact in payloads[:4] for row in artifact["records"]]
    families = {row["family_id"] for row in exposure}
    contexts = {row["context_sha256"] for row in exposure}
    for artifact in payloads[4:]:
        for entry in artifact["cases"]:
            families.add(entry["target"]["family_id"])
            contexts.add(sha256(entry["input"]["context"].encode()))
    return (
        families,
        contexts,
        {path.relative_to(root).as_posix(): key for path, key in zip(paths, pins, strict=True)},
    )


def original(root: Path) -> dict[str, Any]:
    source = root / "cuad-original-r1-v1"
    manifest = (source / "manifest.json").read_bytes()
    if sha256(manifest) != CUAD_PIN:
        raise ValueError("CUAD source manifest differs")
    manifest_value = json.loads(manifest)
    for store in ("evaluator", "inputs"):
        if sha256((source / f"{store}.sqlite").read_bytes()) != manifest_value[store + "_sha256"]:
            raise ValueError("CUAD store differs")
    families, contexts, exclusion_pins = read_exclusions(root)
    ev_path = (source / "evaluator.sqlite").as_uri() + "?mode=ro"
    input_path = (source / "inputs.sqlite").as_uri() + "?mode=ro"
    with closing(sqlite3.connect(ev_path, uri=True)) as ev:
        rows = [
            (PublishedTarget.model_validate_json(raw), context_pin)
            for raw, context_pin in ev.execute(
                "SELECT target, context_sha256 FROM targets JOIN sources USING(case_id) "
                "ORDER BY case_id"
            )
        ]
    families.update(target.family_id for target, key in rows if key in contexts)
    selected = []
    with closing(sqlite3.connect(input_path, uri=True)) as inputs:
        for target, _ in rows:
            if (
                target.split != "holdout"
                or target.family_id in families
                or target.category not in CATEGORIES
            ):
                continue
            context, question = inputs.execute(
                "SELECT context, question FROM questions JOIN contracts USING(contract_id) "
                "WHERE case_id=?",
                (target.case_id,),
            ).fetchone()
            selected.append(
                ExtractionCase(
                    input=ExtractionInput(
                        case_id=target.case_id, context=context, question=question
                    ),
                    target=target,
                )
            )
    plan = ExtractionPlan(
        source_manifest_sha256=CUAD_PIN, cases=tuple(selected), trial_ids=(TRIAL,)
    )
    baseline = tuple(
        ExtractionObservation(case_id=c.input.case_id, trial_id=TRIAL, claim=abstain(c.input))
        for c in plan.cases
    )
    return {
        "source_manifest_sha256": CUAD_PIN,
        "exclusion_pins": exclusion_pins,
        "excluded_families": len(families),
        "always_abstain": extraction_report(plan, baseline),
        "candidate_unrun": extraction_report(plan, ()),
    }


def synthetic() -> dict[str, object]:
    cohort = cases()
    validate_cases(cohort)
    # Keep the original scenario labels in the source cohort. Translate the reason
    # field for the scorecard, which compares machine-readable result codes.
    scored_cases = tuple(
        case.model_copy(
            update={
                "expected": case.expected.model_copy(
                    update={
                        "reason": REVIEW_REASONS[case.expected.reason]
                        if case.expected.disposition == "review"
                        else "exact_monthly_sim_arithmetic",
                    }
                ),
            }
        )
        for case in cohort
    )
    plan = BillingPlan(source_manifest_sha256=WORLDS_PIN, cases=scored_cases, trial_ids=(TRIAL,))
    observations: dict[str, list[BillingObservation]] = {
        "full_engine": [],
        "without_amendments_or_credits": [],
        "engine_disabled_review": [],
    }
    for case in cohort:
        entry = case.input
        results = {
            "full_engine": reconcile(entry),
            "without_amendments_or_credits": reconcile(
                entry.model_copy(update={"amendments": (), "credits": ()})
            ),
            "engine_disabled_review": Reconciliation(
                case_id=entry.case_id,
                disposition="review",
                should_be_minor=None,
                issued_minor=entry.invoice.amount_minor,
                delta_minor=None,
                reasons=("engine_disabled",),
            ),
        }
        for name, result in results.items():
            observations[name].append(
                BillingObservation(case_id=entry.case_id, trial_id=TRIAL, result=result)
            )
    return {name: billing_report(plan, tuple(output)) for name, output in observations.items()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            {
                "version": "revenue-r7-offline-v1",
                "provider_attempts": 0,
                "release_allowed": False,
                "original": original(args.source_dir.resolve(strict=True)),
                "synthetic": synthetic(),
            },
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
    )


if __name__ == "__main__":
    main()
