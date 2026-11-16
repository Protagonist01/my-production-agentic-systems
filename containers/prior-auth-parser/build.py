"""Prepare a minimal image context from the current exact source and uv lock."""

import argparse
import shutil
import subprocess
import tomllib
from pathlib import Path


def build(root: Path, directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=False)
    lock = tomllib.loads((root / "uv.lock").read_text(encoding="utf-8"))
    names = {
        "pydantic",
        "pydantic-core",
        "annotated-types",
        "typing-extensions",
        "typing-inspection",
    }
    packages = {p["name"]: p for p in lock["package"] if p["name"] in names}
    if set(packages) != names:
        raise ValueError("pinned parser dependencies missing")
    requirements = []
    for name, p in sorted(packages.items()):
        hashes = sorted({w["hash"] for w in p["wheels"]})
        requirements.append(
            name + "==" + p["version"] + " \\\n" + " \\\n".join("    --hash=" + h for h in hashes)
        )
    (directory / "requirements.txt").write_text("\n".join(requirements) + "\n", encoding="utf-8")
    shutil.copyfile(root / "containers/prior-auth-parser/Dockerfile", directory / "Dockerfile")
    for package, source in [
        ("agent_harness", root / "harness/src/agent_harness"),
        ("prior_auth", root / "projects/prior-auth/src/prior_auth"),
    ]:
        (directory / package).mkdir()
        for name in ("__init__.py", "contracts.py"):
            shutil.copyfile(source / name, directory / package / name)
    for name in (
        "prior_auth_documents.py",
        "prior_auth_profiling.py",
        "prior_auth_parser_worker.py",
    ):
        shutil.copyfile(root / name, directory / name)
    docker = shutil.which("docker")
    if not docker:
        raise ValueError("Docker required")
    subprocess.run(
        [docker, "build", "--iidfile", str(directory / "image-id.txt"), str(directory)], check=True
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--context", type=Path, required=True)
    args = parser.parse_args()
    build(Path(__file__).resolve().parents[2], args.context.resolve())
