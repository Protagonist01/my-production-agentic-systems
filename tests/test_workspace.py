"""Verify installed packages and declared dependency boundaries."""

import importlib
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MEMBERS = {
    "harness": "agent_harness",
    "projects/olist-support": "olist_support",
    "projects/cfpb-triage": "cfpb_triage",
    "projects/revenue-integrity": "revenue_integrity",
    "projects/prior-auth": "prior_auth",
    "projects/supply-chain-disruption": "supply_chain",
}


@pytest.mark.parametrize("member,module", MEMBERS.items())
def test_package_import_resolves_to_installed_source(member: str, module: str) -> None:
    package = importlib.import_module(module)
    assert Path(package.__file__).resolve() == ROOT / member / "src" / module / "__init__.py"


def test_distribution_dependencies_follow_architecture() -> None:
    for member in MEMBERS:
        config = tomllib.loads((ROOT / member / "pyproject.toml").read_text(encoding="utf-8"))
        dependencies = config["project"]["dependencies"]
        assert dependencies == (
            ["pydantic==2.14.1"] if member == "harness" else ["production-agent-harness"]
        )
