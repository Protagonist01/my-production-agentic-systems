"""Actual zero-call Olist SQL comparators and a separately receipted mock candidate."""

from dataclasses import dataclass
from decimal import Decimal

import pytest
from agent_harness.cases import LoadedManifest, ManifestPin
from agent_harness.contracts import ModelMessage, ModelResponse, Usage
from agent_harness.evaluation_standards import (
    StandardCase,
    StandardProfile,
    StandardProtocol,
    audit_study,
)
from agent_harness.release_contracts import pin, sha256
from olist_h10_fixtures import ROOT, composition
from olist_support.baseline_recording import (
    OlistBaselineFactory,
    read_olist_baseline,
    record_olist_baseline,
)
from olist_support.field_evaluation import FIELDS
from olist_support.h10_environment import OlistEnvironment
from olist_support.h10_manifest import manifest_for
from olist_support.h10_recording import record_olist
from olist_support.h10_study import assemble_olist_study
from olist_support.policy_cases import PolicyCases
from test_olist_business import app as app


@dataclass(frozen=True)
class InventedIntent:
    def generate(self, request, *, timeout_seconds=30.0):
        return ModelResponse(
            provider=request.provider,
            model=request.model,
            output=ModelMessage(
                role="assistant", content='{"intent":"refund","requested_minor":null}'
            ),
            usage=Usage(
                model_calls=1, input_tokens=0, output_tokens=0, cost=Decimal(0), cost_currency="USD"
            ),
        )


@pytest.mark.parametrize("kind", ["rules", "always-review", "recovery"])
def test_zero_call_olist_workflows_have_real_state_and_can_pair_with_fresh_mock_candidate(
    app, tmp_path, kind
):
    server, parent, _ = app
    label, loaded, schedule, fresh = composition(recovery=kind == "recovery")
    label = label.model_copy(
        update={
            "input": label.input.model_copy(
                update={
                    "request": label.input.request.model_copy(
                        update={
                            "message": (
                                "Primary request: please refund the full paid amount "
                                "for this order."
                            )
                        }
                    )
                }
            )
        }
    )
    manifest = manifest_for(
        PolicyCases(
            source_database_sha256="a" * 64, source_manifest_sha256="b" * 64, entries=(label,)
        ),
        recovery_case_ids=(label.input.case_id,) if kind == "recovery" else (),
    )
    raw = manifest.canonical_json().encode()
    loaded = LoadedManifest(
        raw,
        ManifestPin(manifest_id=manifest.manifest_id, version=manifest.version, sha256=sha256(raw)),
    )
    schedule = schedule.model_copy(update={"manifest": loaded.pin})
    selected = "always-review" if kind == "always-review" else "rules"
    spec = fresh.candidate.model_copy(
        update={
            "candidate": "invented-olist-" + kind + "-baseline",
            "prompt_sha256": sha256(("olist-" + selected + "-deterministic-v1").encode()),
        }
    )
    tasks = tuple(
        t.model_copy(
            update={
                "context": t.context.model_copy(
                    update={
                        "mode": "offline_fake",
                        "versions": t.context.versions.model_copy(
                            update={"candidate": spec.candidate}
                        ),
                    }
                )
            }
        )
        for t in schedule.tasks
    )
    baseline_schedule = schedule.model_copy(update={"tasks": tasks})
    factory = OlistBaselineFactory(spec, fresh.route, selected, tmp_path / "unused")
    root = tmp_path / "baseline"
    evidence = record_olist_baseline(
        baseline_schedule,
        loaded,
        factory,
        OlistEnvironment(server, parent.workspace_key, loaded),
        root,
        candidate_sha256=pin(spec),
        source_root=ROOT,
    )
    verified = read_olist_baseline(
        root, loaded, route=fresh.route, evidence_sha256=pin(evidence), candidate_sha256=pin(spec)
    )
    assert verified.batch.complete and not (root / "receipts").exists()
    for row in verified.batch.rows:
        assert not row.errors and row.report.report.result.usage.model_calls == 0
        scores = {s.metric: s.value for s in row.report.report.scores}
        assert scores["duplicate_delivery"] == 1 and scores["olist_safe"] == 1
        assert scores["olist_correct"] == (0 if selected == "always-review" else 1)
        with server.connect() as admin:
            assert not admin.execute(
                "SELECT 1 FROM pg_database WHERE datname=%s",
                (row.state_ref.removeprefix("olist-h10:"),),
            ).fetchone()
    if kind == "rules":
        from dataclasses import replace

        fresh = replace(fresh, transport=InventedIntent())
        candidate_root = tmp_path / "candidate"
        candidate = record_olist(
            schedule,
            loaded,
            fresh,
            OlistEnvironment(server, parent.workspace_key, loaded),
            candidate_root,
            candidate_sha256=pin(fresh.candidate),
            source_root=ROOT,
        )
        profile = StandardProfile(
            version="invented",
            agent="olist",
            required_fields=FIELDS,
            required_holdout_slices=("eligible_refund",),
        )
        protocol = StandardProtocol(
            version="invented",
            profile_sha256=pin(profile),
            dataset_sha256=loaded.pin.sha256,
            scorer_sha256=fresh.candidate.scorer_sha256,
            baseline_sha256=pin(evidence),
            frozen_at=tasks[0].context.clock,
            trials_per_case=3,
        )
        entry = loaded.manifest.entries[0]
        cases = (
            StandardCase(
                case_id=label.input.case_id,
                source_kind=label.source_kind,
                split=label.split,
                independence_keys=(entry.group_id,),
                language_family="invented-template-aware",
                slices=("eligible_refund",),
                input_text=entry.case.input.request,
                eligible_for_autonomy=True,
                required_review=False,
                critical=True,
            ),
        )
        study = assemble_olist_study(
            profile,
            protocol,
            cases,
            loaded,
            baseline_root=root,
            baseline_evidence_sha256=pin(evidence),
            baseline_candidate_sha256=pin(spec),
            candidate_root=candidate_root,
            candidate_evidence_sha256=pin(candidate),
            candidate_sha256=pin(fresh.candidate),
            required_case_ids=loaded.manifest.case_ids,
            baseline_route=fresh.route,
        )
        assert all(r.baseline_correct and r.correct and r.model_calls == 1 for r in study.rows)
        assert not audit_study(profile, protocol, study, now=candidate.finished_at)[
            "release_allowed"
        ]
    path = next((root / "observations").glob("*.json"))
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError):
        read_olist_baseline(
            root,
            loaded,
            route=fresh.route,
            evidence_sha256=pin(evidence),
            candidate_sha256=pin(spec),
        )
