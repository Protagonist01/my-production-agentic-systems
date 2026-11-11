"""Project an approved private draft into input-only data; execution stays blocked."""

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path

from cfpb_triage.source_contracts import ComplaintInput

ROOT = Path(__file__).resolve().parents[2]
PIN = re.compile(r"^[a-f0-9]{64}$")
SOURCE_FILES = {
    "bank-train.csv",
    "BANKING-LICENSE.txt",
    "CLINC-LICENSE.txt",
    "clinc-train-member.json",
    "proposed-mappings.json",
    "review.md",
    "selected-originals.json",
    "selection-provenance.json",
    "source-manifest.json",
    "SOURCE-NOTICE.txt",
}
BLOCKERS = (
    "development_scope_mappings_pending",
    "qualified_semantic_references_missing",
    "representative_cohort_not_approved",
    "project_groups_and_partitions_not_approved",
    "taxonomy_and_candidate_policy_not_frozen",
    "sample_support_and_trial_plan_not_approved",
    "operating_and_cost_limits_not_approved",
    "fresh_provider_scope_not_authorized",
    "existing_provider_stop_not_reusable",
    "human_effort_comparison_not_observed",
    "dependency_33_and_release_evidence_pending",
)
PREPARATION_SOURCES = (
    "docs/evaluation/prepare_cfpb_input_packet.py",
    "projects/cfpb-triage/src/cfpb_triage/source_contracts.py",
    "harness/src/agent_harness/contracts.py",
    "uv.lock",
)


def require(value, message="CFPB input packet refused"):
    if not value:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def private(path):
    path = path.resolve()
    require(not any((p / ".git").exists() for p in (path, *path.parents)))
    return path


def raw_file(root, name):
    require(Path(name).name == name and name not in (".", ".."))
    path = root / name
    require(not path.is_symlink() and path.is_file() and path.stat().st_size <= 50_000_000)
    return path.read_bytes()


def decode(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result)
            result[key] = value
        return result

    return json.loads(raw, object_pairs_hook=unique, parse_constant=lambda _: require(False))


def project(source, expected):
    source = private(source)
    require(PIN.fullmatch(expected) is not None)
    manifest_raw = raw_file(source, "manifest.json")
    require(sha(manifest_raw) == expected)
    manifest = decode(manifest_raw)
    require(
        manifest["complete"] is True
        and manifest["cases"] == 12
        and manifest["labels_accepted"] is False
        and manifest["provider_attempts"] == 0
        and manifest["source_test_records_decoded"] is False
        and manifest["release_allowed"] is False
        and set(manifest["files"]) == SOURCE_FILES
    )
    contents = {name: raw_file(source, name) for name in SOURCE_FILES}
    for name, pin in manifest["files"].items():
        require(PIN.fullmatch(pin) is not None and sha(contents[name]) == pin)
    originals = decode(contents["selected-originals.json"])
    proposals = decode(contents["proposed-mappings.json"])
    provenance = decode(contents["selection-provenance.json"])
    require(len(originals) == len(proposals) == len(provenance) == 12)
    proposal_ids = {r["case_id"] for r in proposals}
    source_ids = {r["case_id"] for r in originals}
    require(
        len(source_ids) == len(proposal_ids) == 12
        and source_ids == proposal_ids
        and source_ids == {r["case_id"] for r in provenance}
    )
    by_id = {r["case_id"]: r for r in proposals}
    inputs, evaluator = [], []
    for original in originals:
        require(
            original["publisher_split"] == "train"
            and original["project_mapping_status"] == "unreviewed_proposal"
        )
        require(original["source"] in ("clinc150", "banking77"))
        text = original["original_text"]
        require(isinstance(text, str) and 0 < len(text) <= 20000)
        text_pin = sha(text.encode())
        proposal = by_id[original["case_id"]]
        require(text_pin == original["text_sha256"] == proposal["text_sha256"])
        require(
            proposal["accepted"] is False
            and proposal["status"] == "AI_proposed_for_development_review_only"
            and all(
                proposal[field] is None for field in ("product", "issue", "priority", "ambiguity")
            )
        )
        item = ComplaintInput(case_id=text_pin, narrative=text)
        inputs.append(item.model_dump(mode="json"))
        evaluator.append(
            {
                "input_case_id": item.case_id,
                "source": original,
                "pending_proposal": proposal,
                "project_partition": None,
                "qualified_reference": False,
            }
        )
    require(len({r["case_id"] for r in inputs}) == 12)
    return inputs, evaluator


