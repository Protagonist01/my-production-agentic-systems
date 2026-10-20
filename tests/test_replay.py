"""H3: exact replay, immutable publication, safe diagnostics and no provider escape."""

import json
import os
import socket
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path

import pytest
from agent_harness.contracts import (
    Failure,
    ModelMessage,
    ModelPart,
    ModelRequest,
    ModelResponse,
    ToolCall,
    ToolSchema,
    Usage,
)
from agent_harness.gateway import ModelExchange, ProviderGateway
from agent_harness.offline_example import FakeAgent, example_case, example_context
from agent_harness.recording import (
    MAX_FIXTURE_BYTES,
    RecordingError,
    RecordingProvenance,
    load_recording,
    make_recording,
    write_recording,
)
from agent_harness.replay import ReplayBinding, ReplayMismatch, StrictReplayGateway
from pydantic import ValidationError


@pytest.fixture(autouse=True)
def no_provider(monkeypatch):
    for key in (
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "LANGFUSE_PUBLIC_KEY",
        "LANGFUSE_SECRET_KEY",
    ):
        monkeypatch.delenv(key, raising=False)

    def forbidden(*args, **kwargs):
        pytest.fail("strict replay attempted outbound network access")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)


def captured(trial="trial-1"):
    return example_context("invented-capture-source", "invented-lock").model_copy(
        update={"mode": "fresh_candidate", "trial_id": trial}
    )


def binding(source):
    return ReplayBinding(
        recorded=source,
        current=source.model_copy(
            update={
                "mode": "strict_replay",
                "run_id": "current-run",
                "versions": source.versions.model_copy(
                    update={
                        "code_revision": "current-code",
                        "candidate": "current-candidate",
                    }
                ),
            }
        ),
    )


def request(**changes):
    return ModelRequest(
        provider="fake",
        model="uppercase-v1",
        endpoint="in-process",
        messages=(ModelMessage(role="user", content=example_case().input.request),),
        parameters={"temperature": 0},
    ).model_copy(update=changes)


def response(text="HELLO, SHARED CONTRACTS", failure=None):
    return ModelResponse(
        provider="fake",
        model="uppercase-v1",
        output=None if failure else ModelMessage(role="assistant", content=text),
        failure=failure,
        usage=Usage(
            model_calls=1, input_tokens=11, output_tokens=None, cost=None, cost_currency=None
        ),
        provider_usage={"candidate_tokens": 2, "thinking_tokens": None},
    )


def provenance(**changes):
    return RecordingProvenance(
        source_kind="synthetic",
        source_version="invented-source-v1",
        snapshot_ref="invented-text-v1",
        policy_version="fake-text-policy-v1",
        scorer_version="fake-exact-text-v1",
        content_policy="invented-only-v1",
        content_review_ref="review:invented-h3-v1",
    ).model_copy(update=changes)


def recording(rows=None):
    if rows is None:
        rows = (
            ModelExchange(context=captured(), occurrence=1, request=request(), response=response()),
            ModelExchange(
                context=captured(), occurrence=2, request=request(), response=response("SECOND")
            ),
            ModelExchange(
                context=captured("trial-2"),
                occurrence=1,
                request=request(),
                response=response("OTHER TRIAL"),
            ),
        )
    return make_recording(tuple(rows), provenance())


def session(value=None):
    value = recording() if value is None else value
    contexts = {row.context.trial_id: row.context for row in value.exchanges}
    bindings = tuple(binding(source) for source in contexts.values())
    return StrictReplayGateway(value, bindings), bindings


def test_current_agent_runs_twice_and_trials_do_not_share_cursors():
    gateway, bindings = session()
    agent = FakeAgent()
    assert (
        agent.run(bindings[0].current, example_case().input, gateway).output
        == "HELLO, SHARED CONTRACTS"
    )
    assert agent.run(bindings[1].current, example_case().input, gateway).output == "OTHER TRIAL"
    assert agent.run(bindings[0].current, example_case().input, gateway).output == "SECOND"
    gateway.assert_complete()
    gateway.assert_complete()
    with pytest.raises(ReplayMismatch, match="already completed"):
        gateway.generate(bindings[0].current, request())


