"""Actual spawned offline dispatch and tamper witnesses, never live provider calls."""

from datetime import timedelta

import pytest
from agent_harness.fresh_example import UppercaseFactory
from agent_harness.fresh_recording import record_candidate, validate_fresh
from agent_harness.release_contracts import CandidateSpec, pin, verify_sources
from agent_harness.release_evidence import read_evidence
from agent_harness.trial_example import FileTrialEnvironment
from agent_harness.trials import TrialRow
from release_fixtures import capture, inputs


def test_three_identical_answers_have_three_new_dispatch_receipts(tmp_path):
    loaded, first, output = capture(tmp_path, "first")
    _, second, _ = capture(tmp_path, "second")
    assert first.batch.complete and first.batch.autonomous_completions == 3
    assert first.manifest.origin == "mock"
    assert len(first.receipts) == len(second.receipts) == 3
    assert len({r.exchange.response.canonical_json() for r in first.receipts}) == 1
    assert len({r.exchange.request.fingerprint() for r in first.receipts}) == 1
    assert {r.nonce for r in first.receipts}.isdisjoint(r.nonce for r in second.receipts)
    assert first.manifest.execution_id != second.manifest.execution_id
    assert sum(r.exchange.response.usage.model_calls for r in first.receipts) == 3
    assert not list((tmp_path / "first-state").iterdir())
    with pytest.raises(ValueError, match="external pin"):
        read_evidence(
            output,
            loaded,
            evidence_sha256=pin(second.manifest),
            candidate_sha256=pin(first.manifest.candidate),
        )


@pytest.mark.parametrize(
    "mutation", ["missing", "changed", "extra", "journal", "timing", "nonce", "identity"]
)
def test_receipt_or_journal_tampering_blocks_read(tmp_path, mutation):
    loaded, evidence, output = capture(tmp_path)
    manifest = evidence.manifest
    path = next((output / "receipts").glob("*/*.json"))
    if mutation == "missing":
        path.unlink()
    elif mutation == "changed":
        path.write_text("{}", encoding="utf-8")
    elif mutation == "extra":
        (output / "receipts" / "extra.txt").write_text("extra", encoding="utf-8")
    elif mutation == "journal":
        next((output / "journal" / "rows").glob("*.json")).unlink()
    elif mutation == "timing":
        path = next((output / "journal" / "rows").glob("*.json"))
        row = TrialRow.model_validate_json(path.read_bytes())
        altered = row.model_copy(
            update={
                "timing": row.timing.model_copy(
                    update={"execution_seconds": row.timing.execution_seconds + 1.0}
                )
            }
        )
        path.write_text(altered.canonical_json(), encoding="utf-8")
    else:
        from agent_harness.release_contracts import AttemptReceipt, sha256

        receipt = AttemptReceipt.model_validate_json(path.read_bytes())
        other = next(r for r in evidence.receipts if r.nonce != receipt.nonce)
        if mutation == "nonce":
            receipt = receipt.model_copy(update={"nonce": other.nonce})
        else:
            receipt = receipt.model_copy(
                update={
                    "exchange": receipt.exchange.model_copy(
                        update={"context": other.exchange.context}
                    )
                }
            )
        path.write_text(receipt.canonical_json(), encoding="utf-8")
        hashes = dict(manifest.receipts)
        hashes[path.relative_to(output / "receipts").as_posix()] = sha256(path.read_bytes())
        manifest = manifest.model_copy(update={"receipts": hashes})
        (output / "evidence.json").write_text(manifest.canonical_json(), encoding="utf-8")
    with pytest.raises(ValueError):
        read_evidence(
            output, loaded, evidence_sha256=pin(manifest), candidate_sha256=pin(manifest.candidate)
        )


