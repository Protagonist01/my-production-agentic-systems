"""H8 fixed redacted projections, without Pydantic AI's automatic prompt capture."""

from typing import Literal

from agent_harness.contracts import ModelGateway, RunContext
from agent_harness.offline_example import example_case
from agent_harness.telemetry import TracedGateway, TraceSession

from cfpb_triage.classifier import route
from cfpb_triage.source_contracts import ComplaintInput
from cfpb_triage.triage_contracts import Decision, RouterPolicy, Taxonomy


def traced_route(
    trace: TraceSession,
    gateway: ModelGateway,
    context: RunContext,
    complaint: ComplaintInput,
    taxonomy: Taxonomy,
    policy: RouterPolicy,
    *,
    provenance: Literal["original", "edited", "invented"] = "original",
) -> Decision:
    # The generic case is a trace envelope only. No fake scorer or quality score
    # runs here; classifier input remains the closed narrative-only contract.
    sample = example_case()
    envelope = sample.model_copy(
        update={
            "case_id": complaint.case_id,
            "source_kind": {"original": "original", "edited": "hybrid", "invented": "synthetic"}[
                provenance
            ],
            "source_version": "cfpb-reviewed-masked-v1",
            "scorer_version": "not-scored-operational-trace",
            "snapshot_ref": context.versions.data_snapshot,
            "input": sample.input.model_copy(
                update={"request": complaint.narrative, "observations": ()}
            ),
        }
    )
    attributes = trace.begin(context, envelope)
    try:
        with trace._span("run", attributes), trace._span("agent", {}):
            return trace.invoke(
                "node",
                "cfpb-typed-classifier-v1",
                lambda: route(TracedGateway(trace, gateway), context, complaint, taxonomy, policy),
            )
    finally:
        trace.finish()
