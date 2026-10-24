"""Actual spawned H10 mock dispatches, partial scorers and sealed observation mutations."""

import json
from dataclasses import replace

import pytest
from agent_harness.contracts import AgentInput
from agent_harness.domain_recording import read_domain, record_domain
from agent_harness.release_contracts import pin
from domain_recording_fixtures import ROOT, composition


@pytest.mark.parametrize("domain", ["cfpb", "revenue"])
@pytest.mark.parametrize("kind", ["normal", "failure", "unknown_cost"])
def test_partial_domains_dispatch_record_recompute_and_refuse_unobserved_release_fields(
    tmp_path, domain, kind
):
    loaded, schedule, factory = composition(
        domain, fail=kind == "failure", unknown_cost=kind == "unknown_cost"
    )
    output = tmp_path / "recording"
    evidence = record_domain(
        schedule, loaded, factory, output, candidate_sha256=pin(factory.candidate), source_root=ROOT
    )
    assert evidence.origin == "mock" and len(evidence.receipts) == 3
    kwargs = dict(evidence_sha256=pin(evidence), candidate_sha256=pin(factory.candidate))
    if kind == "unknown_cost":
        with pytest.raises(ValueError, match="usage evidence is incomplete"):
            read_domain(output, loaded, factory.adapter, **kwargs)
        return
    verified = read_domain(output, loaded, factory.adapter, **kwargs)
    assert len(verified.receipts) == 3 and len({r.nonce for r in verified.receipts}) == 3
    assert not verified.batch.complete
    for row in verified.batch.rows:
        result = row.report.report.result
        fields = {s.metric: s for s in row.report.report.scores}
        assert result.usage.model_calls == 1 and row.timing.elapsed_seconds > 0
        assert fields[domain + "_safe"].failure.code == "scorer_error"
        assert fields["privacy" if domain == "cfpb" else "supported_terms"].value is None
        assert result.outcome == ("failed" if kind == "failure" else "completed")
        if kind == "failure":
            assert result.failure.code == "timeout"
        else:
            assert fields[domain + "_correct"].value == 1.0
    for receipt in verified.receipts:
        public = json.loads(receipt.exchange.request.messages[-1].content)
        assert set(public) == ({"narrative"} if domain == "cfpb" else {"context", "question"})
    if kind == "normal":
        path = next((output / "observations").glob("*.json"))
        original = path.read_bytes()
        path.write_text("{}", encoding="utf-8")
        with pytest.raises(ValueError):
            read_domain(output, loaded, factory.adapter, **kwargs)
        path.write_bytes(original)
        assert read_domain(output, loaded, factory.adapter, **kwargs) == verified
        extra = output / "observations" / "extra.json"
        extra.write_text("{}", encoding="utf-8")
        with pytest.raises(ValueError, match="unexpected"):
            read_domain(output, loaded, factory.adapter, **kwargs)
        extra.unlink()
        path.unlink()
        with pytest.raises((ValueError, OSError)):
            read_domain(output, loaded, factory.adapter, **kwargs)


@pytest.mark.parametrize("domain", ["cfpb", "revenue"])
@pytest.mark.parametrize("change", ["configuration", "recipe", "source", "input"])
def test_domain_preflight_refuses_changed_recipe_configuration_source_or_private_projection(
    tmp_path, domain, change
):
    loaded, schedule, factory = composition(domain)
    if change == "input":
        with pytest.raises(ValueError):
            factory.adapter.validate_case(
                loaded.manifest.entries[0].case.model_copy(
                    update={"input": AgentInput(request="changed")}
                )
            )
        return
    spec = factory.candidate
    if change == "configuration":
        spec = spec.model_copy(update={"model_config_sha256": "0" * 64})
    elif change == "recipe":
        factory = replace(factory, transport=replace(factory.transport, content="changed"))
    else:
        spec = spec.model_copy(update={"source_files": {"uv.lock": spec.environment_lock}})
    factory = replace(factory, candidate=spec)
    with pytest.raises(ValueError):
        record_domain(
            schedule,
            loaded,
            factory,
            tmp_path / "out",
            candidate_sha256=pin(spec),
            source_root=ROOT,
        )
    assert not (tmp_path / "out").exists()
