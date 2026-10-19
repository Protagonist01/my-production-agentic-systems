"""Stream pinned archived complaints into physically separate agent/scorer stores."""

import csv
import hashlib
import io
import json
import re
import sqlite3
import unicodedata
import zipfile
from collections import Counter
from collections.abc import Iterator
from contextlib import closing
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from cfpb_triage.source_contracts import (
    ARCHIVE_MEMBER,
    ARCHIVE_URL,
    COLUMNS,
    POLICY_VERSION,
    TAXONOMY_URL,
    TAXONOMY_VERSION,
    ComplaintInput,
    ConsumerTarget,
    SourcePin,
    temporal_split,
)
from cfpb_triage.source_io import digest_file, external_path, verify_sources

AGENT_COLUMNS = ("case_id", "narrative")
TARGET_COLUMNS = (
    "case_id",
    "product",
    "sub_product",
    "issue",
    "sub_issue",
    "received",
    "split",
    "group_id",
)
LIMITATIONS = (
    "Publication/consent/scrubbing selected archive; not all complaints or population risk.",
    "Consumer-selected targets are unverified reference labels, not independently reviewed truth.",
    "Exact normalized-text groups only; no consumer IDs or near-duplicate independence guarantee.",
    "Published masking retained; no privacy certification or automatic provider export.",
    "No reviewed risk labels, classification evaluation, baseline or harm-reduction result.",
    "Current live database removed narratives in 2026; this is a fixed historical archive.",
)


def case_key(source_id: str) -> str:
    return hashlib.sha256(f"cfpb:{source_id}".encode()).hexdigest()


def group_key(narrative: str) -> str:
    normalized = " ".join(unicodedata.normalize("NFKC", narrative).casefold().split())
    return hashlib.sha256(normalized.encode()).hexdigest()


def archive_rows(archive: Path) -> Iterator[dict[str, str]]:
    with zipfile.ZipFile(archive) as source:
        if source.namelist() != [ARCHIVE_MEMBER]:
            raise ValueError("Archive inventory differs from the fixed source member")
        info = source.getinfo(ARCHIVE_MEMBER)
        if info.file_size > 2_000_000_000 or info.flag_bits & 1:
            raise ValueError("Archive member exceeds size cap or is encrypted")
        with (
            source.open(info) as binary,
            io.TextIOWrapper(binary, encoding="utf-8-sig", newline="") as text,
        ):
            reader = csv.DictReader(text, strict=True)
            if reader.fieldnames != list(COLUMNS):
                raise ValueError("Unexpected archived complaint schema")
            try:
                for row in reader:
                    if None in row or any(value is None for value in row.values()):
                        raise ValueError("Malformed archived complaint record width")
                    yield row
            except (csv.Error, UnicodeError) as error:
                raise ValueError("Malformed archived complaint encoding or CSV") from error


def _readonly(path: Path) -> sqlite3.Connection:
    database = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    database.execute("PRAGMA query_only=ON")
    database.execute("BEGIN")
    # Establish one stable SQLite snapshot for every schema/row read on this connection.
    database.execute("SELECT name FROM sqlite_master").fetchall()
    return database


def read_inputs(agent_database: Path) -> Iterator[ComplaintInput]:
    """Trusted caller scopes IDs before use; the database itself contains no target columns."""
    with closing(_readonly(external_path(agent_database))) as database:
        _schema(database, "inputs", AGENT_COLUMNS)
        for case_id, narrative in database.execute(
            "SELECT case_id,narrative FROM inputs ORDER BY case_id"
        ):
            yield ComplaintInput(case_id=case_id, narrative=narrative)


def read_targets(evaluator_database: Path) -> Iterator[ConsumerTarget]:
    """Evaluator-only composition must never hand this database or iterator to the agent."""
    with closing(_readonly(external_path(evaluator_database))) as database:
        _schema(database, "targets", TARGET_COLUMNS)
        for row in database.execute("SELECT * FROM targets ORDER BY case_id"):
            fields = dict(zip(TARGET_COLUMNS, row, strict=True))
            fields["received"] = date.fromisoformat(fields["received"])
            yield ConsumerTarget(**fields)


