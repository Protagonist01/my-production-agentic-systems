"""Actual packaged reference image plus existing authenticated SQL/PAS witnesses."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from prior_auth_reference_service import docker, identity, start  # noqa: E402


def run(image_file: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    image, name = image_file.read_text().strip(), identity(root)
    if docker(["ps", "--all", "--filter", "name=^/" + name + "$", "--format", "{{.ID}}"]):
        raise PermissionError("new owned test container required")
    try:
        result = start(root, image)
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "tests/integration/test_prior_auth_payer_desk_state.py",
                "-k",
                "actual_reference_payer",
                "-o",
                "addopts=--strict-config --strict-markers",
            ],
            cwd=root,
            env=dict(os.environ, PRIOR_AUTH_REFERENCE_PAYER_URL=result["endpoint"]),
            check=True,
            timeout=600,
        )
        print(
            json.dumps(
                {
                    "packaged_reference_ready": True,
                    "actual_authenticated_SQL_PAS_witnesses": True,
                    "clinical_validation": False,
                    "commercial_payer": False,
                }
            )
        )
    finally:
        exists = docker(["ps", "--all", "--filter", "name=^/" + name + "$", "--format", "{{.ID}}"])
        if exists:
            value = json.loads(docker(["inspect", name]))[0]
            if value["Image"] != image or value["Config"]["Labels"].get("pa.role") != (
                "prior-auth-reference-payer"
            ):
                raise PermissionError("test cleanup ownership differs")
            docker(["stop", "--timeout", "20", name], timeout=45)
            docker(["rm", name])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image-file", type=Path, required=True)
    args = parser.parse_args()
    try:
        run(args.image_file)
    except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as error:
        print("Packaged reference check failed: " + type(error).__name__, file=sys.stderr)
        raise SystemExit(1) from None
