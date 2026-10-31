"""Invented 417-row history and prospective routing scopes. Never reads a real allowance."""

import json
import sqlite3
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx
import pytest
from agent_harness.admission import GEMINI_TOKEN_CEILING
from agent_harness.contracts import Budget, ModelMessage, ModelRequest, ModelResponse, Usage
from agent_harness.controls import ExecutionPolicy
from agent_harness.gemini import ENDPOINT, MODEL, PROVIDER
from agent_harness.model_budget import append_model_extension, model_canaries
from agent_harness.provider_budget import AttemptLedger
from agent_harness.release_contracts import CandidateSpec, pin, sha256
from agent_harness.routing_budget import (
    RoutingExtension,
    RoutingSlot,
    append_routing_extension,
    behavior_pin,
)
from olist_routing_fixtures import ROOT, label_for
from olist_support.policy import POLICY_VERSION
from olist_support.routing_evaluation import RoutingPopulation
from olist_support.routing_provider import RoutingCaptureControls, controlled_fingerprints
from olist_support.workflow import GatewayPlanner, RoutingGatewayPlanner, WorkflowRequest
from test_model_comparison import history
from test_provider_budget_accounting import tariff


@pytest.fixture(scope="module")
def settled_history(tmp_path_factory):
    root = tmp_path_factory.mktemp("invented-routing-history")
    old, ctx, extension, _, _ = history(root)
    newpin = append_model_extension(old, extension)
    store = AttemptLedger(old.path, *extension.historical_pins, newpin)
    for request in model_canaries():
        slot = next(s for s in extension.slots if s.request_sha256 == pin(request))
        context = ctx.model_copy(
            update={
                "agent_id": "revenue",
                "run_id": extension.run_id,
                "case_id": slot.case_id,
                "trial_id": slot.trial_id,
            }
        )
        from test_provider_budget_accounting import response

        store.settle(store.reserve(context, request, project_sha256="a" * 64), response(request))
    assert store.summary()["consumed"] == 417
    return store, ctx


def copy_history(base, path):
    store, ctx = base
    src = sqlite3.connect(store.path)
    dst = sqlite3.connect(path)
    try:
        src.backup(dst)
    finally:
        src.close()
        dst.close()
    return replace(store, path=path), ctx


class Capture:
    request = None

    def generate(self, ctx, request):
        self.request = request
        return ModelResponse(
            provider=request.provider,
            model=request.model,
            output=ModelMessage(role="assistant", content='{"intent":"review"}'),
            usage=Usage(
                model_calls=0, input_tokens=0, output_tokens=0, cost=None, cost_currency=None
            ),
        )


