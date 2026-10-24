"""Partial CFPB H10 adapter: actual classifier calls, no privacy/durable-state credit."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from agent_harness.cases import CaseEntry, CaseManifest, SnapshotSpec
from agent_harness.contracts import (
    AgentInput,
    AgentResult,
    Contract,
    Failure,
    FailureCode,
    ModelGateway,
    RunContext,
    Usage,
)
from agent_harness.controls import combine_usage
from agent_harness.evaluation import EvalCase, ExpectedResult
from agent_harness.release_contracts import pin
from pydantic import JsonValue

from cfpb_triage.release_evaluation import EvaluationPlan, ReferenceCase, _valid
from cfpb_triage.source_contracts import ComplaintInput
from cfpb_triage.triage_contracts import Decision, RouterPolicy, Taxonomy, digest_text

VERSION = "cfpb-partial-h10-v1"


class Payload(Contract):
    decision: Decision
    usage: Usage


@dataclass(frozen=True)
class CfpbAdapter:
    taxonomy: Taxonomy
    policy: RouterPolicy
    agent_id: str = "cfpb"
    scorer_id: str = "cfpb-partial-h10"
    version: str = VERSION
    source_prefix: str = "projects/cfpb-triage/src/cfpb_triage/"

    @property
    def package_root(self) -> Path:
        return Path(__file__).parent

    @property
    def configuration_sha256(self) -> str:
        return digest_text(self.taxonomy.canonical_json() + self.policy.canonical_json())

    def case_for(self, reference: ReferenceCase) -> EvalCase:
        required = reference.priority != "routine" or reference.ambiguity != "clear"
        return EvalCase(
            case_id=reference.complaint.case_id,
            input=AgentInput(request=reference.complaint.canonical_json()),
            snapshot_ref=digest_text(reference.complaint.narrative),
            source_kind=reference.source_kind,
            source_version="cfpb-reference-projection-v1",
            policy_version=pin(self.policy),
            scorer_version=self.version,
            expected=ExpectedResult(
                outcome="review_required" if required else "completed",
                output=None,
                eligible_for_autonomy=not required,
                required_review=required,
                allowed_decisions=("review",) if required else ("classify",),
                expected_state_changes={},
            ),
            hidden_state=reference.model_dump(mode="json"),
            risk="consumer-complaint-assistive",
            slices=(reference.split,),
        )

    def reference(self, case: EvalCase) -> ReferenceCase:
        reference = ReferenceCase.model_validate_json(json.dumps(case.hidden_state))
        if case != self.case_for(reference) or self.policy.taxonomy_sha256 != pin(self.taxonomy):
            raise ValueError("CFPB private/public/configuration binding differs")
        return reference

    def validate_case(self, case: EvalCase) -> None:
        self.reference(case)

    def manifest_for(self, references: tuple[ReferenceCase, ...]) -> CaseManifest:
        entries = tuple(
            CaseEntry(
                group_id=r.group_id,
                split="holdout" if r.split == "holdout" else "development",
                scorer_id=self.scorer_id,
                case=self.case_for(r),
            )
            for r in references
        )
        return CaseManifest(
            manifest_id="cfpb-partial-h10",
            version="v1",
            case_ids=tuple(e.case.case_id for e in entries),
            entries=entries,
            snapshots=tuple(
                SnapshotSpec(
                    reference=snapshot,
                    source_kind=kind,
                    source_version=version,
                )
                for snapshot, kind, version in sorted(
                    {
                        (e.case.snapshot_ref, e.case.source_kind, e.case.source_version)
                        for e in entries
                    }
                )
            ),
        )

    def run(
        self, context: RunContext, input: AgentInput, gateway: ModelGateway
    ) -> dict[str, JsonValue]:
        from cfpb_triage.classifier import route

        complaint = ComplaintInput.model_validate_json(input.request)
        decision = route(gateway, context, complaint, self.taxonomy, self.policy)
        values = tuple(a.usage for a in decision.attempts if a.usage is not None)
        usage = combine_usage(values, context.budget.cost_currency)
        if len(values) != len(decision.attempts):
            usage = usage.model_copy(
                update={
                    "input_tokens": None,
                    "output_tokens": None,
                    "cost": None,
                    "cost_currency": None,
                }
            )
        return Payload(decision=decision, usage=usage).model_dump(mode="json")

    def result(self, context: RunContext, payload: dict[str, JsonValue]) -> AgentResult:
        saved = Payload.model_validate_json(json.dumps(payload))
        d = saved.decision
        if (
            d.case_id != context.case_id
            or d.policy_sha256 != pin(self.policy)
            or d.taxonomy_sha256 != pin(self.taxonomy)
            or d.narrative_sha256 != context.versions.data_snapshot
        ):
            raise ValueError("CFPB result identity/configuration differs")
        failed = any(a.failure for a in d.attempts)
        review = d.outcome == "review_required" and not failed
        code = next((a.failure for a in d.attempts if a.failure), None)
        return AgentResult(
            run_id=context.run_id,
            case_id=context.case_id,
            trial_id=context.trial_id,
            decision="review" if d.outcome == "review_required" else "classify",
            outcome="failed" if failed else "review_required" if review else "completed",
            output=d.canonical_json(),
            review_ref="cfpb-preview-only:" + pin(context) if review else None,
            usage=saved.usage,
            failure=Failure(
                stage="model",
                code=cast(FailureCode, code),
                message="recorded classifier attempt failed",
                retryable=False,
            )
            if failed
            else None,
        )

    def fields(
        self, case: EvalCase, context: RunContext, payload: dict[str, JsonValue]
    ) -> dict[str, bool | None]:
        reference = self.reference(case)
        saved = Payload.model_validate_json(json.dumps(payload))
        d, p = saved.decision, saved.decision.prediction
        plan = EvaluationPlan(
            source_manifest_sha256=self.taxonomy.source_manifest,
            taxonomy=self.taxonomy,
            policy=self.policy,
            cases=(reference,),
            trial_ids=(context.trial_id,),
        )
        valid = _valid(reference, d, plan) and not any(a.failure for a in d.attempts)
        values: dict[str, bool | None] = {
            "product": bool(valid and p and p.product == reference.product),
            "issue": bool(valid and p and p.issue == reference.issue),
            "priority": bool(valid and p and p.priority == reference.priority),
            "ambiguity": bool(valid and p and p.ambiguity == reference.ambiguity),
            "evidence_span": bool(valid and p and p.evidence),
            "route": valid and (d.outcome == "review_required") == case.expected.required_review,
            "privacy": None,
            "review_durability": None,
        }
        values.update(
            cfpb_correct=all(
                values[k] is True
                for k in ("product", "issue", "priority", "ambiguity", "evidence_span", "route")
            ),
            cfpb_safe=None,
            cfpb_review=valid and d.outcome == "review_required",
        )
        return values
