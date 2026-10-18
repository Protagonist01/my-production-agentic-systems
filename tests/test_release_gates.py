"""Offline gate logic against invented reports; no domain baseline is approved."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from agent_harness.release_contracts import pin
from agent_harness.release_evidence import compare_evidence, release_candidate
from release_fixtures import logical_pair


@pytest.fixture(scope="module")
def pair(tmp_path_factory):
    return logical_pair(tmp_path_factory.mktemp("invented-release-logic"))


def decide(pair, **updates):
    loaded, old, new, policy, approval = pair
    values = dict(
        baseline=old,
        candidate=new,
        loaded=loaded,
        policy=policy,
        approval=approval,
        approval_sha256=pin(approval),
        policy_sha256=pin(policy),
        expected_candidate_sha256=pin(new.manifest.candidate),
        now=datetime.now(UTC),
    )
    values.update(updates)
    return release_candidate(**values)


def test_positive_logic_requires_all_independent_inputs(pair):
    result = decide(pair)
    assert result.allowed and result.blockers == () and result.regressed_cases == ()
    assert result.approval_sha256 == pin(pair[4])


@pytest.mark.parametrize("which", ["candidate", "baseline"])
def test_mock_dispatch_never_qualifies_for_release(pair, which):
    value = pair[2] if which == "candidate" else pair[1]
    value = replace(value, manifest=value.manifest.model_copy(update={"origin": "mock"}))
    changes = {which: value}
    if which == "baseline":
        approval = pair[4].model_copy(update={"baseline_sha256": pin(value.manifest)})
        changes.update(approval=approval, approval_sha256=pin(approval))
    result = decide(pair, **changes)
    assert not result.allowed and which + "_mock_evidence" in result.blockers


def test_candidate_cannot_approve_itself_as_baseline(pair):
    loaded, _, new, policy, approval = pair
    approval = approval.model_copy(
        update={"baseline_sha256": pin(new.manifest), "approved_at": new.manifest.finished_at}
    )
    result = decide(pair, baseline=new, approval=approval, approval_sha256=pin(approval))
    assert not result.allowed and "candidate_reuses_baseline_execution" in result.blockers


@pytest.mark.parametrize("which", ["approval", "policy", "candidate", "baseline_binding"])
def test_separate_pins_are_required_and_never_created_by_gate(pair, which):
    changes = (
        {"approval_sha256": "0" * 64}
        if which == "approval"
        else (
            {"policy_sha256": "0" * 64}
            if which == "policy"
            else {"expected_candidate_sha256": "0" * 64}
            if which == "candidate"
            else {"baseline": pair[2]}
        )
    )
    with pytest.raises(ValueError):
        decide(pair, **changes)


@pytest.mark.parametrize(
    "which",
    [
        "approval_expired",
        "approval_future",
        "evidence_old",
        "evidence_future",
        "preapproved",
        "candidate_before_approval",
    ],
)
def test_expired_future_and_wrong_order_evidence_blocks_release(pair, which):
    _, old, new, policy, approval = pair
    now = datetime.now(UTC)
    changes = {}
    if which == "approval_expired":
        changes["now"] = approval.expires_at
    elif which == "approval_future":
        changes["now"] = approval.approved_at - timedelta(seconds=1)
    elif which == "evidence_old":
        changes["now"] = old.manifest.started_at + timedelta(seconds=policy.max_age_seconds + 1)
    elif which == "evidence_future":
        changes["candidate"] = replace(
            new,
            manifest=new.manifest.model_copy(
                update={
                    "started_at": now + timedelta(seconds=1),
                    "finished_at": now + timedelta(seconds=2),
                }
            ),
        )
    else:
        approval = approval.model_copy(
            update={
                "approved_at": (
                    old.manifest.started_at - timedelta(seconds=1)
                    if which == "preapproved"
                    else new.manifest.finished_at + timedelta(seconds=1)
                )
            }
        )
        changes.update(approval=approval, approval_sha256=pin(approval))
    result = decide(pair, **changes)
    assert not result.allowed
    assert any("expired_or_future" in s or "before" in s for s in result.blockers)


@pytest.mark.parametrize("which", ["scorer_sha256", "policy_sha256", "environment_sha256"])
def test_changed_evaluator_policy_or_environment_needs_reviewed_baseline(pair, which):
    new = pair[2]
    new = replace(
        new,
        manifest=new.manifest.model_copy(
            update={"candidate": new.manifest.candidate.model_copy(update={which: "1" * 64})}
        ),
    )
    with pytest.raises(ValueError, match="incompatible"):
        decide(pair, candidate=new, expected_candidate_sha256=pin(new.manifest.candidate))


def change_result(evidence, kind):
    row = evidence.batch.rows[0]
    report = row.report.report
    if kind == "missing":
        rows = evidence.batch.rows[1:]
    else:
        metric = "invented_safe" if kind == "unsafe" else "invented_correct"
        scores = tuple(
            s.model_copy(update={"value": 0.0}) if s.metric == metric else s for s in report.scores
        )
        report = report.model_copy(update={"scores": scores})
        row = row.model_copy(update={"report": row.report.model_copy(update={"report": report})})
        rows = (row, *evidence.batch.rows[1:])
    return replace(evidence, batch=evidence.batch.model_copy(update={"rows": rows}))


@pytest.mark.parametrize("kind", ["missing", "unsafe", "fail"])
def test_missing_critical_or_newly_failing_required_case_blocks_release(pair, kind):
    new = change_result(pair[2], kind)
    result = decide(pair, candidate=new)
    assert not result.allowed
    assert "required_case_failed" in result.blockers
    assert "previously_passing_case_regressed" in result.blockers
    if kind != "fail":
        assert "candidate_incomplete_or_unsafe" in result.blockers


def test_aggregate_floor_and_review_policy_cannot_hide_case_regression(pair):
    policy = pair[3].model_copy(update={"min_autonomous_completion": 0.0, "max_review_rate": 1.0})
    approval = pair[4].model_copy(update={"release_policy_sha256": pin(policy)})
    result = decide(
        pair,
        candidate=change_result(pair[2], "fail"),
        policy=policy,
        approval=approval,
        approval_sha256=pin(approval),
        policy_sha256=pin(policy),
    )
    assert not result.allowed and result.regressed_cases == pair[0].manifest.case_ids


def test_comparison_does_not_issue_or_update_approval(pair):
    before = pair[4].canonical_json()
    assert compare_evidence(pair[1], pair[2], pair[0], pair[3]) == ()
    assert pair[4].canonical_json() == before
