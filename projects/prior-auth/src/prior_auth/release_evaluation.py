"""Fixed P6 case/trial reporting; reference-relative, never clinical approval."""

from collections import Counter
from typing import Literal

from agent_harness.contracts import Contract, NonEmpty
from agent_harness.evaluation_population import ratio, validate_matrix
from agent_harness.release_contracts import Sha256, pin

from prior_auth.assessment import CRITERIA
from prior_auth.contracts import AssessmentResult
from prior_auth.evaluation import EvaluationCase, score, validate_cohort


class AssessmentPlan(Contract):
    version: Literal["prior-auth-release-report-v1"] = "prior-auth-release-report-v1"
    candidate_sha256: Sha256
    source_manifest_sha256: Sha256
    cases: tuple[EvaluationCase, ...]
    trial_ids: tuple[NonEmpty, ...]
    origin: Literal["mock", "provider", "deterministic"]


class AssessmentObservation(Contract):
    case_id: NonEmpty
    trial_id: NonEmpty
    result: AssessmentResult | None = None
    failure_code: NonEmpty | None = None


def assessment_report(
    plan: AssessmentPlan, observations: tuple[AssessmentObservation, ...]
) -> dict[str, object]:
    plan = AssessmentPlan.model_validate_json(plan.canonical_json())
    observations = tuple(
        AssessmentObservation.model_validate_json(o.canonical_json()) for o in observations
    )
    validate_cohort(plan.cases)
    validate_matrix(
        tuple(c.input.case_id for c in plan.cases),
        plan.trial_ids,
        tuple((o.case_id, o.trial_id) for o in observations),
    )
    if len({c.input.policy_sha256 for c in plan.cases}) != 1:
        raise ValueError("one frozen policy required per assessment study")
    lookup = {(o.case_id, o.trial_id): o for o in observations}

    def measure(cases: tuple[EvaluationCase, ...]) -> dict[str, object]:
        counts: Counter[str] = Counter()
        criterion: dict[str, Counter[str]] = {k: Counter() for k in CRITERIA}
        for case in cases:
            all_pass = True
            expected = {c.criterion_id: c.state for c in case.expected}
            for trial in plan.trial_ids:
                o = lookup.get((case.input.case_id, trial))
                result = o.result if o else None
                row = score(case, result)
                counts["scheduled"] += 1
                counts["non_approvable"] += (
                    case.expected_disposition != "evidence_complete_for_review"
                )
                counts["missing"] += result is None
                counts["observed"] += result is not None
                failed = bool(o and o.failure_code) or bool(
                    result and (result.retrieval_failure or result.assessment_failure)
                )
                counts["failed"] += failed
                integrity = result is not None
                actual = {}
                if result:
                    actual = {c.criterion_id: c for c in result.claims}
                    integrity = len(result.claims) == len(CRITERIA) and set(actual) == set(CRITERIA)
                    for claim in result.claims:
                        if claim.state == "met" and not claim.evidence:
                            integrity = False
                        for span in claim.evidence:
                            try:
                                span.require(case.input.text)
                            except ValueError:
                                integrity = False
                counts["invalid"] += result is not None and not integrity
                resolved = result is not None and integrity and not failed
                correct = resolved and row["correct"] == 1
                all_pass &= correct
                counts["correct"] += correct
                counts["completed"] += resolved
                counts["unresolved"] += not resolved
                # Even failed/invalid recommendation outputs remain risk opportunities.
                counts["recommendations"] += int(row["proposed_evidence_complete"])
                counts["incorrect_recommendations"] += int(row["incorrect_evidence_complete"])
                for key in CRITERIA:
                    value = actual.get(key)
                    criterion[key]["scheduled"] += 1
                    criterion[key]["correct"] += bool(
                        resolved and value and value.state == expected[key]
                    )
                    criterion[key]["unsupported_met"] += bool(
                        value and value.state == "met" and expected[key] != "met"
                    )
                counts["appropriate_information_request"] += bool(
                    resolved
                    and result
                    and result.disposition == case.expected_disposition == "request_information"
                )
                counts["required_information_request"] += (
                    case.expected_disposition == "request_information"
                )
            counts["all_trials_correct"] += all_pass
        keys = (
            "scheduled",
            "non_approvable",
            "missing",
            "observed",
            "failed",
            "invalid",
            "correct",
            "completed",
            "unresolved",
            "recommendations",
            "incorrect_recommendations",
            "appropriate_information_request",
            "required_information_request",
            "all_trials_correct",
        )
        return dict(
            cases=len(cases),
            independent_groups=len({c.group_id for c in cases}),
            **{k: counts[k] for k in keys},
            incorrect_per_recommendation=ratio(
                counts["incorrect_recommendations"], counts["recommendations"]
            ),
            incorrect_per_non_approvable=ratio(
                counts["incorrect_recommendations"], counts["non_approvable"]
            ),
            criterion={
                k: {name: value[name] for name in ("scheduled", "correct", "unsupported_met")}
                for k, value in criterion.items()
            },
        )

    return dict(
        version=plan.version,
        plan_sha256=pin(plan),
        candidate_sha256=plan.candidate_sha256,
        observations_sha256=pin(ObservationInventory(observations=observations)),
        origin=plan.origin,
        **{"all": measure(plan.cases)},
        by_split={
            s: measure(tuple(c for c in plan.cases if c.split == s))
            for s in sorted({c.split for c in plan.cases})
        },
        by_provenance={
            s: measure(tuple(c for c in plan.cases if c.input.provenance == s))
            for s in sorted({c.input.provenance for c in plan.cases})
        },
        label_status="ai_provisional",
        clinical_validation=False,
        release_allowed=False,
        limitations=(
            "Reference-relative evidence assessment; no clinical decision or qualified label "
            "validation. Origin is declared, not verified fresh receipts. Privacy/state/fault "
            "checks are separate obligations."
        ),
    )


class ObservationInventory(Contract):
    observations: tuple[AssessmentObservation, ...]
