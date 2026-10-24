"""H7 deterministic boundary execution, state-based outcomes and fail-closed evidence."""

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from agent_harness.cases import LoadedManifest
from agent_harness.contracts import AgentInput, ModelMessage, ModelRequest
from agent_harness.evaluation import ScoreResult
from agent_harness.fault_contracts import FaultPlan, FaultRule
from agent_harness.fault_example import (
    FaultExampleFactory,
    InventedStore,
    approved_effect,
    fault_population,
)
from agent_harness.faults import (
    FaultGateway,
    FaultSession,
    InjectedToolTimeout,
    fault_category,
    selected_occurrence,
    verify_evidence,
)
from agent_harness.invariants import (
    ReviewRecord,
    StateExpectation,
    StateObservation,
    inspect_state,
)
from agent_harness.offline_example import FakeGateway
from agent_harness.trial_example import FileTrialEnvironment, InventedFactory
from agent_harness.trial_runner import run_trials
from agent_harness.trials import BatchReport, TrialJournal, TrialRow, assess
from pydantic import ValidationError


def inline(tmp_path, index, *, behavior="careful", deduplicate=True):
    loaded, schedule = fault_population("h7-invented-test-source", "h7-invented-lock")
    task = schedule.tasks[index - 1]
    case = loaded.entry(task.context.case_id).case
    environment = FileTrialEnvironment(tmp_path)
    lease = environment.prepare(schedule.experiment_id, task)
    session = FaultSession(task.context, case.faults, schedule.fault_plan)
    parts = FaultExampleFactory(behavior, deduplicate).build_faults(task.context, lease, session)
    report = parts.scorers.bind(loaded).run_case(
        task.context, case.case_id, parts.agent, parts.gateway, faults=session
    )
    actual = InventedStore(parts.agent.tools.store.path).read()
    environment.release(lease)
    return loaded, schedule, TrialRow(task=task, report=report), actual


@pytest.mark.parametrize("index", range(1, 9))
def test_each_fault_is_reproducible_and_independently_scored(tmp_path, index):
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    first_root.mkdir()
    second_root.mkdir()
    loaded, schedule, row, actual = inline(first_root, index)
    _, _, second, second_actual = inline(second_root, index)
    assert row == second and actual == second_actual
    case = loaded.entry(row.task.context.case_id).case
    evidence = row.report.report.fault_evidence
    assert evidence.complete and len(evidence.events) == 1
    assert verify_evidence(evidence, schedule.fault_plan, case, row.task.context.seed)
    assessment = assess(row, schedule.outcome_policy)
    assert assessment.evidence_complete
    assert fault_category(row, assessment, recoverable=case.faults[0].recoverable) == (
        "appropriate_review" if index == 2 else "recovered"
    )
    assert len(actual.effects) == (0 if index == 2 else 1)
    assert actual.state == {"status": "start" if index == 2 else "done"}
    wire = evidence.canonical_json()
    assert "UNTRUSTED EXAMPLE" not in wire and "expected_safe_behavior" not in wire
    assert not tuple(first_root.iterdir()) and not tuple(second_root.iterdir())


@pytest.mark.parametrize(
    "index,behavior,deduplicate,invariant",
    [
        (5, "blind_retry", False, "effects_once"),
        (6, "careful", False, "effects_once"),
        (7, "obey_injection", True, "authorized_effects"),
    ],
)
def test_claimed_completion_cannot_hide_duplicate_or_unauthorized_effects(
    tmp_path, index, behavior, deduplicate, invariant
):
    _, schedule, row, actual = inline(tmp_path, index, behavior=behavior, deduplicate=deduplicate)
    assert row.report.report.result.outcome == "completed"
    scores = {score.metric: score.value for score in row.report.report.scores}
    assert scores[invariant] == scores["fault_safe"] == scores["fault_correct"] == 0
    assert len(actual.effects) == (1 if index == 7 else 2)
    verdict = assess(row, schedule.outcome_policy)
    assert verdict.category == fault_category(row, verdict, recoverable=True) == "unsafe"


@pytest.mark.parametrize("behavior,expected", [("blocked", "safe_unresolved"), ("claim", "unsafe")])
def test_outage_is_not_automatic_recovery(tmp_path, behavior, expected):
    _, schedule, row, actual = inline(tmp_path, 2, behavior=behavior)
    verdict = assess(row, schedule.outcome_policy)
    assert fault_category(row, verdict, recoverable=False) == expected
    assert not actual.effects and not actual.reviews
    assert verdict.category != "autonomous_completion"


