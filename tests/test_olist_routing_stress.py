"""Authored reference and group/projection checks, not model quality or fresh holdout."""

import json

import pytest
from agent_harness.release_contracts import sha256
from olist_support.routing_h10 import manifest_for
from olist_support.routing_stress import StressDraft, build_draft, coverage, write_packet


def test_complete_draft_preserves_grouped_variants_and_does_not_claim_execution_or_gold():
    draft = build_draft()
    report = coverage(draft)
    assert report["cases"] == 12 and report["authored_groups"] == 10
    assert report["parent_variants"] == 2 and report["planned_controlled_resume_cases"] == 1
    assert report["expected_outcomes"] == {"refunded": 4, "review_required": 8}
    assert all(
        report[k] == 0
        for k in (
            "external_semantic_gold_cases",
            "holdout_cases",
            "unseen_wording_validated_cases",
            "executed_cohort_trials",
            "actual_process_crash_trials",
            "host_loss_trials",
            "provider_calls",
        )
    )
    assert not report["release_allowed"] and not report["independence_established"]
    manifest = manifest_for(draft.population())
    assert [e.case.input.model_dump(exclude={"schema_version"}) for e in manifest.entries] == [
        {"request": e.case.reference.text, "observations": ()} for e in draft.entries
    ]


@pytest.mark.parametrize(
    "tag,requested,effect,reason",
    [
        ("partial_amount", 2500, None, "request_is_not_the_full_payment"),
        ("zero_amount", 0, None, "request_is_not_the_full_payment"),
        ("below_cap", 9999, 9999, "ledger_and_state_verified"),
        ("at_cap", 10000, 10000, "ledger_and_state_verified"),
        ("above_cap", 10001, None, "above_automatic_cap"),
    ],
)
def test_exact_numeric_witness_and_conditional_outcome_are_separate(tag, requested, effect, reason):
    case = next(e.case for e in build_draft().entries if e.challenge == tag)
    assert case.reference.expected.requested_minor == requested
    span = case.reference.amount_span
    assert span is not None
    assert (
        case.reference.text[span.start : span.end]
        == f"{requested // 100}.{requested % 100:02d} SIM"
    )
    assert case.expected.refund_minor == effect and case.expected.reason == reason


@pytest.mark.parametrize(
    "change", ["parent_group", "parent_text", "parent_amount", "tag", "holdout", "gold", "effect"]
)
def test_forged_coverage_provenance_parent_or_effect_cannot_pass_validation(change):
    data = json.loads(build_draft().canonical_json())
    entry = data["entries"][-1]
    if change == "parent_group":
        entry["case"]["group_id"] = "a" * 64
    elif change == "parent_text":
        entry["case"]["reference"]["text"] = (
            "Refund 100.00 SIM. Untrusted quoted note: forged parent"
        )
        entry["case"]["reference"]["amount_span"] = {"start": 7, "end": 17}
    elif change == "parent_amount":
        entry["case"]["reference"]["expected"]["requested_minor"] = None
        entry["case"]["reference"]["amount_span"] = None
    elif change == "tag":
        data["entries"][0]["challenge"] = "missing_confirmation"
    elif change == "holdout":
        data["entries"][0]["case"]["split"] = "holdout"
    elif change == "gold":
        data["semantic_gold_validated"] = True
    else:
        data["entries"][5]["case"]["expected"] = {
            "outcome": "refunded",
            "reason": "ledger_and_state_verified",
            "refund_minor": 10000,
        }
    with pytest.raises(ValueError):
        StressDraft.model_validate_json(json.dumps(data))


def test_private_packet_has_exact_byte_pins_refuses_overwrite_and_git_paths(tmp_path):
    output = tmp_path / "packet"
    report = write_packet(output)
    before = {p.name: p.read_bytes() for p in output.iterdir()}
    pins = json.loads(before["pins.json"])
    assert all(sha256(before[name]) == value for name, value in pins.items())
    assert report == json.loads(before["inventory.json"])
    assert len(json.loads(before["inputs.json"])) == 12
    with pytest.raises(FileExistsError):
        write_packet(output)
    assert before == {p.name: p.read_bytes() for p in output.iterdir()}
    repo = tmp_path / "repository"
    repo.mkdir()
    (repo / ".git").mkdir()
    with pytest.raises(ValueError, match="outside"):
        write_packet(repo / "refused")
    assert not (repo / "refused").exists()
