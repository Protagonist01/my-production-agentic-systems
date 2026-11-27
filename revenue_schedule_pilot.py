"""Run offline Revenue routing baselines on the public-schedule development pilot."""

import argparse
import json
import re
from decimal import Decimal
from pathlib import Path

from agent_harness.release_contracts import pin, sha256
from revenue_integrity.source_contracts import ExtractionInput

from revenue_assessment import AssessmentResult, ScopeDecision
from revenue_diagnostics import configuration_pin, fixtures, rules
from revenue_evaluation import Observation, Plan, Reference, Variant, scorecard
from revenue_profiling import Recorder

DATA = Path(__file__).resolve().parent / "docs" / "data"
INPUTS = DATA / "revenue-public-schedule-pilot-inputs-v1.json"
REFERENCES = DATA / "revenue-public-schedule-pilot-references-v1.json"
SOURCE_PINS = DATA / "revenue-public-schedule-pilot-source-pins-v1.json"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, help="verify the four retained source PDFs")
    args = parser.parse_args()
    raw_inputs = INPUTS.read_bytes().replace(b"\r\n", b"\n")
    pin_bytes = SOURCE_PINS.read_bytes().replace(b"\r\n", b"\n")
    source_manifest = json.loads(pin_bytes)
    if {"sha256": sha256(raw_inputs), "bytes": len(raw_inputs)} != source_manifest["inputs"]:
        raise ValueError("pilot inputs differ from the reviewed pin")
    if args.source_dir is not None:
        for source in source_manifest["sources"]:
            content = (args.source_dir / source["filename"]).read_bytes()
            if (
                not content.startswith(b"%PDF-")
                or len(content) != source["bytes"]
                or sha256(content) != source["sha256"]
            ):
                raise ValueError("PDF differs from the reviewed pin: " + source["filename"])
    inputs = json.loads(raw_inputs)
    base_fixture = fixtures()[0]
    recorder = Recorder()
    projected = {}
    outputs: dict[str, dict[Variant, AssessmentResult]] = {}
    for row in inputs:
        identifier = row["id"]
        if identifier in projected:
            raise ValueError("duplicate pilot input")
        context = row["schedule"] + "\n\n" + row["order"]
        value = ExtractionInput(
            case_id=sha256(("public-schedule-pilot-v1/" + identifier).encode()),
            context=context,
            question=row["question"],
        )
        projected[identifier] = value
        # Bind the modeled packet to invented order identities and a read-only grant.
        variant_fixture = base_fixture.model_copy(
            update={
                "input": value,
                "binding": base_fixture.binding.model_copy(
                    update={"document_sha256": sha256(context.encode())}
                ),
            }
        )
        outputs[identifier] = {
            "rules": rules(variant_fixture, recorder),
            "always_review": AssessmentResult(
                case_id=value.case_id,
                decision=ScopeDecision(action="review", reason="scope_uncertain"),
            ),
        }

    raw_references = REFERENCES.read_bytes().replace(b"\r\n", b"\n")
    if {"sha256": sha256(raw_references), "bytes": len(raw_references)} != source_manifest[
        "references"
    ]:
        raise ValueError("pilot references differ from the reviewed pin")
    references = json.loads(raw_references)
    if sorted(ref["id"] for ref in references) != sorted(projected):
        raise ValueError("pilot references must cover every input exactly once")
    if sorted((ref["id"], ref["family"]) for ref in references) != sorted(
        (identifier, source["schedule"])
        for source in source_manifest["sources"]
        for identifier in source["case_ids"]
    ):
        raise ValueError("pilot case-to-source mapping differs from the reviewed pin")
    cases = []
    source_rows = {row["id"]: row for row in inputs}
    for ref in references:
        value = projected[ref["id"]]
        delta = ref["expected_delta_minor"]
        if ref["expected_action"] == "analyze":
            total = ref["unit_price_minor"] * ref["quantity"]
            (issued,) = re.findall(r"USD (\d+\.\d{2})", source_rows[ref["id"]]["order"])
            if (total, total - int(100 * Decimal(issued))) != (ref["expected_total_minor"], delta):
                raise ValueError("pilot amount disagrees with independent integer calculation")
        elif (ref["expected_total_minor"], delta) != (None, None):
            raise ValueError("unresolved invoice must have unknown total and delta")
        cases.append(
            Reference(
                case_id=value.case_id,
                input=value,
                family=ref["family"],
                parent=ref["family"],
                template=ref["family"],
                split="training",
                source_kind="authored_development",
                source_ref=ref["family"] + " public rate excerpt with constructed order facts",
                slices=(ref["slice"],),
                expected_action=ref["expected_action"],
                expected_missing_fields=tuple(ref["expected_missing_fields"]),
                expected_delta_minor=delta,
            )
        )
    plan = Plan(
        cases=tuple(cases),
        variants=("rules", "always_review"),
        trials=("offline-1",),
        candidate_sha256={name: configuration_pin(name) for name in ("rules", "always_review")},
    )
    observations = tuple(
        Observation(
            case_id=result.case_id,
            variant=variant,
            trial=plan.trials[0],
            candidate_sha256=plan.candidate_sha256[variant],
            input_sha256=pin(projected[identifier]),
            result=result,
        )
        for identifier, case_outputs in outputs.items()
        for variant, result in case_outputs.items()
    )
    report = scorecard(plan, observations)
    print(
        json.dumps(
            {
                "inputs_sha256": sha256(raw_inputs),
                "references_sha256": sha256(raw_references),
                "source_manifest_sha256": sha256(pin_bytes),
                "verified_source_pdfs": len(source_manifest["sources"]) if args.source_dir else 0,
                "plan_sha256": pin(plan),
                "cases": len(cases),
                "families": len({case.family for case in cases}),
                "provider_attempts": 0,
                "release_allowed": report["release_allowed"],
                "routes": {
                    key: {variant: result.decision.action for variant, result in rows.items()}
                    for key, rows in outputs.items()
                },
                "reference_relative_correct": {
                    name: result["reference_relative_correct"]
                    for name, result in report["variants"].items()
                },
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
