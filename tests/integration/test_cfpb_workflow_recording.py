"""Invented full triage publication, actual disposable Postgres, no provider calls."""

from dataclasses import replace

import pytest
from agent_harness.cases import LoadedManifest, ManifestPin
from agent_harness.domain_recording import scorer_pin
from agent_harness.release_contracts import pin, sha256
from cfpb_triage.workflow_recording import (
    ENVIRONMENT,
    FIXTURE,
    CfpbEnvironment,
    CfpbWorkflowFactory,
    PublicationObservation,
    import_provenance,
    publication_fields,
    read_workflow,
    record_workflow,
)
from domain_recording_fixtures import ROOT, composition
from test_cfpb_desk_state import app as app


def workflow_inputs(*, fail=False):
    old_loaded, schedule, old = composition("cfpb", fail=fail)
    adapter = replace(old.adapter, version="cfpb-durable-h10-v1")
    manifest = adapter.manifest_for(
        tuple(old.adapter.reference(e.case) for e in old_loaded.manifest.entries)
    )
    raw = manifest.canonical_json().encode()
    loaded = LoadedManifest(
        raw,
        ManifestPin(manifest_id=manifest.manifest_id, version=manifest.version, sha256=sha256(raw)),
    )
    spec = old.candidate.model_copy(
        update={
            "environment_sha256": sha256((ENVIRONMENT + FIXTURE).encode()),
            "scorer_sha256": scorer_pin(adapter, old.candidate.source_files),
        }
    )
    schedule = schedule.model_copy(
        update={
            "manifest": loaded.pin,
            "environment_version": ENVIRONMENT,
            "state_fixture": FIXTURE,
        }
    )
    factory = CfpbWorkflowFactory(spec, loaded, adapter, ROOT / "unused", "mock", old.transport)
    return loaded, schedule, factory


@pytest.mark.parametrize("fail", [False, True])
def test_durable_triage_recomputes_publication_privacy_and_receipts_after_database_cleanup(
    app, tmp_path, fail
):
    server, parent, _, _, _ = app
    loaded, schedule, factory = workflow_inputs(fail=fail)
    environment = CfpbEnvironment(server, parent.workspace_key, loaded, factory.adapter)
    root = tmp_path / "recording"
    manifest = record_workflow(
        schedule,
        loaded,
        factory,
        environment,
        root,
        candidate_sha256=pin(factory.candidate),
        source_root=ROOT,
    )
    verified = read_workflow(
        root,
        loaded,
        factory.adapter,
        evidence_sha256=pin(manifest),
        candidate_sha256=pin(factory.candidate),
    )
    assert manifest.origin == "mock" and len(verified.receipts) == 3
    assert len(verified.batch.rows) == 3
    for row in verified.batch.rows:
        assert not row.errors
        fields = {s.metric: s for s in row.report.report.scores}
        assert fields["privacy"].value == fields["review_durability"].value == 1
        assert fields["cfpb_correct"].value == (0 if fail else 1)
        saved = PublicationObservation.model_validate_json(
            (root / "observations" / (pin(row.task.context) + ".json")).read_bytes()
        )
        case = loaded.entry(row.task.context.case_id).case
        assert not publication_fields(
            factory.adapter,
            case,
            row.task.context,
            saved.model_copy(update={"scope_denied": False}),
        )["privacy"]
        assert not publication_fields(
            factory.adapter,
            case,
            row.task.context,
            saved.model_copy(update={"duplicate_rejected": False}),
        )["review_durability"]
        with pytest.raises(ValueError, match="content pins"):
            publication_fields(
                factory.adapter,
                case,
                row.task.context,
                saved.model_copy(update={"persisted": {**saved.persisted, "result": None}}),
            )
    sidecar = next((root / "observations").glob("*.json"))
    saved = PublicationObservation.model_validate_json(sidecar.read_bytes())
    sidecar.write_text(
        saved.model_copy(update={"provider_requests": ()}).canonical_json(), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="dispatch receipts"):
        read_workflow(
            root,
            loaded,
            factory.adapter,
            evidence_sha256=pin(manifest),
            candidate_sha256=pin(factory.candidate),
        )


def test_workflow_mock_cannot_acquire_provider_origin_or_changed_recipe():
    _, _, factory = workflow_inputs()
    factory.validate()
    with pytest.raises(ValueError, match="shared allowance"):
        replace(factory, origin="provider").validate()
    with pytest.raises(ValueError, match="recipe"):
        replace(factory, mock=replace(factory.mock, content="changed")).validate()


def test_published_and_edited_inputs_cannot_invent_a_masking_review():
    loaded, _, factory = workflow_inputs()
    ref = factory.adapter.reference(loaded.manifest.entries[0].case)
    for source, expected in (("original", "original"), ("hybrid", "edited")):
        published = ref.model_copy(update={"source_kind": source})
        with pytest.raises(ValueError, match="actual masking review"):
            import_provenance(published)
        assert import_provenance(
            published.model_copy(update={"masking_review_ref": "invented-test-review"})
        ) == ("invented-test-review", expected)
