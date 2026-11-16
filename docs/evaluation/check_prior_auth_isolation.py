"""Actual restricted container: PDF/OCR, root/network denial and parent deadline."""

import argparse
import json
import secrets
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from docs.evaluation.check_prior_auth_native import text_pdf  # noqa: E402
from prior_auth_documents import DocumentError  # noqa: E402
from prior_auth_parser_isolation import command, normalize_isolated  # noqa: E402


def run(image: str) -> None:
    raw = text_pdf()
    text = normalize_isolated(raw, "pdf_text", image_id=image)
    assert "AHI: 18 events/hour." in text.text and text.regions[0].bbox
    ocr = normalize_isolated(raw, "pdf_ocr", image_id=image)
    assert "AHI:" in ocr.text and ocr.extraction_review_required and ocr.regions[0].bbox
    name = "pa-parser-" + secrets.token_hex(12)
    args = command(image, name)
    probe = """import os,socket,json
from pathlib import Path
denied=False
try: Path('/root-write-probe').write_text('invented')
except OSError: denied=True
network=False
try:
 s=socket.create_connection(('1.1.1.1',443),timeout=1);s.close();network=True
except OSError: pass
status=Path('/proc/self/status').read_text()
assert os.getuid()==65532 and denied and not network
assert 'NoNewPrivs:\\t1' in status and 'Seccomp:\\t2' in status
assert 'CapEff:\\t0000000000000000' in status
assert Path('/sys/fs/cgroup/memory.max').read_text().strip()=='536870912'
assert Path('/sys/fs/cgroup/pids.max').read_text().strip()=='32'
assert not Path('/var/run/docker.sock').exists() and not Path('/app/.env.local').exists()
assert not any(k.endswith('API_KEY') for k in os.environ)
print(json.dumps({'non_root':True,'root_write_denied':True,'network_denied':True,'seccomp':True,'capabilities_empty':True,'resource_limits':True}))
"""
    result = subprocess.run(
        args[:-1] + ["--entrypoint=python", image, "-c", probe],
        input=b"",
        capture_output=True,
        timeout=20,
        check=True,
    )
    assert json.loads(result.stdout)["network_denied"]
    timed = []

    def sleeping(image_id, name):
        timed.append(name)
        original = command(image_id, name)
        return original[:-1] + ["--entrypoint=python", image_id, "-c", "import time;time.sleep(30)"]

    with patch("prior_auth_parser_isolation.command", sleeping):
        try:
            normalize_isolated(b"invented", "text", image_id=image, timeout_seconds=1)
        except DocumentError as error:
            assert str(error) == "isolated_parser_resource_limit"
        else:
            raise AssertionError("parent deadline not enforced")
    # rm --force must have removed that exact owned container after client death.
    found = subprocess.run(
        [args[0], "ps", "--all", "--filter", "name=" + timed[0], "--format", "{{.Names}}"],
        capture_output=True,
        text=True,
        timeout=15,
        check=True,
    )
    assert not found.stdout.strip()
    print(
        "Restricted PA parser: PDF/OCR, source regions, network/root-write denial, "
        "non-root, seccomp, resource limits and deadline cleanup passed"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image-file", type=Path, required=True)
    args = parser.parse_args()
    run(args.image_file.read_text().strip())