@pytest.mark.parametrize(
    "changes",
    [
        {"messages": (ModelMessage(role="user", content=" changed prompt "),)},
        {"parameters": {"temperature": 1}},
        {"provider": "different"},
        {"endpoint": "https://different.invalid"},
        {"model": "other"},
        {"model_revision": "other-revision"},
        {
            "tools": (
                ToolSchema(name="lookup", description="invented", parameters={"type": "object"}),
            )
        },
        {"tool_choice": {"name": "lookup"}},
        {"output_schema": {"type": "object"}},
        {"messages": (ModelMessage(role="system", content="prefix"), request().messages[0])},
    ],
)
def test_changed_requests_fail_with_evidence_and_poison_session(changes):
    gateway, bindings = session()
    with pytest.raises(ReplayMismatch) as caught:
        gateway.generate(bindings[0].current, request(**changes))
    error = caught.value
    assert error.context.case_id == captured().case_id and error.context.trial_id == "trial-1"
    assert error.occurrence == 1 and error.failure.code == "replay_mismatch"
    assert error.failure.evidence and not error.failure.retryable
    assert error.expected_fingerprint != error.actual_fingerprint
    assert "changed prompt" not in str(error)
    for attempt in (
        lambda: gateway.generate(bindings[0].current, request()),
        gateway.assert_complete,
    ):
        with pytest.raises(ReplayMismatch) as again:
            attempt()
        assert again.value is error


def test_reordered_distinct_calls_and_unconsumed_prefix_cannot_pass():
    rows = list(recording().exchanges[:2])
    rows[1] = rows[1].model_copy(update={"request": request(parameters={"temperature": 1})})
    gateway, bindings = session(recording(rows))
    with pytest.raises(ReplayMismatch, match="differs"):
        gateway.generate(bindings[0].current, rows[1].request)
    gateway, bindings = session(recording(rows))
    gateway.generate(bindings[0].current, rows[0].request)
    with pytest.raises(ReplayMismatch, match="unconsumed") as caught:
        gateway.assert_complete()
    assert caught.value.occurrence == 2


def test_extra_call_fails_without_fallback():
    gateway, bindings = session(recording(recording().exchanges[:1]))
    gateway.generate(bindings[0].current, request())
    with pytest.raises(ReplayMismatch, match="no recorded call") as caught:
        gateway.generate(bindings[0].current, request())
    assert caught.value.occurrence == 2


@pytest.mark.parametrize(
    "code", ["timeout", "rate_limited", "invalid_response", "unavailable", "permission_denied"]
)
def test_typed_recorded_failures_retain_usage_and_unknowns(code):
    failure = Failure(stage="model", code=code, message="invented safe failure", retryable=True)
    row = recording().exchanges[0].model_copy(update={"response": response(failure=failure)})
    gateway, bindings = session(recording([row]))
    result = gateway.generate(bindings[0].current, request())
    assert result.failure == failure and result.output is None
    assert result.usage.model_calls == 1 and result.usage.output_tokens is None
    assert result.usage.cost is None and result.provider_usage["thinking_tokens"] is None
    gateway.assert_complete()


@pytest.mark.parametrize(
    "changes",
    [
        {"mode": "fresh_candidate"},
        {"trial_id": "other"},
        {"case_id": "other"},
        {"tenant_id": "other"},
        {"agent_id": "other"},
        {"seed": 1},
        {"business_event_id": "other"},
        {"clock": captured().clock + timedelta(seconds=1)},
        {"deadline": captured().deadline + timedelta(seconds=1)},
    ],
)
def test_context_drift_is_rejected(changes):
    source = captured()
    with pytest.raises(ValueError):
        ReplayBinding(recorded=source, current=binding(source).current.model_copy(update=changes))
    gateway, bindings = session()
    with pytest.raises(ReplayMismatch, match="context"):
        gateway.generate(bindings[0].current.model_copy(update=changes), request())


