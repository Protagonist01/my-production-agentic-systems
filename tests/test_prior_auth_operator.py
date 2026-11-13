"""Auth-before-source access, bounded private inputs, closed output and exposed regressions."""

import argparse
import json
import sys
from pathlib import Path

import pytest
from prior_auth.assessment import CRITERIA, assess
from prior_auth.contracts import digest
from test_prior_auth_review import actor, note, policy

import prior_auth_operator as operator
from prior_auth_intake_readback import IntakeReader
from prior_auth_operator_comparison import readback, run
from prior_auth_operator_rules import conflict_rules
from prior_auth_profiling import Profiler
from prior_auth_scorecards import rules


@pytest.mark.parametrize(
    "text",
    [
        "AHI: 18 events/hour. AHI: 2 events/hour.",
        "AHI: 18 events/hour.\nAHI: 2 events/hour.",
        "AHI = 18 events/h. RDI: 14.5 events/hour.",
    ],
)
def test_conflicting_explicit_rates_abstain_without_changing_original_rules(text):
    value = note(text=text)
    original = rules(value, policy())
    assert assess(value, policy(), original).disposition == "request_information"
    assert conflict_rules(value, policy()) is None
    assert (
        assess(value, policy(), conflict_rules(value, policy())).disposition == "qualified_review"
    )
    assert original == rules(value, policy())


@pytest.mark.parametrize(
    "text",
    [
        "AHI: 18 events/hour. AHI: 18.0 events/h.",
        "AHI: 18 events/hour. RDI: 18 events/hour.",
        "No supporting clinical evidence.",
    ],
)
def test_equal_rates_and_absence_preserve_baseline_behavior(text):
    value = note(text=text)
    assert conflict_rules(value, policy()) == rules(value, policy())
    selected = conflict_rules(value, policy(), ("severity",))
    assert [c.criterion_id for c in selected.claims] == ["severity"]


def test_variant_does_not_claim_broader_grammar_or_noninvented_qualification():
    value = note(text="AHI: 18 events/hour. AHI: 2 events/day.")
    assert conflict_rules(value, policy()) == rules(value, policy())
    assert (
        conflict_rules(value.model_copy(update={"provenance": "published_illustrative"}), policy())
        is None
    )
    assert conflict_rules(value.model_copy(update={"policy_sha256": "a" * 64}), policy()) is None
    with pytest.raises(ValueError):
        conflict_rules(value, policy(), ("severity", "severity"))


def test_failed_auth_never_opens_a_request_or_source(monkeypatch):
    calls = []

    class BadAuth:
        def login(self, *args):
            raise PermissionError("private-login-canary")

        def logout(self, token):
            calls.append("logout")

    monkeypatch.setattr(operator.getpass, "getpass", lambda _: "private-password")
    monkeypatch.setattr(operator, "bounded_private", lambda *args: calls.append("file"))
    with pytest.raises(PermissionError):
        operator.authenticated(
            argparse.Namespace(username="unknown", command="import"),
            lambda: calls.append("connect"),
            BadAuth(),
            Profiler(),
        )
    assert not calls


def test_manifest_scope_checked_before_source_read_and_viewer_cannot_import(tmp_path, monkeypatch):
    operator.draft_demo(tmp_path / "draft")
    request_path = tmp_path / "draft/request.json"
    missing_source = tmp_path / "must-not-open.txt"
    for user in (
        actor("other"),
        actor("demo-case", role="viewer"),
        actor("demo-case").model_copy(update={"tenant_id": "other"}),
    ):
        with pytest.raises(PermissionError):
            operator.import_document(user, None, request_path, missing_source, Profiler())


def test_authenticated_import_failure_still_logs_out(monkeypatch):
    calls = []

    class LoggedIn:
        def login(self, *args):
            return "private-token", "private-csrf", actor("demo-case")

        def logout(self, token):
            calls.append(token)

    def fail(*args):
        raise ValueError("private-import-canary")

    monkeypatch.setattr(operator.getpass, "getpass", lambda _: "private-password")
    monkeypatch.setattr(operator, "import_document", fail)
    args = argparse.Namespace(
        command="import", username="reviewer", request=None, source=None, native_tools=None
    )
    with pytest.raises(ValueError):
        operator.authenticated(args, lambda: None, LoggedIn(), Profiler())
    assert calls == ["private-token"]


def test_private_input_size_and_git_guards_prevent_unbounded_read(tmp_path):
    source = tmp_path / "input"
    source.write_bytes(b"abcdef")
    assert operator.bounded_private(source, 6) == b"abcdef"
    with pytest.raises(ValueError):
        operator.bounded_private(source, 5)
    with pytest.raises(ValueError, match="outside Git"):
        operator.bounded_private(Path(__file__), 100_000)


def test_demo_is_exclusive_and_contains_only_invented_setup(tmp_path):
    target = tmp_path / "demo"
    assert operator.draft_demo(target)["provider_attempts"] == 0
    request = operator.ImportRequest.model_validate_json((target / "request.json").read_bytes())
    assert request.provenance == "invented"
    assert request.source_sha256 == digest((target / "source.txt").read_text())
    with pytest.raises(FileExistsError):
        operator.draft_demo(target)


def test_readback_authorization_precedes_database_access():
    def forbidden():
        raise AssertionError("database must not be touched")

    reader = IntakeReader(forbidden)
    with pytest.raises(PermissionError):
        reader.receipt(actor("case"), "other", "doc")
    with pytest.raises(PermissionError):
        reader.locate(actor("case"), "other", "doc", note_sha256="a" * 64, start=0, end=1)


def test_provider_flag_rejected_without_initializing_workspace(monkeypatch, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        ["prior_auth_operator.py", "--root", ".", "--trial", "demo", "worker", "--live-gemini"],
    )
    monkeypatch.setattr(operator, "Workspace", lambda *args: pytest.fail("workspace initialized"))
    with pytest.raises(SystemExit) as error:
        operator.main()
    assert error.value.code == 2
    assert not capsys.readouterr().out


def test_credential_error_output_does_not_echo_canaries(monkeypatch, capsys):
    class BrokenWorkspace:
        def load_trial(self, trial):
            raise ValueError("private-config-canary")

    monkeypatch.setattr(
        sys, "argv", ["prior_auth_operator.py", "--root", ".", "--trial", "demo", "worker"]
    )
    monkeypatch.setattr(operator, "Workspace", lambda *args: BrokenWorkspace())
    with pytest.raises(SystemExit):
        operator.main()
    captured = capsys.readouterr()
    assert not captured.out and "private-config-canary" not in captured.err
    assert "ValueError" in captured.err


def test_comparison_preserves_unknown_references_and_detects_tampering(tmp_path):
    directory = tmp_path / "comparison"
    report = run(directory)
    assert readback(directory)["observations"] == 6
    assert report["comparators"]["rules"]["overall"]["route_agreement"]["numerator"] == 0
    assert report["comparators"]["conflict_rules"]["overall"]["route_agreement"]["numerator"] == 2
    for name in ("always_review", "rules", "conflict_rules"):
        overall = report["comparators"][name]["overall"]
        assert overall["missing_criterion_references"] == 2 * len(CRITERIA)
        assert overall["criterion_agreement"]["rate"] is None
    with pytest.raises(FileExistsError):
        run(directory)
    rows = json.loads((directory / "conflict_rules.json").read_text())
    rows[0]["model_calls"] = 1
    (directory / "conflict_rules.json").write_text(json.dumps(rows))
    with pytest.raises(ValueError, match="pin differs"):
        readback(directory)