@pytest.mark.parametrize(
    "kind,target,timing,payload",
    [
        ("outage", "model", "after_commit", None),
        ("malformed_output", "tool:write", "after_dispatch", "bad"),
        ("stale_read", "model", "after_dispatch", {}),
        ("tool_timeout", "tool:write", "after_dispatch", None),
        ("duplicate_delivery", "tool:write", "before_dispatch", None),
        ("injection_content", "input", "after_dispatch", "bad"),
        ("outage", "model", "before_dispatch", "bad"),
        ("injection_content", "input", "before_dispatch", None),
    ],
)
def test_unsupported_fault_shapes_are_refused(kind, target, timing, payload):
    with pytest.raises(ValidationError):
        FaultRule.model_validate_json(
            json.dumps(
                dict(scenario_id="s", kind=kind, target=target, timing=timing, payload=payload)
            )
        )


def test_seeded_occurrence_uses_stable_hash_without_global_rng():
    rule = FaultRule(
        scenario_id="s",
        kind="outage",
        target="model",
        timing="before_dispatch",
        first_occurrence=1,
        last_occurrence=9,
    )
    plan = FaultPlan(version="v1", rules=(rule,))
    expected = int.from_bytes(hashlib.sha256(b'["v1","s",42]').digest(), "big") % 9 + 1
    assert selected_occurrence(plan, rule, 42) == expected
    assert len({selected_occurrence(plan, rule, seed) for seed in range(30)}) > 1
    with pytest.raises(ValueError, match="reversed"):
        FaultRule(
            scenario_id="s",
            kind="outage",
            target="model",
            timing="before_dispatch",
            first_occurrence=3,
            last_occurrence=2,
        )
    with pytest.raises(ValueError, match="duplicate"):
        FaultPlan(version="v1", rules=(rule, rule))


@pytest.mark.parametrize(
    "change", ["absent", "extra", "missing", "timing", "inventory", "invariants", "conflict"]
)
def test_invalid_plan_fails_before_state_preparation(tmp_path, change):
    loaded, schedule = fault_population("source", "lock")
    plan = schedule.fault_plan
    if change == "absent":
        schedule = schedule.model_copy(update={"fault_plan": None})
    elif change == "inventory":
        schedule = schedule.model_copy(update={"fault_case_ids": ()})
    elif change in ("invariants", "conflict"):
        manifest = loaded.manifest
        entry = manifest.entries[0]
        scenario = entry.case.faults[0]
        if change == "invariants":
            scenarios = (scenario.model_copy(update={"required_invariants": ()}),)
        else:
            scenarios = (
                *entry.case.faults,
                scenario.model_copy(update={"scenario_id": "conflict"}),
            )
            rule = plan.rules[0].model_copy(update={"scenario_id": "conflict"})
            plan = plan.model_copy(update={"rules": (*plan.rules, rule)})
        entry = entry.model_copy(
            update={"case": entry.case.model_copy(update={"faults": scenarios})}
        )
        manifest = manifest.model_copy(update={"entries": (entry, *manifest.entries[1:])})
        payload = manifest.canonical_json().encode()
        pin = loaded.pin.model_copy(update={"sha256": hashlib.sha256(payload).hexdigest()})
        loaded = LoadedManifest(payload, pin)
        schedule = schedule.model_copy(update={"manifest": pin, "fault_plan": plan})
    else:
        rules = (
            plan.rules[:-1]
            if change == "missing"
            else (*plan.rules, plan.rules[-1].model_copy(update={"scenario_id": "extra"}))
        )
        if change == "timing":
            rules = (*plan.rules[:-1], plan.rules[-1].model_copy(update={"timing": "after_commit"}))
        schedule = schedule.model_copy(
            update={"fault_plan": plan.model_copy(update={"rules": rules})}
        )
    with pytest.raises(ValueError):
        run_trials(
            schedule,
            loaded,
            FaultExampleFactory(),
            FileTrialEnvironment(tmp_path),
            tmp_path / "journal",
        )
    assert not tuple(tmp_path.iterdir())


def test_before_and_after_commit_timeout_have_different_real_effects():
    loaded, schedule = fault_population("source", "lock")
    for index, committed_calls in ((4, 0), (5, 1), (8, 0)):
        task = schedule.tasks[index - 1]
        case = loaded.entry(task.context.case_id).case
        session = FaultSession(task.context, case.faults, schedule.fault_plan)
        session.bind(task.context, case.faults)
        calls = []

        def operation(calls=calls):
            calls.append("committed")
            return None

        with pytest.raises(InjectedToolTimeout):
            session.invoke("tool:write", operation, committed=True, resume=True)
        assert len(calls) == committed_calls and session.evidence().complete
        session.invoke("tool:write", operation, committed=True, resume=True)
        assert len(calls) == committed_calls + 1 and len(session.evidence().events) == 1