@pytest.mark.parametrize("field", ["policy", "data_snapshot", "environment_lock"])
def test_replay_cannot_silently_change_dependency_versions(field):
    bound = binding(captured())
    changed = bound.current.model_copy(
        update={"versions": bound.current.versions.model_copy(update={field: "other"})}
    )
    with pytest.raises(ValueError, match="dependency"):
        ReplayBinding(recorded=bound.recorded, current=changed)


def test_missing_duplicate_and_fabricated_bindings_are_rejected():
    value = recording()
    bound = binding(captured())
    for bindings in ((), (bound,), (bound, bound)):
        with pytest.raises(ValueError):
            StrictReplayGateway(value, bindings)
    changed = captured().model_copy(update={"run_id": "not-captured"})
    with pytest.raises(ValueError, match="captured"):
        StrictReplayGateway(value, (binding(changed),))


def test_recording_sort_does_not_merge_repeated_requests_and_rejects_gaps():
    value = recording()
    assert make_recording(tuple(reversed(value.exchanges)), provenance()) == value
    for rows in ((value.exchanges[1],), (value.exchanges[0], value.exchanges[0])):
        with pytest.raises(ValueError, match="occurrences"):
            recording(rows)
    changed = value.exchanges[1].model_copy(
        update={"context": captured().model_copy(update={"seed": 1})}
    )
    with pytest.raises(ValueError, match="context changes"):
        recording((value.exchanges[0], changed))


def test_provenance_and_route_validation():
    value = recording()
    for field in ("snapshot_ref", "policy_version"):
        with pytest.raises(ValueError, match="provenance"):
            make_recording(value.exchanges, provenance(**{field: "different"}))
    row = value.exchanges[0]
    for changes in ({"provider": "other"}, {"model": "other"}):
        with pytest.raises(ValueError, match="route"):
            recording(
                [row.model_copy(update={"response": row.response.model_copy(update=changes)})]
            )


def test_record_replay_and_returned_values_are_detached():
    value = recording()
    gateway, bindings = session(value)
    value.exchanges[0].request.parameters["temperature"] = 99
    result = gateway.generate(bindings[0].current, request())
    result.provider_usage["candidate_tokens"] = 999
    second = gateway.generate(bindings[0].current, request())
    assert second.provider_usage["candidate_tokens"] == 2
    gateway.generate(bindings[1].current, request())
    gateway.assert_complete()


def test_signed_tool_history_is_preserved_and_matched_exactly():
    call = ToolCall(
        call_id="local-1",
        provider_call_id="provider-1",
        name="lookup",
        arguments={"key": "invented"},
    )
    output = ModelMessage(
        role="assistant",
        tool_calls=(call,),
        parts=(ModelPart(tool_call=call, thought_signature="YWJj"),),
    )
    first = (
        recording()
        .exchanges[0]
        .model_copy(update={"response": response().model_copy(update={"output": output})})
    )
    followup = request(
        messages=(
            *request().messages,
            output,
            ModelMessage(
                role="tool", content='{"answer":42}', tool_call_id="local-1", tool_name="lookup"
            ),
        )
    )
    second = first.model_copy(
        update={"occurrence": 2, "request": followup, "response": response("42")}
    )
    value = recording([first, second])
    gateway, bindings = session(value)
    returned = gateway.generate(bindings[0].current, first.request)
    assert returned.output.parts[0].thought_signature == "YWJj"
    assert returned.output.tool_calls[0].provider_call_id == "provider-1"
    assert gateway.generate(bindings[0].current, followup).output.content == "42"
    gateway.assert_complete()
    gateway, bindings = session(value)
    gateway.generate(bindings[0].current, first.request)
    altered = followup.model_copy(
        update={
            "messages": (
                *request().messages,
                output.model_copy(update={"parts": ()}),
                followup.messages[-1],
            )
        }
    )
    with pytest.raises(ReplayMismatch):
        gateway.generate(bindings[0].current, altered)


