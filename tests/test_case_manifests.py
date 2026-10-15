"""H5 acceptance: fixed populations, evaluator privacy and independent plugins."""

import hashlib
import json
import socket
from pathlib import Path

import pytest
from agent_harness.cases import CaseManifest, LoadedManifest, ManifestPin, load_manifest
from agent_harness.contracts import AgentResult, EvidenceReference, Failure
from agent_harness.evaluation import ScoreResult
from agent_harness.offline_example import (
    FakeAgent,
    FakeGateway,
    example_case,
    example_context,
)
from agent_harness.scorers import (
    ManifestCaseReport,
    ScorerCompatibility,
    ScorerRegistry,
    ScorerSpec,
)
from pydantic import ValidationError

FIXTURE = Path(__file__).parent / "fixtures" / "cases" / "invented-v1.json"
# Reviewed fixture bytes: never derive the trusted production pin from input data.
FIXTURE_DIGEST = "9140c525430e2c9aa66898d5dc95a83e75abb798659e9524accbd7dd9f9b8a3b"


def population():
    case = example_case().model_dump(mode="json")
    case["scorer_version"] = "invented-state-v1"
    case["expected"]["expected_state_changes"] = {"status": "settled"}
    case["hidden_state"] = {"private_answer": "private-hidden-outcome"}
    return {
        "manifest_id": "invented-cases",
        "version": "v1",
        "case_ids": [case["case_id"]],
        "snapshots": [
            {
                "reference": case["snapshot_ref"],
                "source_kind": case["source_kind"],
                "source_version": case["source_version"],
            }
        ],
        "entries": [
            {
                "group_id": "invented-order-1",
                "split": "development",
                "scorer_id": "invented-state",
                "case": case,
            }
        ],
    }


def load_payload(payload=None):
    # Tests intentionally author new pins for invalid structural fixtures.
    raw = json.dumps(population() if payload is None else payload).encode()
    pin = ManifestPin(
        manifest_id="invented-cases", version="v1", sha256=hashlib.sha256(raw).hexdigest()
    )
    return LoadedManifest(raw, pin)


class IndependentStateScorer:
    """Invented evidence reader: actual state is supplied separately from the agent."""

    def __init__(self, actual):
        self.actual = actual
        self.seen = []

    def score(self, case, result):
        self.seen.append((case, result))
        correct = self.actual.get(case.case_id) == case.expected.expected_state_changes
        return (
            ScoreResult(
                metric="invented_state_correct",
                scorer_version="invented-state-v1",
                eligible=case.expected.eligible_for_autonomy,
                value=float(correct),
                evidence=(EvidenceReference(reference="invented-store:1", kind="state"),),
            ),
        )


def spec(**updates):
    value = ScorerSpec(
        scorer_id="invented-state",
        version="invented-state-v1",
        compatible=(
            ScorerCompatibility(
                snapshot_ref="invented-text-v1", policy_version="fake-text-policy-v1"
            ),
        ),
    )
    return ScorerSpec.model_validate_json(value.model_copy(update=updates).canonical_json())


def registry(plugin=None):
    value = ScorerRegistry()
    value.register(spec(), plugin or IndependentStateScorer({}))
    return value


def context():
    return example_context("test-h5-source", "test-h5-lock")


def test_checked_in_population_loads_without_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("H5 attempted network")

    monkeypatch.setattr(socket, "socket", forbidden)
    pin = ManifestPin(manifest_id="invented-cases", version="v1", sha256=FIXTURE_DIGEST)
    loaded = load_manifest(FIXTURE, pin)
    bound = registry().bind(loaded)
    report = bound.run_case(context(), "fake-text-001", FakeAgent(), FakeGateway())
    assert report.manifest == pin
    assert report.report.scores[0].value == 0
    assert ManifestCaseReport.model_validate_json(report.canonical_json()) == report


