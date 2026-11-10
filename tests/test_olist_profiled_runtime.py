import json
from contextlib import contextmanager

import pytest

from olist_profiled_runtime import Finalize, ProfileTelemetry, prepare_evaluation
from olist_profiling import Recorder


def test_profile_finalized_only_after_work_finishes_and_private_flush(tmp_path):
    r = Recorder()
    path = tmp_path / "profile.json"
    telemetry = ProfileTelemetry(
        r, code_revision="invented", environment_lock="a" * 64, output=path
    )
    telemetry.open()
    with r.phase("sql_execute"):
        assert not telemetry.snapshot()["stage_profile"]["finalized"]
    telemetry.close()
    result = json.loads(path.read_bytes())
    assert result["shutdown_finished"]
    assert result["stage_profile"]["finalized"]
    assert result["stage_profile"]["stages"]["sql_execute"]["observations"] == 1
    assert result["profile_scope"] == "operator_console_no_model_transport"
    assert not result["stage_profile"]["all_subprocesses_instrumented"]
    with pytest.raises(ValueError, match="single-use"):
        telemetry.open()


def test_timed_finalization_preserves_exception_suppression_and_rollback_failure():
    @contextmanager
    def suppress():
        try:
            yield "transaction"
        except LookupError:
            pass

    r = Recorder()
    with Finalize(suppress(), r):
        raise LookupError("SECRET")

    @contextmanager
    def failing():
        yield "transaction"
        raise RuntimeError("SECRET rollback")

    with pytest.raises(RuntimeError), Finalize(failing(), r):
        pass
    assert r.snapshot()["stages"]["sql_finalize"]["failures"] == 1
    assert "SECRET" not in json.dumps(r.snapshot())


def test_preparation_separates_proposals_from_input_and_does_not_create_results(tmp_path):
    import hashlib

    output = tmp_path / "packet"
    hashes = prepare_evaluation(output)
    assert all(
        hashlib.sha256((output / name).read_bytes()).hexdigest() == value
        for name, value in hashes.items()
    )
    inputs = json.loads((output / "inputs.json").read_bytes())
    assert len(inputs) == 24 and all(set(c) == {"case_id", "group", "text"} for c in inputs)
    review = json.loads((output / "review.json").read_bytes())
    assert all(r["decision"] == "unreviewed" and r["independent_evidence"] is None for r in review)
    report = json.loads((output / "empty-report.json").read_bytes())
    assert all(v["overall"]["missing"] == 72 for v in report["variants"].values())
    scope = json.loads((output / "scope.json").read_bytes())
    assert not scope["provider_calls_authorized"] and not scope["qualification_accepted"]
    with pytest.raises(FileExistsError):
        prepare_evaluation(output)
    gitroot = tmp_path / "checkout"
    gitroot.mkdir()
    (gitroot / ".git").mkdir()
    with pytest.raises(ValueError, match="outside"):
        prepare_evaluation(gitroot / "bad")