def test_live_gateway_cannot_be_used_as_replay_escape():
    class Forbidden:
        def generate(self, value):
            pytest.fail("provider transport dispatched in replay")

    result = ProviderGateway(Forbidden()).generate(binding(captured()).current, request())
    assert result.failure.code == "permission_denied" and result.usage.model_calls == 0


def test_exclusive_fixture_publication_and_concurrent_writers(tmp_path):
    path = tmp_path / "fixture.json"
    value = recording()

    def publish():
        try:
            return write_recording(path, value)
        except FileExistsError:
            return "exists"

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: publish(), range(4)))
    assert results.count(value.digest()) == 1 and results.count("exists") == 3
    original = path.read_bytes()
    with pytest.raises(FileExistsError):
        write_recording(path, value)
    assert (
        path.read_bytes() == original
        and load_recording(path, expected_digest=value.digest()) == value
    )
    assert list(tmp_path.glob(".capture-*")) == []


def test_publication_error_cleans_staging_without_partial_destination(monkeypatch, tmp_path):
    import agent_harness.recording as module

    def fail(*args):
        raise OSError("invented link failure")

    monkeypatch.setattr(module.os, "link", fail)
    with pytest.raises(OSError):
        write_recording(tmp_path / "fixture.json", recording())
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "secret",
    [
        "private\nvalue",
        "Bearer invented-token",
        "sk-lf-" + "a" * 36,
        "https://user:password@example.invalid",
    ],
)
def test_forbidden_content_is_never_written_or_echoed(secret, tmp_path):
    row = recording().exchanges[0].model_copy(update={"response": response(secret)})
    with pytest.raises(RecordingError) as caught:
        write_recording(tmp_path / "fixture.json", recording([row]), forbidden_values=(secret,))
    assert secret not in str(caught.value) and list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "mutate",
    [
        lambda v: v.update(schema_version=99),
        lambda v: v["exchanges"][0]["request"].update(serializer_version=1),
        lambda v: v["exchanges"][0]["response"]["output"].update(content="tampered"),
        lambda v: v["provenance"].update(source_version="tampered"),
        lambda v: v["exchanges"].pop(),
    ],
)
def test_tampered_fixtures_fail_before_replay(mutate, tmp_path):
    value = recording()
    document = json.loads(value.canonical_json())
    mutate(document)
    path = tmp_path / "fixture.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(RecordingError):
        load_recording(path, expected_digest=value.digest())


@pytest.mark.parametrize(
    "text",
    [
        '{"schema_version":1,"schema_version":1}',
        '{"value":NaN}',
        '{"value":Infinity}',
        "{",
        "[]",
        '"malformed private content"',
    ],
)
def test_malformed_documents_do_not_echo_contents(text, tmp_path):
    path = tmp_path / "fixture.json"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(RecordingError) as caught:
        load_recording(path, expected_digest="0" * 64)
    assert text not in str(caught.value)


def test_bad_pins_and_oversized_documents_fail_closed(tmp_path):
    path = tmp_path / "fixture.json"
    for pin in ("", "a" * 63, "A" * 64, "../fixture"):
        with pytest.raises(RecordingError, match="pin"):
            load_recording(path, expected_digest=pin)
    path.write_bytes(b" " * (MAX_FIXTURE_BYTES + 1))
    with pytest.raises(RecordingError, match="limit"):
        load_recording(path, expected_digest="0" * 64)


def test_nested_nonfinite_mutation_is_rejected_before_storage_or_replay(tmp_path):
    value = recording()
    value.exchanges[0].request.parameters["temperature"] = float("nan")
    with pytest.raises(ValidationError):
        write_recording(tmp_path / "fixture.json", value)
    assert not (tmp_path / "fixture.json").exists()
    with pytest.raises(ValidationError):
        StrictReplayGateway(value, (binding(captured()), binding(captured("trial-2"))))