def test_unreached_hook_is_incomplete_and_cannot_pass_gate(tmp_path):
    loaded, schedule, row, _ = inline(tmp_path, 5)
    evidence = row.report.report.fault_evidence.model_copy(update={"events": ()})
    changed = row.model_copy(
        update={
            "report": row.report.model_copy(
                update={"report": row.report.report.model_copy(update={"fault_evidence": evidence})}
            )
        }
    )
    assert not assess(changed, schedule.outcome_policy).evidence_complete
    journal = TrialJournal.create(tmp_path / "journal", schedule)
    journal.append(changed)
    recovered = journal.read(loaded, fault_plan=schedule.fault_plan)
    assert not recovered.complete and recovered.eligible_trials == 7
    with pytest.raises(ValueError, match="fault evidence"):
        recovered.require_release_evidence(loaded, fault_plan=schedule.fault_plan)
    altered = evidence.model_copy(update={"seed": 999})
    assert not verify_evidence(
        altered,
        schedule.fault_plan,
        loaded.entry(row.task.context.case_id).case,
        row.task.context.seed,
        require_complete=False,
    )


def test_invariant_absence_or_known_violation_cannot_be_hidden(tmp_path):
    _, schedule, row, _ = inline(tmp_path, 1)
    report = row.report.report
    for value, category, complete in ((None, "unverified", False), (0, "unsafe", True)):
        scores = tuple(score for score in report.scores if score.metric != "effects_once")
        if value is not None:
            scores += (
                ScoreResult(
                    metric="effects_once",
                    scorer_version=report.scorer_version,
                    eligible=True,
                    value=float(value),
                ),
            )
        changed = row.model_copy(
            update={
                "report": row.report.model_copy(
                    update={"report": report.model_copy(update={"scores": scores})}
                )
            }
        )
        verdict = assess(changed, schedule.outcome_policy)
        assert verdict.category == category and verdict.evidence_complete == complete


def test_session_reuse_context_drift_and_early_execution_are_rejected():
    loaded, schedule = fault_population("source", "lock")
    context = schedule.tasks[0].context
    case = loaded.entry(context.case_id).case
    session = FaultSession(context, case.faults, schedule.fault_plan)
    with pytest.raises(ValueError, match="not bound"):
        session.input(AgentInput(request="invented"))
    with pytest.raises(ValueError, match="changed"):
        session.bind(context.model_copy(update={"seed": 100}), case.faults)
    session.bind(context, case.faults)
    with pytest.raises(ValueError, match="reused"):
        session.bind(context, case.faults)
    with pytest.raises(ValueError, match="context"):
        FaultGateway(session, FakeGateway()).generate(
            context.model_copy(update={"seed": 100}),
            ModelRequest(
                provider="fake",
                model="uppercase-v1",
                endpoint="in-process",
                messages=(ModelMessage(role="user", content="invented"),),
                parameters={"temperature": 0},
            ),
        )


def test_pure_state_invariants_use_exact_independent_effects_and_durable_reviews():
    effect = approved_effect()
    expected = StateExpectation(
        state={"status": "done"},
        allowed_effects=(effect,),
        required_operation_keys=(effect.operation_key,),
        business_event_id="event",
        allowed_review_reasons=("outage",),
    )
    actual = StateObservation(
        state={"status": "done"},
        effects=(effect,),
        reviews=(
            ReviewRecord(reference="valid", business_event_id="event", reason="outage"),
            ReviewRecord(reference="wrong-event", business_event_id="other", reason="outage"),
        ),
    )
    assert inspect_state(actual, expected).correct
    assert inspect_state(actual, expected).valid_reviews == ("valid",)
    assert not inspect_state(actual.model_copy(update={"effects": ()}), expected).correct
    assert not inspect_state(actual.model_copy(update={"effects": (effect, effect)}), expected).safe
    for field in ("actor", "target", "payload_sha256", "operation_key"):
        altered = effect.model_copy(update={field: "unapproved"})
        assert not inspect_state(
            actual.model_copy(update={"effects": (altered,)}), expected
        ).authorized_effects
    with pytest.raises(ValueError, match="duplicate"):
        expected.model_validate_json(
            expected.model_copy(update={"allowed_effects": (effect, effect)}).canonical_json()
        )


def test_spawned_fault_matrix_keeps_all_rows_and_reopens_pinned_evidence(tmp_path):
    loaded, schedule = fault_population("source", "lock")
    state = tmp_path / "state"
    state.mkdir()
    report = run_trials(
        schedule, loaded, FaultExampleFactory(), FileTrialEnvironment(state), tmp_path / "journal"
    )
    assert (
        report.complete
        and len(report.rows) == 8
        and report.eligible_trials == report.autonomous_completions == 7
    ), [
        (row.task.key, row.errors, assess(row, schedule.outcome_policy).category)
        for row in report.rows
    ]
    report.require_release_evidence(loaded, fault_plan=schedule.fault_plan)
    assert TrialJournal(tmp_path / "journal").read(loaded, fault_plan=schedule.fault_plan) == report
    assert not tuple(state.iterdir())


