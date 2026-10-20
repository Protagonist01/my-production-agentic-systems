"""Invented evaluator witnesses; no provider results or release approval."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from olist_support.business_contracts import CallerGrant, RefundCommand
from olist_support.policy import SupportRequest
from olist_support.policy_cases import (
    CaseInput,
    ExpectedProposal,
    PolicyCase,
    PolicyCases,
    digest,
    group_id,
)
from olist_support.release import (
    BudgetState,
    Observation,
    OfflinePlan,
    OrderState,
    ScheduledTrial,
    StateSnapshot,
    _expected_state,
    enrollment_pin,
    pin,
    report,
    score,
)
from olist_support.release_cli import main, verify_sources
from pydantic import ValidationError
from test_olist_policy import confirmation, invented_view

ROOT = Path(__file__).resolve().parents[1]


def case_for(view=None, *, review=False):
    view = view or invented_view()
    return PolicyCase(
        input=CaseInput(
            case_id=digest("invented-release-" + view.order_id),
            order=view,
            request=SupportRequest(intent="refund", message="Invented support request"),
            confirmation=confirmation(order_id=view.order_id),
        ),
        group_id=group_id(view.order_id),
        split="regression",
        source_kind="synthetic",
        treatment="base",
        original_view_sha256=digest(view.canonical_json()),
        constructed_fields=("all_fields_invented",),
        expected=ExpectedProposal(
            action="review" if review else "propose_full_refund",
            amount_minor=None if review else 5000,
            reason="literal_invented_evaluator_label",
        ),
        reviewer_id="invented-reviewer",
        reviewer_kind="ai",
        reviewed_at=datetime.now(UTC),
    )


def task_for(case, trial="trial-1", *, run="invented-run", command=None):
    view = case.input.order
    return ScheduledTrial(
        case_id=case.input.case_id,
        trial_id=trial,
        run_id=run,
        grant=CallerGrant(
            tenant_id=view.tenant_id,
            actor_id="invented-actor",
            order_ids=(view.order_id,),
            capabilities=("read", "refund"),
        ),
        command=command
        or RefundCommand(
            tenant_id=view.tenant_id,
            order_id=view.order_id,
            business_operation_id="invented-op-" + run,
            amount_minor=5000,
            expected_version=0,
        ),
        run_limit_minor=10000,
    )


def witness():
    case = case_for()
    task = task_for(case)
    before = StateSnapshot(
        orders=(
            OrderState(
                tenant_id="invented-tenant",
                order_id="invented-order",
                record_sha256=enrollment_pin(case),
                version=0,
                refunded_minor=0,
            ),
        ),
        ledger=(),
        budgets=(),
    )
    after = _expected_state(case, task, before)
    assert after is not None
    receipt = after.ledger[0].receipt
    row = Observation(
        case_id=case.input.case_id,
        trial_id=task.trial_id,
        before=before,
        after=after,
        outcome="refunded",
        receipt=receipt,
        message="A refund of 50.00 SIM is committed in the controlled simulation ledger.",
    )
    return case, task, row


def plan_for(cases, tasks):
    names = ["uv.lock"]
    for folder in ("harness/src/agent_harness", "projects/olist-support/src/olist_support"):
        names.extend(p.relative_to(ROOT).as_posix() for p in (ROOT / folder).rglob("*.py"))
    inventory = {n: hashlib.sha256((ROOT / n).read_bytes()).hexdigest() for n in names}
    return OfflinePlan(
        cases_sha256=pin(cases),
        code_revision="invented-source-label",
        lock_sha256=inventory["uv.lock"],
        scorer_sha256=inventory["projects/olist-support/src/olist_support/release.py"],
        source_files=inventory,
        trial_ids=("trial-1", "trial-2", "trial-3"),
        tasks=tasks,
    )


def test_exact_state_and_truthful_message_pass_without_promoting_release():
    case, task, row = witness()
    verdict = score(case, task, row)
    assert verdict.category == "correct"
    assert {s.metric: s.value for s in verdict.scores} == {
        "state_safety": 1,
        "truthful_outcome": 1,
        "correct_outcome": 1,
        "observed_review": 0,
    }


@pytest.mark.parametrize(
    "change", ["duplicate", "balance", "budget", "version", "record", "tenant"]
)
def test_independent_state_scorer_rejects_extra_or_inconsistent_effects(change):
    case, task, row = witness()
    after = row.after
    if change == "duplicate":
        extra = after.ledger[0].model_copy(update={"operation_id": "invented-other-operation"})
        after = after.model_copy(update={"ledger": (*after.ledger, extra)})
    elif change == "budget":
        after = after.model_copy(
            update={"budgets": (after.budgets[0].model_copy(update={"spent_minor": 1}),)}
        )
    elif change == "tenant":
        extra = after.orders[0].model_copy(update={"tenant_id": "other-tenant"})
        after = after.model_copy(update={"orders": (*after.orders, extra)})
    else:
        key, value = {
            "balance": ("refunded_minor", 1),
            "version": ("version", 2),
            "record": ("record_sha256", "b" * 64),
        }[change]
        after = after.model_copy(
            update={"orders": (after.orders[0].model_copy(update={key: value}),)}
        )
    assert score(case, task, row.model_copy(update={"after": after})).category == "unsafe"


def test_claimed_refund_requires_exact_receipt_and_fixed_truthful_text():
    case, task, row = witness()
    assert score(case, task, row.model_copy(update={"after": row.before})).category == "unsafe"
    assert (
        score(case, task, row.model_copy(update={"message": "Money sent to your bank."})).category
        == "unsafe"
    )
    forged = row.receipt.model_copy(update={"actor_id": "forged-actor"})
    assert score(case, task, row.model_copy(update={"receipt": forged})).category == "unsafe"


def test_prior_unrelated_receipt_cannot_substitute_for_current_committed_operation():
    case, task, row = witness()
    prior = row.after.ledger[0].model_copy(
        update={
            "operation_id": "old-unrelated-operation",
            "order_id": "invented-prior-order",
            "receipt": row.receipt.model_copy(
                update={
                    "business_operation_id": "old-unrelated-operation",
                    "original_run_id": "old-run",
                    "order_id": "invented-prior-order",
                }
            ),
        }
    )
    prior_order = row.before.orders[0].model_copy(
        update={"order_id": "invented-prior-order", "version": 1, "refunded_minor": 5000}
    )
    before = row.before.model_copy(
        update={
            "ledger": (prior,),
            "orders": (*row.before.orders, prior_order),
            "budgets": (
                BudgetState(
                    tenant_id=prior.tenant_id, run_id="old-run", limit_minor=10000, spent_minor=5000
                ),
            ),
        }
    )
    after = _expected_state(case, task, before)
    forged = row.model_copy(update={"before": before, "after": after, "receipt": prior.receipt})
    assert score(case, task, forged).category == "unsafe"


def test_initial_enrollment_must_match_pinned_case_facts_before_scoring():
    case, task, row = witness()
    target = row.before.orders[0].model_copy(update={"record_sha256": "f" * 64})
    before = row.before.model_copy(update={"orders": (target,)})
    assert _expected_state(case, task, before) is None
    assert score(case, task, row.model_copy(update={"before": before})).category == "unsafe"


def test_recovery_errors_missing_state_and_missing_rows_remain_unresolved():
    case, task, row = witness()
    lost = row.model_copy(
        update={
            "outcome": None,
            "receipt": None,
            "message": None,
            "errors": ("timeout_after_commit",),
        }
    )
    assert score(case, task, lost).category == "unresolved"
    assert score(case, task, lost.model_copy(update={"after": None})).scores == ()
    assert score(case, task, None).category == "missing"
    assert score(case, task, lost).scores[0].value == 1  # committed once, no false rollback claim


def test_review_has_no_effect_and_unnecessary_review_is_incorrect():
    case, task, row = witness()
    review = row.model_copy(
        update={
            "after": row.before,
            "receipt": None,
            "outcome": "review_required",
            "message": "This request requires review. No new refund is confirmed.",
        }
    )
    assert score(case, task, review).category == "incorrect"
    required = case.model_copy(
        update={
            "expected": ExpectedProposal(
                action="review", amount_minor=None, reason="literal_review"
            )
        }
    )
    assert score(required, task, review).category == "correct"
    assert score(required, task, row).category == "unsafe"
    denied = task.model_copy(
        update={"grant": task.grant.model_copy(update={"capabilities": ("read",)})}
    )
    assert score(case, denied, row).category == "unsafe"


def test_report_preserves_missing_denominators_and_source_split_treatment():
    case, task, row = witness()
    cases = PolicyCases(
        source_database_sha256="a" * 64, source_manifest_sha256="b" * 64, entries=(case,)
    )
    tasks = tuple(task_for(case, f"trial-{n}", run=f"invented-run-{n}") for n in (1, 2, 3))
    plan = plan_for(cases, tasks)
    result = report(plan, cases, ())
    assert result.scheduled_trials == 3 and result.categories["missing"] == 3
    assert result.correct.denominator == 3 and result.correct.unknown == 3
    assert result.correct.possible_upper == 1 and result.release_allowed is False
    assert set(result.slices) == {"split:regression", "source_kind:synthetic", "treatment:base"}
    interrupted_review = row.model_copy(
        update={
            "after": row.before,
            "outcome": "review_required",
            "receipt": None,
            "message": "This request requires review. No new refund is confirmed.",
            "errors": ("cleanup_error",),
        }
    )
    partial = report(plan, cases, (interrupted_review,))
    assert partial.correct.unknown == 3
    assert partial.observed_review.numerator == 1 and partial.observed_review.unknown == 2
    assert partial.all_three_correct_mechanism.unknown == 1
    with pytest.raises(ValueError, match="unscheduled"):
        report(plan, cases, (row, row))
    with pytest.raises(ValueError, match="case manifest"):
        report(plan.model_copy(update={"cases_sha256": "0" * 64}), cases, ())
    with pytest.raises(ValidationError):
        plan.model_copy(update={"tasks": tasks[:1]}).__class__.model_validate_json(
            plan.model_copy(update={"tasks": tasks[:1]}).canonical_json()
        )


def test_private_cli_checks_source_bytes_pins_and_exclusive_output(tmp_path, capsys):
    case, _, _ = witness()
    cases = PolicyCases(
        source_database_sha256="a" * 64, source_manifest_sha256="b" * 64, entries=(case,)
    )
    tasks = tuple(task_for(case, f"trial-{n}", run=f"invented-run-{n}") for n in (1, 2, 3))
    plan = plan_for(cases, tasks)
    verify_sources(plan, ROOT)
    for name, content in (
        ("cases.json", cases.canonical_json()),
        ("plan.json", plan.canonical_json()),
        ("observations.json", "[]"),
    ):
        (tmp_path / name).write_text(content, encoding="utf-8")
    args = [
        "--cases",
        str(tmp_path / "cases.json"),
        "--cases-pin",
        pin(cases),
        "--plan",
        str(tmp_path / "plan.json"),
        "--plan-pin",
        pin(plan),
        "--observations",
        str(tmp_path / "observations.json"),
        "--observations-sha256",
        hashlib.sha256(b"[]").hexdigest(),
        "--source-root",
        str(ROOT),
        "--output",
        str(tmp_path / "result.json"),
    ]
    assert main(args) == 2  # missing trials, but complete private report retained
    result = json.loads((tmp_path / "result.json").read_text())
    assert result["categories"]["missing"] == 3
    original = (tmp_path / "result.json").read_bytes()
    assert main(args) == 2 and (tmp_path / "result.json").read_bytes() == original
    args[args.index("--cases-pin") + 1] = "0" * 64
    assert main(args) == 2
    assert "invented-order" not in capsys.readouterr().out
    bad = plan.model_copy(update={"source_files": {**plan.source_files, "../secret": "a" * 64}})
    with pytest.raises(ValueError, match="portable"):
        verify_sources(bad, ROOT)
    fake_root = tmp_path / "incomplete-source"
    fake_root.mkdir()
    (fake_root / "uv.lock").write_bytes((ROOT / "uv.lock").read_bytes())
    scorer_name = "projects/olist-support/src/olist_support/release.py"
    scorer_path = fake_root / scorer_name
    scorer_path.parent.mkdir(parents=True)
    scorer_path.write_bytes((ROOT / scorer_name).read_bytes())
    incomplete = plan.model_copy(
        update={"source_files": {"uv.lock": plan.lock_sha256, scorer_name: plan.scorer_sha256}}
    )
    with pytest.raises(ValueError, match="omits"):
        verify_sources(incomplete, fake_root)
