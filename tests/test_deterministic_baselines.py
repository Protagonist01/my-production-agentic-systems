"""Executed zero-call domain comparators and guard failures, never provider quality."""

from dataclasses import replace

import pytest
from agent_harness.baseline_recording import DenyModels, GuardAgent, read_baseline, zero_usage
from agent_harness.contracts import AgentInput, AgentResult, ModelMessage, ModelRequest
from agent_harness.domain_recording import (
    DomainBaselineFactory,
    read_domain_baseline,
    record_domain_baseline,
)
from agent_harness.evaluation_study import assemble_study
from agent_harness.release_contracts import pin, sha256
from agent_harness.release_evidence import compare_evidence, read_evidence
from domain_recording_fixtures import ROOT, composition


def baseline(domain):
    loaded, schedule, fresh = composition(domain)
    spec = fresh.candidate.model_copy(
        update={
            "candidate": fresh.candidate.candidate + "-baseline",
            "prompt_sha256": sha256(fresh.adapter.baseline_algorithm.encode()),
        }
    )
    tasks = tuple(
        t.model_copy(
            update={
                "context": t.context.model_copy(
                    update={
                        "mode": "offline_fake",
                        "versions": t.context.versions.model_copy(
                            update={"candidate": spec.candidate}
                        ),
                    }
                )
            }
        )
        for t in schedule.tasks
    )
    schedule = schedule.model_copy(update={"tasks": tasks})
    return loaded, schedule, DomainBaselineFactory(spec, loaded, fresh.adapter, ROOT / "unused")


@pytest.mark.parametrize("domain", ["cfpb", "revenue"])
def test_real_zero_call_baselines_have_no_provider_receipts_and_recompute_domain_scores(
    tmp_path, domain
):
    loaded, schedule, factory = baseline(domain)
    root = tmp_path / "baseline"
    manifest = record_domain_baseline(
        schedule, loaded, factory, root, candidate_sha256=pin(factory.candidate), source_root=ROOT
    )
    kwargs = dict(evidence_sha256=pin(manifest), candidate_sha256=pin(factory.candidate))
    verified = read_domain_baseline(root, loaded, factory.adapter, **kwargs)
    assert verified.manifest.origin == "deterministic" and not (root / "receipts").exists()
    assert len(verified.batch.rows) == 3 and not verified.batch.complete
    for row in verified.batch.rows:
        assert not row.errors and row.timing.elapsed_seconds > 0
        result = row.report.report.result
        assert result.outcome == "review_required" and result.usage == zero_usage("USD")
        assert {s.metric: s for s in row.report.report.scores}[domain + "_safe"].failure
        if domain == "cfpb":
            assert {s.metric: s for s in row.report.report.scores}["cfpb_review"].value == 1
    with pytest.raises((ValueError, OSError)):
        read_evidence(root, loaded, **kwargs)
    with pytest.raises(ValueError, match="candidate requires"):
        assemble_study(None, None, (), loaded, verified, verified, required_case_ids=())
    with pytest.raises(ValueError, match="dispatch-evidence format"):
        compare_evidence(verified, verified, loaded, None)
    path = next((root / "observations").glob("*.json"))
    original = path.read_bytes()
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError):
        read_domain_baseline(root, loaded, factory.adapter, **kwargs)
    path.write_bytes(original)
    assert read_domain_baseline(root, loaded, factory.adapter, **kwargs) == verified
    (root / "receipts").mkdir()
    with pytest.raises(ValueError, match="provider receipts"):
        read_baseline(root, loaded, **kwargs)
    (root / "receipts").rmdir()
    # A missing scheduled execution cannot be legitimized by resealing the partial batch.
    from agent_harness.trials import TrialJournal

    row = verified.batch.rows[0]
    (root / "journal" / "rows" / (row.task.fingerprint() + ".json")).unlink()
    partial = TrialJournal(root / "journal").read(loaded)
    altered = manifest.model_copy(update={"batch_sha256": pin(partial)})
    (root / "baseline.json").write_text(altered.canonical_json(), encoding="utf-8")
    with pytest.raises(ValueError, match="sealed batch"):
        read_baseline(
            root, loaded, evidence_sha256=pin(altered), candidate_sha256=pin(factory.candidate)
        )


@pytest.mark.parametrize("change", ["algorithm", "mode", "pin", "source"])
def test_baseline_preflight_rejects_misbound_configuration_before_output(tmp_path, change):
    loaded, schedule, factory = baseline("cfpb")
    digest = pin(factory.candidate)
    if change == "algorithm":
        factory = replace(
            factory, candidate=factory.candidate.model_copy(update={"prompt_sha256": "0" * 64})
        )
    elif change == "mode":
        schedule = schedule.model_copy(
            update={
                "tasks": tuple(
                    t.model_copy(
                        update={"context": t.context.model_copy(update={"mode": "fresh_candidate"})}
                    )
                    for t in schedule.tasks
                )
            }
        )
    elif change == "source":
        factory = replace(
            factory,
            candidate=factory.candidate.model_copy(update={"source_files": {"uv.lock": "0" * 64}}),
        )
    else:
        digest = "0" * 64
    with pytest.raises(ValueError):
        record_domain_baseline(
            schedule,
            loaded,
            factory,
            tmp_path / "forbidden",
            candidate_sha256=digest,
            source_root=ROOT,
        )
    assert not (tmp_path / "forbidden").exists()


class BadAgent:
    def __init__(self, kind):
        self.kind = kind

    def run(self, context, input, gateway):
        if self.kind == "caught_call":
            try:
                gateway.generate(
                    context,
                    ModelRequest(
                        provider="mock",
                        endpoint="in-process",
                        model="invented",
                        messages=(ModelMessage(role="user", content="invented"),),
                        parameters={},
                    ),
                )
            except ValueError:
                pass
        usage = zero_usage("USD")
        if self.kind == "nonzero":
            usage = usage.model_copy(update={"model_calls": 1})
        elif self.kind == "unknown":
            usage = usage.model_copy(update={"cost": None, "cost_currency": None})
        return AgentResult(
            run_id=context.run_id,
            case_id=context.case_id,
            trial_id=context.trial_id,
            decision="review",
            outcome="review_required",
            review_ref="invented",
            usage=usage,
        )


@pytest.mark.parametrize("kind", ["caught_call", "nonzero", "unknown"])
def test_guard_refuses_even_caught_gateway_attempts_and_false_usage(kind):
    _, schedule, _ = baseline("revenue")
    gate = DenyModels()
    with pytest.raises(ValueError):
        GuardAgent(BadAgent(kind), gate).run(
            schedule.tasks[0].context, AgentInput(request="invented"), gate
        )
    if kind == "caught_call":
        assert gate.attempted


def test_always_review_counts_routing_without_claiming_classifier_predictions():
    loaded, schedule, factory = baseline("cfpb")
    context = schedule.tasks[0].context
    adapter = factory.adapter
    case = loaded.manifest.entries[0].case
    reference = adapter.reference(case).model_copy(update={"priority": "elevated"})
    case = adapter.case_for(reference)
    payload = adapter.baseline(context, case.input)
    fields = adapter.fields(case, context, payload)
    assert fields["route"] and fields["cfpb_review"]
    assert not fields["product"] and not fields["cfpb_correct"]
    assert fields["privacy"] is None and fields["review_durability"] is None
    fresh = context.model_copy(update={"mode": "fresh_candidate"})
    assert not adapter.fields(case, fresh, payload)["cfpb_review"]