def fake_sdk(request):
    wire = json.loads(request.content)
    text = wire["contents"][0]["parts"][0]["text"]
    assert text.startswith("Invented routing")
    assert not wire.get("tools") and wire["generationConfig"]["maxOutputTokens"] == 512
    out = {"intent": "refund", "requested_minor": None}
    if "routing_version" in wire["generationConfig"]["responseJsonSchema"]["properties"]:
        out["routing_version"] = "olist-intent-routing-v2"
    return httpx.Response(
        200,
        json={
            "candidates": [
                {
                    "content": {"role": "model", "parts": [{"text": json.dumps(out)}]},
                    "finishReason": "STOP",
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 3,
                "candidatesTokenCount": 5,
                "totalTokenCount": 8,
            },
        },
    )


def setup_scope(base, path, *, first_intent="refund", origin="mock"):
    old, ctx = copy_history(base, path)
    ctx = ctx.model_copy(
        update={
            "budget": Budget(
                max_model_calls=1,
                max_tokens=GEMINI_TOKEN_CEILING,
                max_cost=Decimal(0),
                cost_currency="USD",
            )
        }
    )
    route = ModelRequest(
        provider=PROVIDER,
        model=MODEL,
        endpoint=ENDPOINT,
        messages=(ModelMessage(role="user", content="unused"),),
        parameters={"temperature": 0.0, "max_output_tokens": 512, "thinking_level": "LOW"},
    )
    source = {"uv.lock": sha256((ROOT / "uv.lock").read_bytes())}
    for prefix in ("harness/src/agent_harness", "projects/olist-support/src/olist_support"):
        for p in (ROOT / prefix).rglob("*"):
            if p.is_file() and p.suffix in (".py", ".sql"):
                source[p.relative_to(ROOT).as_posix()] = sha256(p.read_bytes())
    specs = {
        v: CandidateSpec(
            candidate="invented-routing-" + v,
            code_revision="invented-routing-source",
            environment_lock=source["uv.lock"],
            source_files=source,
            **controlled_fingerprints(route, source, v),
            execution=ExecutionPolicy(max_attempts=1, attempt_timeout_seconds=30.0),
            recording_budget=Budget(
                max_model_calls=3,
                max_tokens=3 * GEMINI_TOKEN_CEILING,
                max_cost=Decimal(0),
                cost_currency="USD",
            ),
        )
        for v in ("candidate", "legacy")
    }
    labels = []
    for i in range(24):
        c = label_for(first_intent if i == 0 else "refund")
        order = c.order.model_copy(update={"order_id": "invented-routing-order-" + str(i)})
        labels.append(
            c.model_copy(
                update={
                    "case_id": sha256(str(i).encode()),
                    "group_id": sha256(("group" + str(i)).encode()),
                    "language_family": "invented-" + str(i),
                    "order": order,
                    "confirmation": c.confirmation.model_copy(update={"order_id": order.order_id}),
                    "reference": c.reference.model_copy(
                        update={"text": "Invented routing request " + str(0 if i == 1 else i)}
                    ),
                }
            )
        )
    population = RoutingPopulation.model_validate_json(
        RoutingPopulation(entries=tuple(labels)).canonical_json()
    )
    slots = []
    requests = {}

    def request_for(variant, text):
        capture = Capture()
        (RoutingGatewayPlanner if variant == "candidate" else GatewayPlanner)(capture, route).plan(
            ctx, WorkflowRequest(order_id="invented", text=text)
        )
        return capture.request

    for v in ("candidate", "legacy"):
        r = request_for(v, "Invented routing canary")
        ordinal = len(slots) + 1
        s = RoutingSlot(
            ordinal=ordinal,
            phase="canary",
            variant=v,
            tenant_id="invented-tenant",
            case_id="invented-canary-" + v,
            run_id="routing-run-" + str(ordinal),
            business_event_id="routing-event-" + str(ordinal),
            data_snapshot="invented-canary-snapshot",
            trial_id="canary-" + v,
            request_sha256=pin(r),
        )
        slots.append(s)
        requests[ordinal] = r
    for i, c in enumerate(population.entries):
        variants = ("candidate", "legacy") if i % 2 == 0 else ("legacy", "candidate")
        for v in variants:
            r = request_for(v, c.reference.text)
            for t in ("trial-1", "trial-2", "trial-3"):
                ordinal = len(slots) + 1
                s = RoutingSlot(
                    ordinal=ordinal,
                    phase="domain",
                    variant=v,
                    tenant_id=c.order.tenant_id,
                    case_id=c.case_id,
                    case_sha256=pin(c),
                    run_id="routing-run-" + str(ordinal),
                    business_event_id="routing-event-" + str(ordinal),
                    data_snapshot=c.order.source_manifest_sha256,
                    trial_id=t,
                    request_sha256=pin(r),
                )
                slots.append(s)
                requests[ordinal] = r
    now = datetime.now(UTC)
    extension = RoutingExtension(
        authorization_ref="invented-owner-614-no-live-permission",
        historical_pins=(
            old.allowance_sha256,
            old.amendment_sha256,
            old.development_extension_sha256,
            old.paired_extension_sha256,
            old.availability_override_sha256,
            old.model_extension_sha256,
        ),
        protocol_sha256="c" * 64,
        population_sha256=pin(population),
        candidate_behavior_sha256={v: behavior_pin(c) for v, c in specs.items()},
        candidate_versions={v: c.candidate for v, c in specs.items()},
        code_revision="invented-routing-source",
        environment_lock=source["uv.lock"],
        policy_version=POLICY_VERSION,
        execution_origin=origin,
        approved_at=now,
        expires_at=now + timedelta(days=7),
        slots=tuple(slots),
    )
    newpin = append_routing_extension(old, extension)
    store = replace(old, routing_extension_sha256=newpin)
    ft = tariff()
    controls = RoutingCaptureControls(
        "invented-only-key",
        store,
        ft,
        pin(ft),
        "a" * 64,
        httpx.MockTransport(fake_sdk) if origin == "mock" else None,
    )
    specs = {
        v: c.model_copy(update={"provider_control_sha256": controls.sha256})
        for v, c in specs.items()
    }
    return old, store, ctx, extension, requests, specs, controls, population, route


def context_for(scope, ordinal):
    _, _, ctx, extension, _, specs, _, _, _ = scope
    s = extension.slots[ordinal - 1]
    now = datetime.now(UTC)
    return ctx.model_copy(
        update={
            "agent_id": "olist",
            "mode": "fresh_candidate",
            "tenant_id": s.tenant_id,
            "run_id": s.run_id,
            "business_event_id": s.business_event_id,
            "case_id": s.case_id,
            "trial_id": s.trial_id,
            "clock": now,
            "deadline": now + timedelta(seconds=300),
            "budget": Budget(
                max_model_calls=1,
                max_tokens=GEMINI_TOKEN_CEILING,
                max_cost=Decimal(0),
                cost_currency="USD",
            ),
            "versions": ctx.versions.model_copy(
                update={
                    "code_revision": extension.code_revision,
                    "candidate": specs[s.variant].candidate,
                    "environment_lock": extension.environment_lock,
                    "policy": extension.policy_version,
                    "data_snapshot": s.data_snapshot,
                }
            ),
        }
    )


def success(request, variant="candidate"):
    data = {"intent": "refund", "requested_minor": None}
    if variant == "candidate":
        data["routing_version"] = "olist-intent-routing-v2"
    return ModelResponse(
        provider=request.provider,
        model=request.model,
        output=ModelMessage(role="assistant", content=json.dumps(data)),
        usage=Usage(model_calls=1, input_tokens=3, output_tokens=5, cost=None, cost_currency=None),
    )


def pass_canaries(scope):
    _, store, _, ext, requests, *_ = scope
    for n in (1, 2):
        context = context_for(scope, n)
        response = success(requests[n], ext.slots[n - 1].variant)
        ticket = store.reserve(context, requests[n], project_sha256="a" * 64)
        store.settle(ticket, response)
        acknowledge_response(scope, n, response, context)


def acknowledge_response(scope, ordinal, response, context):
    from agent_harness.cost_accounting import derive
    from agent_harness.gateway import ModelExchange
    from agent_harness.release_contracts import AttemptReceipt
    from agent_harness.routing_budget import acknowledge_canary

    _, store, _, _, requests, _, controls, *_ = scope
    if response.accounting is None:
        response = derive(
            requests[ordinal],
            response,
            controls.tariff,
            controls.tariff_sha256,
            controls.project_sha256,
            now=datetime.now(UTC),
            allowance_sha256=store.allowance_sha256,
            capture_scope_sha256=controls.scope_sha256,
        )
    now = datetime.now(UTC)
    receipt = AttemptReceipt(
        execution_id=context.run_id,
        nonce="invented-receipt-" + str(ordinal),
        started_at=now,
        finished_at=now,
        exchange=ModelExchange(
            context=context, occurrence=1, request=requests[ordinal], response=response
        ),
    )
    acknowledge_canary(store, receipt)


def batch_for(scope, first_ordinal):
    from pathlib import Path

    from agent_harness.cases import LoadedManifest, ManifestPin
    from agent_harness.trials import TrialSchedule, TrialTask
    from olist_routing_fixtures import composition
    from olist_support.policy import POLICY_VERSION
    from olist_support.routing_h10 import manifest_for
    from olist_support.routing_provider import RoutingProviderFactory

    _, _, _, extension, _, specs, controls, population, route = scope
    slots = extension.slots[first_ordinal - 1 : first_ordinal + 2]
    case = next(c for c in population.entries if c.case_id == slots[0].case_id)
    manifest = manifest_for(RoutingPopulation(entries=(case,)))
    raw = manifest.canonical_json().encode()
    loaded = LoadedManifest(
        raw, ManifestPin(manifest_id=manifest.manifest_id, version="v1", sha256=sha256(raw))
    )
    tasks = []
    for s in slots:
        ctx = context_for(scope, s.ordinal)
        ctx = ctx.model_copy(
            update={
                "versions": ctx.versions.model_copy(
                    update={
                        "policy": POLICY_VERSION,
                        "data_snapshot": case.order.source_manifest_sha256,
                    }
                )
            }
        )
        tasks.append(
            TrialTask(
                context=ctx,
                eligible_for_autonomy=case.expected.outcome == "refunded",
                required_review=case.expected.outcome == "review_required",
            )
        )
    _, _, old, _ = composition()
    schedule = TrialSchedule.model_validate_json(
        old.model_copy(
            update={"manifest": loaded.pin, "case_ids": (case.case_id,), "tasks": tuple(tasks)}
        ).canonical_json()
    )
    factory = RoutingProviderFactory(
        specs[slots[0].variant], route, slots[0].variant, controls, Path("unused")
    )
    return loaded, schedule, factory


def sdk_child(controls, context, request, connection):
    try:
        result = controls.transport(context).generate(request)
        connection.send(result.canonical_json())
    finally:
        connection.close()
