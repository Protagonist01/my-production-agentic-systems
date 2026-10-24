"""Source/configuration bindings for the reviewed Olist H10 composition."""

import inspect
import json
import platform
from pathlib import Path
from typing import Literal

import agent_harness
from agent_harness.contracts import ModelRequest
from agent_harness.gateway import ModelTransport
from agent_harness.release_contracts import CandidateSpec, pin, sha256

import olist_support
from olist_support.h10_environment import ENVIRONMENT_VERSION, FIXTURE

PREFIX = "projects/olist-support/src/olist_support/"
TOOLS = "no_model_business_tools;trusted_scoped_policy_and_store_v1"


def fingerprints(route: ModelRequest, sources: dict[str, str]) -> dict[str, str]:
    """Fingerprints to freeze/review before execution; not automatic approval."""
    from olist_support.h10_runtime import OlistScorer, observed_result

    oracle = {
        name: sources[PREFIX + name]
        for name in ("release.py", "field_evaluation.py", "h10_manifest.py", "h10_evidence.py")
    }
    oracle["h10_scorer"] = sha256(inspect.getsource(OlistScorer).encode())
    oracle["result_binding"] = sha256(inspect.getsource(observed_result).encode())
    environment = {
        "version": ENVIRONMENT_VERSION,
        "fixture": FIXTURE,
        "python": platform.python_version(),
        "platform": platform.system(),
        "lock": sources["uv.lock"],
        "fixture_code": sources[PREFIX + "h10_environment.py"],
        "sql": {name: value for name, value in sources.items() if name.endswith(".sql")},
    }
    return {
        "prompt_sha256": sources[PREFIX + "workflow.py"],
        "model_config_sha256": pin(route),
        "tools_sha256": sha256(
            json.dumps(
                {
                    "mode": TOOLS,
                    "sources": {
                        name: sources[PREFIX + name]
                        for name in ("business.py", "business_contracts.py", "workflow_postgres.py")
                    },
                },
                sort_keys=True,
            ).encode()
        ),
        "policy_sha256": sources[PREFIX + "policy.py"],
        "scorer_sha256": sha256(json.dumps(oracle, sort_keys=True).encode()),
        "environment_sha256": sha256(json.dumps(environment, sort_keys=True).encode()),
    }


def verify_runtime(candidate: CandidateSpec) -> None:
    """Executing wheel/editable resources must match the complete pinned inventory."""
    for prefix, package in (("harness/src/agent_harness/", agent_harness), (PREFIX, olist_support)):
        root = Path(str(package.__file__)).parent
        actual = {
            prefix + p.relative_to(root).as_posix(): sha256(p.read_bytes())
            for p in root.rglob("*")
            if p.is_file() and p.suffix in (".py", ".sql")
        }
        selected = {
            name: value for name, value in candidate.source_files.items() if name.startswith(prefix)
        }
        if selected != actual:
            raise ValueError("Olist H10 executing package differs from source inventory")
    if candidate.source_files.get("uv.lock") != candidate.environment_lock:
        raise ValueError("Olist H10 environment lock differs from pinned inventory")


def validate_composition(
    candidate: CandidateSpec,
    route: ModelRequest,
    transport: ModelTransport,
    origin: Literal["provider", "mock"],
) -> None:
    candidate = CandidateSpec.model_validate_json(candidate.canonical_json())
    route = ModelRequest.model_validate_json(route.canonical_json())
    if origin not in ("provider", "mock"):
        raise ValueError("Olist capture requires an explicit supported origin")
    verify_runtime(candidate)
    if any(
        getattr(candidate, name) != value
        for name, value in fingerprints(route, candidate.source_files).items()
    ):
        raise ValueError("Olist H10 behavior fingerprint differs from composition")
    if candidate.execution.max_attempts != 1 or route.tools or route.output_schema is not None:
        raise ValueError("Olist H10 requires its single-attempt intent-only route template")
    if origin == "mock":
        if (route.provider, route.endpoint) != ("mock", "in-process"):
            raise ValueError("mock Olist capture requires an explicit mock route")
    else:
        # SDK is optional and imported only for an explicitly selected provider composition.
        from agent_harness.gemini import GeminiTransport

        if (
            type(transport) is not GeminiTransport
            or route.provider != "google-gemini-developer-api"
        ):
            raise ValueError("provider Olist capture requires the reviewed Gemini transport")