def test_concurrent_consumption_allocates_each_occurrence_once():
    rows = [
        recording().exchanges[0].model_copy(update={"occurrence": i, "response": response(str(i))})
        for i in range(1, 21)
    ]
    gateway, bindings = session(recording(rows))
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(
            pool.map(
                lambda _: gateway.generate(bindings[0].current, request()).output.content, range(20)
            )
        )
    assert sorted(results, key=int) == list(map(str, range(1, 21)))
    gateway.assert_complete()


def test_invented_probe_executes_current_code_and_retains_both_provenances(monkeypatch):
    from agent_harness.replay_example import invented_recording, run_invented_replay

    value = invented_recording("capture-code", "actual-lock")
    result = run_invented_replay(value, code_revision="new-code", environment_lock="actual-lock")
    assert result["capture_code_revision"] == "capture-code"
    assert result["current_code_revision"] == "new-code"
    assert result["recorded_calls_consumed"] == 6
    assert result["recorded_timeouts_reproduced"] == 2
    assert result["outbound_provider_calls"] == 0 and not result["quality_evaluation"]
    original = FakeAgent.run

    def changed(self, context, input, gateway):
        return original(
            self, context, input.model_copy(update={"request": "changed current code"}), gateway
        )

    monkeypatch.setattr(FakeAgent, "run", changed)
    with pytest.raises(ReplayMismatch, match="differs"):
        run_invented_replay(value, code_revision="changed-code", environment_lock="actual-lock")


def test_probe_refuses_environment_drift():
    from agent_harness.replay_example import invented_recording, run_invented_replay

    value = invented_recording("capture-code", "capture-lock")
    with pytest.raises(ValueError, match="dependency conditions"):
        run_invented_replay(value, code_revision="new-code", environment_lock="changed-lock")


def test_partial_disk_write_cannot_publish_a_fixture(monkeypatch, tmp_path):
    import agent_harness.recording as module

    def fail(*args):
        raise OSError("invented fsync failure")

    monkeypatch.setattr(module.os, "fsync", fail)
    with pytest.raises(OSError):
        write_recording(tmp_path / "fixture.json", recording())
    assert list(tmp_path.iterdir()) == []


def test_loaded_records_do_not_depend_on_later_file_edits(tmp_path):
    path = tmp_path / "fixture.json"
    value = recording()
    write_recording(path, value)
    loaded = load_recording(path, expected_digest=value.digest())
    gateway, bindings = session(loaded)
    path.write_text("corrupted after load", encoding="utf-8")
    assert (
        gateway.generate(bindings[0].current, request()).output.content == "HELLO, SHARED CONTRACTS"
    )
    with pytest.raises(RecordingError):
        load_recording(path, expected_digest=value.digest())


def test_recorded_error_text_is_included_in_content_review(tmp_path):
    failure = Failure(
        stage="model", code="unavailable", message="private-error-value", retryable=True
    )
    row = recording().exchanges[0].model_copy(update={"response": response(failure=failure)})
    with pytest.raises(RecordingError, match="review failed"):
        write_recording(
            tmp_path / "fixture.json", recording([row]), forbidden_values=("private-error-value",)
        )
    assert not (tmp_path / "fixture.json").exists()


def test_replay_cannot_be_recaptured_as_new_evidence():
    row = recording().exchanges[0]
    replayed = row.model_copy(update={"context": binding(captured()).current})
    with pytest.raises(ValueError, match="replayed"):
        recording([replayed])


def test_non_synthetic_source_cannot_claim_offline_fake_capture():
    row = (
        recording()
        .exchanges[0]
        .model_copy(update={"context": captured().model_copy(update={"mode": "offline_fake"})})
    )
    with pytest.raises(ValueError, match="synthetic"):
        make_recording((row,), provenance(source_kind="original"))


def test_budget_and_full_context_are_part_of_binding():
    source = captured()
    current = binding(source).current
    current = current.model_copy(
        update={"budget": current.budget.model_copy(update={"max_tokens": 999})}
    )
    with pytest.raises(ValueError, match="dependency"):
        ReplayBinding(recorded=source, current=current)


def test_unknown_and_empty_review_provenance_fails_validation():
    for changes in ({"schema_version": 99}, {"content_review_ref": ""}, {"content_policy": ""}):
        with pytest.raises(ValidationError):
            make_recording(recording().exchanges, provenance(**changes))


