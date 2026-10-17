"""Invented telemetry canaries, hierarchy, lifecycle and owned-worker evidence."""

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from agent_harness.contracts import ModelMessage, ModelRequest, PublicObservation
from agent_harness.evaluation import run_case
from agent_harness.langfuse_export import LangfuseExporter, accepted, encode
from agent_harness.offline_example import (
    FakeAgent,
    FakeGateway,
    FakeScorer,
    example_case,
    example_context,
)
from agent_harness.telemetry import TracedGateway, TraceSession
from agent_harness.trial_example import FileTrialEnvironment, InventedFactory, invented_schedule
from agent_harness.trial_runner import TrialComponents, run_trials
from agent_harness.trials import TrialJournal
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
    ExportTraceServiceRequest,
    ExportTraceServiceResponse,
)

CANARY = "PRIVATE-ID-secret-example-7259"
KEY = b"invented-test-private-key-32-bytes!!"


class MemoryExporter:
    def __init__(self, bad=None):
        self.bad = bad
        self.calls = []
        self.spans = ()

    def export(self, spans):
        self.calls.append("export")
        self.spans = spans
        if self.bad == "export_raise":
            raise RuntimeError(CANARY)
        return self.bad != "export"

    def flush(self):
        self.calls.append("flush")
        if self.bad == "flush_raise":
            raise RuntimeError(CANARY)
        return self.bad != "flush"

    def shutdown(self):
        self.calls.append("shutdown")
        if self.bad == "shutdown":
            raise RuntimeError(CANARY)


class InstrumentedAgent:
    def __init__(self, trace):
        self.trace = trace

    def run(self, context, input, gateway):
        def node():
            result = FakeAgent().run(context, input, gateway)
            self.trace.invoke("policy", CANARY, lambda: "allow")
            self.trace.invoke("tool", CANARY, lambda: result.output)
            return result

        return self.trace.invoke("node", CANARY, node)


def execute(exporter=None, *, limit=256):
    exporter = exporter or MemoryExporter()
    trace = TraceSession(exporter, KEY, max_spans=limit)
    context = example_context("invented-source", "invented-lock")
    report = run_case(
        context, example_case(), InstrumentedAgent(trace), FakeGateway(), FakeScorer(), trace=trace
    )
    return trace, exporter, report


def test_tree_reaches_model_policy_tool_result_and_scorer():
    trace, exporter, report = execute()
    spans = {span.kind: span for span in exporter.spans}
    assert len(spans) == 7
    assert spans["run"].parent_id is None
    assert spans["agent"].parent_id == spans["scorer"].parent_id == spans["run"].span_id
    assert spans["node"].parent_id == spans["agent"].span_id
    assert {spans[k].parent_id for k in ("model", "policy", "tool")} == {spans["node"].span_id}
    assert spans["model"].attributes["input_tokens"] == 0
    assert "result_ref" in spans["tool"].attributes
    assert report.result.outcome == "completed" and report.scores[0].value == 1
    assert report.telemetry.healthy and report.telemetry == trace.health
    assert exporter.calls == ["export", "flush", "shutdown"]
    assert trace.finish() == trace.health
    assert exporter.calls == ["export", "flush", "shutdown"]


@pytest.mark.parametrize("bad", ["export", "export_raise", "flush", "flush_raise", "shutdown"])
def test_export_lifecycle_failure_retains_result_and_score(bad, caplog):
    trace, exporter, report = execute(MemoryExporter(bad))
    assert report.result.outcome == "completed" and report.scores[0].value == 1
    assert not trace.health.healthy
    assert exporter.calls == ["export", "flush", "shutdown"]
    assert CANARY not in trace.health.canonical_json() + caplog.text
    assert (trace.health.export == "failed") == bad.startswith("export")


def test_canaries_across_inputs_identifiers_versions_sources_and_output_never_export():
    context = example_context(CANARY, CANARY)
    context = context.model_copy(
        update={
            name: CANARY
            for name in (
                "run_id",
                "tenant_id",
                "agent_id",
                "case_id",
                "trial_id",
                "business_event_id",
            )
        }
    )
    context = context.model_copy(
        update={
            "versions": context.versions.model_copy(
                update={
                    "candidate": CANARY,
                    "data_snapshot": CANARY,
                    "policy": CANARY,
                }
            )
        }
    )
    case = example_case().model_copy(
        update={
            "case_id": CANARY,
            "snapshot_ref": CANARY,
            "policy_version": CANARY,
            "source_version": CANARY,
            "scorer_version": CANARY,
            "input": example_case().input.model_copy(
                update={
                    "request": CANARY,
                    "observations": (PublicObservation(reference=CANARY, text=CANARY),),
                }
            ),
        }
    )
    exporter = MemoryExporter()
    trace = TraceSession(exporter, KEY)
    report = run_case(
        context, case, InstrumentedAgent(trace), FakeGateway(), FakeScorer(), trace=trace
    )
    wire = json.dumps([asdict(s) for s in exporter.spans])
    assert CANARY not in wire and CANARY.upper() not in wire
    assert CANARY not in report.telemetry.canonical_json()
    # Full evaluator reports intentionally remain private and retain runtime identity.
    assert CANARY in report.canonical_json()
    payload = encode(exporter.spans)
    decoded = str(ExportTraceServiceRequest.FromString(payload))
    assert CANARY not in decoded and CANARY.upper() not in decoded
    assert KEY.decode() not in decoded


