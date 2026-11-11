"""Revalidate accepted conditional intent evidence; measure no unannotated money field."""

import argparse
import hashlib
import json
import os
import socket
import sys
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent_harness.contracts import RunContext
from agent_harness.offline_example import example_context
from agent_harness.release_contracts import pin
from olist_support.intent_reference import IntentBundle, IntentMethodAcceptance, prepare
from olist_support.policy import POLICY_VERSION
from olist_support.policy_cases import external
from olist_support.reference_audit import ExposureIndex
from olist_support.utterance_reference import UtteranceAudit, verify
from olist_support.workflow import IntentDecision, WorkflowRequest

from olist_routing_baseline import VERSION, ConservativePlanner

ACCEPTANCE = "1590f18efe6a4346b91115aac32eafd208670fea01c2b0245f0adc069e7b852e"
METHOD = "c8554eaafab13938309510cc270a6ce5f33a146e9b32ab712de8ae621283d17d"
CSV = "6f81102b0100b97b8468eb04368033a23206bf1fde9d53500d5806ec1001a434"
AUDIT = "830116abc05c8a3affddadab06f7fd5dd5b8b7f331b7c7eb73804521ff645d5b"
TRIALS = ("native-development-1", "native-development-2", "native-development-3")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_verified(cache):
    accepted = cache / "accepted-intent-method-development-2026-11-04-v1"
    files = json.loads((accepted / "pins.json").read_bytes())
    for name, value in files.items():
        assert Path(name).name == name and digest(accepted / name) == value
    owner = IntentMethodAcceptance.model_validate_json(
        (accepted / "owner-acceptance.json").read_bytes()
    )
    assert pin(owner) == ACCEPTANCE and owner.proposal_sha256 == METHOD
    assert digest(cache / "reference-method-decision-2026-11-03-v2/method.json") == METHOD
    assert owner.source_csv_sha256 == CSV and owner.scope == "development_calibration_intent_only"
    audit = UtteranceAudit.model_validate_json(
        (cache / "utterance-reference-audit-2026-11-03-v2/audit.json").read_bytes()
    )
    assert pin(audit) == AUDIT
    source = cache / "reference-method-proposal-2026-11-03-v1"
    exposure = ExposureIndex.model_validate_json((source / "adapter-exposure.json").read_bytes())
    verify(
        audit,
        (
            source / "Bitext_Sample_Customer_Support_Training_Dataset_27K_responses-v11.csv"
        ).read_bytes(),
        CSV,
        exposure,
    )
    bundle = IntentBundle.model_validate_json(
        (accepted / "intent-reference-bundle.json").read_bytes()
    )
    assert (
        prepare(
            audit,
            owner,
            tuple(c.frame.source_ordinal for c in bundle.cases),
            expected_audit_sha256=AUDIT,
            expected_acceptance_sha256=ACCEPTANCE,
        )
        == bundle
    )
    inputs = json.loads((accepted / "candidate-inputs.json").read_bytes())
    assert inputs == [
        {"case_id": c.case_id, "input": c.input.model_dump(mode="json")} for c in bundle.cases
    ]
    assert len(bundle.cases) == 12 and all(
        not c.amount_reference_established and not c.semantic_gold_validated for c in bundle.cases
    )
    return bundle, inputs


def sources():
    root = Path(__file__).resolve().parents[2]
    names = (
        "olist_routing_baseline.py",
        "uv.lock",
        "docs/evaluation/olist_native_intent_readiness.py",
        "projects/olist-support/src/olist_support/intent_reference.py",
        "projects/olist-support/src/olist_support/utterance_reference.py",
        "projects/olist-support/src/olist_support/reference_audit.py",
        "projects/olist-support/src/olist_support/routing_contracts.py",
        "harness/src/agent_harness/contracts.py",
        "harness/src/agent_harness/baseline_recording.py",
    )
    return {name: digest(root / name) for name in names}