def test_invalid_request_cannot_be_caught_and_retried_into_a_passing_session():
    gateway, bindings = session()
    invalid = request()
    invalid.parameters["temperature"] = float("nan")
    with pytest.raises(ReplayMismatch, match="invalid model request") as caught:
        gateway.generate(bindings[0].current, invalid)
    with pytest.raises(ReplayMismatch) as again:
        gateway.generate(bindings[0].current, request())
    assert caught.value is again.value


def test_packaged_fixture_pin_and_current_agent_execution():
    from importlib.resources import as_file, files

    from agent_harness.replay_example import INVENTED_DIGEST, INVENTED_RESOURCE, run_invented_replay

    with as_file(files("agent_harness").joinpath(INVENTED_RESOURCE)) as path:
        value = load_recording(path, expected_digest=INVENTED_DIGEST)
    lock = value.exchanges[0].context.versions.environment_lock
    report = run_invented_replay(value, code_revision="current-test-code", environment_lock=lock)
    assert report["recorded_calls_consumed"] == 6
    assert report["recorded_timeouts_reproduced"] == 2
    assert value.provenance.source_kind == "synthetic"


def test_standalone_process_blocks_connect_dns_and_datagrams_without_provider_imports(tmp_path):
    script = """
import socket,sys
from agent_harness.replay_example import _deny_network, NetworkDisabledError
sys.addaudithook(_deny_network)
denied = 0
with socket.socket() as stream, socket.socket(type=socket.SOCK_DGRAM) as datagram:
    for attempt in (
        lambda: stream.connect(("127.0.0.1", 9)),
        lambda: socket.getaddrinfo("example.invalid", 443),
        lambda: datagram.sendto(b"invented", ("127.0.0.1", 9)),
    ):
        try:
            attempt()
        except NetworkDisabledError:
            denied += 1
assert denied == 3
assert "google.genai" not in sys.modules and "langfuse" not in sys.modules
print("three network operations denied; no provider SDK imported")
"""
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("GEMINI_", "GOOGLE_", "LANGFUSE_", "OPENAI_", "ANTHROPIC_"))
    }
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
    assert "three network operations denied" in result.stdout


def test_replay_cli_runs_without_credentials_or_services(tmp_path):
    root = Path(__file__).resolve().parents[1]
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("GEMINI_", "GOOGLE_", "LANGFUSE_", "OPENAI_", "ANTHROPIC_"))
    }
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_harness.replay_example",
            "--code-revision",
            "current-cli-source",
            "--lockfile",
            str(root / "uv.lock"),
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["current_code_revision"] == "current-cli-source"
    assert report["recorded_calls_consumed"] == 6 and report["outbound_provider_calls"] == 0


@pytest.mark.parametrize(
    "filename,pin",
    [
        ("invented-v1.json", "72125a30c816dca9f2e72b3ac6f4fc5e718ee9386c95f6243db43ba19702ac2b"),
        ("invented-v2.json", "0d05fc31a93abe4872000aeb81895d5bbf0529f1f427b849edc16e366ce2432e"),
        ("invented-v3.json", "434e62b9e97f6164b41412d94317c257914d6e6d8c6ec5adeedc286db78ea345"),
    ],
)
def test_historical_fixture_is_unchanged_and_refuses_current_dependency_lock(filename, pin):
    import hashlib
    from importlib.resources import as_file, files

    from agent_harness.replay_example import run_invented_replay

    with as_file(files("agent_harness").joinpath("resources/replay/" + filename)) as path:
        old = load_recording(path, expected_digest=pin)
    current_lock = hashlib.sha256(
        (Path(__file__).resolve().parents[1] / "uv.lock").read_bytes()
    ).hexdigest()
    assert old.exchanges[0].context.versions.environment_lock != current_lock
    with pytest.raises(ValueError, match="dependency"):
        run_invented_replay(old, code_revision="current-source", environment_lock=current_lock)