@pytest.mark.parametrize(
    "field",
    [
        "prompt_sha256",
        "model_config_sha256",
        "tools_sha256",
        "policy_sha256",
        "scorer_sha256",
        "environment_sha256",
    ],
)
def test_every_behavior_dimension_changes_candidate_pin(tmp_path, field):
    _, _, spec, _, source = inputs(tmp_path)
    changed = spec.model_copy(update={field: "a" * 64})
    assert pin(changed) != pin(spec)
    (source / "agent.py").write_text("changed behavior", encoding="utf-8")
    with pytest.raises(ValueError, match="source"):
        verify_sources(source, spec)


@pytest.mark.parametrize("mutation", ["two_trials", "parallel", "mode", "candidate", "budget"])
def test_recording_preflight_refuses_wrong_population_or_budget(tmp_path, mutation):
    _, schedule, spec, _, _ = inputs(tmp_path)
    if mutation == "two_trials":
        schedule = schedule.model_copy(
            update={"trial_ids": schedule.trial_ids[:2], "tasks": schedule.tasks[:2]}
        )
    elif mutation == "parallel":
        schedule = schedule.model_copy(update={"max_parallel": 2})
    elif mutation in ("mode", "candidate"):
        tasks = tuple(
            t.model_copy(
                update={
                    "context": t.context.model_copy(
                        update=(
                            {"mode": "strict_replay"}
                            if mutation == "mode"
                            else {
                                "versions": t.context.versions.model_copy(
                                    update={"candidate": "old"}
                                )
                            }
                        )
                    )
                }
            )
            for t in schedule.tasks
        )
        schedule = schedule.model_copy(update={"tasks": tasks})
    else:
        spec = spec.model_copy(
            update={
                "recording_budget": spec.recording_budget.model_copy(update={"max_model_calls": 2})
            }
        )
    with pytest.raises(ValueError):
        validate_fresh(schedule, spec)


def test_existing_execution_is_not_overwritten_or_resumed(tmp_path):
    loaded, schedule, spec, config, source = inputs(tmp_path)
    state = tmp_path / "state"
    state.mkdir()
    output = tmp_path / "recording"
    factory = UppercaseFactory(spec, config)
    kwargs = dict(candidate=spec, candidate_sha256=pin(spec), source_root=source)
    first = record_candidate(
        schedule, loaded, factory, FileTrialEnvironment(state), output, **kwargs
    )
    with pytest.raises(FileExistsError):
        record_candidate(schedule, loaded, factory, FileTrialEnvironment(state), output, **kwargs)
    assert pin(first) == pin(
        read_evidence(
            output, loaded, evidence_sha256=pin(first), candidate_sha256=pin(spec)
        ).manifest
    )


def test_expired_deadline_cannot_be_sealed_as_fresh_success(tmp_path):
    loaded, schedule, spec, config, source = inputs(tmp_path)
    tasks = tuple(
        t.model_copy(
            update={
                "context": t.context.model_copy(
                    update={
                        "clock": t.context.clock - timedelta(days=1),
                        "deadline": t.context.deadline - timedelta(days=1),
                    }
                )
            }
        )
        for t in schedule.tasks
    )
    schedule = schedule.model_copy(update={"tasks": tasks})
    state = tmp_path / "state"
    state.mkdir()
    output = tmp_path / "failed"
    manifest = record_candidate(
        schedule,
        loaded,
        UppercaseFactory(spec, config),
        FileTrialEnvironment(state),
        output,
        candidate=spec,
        candidate_sha256=pin(spec),
        source_root=source,
    )
    with pytest.raises(ValueError, match="dispatch receipts"):
        read_evidence(output, loaded, evidence_sha256=pin(manifest), candidate_sha256=pin(spec))


def test_source_inventory_refuses_escape_and_missing_inventory(tmp_path):
    _, _, spec, _, _ = inputs(tmp_path)
    for values in ({}, {"../escape": "a" * 64}, {"C:/escape": "a" * 64}):
        with pytest.raises(ValueError):
            CandidateSpec.model_validate(spec.model_copy(update={"source_files": values}))