def _schema(database: sqlite3.Connection, table: str, columns: tuple[str, ...]) -> None:
    # Table names are fixed internal constants, never caller-supplied SQL.
    observed = tuple(row[1] for row in database.execute(f"PRAGMA table_info({table})"))
    inventory = tuple(database.execute("SELECT name FROM sqlite_master WHERE type='table'"))
    executable = database.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type IN ('view','trigger')"
    ).fetchone()[0]
    if observed != columns or inventory != ((table,),) or executable:
        raise ValueError("Prepared database schema/inventory differs from closed boundary")


def _stage(archive: Path, database: sqlite3.Connection) -> dict[str, Any]:
    database.executescript(
        "CREATE TABLE identities(id TEXT PRIMARY KEY);"
        "CREATE TABLE staged(case_id TEXT PRIMARY KEY,narrative TEXT,product TEXT,"
        "sub_product TEXT,issue TEXT,sub_issue TEXT,received TEXT,split TEXT,group_id TEXT);"
    )
    empty: Counter[str] = Counter()
    counts: Counter[str] = Counter()
    first = last = None
    mask_tokens = 0
    for row in archive_rows(archive):
        counts["archive_rows"] += 1
        empty.update(column for column in COLUMNS if not row[column].strip())
        source_id = row["Complaint ID"]
        if not source_id.isascii() or not source_id.isdigit():
            raise ValueError("Invalid archived complaint identity")
        try:
            database.execute("INSERT INTO identities VALUES(?)", (source_id,))
            received = date.fromisoformat(row["Date received"])
        except (ValueError, sqlite3.IntegrityError) as error:
            raise ValueError("Invalid complaint date or duplicate source identity") from error
        first = received if first is None else min(first, received)
        last = received if last is None else max(last, received)
        split = temporal_split(received)
        if split is None:
            counts["outside_cohort"] += 1
            continue
        counts["cohort_rows"] += 1
        narrative = row["Consumer complaint narrative"]
        if not narrative.strip():
            counts["missing_narrative"] += 1
            continue
        masks = re.findall(r"(?i)\bx{2,}\b", narrative)
        if masks:
            counts["masked_narrative_rows"] += 1
            mask_tokens += len(masks)
        if not row["Product"].strip() or not row["Issue"].strip():
            counts["missing_required_consumer_target"] += 1
            continue
        database.execute(
            "INSERT INTO staged VALUES(?,?,?,?,?,?,?,?,?)",
            (
                case_key(source_id),
                narrative,
                row["Product"],
                row["Sub-product"],
                row["Issue"],
                row["Sub-issue"],
                received.isoformat(),
                split,
                group_key(narrative),
            ),
        )
    database.execute("CREATE INDEX staged_groups ON staged(group_id,split)")
    database.execute(
        "CREATE TABLE quarantined AS SELECT group_id FROM staged "
        "GROUP BY group_id HAVING COUNT(DISTINCT split)>1"
    )
    database.execute("CREATE UNIQUE INDEX quarantined_groups ON quarantined(group_id)")
    counts["cross_partition_groups"] = database.execute(
        "SELECT COUNT(*) FROM quarantined"
    ).fetchone()[0]
    counts["cross_partition_rows"] = database.execute(
        "SELECT COUNT(*) FROM staged JOIN quarantined USING(group_id)"
    ).fetchone()[0]
    counts["mask_tokens"] = mask_tokens
    return {
        "counts": {
            key: counts[key]
            for key in (
                "archive_rows",
                "outside_cohort",
                "cohort_rows",
                "missing_narrative",
                "missing_required_consumer_target",
                "masked_narrative_rows",
                "mask_tokens",
                "cross_partition_groups",
                "cross_partition_rows",
            )
        },
        "empty_source_fields": {column: empty[column] for column in COLUMNS},
        "received_range": {
            "min": first.isoformat() if first else None,
            "max": last.isoformat() if last else None,
        },
    }