def write(output, name, value):
    raw = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()
    fd = os.open(output / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return digest(output / name)


def summary(bundle, records):
    cases = {c.case_id: c for c in bundle.cases}
    seen, confusions = set(), Counter()
    matched = 0
    for record in records:
        ctx = RunContext.model_validate_json(json.dumps(record["context"]))
        req = WorkflowRequest.model_validate_json(json.dumps(record["request"]))
        result = IntentDecision.model_validate_json(json.dumps(record["decision"]))
        key = ctx.case_id, ctx.trial_id
        assert key not in seen and ctx.case_id in cases and ctx.trial_id in TRIALS
        seen.add(key)
        case = cases[ctx.case_id]
        assert req.text == case.input.request and result.execution_run_id == ctx.run_id
        assert ctx.mode == "offline_fake" and ctx.agent_id == ctx.versions.candidate == VERSION
        assert (
            ctx.versions.data_snapshot == pin(bundle)
            and ctx.budget.max_model_calls == ctx.budget.max_tokens == 1
        )
        assert result.failure_code is None and result.usage.model_calls == result.usage.cost == 0
        assert result.usage.cost_currency == "USD"
        # Intentionally no comparison of requested_minor: the source supplies no such reference.
        confusions[case.expected_intent + ":" + result.plan.intent] += 1
        matched += case.expected_intent == result.plan.intent
    assert seen == {(c.case_id, t) for c in bundle.cases for t in TRIALS}
    return {
        "reference_basis": "accepted_conditional_native_intent_development",
        "cases": len(cases),
        "rows": len(records),
        "intent_agreements": matched,
        "scheduled_agreement": matched / len(records),
        "confusions": dict(sorted(confusions.items())),
        "native_class_counts": dict(Counter(c.expected_intent for c in bundle.cases)),
        "candidate_model_rows": 0,
        "requested_amount_scored": False,
        "semantic_gold_validated": False,
        "whole_service_evaluated": False,
        "representative_population": False,
        "qualification": False,
        "provider_calls": 0,
        "release_allowed": False,
    }


def capture(cache, output):
    bundle, inputs = load_verified(cache)
    pins = sources()
    output.mkdir(mode=0o700)
    write(
        output,
        "before.json",
        {
            "acceptance_sha256": ACCEPTANCE,
            "method_sha256": METHOD,
            "audit_sha256": AUDIT,
            "bundle_sha256": pin(bundle),
            "source_csv_sha256": CSV,
            "source_pins": pins,
        },
    )
    network = {"attempts": 0}
    records = []

    def denied(*args, **kwargs):
        network["attempts"] += 1
        raise RuntimeError("network denied in native-intent development")

    old = (
        socket.socket.connect,
        socket.socket.connect_ex,
        socket.create_connection,
        socket.getaddrinfo,
    )
    socket.socket.connect = socket.socket.connect_ex = socket.create_connection = (
        socket.getaddrinfo
    ) = denied
    try:
        planner = ConservativePlanner()
        for item in inputs:
            req = WorkflowRequest(
                order_id="invented-unused-no-state", text=item["input"]["request"]
            )
            for trial in TRIALS:
                now = datetime.now(UTC)
                ctx = example_context("selected-source-pins", pins["uv.lock"])
                ctx = RunContext.model_validate_json(
                    ctx.model_copy(
                        update={
                            "run_id": f"native-{item['case_id']}-{trial}",
                            "case_id": item["case_id"],
                            "trial_id": trial,
                            "agent_id": VERSION,
                            "clock": now,
                            "deadline": now + timedelta(seconds=30),
                            "versions": ctx.versions.model_copy(
                                update={
                                    "candidate": VERSION,
                                    "policy": POLICY_VERSION,
                                    "data_snapshot": pin(bundle),
                                }
                            ),
                            "budget": ctx.budget.model_copy(
                                update={"max_model_calls": 1, "max_tokens": 1}
                            ),
                        }
                    ).canonical_json()
                )
                decision = planner.plan(ctx, req)
                records.append(
                    {
                        "context": ctx.model_dump(mode="json"),
                        "request": req.model_dump(mode="json"),
                        "decision": decision.model_dump(mode="json"),
                    }
                )
        assert network["attempts"] == 0
    finally:
        (
            socket.socket.connect,
            socket.socket.connect_ex,
            socket.create_connection,
            socket.getaddrinfo,
        ) = old
        write(output, "records.json", records)
        write(output, "network.json", network)
    assert sources() == pins
    report = summary(bundle, records)
    write(output, "report.json", report)
    files = {p.name: digest(p) for p in output.iterdir() if p.is_file()}
    write(
        output,
        "manifest.json",
        {"complete": True, "files": files, "provider_calls": 0, "release_allowed": False},
    )
    return {"manifest_sha256": digest(output / "manifest.json"), **report}


def readback(cache, output, expected):
    assert digest(output / "manifest.json") == expected
    manifest = json.loads((output / "manifest.json").read_bytes())
    assert (
        manifest["complete"] and manifest["provider_calls"] == 0 and not manifest["release_allowed"]
    )
    assert set(manifest["files"]) == {"before.json", "records.json", "network.json", "report.json"}
    for name, value in manifest["files"].items():
        assert digest(output / name) == value
    bundle, _ = load_verified(cache)
    before = json.loads((output / "before.json").read_bytes())
    assert before == {
        "acceptance_sha256": ACCEPTANCE,
        "method_sha256": METHOD,
        "audit_sha256": AUDIT,
        "bundle_sha256": pin(bundle),
        "source_csv_sha256": CSV,
        "source_pins": sources(),
    }
    assert json.loads((output / "network.json").read_bytes()) == {"attempts": 0}
    report = summary(bundle, json.loads((output / "records.json").read_bytes()))
    assert report == json.loads((output / "report.json").read_bytes())
    return {"manifest_sha256": expected, **report}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--verify-manifest")
    args = parser.parse_args()
    if not __debug__:
        parser.error("normal Python assertions required")
    cache, output = external(args.cache), external(args.output)
    result = (
        readback(cache, output, args.verify_manifest)
        if args.verify_manifest
        else capture(cache, output)
    )
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
