"""Actual H10 dispatch/journal/SQL checks with invented inputs and a mock transport."""

import pytest
from agent_harness.evaluation_standards import (
    StandardCase,
    StandardProfile,
    StandardProtocol,
    audit_study,
)
from agent_harness.release_contracts import pin
from agent_harness.trials import TrialJournal, assess
from olist_h10_fixtures import ROOT, composition
from olist_support.field_evaluation import FIELDS
from olist_support.h10_environment import OlistEnvironment
from olist_support.h10_evidence import read_olist_evidence as read_evidence
from olist_support.h10_manifest import private_case
from olist_support.h10_recording import record_olist
from olist_support.h10_study import assemble_olist_study
from test_olist_business import app as app


@pytest.mark.parametrize("kind", ["refund", "review", "recovery", "unknown_cost", "failure"])
def test_olist_uses_owned_h10_receipts_private_scores_and_parent_cleanup(app, tmp_path, kind):
    server, parent, _ = app
    _, loaded, schedule, factory = composition(
        review=kind == "review",
        recovery=kind == "recovery",
        unknown_cost=kind == "unknown_cost",
        failure=kind == "failure",
    )
    output = tmp_path / "new-recording"
    manifest = record_olist(
        schedule,
        loaded,
        factory,
        OlistEnvironment(server, parent.workspace_key, loaded),
        output,
        candidate_sha256=pin(factory.candidate),
        source_root=ROOT,
    )
    assert manifest.origin == "mock" and len(manifest.receipts) == 3
    batch = TrialJournal(output / "journal").read(loaded)
    assert len(batch.rows) == 3 and not batch.missing
    assert all(row.timing is not None and row.timing.elapsed_seconds > 0 for row in batch.rows)
    assert all(
        row.timing.setup_seconds > 0 and row.timing.cleanup_seconds > 0 for row in batch.rows
    )
    assert all(not row.errors and row.report is not None for row in batch.rows)
    assert all(row.report.report.result.usage.model_calls == 1 for row in batch.rows)
    with server.connect() as admin:
        for row in batch.rows:
            database = row.state_ref.removeprefix("olist-h10:")
            assert not admin.execute(
                "SELECT 1 FROM pg_database WHERE datname=%s", (database,)
            ).fetchone()
            assert not admin.execute(
                "SELECT 1 FROM pg_roles WHERE rolname=%s", (database,)
            ).fetchone()
    if kind == "unknown_cost":
        assert all(row.report.report.result.usage.cost is None for row in batch.rows)
        with pytest.raises(ValueError, match="usage evidence is incomplete"):
            read_evidence(
                output,
                loaded,
                evidence_sha256=pin(manifest),
                candidate_sha256=pin(factory.candidate),
            )
        return
    verified = read_evidence(
        output, loaded, evidence_sha256=pin(manifest), candidate_sha256=pin(factory.candidate)
    )
    assert len({r.nonce for r in verified.receipts}) == 3
    assert all(r.exchange.occurrence == 1 for r in verified.receipts)
    if kind == "refund":
        label, _ = private_case(loaded.manifest.entries[0].case)
        profile = StandardProfile(
            version="invented-olist-study",
            agent="olist",
            required_fields=FIELDS,
            required_holdout_slices=("eligible_refund",),
        )
        protocol = StandardProtocol(
            version="invented",
            profile_sha256=pin(profile),
            dataset_sha256=loaded.pin.sha256,
            scorer_sha256=factory.candidate.scorer_sha256,
            baseline_sha256=pin(manifest),
            frozen_at=manifest.started_at,
            trials_per_case=3,
        )
        cases = (
            StandardCase(
                case_id=label.input.case_id,
                independence_keys=(label.group_id,),
                language_family="invented",
                input_text=label.input.request.message,
                split=label.split,
                source_kind=label.source_kind,
                slices=("eligible_refund",),
                eligible_for_autonomy=True,
                required_review=False,
                critical=True,
            ),
        )
        # Same mock evidence in both slots tests read-back/projection only, not an
        # independent baseline comparison or model-quality study.
        study = assemble_olist_study(
            profile,
            protocol,
            cases,
            loaded,
            baseline_root=output,
            baseline_evidence_sha256=pin(manifest),
            baseline_candidate_sha256=pin(factory.candidate),
            candidate_root=output,
            candidate_evidence_sha256=pin(manifest),
            candidate_sha256=pin(factory.candidate),
            required_case_ids=loaded.manifest.case_ids,
        )
        assert len(study.rows) == 3 and all(r.correct for r in study.rows)
        assert all(
            r.elapsed_seconds == row.timing.elapsed_seconds
            for r, row in zip(study.rows, batch.rows, strict=True)
        )
        assert all(c.label_review is None for c in study.cases)
        audit = audit_study(profile, protocol, study, now=manifest.finished_at)
        assert (
            not audit["release_allowed"] and "labels_not_independently_frozen" in audit["blockers"]
        )
    if kind == "failure":
        assert all(
            assess(r, schedule.outcome_policy).category == "safe_unresolved" for r in batch.rows
        )
        assert all(r.report.report.result.failure.code == "timeout" for r in batch.rows)
        assert batch.autonomous_completions == 0
    else:
        assert batch.complete
        for row in batch.rows:
            scores = {s.metric: s for s in row.report.report.scores}
            assert all(scores[name].value == 1 and scores[name].failure is None for name in FIELDS)
        assert batch.autonomous_completions == (0 if kind == "review" else 3)
        assert sum(
            assess(row, schedule.outcome_policy).category == "appropriate_review"
            for row in batch.rows
        ) == (3 if kind == "review" else 0)
    # Same sealed evidence is read twice; there is no dispatch during read-back.
    assert (
        read_evidence(
            output, loaded, evidence_sha256=pin(manifest), candidate_sha256=pin(factory.candidate)
        )
        == verified
    )
    if kind == "refund":
        next((output / "observations").glob("*.json")).write_text("{}", encoding="utf-8")
        expected_error = "differs from sealed"
    elif kind == "review":
        next((output / "observations").glob("*.json")).unlink()
        expected_error = "missing or unreadable"
    elif kind == "recovery":
        (output / "observations" / "unclaimed.json").write_text("{}", encoding="utf-8")
        expected_error = "unexpected files"
    else:
        return
    with pytest.raises(ValueError, match=expected_error):
        read_evidence(
            output, loaded, evidence_sha256=pin(manifest), candidate_sha256=pin(factory.candidate)
        )
