"""Evaluator-only Olist population projection; no label promotion or provider dispatch."""

import json

from agent_harness.cases import CaseEntry, CaseManifest, SnapshotSpec
from agent_harness.contracts import AgentInput, Contract, RunContext
from agent_harness.evaluation import EvalCase, ExpectedResult

from olist_support.business import sha
from olist_support.business_contracts import CallerGrant, RefundCommand
from olist_support.policy_cases import Digest, PolicyCase, PolicyCases, Split
from olist_support.release import ScheduledTrial

SCORER_ID = "olist-h10-fields"
SCORER_VERSION = "olist-h10-fields-v1"


class OlistMetadata(Contract):
    olist_case: PolicyCase
    original_split: Split
    recovery_required: bool
    source_database_sha256: Digest


def expected_for(case: PolicyCase) -> ExpectedResult:
    refund = case.expected.action == "propose_full_refund"
    return ExpectedResult(
        outcome="completed" if refund else "review_required",
        output=None,
        eligible_for_autonomy=refund,
        required_review=not refund,
        allowed_decisions=("refund",) if refund else ("review",),
        expected_state_changes={"amount_minor": case.expected.amount_minor},
    )


def manifest_for(cases: PolicyCases, *, recovery_case_ids: tuple[str, ...] = ()) -> CaseManifest:
    """Encode reviewed labels privately; regression is development, never holdout.

    Callers must freeze/review the resulting byte pin separately. This constructor
    supplies neither independent annotation nor approval of a changed population.
    """
    cases = PolicyCases.model_validate_json(cases.canonical_json())
    ids = {c.input.case_id for c in cases.entries}
    if len(set(recovery_case_ids)) != len(recovery_case_ids) or not set(recovery_case_ids).issubset(
        ids
    ):
        raise ValueError("recovery inventory contains duplicate or unknown cases")
    entries = []
    for case in cases.entries:
        if case.input.order.source_manifest_sha256 != cases.source_manifest_sha256:
            raise ValueError("case source differs from reviewed population")
        entries.append(
            CaseEntry(
                group_id=case.group_id,
                split="holdout" if case.split == "holdout" else "development",
                scorer_id=SCORER_ID,
                case=EvalCase(
                    case_id=case.input.case_id,
                    input=AgentInput(request=case.input.request.message),
                    snapshot_ref=cases.source_manifest_sha256,
                    source_kind=case.source_kind,
                    source_version=cases.version,
                    policy_version=case.guideline,
                    scorer_version=SCORER_VERSION,
                    expected=expected_for(case),
                    hidden_state=OlistMetadata(
                        olist_case=case,
                        original_split=case.split,
                        recovery_required=case.input.case_id in recovery_case_ids,
                        source_database_sha256=cases.source_database_sha256,
                    ).model_dump(mode="json"),
                    risk="simulation_only",
                    slices=(case.treatment, case.split),
                ),
            )
        )
    snapshots = tuple(
        SnapshotSpec(
            reference=cases.source_manifest_sha256,
            source_kind=kind,
            source_version=cases.version,
        )
        for kind in {c.source_kind for c in cases.entries}
    )
    # One snapshot reference cannot ambiguously claim different source kinds.
    if len(snapshots) != 1:
        raise ValueError("separate manifests are required for different source kinds")
    return CaseManifest(
        manifest_id="olist-h10-" + sha(cases.canonical_json())[:16],
        version="v1",
        case_ids=tuple(e.case.case_id for e in entries),
        snapshots=snapshots,
        entries=tuple(entries),
    )


def private_case(case: EvalCase) -> tuple[PolicyCase, bool]:
    """Rebind public identity, source, split and eligibility to the private label."""
    try:
        metadata = OlistMetadata.model_validate_json(json.dumps(case.hidden_state))
    except ValueError:
        raise ValueError("Olist manifest metadata is invalid") from None
    label = metadata.olist_case
    if (
        metadata.original_split != label.split
        or case.case_id != label.input.case_id
        or case.input != AgentInput(request=label.input.request.message)
        or case.snapshot_ref != label.input.order.source_manifest_sha256
        or case.source_kind != label.source_kind
        or case.source_version != "olist-policy-cases-v1"
        or case.scorer_version != SCORER_VERSION
        or case.policy_version != label.guideline
        or case.expected != expected_for(label)
        or case.faults
    ):
        raise ValueError("Olist manifest differs from private evaluator labels")
    return label, metadata.recovery_required


def domain_task(
    case: PolicyCase, context: RunContext, grant: CallerGrant, run_limit_minor: int
) -> ScheduledTrial:
    """Expected command belongs only to the scorer, never to the runtime agent."""
    amount = case.expected.amount_minor
    return ScheduledTrial(
        case_id=context.case_id,
        trial_id=context.trial_id,
        run_id=context.run_id,
        grant=grant,
        run_limit_minor=run_limit_minor,
        command=(
            RefundCommand(
                tenant_id=context.tenant_id,
                order_id=case.input.order.order_id,
                business_operation_id=sha("olist-full-refund-v1|" + context.business_event_id),
                amount_minor=amount,
                expected_version=0,
            )
            if amount is not None
            else None
        ),
    )
