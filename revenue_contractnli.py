"""Training-only native ContractNLI audit. NDA inference is not billing-meaning gold."""

import hashlib
import io
import json
import zipfile
from collections import Counter
from typing import Annotated, Any, Literal

from agent_harness.contracts import Contract
from agent_harness.release_contracts import Sha256, sha256
from pydantic import Field

REVISION = "eced6528dd3c1d14d73f9a87df8f7bdbc03126f9"
ARCHIVE_GIT_BLOB = "757fd1dafd29a997fba00c60c6d40b2930a36159"
LICENSE_GIT_BLOB = "4ea99c213c5c0c005ae4e80df8e52169d06896ec"
ARCHIVE_BYTES = 65_362_913
BASE = f"https://raw.githubusercontent.com/stanfordnlp/contract-nli/{REVISION}/"
Choice = Literal["Entailment", "Contradiction", "NotMentioned"]
CHOICES: tuple[Choice, ...] = ("Entailment", "Contradiction", "NotMentioned")


def git_blob(raw: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate source key")
        value[key] = item
    return value


def strict_json(raw: bytes) -> Any:
    def invalid(value: str) -> None:
        raise ValueError("nonfinite JSON constant")

    return json.loads(raw, object_pairs_hook=unique, parse_constant=invalid)


class NativeInput(Contract):
    case_id: Sha256
    document: str = Field(min_length=1)
    hypothesis: str = Field(min_length=1)


class NativeReference(Contract):
    input: NativeInput
    publisher_document_id: int | str
    publisher_split: Literal["train"] = "train"
    hypothesis_id: str
    choice: Choice
    evidence: tuple[tuple[int, int], ...]
    source_revision: Literal["eced6528dd3c1d14d73f9a87df8f7bdbc03126f9"] = (
        "eced6528dd3c1d14d73f9a87df8f7bdbc03126f9"
    )
    source_member_sha256: Sha256
    family_independence_authenticated: Literal[False] = False
    billing_reference: Literal[False] = False


def parse_training(raw: bytes) -> tuple[NativeReference, ...]:
    """Strict native task import; keep three classes and every publisher evidence span."""
    if not 0 < len(raw) <= 100_000_000:
        raise ValueError("bounded training member required")
    data = strict_json(raw)
    if (
        not isinstance(data, dict)
        or not isinstance(data.get("documents"), list)
        or not isinstance(data.get("labels"), dict)
    ):
        raise ValueError("native documents and labels required")
    labels = data["labels"]
    if not labels or not data["documents"]:
        raise ValueError("empty native source")
    seen: set[int | str] = set()
    member_sha256 = sha256(raw)
    result = []
    for document in data["documents"]:
        identity = document["id"]
        if type(identity) not in (int, str) or identity in seen:
            raise ValueError("duplicate/invalid publisher document id")
        seen.add(identity)
        text = document["text"]
        spans = document["spans"]
        if not isinstance(text, str) or not text or not isinstance(spans, list):
            raise ValueError("native text/span inventory required")
        for span in spans:
            if (
                not isinstance(span, list)
                or len(span) != 2
                or any(type(i) is not int for i in span)
                or not 0 <= span[0] < span[1] <= len(text)
            ):
                raise ValueError("invalid native evidence interval")
        sets = document["annotation_sets"]
        if (
            not isinstance(sets, list)
            or len(sets) != 1
            or set(sets[0]["annotations"]) != set(labels)
        ):
            raise ValueError("single complete publisher annotation required")
        for key, annotation in sets[0]["annotations"].items():
            hypothesis = labels[key]["hypothesis"]
            choice, indices = annotation["choice"], annotation["spans"]
            if (
                choice not in CHOICES
                or not isinstance(indices, list)
                or any(type(i) is not int or not 0 <= i < len(spans) for i in indices)
                or len(set(indices)) != len(indices)
            ):
                raise ValueError("invalid native choice/evidence indices")
            if (choice == "NotMentioned") != (not indices):
                raise ValueError("neutral has no evidence; nonneutral requires evidence")
            public = NativeInput(
                case_id=sha256(
                    (str(identity) + "\0" + key + "\0" + text + "\0" + hypothesis).encode()
                ),
                document=text,
                hypothesis=hypothesis,
            )
            result.append(
                NativeReference(
                    input=public,
                    publisher_document_id=identity,
                    hypothesis_id=key,
                    choice=choice,
                    evidence=tuple(tuple(spans[i]) for i in indices),
                    source_member_sha256=member_sha256,
                )
            )
    return tuple(result)


def audit_archive(archive: bytes, license_bytes: bytes, *, train_member: str) -> dict[str, Any]:
    """Verify official Git object pins; decode only the explicitly named train member."""
    if (
        len(archive) != ARCHIVE_BYTES
        or git_blob(archive) != ARCHIVE_GIT_BLOB
        or git_blob(license_bytes) != LICENSE_GIT_BLOB
    ):
        raise ValueError("immutable source/license object differs")
    with zipfile.ZipFile(io.BytesIO(archive)) as source:
        names = source.namelist()
        if (
            len(names) != len(set(names))
            or train_member not in names
            or train_member.rsplit("/", 1)[-1] != "train.json"
        ):
            raise ValueError("unique explicit train.json member required")
        info = source.getinfo(train_member)
        if info.file_size > 100_000_000:
            raise ValueError("training member exceeds size bound")
        raw = source.read(info)
    refs = parse_training(raw)
    return {
        "source_revision": REVISION,
        "archive_sha256": sha256(archive),
        "license_sha256": sha256(license_bytes),
        "license": "CC-BY-4.0",
        "attribution": (
            "Yuta Koreeda and Christopher D. Manning, ContractNLI, "
            "Findings of EMNLP 2021, 1907–1919."
        ),
        "train_member": train_member,
        "train_sha256": sha256(raw),
        "train_bytes": len(raw),
        "documents": len({r.publisher_document_id for r in refs}),
        "hypotheses": len({r.hypothesis_id for r in refs}),
        "references": len(refs),
        "choices": dict(Counter(r.choice for r in refs)),
        "evidence_intervals": sum(len(r.evidence) for r in refs),
        "source_test_decoded": False,
        "source_development_decoded": False,
        "model_calls": 0,
        "billing_meaning_reference": False,
        "release_allowed": False,
    }


class NativePrediction(Contract):
    case_id: Sha256
    choice: Choice | None
    evidence: Annotated[tuple[tuple[int, int], ...], Field(max_length=500)] = ()
    failure: str | None = None


def native_score(
    references: tuple[NativeReference, ...], predictions: tuple[NativePrediction, ...]
) -> dict[str, Any]:
    """Scheduled three-class report; missing cases fail, no neutral-to-reject conversion."""
    refs = {r.input.case_id: r for r in references}
    if len(refs) != len(references) or not refs:
        raise ValueError("unique nonempty native references required")
    rows: dict[str, NativePrediction] = {}
    for prediction in predictions:
        p: NativePrediction | None = NativePrediction.model_validate_json(
            prediction.canonical_json()
        )
        assert p is not None
        if (
            p.case_id in rows
            or p.case_id not in refs
            or (p.choice is None) != (p.failure is not None)
            or (p.failure is not None and p.evidence)
        ):
            raise ValueError("invalid/duplicate/unscheduled native prediction")
        text = refs[p.case_id].input.document
        if len(set(p.evidence)) != len(p.evidence) or any(
            not 0 <= a < b <= len(text) for a, b in p.evidence
        ):
            raise ValueError("invalid predicted evidence offsets")
        if p.choice == "NotMentioned" and p.evidence:
            raise ValueError("neutral prediction cannot assert evidence")
        rows[p.case_id] = p
    classes = {}
    for choice in CHOICES:
        tp = sum(
            r.choice == choice and (p := rows.get(k)) is not None and p.choice == choice
            for k, r in refs.items()
        )
        fp = sum(refs[k].choice != choice and p.choice == choice for k, p in rows.items())
        fn = sum(r.choice == choice for r in refs.values()) - tp
        classes[choice] = {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None,
        }
    evidence_cases = [r for r in references if r.choice != "NotMentioned"]
    return {
        "scheduled": len(refs),
        "observed": len(rows),
        "missing": len(refs) - len(rows),
        "classes": classes,
        "macro_f1": sum(float(c["f1"] or 0) for c in classes.values()) / 3
        if all(c["f1"] is not None for c in classes.values())
        else None,
        "exact_complete_evidence": {
            "numerator": sum(
                (p := rows.get(r.input.case_id)) is not None
                and p.choice == r.choice
                and set(p.evidence) == set(r.evidence)
                for r in evidence_cases
            ),
            "denominator": len(evidence_cases),
        },
        "native_task_only": True,
        "billing_meaning_certified": False,
        "release_allowed": False,
    }