def test_arbitrary_model_name_endpoint_and_exception_never_export():
    exporter = MemoryExporter()
    trace = TraceSession(exporter, KEY)

    class BrokenGateway:
        def generate(self, context, request):
            raise RuntimeError(CANARY)

    with pytest.raises(RuntimeError, match=CANARY):
        run_case(
            example_context("source", "lock"),
            example_case(),
            InstrumentedAgent(trace),
            BrokenGateway(),
            FakeScorer(),
            trace=trace,
        )
    assert trace.health.healthy
    assert any(s.failed for s in exporter.spans)
    assert CANARY not in str(ExportTraceServiceRequest.FromString(encode(exporter.spans)))


def test_capacity_keeps_parents_and_drops_visibly():
    trace, exporter, report = execute(limit=2)
    assert {s.kind for s in exporter.spans} == {"run", "agent"}
    assert trace.health.dropped == 5 and not trace.health.healthy
    assert report.result.outcome == "completed"


def test_context_parent_restored_after_error_and_thread_isolation():
    exporter = MemoryExporter()
    trace = TraceSession(exporter, KEY)
    attrs = trace.begin(example_context("source", "lock"), example_case())
    with trace._span("run", attrs):

        def parallel(index):
            with trace._span("node", {}) as data:
                trace.invoke("tool", str(index), lambda: str(index))
                data["worker"] = index

        with ThreadPoolExecutor(2) as pool:
            list(pool.map(parallel, (1, 2)))
        with pytest.raises(RuntimeError):
            trace.invoke("tool", "broken", lambda: (_ for _ in ()).throw(RuntimeError(CANARY)))
        trace.invoke("tool", "last", lambda: "done")
        with pytest.raises(ValueError, match="active"):
            trace.finish()
    trace.finish()
    nodes = [s for s in exporter.spans if s.kind == "node"]
    assert len(nodes) == 2 and len({n.span_id for n in nodes}) == 2
    root = next(s for s in exporter.spans if s.kind == "run")
    assert all(n.parent_id == root.span_id for n in nodes)
    tools = [s for s in exporter.spans if s.kind == "tool"]
    for node in nodes:
        assert sum(s.parent_id == node.span_id for s in tools) == 1
    assert tools[-1].parent_id == tools[-2].parent_id
    assert tools[-2].failed and not tools[-1].failed


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com",
        "https://u:p@example.com",
        "https://example.com/path",
        "https://example.com?q=secret",
        "file:///tmp/a",
    ],
)
def test_exporter_requires_explicit_safe_origin(url):
    with pytest.raises(ValueError):
        LangfuseExporter(url, "public", "private")


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf"), 31])
def test_exporter_timeout_checked_before_network(timeout):
    with pytest.raises(ValueError):
        LangfuseExporter("http://localhost:3000", "p", "s", timeout=timeout)


def test_actual_otlp_mapping_uses_closed_resource_and_types(monkeypatch):
    monkeypatch.setenv("OTEL_RESOURCE_ATTRIBUTES", "private=" + CANARY)
    _, exporter, _ = execute()
    payload = encode(exporter.spans)
    request = ExportTraceServiceRequest.FromString(payload)
    assert CANARY not in str(request)
    assert len(request.resource_spans) == 1
    assert len(request.resource_spans[0].resource.attributes) == 1
    attrs = [
        {a.key: a.value for a in s.attributes}
        for s in request.resource_spans[0].scope_spans[0].spans
    ]
    assert {a["langfuse.observation.type"].string_value for a in attrs} == {
        "chain",
        "agent",
        "span",
        "generation",
        "tool",
        "guardrail",
        "evaluator",
    }


@dataclass(frozen=True)
class TracedFactory:
    bad: str = "export"
    crash: bool = False

    def build(self, context, state):
        parts = InventedFactory().build(context, state)
        return TrialComponents(
            CrashingAgent() if self.crash else parts.agent,
            parts.gateway,
            parts.scorers,
            TraceSession(MemoryExporter(self.bad), KEY),
        )