def readiness():
    return {
        "schema_version": 1,
        "purpose": "input_projection_and_preparation_only",
        "input_integrity_passed": True,
        "mapping_acceptance": False,
        "qualification": False,
        "execution_authorized": False,
        "provider_export_authorized": False,
        "provider_attempts": 0,
        "training_or_scoring_performed": False,
        "release_allowed": False,
        "project_partitions": None,
        "trials": None,
        "operating_limits": None,
        "candidate_requests": None,
        "status": "blocked_for_execution",
        "blockers": list(BLOCKERS),
    }


def write(output, name, value):
    raw = (
        json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    ).encode()
    fd = os.open(output / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return sha(raw)


def prepare(source, expected, output):
    inputs, evaluator = project(source, expected)
    output = private(output)
    output.mkdir(mode=0o700)
    files = {
        "inputs.json": write(output, "inputs.json", inputs),
        "evaluator-only.json": write(output, "evaluator-only.json", evaluator),
        "readiness.json": write(output, "readiness.json", readiness()),
    }
    # This binds the preparation/contract bytes, not an approved future model candidate.
    sources = {name: sha((ROOT / name).read_bytes()) for name in PREPARATION_SOURCES}
    manifest = {
        "schema_version": 1,
        "complete": True,
        "source_draft_sha256": expected,
        "preparation_source_pins": sources,
        "files": files,
        "execution_authorized": False,
        "mappings_accepted": False,
    }
    return write(output, "manifest.json", manifest)


def verify(source, expected, output, packet_pin):
    output = private(output)
    require(PIN.fullmatch(packet_pin) is not None)
    manifest_raw = raw_file(output, "manifest.json")
    require(sha(manifest_raw) == packet_pin)
    manifest = decode(manifest_raw)
    require(
        manifest["complete"] is True
        and manifest["source_draft_sha256"] == expected
        and manifest["execution_authorized"] is False
        and manifest["mappings_accepted"] is False
    )
    require(set(manifest["files"]) == {"inputs.json", "evaluator-only.json", "readiness.json"})
    contents = {name: raw_file(output, name) for name in manifest["files"]}
    for name, pin in manifest["files"].items():
        require(sha(contents[name]) == pin)
    require(set(manifest["preparation_source_pins"]) == set(PREPARATION_SOURCES))
    for name, pin in manifest["preparation_source_pins"].items():
        path = (ROOT / name).resolve()
        require(path.is_relative_to(ROOT) and sha(path.read_bytes()) == pin)
    inputs, evaluator = project(source, expected)
    require(decode(contents["inputs.json"]) == inputs)
    require(decode(contents["evaluator-only.json"]) == evaluator)
    require(decode(contents["readiness.json"]) == readiness())
    for item in decode(contents["inputs.json"]):
        require(set(item) == {"schema_version", "case_id", "narrative"})
        ComplaintInput.model_validate_json(json.dumps(item))
    return {
        "verified": True,
        "cases": 12,
        "mappings_accepted": False,
        "execution_authorized": False,
        "readiness": "blocked_for_execution",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "verify"))
    parser.add_argument("--draft", type=Path, required=True)
    parser.add_argument("--draft-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--packet-sha256")
    args = parser.parse_args()
    network = {"attempts": 0}

    def deny(event, arguments):
        if event in {
            "socket.connect",
            "socket.sendto",
            "socket.sendmsg",
            "socket.getaddrinfo",
            "socket.gethostbyname",
            "socket.gethostbyaddr",
        }:
            network["attempts"] += 1
            raise RuntimeError("network denied during input preparation")

    sys.addaudithook(deny)
    if args.command == "prepare":
        result = {
            "packet_sha256": prepare(args.draft, args.draft_sha256, args.output),
            "cases": 12,
            "execution_authorized": False,
        }
    else:
        require(args.packet_sha256 is not None)
        result = verify(args.draft, args.draft_sha256, args.output, args.packet_sha256)
    require(network["attempts"] == 0)
    print(json.dumps({**result, "network_attempts": network["attempts"]}))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, LookupError, TypeError):
        raise SystemExit("CFPB input packet refused; inspect private source/pins") from None
