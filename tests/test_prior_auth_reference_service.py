"""Owned container command and refusal boundaries, no daemon/network effects."""

import json
from pathlib import Path

import pytest

import prior_auth_reference_service as service

IMAGE = "sha256:" + "a" * 64


def test_local_reference_command_has_no_host_mount_credentials_or_public_port(tmp_path):
    args = service.command(tmp_path, IMAGE, 8081)
    assert args[-1] == IMAGE
    assert args[args.index("--publish") + 1] == "127.0.0.1:8081:8081"
    assert "--pull=never" in args and "--cap-drop=ALL" in args
    assert "--memory=2560m" in args and "--pids-limit=256" in args
    assert "--restart=no" in args
    assert not any(a.startswith(("--mount", "--volume", "--env")) for a in args)
    for image, port in (("maven:latest", 8081), (IMAGE, 80)):
        with pytest.raises(ValueError):
            service.command(tmp_path, image, port)


def test_wrong_image_provenance_cannot_start_container(tmp_path, monkeypatch):
    calls = []

    def fake(args, **kwargs):
        calls.append(args)
        return json.dumps([{"Id": IMAGE, "Config": {"Labels": {}}}])

    monkeypatch.setattr(service, "docker", fake)
    with pytest.raises(PermissionError):
        service.start(tmp_path, IMAGE)
    assert len(calls) == 1 and calls[0] == ["image", "inspect", IMAGE]


def test_existing_container_with_public_binding_cannot_be_adopted(tmp_path, monkeypatch):
    calls = []

    def fake(args, **kwargs):
        calls.append(args)
        if args[:2] == ["image", "inspect"]:
            return json.dumps(
                [
                    {
                        "Id": IMAGE,
                        "Config": {
                            "Labels": {"org.opencontainers.image.revision": service.RI_COMMIT}
                        },
                    }
                ]
            )
        if args[0] == "ps":
            return "invented-owned-container"
        return json.dumps(
            [
                {
                    "Image": IMAGE,
                    "Config": {
                        "Labels": {
                            "pa.workspace": service.workspace_key(tmp_path),
                            "pa.role": "prior-auth-reference-payer",
                        }
                    },
                    "HostConfig": {
                        "PortBindings": {"8081/tcp": [{"HostIp": "0.0.0.0", "HostPort": "8081"}]}
                    },
                }
            ]
        )

    monkeypatch.setattr(service, "docker", fake)
    with pytest.raises(PermissionError):
        service.start(tmp_path, IMAGE)
    assert all(args[0] not in {"run", "start", "stop", "rm"} for args in calls)


def test_containerfile_uses_resolved_base_and_preserves_official_source_identity():
    text = (
        Path(__file__).resolve().parents[1] / "containers/prior-auth-reference-payer/Dockerfile"
    ).read_text()
    assert text.count("maven@sha256:") == 2
    assert service.RI_COMMIT in text and "COPY LICENSE" in text
    assert "USER 65532:65532" in text and 'MAVEN_OPTS="-Xmx1024m"' in text
