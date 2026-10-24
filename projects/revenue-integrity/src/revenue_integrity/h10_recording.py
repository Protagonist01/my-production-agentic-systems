"""Partial original-span H10 adapter; no numeric-term/business-state claims."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from agent_harness.cases import CaseEntry, CaseManifest, SnapshotSpec
from agent_harness.contracts import (
    AgentInput,
    AgentResult,
    Failure,
    FailureCode,
    ModelGateway,
    ModelRequest,
    RunContext,
    Usage,
)
from agent_harness.evaluation import EvalCase, ExpectedResult
from agent_harness.release_contracts import pin, sha256
from pydantic import JsonValue

from revenue_integrity.extraction import GatewayExtraction, GatewayExtractor
from revenue_integrity.release_evaluation import (
    ExtractionCase,
    ExtractionObservation,
    ExtractionPlan,
    extraction_report,
)
from revenue_integrity.source_contracts import ExtractionInput

VERSION = "revenue-extraction-partial-h10-v1"


@dataclass(frozen=True)
class RevenueAdapter:
    route: ModelRequest
    source_manifest_sha256: str
    agent_id: str = "revenue"
    scorer_id: str = "revenue-extraction-partial-h10"
    version: str = VERSION
    source_prefix: str = "projects/revenue-integrity/src/revenue_integrity/"

    @property
    def package_root(self) -> Path:
        return Path(__file__).parent

    @property
    def configuration_sha256(self) -> str:
        return pin(self.route)

    def case_for(self, reference: ExtractionCase) -> EvalCase:
        review = reference.target.impossible
        return EvalCase(
            case_id=reference.input.case_id,
            input=AgentInput(request=reference.input.canonical_json()),
            snapshot_ref=self.source_manifest_sha256,
            source_kind="original",
            source_version="cuad-published-span-reference-v1",
            policy_version="literal-spans-no-legal-meaning-v1",
            scorer_version=self.version,
            expected=ExpectedResult(
                outcome="review_required" if review else "completed",
                output=None,
                eligible_for_autonomy=not review,
                required_review=review,
                allowed_decisions=("unsupported",) if review else ("supported",),
                expected_state_changes={},
            ),
            hidden_state=reference.model_dump(mode="json"),
            risk="extraction-only-no-legal-decision",
            slices=(reference.target.split, reference.target.category),
        )

    def reference(self, case: EvalCase) -> ExtractionCase:
        reference = ExtractionCase.model_validate_json(json.dumps(case.hidden_state))
        if case != self.case_for(reference) or reference.target.case_id != reference.input.case_id:
            raise ValueError("Revenue private/public source binding differs")
        return reference

    def validate_case(self, case: EvalCase) -> None:
        self.reference(case)

    def manifest_for(self, references: tuple[ExtractionCase, ...]) -> CaseManifest:
        entries = tuple(
            CaseEntry(
                group_id=r.target.family_id,
                split=r.target.split,
                scorer_id=self.scorer_id,
                case=self.case_for(r),
            )
            for r in references
        )
        return CaseManifest(
            manifest_id="revenue-extraction-partial-h10",
            version="v1",
            case_ids=tuple(e.case.case_id for e in entries),
            entries=entries,
            snapshots=(
                SnapshotSpec(
                    reference=self.source_manifest_sha256,
                    source_kind="original",
                    source_version="cuad-published-span-reference-v1",
                ),
            ),
        )

    def run(
        self, context: RunContext, input: AgentInput, gateway: ModelGateway
    ) -> dict[str, JsonValue]:
        value = ExtractionInput.model_validate_json(input.request)
        return GatewayExtractor(gateway, self.route).run(context, value).model_dump(mode="json")

    def result(self, context: RunContext, payload: dict[str, JsonValue]) -> AgentResult:
        saved = GatewayExtraction.model_validate_json(json.dumps(payload))
        claim = saved.extraction.claim
        if (
            claim.case_id != context.case_id
            or context.versions.data_snapshot != self.source_manifest_sha256
        ):
            raise ValueError("Revenue result differs from source/case scope")
        failed = saved.failure_code is not None or claim.outcome == "uncertain"
        review = claim.outcome == "unsupported" and not failed
        known_codes = {
            "timeout",
            "rate_limited",
            "invalid_response",
            "budget_exhausted",
            "replay_mismatch",
            "permission_denied",
            "unavailable",
            "scorer_error",
        }
        code = saved.failure_code if saved.failure_code in known_codes else "invalid_response"
        return AgentResult(
            run_id=context.run_id,
            case_id=context.case_id,
            trial_id=context.trial_id,
            decision=claim.outcome,
            outcome="failed" if failed else "review_required" if review else "completed",
            output=claim.canonical_json(),
            review_ref="revenue-preview-only:" + pin(context) if review else None,
            usage=saved.usage
            if saved.usage
            else Usage(
                model_calls=0, input_tokens=None, output_tokens=None, cost=None, cost_currency=None
            ),
            failure=Failure(
                stage="model",
                code=cast(FailureCode, code),
                message="recorded extraction unresolved",
                retryable=False,
            )
            if failed
            else None,
        )

    def fields(
        self, case: EvalCase, context: RunContext, payload: dict[str, JsonValue]
    ) -> dict[str, bool | None]:
        reference = self.reference(case)
        saved = GatewayExtraction.model_validate_json(json.dumps(payload))
        if saved.extraction.source_sha256 != sha256(reference.input.context.encode()):
            raise ValueError("Revenue observation source digest differs from reference input")
        report = extraction_report(
            ExtractionPlan(
                source_manifest_sha256=self.source_manifest_sha256,
                cases=(reference,),
                trial_ids=(context.trial_id,),
            ),
            (
                ExtractionObservation(
                    case_id=case.case_id,
                    trial_id=context.trial_id,
                    claim=saved.extraction.claim,
                    failure_code=saved.failure_code,
                ),
            ),
        )
        counts = cast(dict[str, int], report["all"])
        # Empty precision/recall denominator is N/A, never a numeric score of 1.0.
        values: dict[str, bool | None] = {
            "span_precision_check": counts["invalid"] == 0
            and counts["submitted_spans"] == counts["matched_spans"],
            "span_recall_check": counts["reference_spans"] == counts["matched_spans"],
            "abstention": bool(not reference.target.impossible or counts["no_answer_correct"] == 1),
            "supported_terms": None,
            "reconciliation_amount": None,
            "reconciliation_reason": None,
            "authorization": None,
            "exact_state": None,
            "recovery": None,
            "revenue_correct": counts["correct"] == 1,
            "revenue_safe": None,
            "revenue_review": counts["no_answer_correct"] == 1,
        }
        if not counts["submitted_spans"]:
            values["span_precision_check"] = None
        if not counts["reference_spans"]:
            values["span_recall_check"] = None
        return values