class CrashingAgent:
    def run(self, *args):
        raise RuntimeError(CANARY)


def test_spawned_trial_retains_health_through_journal_recovery(tmp_path):
    loaded, schedule = invented_schedule("source", "lock")
    tasks = tuple(
        t.model_copy(
            update={
                "context": t.context.model_copy(
                    update={"deadline": t.context.clock + timedelta(seconds=120)}
                )
            }
        )
        for t in schedule.tasks
    )
    schedule = schedule.model_copy(update={"tasks": tasks, "worker_timeout_seconds": 90.0})
    state = tmp_path / "state"
    state.mkdir()
    report = run_trials(
        schedule, loaded, TracedFactory(), FileTrialEnvironment(state), tmp_path / "journal"
    )
    assert report.autonomous_completions == 2
    assert all(row.telemetry.export == "failed" for row in report.rows)
    assert all(row.report.report.telemetry == row.telemetry for row in report.rows)
    assert TrialJournal(tmp_path / "journal").read(loaded) == report


@pytest.mark.parametrize(
    "body,expected",
    [
        ({}, True),
        ({"partialSuccess": {}}, True),
        ({"partialSuccess": {"rejectedSpans": "1"}}, False),
        ({"partialSuccess": {"errorMessage": CANARY}}, False),
        ({"error": CANARY}, False),
        ([], False),
        (
            {
                "id": "invented-job",
                "name": "ingest",
                "data": {},
                "queueQualifiedName": "invented-queue",
            },
            True,
        ),
    ],
)
def test_json_acceptance_and_partial_rejection(body, expected):
    assert accepted(json.dumps(body).encode(), "application/json; charset=utf-8") is expected


def test_protobuf_partial_rejection_is_failure():
    response = ExportTraceServiceResponse()
    assert accepted(response.SerializeToString(), "application/x-protobuf")
    response.partial_success.rejected_spans = 1
    assert not accepted(response.SerializeToString(), "application/x-protobuf")


@contextmanager
def backend(status, body=b"", *, redirect=False):
    seen = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            seen.append(
                (
                    self.path,
                    self.headers.get("Authorization"),
                    self.rfile.read(int(self.headers["Content-Length"])),
                )
            )
            self.send_response(status)
            self.send_header("Content-Type", "application/x-protobuf")
            if redirect:
                self.send_header("Location", "/credential-trap")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", seen
    finally:
        server.shutdown()
        thread.join(5)
        server.server_close()


@pytest.mark.parametrize(
    "status,body", [(200, b""), (401, b""), (503, CANARY.encode()), (200, b"malformed"), (302, b"")]
)
def test_actual_http_wire_and_redirect_failures(status, body, capsys, caplog, monkeypatch):
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:1")
    _, memory, _ = execute()
    with backend(status, body, redirect=status == 302) as (origin, seen):
        exporter = LangfuseExporter(origin, "invented-public", CANARY)
        assert exporter.export(memory.spans) == (status == 200 and body == b"")
        assert exporter.flush()
        exporter.shutdown()
        assert not exporter.flush() and not exporter.export(memory.spans)
    assert len(seen) == 1 and seen[0][0] == "/api/public/otel/v1/traces"
    assert seen[0][1].startswith("Basic ")
    assert CANARY.encode() not in seen[0][2]
    assert CANARY not in capsys.readouterr().out + caplog.text


def test_invalid_context_cannot_export_raw_mode_and_still_cleans_up():
    memory = MemoryExporter()
    trace = TraceSession(memory, KEY)
    context = example_context("source", "lock").model_copy(update={"mode": CANARY})
    with pytest.raises(ValueError):
        run_case(context, example_case(), FakeAgent(), FakeGateway(), FakeScorer(), trace=trace)
    assert trace.health.export == "empty"
    assert memory.calls == ["flush", "shutdown"]


@pytest.mark.parametrize("stage", ["agent", "scorer"])
def test_runtime_exception_preserved_while_export_also_fails(stage):
    class Broken:
        def run(self, *args):
            raise RuntimeError(CANARY)

        def score(self, *args):
            raise RuntimeError(CANARY)

    trace = TraceSession(MemoryExporter("export_raise"), KEY)
    with pytest.raises(RuntimeError, match=CANARY):
        run_case(
            example_context("source", "lock"),
            example_case(),
            Broken() if stage == "agent" else FakeAgent(),
            FakeGateway(),
            Broken() if stage == "scorer" else FakeScorer(),
            trace=trace,
        )
    assert trace.health.export == "failed" and trace.health.cleanup == "ok"


