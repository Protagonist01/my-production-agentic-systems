"""Prepare a finite live-demo proposal, without keys, provider calls or ledger writes."""

import argparse
import hashlib
import json
import sqlite3
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from agent_harness.contracts import ModelRequest
from prior_auth.contracts import NoteInput, Policy, digest
from prior_auth.source_io import external

from prior_auth_demo_console import plan
from prior_auth_demo_fixtures import EDUCATION, note, requests
from prior_auth_live_gateway import Slot, execution_pin, history, scope_binding
from prior_auth_pipeline import prepare
from prior_auth_profiling import Profiler
from prior_auth_study_draft import verified_policy


def packet(policy: Policy, *, now: datetime) -> dict[str, Any]:
    imported, scripted, files = plan(policy, now=now, scenario="education-wait")
    prepared = prepare(files["source.txt"].encode(), imported, Profiler())
    assert prepared.note is not None
    initial = prepared.note
    resumed_text = initial.text + "\n\n--- Reviewed supplemental evidence ---\n" + EDUCATION
    resumed = NoteInput.model_validate_json(
        initial.model_copy(
            update={"text": resumed_text, "note_sha256": digest(resumed_text)}
        ).canonical_json()
    )
    canaries = requests((note(initial.case_id, policy),), policy)[:2]
    domain = requests((initial,), policy) + tuple(
        r
        for r in requests((resumed,), policy)
        if json.loads(r.messages[1].content or "")["criterion"]["criterion_id"] == "education"
    )
    if len(canaries) != 2 or len(domain) != 7:
        raise ValueError("exact two-canary, six-initial, one-supplement schedule required")
    ordered: list[tuple[Literal["canary", "domain"], ModelRequest]] = [
        ("canary", r) for r in canaries
    ] + [("domain", r) for r in domain]
    scope = scripted.model_copy(
        update={
            "scope_id": "pa-live-wait-" + now.strftime("%Y%m%dT%H%M%SZ"),
            "mode": "fresh_candidate",
            "authorization_ref": "owner-exact-decision-required-for-this-private-packet",
            "provider_scope_sha256": "f" * 64,
            "expires_at": now + timedelta(days=7),
            "max_attempts": 7,
            "max_tokens": 2000000,
            "request_sha256s": tuple(dict.fromkeys(r.fingerprint() for _, r in ordered)),
        }
    )
    return {
        "scope": scope,
        "files": {name: text for name, text in files.items() if name != "scope.json"},
        "requests": [
            {
                "slot": Slot(
                    phase=phase, case_id=initial.case_id, request_sha256=r.fingerprint()
                ).model_dump(mode="json"),
                "request": r.model_dump(mode="json"),
            }
            for phase, r in ordered
        ],
    }


def write_proposal(root: Path, directory: Path, policy_directory: Path, ledger_path: Path) -> str:
    root = root.resolve(strict=True)
    if (
        root != Path(__file__).resolve().parent
        or subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True).strip()
    ):
        raise ValueError("clean actual tested checkout required")
    directory, ledger_path = external(directory), external(ledger_path)
    if directory.exists():
        raise FileExistsError("exclusive proposal directory required")
    value = packet(verified_policy(policy_directory), now=datetime.now(UTC))
    scope = value.pop("scope").model_copy(
        update={
            "code_revision": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=root, text=True
            ).strip(),
            "environment_sha256": hashlib.sha256((root / "uv.lock").read_bytes()).hexdigest(),
        }
    )
    with sqlite3.connect(ledger_path.as_uri() + "?mode=ro", uri=True) as c:
        old = json.loads(c.execute("SELECT document FROM authorization").fetchone()[0])
        if (
            c.execute("SELECT count(*) FROM attempts").fetchone()[0] != 447
            or c.execute("SELECT count(*) FROM pa_settlements").fetchone()[0] != 168
        ):
            raise ValueError("expected615 history required")
        old_pin = history(c)
    proposal = {
        "authorized": False,
        "free_project_confirmation_required": True,
        "new_attempts_max": 9,
        "lifetime_ceiling_proposed": 793,
        "old_bound_slots_preserved": 169,
        "max_tokens": 2000000,
        "no_retry": True,
        "paid_fallback": False,
        "http_seconds": 90,
        "parent_seconds": 110,
        "execution_sha256": execution_pin(root),
        "historical_sha256": old_pin,
        "project_association_sha256": old["project_sha256"],
        "runtime_scope_sha256": scope_binding(scope),
        "purpose": "single synthetic development demonstration, not model qualification",
        "requests": value["requests"],
    }
    directory.mkdir(parents=True, mode=0o700)
    artifacts = {
        "proposal.json": json.dumps(proposal, sort_keys=True, indent=2),
        "scope-template.json": scope.canonical_json(),
        **value["files"],
        "review.md": (
            "# Proposed local Gemini demo\n\n"
            "Preparation only. Nine new attempts: two complete-note canaries, then six initial "
            "criterion calls and one education-only reassessment after the fixed supplement. "
            "Both canaries must have exact supporting quotations that pass the existing checker. "
            "Failures count; unknown usage or interruptions stop; no retries or paid fallback. "
            "The exact request schedule, source/environment and seven-day expiry are in "
            "proposal.json "
            "and scope-template.json. Existing615attempts and169old bound slots stay untouched; "
            "the proposed same-file ceiling is793. At most2milliontokens. The configured project "
            "must be confirmed Free again. No clinical qualification or release approval follows. "
            "The separate168-call comparison proposal remains unapproved.\n"
        ),
    }
    pins = {}
    for name, text in artifacts.items():
        raw = text.encode("utf-8")
        with (directory / name).open("xb") as f:
            f.write(raw)
        pins[name] = hashlib.sha256(raw).hexdigest()
    manifest = json.dumps(pins, sort_keys=True, indent=2).encode("utf-8")
    (directory / "manifest.json").write_bytes(manifest)
    return hashlib.sha256(manifest).hexdigest()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--policy-directory", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    args = parser.parse_args()
    print(
        write_proposal(
            Path(__file__).resolve().parent, args.directory, args.policy_directory, args.ledger
        )
    )
