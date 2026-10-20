"""Pinned original-contract import, conservative family grouping and separate stores."""

import re
import sqlite3
import unicodedata
from collections import Counter
from collections.abc import Iterator
from contextlib import closing
from pathlib import Path
from typing import Annotated, Any

from agent_harness.contracts import Contract, NonEmpty
from pydantic import Field

from revenue_integrity.source_contracts import (
    POLICY,
    ExtractionInput,
    PublishedTarget,
    SourcePin,
    Span,
    Split,
)
from revenue_integrity.source_io import canonical, external, pinned_member, sha256

LIMITATIONS = (
    "Published expert span references are retained unchanged; no candidate authored targets.",
    "Inferred issuer/template families only; unobserved legal relationships may remain.",
    "Local family split replaces the published train/test split; scores are not comparable.",
    "CUAD clause spans are not reviewed normalized billing amounts or account-linked schedules.",
    "No seat/price/uplift billing gold, extraction baseline, provider call or recovered revenue.",
    "Original source may be incomplete, redacted or outdated; no legal advice or warranty.",
    "Separate SQLite files are an application boundary, not an OS sandbox or access control.",
)


class _Answer(Contract):
    answer_start: Annotated[int, Field(ge=0)]
    text: NonEmpty


class _Question(Contract):
    id: NonEmpty
    question: NonEmpty
    answers: tuple[_Answer, ...]
    is_impossible: bool


class _Paragraph(Contract):
    context: NonEmpty
    qas: Annotated[tuple[_Question, ...], Field(min_length=1)]


class _Document(Contract):
    title: NonEmpty
    paragraphs: Annotated[tuple[_Paragraph, ...], Field(min_length=1, max_length=1)]


class _Corpus(Contract):
    version: NonEmpty
    data: Annotated[tuple[_Document, ...], Field(min_length=1)]


def _key(value: str) -> str:
    return sha256(value.encode("utf-8"))