def test_faults_require_explicit_factory_composition(tmp_path):
    loaded, schedule = fault_population("source", "lock")
    state = tmp_path / "state"
    state.mkdir()
    report = run_trials(
        schedule, loaded, InventedFactory(), FileTrialEnvironment(state), tmp_path / "journal"
    )
    assert len(report.rows) == 8 and all(row.errors == ("execution_error",) for row in report.rows)
    assert not report.complete and report.autonomous_completions == 0


def test_seeded_model_hook_fires_at_the_selected_occurrence_only():
    loaded, schedule = fault_population("source", "lock")
    task = schedule.tasks[1]
    case = loaded.entry(task.context.case_id).case
    rule = schedule.fault_plan.rules[1].model_copy(
        update={"first_occurrence": 2, "last_occurrence": 5}
    )
    plan = FaultPlan(version="window-v1", rules=(rule,))
    selected = selected_occurrence(plan, rule, task.context.seed)
    session = FaultSession(task.context, case.faults, plan)
    session.bind(task.context, case.faults)
    delegate = FakeGateway()
    gateway = FaultGateway(session, delegate)
    request = ModelRequest(
        provider="fake",
        model="uppercase-v1",
        endpoint="in-process",
        messages=(ModelMessage(role="user", content="invented"),),
        parameters={"temperature": 0},
    )
    results = [gateway.generate(task.context, request) for _ in range(6)]
    assert [index + 1 for index, response in enumerate(results) if response.failure] == [selected]
    assert len(delegate.requests) == 5 and session.evidence().events[0].occurrence == selected
    assert results[selected - 1].usage.model_calls == 0 and results[selected - 1].usage.cost is None


def test_after_commit_hook_requires_the_adapter_to_declare_commit():
    loaded, schedule = fault_population("source", "lock")
    task = schedule.tasks[4]
    case = loaded.entry(task.context.case_id).case
    session = FaultSession(task.context, case.faults, schedule.fault_plan)
    session.bind(task.context, case.faults)
    session.invoke("tool:write", lambda: None)
    assert not session.evidence().complete


def test_hook_order_cannot_depend_on_concurrent_agent_threads():
    loaded, schedule = fault_population("source", "lock")
    task = schedule.tasks[0]
    case = loaded.entry(task.context.case_id).case
    session = FaultSession(task.context, case.faults, schedule.fault_plan)
    session.bind(task.context, case.faults)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(session.input, AgentInput(request="invented"))
        with pytest.raises(ValueError, match="execution thread"):
            future.result()
    assert not session.evidence().events


@pytest.mark.parametrize("change", ["plan", "event", "invariants", "declaration", "absent"])
def test_recovered_fault_evidence_requires_reviewed_plan_and_exact_metadata(tmp_path, change):
    loaded, schedule, row, _ = inline(tmp_path, 1)
    journal = TrialJournal.create(tmp_path / "journal", schedule)
    report = row.report.report
    evidence = report.fault_evidence
    if change == "plan":
        plan = schedule.fault_plan.model_copy(update={"version": "unreviewed"})
        altered = schedule.model_copy(update={"fault_plan": plan})
        (journal.path / "schedule.json").write_text(altered.canonical_json(), encoding="utf-8")
    elif change != "absent":
        if change == "event":
            evidence = evidence.model_copy(
                update={"events": (evidence.events[0].model_copy(update={"occurrence": 9}),)}
            )
        elif change == "invariants":
            evidence = evidence.model_copy(update={"required_invariants": ("other",)})
        else:
            evidence = evidence.model_copy(update={"declaration_sha256": "0" * 64})
        row = row.model_copy(
            update={
                "report": row.report.model_copy(
                    update={"report": report.model_copy(update={"fault_evidence": evidence})}
                )
            }
        )
    journal.append(row)
    with pytest.raises(ValueError, match="fault"):
        journal.read(loaded, fault_plan=None if change == "absent" else schedule.fault_plan)


def test_missing_entire_fault_evidence_is_incomplete_and_gate_rejects(tmp_path):
    loaded, schedule, row, _ = inline(tmp_path, 1)
    row = row.model_copy(
        update={
            "report": row.report.model_copy(
                update={"report": row.report.report.model_copy(update={"fault_evidence": None})}
            )
        }
    )
    batch = BatchReport(schedule=schedule, rows=(row,))
    assert not batch.complete
    with pytest.raises(ValueError, match="fault evidence"):
        batch.require_release_evidence(loaded, fault_plan=schedule.fault_plan)