@pytest.mark.parametrize(
    "change",
    [
        "duplicate_inventory",
        "duplicate_case",
        "missing_case",
        "unlisted_case",
        "missing_id",
        "empty_id",
        "blank_id",
        "missing_inventory",
        "empty_entries",
        "unknown_snapshot",
        "source_kind",
        "source_version",
        "duplicate_snapshot",
        "unused_snapshot",
        "split_leak",
        "unknown_split",
        "extra_field",
        "missing_eligibility",
        "missing_hidden_state",
        "missing_scorer_version",
        "missing_group",
        "blank_scorer",
    ],
)
def test_invalid_populations_fail_closed(change):
    payload = population()
    entry = payload["entries"][0]
    case = entry["case"]
    if change == "duplicate_inventory":
        payload["case_ids"] *= 2
    elif change == "duplicate_case":
        payload["entries"] *= 2
    elif change == "missing_case":
        payload["case_ids"].append("absent-case")
    elif change == "unlisted_case":
        payload["case_ids"] = ["different-case"]
    elif change == "missing_id":
        del case["case_id"]
    elif change in ("empty_id", "blank_id"):
        case["case_id"] = "" if change == "empty_id" else "  "
        payload["case_ids"] = [case["case_id"]]
    elif change == "missing_inventory":
        del payload["case_ids"]
    elif change == "empty_entries":
        payload["entries"] = []
    elif change == "unknown_snapshot":
        case["snapshot_ref"] = "absent-snapshot"
    elif change in ("source_kind", "source_version"):
        case[change] = "original" if change == "source_kind" else "changed-version"
    elif change == "duplicate_snapshot":
        payload["snapshots"] *= 2
    elif change == "unused_snapshot":
        payload["snapshots"].append({**payload["snapshots"][0], "reference": "unused"})
    elif change == "split_leak":
        other = json.loads(json.dumps(entry))
        other["case"]["case_id"] = "other-case"
        other["split"] = "holdout"
        payload["entries"].append(other)
        payload["case_ids"].append("other-case")
    elif change == "unknown_split":
        entry["split"] = "random"
    elif change == "extra_field":
        payload["python_import"] = "arbitrary.module"
    elif change == "missing_eligibility":
        del case["expected"]["eligible_for_autonomy"]
    elif change in ("missing_hidden_state", "missing_scorer_version"):
        del case[change.removeprefix("missing_")]
    elif change == "missing_group":
        del entry["group_id"]
    elif change == "blank_scorer":
        entry["scorer_id"] = "  "
    with pytest.raises(ValueError):
        load_payload(payload)


def test_group_family_can_share_one_split_but_never_cross_snapshots_into_holdout():
    payload = population()
    other = json.loads(json.dumps(payload["entries"][0]))
    other["case"]["case_id"] = "paraphrase-2"
    payload["entries"].append(other)
    payload["case_ids"].append("paraphrase-2")
    assert len(load_payload(payload).manifest.entries) == 2
    other["case"]["snapshot_ref"] = "other-snapshot"
    payload["snapshots"].append({**payload["snapshots"][0], "reference": "other-snapshot"})
    other["split"] = "holdout"
    with pytest.raises(ValueError, match="group crosses"):
        load_payload(payload)


@pytest.mark.parametrize(
    "field,value", [("manifest_id", "other"), ("version", "v2"), ("sha256", "0" * 64)]
)
def test_reviewed_pin_is_required(field, value):
    loaded = load_payload()
    pin = loaded.pin.model_copy(update={field: value})
    with pytest.raises(ValueError, match="pin"):
        LoadedManifest(json.dumps(population()).encode(), pin)


def test_hash_and_parse_use_same_read_buffer(tmp_path, monkeypatch):
    raw = json.dumps(population()).encode()
    reads = []

    def read(path):
        reads.append(path)
        return raw if len(reads) == 1 else b"{}"

    monkeypatch.setattr(Path, "read_bytes", read)
    loaded = load_manifest(tmp_path / "invented.json", load_payload().pin)
    assert len(reads) == 1 and loaded.entry("fake-text-001").case.source_kind == "synthetic"


def test_duplicate_json_keys_are_not_silently_overwritten():
    raw = (
        json.dumps(population())
        .replace('"version": "v1"', '"version": "wrong", "version": "v1"')
        .encode()
    )
    pin = load_payload().pin.model_copy(update={"sha256": hashlib.sha256(raw).hexdigest()})
    with pytest.raises(ValueError, match="duplicate JSON key"):
        LoadedManifest(raw, pin)


