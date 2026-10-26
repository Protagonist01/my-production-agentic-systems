"""Real owned process death and SQL restart; operator intent, zero model dispatches."""

import pytest
from agent_harness.release_contracts import pin
from agent_harness.trial_runner import WorkerCleanupError
from olist_h10_fixtures import composition
from olist_support.crash_evidence import assess_crash, collect_crash, read_crash
from olist_support.h10_environment import OlistEnvironment
from olist_support.workflow import WorkflowRequest
from test_olist_business import app as app


@pytest.mark.parametrize("crash_stage", ["before_commit", "after_commit"])
def test_saved_process_death_restart_and_redelivery_recompute_after_owned_database_cleanup(
    app, tmp_path, crash_stage
):
    server, parent, _ = app
    label, loaded, schedule, _ = composition()
    task = schedule.tasks[0]
    context = task.context.model_copy(update={"mode": "offline_fake"})
    task = task.model_copy(update={"context": context})
    environment = OlistEnvironment(server, parent.workspace_key, loaded)
    lease = environment.prepare("invented-process-crash", task)
    output = tmp_path / "process-crash"
    can_release = True
    try:
        try:
            evidence = collect_crash(
                context,
                lease.access,
                WorkflowRequest(
                    order_id=label.input.order.order_id, text=label.input.request.message
                ),
                output,
                crash_stage=crash_stage,
            )
        except WorkerCleanupError:
            can_release = False
            raise
    finally:
        if can_release:
            environment.release(lease)
    report = read_crash(output, evidence_sha256=pin(evidence), label=label, context=context)
    assert report["passed"] and report["mechanism_only"] and report["provider_calls"] == 0
    assert report["process_death_observed"] and report["exact_state_after_restart_and_duplicate"]
    assert not report["release_allowed"] and evidence.exit_code == 23 and not evidence.errors
    assert evidence.result.receipt.original_run_id == context.run_id + (
        "-restart" if crash_stage == "before_commit" else ""
    )
    if crash_stage == "before_commit":
        assert evidence.committed == evidence.before
    else:
        assert "before_commit_boundary" not in evidence.model_dump(mode="json")
    with server.connect() as admin:
        database = lease.reference.removeprefix("olist-h10:")
        assert (
            admin.execute("SELECT 1 FROM pg_database WHERE datname=%s", (database,)).fetchone()
            is None
        )
    for change in ("boundary", "exit", "state", "result", "errors"):
        if change == "boundary":
            altered = evidence.model_copy(
                update={
                    "before_commit_boundary"
                    if crash_stage == "before_commit"
                    else "after_commit_boundary": False
                }
            )
        elif change == "exit":
            altered = evidence.model_copy(update={"exit_code": 0})
        elif change == "state":
            altered = evidence.model_copy(update={"duplicate": evidence.before})
        elif change == "result":
            altered = evidence.model_copy(update={"duplicate_result": None})
        else:
            altered = evidence.model_copy(update={"errors": ("worker_timeout",)})
        assert not assess_crash(altered, label, context)["passed"]
    path = output / "crash.json"
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="external pin"):
        read_crash(output, evidence_sha256=pin(evidence), label=label, context=context)


def test_process_drill_rejects_fresh_mode_before_state_or_output(app, tmp_path):
    server, parent, _ = app
    label, loaded, schedule, _ = composition()
    environment = OlistEnvironment(server, parent.workspace_key, loaded)
    task = schedule.tasks[0]
    lease = environment.prepare("invented-rejected-process-drill", task)
    try:
        with pytest.raises(ValueError, match="explicit offline"):
            collect_crash(
                task.context,
                lease.access,
                WorkflowRequest(
                    order_id=label.input.order.order_id, text=label.input.request.message
                ),
                tmp_path / "forbidden",
            )
        assert not (tmp_path / "forbidden").exists()
    finally:
        environment.release(lease)


def test_two_boundaries_are_bound_to_exact_receipted_candidate_and_external_protocol(app, tmp_path):
    from olist_h10_fixtures import ROOT
    from olist_support.fault_binding import FaultBundle, FaultEntry, read_fault_bundle
    from olist_support.h10_evidence import read_olist_evidence
    from olist_support.h10_recording import record_olist

    server, parent, _ = app
    label, loaded, schedule, factory = composition()
    environment = OlistEnvironment(server, parent.workspace_key, loaded)
    output = tmp_path / "candidate"
    manifest = record_olist(
        schedule,
        loaded,
        factory,
        environment,
        output,
        candidate_sha256=pin(factory.candidate),
        source_root=ROOT,
    )
    candidate = read_olist_evidence(
        output, loaded, evidence_sha256=pin(manifest), candidate_sha256=pin(factory.candidate)
    )
    task = schedule.tasks[0]
    context = task.context
    scope = pin(context)
    root = tmp_path / "faults"
    (root / scope).mkdir(parents=True)
    entries = []
    for stage in ("before_commit", "after_commit"):
        drill = context.model_copy(
            update={"mode": "offline_fake", "run_id": context.run_id + "-" + stage}
        )
        lease = environment.prepare("bound-" + stage, task.model_copy(update={"context": drill}))
        can_release = True
        try:
            try:
                saved = collect_crash(
                    drill,
                    lease.access,
                    WorkflowRequest(
                        order_id=label.input.order.order_id, text=label.input.request.message
                    ),
                    root / scope / stage,
                    crash_stage=stage,
                )
            except WorkerCleanupError:
                can_release = False
                raise
        finally:
            if can_release:
                environment.release(lease)
        entries.append(FaultEntry(context_sha256=scope, stage=stage, evidence_sha256=pin(saved)))
    bundle = FaultBundle(
        candidate_sha256=pin(factory.candidate),
        candidate_evidence_sha256=pin(manifest),
        dataset_sha256=loaded.pin.sha256,
        entries=tuple(entries),
    )
    path = root / "bundle.json"
    path.write_text(bundle.canonical_json(), encoding="utf-8")
    report = read_fault_bundle(
        root, loaded, candidate, bundle_sha256=pin(bundle), required_contexts=(scope,)
    )
    assert (
        report["passed"] and report["boundary_observations"] == 2 and not report["release_allowed"]
    )
    assert not report["full_fault_matrix_complete"]
    with pytest.raises(ValueError, match="boundaries"):
        read_fault_bundle(
            root,
            loaded,
            candidate,
            bundle_sha256=pin(bundle),
            required_contexts=tuple(pin(t.context) for t in schedule.tasks),
        )
    for field in ("candidate_sha256", "candidate_evidence_sha256", "dataset_sha256"):
        altered = bundle.model_copy(update={field: "0" * 64})
        path.write_text(altered.canonical_json(), encoding="utf-8")
        with pytest.raises(ValueError, match="scope differs"):
            read_fault_bundle(
                root, loaded, candidate, bundle_sha256=pin(altered), required_contexts=(scope,)
            )
