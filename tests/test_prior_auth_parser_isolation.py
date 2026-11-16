"""Closed isolated-parser configuration, parent validation and scoped entrypoint."""

import io
import json
from pathlib import Path

import pytest

from prior_auth_demo import demo_request
from prior_auth_documents import DocumentError, normalize
from prior_auth_parser_isolation import command, normalize_isolated
from prior_auth_pipeline import prepare
from prior_auth_profiling import Profiler


def test_container_has_no_host_mounts_secrets_network_or_privilege(monkeypatch):
    monkeypatch.setattr("prior_auth_parser_isolation.shutil.which", lambda _: "docker")
    args = command("sha256:" + "a" * 64, "pa-parser-" + "b" * 24)
    for flag in (
        "--network=none",
        "--read-only",
        "--user=65532:65532",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges=true",
        "--pids-limit=32",
        "--memory=512m",
        "--memory-swap=512m",
        "--cpus=1",
        "--pull=never",
        "--log-driver=none",
    ):
        assert flag in args
    assert not any(
        x.startswith(("--mount", "--volume", "--privileged", "--env-file", "--publish"))
        for x in args
    )
    assert args[-1] == "sha256:" + "a" * 64
    for image in ("python:latest", "sha256:foo", "sha256:" + "a" * 64 + " --privileged"):
        with pytest.raises(ValueError):
            command(image, "pa-parser-" + "b" * 24)


def test_operator_pipeline_checks_source_and_normalized_identity():
    raw = b"AHI: 18 events/hour."
    request = demo_request(raw)
    calls = []

    def isolated(data, format):
        calls.append((data, format))
        return normalize(data, format)

    assert prepare(raw, request, Profiler(), normalizer=isolated).decision.admitted
    assert calls == [(raw, "text")]
    with pytest.raises(ValueError):
        prepare(b"changed", request, Profiler(), normalizer=isolated)
    assert len(calls) == 1


@pytest.mark.parametrize("data,seconds", [(b"", 60), (b"a", 0), (b"a", 121)])
def test_invalid_input_refuses_before_docker(data, seconds):
    with pytest.raises(DocumentError):
        normalize_isolated(data, "text", image_id="sha256:" + "a" * 64, timeout_seconds=seconds)


def test_worker_is_closed_and_does_not_echo_parser_errors(monkeypatch, capsys):
    import prior_auth_parser_worker as worker

    class Input:
        buffer = io.BytesIO(
            json.dumps({"format": "text", "data": "!!!", "extra": "private"}).encode()
        )

    monkeypatch.setattr(worker.sys, "stdin", Input())
    worker.main()
    value = capsys.readouterr()
    assert json.loads(value.out) == {"error": "isolated_parser_failed"}
    assert "private" not in value.out + value.err


def test_minimal_image_build_uses_only_reviewed_source_files():
    dockerfile = Path("containers/prior-auth-parser/Dockerfile").read_text()
    assert "--require-hashes" in dockerfile and "USER 65532:65532" in dockerfile
    assert "COPY . " not in dockerfile and "sha256:" in dockerfile
