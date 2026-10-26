"""Gate branches only, invented DTOs: never actual provider or reviewer evidence."""

import pytest
from agent_harness.baseline_recording import BaselineManifest, VerifiedBaseline
from agent_harness.release_contracts import DeterministicBaselineApproval, pin
from release_fixtures import logical_pair
from test_release_gates import change_result, decide


@pytest.fixture(scope="module")
def pair(tmp_path_factory):
    loaded, old, new, policy, approval = logical_pair(
        tmp_path_factory.mktemp("deterministic-release")
    )
    manifest = BaselineManifest(
        execution_id=old.manifest.execution_id,
        algorithm="invented-rules-v1",
        candidate=old.manifest.candidate,
        started_at=old.manifest.started_at,
        finished_at=old.manifest.finished_at,
        batch_sha256=pin(old.batch),
    )
    baseline = VerifiedBaseline(manifest, old.batch)
    approval = DeterministicBaselineApproval(
        **approval.model_dump(),
        algorithm=manifest.algorithm,
        dataset_sha256=loaded.pin.sha256,
        baseline_spec_sha256=pin(manifest.candidate),
    ).model_copy(update={"baseline_sha256": pin(manifest)})
    return loaded, baseline, new, policy, approval


def test_distinct_deterministic_approval_retains_fresh_candidate_and_regression_requirements(pair):
    assert decide(pair).allowed
    regressed = decide(pair, candidate=change_result(pair[2], "fail"))
    assert not regressed.allowed and regressed.regressed_cases == pair[0].manifest.case_ids


@pytest.mark.parametrize("field", ["algorithm", "dataset_sha256", "baseline_spec_sha256"])
def test_wrong_algorithm_population_or_source_approval_rejected(pair, field):
    approval = pair[4].model_copy(update={field: "b" * 64})
    with pytest.raises(ValueError):
        decide(pair, approval=approval, approval_sha256=pin(approval))


def test_provider_approval_cannot_implicitly_promote_deterministic_evidence(pair):
    from agent_harness.release_contracts import BaselineApproval

    approval = BaselineApproval.model_validate(
        {k: v for k, v in pair[4].model_dump().items() if k in BaselineApproval.model_fields}
    )
    with pytest.raises(ValueError):
        decide(pair, approval=approval, approval_sha256=pin(approval))