def _materialize(stage: sqlite3.Connection, output: Path) -> dict[str, Any]:
    agent_path, target_path = output / "agent.sqlite", output / "evaluator.sqlite"
    with (
        closing(sqlite3.connect(agent_path)) as agent,
        closing(sqlite3.connect(target_path)) as target,
    ):
        agent.execute("CREATE TABLE inputs(case_id TEXT PRIMARY KEY,narrative TEXT NOT NULL)")
        target.execute(
            "CREATE TABLE targets(case_id TEXT PRIMARY KEY,product TEXT NOT NULL,"
            "sub_product TEXT NOT NULL,issue TEXT NOT NULL,sub_issue TEXT NOT NULL,"
            "received TEXT NOT NULL,split TEXT NOT NULL,group_id TEXT NOT NULL)"
        )
        rows = stage.execute(
            "SELECT * FROM staged WHERE group_id NOT IN (SELECT group_id FROM quarantined) "
            "ORDER BY case_id"
        )
        for (
            case_id,
            narrative,
            product,
            sub_product,
            issue,
            sub_issue,
            received,
            split,
            group_id,
        ) in rows:
            agent.execute("INSERT INTO inputs VALUES(?,?)", (case_id, narrative))
            target.execute(
                "INSERT INTO targets VALUES(?,?,?,?,?,?,?,?)",
                (case_id, product, sub_product, issue, sub_issue, received, split, group_id),
            )
        agent.commit()
        target.commit()
    for path in (agent_path, target_path):
        path.chmod(0o600)
    return inspect_prepared(output)


def inspect_prepared(output: Path) -> dict[str, Any]:
    """Independently reconcile store schemas, IDs, text grouping and temporal membership."""
    output = external_path(output)
    with (
        closing(_readonly(output / "agent.sqlite")) as agent,
        closing(_readonly(output / "evaluator.sqlite")) as target,
    ):
        _schema(agent, "inputs", AGENT_COLUMNS)
        _schema(target, "targets", TARGET_COLUMNS)
        agent_rows = agent.execute("SELECT * FROM inputs ORDER BY case_id")
        target_rows = target.execute("SELECT * FROM targets ORDER BY case_id")
        splits: Counter[str] = Counter()
        products: Counter[str] = Counter()
        issues: Counter[tuple[str, str]] = Counter()
        groups: dict[str, str] = {}
        count = chars = 0
        for item, label in zip(agent_rows, target_rows, strict=True):
            if item[0] != label[0] or not item[1].strip():
                raise ValueError("Agent/evaluator case inventory differs or text is empty")
            parsed = ConsumerTarget(
                case_id=label[0],
                product=label[1],
                sub_product=label[2],
                issue=label[3],
                sub_issue=label[4],
                received=date.fromisoformat(label[5]),
                split=label[6],
                group_id=label[7],
            )
            if (
                temporal_split(parsed.received) != parsed.split
                or group_key(item[1]) != parsed.group_id
            ):
                raise ValueError("Prepared temporal/group provenance differs")
            if groups.setdefault(parsed.group_id, parsed.split) != parsed.split:
                raise ValueError("Prepared narrative group crosses partitions")
            count += 1
            chars += len(item[1])
            splits[parsed.split] += 1
            products[parsed.product] += 1
            issues[(parsed.product, parsed.issue)] += 1
        return {
            "prepared_rows": count,
            "group_count": len(groups),
            "narrative_characters": chars,
            "split_counts": {key: splits[key] for key in ("development", "regression", "holdout")},
            "product_counts": dict(sorted(products.items())),
            "product_issue_counts": [
                {"product": p, "issue": i, "count": n} for (p, i), n in sorted(issues.items())
            ],
        }


