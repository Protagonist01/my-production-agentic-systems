"""Offline boundaries for generated local state and command dispatch."""

import json
import shutil

import pytest
from agent_harness.local_services import Workspace, main
from agent_harness.postgres import Server, Trial, trial_name


def test_copied_configuration_cannot_attach_to_another_checkout(tmp_path):
    first = Workspace(tmp_path / "first checkout")
    second = Workspace(tmp_path / "second checkout")
    first.config(initialize=True)
    second.local.mkdir(parents=True)
    shutil.copyfile(first.local / "instance.json", second.local / "instance.json")
    with pytest.raises(ValueError, match="another checkout"):
        second.config()


def test_local_state_init_does_not_rotate_existing_credentials(tmp_path):
    workspace = Workspace(tmp_path)
    original = workspace.config(initialize=True)
    assert workspace.config(initialize=True) == original
    assert workspace.key != Workspace(tmp_path / "different").key


def test_missing_docker_is_an_error_not_a_skipped_check(monkeypatch, tmp_path):
    workspace = Workspace(tmp_path)
    workspace.config(initialize=True)
    monkeypatch.setattr(shutil, "which", lambda name: None)
    with pytest.raises(ValueError, match="Docker is unavailable"):
        workspace.compose("up")


def test_destroy_requires_exact_workspace_before_dispatch(monkeypatch, tmp_path):
    def unexpected(*args, **kwargs):
        raise AssertionError("Wrong identity reached lifecycle action")

    monkeypatch.setattr(Workspace, "down", unexpected)
    with pytest.raises(SystemExit) as error:
        main(["destroy", "--root", str(tmp_path), "--confirm-workspace", "another-project"])
    assert error.value.code == 2


@pytest.mark.parametrize("trial_id", ["", " ", "x" * 257])
def test_invalid_trial_identity_is_rejected_before_database_access(trial_id):
    with pytest.raises(ValueError):
        trial_name("0" * 16, trial_id)


def test_trial_input_cannot_become_a_sql_identifier_or_file_path(tmp_path):
    trial = Trial(Workspace(tmp_path).key, "../../escape'; DROP DATABASE postgres; --", "secret")
    assert len(trial.name) < 63 and all(c.isalnum() or c == "_" for c in trial.name)
    assert Workspace(tmp_path).trial_path(trial.trial_id).parent == tmp_path / ".agent-local/trials"
    assert "secret" not in repr(trial)
    assert "secret" not in repr(Server(5432, "secret"))


def test_trial_credentials_cannot_be_relabelled(tmp_path):
    workspace = Workspace(tmp_path)
    path = workspace.trial_path("case-a")
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps({"workspace_key": workspace.key, "trial_id": "case-b", "password": "x" * 64})
    )
    with pytest.raises(ValueError, match="identity mismatch"):
        workspace.load_trial("case-a")