def test_missing_file_and_truncated_json_fail(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_manifest(tmp_path / "missing.json", load_payload().pin)
    raw = b'{"manifest_id":'
    pin = load_payload().pin.model_copy(update={"sha256": hashlib.sha256(raw).hexdigest()})
    with pytest.raises(ValueError):
        LoadedManifest(raw, pin)


def test_loaded_evidence_is_not_mutated_through_returned_nested_values():
    loaded = load_payload()
    entry = loaded.entry("fake-text-001")
    entry.case.hidden_state["private_answer"] = "mutated"
    entry.case.expected.expected_state_changes["status"] = "mutated"
    loaded.manifest.entries[0].case.hidden_state.clear()
    assert (
        loaded.entry("fake-text-001").case.hidden_state["private_answer"]
        == "private-hidden-outcome"
    )
    assert loaded.entry("fake-text-001").case.expected.expected_state_changes == {
        "status": "settled"
    }


@pytest.mark.parametrize("change", ["missing", "version", "snapshot", "policy"])
def test_all_scorer_bindings_fail_before_any_dispatch(change):
    payload = population()
    other = json.loads(json.dumps(payload["entries"][0]))
    other["case"]["case_id"] = "second-case"
    if change == "missing":
        other["scorer_id"] = "unregistered"
    elif change == "version":
        other["case"]["scorer_version"] = "unregistered-v2"
    elif change == "snapshot":
        other["case"]["snapshot_ref"] = "unsupported"
        payload["snapshots"].append({**payload["snapshots"][0], "reference": "unsupported"})
    else:
        other["case"]["policy_version"] = "unsupported-policy"
    payload["entries"].append(other)
    payload["case_ids"].append("second-case")
    with pytest.raises(ValueError, match="scorer"):
        registry().bind(load_payload(payload))


def test_registration_is_unique_and_checks_plugin_and_compatibility():
    value = registry()
    with pytest.raises(ValueError, match="already registered"):
        value.register(spec(), IndependentStateScorer({}))
    with pytest.raises(TypeError, match="implement score"):
        ScorerRegistry().register(spec(), object())
    with pytest.raises(ValidationError, match="duplicate scorer compatibility"):
        spec(compatible=spec().compatible * 2)


@pytest.mark.parametrize(
    "actual,expected", [({"status": "settled"}, 1), ({"status": "pending"}, 0), (None, 0)]
)
def test_same_success_claim_scores_against_independent_actual_state(actual, expected):
    plugin = IndependentStateScorer({"fake-text-001": actual})

    class ClaimingAgent(FakeAgent):
        def run(self, context, input, gateway):
            return (
                super()
                .run(context, input, gateway)
                .model_copy(update={"state_change_refs": ("invented-forged-success",)})
            )

    report = (
        registry(plugin)
        .bind(load_payload())
        .run_case(context(), "fake-text-001", ClaimingAgent(), FakeGateway())
    )
    assert report.report.result.outcome == "completed"
    assert report.report.scores[0].value == expected
    assert report.report.scores[0].evidence[0].kind == "state"


def test_private_labels_group_split_and_eligibility_never_enter_agent_or_gateway():
    payload = population()
    entry = payload["entries"][0]
    entry["group_id"] = "private-group-marker"
    entry["split"] = "holdout"
    entry["case"]["expected"]["output"] = "private-expected-answer"
    entry["case"]["expected"]["eligible_for_autonomy"] = False
    captured = []

    class CapturingAgent(FakeAgent):
        def run(self, context, input, gateway):
            captured.append(context.canonical_json() + input.canonical_json())
            return super().run(context, input, gateway)

    gateway = FakeGateway()
    plugin = IndependentStateScorer({})
    report = (
        registry(plugin)
        .bind(load_payload(payload))
        .run_case(context(), "fake-text-001", CapturingAgent(), gateway)
    )
    wire = captured[0] + gateway.requests[0].canonical_json()
    for private in (
        "private-group-marker",
        "holdout",
        "private-expected-answer",
        "private-hidden-outcome",
        "eligible_for_autonomy",
        "hidden_state",
        "expected",
    ):
        assert private not in wire
    assert plugin.seen[0][0].expected.output == "private-expected-answer"
    assert report.report.scores[0].eligible is False
    assert "private-hidden-outcome" not in report.canonical_json()


@pytest.mark.parametrize("change", ["case", "snapshot", "policy", "absent"])
def test_context_mismatch_is_rejected_before_agent(change):
    ctx = context()
    case_id = "fake-text-001"
    if change == "case":
        ctx = ctx.model_copy(update={"case_id": "wrong"})
    elif change in ("snapshot", "policy"):
        field = "data_snapshot" if change == "snapshot" else "policy"
        ctx = ctx.model_copy(update={"versions": ctx.versions.model_copy(update={field: "wrong"})})
    else:
        case_id = "absent"
    gateway = FakeGateway()
    with pytest.raises(ValueError):
        registry().bind(load_payload()).run_case(ctx, case_id, FakeAgent(), gateway)
    assert not gateway.requests


@pytest.mark.parametrize(
    "mode", ["empty", "duplicate", "wrong_version", "exception", "typed_error"]
)
def test_invalid_plugin_output_never_becomes_a_passing_score(mode):
    class BrokenScorer(IndependentStateScorer):
        def score(self, case, result):
            score = super().score(case, result)[0]
            if mode == "exception":
                raise RuntimeError("invented reader unavailable")
            if mode == "empty":
                return ()
            if mode == "duplicate":
                return (score, score)
            if mode == "wrong_version":
                return (score.model_copy(update={"scorer_version": "wrong"}),)
            return (
                ScoreResult(
                    metric="invented_state_correct",
                    scorer_version="invented-state-v1",
                    eligible=True,
                    failure=Failure(
                        stage="scorer",
                        code="scorer_error",
                        message="invented reader unavailable",
                        retryable=False,
                    ),
                ),
            )

    bound = registry(BrokenScorer({})).bind(load_payload())
    if mode == "typed_error":
        score = bound.run_case(
            context(), "fake-text-001", FakeAgent(), FakeGateway()
        ).report.scores[0]
        assert score.failure is not None and score.value is None and score.category is None
    else:
        with pytest.raises((ValueError, RuntimeError)):
            bound.run_case(context(), "fake-text-001", FakeAgent(), FakeGateway())


def test_plugin_mutation_cannot_change_retained_manifest_or_agent_result():
    class MutatingScorer(IndependentStateScorer):
        def score(self, case, result):
            case.hidden_state.clear()
            case.expected.expected_state_changes.clear()
            object.__setattr__(result, "output", "mutated")
            return super().score(case, result)

    loaded = load_payload()
    bound = registry(MutatingScorer({})).bind(loaded)
    report = bound.run_case(context(), "fake-text-001", FakeAgent(), FakeGateway())
    assert report.report.result.output == "HELLO, SHARED CONTRACTS"
    assert loaded.entry("fake-text-001").case.hidden_state


def test_wrong_agent_result_identity_is_not_scored():
    class WrongAgent(FakeAgent):
        def run(self, context, input, gateway):
            result = super().run(context, input, gateway)
            return AgentResult.model_validate_json(
                result.model_copy(update={"trial_id": "wrong-trial"}).canonical_json()
            )

    plugin = IndependentStateScorer({})
    with pytest.raises(ValueError, match="result identity"):
        registry(plugin).bind(load_payload()).run_case(
            context(), "fake-text-001", WrongAgent(), FakeGateway()
        )
    assert not plugin.seen


def test_explicit_versions_coexist_without_replacing_bound_plugin():
    value = registry(IndependentStateScorer({"fake-text-001": {"status": "settled"}}))
    bound = value.bind(load_payload())
    value.register(spec(version="invented-state-v2"), IndependentStateScorer({}))
    assert (
        bound.run_case(context(), "fake-text-001", FakeAgent(), FakeGateway())
        .report.scores[0]
        .value
        == 1
    )


def test_manifest_roundtrip_does_not_accept_labels_as_public_input():
    manifest = load_payload().manifest
    assert CaseManifest.model_validate_json(manifest.canonical_json()) == manifest
    from agent_harness.contracts import AgentInput

    with pytest.raises(ValidationError):
        AgentInput.model_validate_json(manifest.entries[0].canonical_json())