def prepare_snapshot(
    archive: Path, taxonomy: Path, pin: SourcePin, output: Path, *, code_revision: str
) -> dict[str, Any]:
    if not code_revision.strip():
        raise ValueError("Importer source revision is required")
    archive, taxonomy = verify_sources(archive, taxonomy, pin)
    output = external_path(output)
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    stage_path = output / "staging.sqlite"
    try:
        with closing(sqlite3.connect(stage_path)) as stage:
            stage_path.chmod(0o600)
            profile = _stage(archive, stage)
            prepared = _materialize(stage, output)
            if not prepared["prepared_rows"]:
                raise ValueError("No usable cohort rows remain; no snapshot sealed")
        stage_path.unlink()
        verify_sources(archive, taxonomy, pin)
        with zipfile.ZipFile(archive) as source, source.open(ARCHIVE_MEMBER) as member:
            csv_hasher = hashlib.sha256()
            while chunk := member.read(1024 * 1024):
                csv_hasher.update(chunk)
            csv_digest = csv_hasher.hexdigest()
        manifest = {
            "schema_version": 1,
            "source_kind": "original",
            "source_pin": pin.model_dump(mode="json"),
            "archive_url": ARCHIVE_URL,
            "archive_bytes": archive.stat().st_size,
            "csv_member": ARCHIVE_MEMBER,
            "csv_sha256": csv_digest,
            "taxonomy_url": TAXONOMY_URL,
            "taxonomy_version": TAXONOMY_VERSION,
            "policy_version": POLICY_VERSION,
            "code_revision": code_revision,
            "prepared_at_utc": datetime.now(UTC).isoformat(),
            "temporal_windows": {
                "development": ["2023-09-01", "2023-12-31"],
                "regression": ["2024-01-01", "2024-02-29"],
                "holdout": ["2024-03-01", "2024-03-31"],
            },
            "group_policy": (
                "NFKC/casefold/whitespace-normalized exact narrative; crossing groups quarantined"
            ),
            "profile": profile,
            "prepared": prepared,
            "files": {
                name: {
                    "sha256": digest_file(output / name),
                    "bytes": (output / name).stat().st_size,
                }
                for name in ("agent.sqlite", "evaluator.sqlite")
            },
            "limitations": LIMITATIONS,
        }
        with (output / "manifest.json").open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
        (output / "manifest.json").chmod(0o600)
        return manifest
    except BaseException:
        # Preserve private partial files for diagnosis. A retry must choose a new directory.
        raise


def verify_prepared(output: Path, expected_manifest_sha256: str) -> dict[str, Any]:
    output = external_path(output)
    if digest_file(output / "manifest.json") != expected_manifest_sha256:
        raise ValueError("Prepared manifest differs from externally supplied pin")
    manifest: dict[str, Any] = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    if (manifest["schema_version"], manifest["policy_version"], manifest["taxonomy_version"]) != (
        1,
        POLICY_VERSION,
        TAXONOMY_VERSION,
    ):
        raise ValueError("Prepared manifest version is incompatible")
    _verify_files(output, manifest)
    if inspect_prepared(output) != manifest["prepared"]:
        raise ValueError("Prepared aggregate evidence differs")
    # A concurrent writer between the initial hash and read cannot silently change the stores.
    _verify_files(output, manifest)
    if digest_file(output / "manifest.json") != expected_manifest_sha256:
        raise ValueError("Prepared manifest changed during verification")
    return manifest


def _verify_files(output: Path, manifest: dict[str, Any]) -> None:
    if {path.name for path in output.iterdir()} != {
        "agent.sqlite",
        "evaluator.sqlite",
        "manifest.json",
    }:
        raise ValueError("Prepared output inventory differs")
    for name in ("agent.sqlite", "evaluator.sqlite"):
        if {
            "sha256": digest_file(output / name),
            "bytes": (output / name).stat().st_size,
        } != manifest["files"][name]:
            raise ValueError("Prepared database differs from pinned manifest")