def _normalized(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def _shingles(context: str) -> set[str]:
    # Numeric edits should not let a changed date/price evade template detection.
    words = re.findall(r"[a-z]+|#", re.sub(r"\d+(?:[.,]\d+)*", "#", _normalized(context)))
    return {" ".join(words[i : i + 5]) for i in range(max(0, len(words) - 4))}


def families(documents: tuple[_Document, ...]) -> tuple[dict[str, str], dict[str, int]]:
    """Union same issuer, exact text and >=65% five-word-template Jaccard relations."""
    parents = list(range(len(documents)))

    def find(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def union(left: int, right: int) -> None:
        parents[find(right)] = find(left)

    issuers: dict[str, int] = {}
    contexts: dict[str, int] = {}
    issuer_edges = exact_edges = template_edges = unknown_issuers = 0
    shingles = []
    for i, document in enumerate(documents):
        # CUAD has both issuer_date_filename and manually titled "issuer - contract" names.
        issuer_parts = re.split(r"_| - ", document.title, maxsplit=1)
        issuer = re.sub(r"[^a-z0-9]", "", _normalized(issuer_parts[0]))
        context = document.paragraphs[0].context
        if len(issuer_parts) == 1:
            # Do not invent a source issuer from the one CUAD title without a delimiter.
            unknown_issuers += 1
        elif issuer in issuers:
            union(issuers[issuer], i)
            issuer_edges += 1
        if len(issuer_parts) == 2:
            issuers.setdefault(issuer, i)
        normalized = _normalized(context)
        if normalized in contexts:
            union(contexts[normalized], i)
            exact_edges += 1
        contexts.setdefault(normalized, i)
        shingles.append(_shingles(context))
    for i, left in enumerate(shingles):
        for j in range(i):
            right = shingles[j]
            # An intersection cannot exceed the smaller set; prune impossible ratios.
            if min(len(left), len(right)) < 100:
                continue
            if min(len(left), len(right)) * 100 < max(len(left), len(right)) * 65:
                continue
            overlap = len(left.intersection(right))
            if overlap * 100 >= (len(left) + len(right) - overlap) * 65:
                union(i, j)
                template_edges += 1
    components: dict[int, list[str]] = {}
    for i, document in enumerate(documents):
        components.setdefault(find(i), []).append(document.title)
    groups = {
        title: _key(POLICY + "|" + "\n".join(sorted(titles)))
        for titles in components.values()
        for title in titles
    }
    return groups, {
        "issuer_edges": issuer_edges,
        "unknown_issuer_contracts": unknown_issuers,
        "exact_context_edges": exact_edges,
        "template_edges": template_edges,
        "family_count": len(components),
        "multi_contract_families": sum(len(v) > 1 for v in components.values()),
        "largest_family": max(map(len, components.values())),
    }


def family_split(family_id: str) -> Split:
    # Twenty percent by predeclared hash bucket, never by observed answer labels.
    return "holdout" if int(family_id[:8], 16) % 5 == 0 else "development"


def _validate(raw: bytes, pin: SourcePin) -> _Corpus:
    corpus = _Corpus.model_validate_json(raw)
    if len(corpus.data) != pin.contract_count:
        raise ValueError("contract count differs from independent source manifest")
    titles: set[str] = set()
    question_ids: set[str] = set()
    expected_categories: set[str] | None = None
    for document in corpus.data:
        if document.title in titles:
            raise ValueError("duplicate source document")
        titles.add(document.title)
        paragraph = document.paragraphs[0]
        categories: set[str] = set()
        for question in paragraph.qas:
            category = question.id.rsplit("__", 1)[-1]
            if "__" not in question.id or category in categories or question.id in question_ids:
                raise ValueError("duplicate or malformed source question identity")
            categories.add(category)
            question_ids.add(question.id)
            if question.is_impossible != (not question.answers):
                raise ValueError("published answerability conflicts with spans")
            for answer in question.answers:
                if (
                    paragraph.context[answer.answer_start : answer.answer_start + len(answer.text)]
                    != answer.text
                ):
                    raise ValueError("published answer span does not match original context")
        if len(categories) != pin.category_count or (
            expected_categories is not None and categories != expected_categories
        ):
            raise ValueError("question category coverage differs across source documents")
        expected_categories = categories
    return corpus


def import_corpus(archive: Path, pin: SourcePin, output: Path) -> dict[str, Any]:
    """Exclusive private directory: any failed build remains unpublished and visibly incomplete."""
    output = external(output)
    if output.exists():
        raise FileExistsError("refusing to overwrite an existing private corpus directory")
    corpus = _validate(pinned_member(archive, pin), pin)
    groups, grouping = families(corpus.data)
    output.mkdir(parents=True, exist_ok=False)
    inputs_path, evaluator_path = output / "inputs.sqlite", output / "evaluator.sqlite"
    counts: Counter[str] = Counter()
    category_counts: dict[str, Counter[str]] = {}
    with (
        closing(sqlite3.connect(inputs_path)) as inputs,
        closing(sqlite3.connect(evaluator_path)) as evaluator,
        inputs,
        evaluator,
    ):
        inputs.executescript(
            "CREATE TABLE contracts (contract_id TEXT PRIMARY KEY,context TEXT NOT NULL);"
            "CREATE TABLE questions (case_id TEXT PRIMARY KEY,contract_id TEXT NOT NULL "
            "REFERENCES contracts(contract_id),question TEXT NOT NULL);"
        )
        evaluator.executescript(
            "CREATE TABLE targets (case_id TEXT PRIMARY KEY,target TEXT NOT NULL);"
            "CREATE TABLE sources (case_id TEXT PRIMARY KEY,title TEXT NOT NULL,"
            "source_question_id TEXT NOT NULL,context_sha256 TEXT NOT NULL);"
        )
        for document in sorted(corpus.data, key=lambda item: item.title):
            paragraph = document.paragraphs[0]
            contract_id = _key("cuad-contract-v1|" + document.title)
            family_id = groups[document.title]
            split = family_split(family_id)
            counts[split + "_contracts"] += 1
            inputs.execute("INSERT INTO contracts VALUES (?,?)", (contract_id, paragraph.context))
            for question in sorted(paragraph.qas, key=lambda item: item.id):
                case_id = _key("cuad-question-v1|" + question.id)
                category = question.id.rsplit("__", 1)[-1]
                public = ExtractionInput(
                    case_id=case_id, context=paragraph.context, question=question.question
                )
                target = PublishedTarget(
                    case_id=case_id,
                    category=category,
                    answers=tuple(
                        Span(start=answer.answer_start, text=answer.text)
                        for answer in question.answers
                    ),
                    impossible=question.is_impossible,
                    family_id=family_id,
                    split=split,
                )
                inputs.execute(
                    "INSERT INTO questions VALUES (?,?,?)",
                    (public.case_id, contract_id, public.question),
                )
                evaluator.execute(
                    "INSERT INTO targets VALUES (?,?)", (case_id, target.canonical_json())
                )
                evaluator.execute(
                    "INSERT INTO sources VALUES (?,?,?,?)",
                    (case_id, document.title, question.id, _key(paragraph.context)),
                )
                counts[split + "_questions"] += 1
                counts["answer_spans"] += len(target.answers)
                counts["unanswerable_questions"] += int(target.impossible)
                category_counts.setdefault(category, Counter())["questions"] += 1
                category_counts[category]["answer_spans"] += len(target.answers)
                category_counts[category]["answerable_questions"] += int(not target.impossible)
        inputs.execute("PRAGMA user_version=1")
        evaluator.execute("PRAGMA user_version=1")
    report = {
        "version": "revenue-original-cuad-v1",
        "source": pin.model_dump(mode="json"),
        "source_pin_canonical_sha256": sha256(pin.canonical_json().encode()),
        "family_policy": POLICY,
        "family_split_rule": "SHA256(policy|sorted-source-titles) first32bits mod5=0 holdout",
        "grouping": grouping,
        "counts": {
            "contracts": len(corpus.data),
            "questions": sum(len(document.paragraphs[0].qas) for document in corpus.data),
            "categories": pin.category_count,
            **dict(sorted(counts.items())),
        },
        "category_coverage": dict(sorted(category_counts.items())),
        "inputs_sha256": sha256(inputs_path.read_bytes()),
        "evaluator_sha256": sha256(evaluator_path.read_bytes()),
        "limitations": LIMITATIONS,
    }
    (output / "manifest.json").write_bytes(canonical(report))
    return report


def read_inputs(database: Path) -> Iterator[ExtractionInput]:
    """Trusted evaluator selects cases; candidate receives individual projections, not this path."""
    with closing(sqlite3.connect(external(database).as_uri() + "?mode=ro", uri=True)) as db:
        db.execute("PRAGMA query_only=ON")
        for case_id, context, question in db.execute(
            "SELECT case_id,context,question FROM questions JOIN contracts USING(contract_id) "
            "ORDER BY case_id"
        ):
            yield ExtractionInput(case_id=case_id, context=context, question=question)


def read_targets(database: Path) -> Iterator[PublishedTarget]:
    """Evaluator-only API; never import or pass this store from production extraction code."""
    with closing(sqlite3.connect(external(database).as_uri() + "?mode=ro", uri=True)) as db:
        db.execute("PRAGMA query_only=ON")
        for (raw,) in db.execute("SELECT target FROM targets ORDER BY case_id"):
            yield PublishedTarget.model_validate_json(raw)


def verify_corpus(archive: Path, output: Path, expected_manifest_sha256: str) -> dict[str, Any]:
    """Recheck pinned raw source, both complete stores and every published reference."""
    import json

    output = external(output)
    raw = (output / "manifest.json").read_bytes()
    if sha256(raw) != expected_manifest_sha256:
        raise ValueError("prepared manifest differs from independently supplied pin")
    report: dict[str, Any] = json.loads(raw)
    pin = SourcePin.model_validate_json(json.dumps(report["source"]))
    corpus = _validate(pinned_member(archive, pin), pin)
    if sha256(pin.canonical_json().encode()) != report["source_pin_canonical_sha256"]:
        raise ValueError("source manifest canonical pin differs")
    for name, key in (("inputs.sqlite", "inputs_sha256"), ("evaluator.sqlite", "evaluator_sha256")):
        if sha256((output / name).read_bytes()) != report[key]:
            raise ValueError("prepared store differs from pinned manifest")
    groups, grouping = families(corpus.data)
    if report["family_policy"] != POLICY or report["grouping"] != grouping:
        raise ValueError("family policy or computed group counts differ")
    targets = {entry.case_id: entry for entry in read_targets(output / "evaluator.sqlite")}
    expected_ids: set[str] = set()
    with (
        closing(sqlite3.connect((output / "inputs.sqlite").as_uri() + "?mode=ro", uri=True)) as db,
        closing(
            sqlite3.connect((output / "evaluator.sqlite").as_uri() + "?mode=ro", uri=True)
        ) as ev,
    ):
        if db.execute("PRAGMA integrity_check").fetchone() != ("ok",) or ev.execute(
            "PRAGMA integrity_check"
        ).fetchone() != ("ok",):
            raise ValueError("prepared SQLite integrity check failed")
        for database, tables in ((db, ("contracts", "questions")), (ev, ("targets", "sources"))):
            expected_objects = {
                *(("table", name, name) for name in tables),
                *(("index", "sqlite_autoindex_" + name + "_1", name) for name in tables),
            }
            actual_objects = set(
                database.execute("SELECT type,name,tbl_name FROM sqlite_master").fetchall()
            )
            if actual_objects != expected_objects:
                raise ValueError("prepared database contains unexpected schema objects")
        input_schema = {
            name: tuple(row[1] for row in db.execute(f"PRAGMA table_info({name})"))
            for (name,) in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        if input_schema != {
            "contracts": ("contract_id", "context"),
            "questions": ("case_id", "contract_id", "question"),
        }:
            raise ValueError("agent database contains unexpected schema")
        if db.execute("SELECT COUNT(*) FROM contracts").fetchone() != (pin.contract_count,):
            raise ValueError("unexpected contract population")
        public_ids = {row[0] for row in db.execute("SELECT case_id FROM questions")}
        for document in corpus.data:
            paragraph = document.paragraphs[0]
            for question in paragraph.qas:
                case_id = _key("cuad-question-v1|" + question.id)
                expected_ids.add(case_id)
                expected = PublishedTarget(
                    case_id=case_id,
                    category=question.id.rsplit("__", 1)[-1],
                    answers=tuple(
                        Span(start=a.answer_start, text=a.text) for a in question.answers
                    ),
                    impossible=question.is_impossible,
                    family_id=groups[document.title],
                    split=family_split(groups[document.title]),
                )
                public_row = db.execute(
                    "SELECT context,question FROM questions JOIN contracts USING(contract_id) "
                    "WHERE case_id=?",
                    (case_id,),
                ).fetchone()
                if targets.get(case_id) != expected or public_row != (
                    paragraph.context,
                    question.question,
                ):
                    raise ValueError(
                        "stored input or published reference differs from original source"
                    )
                if ev.execute(
                    "SELECT title,source_question_id,context_sha256 FROM sources WHERE case_id=?",
                    (case_id,),
                ).fetchone() != (document.title, question.id, _key(paragraph.context)):
                    raise ValueError("evaluator source provenance differs")
        if ev.execute("SELECT COUNT(*) FROM sources").fetchone() != (len(expected_ids),):
            raise ValueError("unexpected provenance population")
    if set(targets) != expected_ids or public_ids != expected_ids:
        raise ValueError("stored question population differs from original source")
    counts: Counter[str] = Counter()
    category_counts: dict[str, Counter[str]] = {}
    for document in corpus.data:
        split = family_split(groups[document.title])
        counts[split + "_contracts"] += 1
        for question in document.paragraphs[0].qas:
            counts[split + "_questions"] += 1
            counts["answer_spans"] += len(question.answers)
            counts["unanswerable_questions"] += int(question.is_impossible)
            category = question.id.rsplit("__", 1)[-1]
            category_counts.setdefault(category, Counter())["questions"] += 1
            category_counts[category]["answer_spans"] += len(question.answers)
            category_counts[category]["answerable_questions"] += int(not question.is_impossible)
    expected_counts = {
        "contracts": pin.contract_count,
        "questions": len(expected_ids),
        "categories": pin.category_count,
        **counts,
    }
    if report["counts"] != expected_counts or report["category_coverage"] != category_counts:
        raise ValueError("reported source coverage differs from recomputed original population")
    if (
        tuple(report["limitations"]) != LIMITATIONS
        or report["version"] != "revenue-original-cuad-v1"
    ):
        raise ValueError("report version or limitations differ from this source policy")
    return {
        "manifest_sha256": expected_manifest_sha256,
        "contracts": pin.contract_count,
        "questions": len(expected_ids),
        "answer_spans": sum(len(target.answers) for target in targets.values()),
        "family_count": grouping["family_count"],
        "verified": True,
    }
