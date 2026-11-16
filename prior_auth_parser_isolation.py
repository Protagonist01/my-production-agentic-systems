"""Opt-in fixed-image, no-mount, network-disabled Docker document normalization."""

import base64
import hashlib
import json
import re
import secrets
import shutil
import subprocess
import tempfile
import time

from prior_auth_documents import MAX_BYTES, Document, DocumentError, Format


def command(image_id: str, name: str) -> list[str]:
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", image_id) or not re.fullmatch(
        r"pa-parser-[a-f0-9]{24}", name
    ):
        raise ValueError("exact local image digest and owned job name required")
    docker = shutil.which("docker")
    if docker is None:
        raise DocumentError("isolated_parser_unavailable")
    return [
        docker,
        "run",
        "--name",
        name,
        "--pull=never",
        "--rm",
        "--interactive",
        "--network=none",
        "--read-only",
        "--user=65532:65532",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges=true",
        "--pids-limit=32",
        "--memory=512m",
        "--memory-swap=512m",
        "--cpus=1",
        "--ulimit=nofile=64:64",
        "--ulimit=fsize=33554432:33554432",
        "--log-driver=none",
        "--tmpfs=/tmp:rw,noexec,nosuid,nodev,size=64m,mode=1777",
        "--env=TMPDIR=/tmp",
        "--env=PYTHONDONTWRITEBYTECODE=1",
        "--env=OMP_THREAD_LIMIT=1",
        image_id,
    ]


def normalize_isolated(
    raw: bytes, format: Format, *, image_id: str, timeout_seconds: int = 60
) -> Document:
    if not raw or len(raw) > MAX_BYTES or not 1 <= timeout_seconds <= 120:
        raise DocumentError("isolated_parser_input_limit")
    if format not in {"text", "ccda", "fhir", "pdf_text", "pdf_ocr"}:
        raise DocumentError("isolated_parser_format")
    name = "pa-parser-" + secrets.token_hex(12)
    args = command(image_id, name)
    payload = json.dumps({"format": format, "data": base64.b64encode(raw).decode()}).encode()
    with (
        tempfile.TemporaryFile() as source,
        tempfile.TemporaryFile() as out,
        tempfile.TemporaryFile() as err,
    ):
        source.write(payload)
        source.seek(0)
        process = subprocess.Popen(args, stdin=source, stdout=out, stderr=err)
        deadline = time.monotonic() + timeout_seconds
        try:
            while process.poll() is None:
                if time.monotonic() > deadline or out.tell() > 4_000_000 or err.tell() > 100_000:
                    raise DocumentError("isolated_parser_resource_limit")
                time.sleep(0.02)
            out.seek(0)
            output = out.read(4_000_001)
            if process.returncode or len(output) > 4_000_000:
                raise DocumentError("isolated_parser_failed")
            try:
                value = json.loads(output)
                if isinstance(value, dict) and set(value) == {"error"}:
                    # Preserve the three intake safety classifications without
                    # accepting arbitrary child error text into logs/state.
                    if value["error"] in {"unsafe_xml", "active_narrative", "binary_text"}:
                        raise DocumentError(value["error"])
                    raise ValueError("normalization unavailable")
                if not isinstance(value, dict) or set(value) != {"document"}:
                    raise ValueError("normalization unavailable")
                result = Document.model_validate_json(json.dumps(value["document"]))
            except DocumentError:
                raise
            except (ValueError, TypeError):
                raise DocumentError("isolated_parser_failed") from None
            if result.source_sha256 != hashlib.sha256(raw).hexdigest() or result.format != format:
                raise DocumentError("isolated_parser_identity_differs")
            return result
        finally:
            # Killing the docker client alone need not kill its container. Remove
            # only this unique task-owned name; never touch another parser/service.
            if process.poll() is None:
                process.kill()
            process.wait(timeout=10)
            try:
                subprocess.run(
                    [args[0], "rm", "--force", name],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=15,
                    check=False,
                )
            except (OSError, subprocess.TimeoutExpired):
                pass  # Caller sees a failure; daemon loss may leave a stopped/unknown job.