def test_failed_worker_still_retains_export_health(tmp_path):
    loaded, schedule = invented_schedule("source", "lock")
    tasks = tuple(
        t.model_copy(
            update={
                "context": t.context.model_copy(
                    update={"deadline": t.context.clock + timedelta(seconds=120)}
                )
            }
        )
        for t in schedule.tasks
    )
    schedule = schedule.model_copy(update={"tasks": tasks, "worker_timeout_seconds": 90.0})
    state = tmp_path / "state"
    state.mkdir()
    report = run_trials(
        schedule,
        loaded,
        TracedFactory(crash=True),
        FileTrialEnvironment(state),
        tmp_path / "journal",
    )
    assert report.eligible_trials == 2 and not report.complete
    assert all(row.errors == ("execution_error",) and row.report is None for row in report.rows)
    assert all(
        row.telemetry.export == "failed" and row.telemetry.cleanup == "ok" for row in report.rows
    )
    assert TrialJournal(tmp_path / "journal").read(loaded) == report


def test_untrusted_model_metadata_and_schema_only_export_as_references():
    memory = MemoryExporter()
    trace = TraceSession(memory, KEY)
    context = example_context("source", "lock")
    request = ModelRequest(
        provider=CANARY,
        endpoint=CANARY,
        model=CANARY,
        model_revision=CANARY,
        messages=(ModelMessage(role="user", content=CANARY),),
        parameters={CANARY: CANARY},
        output_schema={"description": CANARY},
    )

    class Gateway:
        def generate(self, context, request):
            from agent_harness.contracts import ModelResponse, Usage

            return ModelResponse(
                provider=CANARY,
                model=CANARY,
                model_revision=CANARY,
                provider_request_id=CANARY,
                finish_reason=CANARY,
                output=ModelMessage(role="assistant", content=CANARY),
                usage=Usage(
                    model_calls=1,
                    input_tokens=None,
                    output_tokens=None,
                    cost=None,
                    cost_currency=None,
                ),
            )

    attrs = trace.begin(context, example_case())
    with trace._span("run", attrs):
        response = TracedGateway(trace, Gateway()).generate(context, request)
    trace.finish()
    assert response.output.content == CANARY
    raw = str(ExportTraceServiceRequest.FromString(encode(memory.spans)))
    assert CANARY not in raw and "input_tokens" not in raw and "output_tokens" not in raw


@pytest.mark.parametrize(
    "change", ["valid", "missing_source", "bad_parent", "canary", "wrong_code"]
)
def test_cli_readback_checks_real_envelope_and_evidence(change):
    from agent_harness.telemetry_probe import validate_readback

    parents = {
        "run": None,
        "agent": "run",
        "scorer": "run",
        "node": "agent",
        "model": "node",
        "tool": "node",
        "policy": "node",
    }
    types = {
        "run": "CHAIN",
        "agent": "AGENT",
        "scorer": "EVALUATOR",
        "node": "SPAN",
        "model": "GENERATION",
        "tool": "TOOL",
        "policy": "GUARDRAIL",
    }
    rows = []
    versions = {
        "version_" + name: "a" * 64
        for name in ("code_revision", "candidate", "policy", "environment_lock", "data_snapshot")
    }
    for kind, parent in parents.items():
        rows.append(
            dict(
                id=kind,
                traceId="b" * 32,
                name="harness-" + kind,
                type=types[kind],
                parentObservationId=parent,
                projectId="invented-project",
                metadata={},
            )
        )
    by_name = {r["id"]: r for r in rows}
    by_name["run"]["output"] = {"outcome": "completed"}
    by_name["run"]["metadata"] = {
        **versions,
        "source_version": "c" * 64,
        "scorer_version": "d" * 64,
        "source_count": 1,
        "source_refs": ["e" * 64],
    }
    by_name["model"].update(
        model="model-" + "f" * 64, usageDetails={"input": 0, "output": 0, "total": 0}
    )
    by_name["tool"]["metadata"] = {"result_ref": "a" * 64}
    if change == "missing_source":
        by_name["run"]["metadata"]["source_count"] = 0
    if change == "bad_parent":
        by_name["tool"]["parentObservationId"] = "model"
    if change == "canary":
        by_name["tool"]["output"] = CANARY
    if change == "wrong_code":
        by_name["run"]["metadata"]["version_code_revision"] = "0" * 64
    raw = json.dumps({"status": 200, "body": {"data": rows}})
    if change == "valid":
        assert validate_readback(raw, "b" * 32, (CANARY,), versions)["versions_verified"]
    else:
        with pytest.raises(ValueError):
            validate_readback(raw, "b" * 32, (CANARY,), versions)
