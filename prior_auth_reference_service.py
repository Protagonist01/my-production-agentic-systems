"""Owned local official reference payer; no model, credentials, remote host or reset."""

import argparse
import json
import re
import socket
import subprocess
import time
from pathlib import Path
from typing import Any

from agent_harness.local_services import workspace_key
from prior_auth.source_io import external

from prior_auth_pas import RI_COMMIT, Loopback, object_from


def docker(arguments: list[str], *, timeout: float = 30) -> str:
    result = subprocess.run(
        ["docker", *arguments], capture_output=True, text=True, timeout=timeout, check=False
    )
    if result.returncode:
        raise ValueError("reference Docker operation failed; inspect local daemon/build log")
    return result.stdout.strip()


def identity(root: Path) -> str:
    return "pa-" + workspace_key(root) + "-reference-payer"


def build(root: Path, repository: Path, image_file: Path) -> str:
    repository = repository.resolve(strict=True)
    image_file = external(image_file)
    if image_file.exists():
        raise FileExistsError("new image record required; preserve earlier build evidence")
    revision = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=repository, text=True, timeout=20
    ).strip()
    changed = subprocess.run(
        ["git", "diff", "--exit-code", "HEAD", "--", "server", "library", "LICENSE"],
        cwd=repository,
        capture_output=True,
        timeout=30,
        check=False,
    ).returncode
    untracked = subprocess.check_output(
        ["git", "ls-files", "--others", "--exclude-standard", "--", "server", "library"],
        cwd=repository,
        text=True,
        timeout=20,
    ).strip()
    if revision != RI_COMMIT or changed or untracked:
        raise PermissionError("unchanged pinned upstream server/library source required")
    with image_file.with_suffix(".build.log").open("x", encoding="utf-8") as log:
        result = subprocess.run(
            [
                "docker",
                "build",
                "--file",
                str(root / "containers/prior-auth-reference-payer/Dockerfile"),
                "--iidfile",
                str(image_file),
                str(repository),
            ],
            stdout=log,
            stderr=subprocess.STDOUT,
            timeout=1800,
            check=False,
        )
    if result.returncode:
        raise ValueError("reference build failed; retain and inspect its private build log")
    image = image_file.read_text().strip()
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", image):
        raise ValueError("invalid completed image record")
    return image


def command(root: Path, image: str, port: int) -> list[str]:
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", image) or not 1024 <= port <= 65535:
        raise ValueError("exact image ID and unprivileged loopback port required")
    return [
        "run",
        "--detach",
        "--pull=never",
        "--name",
        identity(root),
        "--label",
        "pa.workspace=" + workspace_key(root),
        "--label",
        "pa.role=prior-auth-reference-payer",
        "--publish",
        f"127.0.0.1:{port}:8081",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        "--memory=2560m",
        "--memory-swap=2560m",
        "--cpus=2",
        "--pids-limit=256",
        "--log-opt=max-size=10m",
        "--log-opt=max-file=2",
        "--restart=no",
        image,
    ]


def start(root: Path, image: str, *, port: int = 8081) -> dict[str, Any]:
    args = command(root, image, port)
    pin = json.loads(docker(["image", "inspect", image]))[0]
    if (
        pin["Id"] != image
        or pin["Config"].get("Labels", {}).get("org.opencontainers.image.revision") != RI_COMMIT
    ):
        raise PermissionError("built reference image provenance differs")
    name = identity(root)
    exists = docker(["ps", "--all", "--filter", "name=^/" + name + "$", "--format", "{{.ID}}"])
    if exists:
        current = json.loads(docker(["inspect", name]))[0]
        labels = current["Config"].get("Labels", {})
        ports = current["HostConfig"]["PortBindings"]
        if (
            current["Image"] != image
            or labels.get("pa.workspace") != workspace_key(root)
            or labels.get("pa.role") != "prior-auth-reference-payer"
            or ports != {"8081/tcp": [{"HostIp": "127.0.0.1", "HostPort": str(port)}]}
            or current["Mounts"]
            or current["HostConfig"]["NetworkMode"] not in {"default", "bridge"}
        ):
            raise PermissionError("existing container/image/loopback binding differs")
        if not current["State"]["Running"]:
            docker(["start", name], timeout=90)
    else:
        with socket.socket() as check:
            if check.connect_ex(("127.0.0.1", port)) == 0:
                raise PermissionError("reference port occupied by another service")
        docker(args, timeout=90)
    transport = Loopback(f"http://127.0.0.1:{port}/fhir", timeout=5)
    deadline = time.monotonic() + 480
    while time.monotonic() < deadline:
        current = json.loads(docker(["inspect", name]))[0]
        if not current["State"]["Running"]:
            raise RuntimeError(
                "reference payer exited; retain container and inspect its private log"
            )
        try:
            if object_from(transport("GET", "metadata", None)).get("resourceType") == (
                "CapabilityStatement"
            ):
                return {
                    "ready": True,
                    "endpoint": f"http://127.0.0.1:{port}/fhir",
                    "container": name,
                    "image_id": image,
                    "reference_commit": RI_COMMIT,
                    "clinical_validation": False,
                    "commercial_payer": False,
                    "reference_state_transient": True,
                }
        except (ValueError, OSError):
            pass
        time.sleep(2)
    raise TimeoutError("reference startup deadline; no automatic replacement or reset")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--image-file", type=Path, required=True)
    parser.add_argument("--build-repository", type=Path)
    parser.add_argument("--port", type=int, default=8081)
    args = parser.parse_args()
    try:
        result = (
            {"built_image": build(args.root.resolve(), args.build_repository, args.image_file)}
            if args.build_repository is not None
            else start(args.root.resolve(), args.image_file.read_text().strip(), port=args.port)
        )
        print(json.dumps(result))
    except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as error:
        print(
            json.dumps({"startup_failed": type(error).__name__, "detail": "private state retained"})
        )
        raise SystemExit(1) from None
